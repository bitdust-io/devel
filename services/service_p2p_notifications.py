#!/usr/bin/python
# service_p2p_notifications.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (service_p2p_notifications.py) is part of BitDust Software.
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

module:: service_p2p_notifications
"""

from services.local_service import LocalService


def create_service():
    return P2PNotificationsService()


class P2PNotificationsService(LocalService):

    service_name = 'service_p2p_notifications'
    config_path = 'services/p2p-notifications/enabled'

    def dependent_on(self):
        return [
            'service_gateway',
        ]

    def start(self):
        from p2p import p2p_queue
        p2p_queue.init()
        return True

    def stop(self):
        from p2p import p2p_queue
        p2p_queue.shutdown()
        return True

    def request(self, request, info):
        LocalService.request(self, request, info)
        return None

    def cancel(self, request, info):
        LocalService.cancel(self, request, info)
        return True
