#!/usr/bin/env python
# packet_out.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
    * :red:`request-failed`
    * :red:`response-timeout`
    * :red:`run`
    * :red:`unregister-item`
    * :red:`write-error`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import map
from six.moves import range

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

_PacketLogFileEnabled = False

#------------------------------------------------------------------------------

import os
import time

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred, CancelledError

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.p2p import commands
from bitdust.p2p import p2p_stats

from bitdust.lib import nameurl
from bitdust.lib import strng
from bitdust.lib import net_misc

from bitdust.system import tmpfile

from bitdust.contacts import contactsdb
from bitdust.contacts import identitycache

from bitdust.main import settings
from bitdust.main import config

from bitdust.transport import callback

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_OutboxQueue = []
_PacketsCounter = 0

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


def queue():
    global _OutboxQueue
    return _OutboxQueue


def create(outpacket, wide, callbacks, target=None, route=None, response_timeout=None, keep_alive=True, skip_ack=False):
    if _Debug:
        lg.out(
            _DebugLevel, 'packet_out.create [%s/%s/%s]:%s(%s) target=%r route=%r callbacks=%s' % (
                nameurl.GetName(outpacket.OwnerID),
                nameurl.GetName(outpacket.CreatorID),
                nameurl.GetName(outpacket.RemoteID),
                outpacket.Command,
                outpacket.PacketID,
                target,
                route,
                list(callbacks.keys()),
            )
        )
    p = PacketOut(outpacket, wide, callbacks, target, route, response_timeout, keep_alive, skip_ack=skip_ack)
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
                if p.remote_idurl and id_url.is_cached(p.remote_idurl) and id_url.is_cached(remote_idurl):
                    if id_url.field(remote_idurl).to_bin() != id_url.field(p.remote_idurl).to_bin():
                        if _Debug:
                            lg.out(_DebugLevel, 'packet_out.search found a packet addressed to another user: %s != %s' % (p.remote_idurl, remote_idurl))
                            lg.args(_DebugLevel, proto=proto, host=host, filename=filename, route=p.route, outpacket=p.outpacket)
                        continue
                return p, i
    if _Debug:
        for p in queue():
            if p.filename:
                lg.out(_DebugLevel, '%s [%s]' % (os.path.basename(p.filename), ('|'.join(['%s:%s' % (i.proto, i.host) for i in p.items]))))
            else:
                lg.warn('%s was not initialized yet' % str(p))
    return None, None


def search_by_packet_id(packet_id):
    result = []
    for p in queue():
        if p.outpacket.PacketID.count(packet_id):
            result.append(p)
    if _Debug:
        lg.out(_DebugLevel, 'packet_out.search_by_packet_id %s:' % packet_id)
        lg.out(_DebugLevel, '%s' % ('        \n'.join(map(str, result))))
    return result


def search_many(
    proto=None,
    host=None,
    filename=None,
    command=None,
    remote_idurl=None,
    packet_id=None,
):
    results = []
    for p in queue():
        if remote_idurl and id_url.field(p.remote_idurl).to_bin() != id_url.field(remote_idurl).to_bin():
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
        lg.out(_DebugLevel, 'packet_out.search_many query: (%s, %s, %s, %s) found %d items : ' % (proto, host, filename, remote_idurl, len(results)))
        lg.out(_DebugLevel, '%s' % ('        \n'.join(map(str, results))))
    return results


def search_by_transfer_id(transfer_id):
    for p in queue():
        for i in p.items:
            if i.transfer_id and i.transfer_id == transfer_id:
                return p, i
    return None, None


