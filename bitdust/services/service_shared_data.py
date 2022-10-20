#!/usr/bin/python
# service_shared_data.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return SharedDataService()


class SharedDataService(LocalService):

    service_name = 'service_shared_data'
    config_path = 'services/shared-data/enabled'

    def dependent_on(self):
        return [
            'service_my_data',
        ]

    def start(self):
        from bitdust.main import events
        from bitdust.transport import callback
        from bitdust.access import shared_access_coordinator
        callback.append_inbox_callback(self._on_inbox_packet_received)
        events.add_subscriber(shared_access_coordinator.on_supplier_modified, 'supplier-modified')
        events.add_subscriber(shared_access_coordinator.on_my_list_files_refreshed, 'my-list-files-refreshed')
        events.add_subscriber(shared_access_coordinator.on_key_registered, 'key-registered')
        events.add_subscriber(shared_access_coordinator.on_key_erased, 'key-erased')
        events.add_subscriber(shared_access_coordinator.on_share_connected, 'share-connected')
        events.add_subscriber(shared_access_coordinator.on_supplier_file_modified, 'supplier-file-modified')
        shared_access_coordinator.open_known_shares()
        return True

    def stop(self):
        from bitdust.main import events
        from bitdust.transport import callback
        from bitdust.access import shared_access_coordinator
        events.remove_subscriber(shared_access_coordinator.on_key_registered, 'key-registered')
        events.remove_subscriber(shared_access_coordinator.on_key_erased, 'key-erased')
        events.remove_subscriber(shared_access_coordinator.on_share_connected, 'share-connected')
        events.remove_subscriber(shared_access_coordinator.on_my_list_files_refreshed, 'my-list-files-refreshed')
        events.remove_subscriber(shared_access_coordinator.on_supplier_modified, 'supplier-modified')
        events.remove_subscriber(shared_access_coordinator.on_supplier_file_modified, 'supplier-file-modified')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        return True

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from bitdust.p2p import commands
        from bitdust.access import key_ring
        if newpacket.Command == commands.Files():
            return key_ring.on_files_received(newpacket, info)
        return False
