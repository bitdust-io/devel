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
from services.local_service import LocalService


def create_service():
    return MessageHistoryService()


class MessageHistoryService(LocalService):

    service_name = 'service_message_history'
    config_path = 'services/message-history/enabled'

    def dependent_on(self):
        return [
            'service_my_data',
            'service_private_messages',
        ]

    def start(self):
        from chat import message_database
        from chat import message_keeper
        message_database.init()
        message_keeper.init()
        return True

    def stop(self):
        from chat import message_database
        from chat import message_keeper
        message_keeper.shutdown()
        message_database.shutdown()
        return True

    def health_check(self):
        return True
