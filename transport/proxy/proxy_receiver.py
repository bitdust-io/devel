#!/usr/bin/env python
#proxy_receiver.py
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
.. module:: proxy_receiver
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
    * :red:`router-id-received`
    * :red:`service-accepted`
    * :red:`service-refused`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-10sec`
    * :red:`timer-30sec`
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------ 

import cStringIO

from twisted.internet import reactor

from logs import lg

from automats import automat

from main import config

from crypt import key
from crypt import signed
from crypt import encrypted

from p2p import commands
from p2p import p2p_service
from p2p import lookup

from contacts import identitycache

from transport import callback
from transport import packet_in

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

def GetMyOriginalIdentitySource():
    return config.conf().getData('services/proxy-transport/my-original-identity') 

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
    This class implements all the functionality of the ``proxy_receiver()`` state machine.
    """

    timers = {
        'timer-30sec': (30.0, ['ACK?','SERVICE?']),
        'timer-10sec': (10.0, ['ACK?']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of proxy_receiver() machine.
        """
        self.router_idurl = None
        self.router_identity = None
        self.router_proto_host = None
        self.request_service_packet_id = []

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when proxy_receiver() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the proxy_receiver()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The core proxy_receiver() code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(arg)
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start' and not self.isCurrentRouterExist(arg):
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(arg)
            elif event == 'start' and self.isCurrentRouterExist(arg):
                self.state = 'ACK?'
                self.doLoadRouterInfo(arg)
                self.doSendMyIdentity(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'timer-10sec':
                self.doSendMyIdentity(arg)
            elif event == 'ack-received':
                self.state = 'SERVICE?'
                self.doSendRequestService(arg)
            elif event == 'timer-30sec' or event == 'fail-received':
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doReportStopped(arg)
        #---LISTEN---
        elif self.state == 'LISTEN':
            if event == 'router-id-received':
                self.doUpdateRouterID(arg)
            elif event == 'inbox-packet':
                self.doProcessInboxPacket(arg)
            elif event == 'service-refused':
                self.state = 'FIND_NODE?'
                self.doStopListening(arg)
                self.doReportDisconnected(arg)
                self.doDHTFindRandomNode(arg)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doSendCancelService(arg)
                self.doStopListening(arg)
                self.doReportDisconnected(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doSendCancelService(arg)
                self.doStopListening(arg)
                self.doReportDisconnected(arg)
                self.doDestroyMe(arg)
        #---FIND_NODE?---
        elif self.state == 'FIND_NODE?':
            if event == 'nodes-not-found':
                self.doWaitAndTryAgain(arg)
            elif event == 'found-one-node':
                self.state = 'ACK?'
                self.doRememberNode(arg)
                self.doSendMyIdentity(arg)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doReportStopped(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'ack-received':
                self.doSendRequestService(arg)
            elif event == 'service-accepted':
                self.state = 'LISTEN'
                self.doStartListening(arg)
                self.doReportConnected(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doReportStopped(arg)
            elif event == 'timer-30sec' or event == 'service-refused':
                self.state = 'FIND_NODE?'
                self.doLookupRandomNode(arg)
        return None

    def isCurrentRouterExist(self, arg):
        """
        Condition method.
        """
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

    def doLookupRandomNode(self, arg):
        """
        Action method.
        """
        # self._find_random_node()
        # TODO: this is still under construction - so I am using this node for tests
        self.automat('found-one-node', 'http://veselin-p2p.ru/bitdust_j2_vps1001.xml')

    def doWaitAndTryAgain(self, arg):
        """
        Action method.
        """
        reactor.callLater(10, self._find_random_node)

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        p2p_service.SendIdentity(
            self.router_idurl, 
            wide=True, 
            callbacks={
                commands.Ack(): lambda response, info: self.automat('ack-received', (response, info)),
                commands.Fail(): lambda x: self.automat('nodes-not-found')})

    def doRememberNode(self, arg):
        """
        Action method.
        """
        self.router_idurl = arg        

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
        request = p2p_service.SendRequestService(
            self.router_idurl, service_info,
                callbacks={
                    commands.Ack(): self._request_service_ack,
                    commands.Fail(): self._request_service_fail})
        self.request_service_packet_id.append(request.PacketID)

    def doSendCancelService(self, arg):
        """
        Action method.
        """
        p2p_service.SendCancelService(
            self.router_idurl, 'service_proxy_server') 

    def doProcessInboxPacket(self, arg):
        """
        Action method.
        """
        newpacket, info, status, error_message = arg
        block = encrypted.Unserialize(newpacket.Payload)
        if block is None:
            lg.out(2, 'proxy_receiver.doProcessInboxPacket ERROR reading data from %s' % newpacket.RemoteID)
            return
        try:
            session_key = key.DecryptLocalPK(block.EncryptedSessionKey)
            padded_data = key.DecryptWithSessionKey(session_key, block.EncryptedData)
            inpt = cStringIO.StringIO(padded_data[:int(block.Length)])
            data = inpt.read()
        except:
            lg.out(2, 'proxy_receiver.doProcessInboxPacket ERROR reading data from %s' % newpacket.RemoteID)
            lg.out(2, '\n' + padded_data)
            lg.exc()
            try:
                inpt.close()
            except:
                pass
            return
        inpt.close()
        routed_packet = signed.Unserialize(data)
#        transfer_id = gateway.make_transfer_ID()
#        pkt_in = packet_in.create(transfer_id)
#        pkt_in.setup(pkt_in)
#        pkt_in.automat('valid-inbox-packet', routed_packet)
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
        callback.insert_inbox_callback(0, self._on_inbox_packet_received)
        if _Debug:
            lg.out(2, 'proxy_receiver.doStartListening !!!!!!! router: %s at %s://%s' % (
                self.router_idurl, self.router_proto_host[0], self.router_proto_host[1]))

    def doStopListening(self, arg):
        """
        Action method.
        """
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
            lg.warn('cached identity is not same')
            return
        self.router_identity = newidentity

    def doReportStopped(self, arg):
        """
        Action method.
        """

    def doReportConnected(self, arg):
        """
        Action method.
        """
        import proxy_interface
        proxy_interface.interface_receiving_started(self.router_idurl,
            {'router_idurl': self.router_idurl,})

    def doReportDisconnected(self, arg):
        """
        Action method.
        """
        import proxy_interface
        proxy_interface.interface_disconnected()

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        automat.objects().pop(self.index)
        global _ProxyReceiver
        del _ProxyReceiver
        _ProxyReceiver = None

    def _nodes_lookup_finished(self, idurls):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._nodes_lookup_finished : %r' % idurls)
        for idurl in idurls:
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if len(myprotos.intersection(remoteprotos)) > 0:
                self.automat('found-one-user', idurl)
                return
        self.automat('users-not-found')

    def _find_random_node(self):
        d = lookup.start()
        d.addCallback(self._nodes_lookup_finished)
        d.addErrback(lambda err: self.automat('users-not-found'))
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

    def _request_service_ack(self, response, info):
        if response.PacketID not in self.request_service_packet_id:
            lg.warn('wong PacketID in response: %s, but outgoing was : %s' % (
                response.PacketID, str(self.request_service_packet_id)))
            self.automat('service-refused', (response, info))
            return
        self.request_service_packet_id.remove(response.PacketID)
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._request_service_ack : %s' % str(response.Payload))
        if response.Payload.startswith('accepted'):
            self.automat('service-accepted', (response, info))
        else:
            self.automat('service-refused', (response, info))
            
    def _request_service_fail(self, response, info):
        if response.PacketID not in self.request_service_packet_id:
            lg.warn('wong PacketID in response: %s, but outgoing was : %s' % (
                response.PacketID, str(self.request_service_packet_id)))
        else:
            self.request_service_packet_id.remove(response.PacketID)
        self.automat('service-refused', (response, info))

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        if  newpacket.Command == commands.Identity() and \
            newpacket.CreatorID == self.router_idurl and \
            newpacket.RemoteID == my_id.getLocalID():
                self.automat('router-id-received', (newpacket, info))
                return True
        if  newpacket.Command == commands.Fail() and \
            newpacket.CreatorID == self.router_idurl and \
            newpacket.RemoteID == my_id.getLocalID():
            # newpacket.Payload == 'route not exist':
                self.automat('service-refused', (newpacket, info))
                return True
        if newpacket.Command != commands.Data():
            return False
        # if not newpacket.PacketID.startswith('routed_in_'):
            # return False
        if newpacket.RemoteID != my_id.getLocalID():
            return False
        if newpacket.CreatorID != self.router_idurl:
            return False
        self.automat('inbox-packet', (newpacket, info, status, error_message))
        return True             

#------------------------------------------------------------------------------ 

    def doDHTFindRandomNode(self, arg):
        """
        Action method.
        """

def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

if __name__ == "__main__":
    main()

