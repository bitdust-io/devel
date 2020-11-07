#!/usr/bin/python
# service_my_data.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_my_data.py) is part of BitDust Software.
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

module:: service_my_data
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return MyDataService()


class MyDataService(LocalService):

    service_name = 'service_my_data'
    config_path = 'services/my-data/enabled'

    last_time_keys_synchronized = None

    def dependent_on(self):
        return [
            'service_keys_storage',
        ]

    def init(self, **kwargs):
        from main import events
        events.add_subscriber(self._on_my_storage_ready, 'my-storage-ready')
        events.add_subscriber(self._on_my_storage_not_ready_yet, 'my-storage-not-ready-yet')

    def shutdown(self):
        from main import events
        events.remove_subscriber(self._on_my_storage_not_ready_yet, 'my-storage-not-ready-yet')
        events.remove_subscriber(self._on_my_storage_ready, 'my-storage-ready')

    def start(self):
        from twisted.internet.defer import Deferred
        from logs import lg
        from storage import keys_synchronizer
        from storage import index_synchronizer
        self.starting_deferred = Deferred()
        self.starting_deferred.addErrback(lambda err: lg.warn('service %r was not started: %r' % (
            self.service_name, err.getErrorMessage() if err else 'unknown reason')))
        if keys_synchronizer.is_synchronized() and index_synchronizer.is_synchronized():
            if not self.starting_deferred.called:
                self.starting_deferred.callback(True)
        else:
            lg.warn('can not start service_my_data right now, keys_synchronizer.is_synchronized=%r index_synchronizer.is_synchronized=%r' % (
                keys_synchronizer.is_synchronized(), index_synchronizer.is_synchronized()))
        return self.starting_deferred

    def stop(self):
        return True

    def health_check(self):
        return True

    def _on_my_storage_ready(self, evt):
        from logs import lg
        from services import driver
        if self.starting_deferred:
            if not self.starting_deferred.called:
                self.starting_deferred.callback(True)
            self.starting_deferred = None
        if driver.is_enabled('service_my_data'):
            if not driver.is_started('service_my_data'):
                lg.info('my storage is ready, starting service_my_data()')
                driver.start_single('service_my_data')

    def _on_my_storage_not_ready_yet(self, evt):
        from logs import lg
        from services import driver
        if self.starting_deferred:
            if not self.starting_deferred.called:
                self.starting_deferred.errback(Exception('my storage is not ready yet'))
            self.starting_deferred = None
        if driver.is_enabled('service_my_data'):
            if not driver.is_started('service_my_data'):
                lg.info('my storage is not ready yet, stopping service_my_data()')
                driver.stop_single('service_my_data')
