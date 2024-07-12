#!/usr/bin/python
# service_blockchain_id.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_blockchain_id.py) is part of BitDust Software.
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

module:: service_blockchain_id
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return BlockchainIDService()


class BlockchainIDService(LocalService):

    service_name = 'service_blockchain_id'
    config_path = 'services/blockchain-id/enabled'

    def dependent_on(self):
        return [
            'service_bismuth_identity',
        ]

    def installed(self):
        from bitdust.main import config
        if config.conf().getBool('services/blockchain-authority/enabled'):
            return False
        return True

    def start(self):
        from twisted.internet.defer import Deferred
        from bitdust.logs import lg
        from bitdust.blockchain import blockchain_registrator
        self.sync_my_transactions_loop = None
        self.starting_deferred = Deferred()
        self.starting_deferred.addErrback(lambda err: lg.warn('service %r was not started: %r' % (self.service_name, err.getErrorMessage() if err else 'unknown reason')))
        blockchain_registrator.A('start', result_defer=self.starting_deferred)
        self.starting_deferred.addCallback(self.on_blockchain_registrator_ready)
        return self.starting_deferred

    def stop(self):
        from bitdust.blockchain import blockchain_registrator
        if self.sync_my_transactions_loop and self.sync_my_transactions_loop.running:
            self.sync_my_transactions_loop.stop()
        self.sync_my_transactions_loop = None
        blockchain_registrator.A('shutdown')
        return True

    def on_blockchain_registrator_ready(self, success):
        from twisted.internet import task  # @UnresolvedImport
        self.sync_my_transactions_loop = task.LoopingCall(self.on_sync_my_transactions_task)
        self.sync_my_transactions_loop.start(15*60, now=False)
        return success

    def on_sync_my_transactions_task(self):
        from bitdust.blockchain import bismuth_wallet
        bismuth_wallet.sync_my_transactions()
