#!/usr/bin/python
#service_identity_server.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_identity_server

"""

from services.local_service import LocalService

def create_service():
    return IdentityServerService()
    
class IdentityServerService(LocalService):
    
    service_name = 'service_identity_server'
    config_path = 'services/identity-server/enabled'
    
    def init(self):
        # self.debug_level = 2
        self.log_events = True
    
    def dependent_on(self):
        return ['service_tcp_connections',
                ]
        
    def enabled(self):
        from lib import settings
        return settings.enableIdServer()
    
    def start(self):
        from userid import id_server
        from lib import settings
        id_server.A('init')
        id_server.A('start', (settings.getIdServerWebPort(), 
                              settings.getIdServerTCPPort()))
        return True
    
    def stop(self):
        from userid import id_server
        id_server.A('stop')
        id_server.A('shutdown')
        return True
    
    

    