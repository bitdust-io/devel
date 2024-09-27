#!/usr/bin/python
# service_message_history.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from bitdust.services.local_service import LocalService


def create_service():
    return MessageHistoryService()


class MessageHistoryService(LocalService):

    service_name = 'service_message_history'
    config_path = 'services/message-history/enabled'

    def dependent_on(self):
        return [
            'service_my_data',
            'service_private_groups',
        ]

    def start(self):
        from bitdust.chat import message_database
        from bitdust.chat import message_keeper
        from bitdust.main import events
        from bitdust.main import listeners
        message_database.init()
        message_keeper.init()
        events.add_subscriber(self.on_key_registered, 'key-registered')
        events.add_subscriber(self.on_key_renamed, 'key-renamed')
        events.add_subscriber(self.on_key_generated, 'key-generated')
        events.add_subscriber(self.on_key_erased, 'key-erased')
        if listeners.is_populate_required('conversation'):
            # listeners.populate_later().remove('conversation')
            message_database.populate_conversations()
        if listeners.is_populate_required('message'):
            # listeners.populate_later().remove('message')
            message_database.populate_messages()
        return True

    def stop(self):
        from bitdust.chat import message_database
        from bitdust.chat import message_keeper
        from bitdust.main import events
        events.remove_subscriber(self.on_key_erased, 'key-erased')
        events.remove_subscriber(self.on_key_generated, 'key-generated')
        events.remove_subscriber(self.on_key_renamed, 'key-renamed')
        events.remove_subscriber(self.on_key_registered, 'key-registered')
        message_keeper.shutdown()
        message_database.shutdown()
        return True

    def health_check(self):
        return True

    def on_key_generated(self, evt):
        from bitdust.chat import message_database
        message_database.check_create_rename_key(new_key_id=evt.data['key_id'])

    def on_key_registered(self, evt):
        from bitdust.chat import message_database
        message_database.check_create_rename_key(new_key_id=evt.data['key_id'])

    def on_key_renamed(self, evt):
        from bitdust.chat import message_database
        message_database.check_create_rename_key(new_key_id=evt.data['new_key_id'])

    def on_key_erased(self, evt):
        from bitdust.main import listeners
        from bitdust.chat import message_database
        if evt.data['key_id'].startswith('group_'):
            conversation_id = message_database.get_conversation_id(evt.data['local_key_id'], evt.data['local_key_id'], 3)
            listeners.push_snapshot('conversation', snap_id=conversation_id, deleted=True)

    # def do_check_create_rename_key(self, new_key_id):
    #     from bitdust.logs import lg
    #     from bitdust.crypt import my_keys
    #     from bitdust.chat import message_database
    #     try:
    #         new_public_key = my_keys.get_public_key_raw(new_key_id)
    #     except:
    #         lg.exc()
    #         return
    #     try:
    #         new_local_key_id = my_keys.get_local_key_id(new_key_id)
    #     except:
    #         lg.exc()
    #         return
    #     if new_local_key_id is None:
    #         lg.err('did not found local_key_id for %r' % new_key_id)
    #         return
    #     message_database.check_create_rename_key(
    #         new_public_key=new_public_key,
    #         new_key_id=new_key_id,
    #         new_local_key_id=new_local_key_id,
    #     )
