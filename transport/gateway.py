#!/usr/bin/python
# gateway.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import time
import optparse

from twisted.web import xmlrpc
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred, succeed
from twisted.internet.defer import maybeDeferred
from twisted.internet.defer import fail

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from p2p import commands

from lib import nameurl
from lib import misc
from lib import strng

from system import bpio
from system import tmpfile

from main import settings
from main import control
from main import events

from crypt import signed

from userid import my_id

from contacts import identitycache

from transport import callback
from transport import packet_in
from transport import packet_out

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


def transport(proto):
    """
    """
    global _TransportsDict
    proto = strng.to_text(proto)
    return _TransportsDict[proto]


def transports():
    """
    """
    global _TransportsDict
    return _TransportsDict


def listener():
    """
    """
    global _LocalListener
    return _LocalListener


def is_installed(proto):
    """
    Return True if given transport is installed.
    """
    return proto in transports()


def can_send(proto):
    """
    """
    return transport(proto).state == 'LISTENING'


def last_inbox_time():
    """
    """
    global _LastInboxPacketTime
    return _LastInboxPacketTime

#------------------------------------------------------------------------------


def init():
    """
    """
    global _LocalListener
    if _Debug:
        lg.out(4, 'gateway.init')
    open_transport_log(settings.TransportLog())
    if _LocalListener:
        lg.warn('local listener already exist')
    else:
        _LocalListener = TransportGateLocalProxy()


def shutdown():
    """
    Shut down the gateway, need to stop all transports.
    """
    global _LocalListener
    global _XMLRPCListener
    global _XMLRPCPort
    global _XMLRPCURL
    if _Debug:
        lg.out(4, 'gateway.shutdown')
    if _LocalListener:
        _LocalListener = None
    else:
        lg.warn('local listener not exist')
    close_transport_log()


def start():
    """
    """
    if _Debug:
        lg.out(4, 'gateway.start')
    callback.append_outbox_filter_callback(on_outbox_packet)
    callback.add_finish_file_receiving_callback(on_file_received)
    result = []
    for proto, transp in transports().items():
        if settings.transportIsEnabled(proto):
            if transp.state != 'LISTENING':
                if _Debug:
                    lg.out(4, '    sending "start" to %s' % transp)
                transp.automat('start')
                result.append(proto)
            else:
                if _Debug:
                    lg.out(4, '    %r is ready' % transp)
    reactor.callLater(5, packets_timeout_loop)  # @UndefinedVariable
    return result


def cold_start():
    """
    """
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
                    lg.out(4, '    sending "start" to %s and stop' % transp)
                transp.automat('start')
                result.append(proto)
                break
            else:
                if _Debug:
                    lg.out(4, '    %r is ready, try next one' % transp)
    reactor.callLater(5, packets_timeout_loop)  # @UndefinedVariable
    return result


def stop():
    """
    """
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
                    lg.out(4, '    send "stop" to %s' % transp)
                transp.automat('stop')
                result.append(proto)
            else:
                if _Debug:
                    lg.out(4, '    %s already stopped' % proto)
    callback.remove_finish_file_receiving_callback(on_file_received)
    callback.remove_outbox_filter_callback(on_outbox_packet)
    return result


def verify():
    """
    """
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
    """
    """
    global _TransportsDict
    global _AvailableTransports
    proto = strng.to_text(transport_instance.proto)
    _AvailableTransports[proto] = True
    _TransportsDict[proto] = transport_instance
    if _Debug:
        lg.out(4, 'gateway.attach : %r' % transport_instance)


