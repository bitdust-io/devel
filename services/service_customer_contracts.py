#!/usr/bin/python
# service_customer_contracts.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (service_customer_contracts.py) is part of BitDust Software.
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

module:: service_customer_contracts
"""

from services.local_service import LocalService


def create_service():
    return CustomerContractsService()


class CustomerContractsService(LocalService):

    service_name = 'service_customer_contracts'
    config_path = 'services/customer-contracts/enabled'

    def dependent_on(self):
        return ['service_customer',
                'service_contract_chain',
                ]

    def start(self):
        from contacts import contactsdb
        from coins import customer_contract_executor
        for supplier_idurl in contactsdb.suppliers():
            customer_contract_executor.init_contract(supplier_idurl)
        from main import events
        events.add_subscriber(self._on_supplier_modified, 'supplier-modified')
        return True

    def stop(self):
        from main import events
        events.remove_subscriber(self._on_supplier_modified)
        from coins import customer_contract_executor
        for supplier_idurl in list(customer_contract_executor.all_contracts.keys()):
            customer_contract_executor.shutdown_contract(supplier_idurl)
        return True

    def _on_supplier_modified(self, evt):
        from coins import customer_contract_executor
        if evt.data['old_idurl']:
            customer_contract_executor.recheck_contract(evt.data['old_idurl'])
        if evt.data['new_idurl']:
            customer_contract_executor.recheck_contract(evt.data['new_idurl'])
