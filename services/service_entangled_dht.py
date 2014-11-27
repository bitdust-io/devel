#!/usr/bin/python
#service_entangled_dht.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_entangled_dht

"""

from services.local_service import LocalService

def create_service():
    return EntangledDHTService()
    
class EntangledDHTService(LocalService):
    
    service_name = 'service_entangled_dht'
    config_path = 'services/entangled-dht/enabled'
    
    def dependent_on(self):
        return ['service_udp_datagrams', 
                ]
    
    def start(self):
        from dht import dht_service
        from main import settings
        from main.config import conf
        dht_service.init(settings.getDHTPort(), settings.DHTDBFile())
        dht_service.connect()
        conf().addCallback('services/entangled-dht/udp-port',
            self._on_udp_port_modified)
        return True
    
    def stop(self):
        from dht import dht_service
        from main.config import conf
        conf().removeCallback('services/entangled-dht/udp-port')
        dht_service.shutdown()
        return True
    
    def _on_udp_port_modified(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')
        
    