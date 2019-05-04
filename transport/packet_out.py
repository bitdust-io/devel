#!/usr/bin/env python
# packet_out.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (packet_out.py) is part of BitDust Software.
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
.. module:: packet_out.

.. role:: red

BitDust packet_out() Automat

.. raw:: html

    <a href="packet_out.png" target="_blank">
    <img src="packet_out.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`cancel`
    * :red:`failed`
    * :red:`inbox-packet`
    * :red:`item-cancelled`
    * :red:`items-sent`
    * :red:`nothing-to-send`
    * :red:`register-item`
    * :red:`remote-identity-on-hand`
    * :red:`response-timeout`
    * :red:`run`
    * :red:`timer-30sec`
    * :red:`unregister-item`
    * :red:`write-error`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import six
from six.moves import map
from six.moves import range

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

_PacketLogFileEnabled = True

#------------------------------------------------------------------------------

import os
import time

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from p2p import commands
from p2p import p2p_stats

from lib import nameurl
from lib import strng
from lib import net_misc

from system import tmpfile

from contacts import contactsdb
from contacts import identitycache

from userid import my_id
from userid import global_id

from main import settings
from main import events

from transport import callback

#------------------------------------------------------------------------------

_OutboxQueue = []
_PacketsCounter = 0

#------------------------------------------------------------------------------


def get_packets_counter():
    global _PacketsCounter
    return _PacketsCounter


def increment_packets_counter():
    global _PacketsCounter
    _PacketsCounter += 1

#------------------------------------------------------------------------------


def queue():
    """
    """
    global _OutboxQueue
    return _OutboxQueue


def create(outpacket, wide, callbacks, target=None, route=None, response_timeout=None, keep_alive=True):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'packet_out.create [%s/%s/%s]:%s(%s) target=%r route=%r callbacks=%s' % (
            nameurl.GetName(outpacket.OwnerID), nameurl.GetName(outpacket.CreatorID), nameurl.GetName(outpacket.RemoteID),
            outpacket.Command, outpacket.PacketID, target, route, list(callbacks.keys())))
    p = PacketOut(outpacket, wide, callbacks, target, route, response_timeout, keep_alive)
    queue().append(p)
    p.automat('run')
    return p

#------------------------------------------------------------------------------


def search(proto, host, filename, remote_idurl=None):
    for p in queue():
        if p.filename != filename:
            continue
        for i in p.items:
            if i.proto == proto:
                if not remote_idurl:
                    return p, i
                if p.remote_idurl and remote_idurl != p.remote_idurl:
                    if _Debug:
                        lg.out(_DebugLevel, 'packet_out.search found a packet addressed for another idurl: %s != %s' % (
                            p.remote_idurl, remote_idurl))
                return p, i
    if _Debug:
        for p in queue():
            if p.filename:
                lg.out(_DebugLevel, '%s [%s]' % (os.path.basename(p.filename),
                                                 ('|'.join(['%s:%s' % (i.proto, i.host) for i in p.items]))))
            else:
                lg.warn('%s was not initialized yet' % str(p))
    return None, None


def search_by_backup_id(backup_id):
    result = []
    for p in queue():
        if p.outpacket.PacketID.count(backup_id):
            result.append(p)
    if _Debug:
        lg.out(_DebugLevel, 'packet_out.search_by_backup_id %s:' % backup_id)
        lg.out(_DebugLevel, '%s' % ('        \n'.join(map(str, result))))
    return result


def search_many(proto=None,
                host=None,
                filename=None,
                command=None,
                remote_idurl=None,
                packet_id=None,
                ):
    results = []
    for p in queue():
        if remote_idurl and p.remote_idurl != remote_idurl:
            continue
        if filename and p.filename != filename:
            continue
        if command and p.outpacket.Command != command:
            continue
        if packet_id and p.outpacket.PacketID != packet_id:
            continue
        for i in p.items:
            if proto and i.proto != proto:
                continue
            if host and i.host != host:
                continue
            results.append((p, i))
    if _Debug:
        lg.out(_DebugLevel, 'packet_out.search_many query: (%s, %s, %s, %s) found %d items : ' % (
            proto, host, filename, remote_idurl, len(results)))
        lg.out(_DebugLevel, '%s' % ('        \n'.join(map(str, results))))
    return results


def search_by_transfer_id(transfer_id):
    for p in queue():
        for i in p.items:
            if i.transfer_id and i.transfer_id == transfer_id:
                return p, i
    return None, None


