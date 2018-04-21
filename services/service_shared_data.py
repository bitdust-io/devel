#!/usr/bin/python
# service_shared_data.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (service_shared_data.py) is part of BitDust Software.
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

module:: service_shared_data
"""

from services.local_service import LocalService


def create_service():
    return SharedDataService()


class SharedDataService(LocalService):

    service_name = 'service_shared_data'
    config_path = 'services/shared-data/enabled'

    def dependent_on(self):
        return ['service_restores',
                ]

    def start(self):
        from transport import callback
        callback.append_inbox_callback(self._on_inbox_packet_received)
        return True

    def stop(self):
        from transport import callback
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        return True

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from p2p import commands
        if newpacket.Command == commands.Files():
            return self._on_files_received(newpacket, info)
        return False

    def _on_files_received(self, newpacket, info):
        import json
        from logs import lg
        from p2p import p2p_service
        from storage import backup_fs
        from storage import backup_control
        from crypt import encrypted
        from crypt import my_keys
        from userid import my_id
        from userid import global_id
        list_files_global_id = global_id.ParseGlobalID(newpacket.PacketID)
        if not list_files_global_id['idurl']:
            lg.warn('invalid PacketID: %s' % newpacket.PacketID)
            return False
        incoming_key_id = list_files_global_id['key_id']
        if list_files_global_id['idurl'] == my_id.getGlobalID():
            lg.warn('skip %s packet which seems to came from my own supplier' % newpacket)
            # only process list Files() from other users who granted me access
            return False
        if not my_keys.is_valid_key_id(incoming_key_id):
            lg.warn('ignore, invalid key id in packet %s' % newpacket)
            return False
        if not my_keys.is_key_private(incoming_key_id):
            lg.warn('private key is not registered : %s' % incoming_key_id)
            p2p_service.SendFail(newpacket, 'private key is not registered')
            return False
        try:
            block = encrypted.Unserialize(
                newpacket.Payload,
                decrypt_key=incoming_key_id,
            )
        except:
            lg.exc(newpacket.Payload)
            return False
        if block is None:
            lg.warn('failed reading data from %s' % newpacket.RemoteID)
            return False
        if block.CreatorID != list_files_global_id['idurl']:
            lg.warn('invalid packet, creator ID must be present in packet ID : %s ~ %s' % (block.CreatorID, incoming_key_id, ))
            return False
        try:
            json_data = json.loads(block.Data(), encoding='utf-8')
            json_data['items']
            customer_idurl = block.CreatorID
            count = backup_fs.Unserialize(
                raw_data=json_data,
                iter=backup_fs.fs(customer_idurl),
                iterID=backup_fs.fsID(customer_idurl),
                from_json=True,
            )
        except Exception:
            lg.exc()
            return False
        p2p_service.SendAck(newpacket)
        if count == 0:
            lg.warn('no files were imported during file sharing')
        else:
            backup_control.Save()
            lg.info('imported %d shared files from %s, key_id=%s' % (count, customer_idurl, incoming_key_id, ))
        return True

#         from access import shared_access_coordinator
#         this_share = shared_access_coordinator.get_active_share(key_id)
#         if not this_share:
#             lg.warn('share is not opened: %s' % key_id)
#             p2p_service.SendFail(newpacket, 'share is not opened')
#             return False
#         this_share.automat('customer-list-files-received', (newpacket, info, block, ))
        return True
