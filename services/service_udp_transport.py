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
    config_path = 'services/udp-transport/enabled'
    proto = 'udp'
    
    def dependent_on(self):
        return ['service_udp_datagrams',
                'service_stun_client',
                'service_gateway',
                ]
    
    def start(self):
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred
        from transport.udp import udp_interface
        from transport import network_transport
        from transport import gateway
        from lib.config import conf
        self.starting_deferred = Deferred()
        self.interface = udp_interface.GateInterface()
        self.transport = network_transport.NetworkTransport(
            'udp', self.interface)
        self.transport.automat('init', 
            (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')
        conf().addCallback('services/udp-transport/enabled', 
            self._on_enabled_disabled)
        conf().addCallback('services/udp-transport/receiving-enabled', 
            self._on_receiving_enabled_disabled)
        conf().addCallback('services/network/receive-limit', 
            self._on_network_receive_limit_modified)
        conf().addCallback('services/network/send-limit', 
            self._on_network_send_limit_modified)
        return self.starting_deferred
    
    def stop(self):
        from lib.config import conf
        conf().removeCallback('services/udp-transport/enabled') 
        conf().removeCallback('services/udp-transport/receiving-enabled')
        conf().removeCallback('services/network/receive-limit') 
        conf().removeCallback('services/network/send-limit') 
        t = self.transport
        self.transport = None
        self.interface = None
        t.automat('shutdown')
        return True
    
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
        
    def _on_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')
        
    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')
        
    def _on_network_receive_limit_modified(self, path, value, oldvalue, result):
        from transport.udp import udp_stream 
        udp_stream.set_global_limit_receive_bytes_per_sec(int(value))
        
    def _on_network_send_limit_modified(self, path, value, oldvalue, result):
        from transport.udp import udp_stream 
        udp_stream.set_global_limit_send_bytes_per_sec(int(value))
        
    