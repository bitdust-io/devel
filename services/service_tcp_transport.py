#!/usr/bin/python
#service_tcp_transport.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_tcp_transport

"""

from services.local_service import LocalService

def create_service():
    return TCPTransportService()
    
class TCPTransportService(LocalService):
    
    service_name = 'service_tcp_transport'
    config_path = 'services/tcp-transport/enabled'
    proto = 'tcp'
    
    def dependent_on(self):
        return ['service_tcp_connections',
                'service_gateway',
                ]
    
    def start(self):
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred
        from transport.tcp import tcp_interface
        from transport import network_transport
        from transport import gateway
        from lib.config import conf
        self.starting_deferred = Deferred()
        self.interface = tcp_interface.GateInterface()
        self.transport = network_transport.NetworkTransport(
            'tcp', self.interface)
        self.transport.automat('init', 
            (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')
        conf().addCallback('services/tcp-transport/enabled', 
                           self._on_enabled_disabled)
        conf().addCallback('services/tcp-transport/receiving-enabled', 
                           self._on_receiving_enabled_disabled)
        return self.starting_deferred
    
    def stop(self):
        from lib.config import conf
        conf().removeCallback('services/tcp-transport/enabled') 
        conf().removeCallback('services/tcp-transport/receiving-enabled') 
        t = self.transport
        self.transport = None
        self.interface = None
        t.automat('shutdown')
        return True
    
    def installed(self):
        try:
            from transport.tcp import tcp_interface
        except:
            return False
        return True

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        if self.starting_deferred:
            if newstate in ['LISTENING', 'OFFLINE',]:
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
        if self.transport:
            from p2p import network_connector
            network_connector.A('network-transport-state-changed', self.transport)
            
    def _on_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')
        
    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')



        