#!/usr/bin/env python
# proxy_receiver.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

    <i>generated using <a href="http://bitdust.io/visio2python/" target="_blank">visio2python</a> tool</i><br>
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
    * :red:`timer-2sec`
    * :red:`timer-5sec`
    * :red:`timer-7sec`
"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

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

from contacts import identitycache

from transport import callback
from transport import packet_in
from transport import packet_out

from transport.proxy import proxy_interface

from userid import my_id
from userid import identity

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
        _ProxyReceiver = ProxyReceiver('proxy_receiver', 'AT_STARTUP', _DebugLevel, _Debug)
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
        'timer-7sec': (7.0, ['ACK?']),
        'timer-2sec': (2.0, ['ACK?']),
        'timer-10sec': (10.0, ['LISTEN']),
        'timer-5sec': (5.0, ['SERVICE?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of proxy_receiver() machine.
        """

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
        <http://bitdust.io/visio2python/>`_ tool.
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
            elif event == 'timer-2sec':
                self.doSendMyIdentity(arg)
            elif event == 'timer-7sec' or event == 'fail-received':
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
            elif event == 'stop' or event == 'nodes-not-found':
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
        self.router_idurl = None
        self.router_identity = None
        self.router_proto_host = None
        self.request_service_packet_id = []
        self.latest_packet_received = 0

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
        # TODO: this is still under construction - so I am using this node for tests
        # self.automat('found-one-node', 'http://veselin-p2p.ru/bitdust_j2_vps1001.xml')

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver.doSendMyIdentity to %s' % self.router_idurl)
        self._do_send_identity_to_router(my_id.getLocalIdentity().serialize())
        identity_source = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if identity_source:
            if _Debug:
                lg.out(_DebugLevel, '    also sending identity loaded from "my-original-identity" config')
            self._do_send_identity_to_router(identity_source)

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
        service_info = 'service_proxy_server \n'
        orig_identity = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if not orig_identity:
            orig_identity = my_id.getLocalIdentity().serialize()
        service_info += orig_identity
        # for t in gateway.transports().values():
        #     service_info += '%s://%s' % (t.proto, t.host)
        # service_info += ' '
        newpacket = signed.Packet(
            commands.RequestService(),
            my_id.getLocalID(),
            my_id.getLocalID(),
            packetid.UniqueID(),
            service_info,
            self.router_idurl,)
        packet_out.create(newpacket, wide=False, callbacks={
            commands.Ack(): self._on_request_service_ack,
            commands.Fail(): self._on_request_service_fail},)
        self.request_service_packet_id.append(newpacket.PacketID)

    def doSendCancelService(self, arg):
        """
        Action method.
        """
        newpacket = signed.Packet(
            commands.CancelService(),
            my_id.getLocalID(),
            my_id.getLocalID(),
            packetid.UniqueID(),
            'service_proxy_server',
            self.router_idurl,)
        packet_out.create(newpacket, wide=True, callbacks={
            commands.Ack(): self._on_request_service_ack,
            commands.Fail(): self._on_request_service_fail},)

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
            lg.out(2, 'proxy_receiver.doProcessInboxPacket ERROR unserialize packet from %s' % newpacket.CreatorID)
            return
        if _Debug:
            lg.out(_DebugLevel, '<<<Relay-IN %s from %s://%s' % (
                str(routed_packet), info.proto, info.host,))
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
        if ReadMyOriginalIdentitySource():
            lg.warn('my original identity is not empty')
        else:
            config.conf().setData('services/proxy-transport/my-original-identity',
                                  my_id.getLocalIdentity().serialize())
        self.request_service_packet_id = []
        callback.insert_inbox_callback(0, self._on_inbox_packet_received)
        if _Debug:
            lg.out(2, 'proxy_receiver.doStartListening !!!!!!! router: %s at %s://%s' % (
                self.router_idurl, self.router_proto_host[0], self.router_proto_host[1]))

    def doStopListening(self, arg):
        """
        Action method.
        """
        if not ReadMyOriginalIdentitySource():
            lg.warn('my original identity is not empty')
        else:
            config.conf().setData('services/proxy-transport/my-original-identity', '')
        config.conf().setString('services/proxy-transport/current-router', '')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        self.router_identity = None
        self.router_idurl = None
        self.router_proto_host = None
        self.request_service_packet_id = []
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
        if time.time() - self.latest_packet_received < 10:
            return
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver.doCheckPingRouter to %s' % self.router_idurl)
        identity_source = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if identity_source:
            if _Debug:
                lg.out(_DebugLevel, '    identity loaded from "my-original-identity" config')
            identity_source = my_id.getLocalIdentity().serialize()
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

    def _do_send_identity_to_router(self, identity_source, failed_event='nodes-not-found'):
        try:
            identity_obj = identity.identity(xmlsrc=identity_source)
        except:
            lg.exc()
            return
        if _Debug:
            lg.out(_DebugLevel, '        contacts=%s, sources=%s' % (identity_obj.contacts, identity_obj.sources))
        newpacket = signed.Packet(
            commands.Identity(), my_id.getLocalID(),
            my_id.getLocalID(), 'identity',
            identity_source, self.router_idurl,
        )
        packet_out.create(newpacket, wide=True, callbacks={
            commands.Ack(): lambda response, info: self.automat('ack-received', (response, info)),
            commands.Fail(): lambda x: self.automat(failed_event),
        })

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
        # self.automat('found-one-node', 'http://bitdust.io:8084/seed2_b17a.xml')
        # return
        preferred_routers_raw = config.conf().getData('services/proxy-transport/preferred-routers').strip()
        preferred_routers = []
        if preferred_routers_raw:
            preferred_routers.extend(preferred_routers_raw.split('\n'))
        if preferred_routers:
            known_router = random.choice(preferred_routers)
            if _Debug:
                lg.out(_DebugLevel, 'proxy_receiver._find_random_node selected random item from preferred_routers: %s' % known_router)
            self.automat('found-one-node', known_router)
            return
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._find_random_node')
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
        if response.Payload.startswith('accepted'):
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
        if newpacket.Command == commands.Fail() and \
                newpacket.CreatorID == self.router_idurl and \
                newpacket.RemoteID == my_id.getLocalID():
            self.automat('service-refused', (newpacket, info))
            return True
        if newpacket.CreatorID == self.router_idurl:
            self.latest_packet_received = time.time()
        if newpacket.Command != commands.Relay():
            return False
        # if not newpacket.PacketID.startswith('routed_in_'):
            # return False
#         if newpacket.RemoteID != my_id.getLocalID():
#             return False
#         if newpacket.CreatorID != self.router_idurl:
#             return False
        self.automat('inbox-packet', (newpacket, info, status, error_message))
        return True

#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

if __name__ == "__main__":
    main()
