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
            'service_customer',
        ]

    def start(self):
        from customer import io_throttle
        from customer import data_sender
        from customer import data_receiver
        io_throttle.init()
        data_sender.A('init')
        data_receiver.A('init')
        return True

    def stop(self):
        from customer import io_throttle
        from customer import data_sender
        from customer import data_receiver
        data_receiver.A('shutdown')
        data_sender.SetShutdownFlag()
        data_sender.A('shutdown')
        io_throttle.shutdown()
        return True

    def health_check(self):
        return True
