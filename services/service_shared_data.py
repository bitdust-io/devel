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
        from userid import my_id
        from userid import global_id
        try:
            user_id = newpacket.PacketID.strip().split(':')[0]
        except:
            lg.exc()
            return False
        if user_id == my_id.getGlobalID():
            # skip my own Files() packets which comes from my suppliers
            # only process list Files() from other users who granted me access
            return False
        block = encrypted.Unserialize(newpacket.Payload)
        if block is None:
            lg.warn('failed reading data from %s' % newpacket.RemoteID)
            return False
        if block.CreatorID != global_id.GlobalUserToIDURL(user_id):
            lg.warn('invalid packet, creator ID must be present in packet ID')
            return False
        from access import shared_access_coordinator
        for A in shared_access_coordinator.find_active_shares(block.CreatorID):
            A.automat('customer-list-files-received', (newpacket, info, block, ))
            processed = True
        return processed