def search_by_response_packet(newpacket=None, proto=None, host=None, outgoing_command=None, incoming_command=None, incoming_packet_id=None, incoming_owner_idurl=None, incoming_creator_idurl=None, incoming_remote_idurl=None):
    result = []
    if incoming_owner_idurl is None and newpacket:
        incoming_owner_idurl = newpacket.OwnerID
    if incoming_creator_idurl is None and newpacket:
        incoming_creator_idurl = newpacket.CreatorID
    if incoming_remote_idurl is None and newpacket:
        incoming_remote_idurl = newpacket.RemoteID
    if incoming_packet_id is None and newpacket:
        incoming_packet_id = newpacket.PacketID
    if incoming_command is None and newpacket:
        incoming_command = newpacket.Command
    if _Debug:
        lg.out(
            _DebugLevel, 'packet_out.search_by_response_packet for incoming [%s/%s/%s]:%s|%s@%s from [%s://%s]' % (
                nameurl.GetName(incoming_owner_idurl),
                nameurl.GetName(incoming_creator_idurl),
                nameurl.GetName(incoming_remote_idurl),
                outgoing_command,
                incoming_command,
                incoming_packet_id,
                proto,
                host,
            )
        )
    matching_packet_ids = []
    matching_packet_ids.append(incoming_packet_id.lower())
    if incoming_command and incoming_command in [commands.Data(), commands.Retrieve()] and id_url.is_cached(incoming_owner_idurl) and incoming_owner_idurl == my_id.getIDURL():
        my_rotated_idurls = id_url.list_known_idurls(my_id.getIDURL(), num_revisions=10, include_revisions=False)
        # TODO: my_rotated_idurls can be cached for optimization
        for another_idurl in my_rotated_idurls:
            another_packet_id = global_id.SubstitutePacketID(incoming_packet_id, idurl=another_idurl).lower()
            if another_packet_id not in matching_packet_ids:
                matching_packet_ids.append(another_packet_id)
    # if len(matching_packet_ids) > 1:
    #     lg.warn('multiple packet IDs expecting to match for %r: %r' % (newpacket, matching_packet_ids))
    matching_packet_ids_count = 0
    matching_command_ack_count = 0
    for p in queue():
        if p.outpacket.PacketID.lower() not in matching_packet_ids:
            # PacketID of incoming packet not matching with that outgoing packet
            continue
        matching_packet_ids_count += 1
        if p.outpacket.PacketID != incoming_packet_id:
            lg.warn('packet ID in queue "almost" matching with incoming: %s ~ %s' % (p.outpacket.PacketID, incoming_packet_id))
        if outgoing_command is None and not commands.IsCommandAck(p.outpacket.Command, incoming_command):
            # this command must not be in the reply
            continue
        matching_command_ack_count += 1
        if outgoing_command is not None and outgoing_command != p.outpacket.Command:
            # just in case if we are looking for some specific outgoing command
            continue
        expected_recipient = [
            p.outpacket.RemoteID,
        ]
        if id_url.is_cached(p.outpacket.RemoteID) and id_url.is_cached(p.remote_idurl):
            if p.outpacket.RemoteID != id_url.field(p.remote_idurl):
                # for Retrieve() packets I expect response exactly from target node
                if p.outpacket.Command != commands.Retrieve():
                    # outgoing packet was addressed to another node, so that means we need to expect response from another node also
                    expected_recipient.append(id_url.field(p.remote_idurl))
        matched = False
        if not id_url.is_cached(incoming_remote_idurl):
            identitycache.start_one(incoming_remote_idurl)
        else:
            if id_url.is_in(incoming_owner_idurl, expected_recipient, as_field=False):
                if id_url.is_the_same(my_id.getIDURL(), incoming_remote_idurl):
                    if _Debug:
                        lg.out(_DebugLevel, 'packet_out.search_by_response_packet    matched with incoming owner: %s' % expected_recipient)
                    matched = True
            if not matched:
                if id_url.is_in(incoming_creator_idurl, expected_recipient, as_field=False):
                    if id_url.is_the_same(my_id.getIDURL(), incoming_remote_idurl):
                        if _Debug:
                            lg.out(_DebugLevel, 'packet_out.search_by_response_packet    matched with incoming creator: %s' % expected_recipient)
                        matched = True
            if not matched:
                if id_url.is_in(incoming_remote_idurl, expected_recipient, as_field=False):
                    if id_url.is_the_same(my_id.getIDURL(), incoming_owner_idurl) and incoming_command == commands.Data():
                        if _Debug:
                            lg.out(_DebugLevel, 'packet_out.search_by_response_packet    matched my own incoming Data with incoming remote: %s' % expected_recipient)
                        matched = True
        if matched:
            result.append(p)
            if _Debug:
                lg.out(
                    _DebugLevel, 'packet_out.search_by_response_packet        FOUND pending outbox [%s/%s/%s]:%s(%s) cb:%s' % (
                        nameurl.GetName(p.outpacket.OwnerID),
                        nameurl.GetName(p.outpacket.CreatorID),
                        nameurl.GetName(p.outpacket.RemoteID),
                        p.outpacket.Command,
                        p.outpacket.PacketID,
                        list(p.callbacks.keys()),
                    )
                )
    if len(result) == 0:
        if _Debug:
            lg.out(_DebugLevel, 'packet_out.search_by_response_packet        DID NOT FOUND pending packets in outbox queue matching incoming %r' % newpacket)
            lg.args(_DebugLevel, pkt_ids_count=matching_packet_ids_count, cmd_ack_count=matching_command_ack_count, matching_packet_ids=matching_packet_ids)
    return result