def detach(transport_instance):
    """
    """
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
    2) We unserialize 3) We check that it is for us 4) We check that it is from
    one of our contacts.

    5) We use signed.validate() to check signature and that number
    fields are numbers 6) Any other sanity checks we can do and if
    anything funny we toss out the packet . 7) Then change the filename
    to the PackedID that it should be.    and call the right function(s)
    for this new packet    (encryptedblock, scrubber, remotetester,
    customerservice, ...)    to dispatch it to right place(s). 8) We
    have to keep track of bandwidth to/from everyone, and make a report
    every 24 hours    which we send to BitDust sometime in the 24 hours
    after that.
    """
    global _LastInboxPacketTime
#     if _DoingShutdown:
#         if _Debug:
#             lg.out(_DebugLevel, "gateway.inbox ignoring input since _DoingShutdown ")
#         return None
    if _Debug:
        lg.out(_DebugLevel, "gateway.inbox [%s]" % info.filename)

    if info.filename == "" or not os.path.exists(info.filename):
        lg.err("bad filename=" + info.filename)
        return None
    try:
        data = bpio.ReadBinaryFile(info.filename)
    except:
        lg.err("gateway.inbox ERROR reading file " + info.filename)
        return None
    if len(data) == 0:
        lg.err("gateway.inbox ERROR zero byte file from %s://%s" % (info.proto, info.host))
        return None
    if callback.run_finish_file_receiving_callbacks(info, data):
        lg.warn('incoming data of %d bytes was filtered out in file receiving callbacks' % len(data))
        return None
    try:
        newpacket = signed.Unserialize(data)
    except:
        lg.err("gateway.inbox ERROR during Unserialize data from %s://%s" % (info.proto, info.host))
        lg.exc()
        return None
    if newpacket is None:
        lg.warn("newpacket from %s://%s is None" % (info.proto, info.host))
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
        lg.err("gateway.inbox ERROR during Unserialize data from %s://%s" % (info.proto, info.host))
        lg.err("data length=" + str(len(data)))
        lg.exc()
#         fd, filename = tmpfile.make('other', '.bad')
#         os.write(fd, data)
#         os.close(fd)
        return None
    _LastInboxPacketTime = time.time()
    if _Debug:
        lg.out(_DebugLevel - 2, "gateway.inbox [%s] signed by %s|%s (for %s) from %s://%s" % (
            Command,
            nameurl.GetName(OwnerID),
            nameurl.GetName(CreatorID),
            nameurl.GetName(RemoteID),
            info.proto, info.host))
    if _Debug and lg.is_debug(_DebugLevel):
        monitoring()
    # control.request_update([('packet', newpacket.PacketID)])
    return newpacket


def outbox(outpacket, wide=False, callbacks={}, target=None, route=None, response_timeout=None, keep_alive=True, ):
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
        lg.out(_DebugLevel - 2, "gateway.outbox [%s] signed by %s|%s to %s (%s), wide=%s" % (
            outpacket.Command,
            nameurl.GetName(outpacket.OwnerID),
            nameurl.GetName(outpacket.CreatorID),
            nameurl.GetName(outpacket.RemoteID),
            nameurl.GetName(target),
            wide,))
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
        _LastTransferID = int(str(int(time.time() * 100.0))[4:])
    _LastTransferID += 1
    return _LastTransferID

#------------------------------------------------------------------------------

def send_work_item(proto, host, filename, description):
    """
    Send a file to remote peer by given transport.

    Args:     proto (str): identifier of the transport     host (str):
    remote peer's host comes from identity contact     filename (str):
    local source file to be send     description (str): a label for this
    transfer
    """
    return send_file(proto, host, filename, description)


def connect_to(proto, host):
    """
    """
    return transport(proto).call('connect_to', host)


def disconnect_from(proto, host):
    """
    """
    return transport(proto).call('disconnect_from', host)


def send_file(remote_idurl, proto, host, filename, description='', pkt_out=None):
    """
    """
    result_defer = transport(proto).call('send_file', remote_idurl, filename, host, description)
    callback.run_begin_file_sending_callbacks(result_defer, remote_idurl, proto, host, filename, description, pkt_out)
    return result_defer


def send_file_single(remote_idurl, proto, host, filename, description='', pkt_out=None):
    """
    """
    result_defer = transport(proto).call('send_file_single', remote_idurl, filename, host, description)
    callback.run_begin_file_sending_callbacks(result_defer, remote_idurl, proto, host, filename, description, pkt_out)
    return result_defer


def send_keep_alive(proto, host):
    """
    """
    return transport(proto).call('send_keep_alive', host)


def list_active_transports():
    """
    """
    result = []
    for proto, transp in transports().items():
        if settings.transportIsEnabled(proto):
            if transp.state != 'OFFLINE':
                result.append(proto)
    return result


def list_active_sessions(proto):
    """
    """
    return transport(proto).call('list_sessions')


def list_active_streams(proto):
    """
    """
    return transport(proto).call('list_streams')


def find_active_session(proto, host):
    """
    """
    return transport(proto).call('find_session', host)

def find_active_stream(proto, stream_id=None, transfer_id=None):
    """
    """
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
        lg.err('gateway.cancel_outbox_file ERROR packet_out not found: %r' % ((proto, host, filename),))
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
    # for transfer_id, info in transfers_out().items():
    #     res[transfer_id] = info.size
    for pkt_out in packet_out.queue():
        for item in pkt_out.items:
            if item.transfer_id:
                res[item.transfer_id] = pkt_out.payloadsize
    return res


def current_bytes_received():
    res = {}
    # for transfer_id, info in transfers_in().items():
    #     res[transfer_id] = info.size
    for pkt_in in list(packet_in.inbox_items().values()):
        res[pkt_in.transfer_id] = pkt_in.size
    return res

#------------------------------------------------------------------------------


def shutdown_all_outbox_packets():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'gateway.shutdown_all_outbox_packets, %d live objects at the moment' % len(packet_out.queue()))
    for pkt_out in list(packet_out.queue()):
        pkt_out.event('cancel', 'shutdown')


def shutdown_all_inbox_packets():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'gateway.shutdown_all_inbox_packets, %d live objects at the moment' % (
            len(list(packet_in.inbox_items().values())), ))
    for pkt_in in list(packet_in.inbox_items().values()):
        pkt_in.event('cancel', 'shutdown')

#------------------------------------------------------------------------------


def packets_timeout_loop():
    global _PacketsTimeOutTask
    # lg.out(18, 'gateway.packets_timeout_loop')
    delay = 5
    if _Debug:
        delay = 1
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
    if _Debug and lg.is_debug(_DebugLevel):
        monitoring()


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
    if transport_log() and list_pkt_out and list_pkt_in:
        dt = time.time() - lg.when_life_begins()
        mn = dt // 60
        sc = dt - mn * 60
        transport_log().write(u'%02d:%02d    in: %s   out: %s\n' % (
            mn, sc, list_pkt_in, list_pkt_out))
        transport_log().flush()

#------------------------------------------------------------------------------


def on_file_received(info, data):
    if _Debug:
        lg.out(_DebugLevel, '~~~~ received %d bytes in %s' % (len(data), info))
    return False


def on_outbox_packet(outpacket, wide, callbacks, target=None, route=None, response_timeout=None, keep_alive=True):
    """
    """
    started_packets = packet_out.search_similar_packets(outpacket)
    if started_packets:
        for active_packet, active_item in started_packets:
            if callbacks:
                for command, cb in callbacks.items():
                    active_packet.set_callback(command, cb)
            return active_packet
    pkt_out = packet_out.create(outpacket, wide, callbacks, target, route, response_timeout, keep_alive)
    if _Debug and lg.is_debug(_DebugLevel):
        monitoring()
    control.request_update([('packet', outpacket.PacketID)])
    return pkt_out


def on_transport_state_changed(transport, oldstate, newstate):
    """
    """
    global _TransportStateChangedCallbacksList
    if _Debug:
        lg.out(_DebugLevel - 2, 'gateway.on_transport_state_changed in %r : %s->%s' % (
            transport, oldstate, newstate))
    from p2p import network_connector
    if network_connector.A():
        network_connector.A('network-transport-state-changed', transport)
    for cb in _TransportStateChangedCallbacksList:
        cb(transport, oldstate, newstate)


def on_transport_initialized(proto, xmlrpcurl=None):
    """
    """
    transport(proto).automat('transport-initialized', xmlrpcurl)
    events.send('gateway-transport-initialized', data=dict(
        proto=proto,
        rpc_url=xmlrpcurl,
    ))
    return True


def on_receiving_started(proto, host, options_modified=None):
    """
    """
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
    """
    """
    if _Debug:
        lg.out(_DebugLevel - 2, 'gateway.on_receiving_failed %s    error=[%s]' % (proto.upper(), str(error_code)))
    transport(proto).automat('failed')
    events.send('gateway-receiving-failed', data=dict(
        proto=proto,
        error=error_code,
    ))
    return True


def on_disconnected(proto, result=None):
    """
    """
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
    """
    """
    return True


def on_session_opened(host, remote_user_id):
    """
    """


def on_connection_failed(host, error_message=None):
    """
    """


def on_session_closed(host, remote_user_id, reason=None):
    """
    """


def on_message_received(host, remote_user_id, data):
    """
    """


def on_register_file_sending(proto, host, receiver_idurl, filename, size=0, description=''):
    """
    Called from transport plug-in when sending a single file were started to
    some remote peer. Must return a unique transfer ID so plug-in will know
    that ID.

    After finishing that given transfer - that ID is passed to `unregister_file_sending()`.
    """
    if _Debug:
        lg.out(_DebugLevel, 'gateway.on_register_file_sending %s %s' % (filename, description))
    pkt_out, work_item = packet_out.search(proto, host, filename, remote_idurl=receiver_idurl)
    if pkt_out is None:
        if _Debug:
            lg.out(_DebugLevel, '    skip, packet_out not found: %r %r %r' % (
                proto, host, os.path.basename(filename)))
        return None
    transfer_id = make_transfer_ID()
    if _Debug:
        lg.out(_DebugLevel, '... OUT ... %s (%d) send {%s} via [%s] to %s at %s' % (
            pkt_out.description, transfer_id, os.path.basename(filename), proto,
            nameurl.GetName(receiver_idurl), host))
#    if pkt_out.remote_idurl != receiver_idurl and receiver_idurl:
#        if _Debug:
#            lg.out(_DebugLevel, 'gateway.on_register_file_sending [%s] receiver idurl is different [%s]' % (pkt_out.remote_idurl, receiver_idurl))
    pkt_out.automat('register-item', (proto, host, filename, transfer_id))
    control.request_update([('stream', transfer_id)])
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
    control.request_update([('stream', transfer_id)])
    if status == 'finished':
        if _Debug:
            lg.out(_DebugLevel, '>>> OUT >>> %s (%d) [%s://%s] %s with %d bytes' % (
                pkt_out.description, transfer_id, work_item.proto, work_item.host, status.upper(), bytes_sent))
    else:
        if _Debug:
            lg.out(_DebugLevel, '>>> OUT >>> %s (%d) [%s://%s] %s : %s' % (
                pkt_out.description, transfer_id, work_item.proto, work_item.host, str(status).upper(), error_message))
    return True


def on_cancelled_file_sending(proto, host, filename, size, description='', error_message=None):
    """
    """
    pkt_out, work_item = packet_out.search(proto, host, filename)
    if pkt_out is None:
        if _Debug:
            lg.out(_DebugLevel, 'gateway.on_cancelled_file_sending packet_out %s %s %s not found - IT IS OK' % (
                proto, host, os.path.basename(filename)))
        return True
    pkt_out.automat('item-cancelled', (proto, host, filename, size, description, error_message))
    control.request_update([('packet', pkt_out.outpacket.PacketID)])
    if _Debug:
        lg.out(_DebugLevel, '>>> OUT >>>  {%s} CANCELLED via [%s] to %s : %s' % (
            os.path.basename(filename), proto, host, error_message))
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
        lg.out(_DebugLevel, '... IN ... %d receive {%s} via [%s] from %s at %s' % (
            transfer_id, os.path.basename(filename), proto,
            nameurl.GetName(sender_idurl), host))
    incoming_packet = packet_in.create(transfer_id)
    incoming_packet.automat('register-item', (proto, host, sender_idurl, filename, size))
    control.request_update([('stream', transfer_id)])
    return transfer_id


def on_unregister_file_receiving(transfer_id, status, bytes_received, error_message=''):
    """
    Called from transport plug-in after finish receiving a single file.
    """
    pkt_in = packet_in.get(transfer_id)
    assert pkt_in is not None
    if status == 'finished':
        if _Debug:
            lg.out(_DebugLevel, '<<< IN <<< (%d) [%s://%s] %s with %d bytes' % (
                transfer_id, pkt_in.proto, pkt_in.host, status.upper(), bytes_received))
    else:
        if _Debug:
            lg.out(_DebugLevel, '<<< IN <<< (%d) [%s://%s] %s : %s' % (
                transfer_id, pkt_in.proto, pkt_in.host, status.upper(), error_message))
    pkt_in.automat('unregister-item', (status, bytes_received, error_message))
    control.request_update([('stream', transfer_id)])
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
            from twisted.python.failure import Failure
            return fail(Failure(Exception('unsupported method: %s' % method)))
        _d = Deferred()

        def _call():
            r = maybeDeferred(m, *args)
            r.addCallback(_d.callback)
            r.addErrback(_d.errback)
        reactor.callLater(0, _call)  # @UndefinedVariable
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
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                                        "procedure %s not found: %s" % (procedurePath, e))

    def listProcedures(self):
        return list(self.methods.keys())

#------------------------------------------------------------------------------


def parseCommandLine():
    oparser = optparse.OptionParser()
    oparser.add_option("-d", "--debug", dest="debug", type="int", help="set debug level")
    oparser.set_default('debug', 10)
    oparser.add_option("-t", "--tcpport", dest="tcpport", type="int", help="specify port for TCP transport")
    oparser.set_default('tcpport', settings.getTCPPort())
    oparser.add_option("-u", "--udpport", dest="udpport", type="int", help="specify port for UDP transport")
    oparser.set_default('udpport', settings.getUDPPort())
    oparser.add_option("-p", "--dhtport", dest="dhtport", type="int", help="specify UDP port for DHT network")
    oparser.set_default('dhtport', settings.getDHTPort())
    oparser.add_option("-s", "--packetsize", dest="packetsize", type="int", help="set size of UDP datagrams")
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
    from crypt import key
    key.InitMyKey()
    (options, args) = parseCommandLine()
    settings.override('transport.transport-tcp.transport-tcp-port', options.tcpport)
    settings.override('transport.transport-udp.transport-udp-port', options.udpport)
    settings.override('network.network-dht-port', options.dhtport)
    lg.set_debug_level(options.debug)
    tmpfile.init()
    if True:
        import lib.udp
        lib.udp.listen(options.udpport)
        import dht.dht_service
        dht.dht_service.init(options.dhtport)
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
            p = signed.Packet(commands.Data(), my_id.getLocalID(),
                              my_id.getLocalID(), my_id.getLocalID(),
                              bpio.ReadBinaryFile(args[1]), args[0])
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

#------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
