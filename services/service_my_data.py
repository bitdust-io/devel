#!/usr/bin/python
# service_my_data.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_my_data.py) is part of BitDust Software.
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

module:: service_my_data
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return KeysStorageService()


class KeysStorageService(LocalService):

    service_name = 'service_my_data'
    config_path = 'services/my-data/enabled'

    last_time_keys_synchronized = None

    def dependent_on(self):
        return [
            'service_keys_storage',
        ]

    def start(self):
        from access import key_ring
        from storage import index_synchronizer
        if key_ring.is_my_keys_in_sync() and index_synchronizer.is_synchronized():
            return True
        return False

    def stop(self):
        return True

    def health_check(self):
        return True
