#!/usr/bin/python
#service_udp_datagrams.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_udp_datagrams

"""

from services.local_service import LocalService

def create_service():
    return UDPDatagramsService()
    
class UDPDatagramsService(LocalService):
    
    service_name = 'service_udp_datagrams'
    config_path = 'services/udp-datagrams/enabled'
    
    def dependent_on(self):
        return ['service_network',
                ]
    
    def start(self):
        from lib import udp
        from main import settings
        from main.config import conf
        udp_port = settings.getUDPPort()
        conf().addCallback('services/udp-datagrams/udp-port', 
            self._on_udp_port_modified)
        if not udp.proto(udp_port):
            try:
                udp.listen(udp_port)
            except:
                return False
        return True
    
    def stop(self):
        from lib import udp
        from main import settings
        from main.config import conf
        udp_port = settings.getUDPPort()
        if udp.proto(udp_port):
            udp.close(udp_port)
        conf().removeCallback('services/udp-datagrams/udp-port')
        return True
    
    def _on_udp_port_modified(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')

    