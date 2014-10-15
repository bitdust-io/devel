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
        from transport import gateway
        gateway.init()
        gateway.start()
        
        # global _TransportsInitialization
        # _TransportsInitialization = gateway.init()
    
    def stop(self):
        pass
    
    

    