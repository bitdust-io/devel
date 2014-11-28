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
        from customer import supplier_connector
        from contacts import contactsdb 
        for supplier_idurl in contactsdb.suppliers():
            if supplier_idurl:
                sc = supplier_connector.by_idurl(supplier_idurl)
                if sc is None:
                    sc = supplier_connector.create(supplier_idurl)
        return True
    
    def stop(self):
        from customer import supplier_connector
        for sc in supplier_connector.connectors().values():
            sc.automat('shutdown')
        return True
    

    