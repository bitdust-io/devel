#!/usr/bin/python
# service_customer.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return CustomerService()


class CustomerService(LocalService):

    service_name = 'service_customer'
    config_path = 'services/customer/enabled'

    def dependent_on(self):
        return [
            'service_keys_registry',
        ]

    def installed(self):
        from userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def start(self):
        from contacts import contactsdb
        from customer import supplier_connector
        from userid import my_id
        from main import events
        for _, supplier_idurl in enumerate(contactsdb.suppliers()):
            if supplier_idurl and not supplier_connector.by_idurl(supplier_idurl, customer_idurl=my_id.getLocalID()):
                supplier_connector.create(
                    supplier_idurl=supplier_idurl,
                    customer_idurl=my_id.getLocalID(),
                )
        events.add_subscriber(self._on_my_keys_synchronized, 'my-keys-synchronized')
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        # TODO: read from dht and connect to other suppliers - from other customers who shared data to me
        return True

    def stop(self):
        from customer import supplier_connector
        from userid import my_id
        from main import events
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        events.remove_subscriber(self._on_my_keys_synchronized, 'my-keys-synchronized')
        for sc in supplier_connector.connectors(my_id.getLocalID()).values():
            sc.automat('shutdown')
        # TODO: disconnect other suppliers
        return True

    def health_check(self):
        from customer import supplier_connector
        from userid import my_id
        for sc in supplier_connector.connectors(my_id.getLocalID()).values():
            # at least one supplier must be online to consider my customer service to be healthy
            if sc.state in ['CONNECTED', ]:
                return True
        return False

    def _on_my_keys_synchronized(self, evt):
        from logs import lg
        from main import settings
        from storage import keys_synchronizer
        from crypt import my_keys
        from userid import my_id
        customer_key_id = my_id.getGlobalID(key_alias='customer')
        if not my_keys.is_key_registered(customer_key_id) and keys_synchronizer.is_synchronized():
            lg.info('customer key was not found but we know that all keys are in sync, generate new key: %s' % customer_key_id)
            my_keys.generate_key(customer_key_id, key_size=settings.getPrivateKeySize())

    def _on_identity_url_changed(self, evt):
        from logs import lg
        from userid import id_url
        from contacts import contactsdb
        from customer import supplier_connector
        old_idurl = id_url.field(evt.data['old_idurl'])
        for customer_idurl, suppliers_list in contactsdb.all_suppliers(as_dict=True).items():
            if old_idurl == customer_idurl:
                customer_idurl.refresh()
                lg.info('found customer idurl rotated : %r -> %r' % (
                    evt.data['old_idurl'], evt.data['new_idurl'], ))
            for supplier_pos, supplier_idurl in enumerate(suppliers_list):
                if old_idurl == supplier_idurl:
                    supplier_idurl.refresh()
                    lg.info('found supplier idurl rotated for customer %r at position %r : %r -> %r' % (
                        customer_idurl, supplier_pos, evt.data['old_idurl'], evt.data['new_idurl'], ))
            for customer_idurl, sc_dict in supplier_connector.connectors(as_dict=True).items():
                if old_idurl == customer_idurl:
                    customer_idurl.refresh()
                    lg.info('found customer idurl rotated in supplier_connector.connectors() : %r -> %r' % (
                        evt.data['old_idurl'], evt.data['new_idurl'], ))
                for supplier_idurl, sc in sc_dict.items():
                    if old_idurl == supplier_idurl:
                        supplier_idurl.refresh()
                        sc.customer_idurl.refresh()
                        sc.supplier_idurl.refresh()
                        lg.info('found supplier idurl rotated in %r for customer %r : %r -> %r' % (
                            sc, customer_idurl, evt.data['old_idurl'], evt.data['new_idurl'], ))
