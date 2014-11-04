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
    
    def dependent_on(self):
        return ['service_udp_datagrams', 
                'service_network', 
                ]
    
    def start(self):
        from dht import dht_service
        from lib import settings
        dht_service.init(int(settings.getDHTPort()), settings.DHTDBFile())
        dht_service.connect()
        return True
    
    def stop(self):
        from dht import dht_service
        dht_service.shutdown()
        return True
    
    

    