#!/usr/bin/env python
# proxy_receiver.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (proxy_receiver.py) is part of BitDust Software.
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
.. module:: proxy_receiver.

.. role:: red

BitDust proxy_receiver(at_startup) Automat

.. raw:: html

    <i>generated using <a href="https://bitdust.io/visio2python/" target="_blank">visio2python</a> tool</i><br>
    <a href="proxy_receiver.png" target="_blank">
    <img src="proxy_receiver.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`ack-received`
    * :red:`ack-timeout`
    * :red:`fail-received`
    * :red:`found-one-node`
    * :red:`inbox-packet`
    * :red:`init`
    * :red:`nodes-not-found`
    * :red:`request-timeout`
    * :red:`router-disconnected`
    * :red:`router-id-received`
    * :red:`sending-failed`
    * :red:`service-accepted`
    * :red:`service-refused`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-10sec`
    * :red:`timer-15sec`
    * :red:`timer-30sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import BytesIO

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 16

_PacketLogFileEnabled = False

#------------------------------------------------------------------------------

import re
import time
import random

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import packetid
from bitdust.lib import strng
from bitdust.lib import serialization
from bitdust.lib import net_misc

from bitdust.automats import automat

from bitdust.main import config
from bitdust.main import settings

from bitdust.crypt import key
from bitdust.crypt import signed
from bitdust.crypt import encrypted

from bitdust.p2p import commands
from bitdust.p2p import lookup
from bitdust.p2p import online_status

from bitdust.contacts import identitycache

from bitdust.services import driver

from bitdust.transport import callback
from bitdust.transport import packet_in
from bitdust.transport import packet_out

from bitdust.transport import gateway
from bitdust.transport.proxy import proxy_interface

from bitdust.userid import identity
from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_ProxyReceiver = None

#------------------------------------------------------------------------------


def GetRouterIDURL():
    global _ProxyReceiver
    if not _ProxyReceiver:
        return None
    return _ProxyReceiver.router_idurl


def GetPossibleRouterIDURL():
    global _ProxyReceiver
    if not _ProxyReceiver:
        return None
    return _ProxyReceiver.possible_router_idurl


def GetRouterIdentity():
    global _ProxyReceiver
    if not _ProxyReceiver:
        return None
    return _ProxyReceiver.router_identity


def GetRouterProtoHost():
    global _ProxyReceiver
    if not _ProxyReceiver:
        return None
    return _ProxyReceiver.router_proto_host


def ReadMyOriginalIdentitySource():
    return config.conf().getData('services/proxy-transport/my-original-identity').strip()


def WriteMyOriginalIdentitySource(new_identity_xml_src):
    return config.conf().setData('services/proxy-transport/my-original-identity', new_identity_xml_src)


def ReadCurrentRouter():
    return config.conf().getString('services/proxy-transport/current-router').strip()


def VerifyExistingRouter():
    if ReadCurrentRouter() and not ReadMyOriginalIdentitySource():
        lg.err('current router is set, but my original identity is empty')
        return False
    if not ReadCurrentRouter() and ReadMyOriginalIdentitySource():
        lg.err('current router is not set, but some wrong data found as original identity')
        return False
    return True


def LatestPacketReceived():
    global _ProxyReceiver
    if not _ProxyReceiver:
        return 0
    return _ProxyReceiver.latest_packet_received


