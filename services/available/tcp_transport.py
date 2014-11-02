#!/usr/bin/python
#tcp_transport.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: tcp_transport

"""

from services.local_service import LocalService

def create_service():
    return TCPTransportService()
    
class TCPTransportService(LocalService):
    
    service_name = 'tcp_transport'
    proto = 'tcp'
    
    def dependent_on(self):
        return ['tcp_connections',
                'gateway',
                'network',
                ]
    
    def start(self):
        from transport.tcp import tcp_interface
        from transport import network_transport
        from transport import gateway
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred
        self.starting_deferred = Deferred()
        self.interface = tcp_interface.GateInterface()
        self.transport = network_transport.NetworkTransport(
            'tcp', self.interface)
        gateway.attach(self)
        self.transport.automat('init', 
            (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')
        return self.starting_deferred
    
    def stop(self):
        from transport import gateway
        gateway.detach(self)
        t = self.transport
        self.transport = None
        self.interface = None
        t.automat('shutdown')
        return True
    
    def enabled(self):
        from lib import settings
        return settings.enableTCP()
    
    def installed(self):
        try:
            from transport.tcp import tcp_interface
        except:
            return False
        return True

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        from logs import lg
        lg.out(6, 'tcp_transport._on_transport_state_changed in %r : %s->%s' % (
            transport, oldstate, newstate))
        if newstate in ['LISTENING', 'OFFLINE',]:
            self.starting_deferred.callback(newstate)
            self.starting_deferred = None
        from p2p import network_connector
        network_connector.A('network-transport-state-changed', self.transport)
    