def search_similar_packets(outpacket):
    return search_many(
        command=outpacket.Command,
        packet_id=outpacket.PacketID,
        remote_idurl=outpacket.RemoteID,
    )


#------------------------------------------------------------------------------


def on_outgoing_packet_failed(result, *a, **kw):
    if _Debug:
        lg.args(_DebugLevel, result=result, args=a, kwargs=kw)
    if result.type == CancelledError:
        return None
    return result


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

    MESSAGES = {
        'MSG_1': 'file in queue was cancelled',
        'MSG_2': 'sending file was cancelled',
        'MSG_3': 'response waiting were cancelled',
        'MSG_4': 'outgoing packet was cancelled',
        'MSG_5': 'pushing outgoing packet was cancelled',
    }

    def __init__(self, outpacket, wide, callbacks={}, target=None, route=None, response_timeout=None, keep_alive=True, skip_ack=False):
        self.outpacket = outpacket
        if self.outpacket.PacketID.count('&'):
            packet_label = self.outpacket.PacketID.replace(':', '').replace('/', '').replace('_', '').replace('&', '')
        else:
            packet_label = global_id.ParseGlobalID(self.outpacket.PacketID)['path']
            if not packet_label:
                packet_label = self.outpacket.PacketID.replace(':', '').replace('/', '').replace('_', '')
        self.wide = wide
        self.callbacks = {}
        self.caching_deferred = None
        self.finished_deferred = Deferred()
        self.finished_deferred.addErrback(on_outgoing_packet_failed)
        self.final_result = None
        self.description = self.outpacket.Command + '[' + self.outpacket.PacketID + ']'
        self.remote_idurl = id_url.field(target) if target else None
        self.route = route
        self.response_timeout = response_timeout
        if self.route and 'remoteid' in self.route:
            self.description = self.route.get('description', self.description)
            self.remote_idurl = id_url.field(self.route['remoteid'])
        if not self.remote_idurl:
            self.remote_idurl = self.outpacket.RemoteID
        if not self.remote_idurl:
            raise ValueError('outgoing packet %r did not define remote idurl' % outpacket)
        self.remote_name = nameurl.GetName(self.outpacket.RemoteID)
        if id_url.to_bin(self.remote_idurl) != self.outpacket.RemoteID.to_bin():
            self.label = 'out_%d_%s_%s_via_%s' % (
                get_packets_counter(),
                packet_label,
                self.remote_name,
                nameurl.GetName(self.remote_idurl),
            )
        else:
            self.label = 'out_%d_%s_%s' % (get_packets_counter(), packet_label, self.remote_name)
        self.keep_alive = keep_alive
        self.skip_ack = skip_ack
        automat.Automat.__init__(
            self,
            name=self.label,
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
            publish_events=False,
        )
        increment_packets_counter()
        for command, cb in callbacks.items():
            self.set_callback(command, cb)

    def __repr__(self):
        """
        Will return something like: "out_123_alice[Data(9999999999)](SENDING)".
        """
        packet_label = '?'
        if self.outpacket:
            packet_label = '%s@%s' % (
                self.outpacket.Command,
                self.outpacket.PacketID,
            )  # .replace(':', '').replace('/', '').replace('_', '')
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
        self.remote_identity = None
        if last_modified_time and time.time() - last_modified_time < 5*60:
            # use known that identity from cache if we sure that it is fresh enough
            self.remote_identity = contactsdb.get_contact_identity(self.remote_idurl)
            if self.remote_identity:
                if _Debug:
                    lg.out(_DebugLevel, 'packet_out.init  found fresh and cached identity: %s' % self.remote_idurl)
            else:
                if _Debug:
                    lg.out(_DebugLevel, 'packet_out.init  did not found cached identity: %s' % self.remote_idurl)
        else:
            if last_modified_time:
                if _Debug:
                    lg.out(_DebugLevel, 'packet_out.init  cached identity copy is out-dated: %s' % self.remote_idurl)
            else:
                if _Debug:
                    lg.out(_DebugLevel, 'packet_out.init  no cached identity copy exist or last caching time unknown: %s' % self.remote_idurl)
        self.packetdata = None
        self.filename = None
        self.filesize = None
        self.items = []
        self.results = []
        self.response_packet = None
        self.response_info = None
        self.timeout = None
        if self.response_timeout:
            self.timers['response-timeout'] = (self.response_timeout, [
                'RESPONSE?',
            ])

    def msg(self, msgid, *args, **kwargs):
        return self.MESSAGES.get(msgid, '')

    def is_timed_out(self):
        if self.state == 'RESPONSE?':
            return False
        if self.time is None or self.timeout is None:
            return False
        return time.time() - self.time > self.timeout

    def set_callback(self, command, cb):
        if command not in self.callbacks.keys():
            self.callbacks[command] = []
        self.callbacks[command].append(cb)

    def A(self, event, *args, **kwargs):
        #---SENDING---
        if self.state == 'SENDING':
            if event == 'register-item':
                self.doSetTransferID(*args, **kwargs)
            elif event == 'cancel':
                self.state = 'CANCEL'
                self.doCancelItems(*args, **kwargs)
                self.doErrMsg(event, self.msg('MSG_2', *args, **kwargs))
                self.doReportCancelItems(*args, **kwargs)
                self.doPopItems(*args, **kwargs)
                self.doReportCancelled(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'item-cancelled' and self.isMoreItems(*args, **kwargs):
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
            elif (event == 'unregister-item' and self.isFailed(*args, **kwargs)) or (event == 'item-cancelled' and not self.isMoreItems(*args, **kwargs)):
                self.state = 'FAILED'
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'unregister-item' and not self.isFailed(*args, **kwargs) and self.isAckNeeded(*args, **kwargs):
                self.state = 'RESPONSE?'
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
            elif event == 'unregister-item' and not self.isFailed(*args, **kwargs) and not self.isAckNeeded(*args, **kwargs):
                self.state = 'SENT'
                self.doPopItem(*args, **kwargs)
                self.doReportItem(*args, **kwargs)
                self.doReportDoneNoAck(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'run' and self.isRemoteIdentityKnown(*args, **kwargs):
                self.state = 'ITEMS?'
                self.doInit(*args, **kwargs)
                self.Cancelled = False
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
                self.Cancelled = False
                self.doReportStarted(*args, **kwargs)
                self.doSerializeAndWrite(*args, **kwargs)
                self.doPushItems(*args, **kwargs)
            elif event == 'failed':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'cancel':
                self.state = 'CANCEL'
                self.doErrMsg(event, self.msg('MSG_4', *args, **kwargs))
                self.doReportCancelled(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---ITEMS?---
        elif self.state == 'ITEMS?':
            if event == 'nothing-to-send' or event == 'write-error':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'items-sent' and not self.Cancelled:
                self.state = 'IN_QUEUE'
            elif event == 'cancel':
                self.Cancelled = True
            elif event == 'items-sent' and self.Cancelled:
                self.state = 'CANCEL'
                self.doCancelItems(*args, **kwargs)
                self.doErrMsg(event, self.msg('MSG_5', *args, **kwargs))
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
                self.doErrMsg(event, self.msg('MSG_1', *args, **kwargs))
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
        #---RESPONSE?---
        elif self.state == 'RESPONSE?':
            if event == 'cancel':
                self.state = 'CANCEL'
                self.doErrMsg(event, self.msg('MSG_3', *args, **kwargs))
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
            elif (event == 'response-timeout' or event == 'request-failed') and not self.isDataExpected(*args, **kwargs):
                self.state = 'SENT'
                self.doReportTimeOut(*args, **kwargs)
                self.doReportDoneNoAck(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif (event == 'response-timeout' or event == 'request-failed') and self.isDataExpected(*args, **kwargs):
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---SENT---
        elif self.state == 'SENT':
            pass
        #---CANCEL---
        elif self.state == 'CANCEL':
            pass
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
        if self.skip_ack:
            return False
        if commands.IsReplyExpected(self.outpacket.Command):
            if not self.response_timeout and self.outpacket.Command == commands.Message():
                # an exception for sending back a Message() packet with list of archived messages
                # TODO: more elegant solution to be found
                return False
            return True
        return len(self.callbacks.get(commands.Ack(), [])) + len(self.callbacks.get(commands.Fail(), [])) > 0

    def isFailed(self, *args, **kwargs):
        """
        Condition method.
        """
        return args[0][1] != 'finished'

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
        if len(self.callbacks.get(newpacket.Command, [])) > 0:
            return True
        if not commands.IsCommandAck(self.outpacket.Command, newpacket.Command):
            return False
        return True

    def isDataExpected(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.callbacks.get(commands.Data(), [])) > 0

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
        self.caching_deferred.addTimeout(60, clock=reactor)

    def doSerializeAndWrite(self, *args, **kwargs):
        """
        Action method.
        """
        # serialize and write packet on disk
        a_packet = self.outpacket
        if self.route:
            a_packet = self.route.get('packet', a_packet)
        try:
            fileno, self.filename = tmpfile.make('outbox', extension='.out')
            self.packetdata = a_packet.Serialize()
            os.write(fileno, self.packetdata)
            os.close(fileno)
            self.filesize = len(self.packetdata)
            if self.filesize < 1024*10:
                if self.response_timeout:
                    self.timeout = self.response_timeout
                else:
                    self.timeout = settings.P2PTimeOut()
            elif self.filesize > 1024*1024:
                self.timeout = 5 + int(self.filesize/float(settings.SendingSpeedLimit()))
            else:
                self.timeout = 300
        except:
            lg.exc()
            self.packetdata = None
            reactor.callLater(0, self.automat, 'write-error')  # @UndefinedVariable

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
        proto, host, _, transfer_id = args[0]
        for i in range(len(self.items)):
            if self.items[i].proto == proto:
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
        from bitdust.transport import gateway
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
            raise Exception('current outgoing item not exist')
        if _PacketLogFileEnabled:
            if self.popped_item.status == 'finished':
                lg.out(
                    0,
                    '\033[0;49;90mSENT %d bytes to %s://%s TID:%s\033[0m' % (
                        self.popped_item.bytes_sent,
                        strng.to_text(self.popped_item.proto),
                        strng.to_text(self.popped_item.host),
                        self.popped_item.transfer_id,
                    ),
                    log_name='packet',
                    showtime=True,
                )
            else:
                lg.out(
                    0,
                    '\033[0;49;91mFAILED %d bytes to %s://%s with status=%r TID:%s\033[0m' % (
                        self.popped_item.bytes_sent,
                        strng.to_text(self.popped_item.proto),
                        strng.to_text(self.popped_item.host),
                        self.popped_item.status,
                        self.popped_item.transfer_id,
                    ),
                    log_name='packet',
                    showtime=True,
                )
        p2p_stats.count_outbox(self.remote_idurl, self.popped_item.proto, self.popped_item.status, self.popped_item.bytes_sent)
        callback.run_finish_file_sending_callbacks(self, self.popped_item, self.popped_item.status, self.popped_item.bytes_sent, self.popped_item.error_message)
        if self.popped_item.status == 'failed':
            for cb in self.callbacks.pop('item-failed', []):
                cb(self, self.popped_item)
        else:
            for cb in self.callbacks.pop('item-sent', []):
                cb(self, self.popped_item)
        self.popped_item = None

    def doReportCancelItems(self, *args, **kwargs):
        """
        Action method.
        """
        for item in self.results:
            if _PacketLogFileEnabled:
                lg.out(
                    0,
                    '\033[0;49;90mOUT CANCELED %s://%s TID:%s\033[0m' % (strng.to_text(item.proto), strng.to_text(item.host), item.transfer_id),
                    log_name='packet',
                    showtime=True,
                )
            p2p_stats.count_outbox(self.remote_idurl, item.proto, 'failed', 0)
            callback.run_finish_file_sending_callbacks(self, item, 'failed', 0, self.error_message)

    def doReportResponse(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'packet_out.doReportResponse %d callbacks known' % len(self.callbacks))
        for cb in self.callbacks.pop(self.response_packet.Command, []):
            if _Debug:
                lg.out(_DebugLevel, '        calling to %r with %r' % (cb, self.response_packet))
            try:
                cb(self.response_packet, self.response_info)
            except:
                lg.exc()

    def doReportTimeOut(self, *args, **kwargs):
        """
        Action method.
        """
        self.final_result = 'timeout'
        if _PacketLogFileEnabled:
            lg.out(
                0,
                '\033[1;49;91mOUT TIMEOUT %s(%s) sending from %s to %s\033[0m' % (
                    self.outpacket.Command,
                    self.outpacket.PacketID,
                    global_id.UrlToGlobalID(self.outpacket.CreatorID),
                    global_id.UrlToGlobalID(self.remote_idurl),
                ),
                log_name='packet',
                showtime=True,
            )
        for cb in self.callbacks.pop(None, []):
            cb(self)
        for cb in self.callbacks.pop('timeout', []):
            cb(self, 'timeout')

    def doReportDoneWithAck(self, *args, **kwargs):
        """
        Action method.
        """
        self.final_result = 'finished'
        if _PacketLogFileEnabled:
            newpacket, _ = args[0]
            if newpacket.Command in [
                commands.Fail(),
            ]:
                lg.out(
                    0,
                    '                \033[0;49;31mRECEIVE %s on %s(%s) with %s bytes from %s to %s TID:%r\033[0m' % (
                        newpacket.Command,
                        self.outpacket.Command,
                        self.outpacket.PacketID,
                        self.filesize or '?',
                        global_id.UrlToGlobalID(self.outpacket.CreatorID),
                        global_id.UrlToGlobalID(self.remote_idurl),
                        [i.transfer_id for i in self.results],
                    ),
                    log_name='packet',
                    showtime=True,
                )
            else:
                lg.out(
                    0,
                    '                \033[1;49;96mRECEIVE %s on %s(%s) with %s bytes from %s to %s TID:%r\033[0m' % (
                        newpacket.Command,
                        self.outpacket.Command,
                        self.outpacket.PacketID,
                        self.filesize or '?',
                        global_id.UrlToGlobalID(self.outpacket.CreatorID),
                        global_id.UrlToGlobalID(self.remote_idurl),
                        [i.transfer_id for i in self.results],
                    ),
                    log_name='packet',
                    showtime=True,
                )
        callback.run_queue_item_status_callbacks(self, 'finished', '')
        for cb in self.callbacks.pop('acked', []):
            cb(self, 'finished')
        if not self.finished_deferred.called:
            self.finished_deferred.callback(self)

    def doReportDoneNoAck(self, *args, **kwargs):
        """
        Action method.
        """
        self.final_result = 'finished_no_ack'
        if _PacketLogFileEnabled:
            lg.out(
                0,
                '\033[0;49;95mOUT %s(%s) with %s bytes from %s to %s TID:%r\033[0m' % (
                    self.outpacket.Command,
                    self.outpacket.PacketID,
                    self.filesize or '?',
                    global_id.UrlToGlobalID(self.outpacket.CreatorID),
                    global_id.UrlToGlobalID(self.remote_idurl),
                    [i.transfer_id for i in self.results],
                ),
                log_name='packet',
                showtime=True,
            )
        if (args and args[0]) or self.skip_ack:
            callback.run_queue_item_status_callbacks(self, 'finished', '')
        else:
            callback.run_queue_item_status_callbacks(self, 'finished', 'unanswered')
        for cb in self.callbacks.pop('sent', []):
            cb(self, 'finished')
        if not self.finished_deferred.called:
            self.finished_deferred.callback(self)

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            msg = str(args[0][-1])
        except:
            msg = 'failed'
        self.final_result = 'failed'
        if _PacketLogFileEnabled:
            lg.out(
                0,
                '\033[0;49;91mOUT FAILED %s(%s) with %s bytes from %s to %s TID:%r : %s\033[0m' % (
                    self.outpacket.Command,
                    self.outpacket.PacketID,
                    self.filesize or '?',
                    global_id.UrlToGlobalID(self.outpacket.CreatorID),
                    global_id.UrlToGlobalID(self.remote_idurl),
                    [i.transfer_id for i in self.results],
                    msg,
                ),
                log_name='packet',
                showtime=True,
            )
        callback.run_queue_item_status_callbacks(self, 'failed', msg)
        for cb in self.callbacks.pop('failed', []):
            cb(self, msg)
        if not self.finished_deferred.called:
            self.finished_deferred.callback(self)

    def doReportCancelled(self, *args, **kwargs):
        """
        Action method.
        """
        msg = 'cancelled'
        if args and args[0]:
            msg = str(args[0])
        else:
            msg = 'cancelled'
        self.final_result = msg
        if self.final_result == 'timeout':
            if _PacketLogFileEnabled:
                lg.out(
                    0,
                    '\033[0;49;97mOUT CANCELED %s(%s) after TIMEOUT with %s bytes from %s to %s TID:%r\033[0m' % (
                        self.outpacket.Command,
                        self.outpacket.PacketID,
                        self.filesize or '?',
                        global_id.UrlToGlobalID(self.outpacket.CreatorID),
                        global_id.UrlToGlobalID(self.remote_idurl),
                        [i.transfer_id for i in self.results],
                    ),
                    log_name='packet',
                    showtime=True,
                )
            for cb in self.callbacks.pop(None, []):
                cb(self)
            for cb in self.callbacks.pop('timeout', []):
                cb(self, 'timeout')
        else:
            if _PacketLogFileEnabled:
                lg.out(
                    0,
                    '\033[0;49;97mOUT CANCELED %s(%s) with %s bytes from %s to %s TID:%r : %s\033[0m' % (
                        self.outpacket.Command,
                        self.outpacket.PacketID,
                        self.filesize or '?',
                        global_id.UrlToGlobalID(self.outpacket.CreatorID),
                        global_id.UrlToGlobalID(self.remote_idurl),
                        [i.transfer_id for i in self.results],
                        msg,
                    ),
                    log_name='packet',
                    showtime=True,
                )
            callback.run_queue_item_status_callbacks(self, 'cancelled', msg)
            for cb in self.callbacks.pop('cancelled', []):
                cb(self, msg)
            for cb in self.callbacks.pop(None, []):
                cb(self)
            if not self.finished_deferred.called:
                self.finished_deferred.callback(self)

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
        queue().remove(self)
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
        if self.finished_deferred and not self.finished_deferred.called:
            self.finished_deferred.cancel()
        self.destroy()

    def _on_remote_identity_cached(self, xmlsrc):
        self.remote_identity = contactsdb.get_contact_identity(self.remote_idurl)
        if self.remote_identity is None:
            reactor.callLater(0, self.automat, 'failed')  # @UndefinedVariable
        else:
            reactor.callLater(0, self.automat, 'remote-identity-on-hand')  # @UndefinedVariable
        return xmlsrc

    def _on_remote_identity_cache_failed(self, err):
        lg.warn('%s : %s' % (repr(self), str(err)))
        if self.outpacket:
            reactor.callLater(0, self.automat, 'failed')  # @UndefinedVariable
        return None

    def _push(self):
        from bitdust.transport import gateway
        if self.route and 'proto' in self.route and 'host' in self.route and 'remoteid' in self.route:
            # if this packet is routed - send directly to the host specified in the route info
            proto = strng.to_text(self.route['proto'])
            host = strng.to_bin(self.route['host'])
            if not gateway.send_file(
                strng.to_bin(self.route['remoteid']),
                proto,
                host,
                self.filename,
                self.description,
                self,
            ):
                self.automat('nothing-to-send')
                if _PacketLogFileEnabled:
                    lg.out(0, '\033[0;49;97mSKIP sending routed %r : filtered out\033[0m' % self, log_name='packet', showtime=True)
                return
            self.items.append(WorkItem(proto, host, self.filesize))
            if _PacketLogFileEnabled:
                lg.out(
                    0,
                    '\033[0;49;90mPUSH %d bytes to %s://%s ROUTED\033[0m' % (self.filesize, strng.to_text(proto), strng.to_text(host)),
                    log_name='packet',
                    showtime=True,
                )
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
                        gateway.is_installed(proto) and \
                        gateway.can_send(proto):
                    if proto == 'tcp' and localIP:
                        host = localIP
                    if not gateway.send_file(
                        self.remote_idurl.to_bin(),
                        proto,
                        host,
                        self.filename,
                        self.description,
                        self,
                    ):
                        continue
                    self.items.append(WorkItem(proto, host, self.filesize))
                    workitem_sent = True
                    if _PacketLogFileEnabled:
                        lg.out(
                            0,
                            '\033[0;49;90mPUSH %d bytes to %s://%s\033[0m' % (self.filesize, strng.to_text(proto), strng.to_text(host)),
                            log_name='packet',
                            showtime=True,
                        )
            if not workitem_sent:
                self.automat('nothing-to-send')
                lg.warn('(wide) no supported protocols with %s' % self.remote_idurl)
                if _PacketLogFileEnabled:
                    lg.out(0, '\033[0;49;97mSKIP wide sending %r : no supported protocols\033[0m' % self, log_name='packet', showtime=True)
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
                proto, host, port, _ = nameurl.UrlParse(tcp_contact)
                if port:
                    host = localIP + ':' + str(port)
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                if gateway.send_file(self.remote_idurl.to_bin(), proto, host, self.filename, self.description, self):
                    self.items.append(WorkItem(proto, host, self.filesize))
                    if _PacketLogFileEnabled:
                        lg.out(
                            0,
                            '\033[0;49;90mPUSH %d bytes to %s://%s\033[0m' % (self.filesize, strng.to_text(proto), strng.to_text(host)),
                            log_name='packet',
                            showtime=True,
                        )
                    self.automat('items-sent')
                    return
        # tcp is the best proto - if it is working - this is the best case!!!
        if tcp_contact and 'tcp' in working_protos:
            proto, host, port, _ = nameurl.UrlParse(tcp_contact)
            if host.strip() and gateway.is_installed(proto) and gateway.can_send(proto):
                if port:
                    host = host + ':' + str(port)
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                if gateway.send_file(self.remote_idurl.to_bin(), proto, host, self.filename, self.description):
                    self.items.append(WorkItem(proto, host, self.filesize))
                    if _PacketLogFileEnabled:
                        lg.out(
                            0,
                            '\033[0;49;90mPUSH %d bytes to %s://%s\033[0m' % (self.filesize, strng.to_text(proto), strng.to_text(host)),
                            log_name='packet',
                            showtime=True,
                        )
                    self.automat('items-sent')
                    return
        # udp contact
        if udp_contact and 'udp' in working_protos:
            proto, host = nameurl.IdContactSplit(udp_contact)
            if host.strip() and gateway.is_installed('udp') and gateway.can_send(proto):
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                if gateway.send_file(self.remote_idurl.to_bin(), proto, host, self.filename, self.description, self):
                    self.items.append(WorkItem(proto, host, self.filesize))
                    if _PacketLogFileEnabled:
                        lg.out(
                            0,
                            '\033[0;49;90mPUSH %d bytes to %s://%s\033[0m' % (self.filesize, strng.to_text(proto), strng.to_text(host)),
                            log_name='packet',
                            showtime=True,
                        )
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
                if gateway.send_file(self.remote_idurl.to_bin(), proto, host, self.filename, self.description, self):
                    self.items.append(WorkItem(proto, host, self.filesize))
                    if _PacketLogFileEnabled:
                        lg.out(
                            0,
                            '\033[0;49;90mPUSH %d bytes to %s://%s\033[0m' % (self.filesize, strng.to_text(proto), strng.to_text(host)),
                            log_name='packet',
                            showtime=True,
                        )
                    self.automat('items-sent')
                    return
        # proxy contact - he may use other node to receive and send packets
        if proxy_contact and 'proxy' in working_protos:
            proto, host = nameurl.IdContactSplit(proxy_contact)
            if host.strip() and gateway.is_installed('proxy') and gateway.can_send(proto):
                proto = strng.to_text(proto)
                host = strng.to_bin(host)
                if gateway.send_file(self.remote_idurl.to_bin(), proto, host, self.filename, self.description, self):
                    self.items.append(WorkItem(proto, host, self.filesize))
                    if _PacketLogFileEnabled:
                        lg.out(
                            0,
                            '\033[0;49;90mPUSH %d bytes to %s://%s\033[0m' % (self.filesize, strng.to_text(proto), strng.to_text(host)),
                            log_name='packet',
                            showtime=True,
                        )
                    self.automat('items-sent')
                    return
        # finally use the first proto we supported if we can not find the best preferable method
        for contactmethod in self.remote_identity.getContacts():
            proto, host, port, _ = nameurl.UrlParse(contactmethod)
            if port:
                host = host + ':' + str(port)
            # if method exist but empty - don't use it
            if host.strip():
                # try sending with tcp even if it is switched off in the settings
                if gateway.is_installed(proto) and gateway.can_send(proto):
                    if settings.enableTransport(proto) and settings.transportSendingIsEnabled(proto):
                        if gateway.send_file(self.remote_idurl.to_bin(), strng.to_text(proto), strng.to_bin(host), self.filename, self.description, self):
                            self.items.append(WorkItem(strng.to_text(proto), strng.to_bin(host), self.filesize))
                            if _PacketLogFileEnabled:
                                lg.out(
                                    0,
                                    '\033[0;49;90mPUSH %d bytes to %s://%s\033[0m' % (self.filesize, strng.to_text(proto), strng.to_text(host)),
                                    log_name='packet',
                                    showtime=True,
                                )
                            self.automat('items-sent')
                            return
        self.automat('nothing-to-send')
        lg.warn('no supported protocols with %s : %s %s %s, byproto:%s' % (self.remote_idurl, tcp_contact, udp_contact, working_protos, str(byproto)))
        if _PacketLogFileEnabled:
            lg.out(0, '\033[0;49;97mSKIP sending %r : no supported protocols\033[0m' % self, log_name='packet', showtime=True)

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
                        lg.out(
                            0,
                            '\033[0;49;90mPOP %d bytes to %s://%s TID=%r status=%r\033[0m' % (size, strng.to_text(i.proto), strng.to_text(i.host), i.transfer_id, status),
                            log_name='packet',
                            showtime=True,
                        )
                    break
        elif len(packet_args) == 6:
            proto, host, _, size, _, err_msg = packet_args
            for i in self.items:
                if i.proto == proto and i.host == host:
                    self.items.remove(i)
                    i.status = 'failed'
                    i.error_message = err_msg
                    i.bytes_sent = size
                    self.results.append(i)
                    self.popped_item = i
                    if _PacketLogFileEnabled:
                        lg.out(
                            0,
                            '\033[0;49;90mPOP %d bytes to %s://%s TID=%r status=%r\033[0m' % (size, strng.to_text(i.proto), strng.to_text(i.host), i.transfer_id, i.status),
                            log_name='packet',
                            showtime=True,
                        )
                    break
        if not self.popped_item:
            raise Exception('failed to populate active item')
