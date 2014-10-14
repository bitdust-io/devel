#!/usr/bin/python
#supplier.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: supplier

"""

from services.local_service import LocalService

def create_service():
    return SupplierService()
    
class SupplierService(LocalService):
    
    name = 'supplier'
    
    def dependent_on(self):
        return ['gateway',
                ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    