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
    config_path = 'services/id-server/enabled'
    
    def init(self):
        # self.debug_level = 2
        self.log_events = True
    
    def dependent_on(self):
        return ['service_tcp_connections',
                ]
        
    def enabled(self):
        from main import settings
        return settings.enableIdServer()
    
    def start(self):
        from userid import id_server
        from main import settings
        id_server.A('init', (settings.getIdServerWebPort(), 
                             settings.getIdServerTCPPort()))
        id_server.A('start')
        return True
    
    def stop(self):
        from userid import id_server
        id_server.A('stop')
        id_server.A('shutdown')
        return True
    
    

    