#!/usr/bin/python
# service_supplier_contracts.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from bitdust.services.local_service import LocalService


def create_service():
    return SupplierContractsService()


class SupplierContractsService(LocalService):

    service_name = 'service_supplier_contracts'
    config_path = 'services/supplier-contracts/enabled'

    def dependent_on(self):
        return [
            'service_supplier',
            'service_blockchain_id',
        ]

    def start(self):
        from bitdust.main import events
        from bitdust.supplier import storage_contract
        events.add_subscriber(self.on_blockchain_transaction_received, 'blockchain-transaction-received')
        storage_contract.scan_recent_storage_transactions()
        return True

    def stop(self):
        from bitdust.main import events
        events.remove_subscriber(self.on_blockchain_transaction_received, 'blockchain-transaction-received')
        return True

    def on_blockchain_transaction_received(self, evt):
        if evt.data.get('operation') == 'storage':
            from bitdust.supplier import storage_contract
            storage_contract.verify_accept_storage_payment(evt.data)
