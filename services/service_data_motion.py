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

    def init(self, **kwargs):
        from main import events
        events.add_subscriber(self._on_my_suppliers_all_hired, 'my-suppliers-all-hired')
        events.add_subscriber(self._on_my_suppliers_yet_not_hired, 'my-suppliers-yet-not-hired')

    def shutdown(self):
        from main import events
        events.remove_subscriber(self._on_my_suppliers_yet_not_hired, 'my-suppliers-yet-not-hired')
        events.remove_subscriber(self._on_my_suppliers_all_hired, 'my-suppliers-all-hired')
    
    def start(self):
        from logs import lg
        from customer import fire_hire
        if not fire_hire.IsAllHired():
            lg.warn('service_data_motion() can not start right now, not all suppliers hired yet')
            return False
        from main import events
        from customer import io_throttle
        from customer import data_sender
        from customer import data_receiver
        io_throttle.init()
        data_sender.A('init')
        data_receiver.A('init')
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        return True

    def stop(self):
        from main import events
        from customer import io_throttle
        from customer import data_sender
        from customer import data_receiver
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
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
        if driver.is_enabled('service_data_motion'):
            lg.info('all my suppliers are hired, starting service_data_motion()')
            driver.start_single('service_data_motion')

    def _on_my_suppliers_yet_not_hired(self, evt):
        from logs import lg
        from services import driver
        if driver.is_enabled('service_data_motion'):
            lg.info('my suppliers failed to hire, stopping service_data_motion()')
            driver.stop_single('service_data_motion')

    def _on_identity_url_changed(self, evt):
        from logs import lg
        from userid import id_url
        from customer import io_throttle
        old_idurl = id_url.field(evt.data['old_idurl'])
        for supplier_idurl, supplier_queue in io_throttle.throttle().supplierQueues.items():
            if old_idurl == supplier_idurl:
                supplier_idurl.refresh()
                lg.info('found supplier idurl rotated in io_throttle: %r -> %r' % (
                    evt.data['old_idurl'], evt.data['new_idurl'], ))
            if old_idurl == supplier_queue.customerIDURL:
                supplier_queue.customerIDURL.refresh()
                lg.info('found customer idurl rotated in io_throttle %r supplier queue: %r -> %r' % (
                    supplier_idurl, evt.data['old_idurl'], evt.data['new_idurl'], ))
