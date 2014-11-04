#!/usr/bin/python
#service_customers_rejector.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_customers_rejector

"""

from services.local_service import LocalService

def create_service():
    return CustomersRejectorService()
    
class CustomersRejectorService(LocalService):
    
    service_name = 'service_customers_rejector'
    
    def dependent_on(self):
        return ['service_customer',
                ]
    
    def start(self):
        from p2p import customers_rejector
        customers_rejector.A('restart')
        return True
    
    def stop(self):
        from p2p import customers_rejector
        customers_rejector.Destroy()
        return True
    
    

    