def search_by_response_packet(newpacket, proto=None, host=None):
    result = []
    incoming_owner_idurl = newpacket.OwnerID
    incoming_creator_idurl = newpacket.CreatorID
    incoming_remote_idurl = newpacket.RemoteID
    if _Debug:
        lg.out(_DebugLevel, 'packet_out.search_by_response_packet for incoming [%s/%s/%s]:%s(%s) from [%s://%s]' % (
            nameurl.GetName(incoming_owner_idurl), nameurl.GetName(incoming_creator_idurl), nameurl.GetName(incoming_remote_idurl),
            newpacket.Command, newpacket.PacketID, proto, host, ))
        lg.out(_DebugLevel, '    [%s]' % (','.join([str(p.outpacket) for p in queue()])))
    for p in queue():
        # TODO: investigate 
        if p.outpacket.PacketID.lower() != newpacket.PacketID.lower():
            # PacketID of incoming packet not matching with that outgoing packet
            continue
        if p.outpacket.PacketID != newpacket.PacketID:
            lg.warn('packet ID in queue "almost" matching with incoming: %s ~ %s' % (
                p.outpacket.PacketID, newpacket.PacketID, ))
        if not commands.IsCommandAck(p.outpacket.Command, newpacket.Command):
            # this command must not be in the reply
            continue
        expected_recipient = [p.outpacket.RemoteID, ]
        if p.outpacket.RemoteID != p.remote_idurl:
            # outgoing packet was addressed to another node, so that means we need to expect response from another node also
            expected_recipient.append(p.remote_idurl)
        matched = False
        if incoming_owner_idurl in expected_recipient and my_id.getLocalIDURL() == incoming_remote_idurl:
            if _Debug:
                lg.out(_DebugLevel, '    matched with incoming owner: %s' % expected_recipient)
            matched = True
        if incoming_creator_idurl in expected_recipient and my_id.getLocalIDURL() == incoming_remote_idurl:
            if _Debug:
                lg.out(_DebugLevel, '    matched with incoming creator: %s' % expected_recipient)
            matched = True
        if incoming_remote_idurl in expected_recipient and my_id.getLocalIDURL() == incoming_owner_idurl and commands.Data() == newpacket.Command:
            if _Debug:
                lg.out(_DebugLevel, '    matched my own incoming Data with incoming remote: %s' % expected_recipient)
            matched = True
        if matched:
            result.append(p)
            if _Debug:
                lg.out(_DebugLevel, '        found pending outbox [%s/%s/%s]:%s(%s) cb:%s' % (
                    nameurl.GetName(p.outpacket.OwnerID), nameurl.GetName(p.outpacket.CreatorID),
                    nameurl.GetName(p.outpacket.RemoteID), p.outpacket.Command, p.outpacket.PacketID,
                    list(p.callbacks.keys())))
    if len(result) == 0:
        if _Debug:
            lg.out(_DebugLevel, '        NOT FOUND pending packets in outbox queue matching incoming %s' % newpacket)
        if newpacket.Command == commands.Ack() and newpacket.PacketID not in [commands.Identity(), commands.Identity().lower()]:
            lg.warn('received %s was not a "good reply" from %s://%s' % (newpacket, proto, host, ))
    return result


def search_similar_packets(outpacket):
    target = correct_packet_destination(outpacket)
    return search_many(
        command=outpacket.Command,
        packet_id=outpacket.PacketID,
        remote_idurl=target,
    )

#------------------------------------------------------------------------------


def correct_packet_destination(outpacket):
    """
    """
    if outpacket.CreatorID == my_id.getLocalID():
        # our data will go where it should go
        return outpacket.RemoteID
    if outpacket.Command == commands.Data():
        # Data belongs to remote customers and stored locally
        # must go to CreatorID, because RemoteID pointing to this device
        # return outpacket.CreatorID
        # this was changed by Veselin... TODO: test and clean up this
        return outpacket.RemoteID
    lg.warn('sending a packet we did not make, and that is not Data packet')
    return outpacket.RemoteID

#------------------------------------------------------------------------------


class WorkItem(object):

    def __init__(self, proto, host, size=0):
        self.proto = proto
        self.host = net_misc.pack_address(host)
        self.time = time.time()
        self.transfer_id = None
        self.status = None
        self.error_message = None
        self.bytes_sent = 0
        self.size = size

    def __repr__(self):
        return 'WorkItem(%s://%s|%d)' % (self.proto, self.host, self.size)

