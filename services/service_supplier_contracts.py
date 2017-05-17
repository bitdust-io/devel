#!/usr/bin/python
# service_supplier_contracts.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

from services.local_service import LocalService


def create_service():
    return SupplierContractsService()


class SupplierContractsService(LocalService):

    service_name = 'service_supplier_contracts'
    config_path = 'services/supplier-contracts/enabled'

    def dependent_on(self):
        return ['service_supplier',
                'service_nodes_lookup'
                ]

    def start(self):
        from main import events
        events.add_subscriber(self.on_new_customer_accepted, 'new-customer-accepted')
        from p2p import p2p_service_seeker
        p2p_service_seeker.connect_random_node('service_miner')
        return True

    def stop(self):
        return True

    def on_new_customer_accepted(self, e):
        pass

    def on_new_customer_denied(self, e):
        pass

    def on_existing_customer_denied(self, e):
        pass

    def on_existing_customer_accepted(self, e):
        pass



