#!/usr/bin/python
#service_network.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_network

"""

from services.local_service import LocalService

def create_service():
    return NetworkService()
    
class NetworkService(LocalService):
    
    service_name = 'service_network'
    config_path = 'services/network/enabled'
    
    def dependent_on(self):
        return []
    
    def start(self):
        from p2p import network_connector
        network_connector.A('init')
        # from twisted.internet import reactor
        # reactor.callLater(0.01, network_connector.A, 'reconnect')
        return True
    
    def stop(self):
        from p2p import network_connector
        network_connector.Destroy()
        return True
    
    

    