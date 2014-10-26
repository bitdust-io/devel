#!/usr/bin/python
#fire_hire.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: fire_hire

"""

from services.local_service import LocalService

def create_service():
    return FireHireService()
    
class FireHireService(LocalService):
    
    service_name = 'fire_hire'
    
    def dependent_on(self):
        return ['gateway',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    