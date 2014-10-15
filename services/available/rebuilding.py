#!/usr/bin/python
#rebuilding.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: rebuilding

"""

from services.local_service import LocalService

def create_service():
    return RebuildingService()
    
class RebuildingService(LocalService):
    
    service_name = 'rebuilding'
    
    def dependent_on(self):
        return ['gateway',
                'customer',
                'data_sender',]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    