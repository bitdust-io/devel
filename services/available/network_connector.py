#!/usr/bin/python
#network_connector.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: network_connector

"""

from services.local_service import LocalService

def create_service():
    return NetworkConnectorService()
    
class NetworkConnectorService(LocalService):
    
    name = 'network_connector'
    
    def dependent_on(self):
        return []
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    