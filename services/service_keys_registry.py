#!/usr/bin/python
# service_keys_registry.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

from services.local_service import LocalService


def create_service():
    return KeysRegistryService()


class KeysRegistryService(LocalService):

    service_name = 'service_keys_registry'
    config_path = 'services/keys-registry/enabled'

    def dependent_on(self):
        return ['service_list_files',
                'service_employer',
                'service_rebuilding',
                ]

    def start(self):
        from access import key_ring
        from transport import callback
        key_ring.init()
        callback.add_outbox_callback(self._outbox_packet_sent)
        callback.append_inbox_callback(self._inbox_packet_received)
        return True

    def stop(self):
        from access import key_ring
        from transport import callback
        callback.remove_inbox_callback(self._inbox_packet_received)
        callback.remove_outbox_callback(self._outbox_packet_sent)
        key_ring.shutdown()
        return True

    def _outbox_packet_sent(self, pkt_out):
        pass

    def _inbox_packet_received(self, newpacket, info, status, error_message):
        if status != 'finished':
            return False
        from p2p import commands
        from access import key_ring
        if newpacket.Command != commands.Key():
            return False
        return key_ring.on_private_key_received(newpacket, info, status, error_message)
