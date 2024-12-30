#!/usr/bin/python
# gateway.py
#
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (gateway.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#
"""
.. module:: gateway.

This is a replacement for `lib.transport_control` stuff.
Here is place to put `outgoing` files to send to other users in the network.
Also this code receives a `incoming` files from other nodes.

Keeps a list of available `transports` - we use a plug-in system so you can
use external p2p, mech, or centralized networks to transfer files in different ways.

To identify user need to place his ID inside given external network to his public identity file.
So BitDust users can use different ways to communicate and transfer data.
BitDust code will use that module to talk with nodes in the network.

Seems like we faced with such situation -
BitDust software need to work together with other networks software on same machine.
This means we need to communicate between system processes - this is work for plug-ins.
So the idea is to make plug-ins code working inside the main process thread -
they just need to send/receive a short commands to another process in the OS.
So it must be atomic operations (or deferred) and do not use any resources.

And it seems like some plug-ins must have 2 parts:

    * BitDust python module with interface to do peers communications
    * external code to run the given network

Communication between both parts can be done in a different ways, I think XMLRPC can work for most cases.
We need to run XML-RPC on both sides because transport plug-in
must be able to respond to the main process too.

External network can be written in C++ or Java and the second part of the transport plig-in need to
deal with that and be portable.

Different networks provides various functions, something more than just transfer files.
Some of them uses DHT to store data on nodes - we can use that stuff also.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import open

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 24

_PacketLogFileEnabled = False

#------------------------------------------------------------------------------

import os
import time
import optparse

from twisted.web import xmlrpc
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred, maybeDeferred, succeed, fail

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.p2p import commands
from bitdust.p2p import p2p_service

from bitdust.lib import nameurl
from bitdust.lib import misc
from bitdust.lib import strng
from bitdust.lib import packetid

from bitdust.system import bpio
from bitdust.system import tmpfile

from bitdust.main import settings
from bitdust.main import config
from bitdust.main import events

from bitdust.crypt import signed

from bitdust.contacts import identitycache

from bitdust.transport import callback
from bitdust.transport import packet_in
from bitdust.transport import packet_out

from bitdust.userid import global_id
from bitdust.userid import identity
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_AvailableTransports = {}
_TransportsDict = {}
_LocalListener = None
_XMLRPCListener = None
_XMLRPCPort = None
_XMLRPCURL = ''
_LastTransferID = None
_LastInboxPacketTime = 0
_PacketsTimeOutTask = None
_TransportStateChangedCallbacksList = []
_TransportLogFile = None
_TransportLogFilename = None

#------------------------------------------------------------------------------


def init():
    global _LocalListener
    global _PacketLogFileEnabled
    if _Debug:
        lg.out(4, 'gateway.init')
    if _Debug:
        open_transport_log(settings.TransportLog())
    if _LocalListener:
        lg.warn('local listener already exist')
    else:
        _LocalListener = TransportGateLocalProxy()
    _PacketLogFileEnabled = config.conf().getBool('logs/packet-enabled')


def shutdown():
    """
    Shut down the gateway, need to stop all transports.
    """
    global _LocalListener
    global _XMLRPCListener
    global _XMLRPCPort
    global _XMLRPCURL
    global _PacketLogFileEnabled
    if _Debug:
        lg.out(4, 'gateway.shutdown')
    if _LocalListener:
        _LocalListener = None
    else:
        lg.warn('local listener not exist')
    if _Debug:
        close_transport_log()
    _PacketLogFileEnabled = False


#------------------------------------------------------------------------------


def transport(proto):
    global _TransportsDict
    proto = strng.to_text(proto)
    return _TransportsDict[proto]


def transports():
    global _TransportsDict
    return _TransportsDict


def listener():
    global _LocalListener
    return _LocalListener


def is_ready():
    """
    Return True if gateway is ready to run IN / OUT packets.
    """
    if not listener():
        return False
    return True


def is_installed(proto):
    """
    Return True if given transport is installed.
    """
    return proto in transports()


def can_send(proto):
    return transport(proto).state == 'LISTENING'


def last_inbox_time():
    global _LastInboxPacketTime
    return _LastInboxPacketTime


#------------------------------------------------------------------------------


def start():
    if _Debug:
        lg.out(4, 'gateway.start')
    callback.append_outbox_filter_callback(on_outbox_packet)
    callback.add_finish_file_receiving_callback(on_file_received)
    result = []
    for proto, transp in transports().items():
        if settings.transportIsEnabled(proto):
            if transp.state != 'LISTENING':
                if _Debug:
                    lg.out(4, '    sending "start" to %r' % transp)
                transp.automat('start')
                result.append(proto)
            else:
                if _Debug:
                    lg.out(4, '    %r is ready' % transp)
    reactor.callLater(5, packets_timeout_loop)  # @UndefinedVariable
    return result


def cold_start():
    if _Debug:
        lg.out(4, 'gateway.cold_start : sending "start" only to one transport - most preferable')
    callback.append_outbox_filter_callback(on_outbox_packet)
    callback.add_finish_file_receiving_callback(on_file_received)
    ordered_list = list(transports().keys())
    ordered_list.sort(key=settings.getTransportPriority, reverse=True)
    result = []
    for proto in ordered_list:
        transp = transport(proto)
        if settings.transportIsEnabled(proto):
            if transp.state != 'LISTENING':
                if _Debug:
                    lg.out(4, '    sending "start" to %r only' % transp)
                transp.automat('start')
                result.append(proto)
                break
            else:
                if _Debug:
                    lg.out(4, '    %r is ready, try next one' % transp)
    reactor.callLater(5, packets_timeout_loop)  # @UndefinedVariable
    return result


#------------------------------------------------------------------------------


def stop():
    if _Debug:
        lg.out(4, 'gateway.stop')
    stop_packets_timeout_loop()
    shutdown_all_inbox_packets()
    shutdown_all_outbox_packets()
    result = []
    for proto, transp in transports().items():
        if settings.transportIsEnabled(proto):
            if transp.state != 'OFFLINE':
                if _Debug:
                    lg.out(4, '    send "stop" to %r' % transp)
                transp.automat('stop')
                result.append(proto)
            else:
                if _Debug:
                    lg.out(4, '    %r already stopped' % proto)
    callback.remove_finish_file_receiving_callback(on_file_received)
    callback.remove_outbox_filter_callback(on_outbox_packet)
    return result


#------------------------------------------------------------------------------


def verify():
    ordered_list = list(transports().keys())
    ordered_list.sort(key=settings.getTransportPriority, reverse=True)
    if _Debug:
        lg.out(4, 'gateway.verify sorted list : %r' % ordered_list)
    my_id_obj = my_id.getLocalIdentity()
    resulted = Deferred()
    all_results = {}

    def _verify_transport(proto):
        if _Debug:
            lg.out(_DebugLevel - 2, '    verifying %s_transport' % proto)
        if not settings.transportIsEnabled(proto):
            if _Debug:
                lg.out(_DebugLevel - 2, '    %s_transport is disabled' % proto)
            return succeed(True)
        transp = transport(proto)
        if transp.state == 'OFFLINE':
            if _Debug:
                lg.out(_DebugLevel - 2, '    %s_transport state is OFFLINE' % proto)
            return succeed(True)
        if transp.state != 'LISTENING':
            if _Debug:
                lg.out(_DebugLevel - 2, '    %s_transport state is not LISTENING' % proto)
            return succeed(True)
        transp_result = transp.interface.verify_contacts(my_id_obj)
        if _Debug:
            lg.out(_DebugLevel - 2, '        %s result is %r' % (proto, transp_result))
        if isinstance(transp_result, bool) and transp_result:
            return succeed(True)
        if isinstance(transp_result, bool) and transp_result == False:
            return succeed(False)
        if isinstance(transp_result, Deferred):
            ret = Deferred()
            transp_result.addCallback(lambda result_value: ret.callback(result_value))
            return ret
        lg.warn('incorrect result returned from %s_interface.verify_contacts(): %r' % (proto, transp_result))
        return succeed(False)

    def _on_verified_one(t_result, proto):
        all_results[proto] = t_result
        if _Debug:
            lg.out(_DebugLevel - 2, '        verified %s transport, result=%r' % (proto, t_result))
        if len(all_results) == len(ordered_list):
            resulted.callback((ordered_list, all_results))

    for proto in ordered_list:
        d = _verify_transport(proto)
        d.addCallback(_on_verified_one, proto)

    return resulted


#------------------------------------------------------------------------------


def attach(transport_instance):
    global _TransportsDict
    global _AvailableTransports
    proto = strng.to_text(transport_instance.proto)
    _AvailableTransports[proto] = True
    _TransportsDict[proto] = transport_instance
    if _Debug:
        lg.out(4, 'gateway.attach : %r' % transport_instance)


def detach(transport_instance):
    global _TransportsDict
    global _AvailableTransports
    proto = strng.to_text(transport_instance.proto)
    if proto not in list(_AvailableTransports.keys()):
        lg.warn('transport [%s] not available' % proto)
        return
    if proto not in list(_TransportsDict.keys()):
        lg.warn('transport [%s] not attached' % proto)
        return
    _AvailableTransports.pop(proto)
    _TransportsDict.pop(proto)
    if _Debug:
        lg.out(4, 'gateway.detach : %r' % transport_instance)


#------------------------------------------------------------------------------


def inbox(info):
    """
    1) The protocol modules write to temporary files and gives us that filename
    2) We unserialize
    3) We check that it is for us
    4) We check that it is from one of our contacts.
    5) We use signed.validate() to check signature and that number fields are numbers
    6) Any other sanity checks we can do and if anything funny we toss out the packet
    7) Then change the filename to the PackedID that it should be
      and call the right function(s) for this new packet:
      (encryptedblock, scrubber, remotetester, customerservice, ...)
      to dispatch it to right place(s).
    """
    global _LastInboxPacketTime
    #     if _DoingShutdown:
    #         if _Debug:
    #             lg.out(_DebugLevel, "gateway.inbox ignoring input since _DoingShutdown ")
    #         return None
    if _Debug:
        lg.out(_DebugLevel, 'gateway.inbox [%s]' % info.filename)

    if info.filename == '' or not os.path.exists(info.filename):
        lg.err('bad filename=' + info.filename)
        return None
    try:
        data = bpio.ReadBinaryFile(info.filename)
    except:
        lg.err('gateway.inbox ERROR reading file ' + info.filename)
        return None
    if len(data) == 0:
        lg.err('gateway.inbox ERROR zero byte file from %s://%s' % (info.proto, info.host))
        return None
    if callback.run_finish_file_receiving_callbacks(info, data):
        lg.warn('incoming data of %d bytes was filtered out in file receiving callbacks' % len(data))
        return None
    try:
        newpacket = signed.Unserialize(data)
    except:
        lg.err('gateway.inbox ERROR during Unserialize data from %s://%s' % (info.proto, info.host))
        lg.exc()
        return None
    if newpacket is None:
        lg.warn('newpacket from %s://%s is None' % (info.proto, info.host))
        return None
    # newpacket.Valid() will be called later in the flow in packet_in.handle() method
    try:
        Command = newpacket.Command
        OwnerID = newpacket.OwnerID
        CreatorID = newpacket.CreatorID
        PacketID = newpacket.PacketID
        Date = newpacket.Date
        Payload = newpacket.Payload
        RemoteID = newpacket.RemoteID
        Signature = newpacket.Signature
        packet_sz = len(data)
    except:
        lg.err('gateway.inbox ERROR during Unserialize data from %s://%s' % (info.proto, info.host))
        lg.err('data length=' + str(len(data)))
        lg.exc()
        return None
    _LastInboxPacketTime = time.time()
    if _Debug:
        lg.out(_DebugLevel - 2, 'gateway.inbox [%s] signed by %s|%s (for %s) from %s://%s' % (Command, nameurl.GetName(OwnerID), nameurl.GetName(CreatorID), nameurl.GetName(RemoteID), info.proto, info.host))
    if _PacketLogFileEnabled:
        lg.out(
            0,
            '                \033[1;49;92mINBOX %s(%s) %s %s for %s\033[0m' % (
                newpacket.Command,
                newpacket.PacketID,
                global_id.UrlToGlobalID(newpacket.OwnerID),
                global_id.UrlToGlobalID(newpacket.CreatorID),
                global_id.UrlToGlobalID(newpacket.RemoteID),
            ),
            log_name='packet',
            showtime=True,
        )
    return newpacket


def outbox(
    outpacket,
    wide=False,
    callbacks={},
    target=None,
    route=None,
    response_timeout=None,
    keep_alive=True,
):
    """
    Sends `packet` to the network.

        :param outpacket: an instance of ``signed.Packet``
        :param wide:  set to True if you need to send the packet
                      to all contacts of Remote Identity
        :param callbacks: provide a callback methods to get response
                          here need to provide a callback for given command
                          callback arguments are: (response_packet, info)
        :param target:  if your recipient is not equal to outpacket.RemoteID
        :param route:   dict with parameters, you can manage how to process this packet:
                'packet': <another packet to be send>,
                'proto': <receiver proto>,
                'host': <receiver host>,
                'remoteid': <receiver idurl>,
                'description': <description on the packet>,
        :param response_timeout   None, or integer to indicate how long to wait for an ack

    Returns:
        `None` if data was not sent, no filter was applied
        `Deferred` object if filter was applied but sending was delayed
        `packet_out.PacketOut` object if packet was sent
    """
    if _Debug:
        lg.out(
            _DebugLevel, 'gateway.outbox [%s] signed by %s|%s to %s (%s), wide=%s' % (
                outpacket.Command,
                nameurl.GetName(outpacket.OwnerID),
                nameurl.GetName(outpacket.CreatorID),
                nameurl.GetName(outpacket.RemoteID),
                nameurl.GetName(target),
                wide,
            )
        )
    if _PacketLogFileEnabled:
        lg.out(
            0,
            '\033[1;49;96mOUTBOX %s(%s) %s %s to %s\033[0m' % (
                outpacket.Command,
                outpacket.PacketID,
                global_id.UrlToGlobalID(outpacket.OwnerID),
                global_id.UrlToGlobalID(outpacket.CreatorID),
                global_id.UrlToGlobalID(outpacket.RemoteID),
            ),
            log_name='packet',
            showtime=True,
        )
    return callback.run_outbox_filter_callbacks(
        outpacket,
        wide=wide,
        callbacks=callbacks,
        target=target,
        route=route,
        response_timeout=response_timeout,
        keep_alive=keep_alive,
    )


#------------------------------------------------------------------------------


def make_transfer_ID():
    """
    Generate a unique transfer ID.
    """
    global _LastTransferID
    if _LastTransferID is None:
        _LastTransferID = int(str(int(time.time()*100.0))[4:])
    _LastTransferID += 1
    return _LastTransferID


#------------------------------------------------------------------------------


def connect_to(proto, host):
    if not is_ready():
        return fail(Exception('gateway is not ready'))
    if not is_installed(proto):
        return fail(Exception('transport %r not installed' % proto))
    return transport(proto).call('connect_to', host)


def disconnect_from(proto, host):
    if not is_ready():
        return fail(Exception('gateway is not ready'))
    if not is_installed(proto):
        return fail(Exception('transport %r not installed' % proto))
    return transport(proto).call('disconnect_from', host)


def send_file(remote_idurl, proto, host, filename, description='', pkt_out=None):
    """
    Send a file to remote peer via given transport.

    Args:
        + proto (str): identifier of the transport
        + host (str): remote peer's host comes from identity contact
        + filename (str): local source file to be send
        + description (str): a label for this transfer
        + remote_idurl (idurl): remote user idurl (optional)
    """
    if not is_ready():
        lg.warn('gateway is not ready')
        return False
    if not is_installed(proto):
        lg.warn('transport %r not installed' % proto)
        return False
    filtered = callback.run_file_sending_filter_callbacks(remote_idurl, proto, host, filename, description, pkt_out)
    if filtered is not None:
        return filtered
    result_defer = transport(proto).call('send_file', remote_idurl, filename, host, description)
    callback.run_begin_file_sending_callbacks(result_defer, remote_idurl, proto, host, filename, description, pkt_out)
    return True


def send_file_single(remote_idurl, proto, host, filename, description='', pkt_out=None):
    if not is_ready():
        lg.warn('gateway is not ready')
        return False
    if not is_installed(proto):
        lg.warn('transport %r not installed' % proto)
        return False
    result_defer = transport(proto).call('send_file_single', remote_idurl, filename, host, description)
    callback.run_begin_file_sending_callbacks(result_defer, remote_idurl, proto, host, filename, description, pkt_out)
    return True


def send_keep_alive(proto, host):
    if not is_ready():
        lg.warn('gateway is not ready')
        return False
    if not is_installed(proto):
        lg.warn('transport %r not installed' % proto)
        return False
    transport(proto).call('send_keep_alive', host)
    return True


def list_active_transports():
    if not is_ready():
        return fail(Exception('gateway is not ready'))
    result = []
    for proto, transp in transports().items():
        if settings.transportIsEnabled(proto):
            if transp.state != 'OFFLINE':
                result.append(proto)
    return result


def list_active_sessions(proto):
    if not is_ready():
        return fail(Exception('gateway is not ready'))
    if not is_installed(proto):
        return fail(Exception('transport %r not installed' % proto))
    return transport(proto).call('list_sessions')


def list_active_streams(proto):
    if not is_ready():
        return fail(Exception('gateway is not ready'))
    if not is_installed(proto):
        return fail(Exception('transport %r not installed' % proto))
    return transport(proto).call('list_streams')


def find_active_session(proto, host=None, idurl=None):
    if not is_ready():
        # return fail(Exception('gateway is not ready'))
        lg.warn('gateway is not ready')
        return None
    if not is_installed(proto):
        # return fail(Exception('transport %r not installed' % proto))
        lg.warn('transport %r not installed' % proto)
        return None
    return transport(proto).call('find_session', host, idurl)


def find_active_stream(proto, stream_id=None, transfer_id=None):
    if not is_ready():
        lg.warn('gateway is not ready')
        return None
    if not is_installed(proto):
        lg.warn('transport %r not installed' % proto)
        return None
    return transport(proto).call('find_stream', stream_id=stream_id, transfer_id=transfer_id)


#------------------------------------------------------------------------------


def cancel_input_file(transferID, why=None):
    pkt_in = packet_in.get(transferID)
    assert pkt_in is not None
    if _Debug:
        lg.out(_DebugLevel, 'gateway.cancel_input_file : %s why: %s' % (transferID, why))
    pkt_in.automat('cancel', why)
    return True


def cancel_outbox_file(proto, host, filename, why=None):
    pkt_out, _ = packet_out.search(proto, host, filename)
    if pkt_out is None:
        lg.err('gateway.cancel_outbox_file ERROR packet_out not found: %r' % ((proto, host, filename), ))
        return None
    if _Debug:
        lg.out(_DebugLevel, 'gateway.cancel_outbox_file : %s:%s %s, why: %s' % (proto, host, filename, why))
    pkt_out.automat('cancel', why)


def cancel_outbox_file_by_transfer_id(transferID, why=None):
    pkt_out, _ = packet_out.search_by_transfer_id(transferID)
    if pkt_out is None:
        lg.warn('%s is not found' % str(transferID))
        return False
    if _Debug:
        lg.out(_DebugLevel, 'gateway.cancel_outbox_file_by_transfer_id : %s' % transferID)
    pkt_out.automat('cancel', why)
    return True


#------------------------------------------------------------------------------


def current_bytes_sent():
    res = {}
    for pkt_out in packet_out.queue():
        for item in pkt_out.items:
            if item.transfer_id:
                res[item.transfer_id] = pkt_out.payloadsize
    return res


def current_bytes_received():
    res = {}
    for pkt_in in list(packet_in.inbox_items().values()):
        res[pkt_in.transfer_id] = pkt_in.size
    return res


#------------------------------------------------------------------------------


def shutdown_all_outbox_packets():
    if _Debug:
        lg.out(_DebugLevel, 'gateway.shutdown_all_outbox_packets, %d live objects at the moment' % len(packet_out.queue()))
    for pkt_out in list(packet_out.queue()):
        pkt_out.event('cancel', 'shutdown')


def shutdown_all_inbox_packets():
    if _Debug:
        lg.out(_DebugLevel, 'gateway.shutdown_all_inbox_packets, %d live objects at the moment' % len(list(packet_in.inbox_items().values())))
    for pkt_in in list(packet_in.inbox_items().values()):
        pkt_in.event('cancel', 'shutdown')


#------------------------------------------------------------------------------


def packets_timeout_loop():
    global _PacketsTimeOutTask
    delay = 30
    _PacketsTimeOutTask = reactor.callLater(delay, packets_timeout_loop)  # @UndefinedVariable
    for pkt_in in list(packet_in.inbox_items().values()):
        if pkt_in.is_timed_out():
            if _Debug:
                lg.out(_DebugLevel, 'gateway.packets_timeout_loop %r is timed out: %s' % (pkt_in, pkt_in.timeout))
            pkt_in.automat('cancel', 'timeout')
    for pkt_out in packet_out.queue():
        if pkt_out.is_timed_out():
            if _Debug:
                lg.out(_DebugLevel, 'gateway.packets_timeout_loop %r is timed out: %s' % (pkt_out, pkt_out.timeout))
            pkt_out.automat('cancel', 'timeout')


def stop_packets_timeout_loop():
    global _PacketsTimeOutTask
    if _PacketsTimeOutTask:
        if _PacketsTimeOutTask.active():
            _PacketsTimeOutTask.cancel()
        _PacketsTimeOutTask = None


#------------------------------------------------------------------------------


def monitoring():
    list_pkt_in = []
    for pkt_in in list(packet_in.inbox_items().values()):
        list_pkt_in.append(pkt_in.label)
    list_pkt_out = []
    for pkt_out in packet_out.queue():
        list_pkt_out.append(pkt_out.label)
    if _Debug:
        if transport_log() and list_pkt_out and list_pkt_in:
            dt = time.time() - lg.when_life_begins()
            mn = dt // 60
            sc = dt - mn*60
            transport_log().write(u'%02d:%02d    in: %s   out: %s\n' % (mn, sc, list_pkt_in, list_pkt_out))
            transport_log().flush()


#------------------------------------------------------------------------------


def on_file_received(info, data):
    if _Debug:
        lg.dbg(_DebugLevel, 'received %d bytes in %s' % (len(data), info))
    return False


def on_identity_received(newpacket, send_ack=True):
    """
    A normal node or identity server is sending us a new copy of an identity for a contact of ours.
    Checks that identity is signed correctly.
    This will be also sending requests to cache all sources (other identity servers) holding that identity.
    """
    # TODO:  move to service_gateway
    newxml = newpacket.Payload
    newidentity = identity.identity(xmlsrc=newxml)
    # SECURITY
    # check that identity is signed correctly
    # old public key matches new one
    # this is done in `UpdateAfterChecking()`
    idurl = newidentity.getIDURL()
    if not identitycache.HasKey(idurl):
        lg.info('received new identity %s rev %r' % (idurl, newidentity.getRevisionValue()))
    if my_id.isLocalIdentityReady():
        if newidentity.getPublicKey() == my_id.getLocalIdentity().getPublicKey():
            if newidentity.getRevisionValue() > my_id.getLocalIdentity().getRevisionValue():
                lg.warn('received my own identity from another user, but with higher revision number')
                reactor.callLater(0, my_id.rebuildLocalIdentity, new_revision=newidentity.getRevisionValue() + 1)  # @UndefinedVariable
                return False
    if not identitycache.UpdateAfterChecking(idurl, newxml):
        lg.warn('ERROR has non-Valid identity')
        return False
    latest_identity = id_url.get_latest_ident(newidentity.getPublicKey())
    if latest_identity:
        if latest_identity.getRevisionValue() > newidentity.getRevisionValue():
            # check if received identity is the most recent revision number we ever saw for that remote user
            # in case we saw same identity with higher revision number need to reply with Fail packet and notify user
            # this may happen after identity restore - the user starts counting revision number from 0
            # but other nodes already store previous copies, user just need to jump to the most recent revision number
            lg.warn('received new identity with out-dated revision number %d from %r, known revision is %d' % (newidentity.getRevisionValue(), idurl, latest_identity.getRevisionValue()))
            lg.warn('received identity: %r' % newxml)
            lg.warn('known identity: %r' % latest_identity.serialize())
            ident_packet = signed.Packet(
                Command=commands.Identity(),
                OwnerID=latest_identity.getIDURL(),
                CreatorID=latest_identity.getIDURL(),
                PacketID='identity:%s' % packetid.UniqueID(),
                Payload=latest_identity.serialize(),
                RemoteID=idurl,
            )
            reactor.callLater(0, packet_out.create, outpacket=ident_packet, wide=True, callbacks={}, keep_alive=False)  # @UndefinedVariable
            return False
    # Now that we have ID we can check the packet
    if not newpacket.Valid():
        # If not valid do nothing
        lg.warn('not Valid packet from %s' % idurl)
        return False
    if not send_ack:
        if _Debug:
            lg.dbg(_DebugLevel, '%s  idurl=%s  remoteID=%r  skip sending Ack()' % (newpacket.PacketID, idurl, newpacket.RemoteID))
        return True
    if newpacket.OwnerID == idurl:
        if _Debug:
            lg.dbg(_DebugLevel, '%s  idurl=%s  remoteID=%r  sending wide Ack()' % (newpacket.PacketID, idurl, newpacket.RemoteID))
    else:
        if _Debug:
            lg.dbg(_DebugLevel, '%s  idurl=%s  remoteID=%r  but packet ownerID=%s   sending wide Ack()' % (newpacket.PacketID, idurl, newpacket.RemoteID, newpacket.OwnerID))
    # wide=True : a small trick to respond to all known contacts of the remote user
    reactor.callLater(0, p2p_service.SendAck, newpacket, wide=True)  # @UndefinedVariable
    return True


def on_outbox_packet(outpacket, wide, callbacks, target=None, route=None, response_timeout=None, keep_alive=True):
    started_packets = packet_out.search_similar_packets(outpacket)
    if started_packets:
        for active_packet, _ in started_packets:
            if active_packet.outpacket and active_packet.outpacket.Command in [commands.Ack(), commands.Fail()]:
                continue
            if callbacks:
                for command, cb in callbacks.items():
                    active_packet.set_callback(command, cb)
            lg.warn('skip creating new outbox packet because found similar pending packet: %r' % active_packet)
            return active_packet
    pkt_out = packet_out.create(outpacket, wide, callbacks, target, route, response_timeout, keep_alive)
    # control.request_update([('packet', outpacket.PacketID)])
    return pkt_out


def on_transport_state_changed(transport, oldstate, newstate):
    global _TransportStateChangedCallbacksList
    if _Debug:
        lg.out(_DebugLevel - 2, 'gateway.on_transport_state_changed in %r : %s->%s' % (transport, oldstate, newstate))
    from bitdust.p2p import network_connector
    if network_connector.A():
        network_connector.A('network-transport-state-changed', transport)
    for cb in _TransportStateChangedCallbacksList:
        cb(transport, oldstate, newstate)


def on_transport_initialized(proto, xmlrpcurl=None):
    transport(proto).automat('transport-initialized', xmlrpcurl)
    events.send('gateway-transport-initialized', data=dict(
        proto=proto,
        rpc_url=xmlrpcurl,
    ))
    return True


def on_receiving_started(proto, host, options_modified=None):
    if _Debug:
        lg.out(_DebugLevel - 2, 'gateway.on_receiving_started %r host=%r' % (proto.upper(), host))
    transport(proto).automat('receiving-started', (proto, host, options_modified))
    events.send('gateway-receiving-started', data=dict(
        proto=proto,
        host=host,
        options=options_modified,
    ))
    return True


def on_receiving_failed(proto, error_code=None):
    if _Debug:
        lg.out(_DebugLevel - 2, 'gateway.on_receiving_failed %s    error=[%s]' % (proto.upper(), str(error_code)))
    transport(proto).automat('failed')
    events.send('gateway-receiving-failed', data=dict(
        proto=proto,
        error=error_code,
    ))
    return True


def on_disconnected(proto, result=None):
    if _Debug:
        lg.out(_DebugLevel - 2, 'gateway.on_disconnected %s    result=%s' % (proto.upper(), str(result)))
    if proto in transports():
        transport(proto).automat('stopped')
    events.send('gateway-disconnected', data=dict(
        proto=proto,
        result=result,
    ))
    return True


def on_start_connecting(host):
    return True


def on_session_opened(host, remote_user_id):
    pass


def on_connection_failed(host, error_message=None):
    pass


def on_session_closed(host, remote_user_id, reason=None):
    pass


def on_message_received(host, remote_user_id, data):
    pass


def on_register_file_sending(proto, host, receiver_idurl, filename, size=0, description=''):
    """
    Called from transport plug-in when sending of a single file started towards remote peer.
    Must return a unique transfer ID so plug-in will know that ID.
    After finishing that given transfer - that ID is passed to `unregister_file_sending()`.
    Need to first find existing outgoing packet and register that item.
    """
    if _Debug:
        lg.out(_DebugLevel, 'gateway.on_register_file_sending %s %s to %r' % (filename, description, receiver_idurl))


#     if id_url.field(receiver_idurl).to_bin() == my_id.getIDURL().to_bin():
#         pkt_out, work_item = packet_out.search(proto, host, filename)
#     else:
#         pkt_out, work_item = packet_out.search(proto, host, filename, remote_idurl=receiver_idurl)
    pkt_out, work_item = packet_out.search(proto, host, filename)
    if pkt_out is None:
        lg.warn('skip register file sending, packet_out not found: %r %r %r %r' % (proto, host, os.path.basename(filename), receiver_idurl))
        return None
    transfer_id = make_transfer_ID()
    if _Debug:
        lg.out(_DebugLevel, '... OUT ... %s (%d) send {%s} via [%s] to %s at %s' % (pkt_out.description, transfer_id, os.path.basename(filename), proto, nameurl.GetName(receiver_idurl), host))
    pkt_out.automat('register-item', (proto, host, filename, transfer_id))
    # control.request_update([('stream', transfer_id)])
    return transfer_id


def on_unregister_file_sending(transfer_id, status, bytes_sent, error_message=None):
    """
    Called from transport plug-in after finish sending a single file.
    """
    if transfer_id is None:
        return False
    if _Debug:
        lg.out(_DebugLevel, 'gateway.on_unregister_file_sending %s %s' % (transfer_id, status))
    pkt_out, work_item = packet_out.search_by_transfer_id(transfer_id)
    if pkt_out is None:
        if _Debug:
            lg.out(_DebugLevel, '        %s is not found' % str(transfer_id))
        return False
    pkt_out.automat('unregister-item', (transfer_id, status, bytes_sent, error_message))
    # control.request_update([('stream', transfer_id)])
    if status == 'finished':
        if _Debug:
            lg.out(_DebugLevel, '>>> OUT >>> %s (%d) [%s://%s] %s with %d bytes' % (pkt_out.description, transfer_id, work_item.proto, work_item.host, status.upper(), bytes_sent))
    else:
        if _Debug:
            lg.out(_DebugLevel, '>>> OUT >>> %s (%d) [%s://%s] %s : %s' % (pkt_out.description, transfer_id, work_item.proto, work_item.host, str(status).upper(), error_message))
    return True


def on_cancelled_file_sending(proto, host, filename, size, description='', error_message=None):
    pkt_out, work_item = packet_out.search(proto, host, filename)
    if pkt_out is None:
        if _Debug:
            lg.out(_DebugLevel, 'gateway.on_cancelled_file_sending packet_out %s %s %s not found - IT IS OK' % (proto, host, os.path.basename(filename)))
        return True
    pkt_out.automat('item-cancelled', (
        proto,
        host,
        filename,
        size,
        description,
        error_message,
    ))
    # if pkt_out.outpacket:
    #     control.request_update([('packet', pkt_out.outpacket.PacketID)])
    if _Debug:
        lg.out(_DebugLevel, '>>> OUT >>>  {%s} CANCELLED via [%s] to %s : %s' % (os.path.basename(filename), proto, host, error_message))
    return True


def on_register_file_receiving(proto, host, sender_idurl, filename, size=0):
    """
    Called from transport plug-in when receiving a single file were started
    from some peer.

    Must return a unique transfer ID, create a `FileTransferInfo` object
    and put it into "transfers" list. Plug-in's code must create a
    temporary file and write incoming data into that file.
    """
    transfer_id = make_transfer_ID()
    if _Debug:
        lg.out(_DebugLevel, '... IN ... %d receive {%s} via [%s] from %s at %s' % (transfer_id, os.path.basename(filename), proto, nameurl.GetName(sender_idurl), host))
    incoming_packet = packet_in.create(transfer_id)
    incoming_packet.event('register-item', (proto, host, sender_idurl, filename, size))
    # control.request_update([('stream', transfer_id)])
    return transfer_id


def on_unregister_file_receiving(transfer_id, status, bytes_received, error_message=''):
    """
    Called from transport plug-in after finish receiving a single file.
    """
    pkt_in = packet_in.get(transfer_id)
    if not pkt_in:
        lg.exc(exc_value=Exception('incoming packet with transfer_id=%r not exist' % transfer_id))
        return False
    if _Debug:
        if status == 'finished':
            lg.out(_DebugLevel, '<<< IN <<< (%d) [%s://%s] %s with %d bytes' % (transfer_id, pkt_in.proto, pkt_in.host, status.upper(), bytes_received))
        else:
            lg.out(_DebugLevel, '<<< IN <<< (%d) [%s://%s] %s : %s' % (transfer_id, pkt_in.proto, pkt_in.host, status.upper(), error_message))
    pkt_in.automat('unregister-item', (status, bytes_received, error_message))
    # control.request_update([('stream', transfer_id)])
    return True


#------------------------------------------------------------------------------


def add_transport_state_changed_callback(cb):
    global _TransportStateChangedCallbacksList
    if cb not in _TransportStateChangedCallbacksList:
        _TransportStateChangedCallbacksList.append(cb)


def remove_transport_state_changed_callback(cb):
    global _TransportStateChangedCallbacksList
    if cb in _TransportStateChangedCallbacksList:
        _TransportStateChangedCallbacksList.remove(cb)


#------------------------------------------------------------------------------


def open_transport_log(filename):
    global _TransportLogFile
    global _TransportLogFilename
    if _TransportLogFile:
        return
    _TransportLogFilename = filename
    try:
        _TransportLogFile = open(_TransportLogFilename, 'w')
    except:
        _TransportLogFile = None


def close_transport_log():
    global _TransportLogFile
    if not _TransportLogFile:
        return
    _TransportLogFile.flush()
    _TransportLogFile.close()
    _TransportLogFile = None
    _TransportLogFilename = None


def transport_log():
    global _TransportLogFile
    return _TransportLogFile


#------------------------------------------------------------------------------


class TransportGateLocalProxy():

    """
    A class to handle calls from transport plug-ins in the main thread.
    """

    def __init__(self):
        self.methods = {
            'transport_initialized': on_transport_initialized,
            'receiving_started': on_receiving_started,
            'receiving_failed': on_receiving_failed,
            'disconnected': on_disconnected,
            'start_connecting': on_start_connecting,
            'session_opened': on_session_opened,
            'message_received': on_message_received,
            'connection_failed': on_connection_failed,
            'register_file_sending': on_register_file_sending,
            'unregister_file_sending': on_unregister_file_sending,
            'register_file_receiving': on_register_file_receiving,
            'unregister_file_receiving': on_unregister_file_receiving,
            'cancelled_file_sending': on_cancelled_file_sending,
        }

    def callRemote(self, method, *args):
        m = self.methods.get(method)
        if not m:
            lg.warn('unsupported method: %s' % method)
            return fail(Exception('unsupported method: %s' % method))
        _d = Deferred()

        def _call(meth):
            if _Debug:
                lg.args(_DebugLevel, method=meth, args=args)
            r = maybeDeferred(m, *args)
            r.addCallback(_d.callback)
            r.addErrback(_d.errback)

        reactor.callLater(0, _call, method)  # @UndefinedVariable
        return _d


#------------------------------------------------------------------------------


class TransportGateXMLRPCServer(xmlrpc.XMLRPC):

    """
    XML-RPC server to receive calls from transport plug-ins.
    """

    def __init__(self):
        xmlrpc.XMLRPC.__init__(self, allowNone=True)
        self.methods = {
            'transport_initialized': on_transport_initialized,
            'receiving_started': on_receiving_started,
            'receiving_failed': on_receiving_failed,
            'disconnected': on_disconnected,
            'start_connecting': on_start_connecting,
            'session_opened': on_session_opened,
            'message_received': on_message_received,
            'connection_failed': on_connection_failed,
            'register_file_sending': on_register_file_sending,
            'unregister_file_sending': on_unregister_file_sending,
            'register_file_receiving': on_register_file_receiving,
            'unregister_file_receiving': on_unregister_file_receiving,
            'cancelled_file_sending': on_cancelled_file_sending,
        }

    def lookupProcedure(self, procedurePath):
        try:
            return self.methods[procedurePath]
        except KeyError as e:
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND, 'procedure %s not found: %s' % (procedurePath, e))

    def listProcedures(self):
        return list(self.methods.keys())


#------------------------------------------------------------------------------


def parseCommandLine():
    oparser = optparse.OptionParser()
    oparser.add_option('-d', '--debug', dest='debug', type='int', help='set debug level')
    oparser.set_default('debug', 10)
    oparser.add_option('-t', '--tcpport', dest='tcpport', type='int', help='specify port for TCP transport')
    oparser.set_default('tcpport', settings.getTCPPort())
    oparser.add_option('-u', '--udpport', dest='udpport', type='int', help='specify port for UDP transport')
    oparser.set_default('udpport', settings.getUDPPort())
    oparser.add_option('-p', '--dhtport', dest='dhtport', type='int', help='specify UDP port for DHT network')
    oparser.set_default('dhtport', settings.getDHTPort())
    oparser.add_option('-s', '--packetsize', dest='packetsize', type='int', help='set size of UDP datagrams')
    oparser.set_default('packetsize', 480)
    (options, args) = oparser.parse_args()
    return options, args


#------------------------------------------------------------------------------


def main():
    lg.life_begins()
    bpio.init()
    settings.init()
    misc.init()
    my_id.init()
    identitycache.init()
    from bitdust.crypt import key
    key.InitMyKey()
    (options, args) = parseCommandLine()
    settings.override('transport.transport-tcp.transport-tcp-port', options.tcpport)
    settings.override('transport.transport-udp.transport-udp-port', options.udpport)
    settings.override('network.network-dht-port', options.dhtport)
    lg.set_debug_level(options.debug)
    tmpfile.init()
    if True:
        import bitdust.lib.udp
        bitdust.lib.udp.listen(options.udpport)
        import bitdust.dht.dht_service
        bitdust.dht.dht_service.init(options.dhtport)
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)  # @UndefinedVariable
    init()
    start()
    globals()['num_in'] = 0

    def _in(a, b, c, d):
        lg.out(2, 'INBOX %d : %r' % (globals()['num_in'], a))
        globals()['num_in'] += 1
        return False

    callback.insert_inbox_callback(0, _in)
    if len(args) > 0:
        globals()['num_out'] = 0

        def _s():
            p = signed.Packet(commands.Data(), my_id.getIDURL(), my_id.getIDURL(), my_id.getIDURL(), bpio.ReadBinaryFile(args[1]), args[0])
            outbox(p, wide=True)
            lg.out(2, 'OUTBOX %d : %r' % (globals()['num_out'], p))
            globals()['num_out'] += 1

        old_state_changed = transport('udp').state_changed

        def new_state_changed(oldstate, newstate, event, *args, **kwargs):
            old_state_changed(oldstate, newstate, event, *args, **kwargs)
            if newstate == 'LISTENING':
                reactor.callLater(1, _s)  # @UndefinedVariable

        transport('udp').state_changed = new_state_changed
        # t = task.LoopingCall(_s)
        # reactor.callLater(5, t.start, 60, True)
        # reactor.callLater(2, t.stop)

    reactor.run()  # @UndefinedVariable
    settings.shutdown()


#------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