#------------------------------------------------------------------------------


class PacketOut(automat.Automat):
    """
    This class implements all the functionality of the ``packet_out()`` state
    machine.
    """

    timers = {
        'timer-30sec': (30.0, ['RESPONSE?']),
    }

    MESSAGES = {
        'MSG_1': 'file in queue was cancelled',
        'MSG_2': 'sending file was cancelled',
        'MSG_3': 'response waiting were cancelled',
        'MSG_4': 'outgoing packet was cancelled',
        'MSG_5': 'pushing outgoing packet was cancelled',
    }

    def __init__(self, outpacket, wide, callbacks={}, target=None, route=None, response_timeout=None, keep_alive=True):
        self.outpacket = outpacket
        self.wide = wide
        self.callbacks = {}
        self.caching_deferred = None
        self.description = self.outpacket.Command + '[' + self.outpacket.PacketID + ']'
        self.remote_idurl = target
        self.route = route
        self.response_timeout = response_timeout
        if self.route:
            self.description = self.route['description']
            self.remote_idurl = self.route['remoteid']
        if not self.remote_idurl:
            self.remote_idurl = self.outpacket.RemoteID  # correct_packet_destination(self.outpacket)
        self.remote_name = nameurl.GetName(self.remote_idurl)
        self.label = 'out_%d_%s' % (get_packets_counter(), self.remote_name)
        self.keep_alive = keep_alive
        automat.Automat.__init__(
            self, self.label, 'AT_STARTUP',
            debug_level=_DebugLevel, log_events=_Debug, publish_events=False, )
        increment_packets_counter()
        for command, cb in callbacks.items():
            self.set_callback(command, cb)

    def __repr__(self):
        """
        Will print something like: "out_123_alice[Data(9999999999)](SENDING)".
        """
        packet_label = '?'
        if self.outpacket:
            packet_label = '%s:%s' % (self.outpacket.Command, self.outpacket.PacketID[:10], )
        return '%s[%s](%s)' % (self.id, packet_label, self.state)

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.error_message = None
        self.time = time.time()
        self.description = self.outpacket.Command + '(' + self.outpacket.PacketID + ')'
        self.payloadsize = len(self.outpacket.Payload)
        last_modified_time = identitycache.GetLastModifiedTime(self.remote_idurl)
        if not last_modified_time or time.time() - last_modified_time < 60:
            # use known identity from cache
            self.remote_identity = contactsdb.get_contact_identity(self.remote_idurl)
        else:
            self.remote_identity = None
            if _Debug:
                lg.out(_DebugLevel, 'packet_out.init  cached identity copy is outdated or not exist: %s' % self.remote_idurl)
        self.packetdata = None
        self.filename = None
        self.filesize = None
        self.items = []
        self.results = []
        self.response_packet = None
        self.response_info = None
        self.timeout = None  # 300  # settings.SendTimeOut() * 3
        if self.response_timeout:
            self.timers['response-timeout'] = (self.response_timeout, ['RESPONSE?', ], )

    def msg(self, msgid, *args, **kwargs):
        return self.MESSAGES.get(msgid, '')

    def is_timed_out(self):
        if self.state == 'RESPONSE?':
            return False
        if self.time is None or self.timeout is None:
            return False
        return time.time() - self.time > self.timeout

    def set_callback(self, command, cb):
        if command not in list(self.callbacks.keys()):
            self.callbacks[command] = []
        self.callbacks[command].append(cb)
        if _Debug:
            lg.out(_DebugLevel, '%s : new callback for [%s] added, expecting: %r' % (
                self, command, list(self.callbacks.keys())))

    def A(self, event, *args, **kwargs):
        #---SENDING---
        if self.state == 'SENDING':
            if event == 'register-item':
                self.doSetTransferID(*args, **kwargs)
            elif event == 'cancel':
                self.state = 'CANCEL'
                self.doCancelItems(*args, **kwargs)
                self.doErrMsg(event,self.msg('MSG_2', *args, **kwargs))
                self.doReportCancelItems(*args, **kwargs)
                self.doPopItems(*args, **kwargs)
                self.doReportCancelled(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'unregister-item' and self.isAckNeeded(*args, **kwargs):
                self.state = 'RESPONSE?'
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
            elif event == 'item-cancelled' and self.isMoreItems(*args, **kwargs):
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
            elif event == 'unregister-item' and not self.isAckNeeded(*args, **kwargs):
                self.state = 'SENT'
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
                self.doReportDoneNoAck(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'item-cancelled' and not self.isMoreItems(*args, **kwargs):
                self.state = 'FAILED'
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'run' and self.isRemoteIdentityKnown(*args, **kwargs):
                self.state = 'ITEMS?'
                self.doInit(*args, **kwargs)
                self.Cancelled=False
                self.doReportStarted(*args, **kwargs)
                self.doSerializeAndWrite(*args, **kwargs)
                self.doPushItems(*args, **kwargs)
            elif event == 'run' and not self.isRemoteIdentityKnown(*args, **kwargs):
                self.state = 'CACHING'
                self.doInit(*args, **kwargs)
                self.doCacheRemoteIdentity(*args, **kwargs)
        #---CACHING---
        elif self.state == 'CACHING':
            if event == 'remote-identity-on-hand':
                self.state = 'ITEMS?'
                self.Cancelled=False
                self.doReportStarted(*args, **kwargs)
                self.doSerializeAndWrite(*args, **kwargs)
                self.doPushItems(*args, **kwargs)
            elif event == 'failed':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'cancel':
                self.state = 'CANCEL'
                self.doErrMsg(event,self.msg('MSG_4', *args, **kwargs))
                self.doReportCancelled(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---ITEMS?---
        elif self.state == 'ITEMS?':
            if event == 'nothing-to-send' or event == 'write-error':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'items-sent' and not self.Cancelled:
                self.state = 'IN_QUEUE'
            elif event == 'cancel':
                self.Cancelled=True
            elif event == 'items-sent' and self.Cancelled:
                self.state = 'CANCEL'
                self.doCancelItems(*args, **kwargs)
                self.doErrMsg(event,self.msg('MSG_5', *args, **kwargs))
                self.doReportCancelItems(*args, **kwargs)
                self.doPopItems(*args, **kwargs)
                self.doReportCancelled(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---IN_QUEUE---
        elif self.state == 'IN_QUEUE':
            if event == 'item-cancelled' and self.isMoreItems(*args, **kwargs):
                self.doPopItem(*args, **kwargs)
            elif event == 'register-item':
                self.state = 'SENDING'
                self.doSetTransferID(*args, **kwargs)
            elif event == 'cancel':
                self.state = 'CANCEL'
                self.doCancelItems(*args, **kwargs)
                self.doErrMsg(event,self.msg('MSG_1', *args, **kwargs))
                self.doReportCancelItems(*args, **kwargs)
                self.doPopItems(*args, **kwargs)
                self.doReportCancelled(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'item-cancelled' and not self.isMoreItems(*args, **kwargs):
                self.state = 'FAILED'
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---SENT---
        elif self.state == 'SENT':
            pass
        #---CANCEL---
        elif self.state == 'CANCEL':
            pass
        #---RESPONSE?---
        elif self.state == 'RESPONSE?':
            if event == 'cancel':
                self.state = 'CANCEL'
                self.doErrMsg(event,self.msg('MSG_3', *args, **kwargs))
                self.doReportCancelItems(*args, **kwargs)
                self.doReportCancelled(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'inbox-packet' and self.isResponse(*args, **kwargs):
                self.state = 'SENT'
                self.doSaveResponse(*args, **kwargs)
                self.doReportResponse(*args, **kwargs)
                self.doReportDoneWithAck(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'unregister-item' or event == 'item-cancelled':
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
            elif ( event == 'response-timeout' or event == 'timer-30sec' ) and not self.isDataExpected(*args, **kwargs):
                self.state = 'SENT'
                self.doReportTimeOut(*args, **kwargs)
                self.doReportDoneNoAck(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        return None

    def isRemoteIdentityKnown(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.remote_identity is not None

    def isAckNeeded(self, *args, **kwargs):
        """
        Condition method.
        """
        return commands.Ack() in list(self.callbacks.keys()) or commands.Fail() in list(self.callbacks.keys())

    def isMoreItems(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.items) > 1

    def isResponse(self, *args, **kwargs):
        """
        Condition method.
        """
        newpacket, _ = args[0]
        return newpacket.Command in list(self.callbacks.keys())

    def isDataExpected(self, *args, **kwargs):
        """
        Condition method.
        """
        return commands.Data() in list(self.callbacks.keys())

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        if self in self.outpacket.Packets:
            lg.warn('packet_out already connected to the packet')
        else:
            self.outpacket.Packets.append(self)

    def doCacheRemoteIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        self.caching_deferred = identitycache.immediatelyCaching(self.remote_idurl)
        self.caching_deferred.addCallback(self._on_remote_identity_cached)
        self.caching_deferred.addErrback(self._on_remote_identity_cache_failed)

    def doSerializeAndWrite(self, *args, **kwargs):
        """
        Action method.
        """
        # serialize and write packet on disk
        a_packet = self.outpacket
        if self.route:
            a_packet = self.route['packet']
        try:
            fileno, self.filename = tmpfile.make('outbox', extension='.out')
            self.packetdata = a_packet.Serialize()
            os.write(fileno, self.packetdata)
            os.close(fileno)
            self.filesize = len(self.packetdata)
            if self.filesize < 1024 * 10:
                self.timeout = 10
            elif self.filesize > 1024 * 1024:
                self.timeout = int(self.filesize / float(settings.SendingSpeedLimit()))
            else:
                self.timeout = 300
#             self.timeout = min(
#                 settings.SendTimeOut() * 3,
#                 max(int(self.filesize/(settings.SendingSpeedLimit()/len(queue()))),
#                     settings.SendTimeOut()))
        except:
            lg.exc()
            self.packetdata = None
            self.automat('write-error')

    def doPushItems(self, *args, **kwargs):
        """
        Action method.
        """
        self._push()

    def doPopItem(self, *args, **kwargs):
        """
        Action method.
        """
        self._pop(args[0])

    def doPopItems(self, *args, **kwargs):
        """
        Action method.
        """
        self.items = []

    def doSetTransferID(self, *args, **kwargs):
        """
        Action method.
        """
        ok = False
        proto, host, filename, transfer_id = args[0]
        for i in range(len(self.items)):
            if self.items[i].proto == proto:  # and self.items[i].host == host:
                self.items[i].transfer_id = transfer_id
                if _Debug:
                    lg.out(_DebugLevel, 'packet_out.doSetTransferID  %r:%r = %r' % (proto, host, transfer_id))
                ok = True
        if not ok:
            lg.warn('not found item for %r:%r' % (proto, host))

    def doSaveResponse(self, *args, **kwargs):
        """
        Action method.
        """
        self.response_packet, self.response_info = args[0]

    def doCancelItems(self, *args, **kwargs):
        """
        Action method.
        """
        from transport import gateway
        for i in self.items:
            t = gateway.transports().get(i.proto, None)
            if t:
                if i.transfer_id:
                    t.call('cancel_file_sending', i.transfer_id)
                t.call('cancel_outbox_file', i.host, self.filename)

    def doReportStarted(self, *args, **kwargs):
        """
        Action method.
        """
        handled = callback.run_outbox_callbacks(self)
        if not handled:
            pass

    def doReportItem(self, *args, **kwargs):
        """
        Action method.
        """
        if not self.popped_item:
            raise Exception('Current outgoing item not exist')
        p2p_stats.count_outbox(
            self.remote_idurl, self.popped_item.proto,
            self.popped_item.status, self.popped_item.bytes_sent)
        callback.run_finish_file_sending_callbacks(
            self, self.popped_item, self.popped_item.status,
            self.popped_item.bytes_sent, self.popped_item.error_message)
        if _PacketLogFileEnabled:
            lg.out(0, '    \033[2;49;90mSENT %d bytes to %s://%s TID:%s\033[0m' % (
                self.popped_item.bytes_sent, self.popped_item.proto,
                self.popped_item.host, self.popped_item.transfer_id), log_name='packet', showtime=True)
        self.popped_item = None

    def doReportCancelItems(self, *args, **kwargs):
        """
        Action method.
        """
        for item in self.results:
            p2p_stats.count_outbox(self.remote_idurl, item.proto, 'failed', 0)
            callback.run_finish_file_sending_callbacks(
                self, item, 'failed', 0, self.error_message)
            if _PacketLogFileEnabled:
                lg.out(0, '\033[2;49;90mCANCELED %s://%s TID:%s\033[0m' % (
                    item.proto, item.host, item.transfer_id), log_name='packet', showtime=True)

    def doReportResponse(self, *args, **kwargs):
        """
        Action method.
        """
        if self.response_packet.Command in self.callbacks:
            for cb in self.callbacks[self.response_packet.Command]:
                try:
                    cb(self.response_packet, self.response_info)
                except:
                    lg.exc()

    def doReportTimeOut(self, *args, **kwargs):
        """
        Action method.
        """
        if None in self.callbacks:
            for cb in self.callbacks[None]:
                cb(self)
        if _PacketLogFileEnabled:
            lg.out(0, '\033[2;49;90mTIMEOUT %s(%s) sending to %s\033[0m' % (
                self.outpacket.Command, self.outpacket.PacketID,
                global_id.UrlToGlobalID(self.remote_idurl)), log_name='packet', showtime=True)

    def doReportDoneWithAck(self, *args, **kwargs):
        """
        Action method.
        """
        callback.run_queue_item_status_callbacks(self, 'finished', '')
        if _PacketLogFileEnabled:
            lg.out(0, '\033[0;49;95mOUT %s(%s) with %s bytes to %s (ACK received) TID:%r\033[0m' % (
                self.outpacket.Command, self.outpacket.PacketID, self.filesize or '?', global_id.UrlToGlobalID(self.remote_idurl),
                [i.transfer_id for i in self.results]), log_name='packet', showtime=True)

    def doReportDoneNoAck(self, *args, **kwargs):
        """
        Action method.
        """
        callback.run_queue_item_status_callbacks(self, 'finished', 'unanswered')
        if _PacketLogFileEnabled:
            lg.out(0, '\033[0;49;95mOUT %s(%s) with %s bytes to %s TID:%r\033[0m' % (
                self.outpacket.Command, self.outpacket.PacketID, self.filesize or '?', global_id.UrlToGlobalID(self.remote_idurl),
                [i.transfer_id for i in self.results]), log_name='packet', showtime=True)

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            msg = str(args[0][-1])
        except:
            msg = 'failed'
        callback.run_queue_item_status_callbacks(self, 'failed', msg)
        if _PacketLogFileEnabled:
            lg.out(0, '\033[0;49;91mFAILED %s(%s) with %s bytes to %s TID:%r : %s\033[0m' % (
                self.outpacket.Command, self.outpacket.PacketID, self.filesize or '?', global_id.UrlToGlobalID(self.remote_idurl),
                [i.transfer_id for i in self.results], msg), log_name='packet', showtime=True)

    def doReportCancelled(self, *args, **kwargs):
        """
        Action method.
        """
        msg = 'cancelled'
        if args and args[0]:
            msg = str(args[0])
        else:
            msg = 'cancelled'
        callback.run_queue_item_status_callbacks(self, 'cancelled', msg)
        if _PacketLogFileEnabled:
            lg.out(0, '\033[0;49;97mOUT %s(%s) with %s bytes CANCELED to %s TID:%r : %s\033[0m' % (
                self.outpacket.Command, self.outpacket.PacketID, self.filesize or '?', global_id.UrlToGlobalID(self.remote_idurl),
                [i.transfer_id for i in self.results], msg), log_name='packet', showtime=True)

    def doErrMsg(self, event, *args, **kwargs):
        """
        Action method.
        """
        if event.count('timer'):
            self.error_message = 'timeout responding from remote side'
        else:
            self.error_message = args[0]

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        if False:
            events.send('outbox-packet-finished', data=dict(
                description=self.description,
                packet_id=self.outpacket.PacketID,
                command=self.outpacket.Command,
                creator_id=self.outpacket.CreatorID,
                date=self.outpacket.Date,
                size=len(self.outpacket.Payload),
                remote_id=self.outpacket.RemoteID,
            ))
        if self not in self.outpacket.Packets:
            lg.warn('packet_out not connected to the packet')
        else:
            self.outpacket.Packets.remove(self)
        self.outpacket = None
        self.remote_identity = None
        if self.caching_deferred and not self.caching_deferred.called:
            self.caching_deferred.cancel()
        self.caching_deferred = None
        self.callbacks.clear()
        queue().remove(self)
        self.destroy()

    def _on_remote_identity_cached(self, xmlsrc):
        self.remote_identity = contactsdb.get_contact_identity(self.remote_idurl)
        if self.remote_identity is None:
            self.automat('failed')
        else:
            self.automat('remote-identity-on-hand')
        return xmlsrc

    def _on_remote_identity_cache_failed(self, err):
        if self.outpacket:
            self.automat('failed')
            lg.warn('%s : %s' % (self.remote_idurl, str(err)))
        return None

    def _push(self):
        from transport import gateway
        if self.route:
            # if this packet is routed - send directly to route host
            proto = strng.to_text(self.route['proto'])
            host = strng.to_bin(self.route['host'])
            gateway.send_file(
                strng.to_bin(self.route['remoteid']),
                proto,
                host,
                self.filename,
                self.description,
                self,
            )
            self.items.append(WorkItem(
                proto,
                host,
                self.filesize))
            if _PacketLogFileEnabled:
                lg.out(0, '        \033[2;49;90mPUSH %d bytes to %s://%r ROUTED\033[0m' % (
                    self.filesize, proto, host), log_name='packet', showtime=True)
            self.automat('items-sent')
            return
        # get info about his local IP
        localIP = identitycache.GetLocalIP(self.remote_idurl)
        workitem_sent = False
        if self.wide:
            # send to all his contacts
            for contactmethod in self.remote_identity.getContacts():
                proto, host = nameurl.IdContactSplit(contactmethod)
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                if host.strip() and \
                        settings.transportIsEnabled(proto) and \
                        settings.transportSendingIsEnabled(proto) and \
                        gateway.can_send(proto) and \
                        gateway.is_installed(proto):
                    if proto == 'tcp' and localIP:
                        host = localIP
                    gateway.send_file(
                        strng.to_bin(self.remote_idurl),
                        proto,
                        host,
                        self.filename,
                        self.description,
                        self,
                    )
                    self.items.append(WorkItem(proto, host, self.filesize))
                    workitem_sent = True
                    if _PacketLogFileEnabled:
                        lg.out(0, '        \033[2;49;90mPUSH %d bytes to %s://%r\033[0m' % (
                            self.filesize, proto, host), log_name='packet', showtime=True)
            if not workitem_sent:
                self.automat('nothing-to-send')
                lg.warn('(wide) no supported protocols with %s' % self.remote_idurl)
            else:
                self.automat('items-sent')
            return
        # send to one of his contacts,
        # now need to decide which transport to use
        # let's prepare his contacts first
        byproto = self.remote_identity.getContactsByProto()
        tcp_contact = None
        if settings.enableTCP() and settings.enableTCPsending():
            tcp_contact = byproto.get('tcp', None)
        udp_contact = None
        if settings.enableUDP() and settings.enableUDPsending():
            udp_contact = byproto.get('udp', None)
        http_contact = None
        if settings.enableHTTP() and settings.enableHTTPsending():
            http_contact = byproto.get('http', None)
        proxy_contact = None
        if settings.enablePROXY() and settings.enablePROXYsending():
            proxy_contact = byproto.get('proxy', None)
        working_protos = p2p_stats.peers_protos().get(self.remote_idurl, set())
        # tcp seems to be the most stable proto
        # now let's check if we know his local IP and
        # he enabled tcp in his settings to be able to receive packets from others
        # try to send to his local IP first, not external
        if tcp_contact and localIP:
            if gateway.is_installed('tcp') and gateway.can_send(proto):
                proto, host, port, fn = nameurl.UrlParse(tcp_contact)
                if port:
                    host = localIP + ':' + str(port)
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                gateway.send_file(strng.to_bin(self.remote_idurl), proto, host, self.filename, self.description, self)
                self.items.append(WorkItem(proto, host, self.filesize))
                if _PacketLogFileEnabled:
                    lg.out(0, '        \033[2;49;90mPUSH %d bytes to %s://%r\033[0m' % (
                        self.filesize, proto, host), log_name='packet', showtime=True)
                self.automat('items-sent')
                return
        # tcp is the best proto - if it is working - this is the best case!!!
        if tcp_contact and 'tcp' in working_protos:
            proto, host, port, fn = nameurl.UrlParse(tcp_contact)
            if host.strip() and gateway.is_installed(proto) and gateway.can_send(proto):
                if port:
                    host = host + ':' + str(port)
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                gateway.send_file(strng.to_bin(self.remote_idurl), proto, host, self.filename, self.description)
                self.items.append(WorkItem(proto, host, self.filesize))
                if _PacketLogFileEnabled:
                    lg.out(0, '        \033[2;49;90mPUSH %d bytes to %s://%r\033[0m' % (
                        self.filesize, proto, host), log_name='packet', showtime=True)
                self.automat('items-sent')
                return
        # udp contact
        if udp_contact and 'udp' in working_protos:
            proto, host = nameurl.IdContactSplit(udp_contact)
            if host.strip() and gateway.is_installed('udp') and gateway.can_send(proto):
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                gateway.send_file(strng.to_bin(self.remote_idurl), proto, host, self.filename, self.description, self)
                self.items.append(WorkItem(proto, host, self.filesize))
                if _PacketLogFileEnabled:
                    lg.out(0, '        \033[2;49;90mPUSH %d bytes to %s://%r\033[0m' % (
                        self.filesize, proto, host), log_name='packet', showtime=True)
                self.automat('items-sent')
                return
        # http contact
        if http_contact and 'http' in working_protos:
            proto, host, port, _ = nameurl.UrlParse(http_contact)
            if host.strip() and gateway.is_installed(proto) and gateway.can_send(proto):
                if port:
                    host = host + ':' + str(port)
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                gateway.send_file(strng.to_bin(self.remote_idurl), proto, host, self.filename, self.description, self)
                self.items.append(WorkItem(proto, host, self.filesize))
                if _PacketLogFileEnabled:
                    lg.out(0, '        \033[2;49;90mPUSH %d bytes to %s://%r\033[0m' % (
                        self.filesize, proto, host), log_name='packet', showtime=True)
                self.automat('items-sent')
                return
        # proxy contact - he may use other node to receive and send packets
        if proxy_contact and 'proxy' in working_protos:
            proto, host = nameurl.IdContactSplit(proxy_contact)
            if host.strip() and gateway.is_installed('proxy') and gateway.can_send(proto):
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                gateway.send_file(strng.to_bin(self.remote_idurl), proto, host, self.filename, self.description, self)
                self.items.append(WorkItem(proto, host, self.filesize))
                if _PacketLogFileEnabled:
                    lg.out(0, '        \033[2;49;90mPUSH %d bytes to %s://%r\033[0m' % (
                        self.filesize, proto, host), log_name='packet', showtime=True)
                self.automat('items-sent')
                return
        # finally use the first proto we supported if we can not find the best preferable method
        for contactmethod in self.remote_identity.getContacts():
            proto, host, port, fn = nameurl.UrlParse(contactmethod)
            if port:
                host = host + ':' + str(port)
            # if method exist but empty - don't use it
            if host.strip():
                # try sending with tcp even if it is switched off in the settings
                if gateway.is_installed(proto) and gateway.can_send(proto):
                    if settings.enableTransport(proto) and settings.transportSendingIsEnabled(proto):
                        gateway.send_file(strng.to_bin(self.remote_idurl), strng.to_text(proto), strng.to_bin(host), self.filename, self.description, self)
                        self.items.append(WorkItem(strng.to_text(proto), strng.to_bin(host), self.filesize))
                        if _PacketLogFileEnabled:
                            lg.out(0, '        \033[2;49;90mPUSH %d bytes to %s://%r\033[0m' % (
                                self.filesize, proto, host), log_name='packet', showtime=True)
                        self.automat('items-sent')
                        return
        self.automat('nothing-to-send')
        lg.warn('no supported protocols with %s : %s %s %s, byproto:%s' % (
            self.remote_idurl, tcp_contact, udp_contact, working_protos, str(byproto)))

    def _pop(self, packet_args):
        self.popped_item = None
        if len(packet_args) == 4:
            transfer_id, status, size, error_message = packet_args
            for i in self.items:
                if i.transfer_id and i.transfer_id == transfer_id:
                    self.items.remove(i)
                    i.status = status
                    i.error_message = error_message
                    i.bytes_sent = size
                    self.results.append(i)
                    self.popped_item = i
                    if _PacketLogFileEnabled:
                        lg.out(0, '            \033[2;49;90mPOP %d bytes to %s://%r TID=%r status=%r\033[0m' % (
                            size, i.proto, i.host, i.transfer_id, status), log_name='packet', showtime=True)
                    break
        elif len(packet_args) == 6:
            proto, host, filename, size, descr, err_msg = packet_args
            for i in self.items:
                if i.proto == proto and i.host == host:
                    self.items.remove(i)
                    i.status = 'failed'
                    i.error_message = err_msg
                    i.bytes_sent = size
                    self.results.append(i)
                    self.popped_item = i
                    if _PacketLogFileEnabled:
                        lg.out(0, '            \033[2;49;90mPOP %d bytes to %s://%r TID=%r status=%r\033[0m' % (
                            size, i.proto, i.host, i.transfer_id, i.status), log_name='packet', showtime=True)
                    break
        if not self.popped_item:
            raise Exception('Failed to populate active item')

#------------------------------------------------------------------------------
