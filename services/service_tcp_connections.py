#!/usr/bin/python
#service_tcp_connections.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_tcp_connections

"""

from services.local_service import LocalService

def create_service():
    return TCPConnectionsService()
    
class TCPConnectionsService(LocalService):
    
    service_name = 'service_tcp_connections'
    config_path = 'services/tcp-connections/enabled'
    
    def dependent_on(self):
        return ['service_network',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    