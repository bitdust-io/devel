#!/usr/bin/python
#service_fire_hire.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_fire_hire

"""

from services.local_service import LocalService

def create_service():
    return FireHireService()
    
class FireHireService(LocalService):
    
    service_name = 'service_fire_hire'
    config_path = 'services/fire-hire/enabled'
    
    def dependent_on(self):
        return ['service_customer',
                ]
    
    def start(self):
        from p2p import fire_hire
        from lib.config import conf
        fire_hire.A('init')
        conf().addCallback('services/customer/suppliers-number', 
            self._on_suppliers_number_modified)
        conf().addCallback('services/customer/needed-space', 
            self._on_needed_space_modified)
        return True
    
    def stop(self):
        from p2p import fire_hire
        from lib.config import conf
        conf().removeCallback('services/customer/suppliers-number')
        conf().removeCallback('services/customer/needed-space') 
        fire_hire.Destroy()
        return True
    
    def _on_suppliers_number_modified(self, path, value, oldvalue, result):
        from p2p import fire_hire
        fire_hire.ClearLastFireTime()
        fire_hire.A('restart')
        
    def _on_needed_space_modified(self, path, value, oldvalue, result):
        from p2p import fire_hire
        fire_hire.ClearLastFireTime()
        fire_hire.A('restart')


    