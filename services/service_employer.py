#!/usr/bin/python
#service_employer.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_employer

"""

from services.local_service import LocalService

def create_service():
    return EmployerService()
    
class EmployerService(LocalService):
    
    service_name = 'service_employer'
    config_path = 'services/employer/enabled'
    
    def dependent_on(self):
        return ['service_customer',
                ]
    
    def start(self):
        from customer import fire_hire
        from main.config import conf
        fire_hire.A('init')
        conf().addCallback('services/customer/suppliers-number', 
            self._on_suppliers_number_modified)
        conf().addCallback('services/customer/needed-space', 
            self._on_needed_space_modified)
        return True
    
    def stop(self):
        from customer import fire_hire
        from main.config import conf
        conf().removeCallback('services/customer/suppliers-number')
        conf().removeCallback('services/customer/needed-space') 
        fire_hire.Destroy()
        return True
    
    def _on_suppliers_number_modified(self, path, value, oldvalue, result):
        from customer import fire_hire
        fire_hire.ClearLastFireTime()
        fire_hire.A('restart')
        
    def _on_needed_space_modified(self, path, value, oldvalue, result):
        from customer import fire_hire
        fire_hire.ClearLastFireTime()
        fire_hire.A('restart')


    