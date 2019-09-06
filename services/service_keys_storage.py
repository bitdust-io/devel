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
        from logs import lg
        from main import events
        from storage import index_synchronizer
        from storage import keys_synchronizer
        keys_synchronizer.A('init')
        self.starting_deferred = Deferred()
        self.starting_deferred.addErrback(lambda err: lg.warn('service %r was not started: %r' % (
            self.service_name, err.getErrorMessage() if err else 'unknown reason')))
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        events.add_subscriber(self._on_key_generated, 'key-generated')
        events.add_subscriber(self._on_key_registered, 'key-registered')
        events.add_subscriber(self._on_key_erased, 'key-erased')
        events.add_subscriber(self._on_my_backup_index_synchronized, 'my-backup-index-synchronized')
        events.add_subscriber(self._on_my_backup_index_out_of_sync, 'my-backup-index-out-of-sync')
        if index_synchronizer.A().state == 'NO_INFO':
            # it seems I am offline...  must start here, but expect to be online soon and sync keys later 
            return True
        if index_synchronizer.A().state == 'IN_SYNC!':
            # if I am already online and backup index in sync - refresh keys ASAP
            self._do_synchronize_keys()
        return self.starting_deferred

    def stop(self):
        from main import events
        from storage import keys_synchronizer
        events.remove_subscriber(self._on_my_backup_index_out_of_sync, 'my-backup-index-out-of-sync')
        events.remove_subscriber(self._on_my_backup_index_synchronized, 'my-backup-index-synchronized')
        events.remove_subscriber(self._on_key_erased, 'key-erased')
        events.remove_subscriber(self._on_key_registered, 'key-registered')
        events.remove_subscriber(self._on_key_generated, 'key-generated')
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        keys_synchronizer.A('shutdown')
        return True

    def health_check(self):
        from storage import index_synchronizer
        from storage import keys_synchronizer
        return keys_synchronizer.is_synchronized() and index_synchronizer.is_synchronized()

    def _on_key_generated(self, evt):
        self._do_synchronize_keys()

    def _on_key_registered(self, evt):
        self._do_synchronize_keys()

    def _on_key_erased(self, evt):
        self._do_synchronize_keys()

    def _do_synchronize_keys(self):
        """
        Make sure all my keys are stored on my suppliers nodes (encrypted with my master key).
        If some key I do not have locally, but I know remote copy exists - download it.
        If some key was not stored - make a remote copy on supplier machine.
        When key was renamed (after identity rotate) make sure to store the latest copy and remove older one. 
        """
        from logs import lg
        from userid import global_id
        from userid import my_id
        from interface import api
        from storage import backup_control
        from storage import index_synchronizer
        from storage import keys_synchronizer
        from twisted.internet.defer import Deferred
        result = Deferred()
        result.addCallback(self._on_keys_synchronized)
        result.addErrback(self._on_keys_synchronize_failed)
        is_in_sync = index_synchronizer.is_synchronized() and backup_control.revision() > 0
        if not is_in_sync:
            lg.warn('backup index database is not synchronized yet')
            result.errback(Exception('backup index database is not synchronized yet'))
            return None
        global_keys_folder_path = global_id.MakeGlobalID(
            key_alias='master', customer=my_id.getGlobalID(), path='.keys')
        res = api.file_exists(global_keys_folder_path)
        if res['status'] != 'OK' or not res['result']:
            res = api.file_create(global_keys_folder_path, as_folder=True)
            if res['status'] != 'OK':
                lg.err('failed to create keys folder "%s" in the catalog: %r' % (global_keys_folder_path, res))
                result.errback(Exception('failed to create keys folder "%s" in the catalog: %r' % (global_keys_folder_path, res)))
                return
            lg.info('created new remote folder ".keys" in the catalog: %r' % global_keys_folder_path)
        keys_synchronizer.A('sync', result)

    def _on_my_backup_index_synchronized(self, evt):
        import time
        from logs import lg
        if self.starting_deferred:
            self._do_synchronize_keys()
            return
        if not self.last_time_keys_synchronized:
            self._do_synchronize_keys()
            return
        from storage import keys_synchronizer
        if not keys_synchronizer.is_synchronized():
            self._do_synchronize_keys()
            return
        if time.time() - self.last_time_keys_synchronized > 5 * 60:
            self._do_synchronize_keys()
            return
        from main import events
        lg.info('backup index and all my keys synchronized')
        events.send('my-storage-ready', data=dict())

    def _on_my_backup_index_out_of_sync(self, evt):
        from logs import lg
        from main import events
        if self.starting_deferred:
            self.starting_deferred.errback(Exception('not possible to synchronize keys because backup index is out of sync'))
            self.starting_deferred = None
        lg.info('not possible to synchronize keys because backup index is out of sync')
        events.send('my-storage-not-ready-yet', data=dict())

    def _on_keys_synchronized(self, x):
        import time
        from logs import lg
        from main import events
        self.last_time_keys_synchronized = time.time()
        if self.starting_deferred:
            self.starting_deferred.callback(True)
            self.starting_deferred = None
        lg.info('all my keys are synchronized, my distributed storage is ready')
        events.send('my-keys-synchronized', data=dict())
        events.send('my-storage-ready', data=dict())
        return None

    def _on_keys_synchronize_failed(self, err=None):
        from logs import lg
        from main import events
        if self.starting_deferred:
            self.starting_deferred.errback(err)
            self.starting_deferred = None
        lg.err(err.getErrorMessage() if err else 'synchronize keys failed with unknown reason')
        events.send('my-keys-out-of-sync', data=dict())
        events.send('my-storage-not-ready-yet', data=dict())
        return None

    def _on_identity_url_changed(self, evt):
        from userid import id_url
        from userid import my_id
        if id_url.field(evt.data['new_idurl']) == my_id.getLocalID():
            # do not take any actions here if my own identity was rotated
            return None
        from access import key_ring
        from storage import backup_control
        key_ring.check_rename_my_keys()
        self._do_synchronize_keys()
        backup_control.Save()
        return None
