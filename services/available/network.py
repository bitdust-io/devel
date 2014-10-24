#!/usr/bin/python
#network.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: network

"""

from services.local_service import LocalService

def create_service():
    return NetworkService()
    
class NetworkService(LocalService):
    
    service_name = 'network'
    
    def dependent_on(self):
        return []
    
    def start(self):
        from p2p import network_connector
        network_connector.A('init')
        return True
    
    def stop(self):
        return True
    
    

    