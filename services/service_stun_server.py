#!/usr/bin/python
#service_stun_server.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_stun_server

"""

from services.local_service import LocalService

def create_service():
    return StunServerService()
    
class StunServerService(LocalService):
    
    service_name = 'service_stun_server'
    config_path = 'services/stun-server/enabled'
    
    def dependent_on(self):
        return ['service_udp_datagrams',
                'service_entangled_dht',
                ]
    
    def start(self):
        from stun import stun_server
        from main import settings
        udp_port = int(settings.getUDPPort())
        stun_server.A('start', udp_port) 
        return True
    
    def stop(self):
        from stun import stun_server
        stun_server.A('stop')
        stun_server.Destroy()
        return True
    
    

    