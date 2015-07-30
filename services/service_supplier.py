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

import os

from twisted.internet import reactor

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio

from main import settings

from services.local_service import LocalService

from p2p import p2p_service

from contacts import contactsdb

#------------------------------------------------------------------------------ 

def create_service():
    return SupplierService()
    
class SupplierService(LocalService):
    
    service_name = 'service_supplier'
    config_path = 'services/supplier/enabled'
    
    def dependent_on(self):
        return ['service_gateway',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    def request(self, request):
        words = request.Payload.split(' ')
        try:
            bytes_for_customer = int(words[1])
        except:
            lg.exc()
            bytes_for_customer = None
        if not bytes_for_customer or bytes_for_customer < 0:
            lg.warn("wrong storage value : %s" % request.Payload)
            return p2p_service.SendFail(request, 'wrong storage value')
        current_customers = contactsdb.customers()
        donated_bytes = settings.getDonatedBytes()
        if not os.path.isfile(settings.CustomersSpaceFile()):
            bpio._write_dict(settings.CustomersSpaceFile(), {'free': donated_bytes})
            lg.out(6, 'p2p_service.RequestService created a new space file')
        space_dict = bpio._read_dict(settings.CustomersSpaceFile())
        try:
            free_bytes = int(space_dict['free'])
        except:
            lg.exc()
            return p2p_service.SendFail(request, 'broken space file')
        if ( request.OwnerID not in current_customers and request.OwnerID in space_dict.keys() ):
            lg.warn("broken space file")
            return p2p_service.SendFail(request, 'broken space file')
        if ( request.OwnerID in current_customers and request.OwnerID not in space_dict.keys() ):
            lg.warn("broken customers file")
            return p2p_service.SendFail(request, 'broken customers file')
        if request.OwnerID in current_customers:
            free_bytes += int(space_dict[request.OwnerID])
            space_dict['free'] = free_bytes
            current_customers.remove(request.OwnerID)  
            space_dict.pop(request.OwnerID)
            new_customer = False
        else:
            new_customer = True
        from supplier import local_tester
        if free_bytes <= bytes_for_customer:
            contactsdb.update_customers(current_customers)
            contactsdb.save_customers()
            bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
            reactor.callLater(0, local_tester.TestUpdateCustomers)
            if new_customer:
                lg.out(8, "    NEW CUSTOMER - DENIED !!!!!!!!!!!    not enough space")
            else:
                lg.out(8, "    OLD CUSTOMER - DENIED !!!!!!!!!!!    not enough space")
            return p2p_service.SendAck(request, 'deny')
        space_dict['free'] = free_bytes - bytes_for_customer
        current_customers.append(request.OwnerID)  
        space_dict[request.OwnerID] = bytes_for_customer
        contactsdb.update_customers(current_customers)
        contactsdb.save_customers()
        bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        if new_customer:
            lg.out(8, "    NEW CUSTOMER ACCEPTED !!!!!!!!!!!!!!")
        else:
            lg.out(8, "    OLD CUSTOMER ACCEPTED !!!!!!!!!!!!!!")
        return p2p_service.SendAck(request, 'accepted')
    
    def cancel(self, request):
        if not contactsdb.is_customer(request.OwnerID):
            lg.warn("got packet from %s, but he is not a customer" % request.OwnerID)
            return p2p_service.SendFail(request, 'not a customer')
        donated_bytes = settings.getDonatedBytes()
        if not os.path.isfile(settings.CustomersSpaceFile()):
            bpio._write_dict(settings.CustomersSpaceFile(), {'free': donated_bytes})
            lg.out(6, 'p2p_service.CancelService created a new space file')
        space_dict = bpio._read_dict(settings.CustomersSpaceFile())
        if request.OwnerID not in space_dict.keys():
            lg.warn("got packet from %s, but not found him in space dictionary" % request.OwnerID)
            return p2p_service.SendFail(request, 'not a customer')
        try:
            free_bytes = int(space_dict['free'])
            space_dict['free'] = free_bytes + int(space_dict[request.OwnerID])
        except:
            lg.exc()
            return p2p_service.SendFail(request, 'broken space file')
        new_customers = list(contactsdb.customers())
        new_customers.remove(request.OwnerID)
        contactsdb.update_customers(new_customers)
        contactsdb.save_customers()
        space_dict.pop(request.OwnerID)
        bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
        from supplier import local_tester
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        return p2p_service.SendAck(request, 'accepted')

    