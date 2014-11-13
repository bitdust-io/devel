#!/usr/bin/python
#service_customer.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_customer

"""

from services.local_service import LocalService

def create_service():
    return CustomerService()
    
class CustomerService(LocalService):
    
    service_name = 'service_customer'
    config_path = 'services/customer/enabled'
    
    def dependent_on(self):
        return ['service_p2p_hookups',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    