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
        from twisted.internet.defer import Deferred
        from main import events
        events.add_subscriber(self._on_key_generated, 'key-generated')
        events.add_subscriber(self._on_key_registered, 'key-registered')
        events.add_subscriber(self._on_key_erased, 'key-erased')
        events.add_subscriber(self._on_my_backup_index_synchronized, 'my-backup-index-synchronized')
        events.add_subscriber(self._on_my_backup_index_out_of_sync, 'my-backup-index-out-of-sync')
        self.starting_deferred = Deferred()
        from storage import index_synchronizer
        if index_synchronizer.A().state == 'IN_SYNC!':
            self._do_synchronize_keys()
            return True
        if index_synchronizer.A().state == 'NO_INFO':
            index_synchronizer.A('pull')
        return self.starting_deferred

    def stop(self):
        from main import events
        events.remove_subscriber(self._on_my_backup_index_out_of_sync, 'my-backup-index-out-of-sync')
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

    def _do_synchronize_keys(self):
        from access import key_ring
        d = key_ring.do_synchronize_keys(wait_result=True)
        d.addCallback(self._on_keys_synchronized)
        d.addErrback(self._on_keys_synchronize_failed)

    def _on_my_backup_index_synchronized(self, evt):
        import time
        if self.starting_deferred:
            self._do_synchronize_keys()
            return
        if not self.last_time_keys_synchronized:
            self._do_synchronize_keys()
            return
        if time.time() - self.last_time_keys_synchronized > 5 * 60:
            self._do_synchronize_keys()
            return

    def _on_my_backup_index_out_of_sync(self, evt):
        from logs import lg
        lg.warn('not possible to synchronize keys because backup index is out of sync')
        if self.starting_deferred:
            self.starting_deferred.errback(Exception('not possible to synchronize keys because backup index is out of sync'))
            self.starting_deferred = None

    def _on_keys_synchronized(self, x):
        import time
        from logs import lg
        from main import events
        lg.info('all keys synchronized')
        self.last_time_keys_synchronized = time.time()
        if self.starting_deferred:
            self.starting_deferred.callback(True)
            self.starting_deferred = None
        events.send('my-keys-synchronized', data=dict())
        return None

    def _on_keys_synchronize_failed(self, err):
        from logs import lg
        lg.err(err)
        if self.starting_deferred:
            self.starting_deferred.errback(err)
            self.starting_deferred = None
        return None
