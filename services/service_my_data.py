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

    def init(self, **kwargs):
        from main import events
        events.add_subscriber(self._on_my_storage_ready, 'my-storage-ready')
        events.add_subscriber(self._on_my_storage_not_ready_yet, 'my-storage-not-ready-yet')

    def shutdown(self):
        from main import events
        events.remove_subscriber(self._on_my_storage_not_ready_yet, 'my-storage-not-ready-yet')
        events.remove_subscriber(self._on_my_storage_ready, 'my-storage-ready')

    def start(self):
        from logs import lg
        from access import key_ring
        from storage import index_synchronizer
        if key_ring.is_my_keys_in_sync() and index_synchronizer.is_synchronized():
            return True
        lg.warn('can not start service_my_data right now, key_ring.is_my_keys_in_sync=%r index_synchronizer.is_synchronized=%r' % (
            key_ring.is_my_keys_in_sync(), index_synchronizer.is_synchronized()))
        return False

    def stop(self):
        return True

    def health_check(self):
        return True

    def _on_my_storage_ready(self, evt):
        from logs import lg
        from services import driver
        if driver.is_enabled('service_my_data'):
            lg.info('my storage is ready, starting service_my_data()')
            driver.start_single('service_my_data')

    def _on_my_storage_not_ready_yet(self, evt):
        from logs import lg
        from services import driver
        if driver.is_enabled('service_my_data'):
            lg.info('my storage is not ready yet, stopping service_my_data()')
            driver.stop_single('service_my_data')
