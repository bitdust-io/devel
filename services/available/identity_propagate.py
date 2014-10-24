#!/usr/bin/python
#identity_propagate.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: identity_propagate

"""

from services.local_service import LocalService

def create_service():
    return IdentityPropagateService()
    
class IdentityPropagateService(LocalService):
    
    service_name = 'identity_propagate'
    
    def dependent_on(self):
        return ['network',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    