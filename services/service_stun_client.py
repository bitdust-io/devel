#!/usr/bin/python
#service_stun_client.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_stun_client

"""

from services.local_service import LocalService

def create_service():
    return StunClientService()
    
class StunClientService(LocalService):
    
    service_name = 'service_stun_client'
    config_path = 'services/stun-client/enabled'
    
    def dependent_on(self):
        return ['service_entangled_dht',
                'service_udp_datagrams',
                ]
    
    def start(self):
        from stun import stun_client
        from lib import settings
        try:
            port_num = int(settings.getUDPPort())
        except:
            from logs import lg
            lg.exc()
            port_num = settings.DefaultUDPPort()
        stun_client.A('init', port_num)
        return True
    
    def stop(self):
        from stun import stun_client
        stun_client.A('shutdown')
        return True
    
    

    