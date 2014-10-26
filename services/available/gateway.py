#!/usr/bin/python
#gateway.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: gateway

"""

from services.local_service import LocalService

def create_service():
    return GatewayService()
    
class GatewayService(LocalService):
    
    service_name = 'gateway'
    
    def dependent_on(self):
        from lib import settings
        depends = ['network',]
        if settings.enableTCP():
            depends.append('tcp_transport')
        if settings.enableUDP():
            depends.append('udp_transport')
        return depends
    
    def start(self):
        from transport import gateway
        gateway.init()
        # gateway.start()
        return True
    
    def stop(self):
        from transport import gateway
        gateway.shutdown()
        return True
    
    

    