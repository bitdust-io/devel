#!/usr/bin/python
# service_supplier_relations.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (service_supplier_relations.py) is part of BitDust Software.
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

module:: service_supplier_relations
"""

from services.local_service import LocalService


def create_service():
    return SupplierRelationsService()


class SupplierRelationsService(LocalService):

    service_name = 'service_supplier_relations'
    config_path = 'services/supplier-relations/enabled'

    def dependent_on(self):
        return ['service_supplier',
                'service_entangled_dht',
                ]

    def start(self):
        from dht import dht_relations
        from contacts import contactsdb
        from userid import my_id
        from main import events
        events.add_subscriber(self._on_new_customer_accepted, 'new-customer-accepted')
        events.add_subscriber(self._on_existing_customer_accepted, 'existing-customer-accepted')
        events.add_subscriber(self._on_existing_customer_terminated, 'existing-customer-terminated')
        for customer_idurl in contactsdb.customers():
            dht_relations.publish_customer_supplier_relation(customer_idurl)
        dht_relations.scan_customer_supplier_relations(my_id.getLocalID())
        return True

    def stop(self):
        from main import events
        events.remove_subscriber(self._on_new_customer_accepted)
        events.remove_subscriber(self._on_existing_customer_accepted)
        events.remove_subscriber(self._on_existing_customer_terminated)
        return True

    #------------------------------------------------------------------------------

    def _on_new_customer_accepted(self, evt):
        from twisted.internet import reactor
        from dht import dht_relations
        reactor.callLater(0, dht_relations.publish_customer_supplier_relation, evt.data['idurl'])

    def _on_existing_customer_accepted(self, evt):
        from twisted.internet import reactor
        from dht import dht_relations
        reactor.callLater(0, dht_relations.publish_customer_supplier_relation, evt.data['idurl'])

    def _on_existing_customer_terminated(self, evt):
        from twisted.internet import reactor
        from dht import dht_relations
        reactor.callLater(0, dht_relations.close_customer_supplier_relation, evt.data['idurl'])
