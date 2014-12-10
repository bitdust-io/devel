#!/usr/bin/python
#service_ip_port_responder.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_ip_port_responder

"""

from services.local_service import LocalService

def create_service():
    return IPPortResponderService()
    
class IPPortResponderService(LocalService):
    
    service_name = 'service_ip_port_responder'
    config_path = 'services/stun-server/enabled'
    
    def dependent_on(self):
        return ['service_udp_datagrams',
                'service_entangled_dht',
                ]
    
    def start(self):
        from stun import stun_server
        from main import settings
        udp_port = int(settings.getUDPPort())
        stun_server.A('start', udp_port) 
        return True
    
    def stop(self):
        from stun import stun_server
        stun_server.A('stop')
        stun_server.Destroy()
        return True
    
    

    