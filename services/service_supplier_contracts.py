#!/usr/bin/python
# service_supplier_contracts.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_supplier_contracts.py) is part of BitDust Software.
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

module:: service_supplier_contracts
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return SupplierContractsService()


class SupplierContractsService(LocalService):

    service_name = 'service_supplier_contracts'
    config_path = 'services/supplier-contracts/enabled'

    def dependent_on(self):
        return [
            'service_supplier',
            'service_contract_chain',
        ]

    def installed(self):
        # TODO: to be continue...
        return False

    def start(self):
        from main import events
        from contacts import contactsdb
        from coins import supplier_contract_executor
        for customer_idurl in contactsdb.customers():
            supplier_contract_executor.init_contract(customer_idurl)
        events.add_subscriber(self._on_customer_modified, 'customer-modified')
        return True

    def stop(self):
        from main import events
        from coins import supplier_contract_executor
        events.remove_subscriber(self._on_customer_modified)
        for customer_idurl in list(supplier_contract_executor.all_contracts.keys()):
            supplier_contract_executor.shutdown_contract(customer_idurl)
        return True

    def _on_customer_modified(self, evt):
        from coins import supplier_contract_executor
        if evt.data.get('idurl'):
            supplier_contract_executor.recheck_contract(evt.data['idurl'])
