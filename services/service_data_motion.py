#!/usr/bin/python
# service_data_motion.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_data_motion.py) is part of BitDust Software.
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

module:: service_data_motion
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return DataMotionService()


class DataMotionService(LocalService):

    service_name = 'service_data_motion'
    config_path = 'services/data-motion/enabled'

    def dependent_on(self):
        return [
            'service_employer',
        ]

    def start(self):
        from logs import lg
        from main import events
        from customer import fire_hire
        from customer import io_throttle
        from customer import data_sender
        from customer import data_receiver
        io_throttle.init()
        data_sender.A('init')
        data_receiver.A('init')
        events.add_subscriber(self._on_my_suppliers_all_hired, 'my-suppliers-all-hired')
        events.add_subscriber(self._on_my_suppliers_failed_to_hire, 'my-suppliers-failed-to-hire')
        if not fire_hire.IsAllHired():
            lg.warn('service_data_motion() can not start right now, not all suppliers hired yet')
            return False
        return True

    def stop(self):
        from main import events
        from customer import io_throttle
        from customer import data_sender
        from customer import data_receiver
        events.remove_subscriber(self._on_my_suppliers_failed_to_hire, 'my-suppliers-failed-to-hire')
        events.remove_subscriber(self._on_my_suppliers_all_hired, 'my-suppliers-all-hired')
        data_receiver.A('shutdown')
        data_sender.SetShutdownFlag()
        data_sender.A('shutdown')
        io_throttle.shutdown()
        return True

    def health_check(self):
        return True

    def _on_my_suppliers_all_hired(self, evt):
        from logs import lg
        from services import driver
        if not driver.is_on('service_data_motion'):
            lg.info('all my suppliers are hired, starting service_data_motion()')
            driver.start_single('service_data_motion')

    def _on_my_suppliers_failed_to_hire(self, evt):
        from logs import lg
        from services import driver
        if driver.is_on('service_data_motion'):
            lg.info('my suppliers failed to hire, stopping service_data_motion()')
            driver.stop_single('service_data_motion')
