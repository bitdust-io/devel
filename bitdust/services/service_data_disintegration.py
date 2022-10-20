#!/usr/bin/python
# service_data_disintegration.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_data_disintegration.py) is part of BitDust Software.
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

module:: service_data_disintegration
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return DataDisintegrationService()


class DataDisintegrationService(LocalService):

    service_name = 'service_data_disintegration'
    config_path = 'services/data-disintegration/enabled'

    def dependent_on(self):
        return [
            'service_keys_registry',
        ]

    def start(self):
        from bitdust.raid import raid_worker
        raid_worker.A('init')
        return True

    def stop(self):
        from bitdust.raid import raid_worker
        raid_worker.A('shutdown')
        return True
