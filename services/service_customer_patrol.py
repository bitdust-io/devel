#!/usr/bin/python
# service_customer_patrol.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_customer_patrol.py) is part of BitDust Software.
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

module:: service_customer_patrol
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return CustomerPatrolService()


class CustomerPatrolService(LocalService):

    service_name = 'service_customer_patrol'
    config_path = 'services/customer-patrol/enabled'

    def dependent_on(self):
        return [
            'service_supplier',
        ]

    def start(self):
        from supplier import customers_rejector
        from main.config import conf
        from supplier import local_tester
        customers_rejector.A('restart')
        conf().addCallback('services/supplier/donated-space',
                           self._on_donated_space_modified)
        local_tester.init()
        return True

    def stop(self):
        from supplier import customers_rejector
        from main.config import conf
        from supplier import local_tester
        local_tester.shutdown()
        conf().removeCallback('services/supplier/donated-space')
        customers_rejector.Destroy()
        return True

    def health_check(self):
        return True

    def _on_donated_space_modified(self, path, value, oldvalue, result):
        from supplier import customers_rejector
        customers_rejector.A('restart')
