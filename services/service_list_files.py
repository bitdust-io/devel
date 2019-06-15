#!/usr/bin/python
# service_list_files.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_list_files.py) is part of BitDust Software.
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

module:: service_list_files
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return ListFilesService()


class ListFilesService(LocalService):

    service_name = 'service_list_files'
    config_path = 'services/list-files/enabled'

    def dependent_on(self):
        return [
            'service_employer',
        ]

    def start(self):
        from logs import lg
        from main import events
        from customer import fire_hire
        from customer import list_files_orator
        list_files_orator.A('init')
        events.add_subscriber(self._on_my_suppliers_all_hired, 'my-suppliers-all-hired')
        events.add_subscriber(self._on_my_suppliers_failed_to_hire, 'my-suppliers-failed-to-hire')
        if not fire_hire.IsAllHired():
            lg.warn('service_list_files() can not start right now, not all suppliers hired yet')
            return False
        return True

    def stop(self):
        from main import events
        from customer import list_files_orator
        events.remove_subscriber(self._on_my_suppliers_failed_to_hire, 'my-suppliers-failed-to-hire')
        events.remove_subscriber(self._on_my_suppliers_all_hired, 'my-suppliers-all-hired')
        list_files_orator.Destroy()
        return True

    def _on_my_suppliers_all_hired(self, evt):
        from logs import lg
        from services import driver
        if not driver.is_on('service_list_files'):
            lg.info('all my suppliers are hired, starting service_list_files()')
            driver.start_single('service_list_files')

    def _on_my_suppliers_failed_to_hire(self, evt):
        from logs import lg
        from services import driver
        if driver.is_on('service_list_files'):
            lg.info('my suppliers failed to hire, stopping service_list_files()')
            driver.stop_single('service_list_files')
