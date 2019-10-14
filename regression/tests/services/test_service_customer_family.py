#!/usr/bin/env python
# test_service_customer_family.py
#
# Copyright (C) 2008-2019 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (test_service_customer_family.py) is part of BitDust Software.
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

import os
import pytest

from ..keywords import supplier_list_dht_v1, config_set_v1, supplier_list_v1, service_info_v1


def test_customer_family_increase_for_customer_4():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    supplier_list_v1('customer_4', expected_min_suppliers=2, expected_max_suppliers=2)
    supplier_list_dht_v1(
        customer_node='customer_4',
        observer_node='customer_4',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    supplier_list_dht_v1(
        customer_node='customer_4',
        observer_node='customer_1',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    service_info_v1('customer_4', 'service_shared_data', 'ON')

    config_set_v1('customer_4', 'services/customer/suppliers-number', '4')
    supplier_list_dht_v1(
        customer_node='customer_4',
        observer_node='customer_4',
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    supplier_list_dht_v1(
        customer_node='customer_4',
        observer_node='customer_1',
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    supplier_list_v1('customer_4', expected_min_suppliers=4, expected_max_suppliers=4)
    service_info_v1('customer_4', 'service_shared_data', 'ON')

    config_set_v1('customer_4', 'services/customer/suppliers-number', '2')
    supplier_list_dht_v1(
        customer_node='customer_4',
        observer_node='customer_4',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    supplier_list_dht_v1(
        customer_node='customer_4',
        observer_node='customer_1',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    supplier_list_v1('customer_4', expected_min_suppliers=2, expected_max_suppliers=2)
    service_info_v1('customer_4', 'service_shared_data', 'ON')


# def test_customer_family_decrease_for_customer_5():
#     if os.environ.get('RUN_TESTS', '1') == '0':
#         return pytest.skip()  # @UndefinedVariable
# 
#     supplier_list_v1('customer_5', expected_min_suppliers=4, expected_max_suppliers=4)
#     supplier_list_dht_v1(
#         customer_node='customer_5',
#         observer_node='customer_5',
#         expected_ecc_map='ecc/4x4',
#         expected_suppliers_number=4,
#         # accepted_mistakes=0,
#     )
#     supplier_list_dht_v1(
#         customer_node='customer_5',
#         observer_node='customer_3',
#         expected_ecc_map='ecc/4x4',
#         expected_suppliers_number=4,
#         # accepted_mistakes=0,
#     )
#     service_info_v1('customer_5', 'service_shared_data', 'ON')
# 
#     config_set_v1('customer_5', 'services/customer/suppliers-number', '2')
#     supplier_list_dht_v1(
#         customer_node='customer_5',
#         observer_node='customer_5',
#         expected_ecc_map='ecc/2x2',
#         expected_suppliers_number=2,
#     )
#     supplier_list_dht_v1(
#         customer_node='customer_5',
#         observer_node='customer_3',
#         expected_ecc_map='ecc/2x2',
#         expected_suppliers_number=2,
#     )
#     supplier_list_v1('customer_5', expected_min_suppliers=2, expected_max_suppliers=2)
#     service_info_v1('customer_5', 'service_shared_data', 'ON')
# 
#     config_set_v1('customer_5', 'services/customer/suppliers-number', '4')
#     supplier_list_dht_v1(
#         customer_node='customer_5',
#         observer_node='customer_5',
#         expected_ecc_map='ecc/4x4',
#         expected_suppliers_number=4,
#     )
#     supplier_list_dht_v1(
#         customer_node='customer_5',
#         observer_node='customer_3',
#         expected_ecc_map='ecc/4x4',
#         expected_suppliers_number=4,
#     )
#     supplier_list_v1('customer_5', expected_min_suppliers=4, expected_max_suppliers=4)
#     service_info_v1('customer_5', 'service_shared_data', 'ON')
