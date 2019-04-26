#!/usr/bin/python
# service_message_history.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_message_history.py) is part of BitDust Software.
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

module:: service_message_history
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return KeysStorageService()


class KeysStorageService(LocalService):

    service_name = 'service_message_history'
    config_path = 'services/message-history/enabled'

    def dependent_on(self):
        return [
            'service_keys_storage',
            'service_private_messages',
        ]

    def start(self):
        from main import events
        from chat import message_db
        from chat import message_keeper
        message_db.init()
        message_keeper.init()
        events.add_subscriber(self._on_my_keys_synchronized, 'my-keys-synchronized')
        return True

    def stop(self):
        from main import events
        from chat import message_db
        from chat import message_keeper
        events.remove_subscriber(self._on_my_keys_synchronized, 'my-keys-synchronized')
        message_keeper.shutdown()
        message_db.shutdown()
        return True

    def health_check(self):
        return True

    def _on_my_keys_synchronized(self, evt):
        from logs import lg
        from main import settings
        from access import key_ring
        from crypt import my_keys
        from chat import message_keeper
        if not my_keys.is_key_registered(message_keeper.messages_key_id()) and key_ring.is_my_keys_in_sync():
            lg.info('key to store messages was not found but we know that all my keys are in sync, generate a new key: %s' % message_keeper.messages_key_id())
            my_keys.generate_key(message_keeper.messages_key_id(), key_size=settings.getPrivateKeySize())
