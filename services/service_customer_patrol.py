#!/usr/bin/python
#service_customer_patrol.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_customer_patrol

"""

from services.local_service import LocalService

def create_service():
    return CustomerPatrolService()
    
class CustomerPatrolService(LocalService):
    
    service_name = 'service_customer_patrol'
    config_path = 'services/customer-patrol/enabled'
    
    def dependent_on(self):
        return ['service_supplier',
                ]
    
    def start(self):
        from supplier import customers_rejector
        from main.config import conf
        from supplier import local_tester
        customers_rejector.A('restart')
        conf().addCallback('services/supplier/donated-space',
            self._on_donated_space_modified)
        local_tester.init()
        return True
    
    def stop(self):
        from supplier import customers_rejector
        from main.config import conf
        from supplier import local_tester
        local_tester.shutdown()
        conf().removeCallback('services/supplier/donated-space')
        customers_rejector.Destroy()
        return True
    
    def _on_donated_space_modified(self, path, value, oldvalue, result):
        from supplier import customers_rejector
        customers_rejector.A('restart')

    