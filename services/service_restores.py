#!/usr/bin/python
# service_restores.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_restores.py) is part of BitDust Software.
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

module:: service_restores
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return RestoreMonitorService()


class RestoreMonitorService(LocalService):

    service_name = 'service_restores'
    config_path = 'services/restores/enabled'

    def dependent_on(self):
        return [
            'service_backups',
        ]

    def start(self):
        from storage import restore_monitor
        restore_monitor.init()
        return True

    def stop(self):
        from storage import restore_monitor
        restore_monitor.shutdown()
        return True
