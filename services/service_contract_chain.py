#!/usr/bin/python
# service_contract_chain.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return ContractChainService()


class ContractChainService(LocalService):

    service_name = 'service_contract_chain'
    config_path = 'services/contract-chain/enabled'

    def dependent_on(self):
        return [
            'service_nodes_lookup',
        ]

    def installed(self):
        # TODO: to be continue...
        return False

    def start(self):
        from twisted.internet.defer import Deferred
        from coins import contract_chain_consumer
        self.starting_deferred = Deferred()
        contract_chain_consumer.A('init')
        contract_chain_consumer.A().addStateChangedCallback(self._on_contract_chain_state_changed)
        contract_chain_consumer.A('start')
        return self.starting_deferred

    def stop(self):
        from coins import contract_chain_consumer
        contract_chain_consumer.A().removeStateChangedCallback(self._on_contract_chain_state_changed)
        contract_chain_consumer.A('stop')
        contract_chain_consumer.A('shutdown')
        return True

    def health_check(self):
        from coins import contract_chain_consumer
        return contract_chain_consumer.A().state in ['CONNECTED', ]

    def _on_contract_chain_state_changed(self, oldstate, newstate, event_string, *args, **kwargs):
        if self.starting_deferred:
            if newstate in ['CONNECTED', 'DISCONNECTED', ] and oldstate not in ['AT_STARTUP', ]:
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
