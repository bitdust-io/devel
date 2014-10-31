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
        return ['network',
                ]
    
    def start(self):
        # from lib import settings
        from transport import gateway
#        transports_list = []
#        if settings.enableTCP():
#            transports_list.append('tcp')
#        if settings.enableUDP():
#            transports_list.append('udp')
        gateway.init()
        # gateway.start()
        return True
    
    def stop(self):
        from transport import gateway
        gateway.stop()
        gateway.shutdown()
        return True
    
    

    