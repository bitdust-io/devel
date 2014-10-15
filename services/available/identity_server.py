#!/usr/bin/python
#identity_server.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: identity_server

"""

from services.local_service import LocalService

def create_service():
    return IdentityServerService()
    
class IdentityServerService(LocalService):
    
    service_name = 'identity_server'
    
    def dependent_on(self):
        return ['tcp_connections',
                ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    