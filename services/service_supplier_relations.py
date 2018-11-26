#!/usr/bin/python
# service_supplier_relations.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import
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

    def installed(self):
        return False

    def start(self):
        from twisted.internet.task import LoopingCall  #@UnresolvedImport
        from main import events
        from dht import dht_service
        events.add_subscriber(self._on_new_customer_accepted, 'new-customer-accepted')
        events.add_subscriber(self._on_existing_customer_accepted, 'existing-customer-accepted')
        events.add_subscriber(self._on_existing_customer_terminated, 'existing-customer-terminated')
        self.refresh_task = LoopingCall(self._do_refresh_dht_records)
        self.refresh_task.start(dht_service.KEY_EXPIRE_MIN_SECONDS * 2, now=False)
        return True

    def stop(self):
        from main import events
        self.refresh_task.stop()
        events.remove_subscriber(self._on_new_customer_accepted)
        events.remove_subscriber(self._on_existing_customer_accepted)
        events.remove_subscriber(self._on_existing_customer_terminated)
        return True

    def cancel(self, json_payload, newpacket, info):
        from logs import lg
        from contacts import contactsdb
        from p2p import p2p_service
        customer_idurl = newpacket.OwnerID
        if not contactsdb.is_customer(customer_idurl):
            lg.warn("got packet from %s, but he is not a customer" % customer_idurl)
        from dht import dht_relations
        dht_relations.close_customer_supplier_relation(customer_idurl)
        return p2p_service.SendAck(newpacket, 'accepted')

    #------------------------------------------------------------------------------

    def _do_refresh_dht_records(self):
        from dht import dht_relations
        from contacts import contactsdb
        for customer_idurl in contactsdb.customers():
            dht_relations.publish_customer_supplier_relation(customer_idurl)

    def _on_new_customer_accepted(self, evt):
        from twisted.internet import reactor  # @UnresolvedImport
        from dht import dht_relations
        if evt.data.get('allocated_bytes', 0) > 0:
            reactor.callLater(0, dht_relations.publish_customer_supplier_relation, evt.data['idurl'])

    def _on_existing_customer_accepted(self, evt):
        from twisted.internet import reactor  # @UnresolvedImport
        from dht import dht_relations
        if evt.data.get('allocated_bytes', 0) > 0:
            reactor.callLater(0, dht_relations.publish_customer_supplier_relation, evt.data['idurl'])

    def _on_existing_customer_terminated(self, evt):
        from twisted.internet import reactor  # @UnresolvedImport
        from dht import dht_relations
        reactor.callLater(0, dht_relations.close_customer_supplier_relation, evt.data['idurl'])
