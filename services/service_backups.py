#!/usr/bin/python
# service_backups.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

from services.local_service import LocalService


def create_service():
    return BackupsService()


class BackupsService(LocalService):

    service_name = 'service_backups'
    config_path = 'services/backups/enabled'

    def dependent_on(self):
        return ['service_keys_registry',
                ]

    def start(self):
        from storage import backup_fs
        from storage import backup_control
        from storage import backup_matrix
        from storage import backup_monitor
        from main import settings
        from main.config import conf
        from transport import callback
        from p2p import p2p_connector
        backup_fs.init()
        backup_control.init()
        backup_matrix.init()
        if settings.NewWebGUI():
            from web import control
            backup_matrix.SetBackupStatusNotifyCallback(control.on_backup_stats)
            backup_matrix.SetLocalFilesNotifyCallback(control.on_read_local_files)
        else:
            from web import webcontrol
            backup_matrix.SetBackupStatusNotifyCallback(webcontrol.OnBackupStats)
            backup_matrix.SetLocalFilesNotifyCallback(webcontrol.OnReadLocalFiles)
        backup_monitor.A('init')
        backup_monitor.A('restart')
        conf().addCallback('services/backups/keep-local-copies-enabled',
                           self._on_keep_local_copies_modified)
        conf().addCallback('services/backups/wait-suppliers-enabled',
                           self._on_wait_suppliers_modified)
        p2p_connector.A().addStateChangedCallback(
            self._on_p2p_connector_state_changed, 'INCOMMING?', 'CONNECTED')
        p2p_connector.A().addStateChangedCallback(
            self._on_p2p_connector_state_changed, 'MY_IDENTITY', 'CONNECTED')
        callback.append_inbox_callback(self._on_inbox_packet_received)
        return True

    def stop(self):
        from storage import backup_fs
        from storage import backup_monitor
        from storage import backup_control
        from transport import callback
        from p2p import p2p_connector
        from main.config import conf
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        if p2p_connector.A():
            p2p_connector.A().removeStateChangedCallback(self._on_p2p_connector_state_changed)
        backup_monitor.Destroy()
        backup_fs.shutdown()
        backup_control.shutdown()
        conf().removeCallback('services/backups/keep-local-copies-enabled')
        return True

    def _on_keep_local_copies_modified(self, path, value, oldvalue, result):
        from storage import backup_monitor
        backup_monitor.A('restart')

    def _on_wait_suppliers_modified(self, path, value, oldvalue, result):
        from storage import backup_monitor
        backup_monitor.A('restart')

    def _on_p2p_connector_state_changed(self, oldstate, newstate, event_string, args):
        from storage import backup_monitor
        backup_monitor.A('restart')

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from logs import lg
        from main import settings
        from contacts import contactsdb
        from userid import my_id
        from userid import global_id
        from storage import backup_control
        from p2p import commands
        if newpacket.Command == commands.Data():
            if newpacket.OwnerID != my_id.getLocalID():
                # only catch data belongs to me
                return False
            lg.out(self.debug_level, "service_backups._on_inbox_packet_received: %r for us from %s" % (
                newpacket, newpacket.RemoteID, ))
            if newpacket.PacketID == global_id.MakeGlobalID(
                idurl=my_id.getLocalID(),
                path=settings.BackupIndexFileName(),
            ):
                # TODO: move to service_backup_db
                backup_control.IncomingSupplierBackupIndex(newpacket)
                return True
        if newpacket.Command == commands.Files():
            list_files_global_id = global_id.ParseGlobalID(newpacket.PacketID)
            if not list_files_global_id['idurl']:
                lg.warn('invalid PacketID: %s' % newpacket.PacketID)
                return False
            if list_files_global_id['idurl'] != my_id.getLocalIDURL():
                lg.warn('skip %s which is from another customer' % newpacket)
                return False
            if not contactsdb.is_supplier(newpacket.OwnerID):
                lg.warn('%s came, but %s is not my supplier' % (newpacket, newpacket.OwnerID, ))
                # skip Files() if this is not my supplier
                return False
            lg.out(self.debug_level, "service_backups._on_inbox_packet_received: %r for us from %s" % (
                newpacket, newpacket.RemoteID, ))
            return backup_control.IncomingSupplierListFiles(newpacket, list_files_global_id)
        return False
