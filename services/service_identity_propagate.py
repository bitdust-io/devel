#!/usr/bin/python
#service_identity_propagate.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_identity_propagate

"""

from services.local_service import LocalService

def create_service():
    return IdentityPropagateService()
    
class IdentityPropagateService(LocalService):
    
    service_name = 'service_identity_propagate'
    config_path = 'services/identity-propagate/enabled'
    
    def dependent_on(self):
        return ['service_gateway',
                'service_tcp_connections',
                ]
    
    def start(self):
        from userid import my_id
        my_id.loadLocalIdentity()
        if my_id._LocalIdentity is None:
            from logs import lg
            lg.warn('Loading local identity failed - need to register first')
            return False
        from contacts import identitycache
        identitycache.init()
        from contacts import contactsdb
        contactsdb.init()
        from p2p import propagate
        propagate.init()
        return True
    
    def stop(self):
        from p2p import propagate
        propagate.shutdown()
        from contacts import contactsdb
        contactsdb.shutdown()
        from contacts import identitycache
        identitycache.shutdown()
        from userid import my_id
        my_id.shutdown()
        return True
    
    

    