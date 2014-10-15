#!/usr/bin/python
#customer.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: customer

"""

from services.local_service import LocalService

def create_service():
    return CustomerService()
    
class CustomerService(LocalService):
    
    service_name = 'customer'
    
    def dependent_on(self):
        return []
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    