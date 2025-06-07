#!/usr/bin/python
# service_backups.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_backups.py) is part of BitDust Software.
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

module:: service_backups
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return BackupsService()


class BackupsService(LocalService):

    service_name = 'service_backups'
    config_path = 'services/backups/enabled'

    def dependent_on(self):
        return [
            'service_list_files',
            'service_rebuilding',
            'service_backup_db',
        ]

    def start(self):
        from bitdust.storage import backup_control
        from bitdust.storage import backup_matrix
        from bitdust.storage import backup_monitor
        from bitdust.main.config import conf
        from bitdust.main import events
        from bitdust.main import listeners
        from bitdust.transport import callback
        from bitdust.p2p import p2p_connector
        backup_control.init()
        backup_matrix.init()
        backup_monitor.A('init')
        backup_monitor.A('restart')
        conf().addConfigNotifier('services/backups/keep-local-copies-enabled', self._on_keep_local_copies_modified)
        conf().addConfigNotifier('services/backups/wait-suppliers-enabled', self._on_wait_suppliers_modified)
        p2p_connector.A().addStateChangedCallback(self._on_p2p_connector_state_changed, 'INCOMMING?', 'CONNECTED')
        p2p_connector.A().addStateChangedCallback(self._on_p2p_connector_state_changed, 'MY_IDENTITY', 'CONNECTED')
        callback.append_inbox_callback(self._on_inbox_packet_received)
        events.add_subscriber(self._on_my_identity_rotated, 'my-identity-rotated')
        events.add_subscriber(self._on_key_erased, 'key-erased')
        if listeners.is_populate_required('remote_version'):
            backup_matrix.populate_remote_versions()
        return True

    def stop(self):
        from bitdust.storage import backup_monitor
        from bitdust.storage import backup_control
        from bitdust.transport import callback
        from bitdust.p2p import p2p_connector
        from bitdust.main import events
        from bitdust.main.config import conf
        events.remove_subscriber(self._on_key_erased, 'key-erased')
        events.remove_subscriber(self._on_my_identity_rotated, 'my-identity-rotated')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        if p2p_connector.A():
            p2p_connector.A().removeStateChangedCallback(self._on_p2p_connector_state_changed)
        backup_monitor.Destroy()
        backup_control.shutdown()
        conf().removeConfigNotifier('services/backups/keep-local-copies-enabled')
        return True

    def health_check(self):
        from bitdust.storage import backup_monitor
        return backup_monitor.A().state in [
            'READY',
            'FIRE_HIRE',
            'LIST_FILES',
            'LIST_BACKUPS',
            'REBUILDING',
        ]

    def _on_key_erased(self, evt):
        from bitdust.interface import api
        ret = api.files_list(
            remote_path='',
            key_id=evt.data['key_id'],
            recursive=True,
            all_customers=True,
        )
        if ret.get('status') == 'OK':
            for one_file in ret['result']:
                api.file_delete(remote_path=one_file['remote_path'])

    def _on_keep_local_copies_modified(self, path, value, oldvalue, result):
        from bitdust.storage import backup_monitor
        from bitdust.logs import lg
        lg.warn('restarting backup_monitor() machine')
        backup_monitor.A('restart')

    def _on_wait_suppliers_modified(self, path, value, oldvalue, result):
        from bitdust.storage import backup_monitor
        from bitdust.logs import lg
        lg.warn('restarting backup_monitor() machine')
        backup_monitor.A('restart')

    def _on_p2p_connector_state_changed(self, oldstate, newstate, event_string, *args, **kwargs):
        from bitdust.storage import backup_monitor
        backup_monitor.A('restart')

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from bitdust.storage import backup_control
        from bitdust.p2p import commands
        if newpacket.Command == commands.Files():
            return backup_control.on_files_received(newpacket, info)
        return False

    def _on_my_identity_rotated(self, evt):
        from bitdust.logs import lg
        from bitdust.lib import packetid
        from bitdust.storage import backup_matrix
        backup_matrix.ReadLocalFiles()
        remote_files_ids = list(backup_matrix.remote_files().keys())
        for currentID in remote_files_ids:
            latestID = packetid.LatestBackupID(currentID)
            if latestID != currentID:
                backup_matrix.remote_files()[latestID] = backup_matrix.remote_files().pop(currentID)
                lg.info('detected backup ID change in remote_files() after identity rotate : %r -> %r' % (currentID, latestID))
        remote_max_block_numbers_ids = list(backup_matrix.remote_max_block_numbers().keys())
        for currentID in remote_max_block_numbers_ids:
            latestID = packetid.LatestBackupID(currentID)
            if latestID != currentID:
                backup_matrix.remote_max_block_numbers()[latestID] = backup_matrix.remote_max_block_numbers().pop(currentID)
                lg.info('detected backup ID change in remote_max_block_numbers() after identity rotate : %r -> %r' % (currentID, latestID))
