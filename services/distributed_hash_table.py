#!/usr/bin/python
#dht_service.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_distributed_hash_table

"""

from local_service import LocalService

def create_service():
    return DistributedHashTableService()
    
class DistributedHashTableService(LocalService):
    
    name = 'distributed_hash_table'
    
    def dependent_on(self):
        return ['udp_datagrams', ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    