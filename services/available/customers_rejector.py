#!/usr/bin/python
#customers_rejector.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: customers_rejector

"""

from services.local_service import LocalService

def create_service():
    return CustomersRejectorService()
    
class CustomersRejectorService(LocalService):
    
    service_name = 'customers_rejector'
    
    def dependent_on(self):
        return ['gateway',]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    