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
    
    name = 'customers_rejector'
    
    def dependent_on(self):
        return []
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    