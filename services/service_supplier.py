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
    config_path = 'services/supplier/enabled'
    
    def dependent_on(self):
        return ['service_gateway',
                ]
    
    def start(self):
        from supplier import local_tester
        local_tester.init()
        return True
    
    def stop(self):
        from supplier import local_tester
        local_tester.shutdown()
        return True
    
    

    