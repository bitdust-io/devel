#!/usr/bin/python
#service_proxy_transport.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_proxy_transport

"""

from services.local_service import LocalService

def create_service():
    return ProxyTransportService()
    
class ProxyTransportService(LocalService):
    
    service_name = 'service_proxy_transport'
    config_path = 'services/proxy-transport/enabled'
    proto = 'proxy'
    
    def dependent_on(self):
        return ['service_gateway',
                ]
    
    def start(self):
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred
        from transport.proxy import proxy_interface
        from transport import network_transport
        from transport import gateway
        from main.config import conf
        self.starting_deferred = Deferred()
        self.interface = proxy_interface.GateInterface()
        self.transport = network_transport.NetworkTransport(
            'proxy', self.interface)
        self.transport.automat('init', 
            (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')
        conf().addCallback('services/proxy-transport/enabled', 
                           self._on_enabled_disabled)
        conf().addCallback('services/proxy-transport/sending-enabled', 
                           self._on_sending_enabled_disabled)
        conf().addCallback('services/proxy-transport/receiving-enabled', 
                           self._on_receiving_enabled_disabled)
        return self.starting_deferred
    
    def stop(self):
        from main.config import conf
        conf().removeCallback('services/proxy-transport/enabled') 
        conf().removeCallback('services/proxy-transport/sending-enabled') 
        conf().removeCallback('services/proxy-transport/receiving-enabled') 
        t = self.transport
        self.transport = None
        self.interface = None
        t.automat('shutdown')
        return True
    
    def installed(self):
        try:
            from transport.proxy import proxy_interface
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
        from transport.proxy import proxy_receiver
        from transport.proxy import proxy_sender
        if value:
            proxy_receiver.A('stop')
            proxy_sender.A('stop')
        else:
            proxy_receiver.A('start')
            proxy_sender.A('start')
        
    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from transport.proxy import proxy_receiver
        if value:
            proxy_receiver.A('stop')
        else:
            proxy_receiver.A('start')
        
    def _on_sending_enabled_disabled(self, path, value, oldvalue, result):
        from transport.proxy import proxy_sender
        if value:
            proxy_sender.A('stop')
        else:
            proxy_sender.A('start')

