#!/usr/bin/python
# service_contract_chain.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (service_contract_chain.py) is part of BitDust Software.
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

module:: service_contract_chain
"""

from services.local_service import LocalService


def create_service():
    return SupplierContractsService()


class SupplierContractsService(LocalService):

    service_name = 'service_contract_chain'
    config_path = 'services/contract-chain/enabled'

    def dependent_on(self):
        return ['service_nodes_lookup',
                ]

    def start(self):
        from coins import contract_chain_consumer
        contract_chain_consumer.A('init')
        contract_chain_consumer.A('start')
        return True

    def stop(self):
        from coins import contract_chain_consumer
        contract_chain_consumer.A('stop')
        contract_chain_consumer.A('shutdown')
        return True
