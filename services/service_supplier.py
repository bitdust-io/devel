#!/usr/bin/python
# service_supplier.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (service_supplier.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#

"""
..

module:: service_supplier
"""

from twisted.internet import reactor

#------------------------------------------------------------------------------

from logs import lg

from services.local_service import LocalService

from contacts import contactsdb

from storage import accounting

#------------------------------------------------------------------------------


def create_service():
    return SupplierService()


class SupplierService(LocalService):

    service_name = 'service_supplier'
    config_path = 'services/supplier/enabled'

    def dependent_on(self):
        return ['service_p2p_hookups',
                ]

    def installed(self):
        from userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def start(self):
        return True

    def stop(self):
        return True

    def request(self, request, info):
        from main import events
        from p2p import p2p_service
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
        if accounting.check_create_customers_quotas():
            lg.out(6, 'service_supplier.request created a new space file')
        space_dict = accounting.read_customers_quotas()
        try:
            free_bytes = int(space_dict['free'])
        except:
            lg.exc()
            return p2p_service.SendFail(request, 'broken space file')
        if (request.OwnerID not in current_customers and request.OwnerID in space_dict.keys()):
            lg.warn("broken space file")
            return p2p_service.SendFail(request, 'broken space file')
        if (request.OwnerID in current_customers and request.OwnerID not in space_dict.keys()):
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
            accounting.write_customers_quotas(space_dict)
            reactor.callLater(0, local_tester.TestUpdateCustomers)
            if new_customer:
                lg.out(8, "    NEW CUSTOMER: DENIED !!!!!!!!!!!    not enough space available")
                events.send('new-customer-denied', dict(idurl=request.OwnerID))
            else:
                lg.out(8, "    OLD CUSTOMER: DENIED !!!!!!!!!!!    not enough space available")
                events.send('existing-customer-denied', dict(idurl=request.OwnerID))
            return p2p_service.SendAck(request, 'deny')
        space_dict['free'] = free_bytes - bytes_for_customer
        current_customers.append(request.OwnerID)
        space_dict[request.OwnerID] = bytes_for_customer
        contactsdb.update_customers(current_customers)
        contactsdb.save_customers()
        accounting.write_customers_quotas(space_dict)
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        if new_customer:
            lg.out(8, "    NEW CUSTOMER: ACCEPTED !!!!!!!!!!!!!!")
            events.send('new-customer-accepted', dict(idurl=request.OwnerID))
        else:
            lg.out(8, "    OLD CUSTOMER: ACCEPTED !!!!!!!!!!!!!!")
            events.send('existing-customer-accepted', dict(idurl=request.OwnerID))
        return p2p_service.SendAck(request, 'accepted')

    def cancel(self, request, info):
        from main import events
        from p2p import p2p_service
        if not contactsdb.is_customer(request.OwnerID):
            lg.warn(
                "got packet from %s, but he is not a customer" %
                request.OwnerID)
            return p2p_service.SendFail(request, 'not a customer')
        if accounting.check_create_customers_quotas():
            lg.out(6, 'service_supplier.cancel created a new space file')
        space_dict = accounting.read_customers_quotas()
        if request.OwnerID not in space_dict.keys():
            lg.warn(
                "got packet from %s, but not found him in space dictionary" %
                request.OwnerID)
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
        accounting.write_customers_quotas(space_dict)
        from supplier import local_tester
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        lg.out(8, "    OLD CUSTOMER: TERMINATED !!!!!!!!!!!!!!")
        events.send('existing-customer-terminated', dict(idurl=request.OwnerID))
        return p2p_service.SendAck(request, 'accepted')
