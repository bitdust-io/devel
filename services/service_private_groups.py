#!/usr/bin/python
# service_private_groups.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_private_groups.py) is part of BitDust Software.
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

module:: service_private_groups
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return PrivateGroupsService()


class PrivateGroupsService(LocalService):

    service_name = 'service_private_groups'
    config_path = 'services/private-groups/enabled'

    def dependent_on(self):
        return [
            'service_my_data',
            'service_private_messages',
        ]

    def start(self):
        return True

    def stop(self):
        return True

    def health_check(self):
        return True
