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
        from lib import settings
        from transport import gateway
        transports_list = []
        if settings.enableTCP():
            transports_list.append('tcp')
        if settings.enableUDP():
            transports_list.append('udp')
        gateway.init(transports_list)
        # gateway.start()
        return True
    
    def stop(self):
        from transport import gateway
        gateway.shutdown()
        return True
    
    

    