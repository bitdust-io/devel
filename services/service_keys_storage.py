#!/usr/bin/python
# service_keys_storage.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_keys_storage.py) is part of BitDust Software.
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

module:: service_keys_storage
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return KeysStorageService()


class KeysStorageService(LocalService):

    service_name = 'service_keys_storage'
    config_path = 'services/keys-storage/enabled'

    last_time_keys_synchronized = None

    def dependent_on(self):
        return [
            'service_restores',
            'service_backup_db',
        ]

    def start(self):
        from main import events
        from access import key_ring
        events.add_subscriber(self._on_key_generated, 'key-generated')
        events.add_subscriber(self._on_key_registered, 'key-registered')
        events.add_subscriber(self._on_key_erased, 'key-erased')
        events.add_subscriber(self._on_my_backup_index_synchronized, 'my-backup-index-synchronized')
        d = key_ring.do_synchronize_keys(wait_result=True)
        d.addCallback(self._on_keys_synchronized)
        d.addErrback(self._on_keys_synchronize_failed)
        return d

    def stop(self):
        from main import events
        events.remove_subscriber(self._on_my_backup_index_synchronized, 'my-backup-index-synchronized')
        events.remove_subscriber(self._on_key_erased, 'key-erased')
        events.remove_subscriber(self._on_key_registered, 'key-registered')
        events.remove_subscriber(self._on_key_generated, 'key-generated')
        return True

    def health_check(self):
        return True

    def _on_key_generated(self, evt):
        from access import key_ring
        key_ring.do_backup_key(key_id=evt.data['key_id'])

    def _on_key_registered(self, evt):
        from access import key_ring
        key_ring.do_backup_key(key_id=evt.data['key_id'])

    def _on_key_erased(self, evt):
        from access import key_ring
        key_ring.do_delete_key(key_id=evt.data['key_id'], is_private=evt.data['is_private'])

    def _on_my_backup_index_synchronized(self, evt):
        import time
        if self.last_time_keys_synchronized and time.time() - self.last_time_keys_synchronized < 60:
            return
        from access import key_ring
        if key_ring.do_synchronize_keys():
            d = key_ring.do_synchronize_keys(wait_result=True)
            d.addCallback(self._on_keys_synchronized)
            d.addErrback(self._on_keys_synchronize_failed)

    def _on_keys_synchronized(self, x):
        import time
        from logs import lg
        lg.info('all keys synchronized, last time that happens %d seconds ago' % (time.time() - self.last_time_keys_synchronized))
        self.last_time_keys_synchronized = time.time()
        return x

    def _on_keys_synchronize_failed(self, err):
        from logs import lg
        lg.err(err)
        return err
