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
    
    name = 'stun_server'
    
    def dependent_on(self):
        return ['udp_datagrams',
                ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    