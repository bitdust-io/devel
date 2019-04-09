#!/usr/bin/python
# service_customer_family.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_customer_family.py) is part of BitDust Software.
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

module:: service_customer_family
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return SupplierRelationsService()


class SupplierRelationsService(LocalService):

    service_name = 'service_customer_family'
    config_path = 'services/customer-family/enabled'

    def dependent_on(self):
        return [
            'service_supplier',
            'service_entangled_dht',
        ]

    def start(self):
        from logs import lg
        from main import events
        from contacts import contactsdb
        from supplier import family_member
        from transport import callback
        # TODO: check all imports.! my_id must be loaded latest as possible!
        from userid import my_id
        
        callback.append_inbox_callback(self._on_inbox_packet_received)
        
        for customer_idurl in contactsdb.customers():
            if not customer_idurl:
                continue
            if customer_idurl == my_id.getLocalIDURL():
                lg.warn('skipping my own identity')
                continue
            fm = family_member.by_customer_idurl(customer_idurl)
            if not fm:
                fm = family_member.create_family(customer_idurl)
            fm.automat('init')
            local_customer_meta_info = contactsdb.get_customer_meta_info(customer_idurl)
            fm.automat('family-join', {
                'supplier_idurl': my_id.getLocalIDURL(),
                'ecc_map': local_customer_meta_info.get('ecc_map'),
                'position': local_customer_meta_info.get('position', -1),
                'family_snapshot': local_customer_meta_info.get('family_snapshot'),
            })

        events.add_subscriber(self._on_existing_customer_accepted, 'existing-customer-accepted')
        events.add_subscriber(self._on_new_customer_accepted, 'new-customer-accepted')
        events.add_subscriber(self._on_existing_customer_terminated, 'existing-customer-terminated')
        return True

    def stop(self):
        from main import events
        from supplier import family_member
        events.remove_subscriber(self._on_new_customer_accepted)
        events.remove_subscriber(self._on_existing_customer_accepted)
        events.remove_subscriber(self._on_existing_customer_terminated)
        for fm in family_member.families().values():
            fm.automat('shutdown')
        return True

    def _on_new_customer_accepted(self, evt):
        from logs import lg
        from userid import my_id
        from supplier import family_member
        customer_idurl = evt.data['idurl']
        fm = family_member.by_customer_idurl(customer_idurl)
        if not fm:
            fm = family_member.create_family(customer_idurl)
            fm.automat('init')
        else:
            lg.warn('family_member() instance already exists, but new customer just accepted %s' % customer_idurl)
        fm.automat('family-join', {
            'supplier_idurl': my_id.getLocalIDURL(),
            'ecc_map': evt.data.get('ecc_map'),
            'position': evt.data.get('position', -1),
            'family_snapshot': evt.data.get('family_snapshot'),
        })

    def _on_existing_customer_accepted(self, evt):
        from logs import lg
        from supplier import family_member
        from userid import my_id
        customer_idurl = evt.data['idurl']
        if customer_idurl == my_id.getLocalIDURL():
            lg.warn('skipping my own identity')
            return
        if evt.data.get('position') is None:
            lg.warn('position of supplier in the family is still unclear')
            return
        fm = family_member.by_customer_idurl(customer_idurl)
        if not fm:
            lg.err('family_member() instance was not found for existing customer %s' % customer_idurl)
            return
        fm.automat('family-join', {
            'supplier_idurl': my_id.getLocalIDURL(),
            'ecc_map': evt.data.get('ecc_map'),
            'position': evt.data.get('position'),
            'family_snapshot': evt.data.get('family_snapshot'),
        })

    def _on_existing_customer_terminated(self, evt):
        from logs import lg
        from supplier import family_member
        from userid import my_id
        customer_idurl = evt.data['idurl']
        if customer_idurl == my_id.getLocalIDURL():
            lg.warn('skipping my own identity')
            return
        fm = family_member.by_customer_idurl(customer_idurl)
        if not fm:
            lg.err('family_member() instance not found for existing customer %s' % customer_idurl)
            return
        fm.automat('family-leave', {
            'supplier_idurl': my_id.getLocalIDURL(),
        })

    def _on_incoming_contacts_packet(self, newpacket, info):
        from logs import lg
        from lib import serialization
        from lib import strng
        from supplier import family_member
        from userid import my_id
        try:
            json_payload = serialization.BytesToDict(newpacket.Payload, keys_to_text=True)
            contacts_type = strng.to_text(json_payload['type'])
            contacts_space = strng.to_text(json_payload['space'])
        except:
            lg.exc()
            return False

        if contacts_space != 'family_member':
            return False

        if contacts_type == 'suppliers_list':
            try:
                customer_idurl = strng.to_bin(json_payload['customer_idurl'])
                ecc_map = strng.to_text(json_payload['customer_ecc_map'])
                suppliers_list = list(map(strng.to_bin, json_payload['suppliers_list']))
                transaction_revision = json_payload.get('transaction_revision')
            except:
                lg.exc()
                return False
            if customer_idurl == my_id.getLocalIDURL():
                lg.warn('received contacts for my own customer family')
                return False
            fm = family_member.by_customer_idurl(customer_idurl)
            if not fm:
                lg.warn('family_member() instance not found for incoming %s from %s for customer %r' % (
                    newpacket, info, customer_idurl, ))
                return False
            fm.automat('contacts-received', {
                'type': contacts_type,
                'packet': newpacket,
                'customer_idurl': customer_idurl,
                'customer_ecc_map': ecc_map,
                'suppliers_list': suppliers_list,
                'transaction_revision': transaction_revision,
            })
            return True

        elif contacts_type == 'supplier_position':
            try:
                customer_idurl = strng.to_bin(json_payload['customer_idurl'])
                ecc_map = strng.to_text(json_payload['customer_ecc_map'])
                supplier_idurl = strng.to_bin(json_payload['supplier_idurl'])
                supplier_position = json_payload['supplier_position']
                family_snapshot = json_payload.get('family_snapshot')
            except:
                lg.exc()
                return False
            if customer_idurl == my_id.getLocalIDURL():
                lg.warn('received contacts for my own customer family')
                return False
            fm = family_member.by_customer_idurl(customer_idurl)
            if not fm:
                lg.warn('family_member() instance not found for incoming %s from %s for customer %r' % (
                    newpacket, info, customer_idurl, ))
                return False
            fm.automat('contacts-received', {
                'type': contacts_type,
                'packet': newpacket,
                'customer_idurl': customer_idurl,
                'customer_ecc_map': ecc_map,
                'supplier_idurl': supplier_idurl,
                'supplier_position': supplier_position,
                'family_snapshot': family_snapshot,
            })
            return True

        return False

    def _on_inbox_packet_received(self, newpacket, info, *args):
        from p2p import commands
        if newpacket.Command == commands.Contacts():
            return self._on_incoming_contacts_packet(newpacket, info)
        return False
