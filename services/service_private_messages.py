#!/usr/bin/python
# service_private_messages.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_private_messages.py) is part of BitDust Software.
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

module:: service_private_messages
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return PrivateMessagesService()


class PrivateMessagesService(LocalService):

    service_name = 'service_private_messages'
    config_path = 'services/private-messages/enabled'

    def dependent_on(self):
        return [
            'service_keys_registry',
            'service_entangled_dht',
        ]

    def start(self):
        from transport import callback
        from chat import message
        from chat import nickname_holder
        message.init()
        nickname_holder.A('set')
        callback.append_inbox_callback(self._on_inbox_packet_received)
        return True

    def stop(self):
        from transport import callback
        from chat import message
        from chat import nickname_holder
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        nickname_holder.Destroy()
        message.shutdown()
        return True

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from p2p import commands
        from chat import message
        if newpacket.Command != commands.Message():
            return False
        return message.on_incoming_message(newpacket, info, status, error_message)
