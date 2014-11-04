#!/usr/bin/python
#service_supplier.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_supplier

"""

from services.local_service import LocalService

def create_service():
    return SupplierService()
    
class SupplierService(LocalService):
    
    service_name = 'service_supplier'
    
    def dependent_on(self):
        return ['service_gateway',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    