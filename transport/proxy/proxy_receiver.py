#!/usr/bin/env python
# proxy_receiver.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
    * :red:`fail-received`
    * :red:`found-one-node`
    * :red:`inbox-packet`
    * :red:`init`
    * :red:`nodes-not-found`
    * :red:`router-disconnected`
    * :red:`router-id-received`
    * :red:`service-accepted`
    * :red:`service-refused`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-10sec`
    * :red:`timer-1sec`
    * :red:`timer-20sec`
    * :red:`timer-4sec`
    * :red:`timer-5sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import BytesIO

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import re
import time
import random

#------------------------------------------------------------------------------

from logs import lg

from lib import packetid
from lib import strng
from lib import serialization

from automats import automat

from main import config
from main import settings

from crypt import key
from crypt import signed
from crypt import encrypted

from p2p import commands
from p2p import lookup
from p2p import online_status
from p2p import propagate

from contacts import identitycache

from transport import callback
from transport import packet_in
from transport import packet_out

from transport import gateway
from transport.proxy import proxy_interface

from userid import my_id
from userid import identity
from userid import global_id

#------------------------------------------------------------------------------

_ProxyReceiver = None

#------------------------------------------------------------------------------


def GetRouterIDURL():
    global _ProxyReceiver
    if not _ProxyReceiver:
        return None
    return _ProxyReceiver.router_idurl


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
        lg.warn('current router is set, but my original identity is empty')
        return False
    if not ReadCurrentRouter() and ReadMyOriginalIdentitySource():
        lg.warn('current router is not set, but some wrong data found as original identity')
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
        _ProxyReceiver = ProxyReceiver(
            name='proxy_receiver',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=(_Debug and _DebugLevel>12),
            log_transitions=_Debug,
        )
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
        'timer-1sec': (1.0, ['ACK?']),
        'timer-5sec': (5.0, ['SERVICE?']),
        'timer-10sec': (10.0, ['LISTEN']),
        'timer-20sec': (20.0, ['FIND_NODE?']),
        'timer-4sec': (4.0, ['ACK?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of proxy_receiver() machine.
        """
        self.router_idurl = None
        self.router_identity = None
        self.router_proto_host = None
        self.request_service_packet_id = []
        self.latest_packet_received = 0
        self.router_connection_info = None
        self.traffic_in = 0

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when proxy_receiver() state were changed.
        """
        if settings.enablePROXYsending():
            from transport.proxy import proxy_sender
            proxy_sender.A('proxy_receiver.state', newstate)

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in
        the proxy_receiver() but its state was not changed.
        """

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
            elif event == 'timer-1sec':
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'timer-4sec' or event == 'fail-received':
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
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop' or event == 'nodes-not-found' or event == 'timer-20sec':
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
            elif event == 'timer-5sec' or event == 'service-refused':
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(*args, **kwargs)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'start' and self.isCurrentRouterExist(*args, **kwargs):
                self.state = 'ACK?'
                self.doLoadRouterInfo(*args, **kwargs)
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
        if not ReadMyOriginalIdentitySource():
            return False
        return config.conf().getString('services/proxy-transport/current-router', '').strip() != ''

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doLoadRouterInfo(self, *args, **kwargs):
        """
        Action method.
        """
        s = config.conf().getString('services/proxy-transport/current-router').strip()
        try:
            self.router_idurl = strng.to_bin(s.split(' ')[0])
        except:
            lg.exc()
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver.doLoadRouterInfo : %s' % self.router_idurl)

    def doLookupRandomNode(self, *args, **kwargs):
        """
        Action method.
        """
        self._find_random_node()

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_send_identity_to_router(my_id.getLocalIdentity().serialize(), failed_event='fail-received')
        identity_source = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if identity_source:
            if _Debug:
                lg.out(_DebugLevel, '    also sending identity loaded from "my-original-identity" config')
            self._do_send_identity_to_router(identity_source, failed_event='fail-received')

    def doRememberNode(self, *args, **kwargs):
        """
        Action method.
        """
        self.router_idurl = strng.to_bin(args[0])
        self.router_identity = None
        self.router_proto_host = None
        self.request_service_packet_id = []
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
            my_id.getLocalID(),
            my_id.getLocalID(),
            packetid.UniqueID(),
            serialization.DictToBytes({'name': 'service_proxy_server', }),
            self.router_idurl,
        )
        packet_out.create(newpacket, wide=True, callbacks={
            commands.Ack(): self._on_request_service_ack,
            commands.Fail(): self._on_request_service_fail,
        },)

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
            _, info = args[0]
            self.router_proto_host = (info.proto, info.host)
        except:
            try:
                s = config.conf().getString('services/proxy-transport/current-router').strip()
                _, router_proto, router_host = s.split(' ')
                self.router_proto_host = (router_proto, strng.to_bin(router_host), )
            except:
                lg.exc()
        self.router_identity = identitycache.FromCache(self.router_idurl)
        config.conf().setString('services/proxy-transport/current-router', '%s %s %s' % (
            strng.to_text(self.router_idurl),
            strng.to_text(self.router_proto_host[0]),
            strng.to_text(self.router_proto_host[1]),
        ))
        current_identity = my_id.getLocalIdentity().serialize(as_text=True)
        previous_identity = ReadMyOriginalIdentitySource()
        if previous_identity:
            lg.warn('my original identity is not empty, SKIP overwriting')
            lg.out(2, '\nPREVIOUS ORIGINAL IDENTITY:\n%s\n' % current_identity)
        else:
            WriteMyOriginalIdentitySource(current_identity)
            lg.warn('current identity was stored as my-original-identity')
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
            # contact_status.A(self.router_idurl).addStateChangedCallback(
            #     self._on_router_contact_status_connected, newstate='CONNECTED')
            # contact_status.A(self.router_idurl).addStateChangedCallback(
            #     self._on_router_contact_status_offline, newstate='OFFLINE')
        active_router_sessions = gateway.find_active_session(info.proto, info.host)
        if active_router_sessions:
            self.router_connection_info = {
                'id': active_router_sessions[0].id,
                'index': active_router_sessions[0].index,
                'proto': info.proto,
                'host': info.host,
                'idurl': self.router_idurl,
                'global_id': global_id.UrlToGlobalID(self.router_idurl),
            }
            active_router_session_machine = automat.objects().get(self.router_connection_info['index'], None)
            if active_router_session_machine:
                active_router_session_machine.addStateChangedCallback(
                    self._on_router_session_disconnected, oldstate='CONNECTED')
                lg.info('connected to proxy router and set active session: %s' % self.router_connection_info)
            else:
                lg.err('not found proxy router session state machine: %s' % self.router_connection_info['index'])
        else:
            lg.err('active connection with proxy router at %s:%s was not found' % (info.proto, info.host, ))
        if _Debug:
            lg.out(2, 'proxy_receiver.doStartListening !!!!!!! router: %s at %s://%s' % (
                self.router_idurl, self.router_proto_host[0], self.router_proto_host[1]))

    def doStopListening(self, *args, **kwargs):
        """
        Action method.
        """
        if online_status.isKnown(self.router_idurl):
            online_status.remove_online_status_listener_callbackove_(
                idurl=self.router_idurl,
                callback_method=self._on_router_contact_status_connected,
            )
            online_status.remove_online_status_listener_callbackove_(
                idurl=self.router_idurl,
                callback_method=self._on_router_contact_status_offline,
            )
        # if contact_status.isKnown(self.router_idurl):
        #     contact_status.A(self.router_idurl).removeStateChangedCallback(self._on_router_contact_status_connected)
        #     contact_status.A(self.router_idurl).removeStateChangedCallback(self._on_router_contact_status_offline)
        WriteMyOriginalIdentitySource('')
        config.conf().setString('services/proxy-transport/current-router', '')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        self.router_identity = None
        self.router_idurl = None
        self.router_proto_host = None
        self.request_service_packet_id = []
        self.router_connection_info = None
        my_id.rebuildLocalIdentity()
        if _Debug:
            lg.out(2, 'proxy_receiver.doStopListening')

    def doUpdateRouterID(self, *args, **kwargs):
        """
        Action method.
        """
        newpacket, _ = args[0]
        newxml = newpacket.Payload
        newidentity = identity.identity(xmlsrc=newxml)
        cachedidentity = identitycache.FromCache(self.router_idurl)
        if self.router_idurl != newidentity.getIDURL():
            lg.warn('router_idurl != newidentity.getIDURL()')
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
        proxy_interface.interface_receiving_started(
            self.router_idurl, {'router_idurl': self.router_idurl, },)

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
        self.unregister()
        global _ProxyReceiver
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
            padded_data = key.DecryptWithSessionKey(session_key, block.EncryptedData)
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
        routed_packet = signed.Unserialize(data)
        if not routed_packet:
            lg.err('unserialize packet failed from %s' % newpacket.CreatorID)
            return
        if _Debug:
            lg.out(_DebugLevel, '<<<Relay-IN %s from %s://%s with %d bytes' % (
                str(routed_packet), info.proto, info.host, len(data)))
        if routed_packet.Command == commands.Identity():
            if _Debug:
                lg.out(_DebugLevel, '    found identity in relay packet %s' % routed_packet)
            newidentity = identity.identity(xmlsrc=routed_packet.Payload)
            idurl = newidentity.getIDURL()
            if not identitycache.HasKey(idurl):
                lg.info('received new identity: %s' % idurl)
            if not identitycache.UpdateAfterChecking(idurl, routed_packet.Payload):
                lg.warn("ERROR has non-Valid identity")
                return
        if routed_packet.Command == commands.Relay() and routed_packet.PacketID.lower() == 'identity':
            if _Debug:
                lg.out(_DebugLevel, '    found routed identity in relay packet %s' % routed_packet)
            try:
                routed_identity = signed.Unserialize(routed_packet.Payload)
                newidentity = identity.identity(xmlsrc=routed_identity.Payload)
                idurl = newidentity.getIDURL()
                if not identitycache.HasKey(idurl):
                    lg.warn('received new "routed" identity: %s' % idurl)
                if not identitycache.UpdateAfterChecking(idurl, routed_identity.Payload):
                    lg.warn("ERROR has non-Valid identity")
                    return
            except:
                lg.exc()
#         if not routed_packet.Valid():
#             lg.err('invalid packet %s from %s' % (
#                 routed_packet, newpacket.CreatorID, ))
#             return
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
            lg.out(_DebugLevel, 'proxy_receiver.doSendMyIdentity to %s' % self.router_idurl)
            lg.out(_DebugLevel, '        contacts=%s, sources=%s' % (identity_obj.contacts, identity_obj.sources))
        newpacket = signed.Packet(
            commands.Identity(),
            my_id.getLocalID(),
            my_id.getLocalID(),
            commands.Identity(),
            identity_obj.serialize(),
            self.router_idurl,
        )
        packet_out.create(
            newpacket,
            wide=True,
            callbacks={
                commands.Ack(): lambda response, info: self.automat('ack-received', (response, info)),
                commands.Fail(): lambda x: self.automat(failed_event),
            },
            keep_alive=True,
        )

    def _do_send_request_service(self, *args, **kwargs):
        if len(self.request_service_packet_id) >= 3:
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
            my_id.getLocalID(),
            my_id.getLocalID(),
            packetid.UniqueID(),
            serialization.DictToBytes(service_info, values_to_text=True),
            self.router_idurl,
        )
        packet_out.create(newpacket, wide=False, callbacks={
            commands.Ack(): self._on_request_service_ack,
            commands.Fail(): self._on_request_service_fail,
        },)
        self.request_service_packet_id.append(newpacket.PacketID)

    def _on_nodes_lookup_finished(self, idurls):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._on_nodes_lookup_finished : %r' % idurls)
#         excluded_idurls = []
#         if driver.is_on('service_customer'):
#             excluded_idurls.extend(contactsdb.suppliers())
        for idurl in idurls:
#             if idurl in excluded_idurls:
#                 continue
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if len(myprotos.intersection(remoteprotos)) > 0:
                self.automat('found-one-node', idurl)
                return
        self.automat('nodes-not-found')

    def _find_random_node(self):
        # DEBUG
        # self.automat('found-one-node', 'http://p2p-id.ru/seed0_cb67.xml')
        # self.automat('found-one-node', 'https://bitdust.io:8084/seed2_b17a.xml')
        # self.automat('found-one-node', 'http://datahaven.net/seed2_916e.xml')
        # self.automat('found-one-node', 'http://bitdust.ai/seed1_c2c2.xml')
        # return
        preferred_routers = []
        preferred_routers_raw = config.conf().getData('services/proxy-transport/preferred-routers').strip()
        if preferred_routers_raw:
            preferred_routers_list = re.split('\n|,|;| ', preferred_routers_raw)
            preferred_routers.extend(preferred_routers_list)
        if preferred_routers:
            known_router = random.choice(preferred_routers)
            if _Debug:
                lg.out(_DebugLevel, 'proxy_receiver._find_random_node selected random item from preferred_routers: %s' % known_router)
            d = propagate.PingContact(known_router, timeout=5)
            d.addCallback(lambda resp_tuple: self.automat('found-one-node', known_router))
            d.addErrback(lambda err: self.automat('nodes-not-found'))
            # d.addErrback(lg.errback)
            # self.automat('found-one-node', known_router)
            return
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._find_random_node will start DHT lookup')
        tsk = lookup.start()
        if tsk:
            tsk.result_defer.addCallback(self._on_nodes_lookup_finished)
            tsk.result_defer.addErrback(lambda err: self.automat('nodes-not-found'))
        else:
            self.automat('nodes-not-found')

    def _on_request_service_ack(self, response, info):
        if response.PacketID not in self.request_service_packet_id:
            lg.warn('wong PacketID in response: %s, but outgoing was : %s' % (
                response.PacketID, str(self.request_service_packet_id)))
            self.automat('service-refused', (response, info))
            return
        if response.PacketID in self.request_service_packet_id:
            self.request_service_packet_id.remove(response.PacketID)
        else:
            lg.warn('%s was not found in pending requests: %s' % (response.PacketID, self.request_service_packet_id))
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._on_request_service_ack : %s' % str(response.Payload))
        service_ack_info = strng.to_text(response.Payload)
        if not service_ack_info.startswith('rejected'):
            self.automat('service-accepted', (response, info))
        else:
            self.automat('service-refused', (response, info))

    def _on_request_service_fail(self, response, info):
        if response.PacketID not in self.request_service_packet_id:
            lg.warn('wong PacketID in response: %s, but outgoing was : %s' % (
                response.PacketID, str(self.request_service_packet_id)))
        else:
            self.request_service_packet_id.remove(response.PacketID)
        self.automat('service-refused', (response, info))

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        if newpacket.Command == commands.Identity() and \
                newpacket.CreatorID == self.router_idurl and \
                newpacket.RemoteID == my_id.getLocalID():
            self.automat('router-id-received', (newpacket, info))
            self.latest_packet_received = time.time()
            return True
        if newpacket.CreatorID == self.router_idurl:
            self.latest_packet_received = time.time()
        if newpacket.Command == commands.Relay():
            self.automat('inbox-packet', (newpacket, info, status, error_message))
            return True
        return False

    def _on_router_contact_status_connected(self, oldstate, newstate, event_string, *args, **kwargs):
        lg.info('router %r contact status online: %s->%s after "%s"' % (self.router_idurl, oldstate, newstate, event_string, ))

    def _on_router_contact_status_offline(self, oldstate, newstate, event_string, *args, **kwargs):
        lg.warn('router %r contact status offline: %s->%s after "%s"' % (self.router_idurl, oldstate, newstate, event_string, ))
        # self.automat('router-disconnected')

    def _on_router_session_disconnected(self, oldstate, newstate, event_string, *args, **kwargs):
        lg.warn('router session disconnected: %s->%s' % (oldstate, newstate, ))
        self.automat('router-disconnected')

#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor  # @UnresolvedImport
    reactor.callWhenRunning(A, 'init')  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable


if __name__ == "__main__":
    main()
