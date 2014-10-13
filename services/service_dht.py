#!/usr/bin/python
#dht_service.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: dht_service

"""


from switchable_service import SwitchableService

class DistributedHashTableService(SwitchableService):
    name = 'distributed_hash_table'
    
    def dependent_on(self):
        return ['udp_datagrams', ]
    
    
    