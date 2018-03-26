#!/usr/bin/python
# service_customer.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (service_customer.py) is part of BitDust Software.
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

module:: service_customer
"""

from services.local_service import LocalService


def create_service():
    return CustomerService()


class CustomerService(LocalService):

    service_name = 'service_customer'
    config_path = 'services/customer/enabled'

    def dependent_on(self):
        return ['service_p2p_notifications',
                ]

    def installed(self):
        from userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def start(self):
        from contacts import contactsdb
        from crypt import my_keys
        from customer import supplier_connector
        from customer import customer_state
        from userid import my_id
        from logs import lg
        if not my_keys.is_key_registered(customer_state.customer_key_id()):
            lg.warn('customer key was not found, generate new key: %s' % customer_state.customer_key_id())
            my_keys.generate_key(customer_state.customer_key_id())
        for supplier_idurl in contactsdb.suppliers():
            if supplier_idurl and not supplier_connector.by_idurl(supplier_idurl, customer_idurl=my_id.getLocalID()):
                supplier_connector.create(supplier_idurl, customer_idurl=my_id.getLocalID())
        # TODO: read from dht and connect to other suppliers - from other customers who shared data to me
        return True

    def stop(self):
        from customer import supplier_connector
        from userid import my_id
        for sc in supplier_connector.connectors(my_id.getLocalID()).values():
            sc.automat('shutdown')
        # TODO: disconnect other suppliers
        return True
