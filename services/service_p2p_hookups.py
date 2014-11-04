#!/usr/bin/python
#service_p2p_hookups.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_p2p_hookups

"""

from services.local_service import LocalService

def create_service():
    return P2PHookupsService()
    
class P2PHookupsService(LocalService):
    
    service_name = 'service_p2p_hookups'
    
    def dependent_on(self):
        from lib import settings
        depends = ['service_gateway',
                   'service_identity_propagate', ]
        if settings.enableTCP():
            depends.append('service_tcp_transport')
        if settings.enableUDP():
            depends.append('service_udp_transport')
        return depends
    
    def start(self):
        from p2p import p2p_service
        from p2p import contact_status
        from p2p import p2p_connector
        p2p_service.init()
        contact_status.init()
        p2p_connector.A('init')
        return True
    
    def stop(self):
        from p2p import contact_status
        from p2p import p2p_connector
        contact_status.shutdown()
        p2p_connector.Destroy()
        return True
    
    

    