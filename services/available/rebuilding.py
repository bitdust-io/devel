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
        return ['data_sender',
                ]
    
    def start(self):
        from p2p import data_sender
        data_sender.A('init')
        return True
    
    def stop(self):
        return True
    
    

    