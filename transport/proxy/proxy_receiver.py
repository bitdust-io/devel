

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
    * :red:`init`
    * :red:`nodes-not-found`
    * :red:`service-accepted`
    * :red:`service-refused`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-10sec`
    * :red:`timer-30sec`
"""

import random

from twisted.internet import reactor

from logs import lg

from automats import automat

from dht import dht_service

from p2p import commands
from p2p import p2p_service
from p2p import p2p_connector

from contacts import identitycache

import proxy_interface

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

_ProxyReceiver = None

#------------------------------------------------------------------------------

def A(event=None, arg=None):
    """
    Access method to interact with proxy_receiver() machine.
    """
    global _ProxyReceiver
    if _ProxyReceiver is None:
        # set automat name and starting state here
        _ProxyReceiver = ProxyReceiver('proxy_receiver', 'AT_STARTUP', _DebugLevel)
    if event is not None:
        _ProxyReceiver.automat(event, arg)
    return _ProxyReceiver

#------------------------------------------------------------------------------

class ProxyReceiver(automat.Automat):
    """
    This class implements all the functionality of the ``proxy_receiver()`` state machine.
    """

    timers = {
        'timer-30sec': (30.0, ['SERVICE?']),
        'timer-10sec': (10.0, ['ACK?']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of proxy_receiver() machine.
        """
        self.router_idurl = None
        self.router_identity = None
        self.request_service_packet_id = None

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
        #---ACK?---
        if self.state == 'ACK?':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop' :
                self.state = 'STOPPED'
                self.doReportStopped(arg)
            elif event == 'ack-received' :
                self.state = 'SERVICE?'
                self.doSendRequestService(arg)
            elif event == 'timer-10sec' or event == 'fail-received' :
                self.state = 'FIND_NODE?'
                self.doDHTFindRandomNode(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'STOPPED'
                self.doInit(arg)
        #---LISTEN---
        elif self.state == 'LISTEN':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doStopListening(arg)
                self.doReportDisconnected(arg)
                self.doDestroyMe(arg)
            elif event == 'stop' :
                self.state = 'STOPPED'
                self.doStopListening(arg)
                self.doReportDisconnected(arg)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'service-accepted' :
                self.state = 'LISTEN'
                self.doStartListening(arg)
                self.doReportConnected(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop' :
                self.state = 'STOPPED'
                self.doReportStopped(arg)
            elif event == 'timer-30sec' or event == 'service-refused' :
                self.state = 'FIND_NODE?'
                self.doDHTFindRandomNode(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start' :
                self.state = 'FIND_NODE?'
                self.doDHTFindRandomNode(arg)
        #---FIND_NODE?---
        elif self.state == 'FIND_NODE?':
            if event == 'nodes-not-found' :
                self.doWaitAndTryAgain(arg)
            elif event == 'found-one-node' :
                self.state = 'ACK?'
                self.doRememberNode(arg)
                self.doSendMyIdentity(arg)
            elif event == 'stop' :
                self.state = 'STOPPED'
                self.doReportStopped(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        return None

    def doInit(self, arg):
        """
        Action method.
        """

    def doDHTFindRandomNode(self, arg):
        """
        Action method.
        """
        self._find_random_node()

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

    def doSendRequestService(self, arg):
        """
        Action method.
        """
        request = p2p_service.SendRequestService(
            self.router_idurl, 'service_proxy_server', callbacks={
                commands.Ack(): self._request_service_ack,
                commands.Fail(): lambda response, info: self.automat('service-refused', response)})
        self.request_service_packet_id = request.PacketID

    def doRememberNode(self, arg):
        """
        Action method.
        """
        self.router_idurl = arg        

    def doStartListening(self, arg):
        """
        Action method.
        """
        self.router_identity = identitycache.FromCache(self.router_idurl)

    def doStopListening(self, arg):
        """
        Action method.
        """
        self.router_identity = None
        self.router_idurl = None

    def doReportStopped(self, arg):
        """
        Action method.
        """

    def doReportConnected(self, arg):
        """
        Action method.
        """
        proxy_interface.interface_receiving_started(self.router_idurl)

    def doReportDisconnected(self, arg):
        """
        Action method.
        """
        proxy_interface.interface_disconnected()
        
    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        automat.objects().pop(self.index)
        global _ProxyReceiver
        del _ProxyReceiver
        _ProxyReceiver = None

    def _find_random_node(self):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._find_random_node')
        # DEBUG
        self._got_remote_idurl({'idurl': 'http://p2p-id.ru/bitdust_vps1001_i.xml'})
        return
        new_key = dht_service.random_key()
        d = dht_service.find_node(new_key)
        d.addCallback(self._some_nodes_found)
        d.addErrback(lambda x: self.automat('nodes-not-found'))
        return d

    def _some_nodes_found(self, nodes):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._some_nodes_found : %d' % len(nodes))
        if len(nodes) > 0:
            node = random.choice(nodes)
            d = node.request('idurl')
            d.addCallback(self._got_remote_idurl)
            d.addErrback(lambda x: self.automat('nodes-not-found'))
        else:
            self.automat('nodes-not-found')
        return nodes
            
    def _got_remote_idurl(self, response):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._got_remote_idurl response=%s' % str(response) )
        try:
            idurl = response['idurl']
        except:
            idurl = None
        if not idurl or idurl == 'None':
            self.automat('nodes-not-found')
            return response
        d = identitycache.immediatelyCaching(idurl)
        d.addCallback(lambda src: self.automat('found-one-node', idurl))
        d.addErrback(lambda x: self.automat('nodes-not-found'))
        return response

    def _request_service_ack(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_receiver._request_service_ack : %s' % str(response.Payload))
        if response.Payload.startswith('accepted'):
            self.automat('service-accepted')
        else:
            self.automat('service-refused')
        
#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

if __name__ == "__main__":
    main()

