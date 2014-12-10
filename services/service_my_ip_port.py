#!/usr/bin/python
#service_my_ip_port.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_my_ip_port

"""

from services.local_service import LocalService

def create_service():
    return MyIPPortService()
    
class MyIPPortService(LocalService):
    
    service_name = 'service_my_ip_port'
    config_path = 'services/my-ip-port/enabled'
    
    def init(self):
        self._my_address = None
    
    def dependent_on(self):
        return ['service_entangled_dht',
                'service_udp_datagrams',
                ]
    
    def start(self):
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred
        from stun import stun_client
        from main import settings
        stun_client.A('init', settings.getUDPPort())
        return True
        # d = Deferred()
        # reactor.callLater(0.5, stun_client.A, 'start', 
        #     lambda result, typ, ip, details: 
        #         self._on_stun_client_finished(result, typ, ip, details, d))
        # return d
    
    def stop(self):
        from stun import stun_client
        stun_client.A('shutdown')
        return True
    
    def _on_stun_client_finished(self, result, typ, ip, details, result_defer):
        from stun import stun_client
        result_defer.callback(stun_client.A().getMyExternalAddress()) 

