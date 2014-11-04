#!/usr/bin/python
#service_rebuilding.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_rebuilding

"""

from services.local_service import LocalService

def create_service():
    return RebuildingService()
    
class RebuildingService(LocalService):
    
    service_name = 'service_rebuilding'
    
    def dependent_on(self):
        return ['service_data_sender',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    