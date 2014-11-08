#!/usr/bin/python
#service_udp_transport.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_udp_transport

"""

from services.local_service import LocalService

def create_service():
    return UDPTransportService()
    
class UDPTransportService(LocalService):
    
    service_name = 'service_udp_transport'
    proto = 'udp'
    
    def dependent_on(self):
        return ['service_udp_datagrams',
                'service_stun_client',
                'service_gateway',
                ]
    
    def start(self):
        from transport.udp import udp_interface
        from transport import network_transport
        from transport import gateway
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred
        self.starting_deferred = Deferred()
        self.interface = udp_interface.GateInterface()
        self.transport = network_transport.NetworkTransport(
            'udp', self.interface)
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
        return settings.enableUDP()

    def installed(self):
        try:
            from transport.udp import udp_interface
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
        
        
    