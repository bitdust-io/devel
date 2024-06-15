#!/usr/bin/python
# service_bismuth_blockchain.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_bismuth_blockchain.py) is part of BitDust Software.
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

module:: service_bismuth_blockchain
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return BismuthBlockchainService()


class BismuthBlockchainService(LocalService):

    service_name = 'service_bismuth_blockchain'
    config_path = 'services/bismuth-blockchain/enabled'

    def dependent_on(self):
        return [
            'service_tcp_connections',
        ]

    def installed(self):
        return True

    def start(self):
        import os
        import sys
        from bitdust.main import settings
        src_dir_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        sys.path.insert(0, os.path.join(src_dir_path, 'bitdust_forks', 'Bismuth'))
        data_dir_path = settings.ServiceDir('bismuth_blockchain')
        if not os.path.exists(data_dir_path):
            os.makedirs(data_dir_path)
        return True

    def stop(self):
        return True
