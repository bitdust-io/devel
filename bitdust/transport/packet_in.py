#!/usr/bin/env python
# packet_in.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (packet_in.py) is part of BitDust Software.
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
"""
.. module:: packet_in.

.. role:: red

BitDust packet_in() Automat

.. raw:: html

    <a href="packet_in.png" target="_blank">
    <img src="packet_in.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`cancel`
    * :red:`failed`
    * :red:`register-item`
    * :red:`remote-id-cached`
    * :red:`unregister-item`
    * :red:`unserialize-failed`
    * :red:`valid-inbox-packet`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 16

_PacketLogFileEnabled = False

#------------------------------------------------------------------------------

import os
import time

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.main import settings
from bitdust.main import config

from bitdust.automats import automat

from bitdust.lib import nameurl
from bitdust.lib import strng

from bitdust.system import bpio
from bitdust.system import tmpfile

from bitdust.userid import global_id
from bitdust.userid import id_url

from bitdust.contacts import contactsdb
from bitdust.contacts import identitycache

from bitdust.services import driver

from bitdust.p2p import commands
from bitdust.p2p import p2p_stats

from bitdust.transport import callback

#------------------------------------------------------------------------------

_InboxItems = {}
_PacketsCounter = 0
_History = []

#------------------------------------------------------------------------------


def init():
    global _PacketLogFileEnabled
    _PacketLogFileEnabled = config.conf().getBool('logs/packet-enabled')


def shutdown():
    global _PacketLogFileEnabled
    _PacketLogFileEnabled = False


#------------------------------------------------------------------------------


def get_packets_counter():
    global _PacketsCounter
    return _PacketsCounter


def increment_packets_counter():
    global _PacketsCounter
    _PacketsCounter += 1


#------------------------------------------------------------------------------


def inbox_items():
    global _InboxItems
    return _InboxItems


def create(transfer_id):
    p = PacketIn(transfer_id)
    inbox_items()[transfer_id] = p
    # lg.out(10, 'packet_in.create  %s,  %d working items now' % (
    #     transfer_id, len(items())))
    return p


def get(transfer_id):
    return inbox_items().get(transfer_id, None)


def search(sender_idurl=None, proto=None, host=None):
    """
    Returns list of transfer ids of incoming packets which satisfies given criteria.
    """
    if sender_idurl and not isinstance(sender_idurl, list):
        sender_idurl = [
            sender_idurl,
        ]
    results = set()
    for transfer_id, itm in inbox_items().items():
        if sender_idurl:
            if itm.sender_idurl and itm.sender_idurl == sender_idurl:
                results.add(transfer_id)
                continue
        if proto and host:
            if itm.proto and itm.proto == proto and itm.host and itm.host == host:
                results.add(transfer_id)
                continue
        if host:
            if itm.host and itm.host == host:
                results.add(transfer_id)
                continue
        if proto:
            if itm.proto and itm.proto == proto:
                results.add(transfer_id)
                continue
    return list(results)


def history():
    global _History
    return _History


#------------------------------------------------------------------------------


def process(newpacket, info):
    """
    Main entry point where all incoming signed packets are coming from remote peers.
    The main aspect here is to "authenticate" remote node - need to know it identity.
    """
    # from bitdust.p2p import p2p_service
    from bitdust.transport import gateway
    from bitdust.userid import my_id
    if not driver.is_on('service_p2p_hookups'):
        if _Debug:
            lg.out(_DebugLevel, 'packet_in.process SKIP incoming packet, service_p2p_hookups is not started')
        return None
    if _Debug:
        lg.out(
            _DebugLevel, 'packet_in.process [%s/%s/%s]:%s(%s) from %s://%s is "%s"' % (
                nameurl.GetName(newpacket.OwnerID),
                nameurl.GetName(newpacket.CreatorID),
                nameurl.GetName(newpacket.RemoteID),
                newpacket.Command,
                newpacket.PacketID,
                info.proto,
                info.host,
                info.status,
            )
        )
    if info.status != 'finished':
        if _Debug:
            lg.out(_DebugLevel, '    skip, packet status is : [%s]' % info.status)
        return None


#     if _PacketLogFileEnabled:
#         lg.out(0, '        \033[0;49;92mIN %s(%s) with %d bytes from %s to %s TID:%s\033[0m' % (
#             newpacket.Command, newpacket.PacketID, info.bytes_received,
#             global_id.UrlToGlobalID(info.sender_idurl), global_id.UrlToGlobalID(newpacket.RemoteID),
#             info.transfer_id), log_name='packet', showtime=True)
# we must know recipient identity
    if not id_url.is_cached(newpacket.RemoteID):
        d = identitycache.immediatelyCaching(newpacket.RemoteID)
        d.addCallback(lambda _: process(newpacket, info))
        d.addErrback(lambda err: lg.err('incoming remote ID is unknown, failed caching remote %s identity: %s' % (newpacket.RemoteID, str(err))) and None)
        return d
    if newpacket.Command == commands.Identity():
        if not id_url.is_the_same(newpacket.RemoteID, my_id.getIDURL()):
            if _Debug:
                lg.out(_DebugLevel, '    incoming Identity is routed to another user')
            if not gateway.on_identity_received(newpacket, send_ack=False):
                lg.warn('received identity was not processed')
                return None
            # remote peer sending a valid identity to another peer routed via my machine
            # need to handle that packet - it should be processed by proxy_server
            return handle(newpacket, info)
        # contact sending us current identity we might not have
        # so we handle it before check that packet is valid
        # because we might not have his identity on hands and so can not verify the packet
        # so we check that his Identity is valid and save it into cache
        # than we check the packet to be valid too.
        if not gateway.on_identity_received(newpacket):
            lg.warn('received identity was not processed')
            return None
    if not identitycache.HasKey(newpacket.CreatorID):
        if _Debug:
            lg.out(_DebugLevel, '    will cache remote identity %s before processing incoming packet %s' % (newpacket.CreatorID, newpacket))
        d = identitycache.immediatelyCaching(newpacket.CreatorID)
        d.addCallback(lambda _: handle(newpacket, info))
        d.addErrback(lambda err: lg.err('failed caching remote %s identity: %s' % (newpacket.CreatorID, str(err))) and None)
        return d
    return handle(newpacket, info)


def handle(newpacket, info):
    """
    Actually process incoming packet. Here we can be sure that owner/creator of the packet is identified.
    """
    from bitdust.transport import packet_out
    handled = False
    # check that signed by a contact of ours
    try:
        is_signature_valid = newpacket.Valid(raise_signature_invalid=False)
    except:
        is_signature_valid = False
        # lg.exc('new packet from %s://%s is NOT VALID:\n\n%r\n' % (
        #     info.proto, info.host, newpacket.Serialize()))
    if not is_signature_valid:
        if _Debug:
            lg.args(_DebugLevel, PacketID=newpacket.PacketID, OwnerID=newpacket.OwnerID, CreatorID=newpacket.CreatorID, RemoteID=newpacket.RemoteID)
        lg.warn('signature is not valid for %r from %r|%r to %r' % (newpacket, newpacket.OwnerID, newpacket.CreatorID, newpacket.RemoteID))
        return None
    try:
        if not commands.IsRelay(newpacket.Command):
            for p in packet_out.search_by_response_packet(newpacket, info.proto, info.host):
                p.automat('inbox-packet', (newpacket, info))
                handled = True
                if _Debug:
                    lg.out(_DebugLevel, '    processed by %s as response packet' % p)
    except:
        lg.exc()
    try:
        handled = callback.run_inbox_callbacks(newpacket, info, info.status, info.error_message) or handled
    except:
        lg.exc()
    if not handled and newpacket.Command not in [
        commands.Ack(),
        commands.Fail(),
        commands.Identity(),
    ]:
        lg.warn('incoming %s from [%s://%s] was NOT HANDLED' % (newpacket, info.proto, info.host))
        if _PacketLogFileEnabled:
            lg.out(
                0,
                '                \033[1;49;91mIN NOT HANDLED %s(%s) with %d bytes from %s to %s TID:%s\033[0m' % (
                    newpacket.Command,
                    newpacket.PacketID,
                    info.bytes_received,
                    global_id.UrlToGlobalID(info.sender_idurl),
                    global_id.UrlToGlobalID(newpacket.RemoteID),
                    info.transfer_id,
                ),
                log_name='packet',
                showtime=True,
            )
    else:
        if _PacketLogFileEnabled:
            lg.out(
                0,
                '                \033[0;49;93mIN OK %s(%s) with %d bytes from %s to %s TID:%s\033[0m' % (
                    newpacket.Command,
                    newpacket.PacketID,
                    info.bytes_received,
                    global_id.UrlToGlobalID(info.sender_idurl),
                    global_id.UrlToGlobalID(newpacket.RemoteID),
                    info.transfer_id,
                ),
                log_name='packet',
                showtime=True,
            )
    if _Debug and False:
        history().append(
            {
                'time': newpacket.Date,
                'command': newpacket.Command,
                'packet_id': newpacket.PacketID,
                'creator_id': newpacket.CreatorID,
                'owner_id': newpacket.OwnerID,
                'remote_id': newpacket.RemoteID,
                'payload': len(newpacket.Payload),
                'address': '%s://%s' % (info.proto, info.host),
            }
        )
        if len(history()) > 100:
            history().pop(0)
    return handled


#------------------------------------------------------------------------------


class PacketIn(automat.Automat):
    """
    This class implements all the functionality of the ``packet_in()`` state
    machine.
    """
    def __init__(self, transfer_id):
        self.transfer_id = transfer_id
        self.time = None
        self.timeout = None
        self.proto = None
        self.host = None
        self.sender_idurl = None
        self.filename = None
        self.size = None
        self.bytes_received = None
        self.status = None
        self.error_message = None
        _counter = get_packets_counter()
        increment_packets_counter()
        self.label = ''
        automat.Automat.__init__(
            self,
            name='in_%d_%s' % (_counter, self.transfer_id),
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
            publish_events=False,
        )

    def __repr__(self):
        """
        Will return something like: "in_4_1315435345[Ack(987654321)](DONE)".
        """
        return '%s%s(%s)' % (self.id, self.label, self.state)

    def is_timed_out(self):
        #         if self.time is None or self.timeout is None:
        #             return False
        #         return time.time() - self.time > self.timeout
        return False

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'register-item':
                self.state = 'RECEIVING'
                self.doInit(*args, **kwargs)
        #---RECEIVING---
        elif self.state == 'RECEIVING':
            if event == 'cancel':
                self.doCancelItem(*args, **kwargs)
            elif event == 'unregister-item' and not self.isTransferFinished(*args, **kwargs):
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doEraseInputFile(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'unregister-item' and self.isTransferFinished(*args, **kwargs) and not self.isRemoteIdentityCached(*args, **kwargs):
                self.state = 'CACHING'
                self.doCacheRemoteIdentity(*args, **kwargs)
            elif event == 'unregister-item' and self.isTransferFinished(*args, **kwargs) and self.isRemoteIdentityCached(*args, **kwargs):
                self.state = 'INBOX?'
                self.doReadAndUnserialize(*args, **kwargs)
        #---INBOX?---
        elif self.state == 'INBOX?':
            if event == 'valid-inbox-packet':
                self.state = 'DONE'
                self.doReportReceived(*args, **kwargs)
                self.doEraseInputFile(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'unserialize-failed':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doEraseInputFile(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---CACHING---
        elif self.state == 'CACHING':
            if event == 'failed':
                self.state = 'FAILED'
                self.doReportCacheFailed(*args, **kwargs)
                self.doEraseInputFile(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'remote-id-cached':
                self.state = 'INBOX?'
                self.doReadAndUnserialize(*args, **kwargs)
        return None

    def isTransferFinished(self, *args, **kwargs):
        """
        Condition method.
        """
        status, bytes_received, _ = args[0]
        if status != 'finished':
            return False
        if self.size and self.size > 0 and self.size != bytes_received:
            return False
        return True

    def isRemoteIdentityCached(self, *args, **kwargs):
        """
        Condition method.
        """
        if not self.sender_idurl:
            return True
        return self.sender_idurl and identitycache.HasKey(self.sender_idurl)

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.proto, self.host, self.sender_idurl, self.filename, self.size = args[0]
        self.time = time.time()
        # 300  # max(10 * int(self.size/float(settings.SendingSpeedLimit())), 10)
        if self.size < 1024*10:
            self.timeout = 10
        elif self.size > 1024*1024:
            self.timeout = int(self.size/float(settings.SendingSpeedLimit()))
        else:
            self.timeout = 300
        if not self.sender_idurl:
            lg.warn('sender_idurl is None: %s' % str(*args, **kwargs))
        reactor.callLater(0, callback.run_begin_file_receiving_callbacks, self)  # @UndefinedVariable

    def doEraseInputFile(self, *args, **kwargs):
        """
        Action method.
        """
        reactor.callLater(1, tmpfile.throw_out, self.filename, 'received')  # @UndefinedVariable

    def doCancelItem(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.transport import gateway
        t = gateway.transports().get(self.proto, None)
        if t:
            t.call('cancel_file_receiving', self.transfer_id)

    def doCacheRemoteIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        d = identitycache.immediatelyCaching(self.sender_idurl)
        d.addCallback(self._on_remote_identity_cached, *args, **kwargs)
        d.addErrback(self._on_remote_identity_cache_failed, *args, **kwargs)

    def doReadAndUnserialize(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.transport import gateway
        self.status, self.bytes_received, self.error_message = args[0]
        if _PacketLogFileEnabled:
            lg.out(
                0,
                '                \033[2;49;32mRECEIVED %d bytes from %s://%s TID:%s\033[0m' % (self.bytes_received, self.proto, self.host, self.transfer_id),
                log_name='packet',
                showtime=True,
            )
        # DO UNSERIALIZE HERE , no exceptions
        newpacket = gateway.inbox(self)
        if newpacket is None:
            if _Debug:
                lg.out(_DebugLevel, '<<< IN <<< !!!NONE!!! [%s] %s from %s %s' % (
                    self.proto.upper().ljust(5),
                    self.status.ljust(8),
                    self.host,
                    os.path.basename(self.filename),
                ))
            # net_misc.ConnectionFailed(None, proto, 'receiveStatusReport %s' % host)
            try:
                fd, _ = tmpfile.make('error', extension='.inbox')
                data = bpio.ReadBinaryFile(self.filename)
                os.write(fd, strng.to_bin('from %s:%s %s\n' % (self.proto, self.host, self.status)))
                os.write(fd, data)
                os.close(fd)
            except:
                lg.exc()
            if os.path.isfile(self.filename):
                try:
                    os.remove(self.filename)
                except:
                    lg.exc()
            self.automat('unserialize-failed', None)
            return
        self.label = '[%s@%s]' % (newpacket.Command, newpacket.PacketID)
        if _Debug:
            lg.out(_DebugLevel, 'packet_in.doReadAndUnserialize: %s' % newpacket)
        self.automat('valid-inbox-packet', newpacket)

    def doReportReceived(self, *args, **kwargs):
        """
        Action method.
        """
        newpacket = args[0]
        p2p_stats.count_inbox(self.sender_idurl, self.proto, self.status, self.bytes_received)
        process(newpacket, self)

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            status, bytes_received, _ = args[0]
        except:
            status = 'failed'
            bytes_received = 0
        p2p_stats.count_inbox(self.sender_idurl, self.proto, status, bytes_received)
        lg.warn('incoming packet failed %s with %s' % (self.transfer_id, status))
        if _PacketLogFileEnabled:
            lg.out(
                0,
                '                \033[0;49;31mIN FAILED with status "%s" from %s://%s TID:%s\033[0m' % (status, self.proto, self.host, self.transfer_id),
                log_name='packet',
                showtime=True,
            )

    def doReportCacheFailed(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0]:
            status, bytes_received, msg = args[0]
            p2p_stats.count_inbox(self.sender_idurl, self.proto, status, bytes_received)
        else:
            status = 'failed'
            bytes_received = 0
            msg = 'unknown reason'
        lg.warn('cache failed : %s' % self.sender_idurl)
        if _PacketLogFileEnabled:
            lg.out(
                0,
                '                \033[0;49;31mIN CACHE FAILED with "%s" for %s TID:%s\033[0m' % (msg, self.sender_idurl, self.transfer_id),
                log_name='packet',
                showtime=True,
            )

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        inbox_items().pop(self.transfer_id)
        self.destroy()

    def _on_remote_identity_cached(self, xmlsrc, *args, **kwargs):
        sender_identity = contactsdb.get_contact_identity(self.sender_idurl)
        if sender_identity is None:
            self.automat('failed')
        else:
            self.automat('remote-id-cached', *args, **kwargs)

    def _on_remote_identity_cache_failed(self, err, *args, **kwargs):
        lg.warn('%s : %s' % (repr(self), str(err)))
        self.automat('failed')
        return None
