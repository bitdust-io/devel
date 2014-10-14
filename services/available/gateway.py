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
    
    name = 'gateway'
    
    def dependent_on(self):
        return ['network_connector',
                ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    