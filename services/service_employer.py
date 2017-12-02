#!/usr/bin/python
# service_employer.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (service_employer.py) is part of BitDust Software.
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

module:: service_employer
"""

from services.local_service import LocalService


def create_service():
    return EmployerService()


class EmployerService(LocalService):

    service_name = 'service_employer'
    config_path = 'services/employer/enabled'

    def dependent_on(self):
        return ['service_customer',
                'service_nodes_lookup',
                ]

    def start(self):
        from customer import fire_hire
        from main.config import conf
        fire_hire.A('init')
        conf().addCallback('services/customer/suppliers-number',
                           self._on_suppliers_number_modified)
        conf().addCallback('services/customer/needed-space',
                           self._on_needed_space_modified)
        return True

    def stop(self):
        from customer import fire_hire
        from main.config import conf
        conf().removeCallback('services/customer/suppliers-number')
        conf().removeCallback('services/customer/needed-space')
        fire_hire.Destroy()
        return True

    def _on_suppliers_number_modified(self, path, value, oldvalue, result):
        from customer import fire_hire
        fire_hire.ClearLastFireTime()
        fire_hire.A('restart')

    def _on_needed_space_modified(self, path, value, oldvalue, result):
        from customer import fire_hire
        fire_hire.ClearLastFireTime()
        fire_hire.A('restart')
