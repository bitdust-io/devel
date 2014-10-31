#!/usr/bin/python
#stun_server.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: stun_server

"""

from services.local_service import LocalService

def create_service():
    return StunServerService()
    
class StunServerService(LocalService):
    
    service_name = 'stun_server'
    
    def dependent_on(self):
        return ['udp_datagrams',
                ]
    
    def start(self):
        from stun import stun_server
        from lib import settings
        udp_port = int(settings.getUDPPort())
        stun_server.A('start', udp_port) 
        return True
    
    def stop(self):
        from stun import stun_server
        stun_server.A('stop')
        stun_server.Destroy()
        return True
    
    

    