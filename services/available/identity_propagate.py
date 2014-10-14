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
    
    name = 'identity_propagate'
    
    def dependent_on(self):
        return []
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    