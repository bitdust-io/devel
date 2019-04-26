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

    def dependent_on(self):
        return [
            'service_p2p_notifications',
        ]

    def start(self):
        from transport import callback
        from access import key_ring
        key_ring.init()
        callback.add_outbox_callback(self._on_outbox_packet_sent)
        callback.append_inbox_callback(self._on_inbox_packet_received)
        return True

    def stop(self):
        from transport import callback
        from access import key_ring
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        callback.remove_outbox_callback(self._on_outbox_packet_sent)
        key_ring.shutdown()
        return True

    def request(self, json_payload, newpacket, info):
        # TODO: work in progress
        # from main import events
        from p2p import p2p_service
        # events.send('key-registry-request', dict(idurl=newpacket.OwnerID))
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
