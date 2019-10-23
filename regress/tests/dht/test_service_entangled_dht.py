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
import time
import pytest

from keywords import dht_value_get_v1, dht_value_set_v1


def test_dht_get_value_not_exist_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    dht_value_get_v1(
        node='customer-1',
        key='value_not_exist_customer_1',
        expected_data='not_exist',
    )


def test_dht_set_value_customer_1_and_get_value_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    dht_value_set_v1(
        node='customer-1',
        key='test_key_1_customer_1',
        new_data='test_data_1_customer_1',
    )
    dht_value_get_v1(
        node='customer-1',
        key='test_key_1_customer_1',
        expected_data=['test_data_1_customer_1', ],
    )


def test_dht_set_value_customer_1_and_get_value_supplier_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    dht_value_set_v1(
        node='customer-1',
        key='test_key_2_customer_1',
        new_data='test_data_2_customer_1',
    )
    dht_value_get_v1(
        node='supplier-1',
        key='test_key_2_customer_1',
        expected_data=['test_data_2_customer_1', ],
    )


def test_dht_set_value_customer_2_and_get_value_customer_3():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    dht_value_set_v1(
        node='customer-2',
        key='test_key_1_customer_2',
        new_data='test_data_1_customer_2',
    )
    dht_value_get_v1(
        node='customer-3',
        key='test_key_1_customer_2',
        expected_data=['test_data_1_customer_2', ],
    )


def test_dht_get_value_multiple_nodes():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    dht_value_set_v1(
        node='supplier-1',
        key='test_key_1_supplier_1',
        new_data='test_data_1_supplier_1',
    )
    time.sleep(2)
    for node in ['customer-1', 'customer-2', 'customer-3', ]:
        dht_value_get_v1(
            node=node,
            key='test_key_1_supplier_1',
            expected_data=['test_data_1_supplier_1', ],
        )

def test_dht_write_value_multiple_nodes():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    for node in ['supplier-1', 'supplier-2', ]:
        dht_value_set_v1(
            node=node,
            key='test_key_2_shared',
            new_data=f'test_data_2_shared_%s' % (node.replace('-', '_')),
        )
        time.sleep(2)
    for node in ['customer-1', 'customer-2', 'customer-3', ]:
        dht_value_get_v1(
            node=node,
            key='test_key_2_shared',
            expected_data=['test_data_2_shared_supplier_1', 'test_data_2_shared_supplier_2', 'test_data_2_shared_supplier_3'],
        )