#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with proxy_receiver machine.
    """
    global _ProxyReceiver
    if event is None and not args:
        return _ProxyReceiver
    if _ProxyReceiver is None:
        # set automat name and starting state here
        _ProxyReceiver = ProxyReceiver()
    if event is not None:
        _ProxyReceiver.automat(event, *args, **kwargs)
    return _ProxyReceiver


#------------------------------------------------------------------------------


class ProxyReceiver(automat.Automat):

    """
    This class implements all the functionality of the ``proxy_receiver()``
    state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['LISTEN']),
        'timer-15sec': (15.0, ['ACK?']),
        'timer-30sec': (30.0, ['FIND_NODE?']),
    }

    def __init__(self):
        """
        Builds `proxy_receiver()` state machine.
        """
        self.possible_router_idurl = None
        self.router_idurl = None
        self.router_identity = None
        self.router_id = ''
        self.router_proto_host = None
        self.request_service_packet_id = []
        self.latest_packet_received = 0
        self.router_connection_info = None
        self.traffic_in = 0
        super(ProxyReceiver, self).__init__(
            name='proxy_receiver',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=False,
            log_transitions=_Debug,
            publish_events=False,
        )

    def __repr__(self):
        return '%s_%s_%s(%s)' % (self.id, self.router_id, (self.router_connection_info or {}).get('repr', '?'), self.state)

    def to_json(self):
        j = super().to_json()
        j.update(
            {
                'proto': self.router_proto_host[0] if self.router_proto_host else '',
                'host': net_misc.pack_address(self.router_proto_host[1]) if self.router_proto_host else '',
                'idurl': self.router_idurl,
                'bytes_received': self.traffic_in,
                'bytes_sent': 0,
                'connection_info': self.router_connection_info,
                'idle_seconds': int(time.time() - self.latest_packet_received),
            }
        )
        return j

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when proxy_receiver() state were changed.
        """
        from bitdust.transport.proxy import proxy_sender
        proxy_sender.A('proxy_receiver.state', newstate)

    def A(self, event, *args, **kwargs):
        """
        The core proxy_receiver() code, generated using `visio2python
        <https://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'ack-received':
                self.state = 'SERVICE?'
                self.doSendRequestService(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop':
                self.state = 'OFFLINE'
                self.doNotifyFailed(*args, **kwargs)
            elif event == 'sending-failed':
                self.Retries += 1
                self.doSendMyIdentity(*args, **kwargs)
            elif (event == 'sending-failed' and self.Retries > 3) or event == 'ack-timeout' or event == 'fail-received' or event == 'timer-15sec':
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(*args, **kwargs)
        #---LISTEN---
        elif self.state == 'LISTEN':
            if event == 'router-id-received':
                self.doUpdateRouterID(*args, **kwargs)
            elif event == 'inbox-packet':
                self.doProcessInboxPacket(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopListening(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop':
                self.state = 'OFFLINE'
                self.doSendCancelService(*args, **kwargs)
                self.doStopListening(*args, **kwargs)
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'timer-10sec':
                self.doCheckPingRouter(*args, **kwargs)
            elif event == 'service-refused' or event == 'router-disconnected':
                self.state = 'FIND_NODE?'
                self.doStopListening(*args, **kwargs)
                self.doNotifyDisconnected(*args, **kwargs)
                self.doLookupRandomNode(*args, **kwargs)
        #---FIND_NODE?---
        elif self.state == 'FIND_NODE?':
            if event == 'found-one-node':
                self.state = 'ACK?'
                self.doRememberNode(*args, **kwargs)
                self.Retries = 0
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop' or event == 'nodes-not-found' or event == 'timer-30sec':
                self.state = 'OFFLINE'
                self.doNotifyFailed(*args, **kwargs)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'service-accepted':
                self.state = 'LISTEN'
                self.doStartListening(*args, **kwargs)
                self.doNotifyConnected(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop':
                self.state = 'OFFLINE'
                self.doSendCancelService(*args, **kwargs)
                self.doNotifyFailed(*args, **kwargs)
            elif event == 'request-timeout' or event == 'service-refused':
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(*args, **kwargs)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'start' and self.isCurrentRouterExist(*args, **kwargs):
                self.state = 'ACK?'
                self.doLoadRouterInfo(*args, **kwargs)
                self.Retries = 0
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'start' and not self.isCurrentRouterExist(*args, **kwargs):
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        return None

    def isCurrentRouterExist(self, *args, **kwargs):
        """
        Condition method.
        """
        if not ReadCurrentRouter():
            return False
        if not ReadMyOriginalIdentitySource():
            return False
        return True

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        global _PacketLogFileEnabled
        _PacketLogFileEnabled = config.conf().getBool('logs/packet-enabled')
        callback.add_queue_item_status_callback(self._on_queue_item_status_changed)

    def doLoadRouterInfo(self, *args, **kwargs):
        """
        Action method.
        """
        s = config.conf().getString('services/proxy-transport/current-router').strip()
        try:
            self.router_idurl = id_url.field(s.split(' ')[0])
            self.router_id = global_id.idurl2glob(self.router_idurl)
        except:
            lg.exc()
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver.doLoadRouterInfo : %s' % self.router_idurl)

    def doLookupRandomNode(self, *args, **kwargs):
        """
        Action method.
        """
        self._find_random_node(attempts=5)

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        reactor.callLater(0, self._do_send_identity_to_router, my_id.getLocalIdentity().serialize(), failed_event='fail-received')  # @UndefinedVariable
        identity_source = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if identity_source:
            if _Debug:
                lg.out(_DebugLevel, '    also sending identity loaded from "my-original-identity" config')
            reactor.callLater(0, self._do_send_identity_to_router, identity_source, failed_event='fail-received')  # @UndefinedVariable

    def doRememberNode(self, *args, **kwargs):
        """
        Action method.
        """
        self.possible_router_idurl = None
        self.router_idurl = id_url.field(args[0])
        self.router_id = global_id.idurl2glob(self.router_idurl)
        self.router_identity = None
        self.router_proto_host = None
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver.doRememberNode %r' % self.router_idurl)

    def doSendRequestService(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_send_request_service(args[0])

    def doSendCancelService(self, *args, **kwargs):
        """
        Action method.
        """
        newpacket = signed.Packet(
            commands.CancelService(),
            my_id.getIDURL(),
            my_id.getIDURL(),
            packetid.UniqueID(),
            serialization.DictToBytes({
                'name': 'service_proxy_server',
            }),
            self.router_idurl,
        )
        packet_out.create(
            newpacket,
            wide=True,
            callbacks={},
            # callbacks={
            #     commands.Ack(): self._on_request_service_ack,
            #     commands.Fail(): self._on_request_service_fail,
            # },
            response_timeout=settings.P2PTimeOut(),
        )

    def doProcessInboxPacket(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_process_inbox_packet(args[0])

    def doStartListening(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            _, info, active_router_session_machine = args[0]
            self.router_proto_host = (info.proto, info.host)
        except:
            try:
                # TODO: move that setting to separate file
                s = config.conf().getString('services/proxy-transport/current-router').strip()
                _, router_proto, router_host = s.split(' ')
                self.router_proto_host = (router_proto, strng.to_bin(router_host))
            except:
                lg.exc()
        self.router_identity = identitycache.FromCache(self.router_idurl)
        if _Debug:
            lg.args(_DebugLevel, router_idurl=self.router_idurl)
        config.conf().setString('services/proxy-transport/current-router', '%s %s %s' % (
            strng.to_text(self.router_idurl),
            strng.to_text(self.router_proto_host[0]),
            strng.to_text(self.router_proto_host[1]),
        ))
        current_identity = my_id.getLocalIdentity().serialize(as_text=True)
        previous_identity = ReadMyOriginalIdentitySource()
        if previous_identity:
            lg.err('my original identity is not empty, SKIP overwriting')
            if _Debug:
                lg.out(_DebugLevel, 'PREVIOUS ORIGINAL IDENTITY:\n%s\n' % previous_identity)
        WriteMyOriginalIdentitySource(current_identity)
        lg.info('copy of my current identity was stored as my "original" identity')
        self.request_service_packet_id = []
        callback.insert_inbox_callback(0, self._on_inbox_packet_received)
        if online_status.isKnown(self.router_idurl):
            online_status.add_online_status_listener_callback(
                idurl=self.router_idurl,
                callback_method=self._on_router_contact_status_connected,
                newstate='CONNECTED',
            )
            online_status.add_online_status_listener_callback(
                idurl=self.router_idurl,
                callback_method=self._on_router_contact_status_offline,
                newstate='OFFLINE',
            )
        active_router_session_machine.addStateChangedCallback(self._on_router_session_disconnected, oldstate='CONNECTED')
        lg.info('router %s is connected at %s://%s' % (self.router_idurl, self.router_proto_host[0], self.router_proto_host[1]))
        my_id.rebuildLocalIdentity()

    def doStopListening(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, router_idurl=self.router_idurl)
        if online_status.isKnown(self.router_idurl):
            online_status.remove_online_status_listener_callback(
                idurl=self.router_idurl,
                callback_method=self._on_router_contact_status_connected,
            )
            online_status.remove_online_status_listener_callback(
                idurl=self.router_idurl,
                callback_method=self._on_router_contact_status_offline,
            )
        active_router_session_machine_index = None
        if self.router_connection_info:
            active_router_session_machine = None
            active_router_session_machine_index = self.router_connection_info.get('index', None)
            if active_router_session_machine_index is not None:
                active_router_session_machine = automat.by_index(active_router_session_machine_index)
            if not active_router_session_machine:
                active_router_sessions = gateway.find_active_session(
                    proto=self.router_connection_info.get('proto'),
                    host=self.router_connection_info.get('host'),
                )
                if not active_router_sessions:
                    active_router_sessions = gateway.find_active_session(
                        proto=self.router_connection_info.get('proto'),
                        idurl=id_url.to_bin(self.router_idurl),
                    )
                if active_router_sessions:
                    active_router_session_machine = automat.by_index(active_router_sessions[0].index)
            if active_router_session_machine is not None:
                active_router_session_machine.removeStateChangedCallback(self._on_router_session_disconnected)
                lg.info('removed callback from router active session: %r' % active_router_session_machine)
            else:
                lg.err('did not found active router session state machine with index %s' % active_router_session_machine_index)
        WriteMyOriginalIdentitySource('')
        config.conf().setString('services/proxy-transport/current-router', '')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        self.router_identity = None
        self.router_idurl = None
        self.router_id = ''
        self.router_proto_host = None
        self.request_service_packet_id = []
        self.router_connection_info = None
        my_id.rebuildLocalIdentity()

    def doUpdateRouterID(self, *args, **kwargs):
        """
        Action method.
        """
        newpacket, _ = args[0]
        newxml = newpacket.Payload
        newidentity = identity.identity(xmlsrc=newxml)
        cachedidentity = identitycache.FromCache(self.router_idurl)
        if self.router_idurl != newidentity.getIDURL():
            lg.warn('router idurl is unrecognized from response %r != %r' % (self.router_idurl, newidentity.getIDURL()))
            return
        if newidentity.serialize() != cachedidentity.serialize():
            lg.warn('cached identity is not same, router identity changed')
        self.router_identity = newidentity

    def doCheckPingRouter(self, *args, **kwargs):
        """
        Action method.
        """
        if self.router_connection_info:
            gateway.send_keep_alive(self.router_connection_info['proto'], self.router_connection_info['host'])
        live_time = time.time() - self.latest_packet_received
        if live_time < 60.0:
            if _Debug:
                lg.out(_DebugLevel, 'proxy_receiver.doCheckPingRouter OK, latest packet received %f sec ago' % live_time)
            return
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver.doCheckPingRouter to %s' % self.router_idurl)
        identity_source = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if identity_source:
            if _Debug:
                lg.out(_DebugLevel, '    "my-original-identity" prepared for sending')
        else:
            identity_source = my_id.getLocalIdentity().serialize()
            if _Debug:
                lg.out(_DebugLevel, '    local identity prepared for sending')
        self._do_send_identity_to_router(identity_source, failed_event='router-disconnected')

    def doNotifyConnected(self, *args, **kwargs):
        """
        Action method.
        """
        proxy_interface.interface_receiving_started(self.router_idurl, {
            'router_idurl': self.router_idurl,
        })

    def doNotifyDisconnected(self, *args, **kwargs):
        """
        Action method.
        """
        proxy_interface.interface_disconnected().addErrback(lambda _: None)

    def doNotifyFailed(self, *args, **kwargs):
        """
        Action method.
        """
        proxy_interface.interface_receiving_failed()

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _PacketLogFileEnabled
        global _ProxyReceiver
        _PacketLogFileEnabled = False
        callback.remove_queue_item_status_callback(self._on_queue_item_status_changed)
        self.possible_router_idurl = None
        self.router_idurl = None
        self.router_id = ''
        self.router_identity = None
        self.router_proto_host = None
        self.request_service_packet_id = []
        self.latest_packet_received = 0
        self.router_connection_info = None
        self.traffic_in = 0
        self.destroy()
        del _ProxyReceiver
        _ProxyReceiver = None

    def _do_process_inbox_packet(self, *args, **kwargs):
        newpacket, info, _, _ = args[0]
        block = encrypted.Unserialize(newpacket.Payload)
        if block is None:
            lg.err('reading data from %s' % newpacket.CreatorID)
            return
        try:
            session_key = key.DecryptLocalPrivateKey(block.EncryptedSessionKey)
            padded_data = key.DecryptWithSessionKey(session_key, block.EncryptedData, session_key_type=block.SessionKeyType)
            inpt = BytesIO(padded_data[:int(block.Length)])
            data = inpt.read()
        except:
            lg.err('reading data from %s' % newpacket.CreatorID)
            lg.exc()
            try:
                inpt.close()
            except:
                pass
            return
        inpt.close()

        if newpacket.Command == commands.RelayAck():
            try:
                ack_info = serialization.BytesToDict(data, keys_to_text=True, values_to_text=True)
            except:
                lg.exc()
                return
            if _Debug:
                lg.out(_DebugLevel, '<<<Relay-ACK %s:%s from %s://%s with %d bytes %s' % (ack_info['command'], ack_info['packet_id'], info.proto, info.host, len(data), ack_info['error']))
            if _PacketLogFileEnabled:
                lg.out(
                    0, '                \033[0;49;33mRELAY ACK %s(%s) with %d bytes from %s to %s TID:%s\033[0m' %
                    (ack_info['command'], ack_info['packet_id'], info.bytes_received, global_id.UrlToGlobalID(ack_info['from']), global_id.UrlToGlobalID(ack_info['to']), info.transfer_id), log_name='packet', showtime=True
                )
            from bitdust.transport.proxy import proxy_sender
            if proxy_sender.A():
                proxy_sender.A('relay-ack', ack_info, info)
            return True

        if newpacket.Command == commands.RelayFail():
            try:
                fail_info = serialization.BytesToDict(data, keys_to_text=True, values_to_text=True)
            except:
                lg.exc()
                return
            if _Debug:
                lg.out(_DebugLevel, '<<<Relay-FAIL %s:%s from %s://%s with %d bytes %s' % (fail_info['command'], fail_info['packet_id'], info.proto, info.host, len(data), fail_info['error']))
            if _PacketLogFileEnabled:
                lg.out(
                    0, '                \033[0;49;33mRELAY FAIL %s(%s) with %d bytes from %s to %s TID:%s\033[0m' %
                    (fail_info['command'], fail_info['packet_id'], info.bytes_received, global_id.UrlToGlobalID(fail_info['from']), global_id.UrlToGlobalID(fail_info['to']), info.transfer_id), log_name='packet', showtime=True
                )
            from bitdust.transport.proxy import proxy_sender
            if proxy_sender.A():
                proxy_sender.A('relay-failed', fail_info, info)
            return True

        routed_packet = signed.Unserialize(data)
        if not routed_packet:
            lg.err('unserialize packet failed from %s' % newpacket.CreatorID)
            return

        if _Debug:
            lg.out(_DebugLevel, '<<<Relay-IN %s from %s://%s with %d bytes' % (str(routed_packet), info.proto, info.host, len(data)))
        if _PacketLogFileEnabled:
            lg.out(
                0, '                \033[0;49;33mRELAY IN %s(%s) with %d bytes from %s to %s TID:%s\033[0m' %
                (routed_packet.Command, routed_packet.PacketID, info.bytes_received, global_id.UrlToGlobalID(info.sender_idurl), global_id.UrlToGlobalID(routed_packet.RemoteID), info.transfer_id), log_name='packet', showtime=True
            )

        if routed_packet.Command == commands.Identity():
            if _Debug:
                lg.out(_DebugLevel, '    found identity in relay packet %s' % routed_packet)
            newidentity = identity.identity(xmlsrc=routed_packet.Payload)
            idurl = newidentity.getIDURL()
            if not identitycache.HasKey(idurl):
                lg.info('received new identity %s rev %r' % (idurl.original(), newidentity.getRevisionValue()))
            if not identitycache.UpdateAfterChecking(idurl, routed_packet.Payload):
                lg.warn('ERROR has non-Valid identity')
                return

        if routed_packet.Command in [
            commands.Relay(),
            commands.RelayIn(),
        ] and routed_packet.PacketID.lower().startswith('identity:'):
            if _Debug:
                lg.out(_DebugLevel, '    found routed identity in relay packet %s' % routed_packet)
            try:
                routed_identity = signed.Unserialize(routed_packet.Payload)
                newidentity = identity.identity(xmlsrc=routed_identity.Payload)
                idurl = newidentity.getIDURL()
                if not identitycache.HasKey(idurl):
                    lg.warn('received new "routed" identity: %s' % idurl)
                if not identitycache.UpdateAfterChecking(idurl, routed_identity.Payload):
                    lg.warn('ERROR has non-Valid identity')
                    return
            except:
                lg.exc()

        if newpacket.Command == commands.RelayIn() and routed_packet.Command == commands.Fail():
            if routed_packet.Payload == b'route not exist' or routed_packet.Payload == b'route already closed':
                for pout in packet_out.search_by_packet_id(routed_packet.PacketID):
                    if _Debug:
                        lg.dbg(_DebugLevel, 'received %r from %r, outgoing packet is failed: %r' % (routed_packet.Payload, newpacket.CreatorID, pout))
                    pout.automat('request-failed')
                return

        self.traffic_in += len(data)
        packet_in.process(routed_packet, info)
        del block
        del data
        del padded_data
        del inpt
        del session_key
        del routed_packet

    def _do_send_identity_to_router(self, identity_source, failed_event):
        try:
            identity_obj = identity.identity(xmlsrc=identity_source)
        except:
            lg.exc()
            return
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._do_send_identity_to_router to %s' % self.router_idurl)
            lg.out(_DebugLevel, '        contacts=%r, sources=%r' % (identity_obj.contacts, identity_obj.getSources(as_originals=True)))
        newpacket = signed.Packet(
            Command=commands.Identity(),
            OwnerID=my_id.getIDURL(),
            CreatorID=my_id.getIDURL(),
            PacketID='proxy_receiver:%s' % packetid.UniqueID(),
            Payload=identity_obj.serialize(),
            RemoteID=self.router_idurl,
        )
        packet_out.create(
            newpacket,
            wide=True,
            callbacks={
                commands.Ack(): lambda response, info: self.automat('ack-received', (response, info)),
                commands.Fail(): lambda x: self.automat(failed_event),
                None: lambda pkt_out: self.automat('ack-timeout', pkt_out),
                'failed': lambda pkt_out, error_message: self.automat('sending-failed', (pkt_out, error_message)),
            },
            keep_alive=True,
            response_timeout=settings.P2PTimeOut(),
        )

    def _do_send_request_service(self, *args, **kwargs):
        if len(self.request_service_packet_id) >= 10:
            if _Debug:
                lg.warn('too many service requests to %r' % self.router_idurl)
            self.automat('service-refused', *args, **kwargs)
            return
        orig_identity = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if not orig_identity:
            orig_identity = my_id.getLocalIdentity().serialize(as_text=True)
        service_info = {
            'name': 'service_proxy_server',
            'payload': {
                'identity': orig_identity,
            },
        }
        newpacket = signed.Packet(
            commands.RequestService(),
            my_id.getIDURL(),
            my_id.getIDURL(),
            packetid.UniqueID(),
            serialization.DictToBytes(service_info, values_to_text=True),
            self.router_idurl,
        )
        packet_out.create(
            newpacket,
            wide=False,
            callbacks={
                commands.Ack(): self._on_request_service_ack,
                commands.Fail(): self._on_request_service_fail,
                # 'timeout': lambda pkt_out, err: self.automat('request-timeout', pkt_out),
                None: lambda pkt_out: self.automat('request-timeout', pkt_out),
            },
            response_timeout=settings.P2PTimeOut(),
        )
        self.request_service_packet_id.append(newpacket.PacketID)

    def _on_nodes_lookup_finished(self, idurls, attempts):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._on_nodes_lookup_finished : %r' % idurls)
        for idurl in idurls:
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if len(myprotos.intersection(remoteprotos)) > 0:
                self.possible_router_idurl = id_url.field(idurl)
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_receiver._on_nodes_lookup_finished found : %r' % self.possible_router_idurl)
                self.automat('found-one-node', self.possible_router_idurl)
                return
        if attempts > 0:
            self._find_random_node(attempts - 1)
        else:
            self.automat('nodes-not-found')

    def _find_random_node(self, attempts):
        preferred_routers = []
        preferred_routers_raw = config.conf().getString('services/proxy-transport/preferred-routers').strip()
        if preferred_routers_raw:
            preferred_routers_list = re.split('\n|,|;| ', preferred_routers_raw)
            preferred_routers.extend(preferred_routers_list)
        if preferred_routers:
            self.possible_router_idurl = id_url.field(random.choice(preferred_routers))
            if _Debug:
                lg.out(_DebugLevel, 'proxy_receiver._find_random_node selected random item from preferred_routers: %r' % self.possible_router_idurl)
            idcache_defer = identitycache.immediatelyCaching(self.possible_router_idurl)
            idcache_defer.addCallback(lambda *args: self.automat('found-one-node', self.possible_router_idurl))
            idcache_defer.addErrback(lambda err: self.automat('nodes-not-found') and None)
            return
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._find_random_node will start DHT lookup')
        tsk = lookup.random_proxy_router()
        if tsk:
            tsk.result_defer.addCallback(self._on_nodes_lookup_finished, attempts=attempts)
            tsk.result_defer.addErrback(lambda err: self.automat('nodes-not-found'))
        else:
            self.automat('nodes-not-found')

    def _on_request_service_ack(self, response, info):
        self.router_connection_info = None
        if response.PacketID not in self.request_service_packet_id:
            lg.warn('wrong PacketID in response: %s, but outgoing was : %s' % (response.PacketID, str(self.request_service_packet_id)))
            self.automat('service-refused', (response, info))
            return
        if response.PacketID in self.request_service_packet_id:
            self.request_service_packet_id.remove(response.PacketID)
        else:
            lg.warn('%s was not found in pending requests: %s' % (response.PacketID, self.request_service_packet_id))
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._on_request_service_ack : %s' % str(response.Payload))
        if self.router_idurl != response.CreatorID:
            lg.err('received unexpected response from another node: %r ~ %r' % (self.router_idurl, response.CreatorID))
            self.automat('service-refused', (response, info))
            return
        service_ack_info = strng.to_text(response.Payload)
        if service_ack_info.startswith('rejected'):
            self.automat('service-refused', (response, info))
            return
        active_router_sessions = gateway.find_active_session(info.proto, host=info.host)
        if not active_router_sessions:
            active_router_sessions = gateway.find_active_session(info.proto, idurl=id_url.to_bin(response.CreatorID))
        if not active_router_sessions:
            lg.err('active connection with proxy router at %s:%s was not found' % (info.proto, info.host))
            if _Debug:
                lg.args(_DebugLevel, router_idurl=self.router_idurl, ack_packet=info, active_sessions=gateway.list_active_sessions(info.proto))
            self.automat('service-refused', (response, info))
            return
        self.router_connection_info = {
            'id': active_router_sessions[0].id,
            'index': active_router_sessions[0].index,
            'repr': repr(active_router_sessions[0]),
            'proto': info.proto,
            'host': info.host,
            'idurl': self.router_idurl,
            'global_id': global_id.UrlToGlobalID(self.router_idurl),
        }
        active_router_session_machine = automat.by_index(self.router_connection_info['index'])
        if active_router_session_machine is None:
            lg.err('did not found proxy router session state machine instance: %s' % self.router_connection_info)
            self.router_connection_info = None
            if _Debug:
                lg.args(_DebugLevel, automats=automat.objects())
            self.automat('service-refused', (response, info))
            return
        lg.info('found active session for proxy router: %s' % active_router_session_machine)
        self.automat('service-accepted', (response, info, active_router_session_machine))

    def _on_request_service_fail(self, response, info):
        if response.PacketID not in self.request_service_packet_id:
            lg.warn('wrong PacketID in response: %s, but outgoing was : %s' % (response.PacketID, str(self.request_service_packet_id)))
        else:
            self.request_service_packet_id.remove(response.PacketID)
        self.automat('service-refused', (response, info))

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        if newpacket.Command == commands.Identity() and \
                newpacket.CreatorID == self.router_idurl and \
                newpacket.RemoteID == my_id.getIDURL():
            self.automat('router-id-received', (newpacket, info))
            self.latest_packet_received = time.time()
            return True
        if newpacket.CreatorID == self.router_idurl:
            self.latest_packet_received = time.time()
        if newpacket.Command in [
            commands.Relay(),
            commands.RelayIn(),
            commands.RelayAck(),
            commands.RelayFail(),
        ]:
            if driver.is_enabled('service_proxy_server'):
                # TODO:
                # in case this node already running proxy router service this will not work
                # actually you can not use proxy transport for receiving and running proxy router at same time
                # need to change one of the services to solve that dependency and prevent this
                return False
            self.automat('inbox-packet', (newpacket, info, status, error_message))
            return True
        return False

    def _on_router_contact_status_connected(self, oldstate, newstate, event_string, *args, **kwargs):
        lg.info('router %r contact status online: %s->%s after "%s"' % (self.router_idurl, oldstate, newstate, event_string))

    def _on_router_contact_status_offline(self, oldstate, newstate, event_string, *args, **kwargs):
        lg.warn('router %r contact status offline: %s->%s after "%s"' % (self.router_idurl, oldstate, newstate, event_string))
        # self.automat('router-disconnected')

    def _on_router_session_disconnected(self, oldstate, newstate, event_string, *args, **kwargs):
        lg.err('router session disconnected: %s->%s because of %r' % (oldstate, newstate, event_string))
        self.automat('router-disconnected')

    def _on_queue_item_status_changed(self, pkt_out, status, error=''):
        from bitdust.transport.proxy import proxy_receiver
        if status == 'finished':
            return False
        if error != 'connection failed':
            return False
        if not pkt_out.remote_idurl or not pkt_out.outpacket:
            return False
        if id_url.to_bin(pkt_out.remote_idurl) == pkt_out.outpacket.RemoteID.to_bin():
            return False
        if not proxy_receiver.GetRouterIDURL():
            return False
        if pkt_out.remote_idurl != proxy_receiver.GetRouterIDURL():
            return False
        lg.err('connection failed with current proxy router, must reconnect to another router: %r %r %r' % (pkt_out, status, error))
        self.automat('router-disconnected')
        return True


#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor  # @UnresolvedImport
    reactor.callWhenRunning(A, 'init')  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable


if __name__ == '__main__':
    main()
