#!/usr/bin/python
# service_keys_storage.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from bitdust.services.local_service import LocalService


def create_service():
    return KeysStorageService()


class KeysStorageService(LocalService):

    service_name = 'service_keys_storage'
    config_path = 'services/keys-storage/enabled'

    last_time_keys_synchronized = None
    sync_keys_requested = False

    def dependent_on(self):
        return [
            'service_restores',
        ]

    def start(self):
        from twisted.internet.defer import Deferred
        from bitdust.logs import lg
        from bitdust.main import events
        from bitdust.storage import index_synchronizer
        from bitdust.storage import keys_synchronizer
        keys_synchronizer.A('init')
        self.starting_deferred = Deferred()
        self.starting_deferred.addErrback(lambda err: lg.warn('service %r was not started: %r' % (self.service_name, err.getErrorMessage() if err else 'unknown reason')))
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        events.add_subscriber(self._on_key_generated, 'key-generated')
        events.add_subscriber(self._on_key_registered, 'key-registered')
        events.add_subscriber(self._on_key_erased, 'key-erased')
        events.add_subscriber(self._on_my_backup_index_synchronized, 'my-backup-index-synchronized')
        events.add_subscriber(self._on_my_backup_index_out_of_sync, 'my-backup-index-out-of-sync')
        events.add_subscriber(self._on_my_keys_synchronize_failed, 'my-keys-synchronize-failed')
        if index_synchronizer.A():
            index_synchronizer.A().addStateChangedCallback(self._on_index_synchronizer_state_changed)
        if index_synchronizer.A() and index_synchronizer.A().state == 'NO_INFO':
            # it seems I am offline...
            #   must start here, but expect to be online soon and sync keys later
            return True
        if index_synchronizer.A() and index_synchronizer.A().state == 'IN_SYNC!':
            # if I am already online and backup index in sync - refresh keys ASAP
            self._do_synchronize_keys()
        return self.starting_deferred

    def stop(self):
        from bitdust.main import events
        from bitdust.storage import index_synchronizer
        from bitdust.storage import keys_synchronizer
        if index_synchronizer.A():
            index_synchronizer.A().removeStateChangedCallback(self._on_index_synchronizer_state_changed)
        events.remove_subscriber(self._on_my_keys_synchronize_failed, 'my-keys-synchronize-failed')
        events.remove_subscriber(self._on_my_backup_index_out_of_sync, 'my-backup-index-out-of-sync')
        events.remove_subscriber(self._on_my_backup_index_synchronized, 'my-backup-index-synchronized')
        events.remove_subscriber(self._on_key_erased, 'key-erased')
        events.remove_subscriber(self._on_key_registered, 'key-registered')
        events.remove_subscriber(self._on_key_generated, 'key-generated')
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        if keys_synchronizer.A():
            keys_synchronizer.A('shutdown')
        return True

    def health_check(self):
        from bitdust.storage import index_synchronizer
        from bitdust.storage import keys_synchronizer
        return keys_synchronizer.is_synchronized() and index_synchronizer.is_synchronized()

    def _do_synchronize_keys(self):
        """
        Make sure all my keys are stored on my suppliers nodes (encrypted with my master key).
        If some key I do not have locally, but I know remote copy exists - download it.
        If some key was not stored - make a remote copy on supplier machine.
        When key was renamed (after identity rotate) make sure to store the latest copy and remove older one.
        """
        from bitdust.logs import lg
        from bitdust.storage import index_synchronizer
        from twisted.internet.defer import Deferred
        is_in_sync = index_synchronizer.is_synchronized()
        if is_in_sync:
            result = Deferred()
            result.addCallback(self._on_keys_synchronized)
            result.addErrback(self._on_keys_synchronize_failed)
            self._do_check_sync_keys(result)
            return
        lg.warn('backup index database is not synchronized yet')
        if index_synchronizer.is_synchronizing():
            self.sync_keys_requested = True
            return
        result = Deferred()
        result.addCallback(self._on_keys_synchronized)
        result.addErrback(self._on_keys_synchronize_failed)
        result.errback(Exception('backup index database is not synchronized'))
        return None

    def _do_check_sync_keys(self, result):
        from bitdust.logs import lg
        from bitdust.interface import api
        from bitdust.storage import keys_synchronizer
        from bitdust.userid import global_id
        from bitdust.userid import my_id
        self.sync_keys_requested = False
        global_keys_folder_path = global_id.MakeGlobalID(key_alias='master', customer=my_id.getGlobalID(), path='.keys')
        res = api.file_exists(global_keys_folder_path)
        if res['status'] != 'OK' or not res['result'] or not res['result'].get('exist'):
            res = api.file_create(global_keys_folder_path, as_folder=True)
            if res['status'] != 'OK':
                lg.err('failed to create ".keys" folder "%s" in the catalog: %r' % (global_keys_folder_path, res))
                result.errback(Exception('failed to create keys folder "%s" in the catalog: %r' % (global_keys_folder_path, res)))
                return
            lg.info('created new remote folder ".keys" in the catalog: %r' % global_keys_folder_path)
        keys_synchronizer.A('sync', result)

    def _on_key_generated(self, evt):
        self._do_synchronize_keys()

    def _on_key_registered(self, evt):
        self._do_synchronize_keys()

    def _on_key_erased(self, evt):
        from bitdust.interface import api
        from bitdust.userid import global_id
        from bitdust.userid import my_id
        if evt.data['is_private']:
            remote_path_for_key = '.keys/%s.private' % evt.data['key_id']
        else:
            remote_path_for_key = '.keys/%s.public' % evt.data['key_id']
        global_key_path = global_id.MakeGlobalID(
            key_alias='master',
            customer=my_id.getGlobalID(),
            path=remote_path_for_key,
        )
        api.file_delete(remote_path=global_key_path)
        self._do_synchronize_keys()

    def _on_my_backup_index_synchronized(self, evt):
        import time
        from bitdust.logs import lg
        if self.starting_deferred:
            self._do_synchronize_keys()
            return
        if not self.last_time_keys_synchronized:
            self._do_synchronize_keys()
            return
        from bitdust.storage import keys_synchronizer
        if not keys_synchronizer.is_synchronized():
            self._do_synchronize_keys()
            return
        if time.time() - self.last_time_keys_synchronized > 5*60:
            self._do_synchronize_keys()
            return
        from bitdust.main import events
        lg.info('backup index and all my keys synchronized')
        events.send('my-storage-ready', data=dict())

    def _on_my_backup_index_out_of_sync(self, evt):
        from bitdust.logs import lg
        from bitdust.main import events
        if self.starting_deferred:
            self.starting_deferred.errback(Exception('not possible to synchronize keys because backup index is out of sync'))
            self.starting_deferred = None
        lg.info('not possible to synchronize keys because backup index is out of sync')
        events.send('my-storage-not-ready-yet', data=dict())

    def _on_keys_synchronized(self, x):
        import time
        from bitdust.logs import lg
        from bitdust.main import events
        self.last_time_keys_synchronized = time.time()
        if self.starting_deferred:
            self.starting_deferred.callback(True)
            self.starting_deferred = None
        lg.info('all my keys are synchronized, my distributed storage is ready')
        events.send('my-keys-synchronized', data=dict())
        events.send('my-storage-ready', data=dict())
        return None

    def _on_keys_synchronize_failed(self, err=None):
        from bitdust.logs import lg
        from bitdust.main import events
        if self.starting_deferred:
            self.starting_deferred.errback(err)
            self.starting_deferred = None
        lg.warn(err.getErrorMessage() if err else 'synchronize keys failed with unknown reason')
        events.send('my-keys-out-of-sync', data=dict())
        events.send('my-storage-not-ready-yet', data=dict())
        return None

    def _on_identity_url_changed(self, evt):
        from bitdust.crypt import my_keys
        # from bitdust.storage import backup_control
        my_keys.check_rename_my_keys()
        self._do_synchronize_keys()
        # backup_control.Save()
        return None

    def _on_index_synchronizer_state_changed(self, oldstate, newstate, event_string, *args, **kwargs):
        from twisted.internet.defer import Deferred
        if oldstate in ['REQUEST?', 'SENDING'] and newstate == 'IN_SYNC!':
            if self.sync_keys_requested:
                result = Deferred()
                result.addCallback(self._on_keys_synchronized)
                result.addErrback(self._on_keys_synchronize_failed)
                self._do_check_sync_keys(result)

    def _on_my_keys_synchronize_failed(self, evt):
        from bitdust.logs import lg
        from bitdust.main import config
        from bitdust.interface import api
        from bitdust.userid import global_id
        from bitdust.userid import my_id
        if not config.conf().getBool('services/keys-storage/reset-unreliable-backup-copies'):
            return
        global_keys_folder_path = global_id.MakeGlobalID(key_alias='master', customer=my_id.getGlobalID(), path='.keys')
        lg.info('about to erase ".keys" folder in the catalog: %r' % global_keys_folder_path)
        res = api.file_delete(remote_path=global_keys_folder_path)
        if res['status'] == 'OK':
            api.network_reconnect()
        else:
            errors = res.get('errors') or []
            if errors and errors[0].count('remote path') and errors[0].count('was not found'):
                api.network_reconnect()
