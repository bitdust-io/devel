#!/usr/bin/python
# service_customer_family.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from bitdust.services.local_service import LocalService


def create_service():
    return CustomerFamilyService()


class CustomerFamilyService(LocalService):

    service_name = 'service_customer_family'
    config_path = 'services/customer-family/enabled'

    def dependent_on(self):
        return [
            'service_supplier',
            'service_entangled_dht',
        ]

    def start(self):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.main import events
        from bitdust.contacts import contactsdb
        from bitdust.userid import id_url
        from bitdust.supplier import family_member
        from bitdust.transport import callback
        from bitdust.userid import my_id
        callback.append_inbox_callback(self._on_inbox_packet_received)
        for customer_idurl in contactsdb.customers():
            if not customer_idurl:
                continue
            if not id_url.is_cached(customer_idurl):
                continue
            if customer_idurl == my_id.getIDURL():
                lg.warn('skipping my own identity')
                continue
            fm = family_member.by_customer_idurl(customer_idurl)
            if not fm:
                fm = family_member.create_family(customer_idurl)
            fm.automat('init')
            local_customer_meta_info = contactsdb.get_customer_meta_info(customer_idurl)
            reactor.callLater(  # @UndefinedVariable
                0,
                fm.automat,
                'family-join',
                {
                    'supplier_idurl': my_id.getIDURL().to_bin(),
                    'ecc_map': local_customer_meta_info.get('ecc_map'),
                    'position': local_customer_meta_info.get('position', -1),
                    'family_snapshot': id_url.to_bin_list(local_customer_meta_info.get('family_snapshot')),
                },
            )
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        events.add_subscriber(self._on_existing_customer_accepted, 'existing-customer-accepted')
        events.add_subscriber(self._on_new_customer_accepted, 'new-customer-accepted')
        events.add_subscriber(self._on_existing_customer_terminated, 'existing-customer-terminated')
        return True

    def stop(self):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.main import events
        from bitdust.supplier import family_member
        events.remove_subscriber(self._on_new_customer_accepted, 'new-customer-accepted')
        events.remove_subscriber(self._on_existing_customer_accepted, 'existing-customer-accepted')
        events.remove_subscriber(self._on_existing_customer_terminated, 'existing-customer-terminated')
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        for fm in family_member.families().values():
            reactor.callLater(0, fm.automat, 'shutdown')  # @UndefinedVariable
        return True

    def _on_new_customer_accepted(self, evt):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.userid import my_id
        from bitdust.userid import id_url
        from bitdust.supplier import family_member
        customer_idurl = evt.data['idurl']
        fm = family_member.by_customer_idurl(customer_idurl)
        if not fm:
            fm = family_member.create_family(customer_idurl)
            fm.automat('init')
        else:
            lg.warn('family_member() instance already exists, but new customer just accepted %s' % customer_idurl)
        reactor.callLater(  # @UndefinedVariable
            0,
            fm.automat,
            'family-join',
            {
                'supplier_idurl': my_id.getIDURL().to_bin(),
                'ecc_map': evt.data.get('ecc_map'),
                'position': evt.data.get('position', -1),
                'family_snapshot': id_url.to_bin_list(evt.data.get('family_snapshot')),
            },
        )

    def _on_existing_customer_accepted(self, evt):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.supplier import family_member
        from bitdust.userid import id_url
        from bitdust.userid import my_id
        customer_idurl = evt.data['idurl']
        if customer_idurl == my_id.getIDURL():
            lg.warn('skipping my own identity')
            return
        if evt.data.get('position') is None:
            lg.warn('position of supplier in the family is still unclear')
            return
        fm = family_member.by_customer_idurl(customer_idurl)
        if not fm:
            lg.err('family_member() instance was not found for existing customer %s' % customer_idurl)
            return
        reactor.callLater(  # @UndefinedVariable
            0,
            fm.automat,
            'family-join',
            {
                'supplier_idurl': my_id.getIDURL().to_bin(),
                'ecc_map': evt.data.get('ecc_map'),
                'position': evt.data.get('position'),
                'family_snapshot': id_url.to_bin_list(evt.data.get('family_snapshot')),
            },
        )

    def _on_existing_customer_terminated(self, evt):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.supplier import family_member
        from bitdust.userid import my_id
        customer_idurl = evt.data['idurl']
        if customer_idurl == my_id.getIDURL():
            lg.warn('skipping my own identity')
            return
        fm = family_member.by_customer_idurl(customer_idurl)
        if not fm:
            lg.err('family_member() instance not found for existing customer %s' % customer_idurl)
            return
        reactor.callLater(  # @UndefinedVariable
            0,
            fm.automat,
            'family-leave',
            {
                'supplier_idurl': my_id.getIDURL().to_bin(),
                'ecc_map': evt.data.get('ecc_map'),
            },
        )

    def _on_incoming_contacts_packet(self, newpacket, info):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.lib import serialization
        from bitdust.lib import strng
        from bitdust.supplier import family_member
        from bitdust.userid import my_id
        from bitdust.userid import id_url
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
                customer_idurl = id_url.field(json_payload['customer_idurl'])
                ecc_map = strng.to_text(json_payload['customer_ecc_map'])
                suppliers_list = id_url.fields_list(json_payload['suppliers_list'])
                transaction_revision = json_payload.get('transaction_revision')
            except:
                lg.exc()
                return False
            if customer_idurl.to_bin() == my_id.getIDURL().to_bin():
                lg.warn('received contacts for my own customer family')
                return False
            if not id_url.is_cached(customer_idurl):
                lg.warn('received contacts from unknown user: %r' % customer_idurl)
                return False
            fm = family_member.by_customer_idurl(customer_idurl)
            if not fm:
                lg.warn('family_member() instance not found for incoming %s from %s for customer %r' % (newpacket, info, customer_idurl))
                return False
            reactor.callLater(  # @UndefinedVariable
                0,
                fm.automat,
                'contacts-received',
                {
                    'type': contacts_type,
                    'packet': newpacket,
                    'customer_idurl': customer_idurl,
                    'customer_ecc_map': ecc_map,
                    'suppliers_list': suppliers_list,
                    'transaction_revision': transaction_revision,
                },
            )
            return True

        elif contacts_type == 'supplier_position':
            try:
                customer_idurl = id_url.field(json_payload['customer_idurl'])
                ecc_map = strng.to_text(json_payload['customer_ecc_map'])
                supplier_idurl = id_url.field(json_payload['supplier_idurl'])
                supplier_position = json_payload['supplier_position']
                family_snapshot = id_url.to_bin_list(json_payload.get('family_snapshot'))
            except:
                lg.exc()
                return False
            if customer_idurl.to_bin() == my_id.getIDURL().to_bin():
                lg.warn('received contacts for my own customer family')
                return False
            fm = family_member.by_customer_idurl(customer_idurl)
            if not fm:
                lg.warn('family_member() instance not found for incoming %s from %s for customer %r' % (newpacket, info, customer_idurl))
                return False
            reactor.callLater(  # @UndefinedVariable
                0,
                fm.automat,
                'contacts-received',
                {
                    'type': contacts_type,
                    'packet': newpacket,
                    'customer_idurl': customer_idurl,
                    'customer_ecc_map': ecc_map,
                    'supplier_idurl': supplier_idurl,
                    'supplier_position': supplier_position,
                    'family_snapshot': family_snapshot,
                },
            )
            return True

        return False

    def _on_inbox_packet_received(self, newpacket, info, *args):
        from bitdust.p2p import commands
        if newpacket.Command == commands.Contacts():
            return self._on_incoming_contacts_packet(newpacket, info)
        return False

    def _on_identity_url_changed(self, evt):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.userid import id_url
        from bitdust.supplier import family_member
        for customer_idurl, fm in family_member.families().items():
            if customer_idurl == id_url.field(evt.data['old_idurl']):
                customer_idurl.refresh(replace_original=True)
                fm.customer_idurl.refresh(replace_original=True)
                lg.info('found %r for customer with rotated identity and refreshed: %r' % (fm, customer_idurl))
                reactor.callLater(0, fm.automat, 'family-refresh')  # @UndefinedVariable
