#!/usr/bin/python
# service_employer.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_employer.py) is part of BitDust Software.
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

module:: service_employer
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return EmployerService()


class EmployerService(LocalService):

    service_name = 'service_employer'
    config_path = 'services/employer/enabled'

    def dependent_on(self):
        return [
            'service_customer',
            'service_nodes_lookup',
        ]

    def start(self):
        from customer import fire_hire
        from main.config import conf
        from main import events
        from raid import eccmap
        eccmap.Update()
        fire_hire.A('init')
        conf().addCallback('services/customer/suppliers-number',
                           self._on_suppliers_number_modified)
        conf().addCallback('services/customer/needed-space',
                           self._on_needed_space_modified)
        events.add_subscriber(self._on_supplier_modified,
                              'supplier-modified')
        self._do_cleanup_dht_suppliers()
        return True

    def stop(self):
        from customer import fire_hire
        from main.config import conf
        from main import events
        events.remove_subscriber(self._on_supplier_modified)
        conf().removeCallback('services/customer/suppliers-number')
        conf().removeCallback('services/customer/needed-space')
        fire_hire.Destroy()
        return True

    def health_check(self):
        from contacts import contactsdb
        from raid import eccmap
        missed_suppliers = contactsdb.suppliers().count('')
        # critical amount of suppliers must be already in the family to have that service running
        return missed_suppliers <= eccmap.Current().CorrectableErrors

    def _do_cleanup_dht_suppliers(self):
        from logs import lg
        from services import driver
        if driver.is_on('service_entangled_dht'):
            from dht import dht_relations
            from userid import my_id
            d = dht_relations.read_customer_suppliers(my_id.getLocalID())
            d.addCallback(self._on_my_dht_relations_discovered)
            d.addErrback(self._on_my_dht_relations_failed)
        else:
            lg.warn('service service_entangled_dht is OFF')

    def _on_suppliers_number_modified(self, path, value, oldvalue, result):
        from customer import fire_hire
        from raid import eccmap
        eccmap.Update()
        fire_hire.ClearLastFireTime()
        fire_hire.A('restart')

    def _on_needed_space_modified(self, path, value, oldvalue, result):
        from customer import fire_hire
        fire_hire.ClearLastFireTime()
        fire_hire.A('restart')

    def _on_supplier_modified(self, evt):
        # if evt.data['new_idurl']:
        #     self._do_notify_supplier_position(evt.data['new_idurl'], evt.data['position'], )
        self._do_cleanup_dht_suppliers()

    def _on_my_dht_relations_discovered(self, dht_result):
        from p2p import p2p_service
        from contacts import contactsdb
        from userid import my_id
        from crypt import my_keys
        from logs import lg
        if not (dht_result and isinstance(dht_result, dict) and len(dht_result.get('suppliers', [])) > 0):
            lg.warn('no dht records found for my customer family')
            return
        suppliers_to_be_dismissed = set()
        # clean up old suppliers
        for idurl in dht_result['suppliers']:
            if not idurl:
                continue
            if not contactsdb.is_supplier(idurl):
                lg.warn('dht relation with %s is not valid anymore' % idurl)
                suppliers_to_be_dismissed.add(idurl)
        for supplier_idurl in suppliers_to_be_dismissed:
            service_info = {}
            my_customer_key_id = my_id.getGlobalID(key_alias='customer')
            if my_keys.is_key_registered(my_customer_key_id):
                service_info['customer_public_key'] = my_keys.get_key_info(
                    key_id=my_customer_key_id,
                    include_private=False,
                )
            p2p_service.SendCancelService(
                remote_idurl=supplier_idurl,
                service_name='service_supplier',
                json_payload=service_info,
            )
#             p2p_service.SendCancelService(
#                 remote_idurl=idurl,
#                 service_name='service_p2p_notifications',
#             )
        if suppliers_to_be_dismissed:
            lg.info('found %d suppliers to be cleaned and sent CancelService() packets' % len(suppliers_to_be_dismissed))

    def _on_my_dht_relations_failed(self, err):
        from logs import lg
        lg.err(err)

    def _do_notify_supplier_position(self, supplier_idurl, supplier_position):
        from p2p import p2p_service
        from raid import eccmap
        from userid import my_id
        p2p_service.SendContacts(
            remote_idurl=supplier_idurl,
            json_payload={
                'space': 'family_member',
                'type': 'supplier_position',
                'customer_idurl': my_id.getLocalIDURL(),
                'customer_ecc_map': eccmap.Current().name,
                'supplier_idurl': supplier_idurl,
                'supplier_position': supplier_position,
            },
        )
