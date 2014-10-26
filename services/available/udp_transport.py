#!/usr/bin/python
#udp_transport.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: udp_transport

"""

from services.local_service import LocalService

def create_service():
    return UDPTransportService()
    
class UDPTransportService(LocalService):
    
    service_name = 'udp_transport'
    
    def dependent_on(self):
        return ['udp_datagrams',
                'stun_client',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    def is_enabled(self):
        from lib import settings
        return settings.enableUDP()

    