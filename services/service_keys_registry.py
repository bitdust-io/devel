#!/usr/bin/python
# service_keys_registry.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_keys_registry.py) is part of BitDust Software.
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

module:: service_keys_registry
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return KeysRegistryService()


class KeysRegistryService(LocalService):

    service_name = 'service_keys_registry'
    config_path = 'services/keys-registry/enabled'

    last_time_keys_synchronized = None

    def dependent_on(self):
        return [
            'service_p2p_notifications',
        ]

    def start(self):
        from access import key_ring
        from transport import callback
        from main import events
        key_ring.init()
        callback.add_outbox_callback(self._on_outbox_packet_sent)
        callback.append_inbox_callback(self._on_inbox_packet_received)
        events.add_subscriber(self._on_key_generated, 'key-generated')
        events.add_subscriber(self._on_key_registered, 'key-registered')
        events.add_subscriber(self._on_key_erased, 'key-erased')
        events.add_subscriber(self._on_my_backup_index_synchronized, 'my-backup-index-synchronized')
        return True

    def stop(self):
        from access import key_ring
        from transport import callback
        from main import events
        events.remove_subscriber(self._on_my_backup_index_synchronized, 'my-backup-index-synchronized')
        events.remove_subscriber(self._on_key_erased, 'key-erased')
        events.remove_subscriber(self._on_key_registered, 'key-registered')
        events.remove_subscriber(self._on_key_generated, 'key-generated')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        callback.remove_outbox_callback(self._on_outbox_packet_sent)
        key_ring.shutdown()
        return True

    def request(self, json_payload, newpacket, info):
        # TODO: work in progress
        from main import events
        from p2p import p2p_service
        events.send('key-registry-request', dict(idurl=newpacket.OwnerID))
        return p2p_service.SendAck(newpacket, 'accepted')

    def _on_outbox_packet_sent(self, pkt_out):
        from p2p import commands
        if pkt_out.outpacket.Command == commands.Key():
            # TODO: work in progress : need to store history of all keys transfers
            return True
        return False

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from p2p import commands
        from access import key_ring
        if newpacket.Command == commands.Key():
            # TODO: work in progress : need to store history of all keys transfers
            return key_ring.on_key_received(newpacket, info, status, error_message)
        elif newpacket.Command == commands.AuditKey():
            return key_ring.on_audit_key_received(newpacket, info, status, error_message)
        return False

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
        key_ring.do_synchronize_keys()
        self.last_time_keys_synchronized = time.time()
