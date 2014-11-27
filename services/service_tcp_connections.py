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
        from main.config import conf
        conf().addCallback('services/tcp-connections/tcp-port', 
                           self._on_tcp_port_modified)
        return True
    
    def stop(self):
        from main.config import conf
        conf().removeCallback('services/tcp-connections/tcp-port')
        return True
    
    def _on_tcp_port_modified(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')
        

    