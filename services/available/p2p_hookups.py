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
    return IdentityServerService()
    
class IdentityServerService(LocalService):
    
    service_name = 'p2p_hookups'
    
    def dependent_on(self):
        return ['gateway',
                ]
    
    def start(self):
        from p2p import p2p_connector
        p2p_connector.A('init')
        return True
    
    def stop(self):
        return True
    
    

    