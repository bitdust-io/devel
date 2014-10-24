#!/usr/bin/python
#distributed_hash_table.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: distributed_hash_table

"""

from services.local_service import LocalService

def create_service():
    return DistributedHashTableService()
    
class DistributedHashTableService(LocalService):
    
    service_name = 'distributed_hash_table'
    
    def dependent_on(self):
        return ['udp_datagrams', 
                'network', ]
    
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
    
    

    