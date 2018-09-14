#!/usr/bin/env python
# proxy_receiver.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import json
import time
import random
import cStringIO

#------------------------------------------------------------------------------

from logs import lg

from lib import packetid

from automats import automat

from main import config
from main import settings

from crypt import key
from crypt import signed
from crypt import encrypted

from p2p import commands
from p2p import lookup
from p2p import contact_status
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


def A(event=None, arg=None):
    """
    Access method to interact with proxy_receiver machine.
    """
    global _ProxyReceiver
    if event is None and arg is None:
        return _ProxyReceiver
    if _ProxyReceiver is None:
        # set automat name and starting state here
        _ProxyReceiver = ProxyReceiver('proxy_receiver', 'AT_STARTUP',
                                       debug_level=_DebugLevel,
                                       log_events=(_Debug and _DebugLevel>12),
                                       log_transitions=_Debug, )
    if event is not None:
        _ProxyReceiver.automat(event, arg)
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

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when proxy_receiver() state were changed.
        """
        if settings.enablePROXYsending():
            from transport.proxy import proxy_sender
            proxy_sender.A('proxy_receiver.state', newstate)

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in
        the proxy_receiver() but its state was not changed.
        """

    def A(self, event, arg):
        """
        The core proxy_receiver() code, generated using `visio2python
        <https://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'ack-received':
                self.state = 'SERVICE?'
                self.doSendRequestService(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'OFFLINE'
                self.doNotifyFailed(arg)
            elif event == 'timer-1sec':
                self.doSendMyIdentity(arg)
            elif event == 'timer-4sec' or event == 'fail-received':
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(arg)
        #---LISTEN---
        elif self.state == 'LISTEN':
            if event == 'router-id-received':
                self.doUpdateRouterID(arg)
            elif event == 'inbox-packet':
                self.doProcessInboxPacket(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopListening(arg)
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'OFFLINE'
                self.doSendCancelService(arg)
                self.doStopListening(arg)
                self.doNotifyDisconnected(arg)
            elif event == 'timer-10sec':
                self.doCheckPingRouter(arg)
            elif event == 'service-refused' or event == 'router-disconnected':
                self.state = 'FIND_NODE?'
                self.doStopListening(arg)
                self.doNotifyDisconnected(arg)
                self.doLookupRandomNode(arg)
        #---FIND_NODE?---
        elif self.state == 'FIND_NODE?':
            if event == 'found-one-node':
                self.state = 'ACK?'
                self.doRememberNode(arg)
                self.doSendMyIdentity(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop' or event == 'nodes-not-found' or event == 'timer-20sec':
                self.state = 'OFFLINE'
                self.doNotifyFailed(arg)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'service-accepted':
                self.state = 'LISTEN'
                self.doStartListening(arg)
                self.doNotifyConnected(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'OFFLINE'
                self.doSendCancelService(arg)
                self.doNotifyFailed(arg)
            elif event == 'timer-5sec' or event == 'service-refused':
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(arg)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'start' and self.isCurrentRouterExist(arg):
                self.state = 'ACK?'
                self.doLoadRouterInfo(arg)
                self.doSendMyIdentity(arg)
            elif event == 'start' and not self.isCurrentRouterExist(arg):
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        return None

    def isCurrentRouterExist(self, arg):
        """
        Condition method.
        """
        if not ReadMyOriginalIdentitySource():
            return False
        return config.conf().getString('services/proxy-transport/current-router', '').strip() != ''

    def doInit(self, arg):
        """
        Action method.
        """

    def doLoadRouterInfo(self, arg):
        """
        Action method.
        """
        s = config.conf().getString('services/proxy-transport/current-router').strip()
        try:
            self.router_idurl, _, _ = s.split(' ')
        except:
            lg.exc()
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver.doLoadRouterInfo : %s' % self.router_idurl)

    def doLookupRandomNode(self, arg):
        """
        Action method.
        """
        self._find_random_node()

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver.doSendMyIdentity to %s' % self.router_idurl)
        self._do_send_identity_to_router(my_id.getLocalIdentity().serialize(), failed_event='fail-received')
        identity_source = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if identity_source:
            if _Debug:
                lg.out(_DebugLevel, '    also sending identity loaded from "my-original-identity" config')
            self._do_send_identity_to_router(identity_source, failed_event='fail-received')

    def doRememberNode(self, arg):
        """
        Action method.
        """
        self.router_idurl = arg
        self.router_identity = None
        self.router_proto_host = None
        self.request_service_packet_id = []
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver.doRememberNode %s' % self.router_idurl)

    def doSendRequestService(self, arg):
        """
        Action method.
        """
        if len(self.request_service_packet_id) >= 3:
            if _Debug:
                lg.warn('too many service requests to %s' % self.router_idurl)
            self.automat('service-refused', arg)
            return
        orig_identity = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if not orig_identity:
            orig_identity = my_id.getLocalIdentity().serialize()
        service_info = {
            'name': 'service_proxy_server',
            'payload': {
                'identity': orig_identity,
            },
        }
        service_info_raw = json.dumps(service_info)
        newpacket = signed.Packet(
            commands.RequestService(),
            my_id.getLocalID(),
            my_id.getLocalID(),
            packetid.UniqueID(),
            service_info_raw,
            self.router_idurl,)
        packet_out.create(newpacket, wide=False, callbacks={
            commands.Ack(): self._on_request_service_ack,
            commands.Fail(): self._on_request_service_fail,
        },)
        self.request_service_packet_id.append(newpacket.PacketID)

    def doSendCancelService(self, arg):
        """
        Action method.
        """
        service_info = {
            'name': 'service_proxy_server',
        }
        service_info_raw = json.dumps(service_info)
        newpacket = signed.Packet(
            commands.CancelService(),
            my_id.getLocalID(),
            my_id.getLocalID(),
            packetid.UniqueID(),
            service_info_raw,
            self.router_idurl, )
        packet_out.create(newpacket, wide=True, callbacks={
            commands.Ack(): self._on_request_service_ack,
            commands.Fail(): self._on_request_service_fail,
        },)

    def doProcessInboxPacket(self, arg):
        """
        Action method.
        """
        newpacket, info, _, _ = arg
        block = encrypted.Unserialize(newpacket.Payload)
        if block is None:
            lg.out(2, 'proxy_receiver.doProcessInboxPacket ERROR reading data from %s' % newpacket.CreatorID)
            return
        try:
            session_key = key.DecryptLocalPrivateKey(block.EncryptedSessionKey)
            padded_data = key.DecryptWithSessionKey(session_key, block.EncryptedData)
            inpt = cStringIO.StringIO(padded_data[:int(block.Length)])
            data = inpt.read()
        except:
            lg.out(2, 'proxy_receiver.doProcessInboxPacket ERROR reading data from %s' % newpacket.CreatorID)
            lg.exc()
            try:
                inpt.close()
            except:
                pass
            return
        inpt.close()
        routed_packet = signed.Unserialize(data)
        if not routed_packet:
            lg.out(2, 'proxy_receiver.doProcessInboxPacket ERROR unserialize packet failed from %s' % newpacket.CreatorID)
            return
        if routed_packet.Command == commands.Identity():
            newidentity = identity.identity(xmlsrc=routed_packet.Payload)
            idurl = newidentity.getIDURL()
            if not identitycache.HasKey(idurl):
                lg.warn('received new identity: %s' % idurl)
            if not identitycache.UpdateAfterChecking(idurl, routed_packet.Payload):
                lg.warn("ERROR has non-Valid identity")
                return
        if not routed_packet.Valid():
            lg.out(2, 'proxy_receiver.doProcessInboxPacket ERROR invalid packet from %s' % newpacket.CreatorID)
            return
        self.traffic_in += len(data)
        if _Debug:
            lg.out(_DebugLevel, '<<<Relay-IN %s from %s://%s with %d bytes' % (
                str(routed_packet), info.proto, info.host, len(data)))
        packet_in.process(routed_packet, info)
        del block
        del data
        del padded_data
        del inpt
        del session_key
        del routed_packet

    def doStartListening(self, arg):
        """
        Action method.
        """
        try:
            _, info = arg
            self.router_proto_host = (info.proto, info.host)
        except:
            try:
                s = config.conf().getString('services/proxy-transport/current-router').strip()
                _, router_proto, router_host = s.split(' ')
                self.router_proto_host = (router_proto, router_host)
            except:
                lg.exc()
        self.router_identity = identitycache.FromCache(self.router_idurl)
        config.conf().setString('services/proxy-transport/current-router', '%s %s %s' % (
            self.router_idurl, self.router_proto_host[0], self.router_proto_host[1]))
        current_identity = my_id.getLocalIdentity().serialize()
        previous_identity = ReadMyOriginalIdentitySource()
        if previous_identity:
            lg.warn('my original identity is not empty, SKIP overwriting')
            lg.out(2, '\nPREVIOUS ORIGINAL IDENTITY:\n%s\n' % current_identity)
        else:
            WriteMyOriginalIdentitySource(current_identity)
            lg.warn('current identity was stored as my-original-identity')
        self.request_service_packet_id = []
        callback.insert_inbox_callback(0, self._on_inbox_packet_received)
        if contact_status.isKnown(self.router_idurl):
            contact_status.A(self.router_idurl).addStateChangedCallback(
                self._on_router_contact_status_connected, newstate='CONNECTED')
            contact_status.A(self.router_idurl).addStateChangedCallback(
                self._on_router_contact_status_offline, newstate='OFFLINE')
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

    def doStopListening(self, arg):
        """
        Action method.
        """
        if contact_status.isKnown(self.router_idurl):
            contact_status.A(self.router_idurl).removeStateChangedCallback(self._on_router_contact_status_connected)
            contact_status.A(self.router_idurl).removeStateChangedCallback(self._on_router_contact_status_offline)
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

    def doUpdateRouterID(self, arg):
        """
        Action method.
        """
        newpacket, _ = arg
        newxml = newpacket.Payload
        newidentity = identity.identity(xmlsrc=newxml)
        cachedidentity = identitycache.FromCache(self.router_idurl)
        if self.router_idurl != newidentity.getIDURL():
            lg.warn('router_idurl != newidentity.getIDURL()')
            return
        if newidentity.serialize() != cachedidentity.serialize():
            lg.warn('cached identity is not same, router identity changed')
        self.router_identity = newidentity

    def doCheckPingRouter(self, arg):
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

    def doNotifyConnected(self, arg):
        """
        Action method.
        """
        proxy_interface.interface_receiving_started(self.router_idurl,
                                                    {'router_idurl': self.router_idurl, })

    def doNotifyDisconnected(self, arg):
        """
        Action method.
        """
        proxy_interface.interface_disconnected().addErrback(lambda _: None)

    def doNotifyFailed(self, arg):
        """
        Action method.
        """
        proxy_interface.interface_receiving_failed()

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()
        global _ProxyReceiver
        del _ProxyReceiver
        _ProxyReceiver = None

    def _do_send_identity_to_router(self, identity_source, failed_event):
        try:
            identity_obj = identity.identity(xmlsrc=identity_source)
        except:
            lg.exc()
            return
        if _Debug:
            lg.out(_DebugLevel, '        contacts=%s, sources=%s' % (identity_obj.contacts, identity_obj.sources))
        newpacket = signed.Packet(
            commands.Identity(),
            my_id.getLocalID(),
            my_id.getLocalID(),
            'identity',
            identity_source,
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

    def _on_nodes_lookup_finished(self, idurls):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._on_nodes_lookup_finished : %r' % idurls)
        for idurl in idurls:
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
        # return
        preferred_routers_raw = config.conf().getData('services/proxy-transport/preferred-routers').strip()
        preferred_routers = []
        if preferred_routers_raw:
            preferred_routers.extend(preferred_routers_raw.split('\n'))
        if preferred_routers:
            known_router = random.choice(preferred_routers)
            if _Debug:
                lg.out(_DebugLevel, 'proxy_receiver._find_random_node selected random item from preferred_routers: %s' % known_router)
            d = propagate.PingContact(known_router, timeout=5)
            d.addCallback(lambda resp_tuple: self.automat('found-one-node', known_router))
            d.addErrback(lg.errback)
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

#         if _Debug:
#             lg.out(_DebugLevel, 'proxy_receiver._find_random_node')
#         # DEBUG
#         self._got_remote_idurl({'idurl': 'http://veselin-p2p.ru/bitdust_j_vps1001.xml'})
#         return
#         new_key = dht_service.random_key()
#         d = dht_service.find_node(new_key)
#         d.addCallback(self._some_nodes_found)
#         d.addErrback(lambda x: self.automat('nodes-not-found'))
#         return d
#
#     def _some_nodes_found(self, nodes):
#         if _Debug:
#             lg.out(_DebugLevel, 'proxy_receiver._some_nodes_found : %d' % len(nodes))
#         if len(nodes) > 0:
#             node = random.choice(nodes)
#             d = node.request('idurl')
#             d.addCallback(self._got_remote_idurl)
#             d.addErrback(lambda x: self.automat('nodes-not-found'))
#         else:
#             self.automat('nodes-not-found')
#         return nodes
#
#     def _got_remote_idurl(self, response):
#         if _Debug:
#             lg.out(_DebugLevel, 'proxy_receiver._got_remote_idurl response=%s' % str(response) )
#         try:
#             idurl = response['idurl']
#         except:
#             idurl = None
#         if not idurl or idurl == 'None':
#             self.automat('nodes-not-found')
#             return response
#         d = identitycache.immediatelyCaching(idurl)
#         d.addCallback(lambda src: self.automat('found-one-node', idurl))
#         d.addErrback(lambda x: self.automat('nodes-not-found'))
#         return response

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
        if not response.Payload.startswith('rejected'):
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
        # TODO: if this is a response from supplier - this must be skipped here
        # if newpacket.Command == commands.Fail() and \
        #         newpacket.CreatorID == self.router_idurl and \
        #         newpacket.RemoteID == my_id.getLocalID():
        #     self.automat('service-refused', (newpacket, info))
        #     return True
        if newpacket.CreatorID == self.router_idurl:
            self.latest_packet_received = time.time()
        if newpacket.Command == commands.Relay():
            self.automat('inbox-packet', (newpacket, info, status, error_message))
            return True
        return False

    def _on_router_contact_status_connected(self, oldstate, newstate, event_string, args):
        pass

    def _on_router_contact_status_offline(self, oldstate, newstate, event_string, args):
        lg.warn('router contact status offline: %s->%s after "%s"' % (oldstate, newstate, event_string, ))
        # self.automat('router-disconnected')

    def _on_router_session_disconnected(self, oldstate, newstate, event_string, args):
        lg.warn('router session disconnected: %s->%s' % (oldstate, newstate))
        self.automat('router-disconnected')

#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()


if __name__ == "__main__":
    main()
