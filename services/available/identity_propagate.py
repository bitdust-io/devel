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
                'gateway',
                'tcp_connections',
                ]
    
    def start(self):
        from lib import misc
        misc.loadLocalIdentity()
        if misc._LocalIdentity is None:
            raise Exception('Loading local identity failed - need to register first')
            return
        from lib import contacts
        contacts.init()
        import userid.identitycache as identitycache
        identitycache.init()
        from userid import propagate
        propagate.init()
        return True
    
    def stop(self):
        return True
    
    

    