#!/usr/bin/python
# service_rebuilding.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_rebuilding.py) is part of BitDust Software.
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

module:: service_rebuilding
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return RebuildingService()


class RebuildingService(LocalService):

    service_name = 'service_rebuilding'
    config_path = 'services/rebuilding/enabled'

    def dependent_on(self):
        return [
            'service_data_motion',
        ]

    def start(self):
        from raid import raid_worker
        from storage import backup_rebuilder
        raid_worker.A('init')
        backup_rebuilder.A('init')
        return True

    def stop(self):
        from raid import raid_worker
        from storage import backup_rebuilder
        backup_rebuilder.Destroy()
        raid_worker.A('shutdown')
        return True
