#!/usr/bin/python
#p2p_hookups.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: p2p_hookups

"""

from services.local_service import LocalService

def create_service():
    return P2PHookupsService()
    
class P2PHookupsService(LocalService):
    
    service_name = 'p2p_hookups'
    
    def dependent_on(self):
        from lib import settings
        depends = ['gateway',
                   'identity_propagate']
        if settings.enableTCP():
            depends.append('tcp_transport')
        if settings.enableUDP():
            depends.append('udp_transport')
        return depends
    
    def start(self):
        from p2p import p2p_connector
        p2p_connector.A('init')
        return True
    
    def stop(self):
        from p2p import p2p_connector
        p2p_connector.Destroy()
        return True
    
    

    