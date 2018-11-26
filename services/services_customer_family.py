#!/usr/bin/python
# service_customer_family.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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
    config_path = 'services/supplier-customer-family/enabled'

    def dependent_on(self):
        return ['service_supplier',
                'service_entangled_dht',
                ]

    def start(self):
        from main import events
        from contacts import contactsdb
        from supplier import family_member
        for customer_idurl in contactsdb.customers():
            if customer_idurl and not family_member.by_idurl(customer_idurl):
                fm = family_member.create(customer_idurl)
                fm.automat('init')
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
        for fm in family_member.families():
            fm.automat('shutdown')
        return True

    def _on_new_customer_accepted(self, evt):
        from logs import lg
        from supplier import family_member
        customer_idurl = evt.data['idurl']
        fm = family_member.by_idurl(customer_idurl)
        if not fm:
            fm = family_member.create(customer_idurl)
            fm.automat('init')
        else:
            lg.warn('FamilyMember already exists, but new customer just accepted %s' % customer_idurl)
        fm.automat('customer-accepted', customer_idurl)

    def _on_existing_customer_accepted(self, evt):
        from logs import lg
        from supplier import family_member
        customer_idurl = evt.data['idurl']
        fm = family_member.by_idurl(customer_idurl)
        if not fm:
            lg.err('FamilyMember was not found for existing customer %s' % customer_idurl)
            return
        fm.automat('customer-accepted', customer_idurl)

    def _on_existing_customer_terminated(self, evt):
        from logs import lg
        from supplier import family_member
        customer_idurl = evt.data['idurl']
        fm = family_member.by_idurl(customer_idurl)
        if not fm:
            lg.err('FamilyMember not found for existing customer %s' % customer_idurl)
            return
        fm.automat('customer-rejected', customer_idurl)
