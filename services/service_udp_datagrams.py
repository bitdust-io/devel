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
        from lib import settings
        udp_port = int(settings.getUDPPort())
        if not udp.proto(udp_port):
            udp.listen(udp_port)
        return True
    
    def stop(self):
        from lib import udp
        from lib import settings
        udp_port = int(settings.getUDPPort())
        if udp.proto(udp_port):
            udp.close(udp_port)
        return True
    
    

    