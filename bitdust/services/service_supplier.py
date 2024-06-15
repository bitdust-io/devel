#!/usr/bin/python
# service_supplier.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_supplier.py) is part of BitDust Software.
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

module:: service_supplier
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return SupplierService()


class SupplierService(LocalService):

    service_name = 'service_supplier'
    config_path = 'services/supplier/enabled'

    def dependent_on(self):
        return [
            'service_keys_registry',
        ]

    def installed(self):
        from bitdust.userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def attached_dht_layers(self):
        from bitdust.dht import dht_records
        return [
            dht_records.LAYER_SUPPLIERS,
        ]

    def start(self):
        from bitdust.supplier import customer_space
        customer_space.init()
        return True

    def stop(self):
        from bitdust.supplier import customer_space
        customer_space.shutdown()
        return True

    def request(self, json_payload, newpacket, info):
        from bitdust.supplier import customer_space
        return customer_space.on_service_supplier_request(json_payload, newpacket, info)

    def cancel(self, json_payload, newpacket, info):
        from bitdust.supplier import customer_space
        return customer_space.on_service_supplier_cancel(json_payload, newpacket, info)
