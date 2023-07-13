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
            'service_bismuth_wallet',
            'service_identity_propagate',
            'service_entangled_dht',
        ]

    def installed(self):
        return True

    def start(self):
        from twisted.internet.defer import Deferred
        from bitdust.logs import lg
        from bitdust.blockchain import bismuth_identity
        self.starting_deferred = Deferred()
        self.starting_deferred.addErrback(lambda err: lg.warn('service %r was not started: %r' % (self.service_name, err.getErrorMessage() if err else 'unknown reason')))
        bismuth_identity.A('start', result_defer=self.starting_deferred)
        return self.starting_deferred

    def stop(self):
        from bitdust.blockchain import bismuth_identity
        bismuth_identity.A('shutdown')
        return True
