#!/usr/bin/env python
# test_service_customer_family.py
#
# Copyright (C) 2008-2018 Stanislav Evseev, Veselin Penev  https://bitdust.io
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
import requests

from ..testsupport import tunnel_url


# TODO: keep this list up to date with docker-compose links
VALIDATORS_NODES = [
    'customer_1',
    'customer_2',
    'customer_3',
    'customer_4',
    'customer_5',
    'supplier_1',
    'supplier_2',
    'supplier_3',
    'supplier_4',
    'supplier_5',
    'supplier_6',
    'supplier_7',
    'supplier_8',
    'proxy_server_1',
    'proxy_server_2',
    'stun_1',
    'stun_2',
    'dht_seed_1',
    'dht_seed_2',
]


def read_value(node, key, expected_data, record_type='skip_validation', ):
    response = requests.get(tunnel_url(node, 'dht/value/get/v1?record_type=%s&key=%s' % (record_type, key, )))
    assert response.status_code == 200
    # print('\n\ndht/value/get/v1?key=%s from %s\n%s\n' % (key, node, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    assert len(response.json()['result']) > 0, response.json()
    assert response.json()['result'][0]['key'] == key, response.json()
    if expected_data == 'not_exist':
        assert response.json()['result'][0]['read'] == 'failed', response.json()
        assert 'value' not in response.json()['result'][0], response.json()
        assert len(response.json()['result'][0]['closest_nodes']) > 0, response.json()
    else:
        if response.json()['result'][0]['read'] == 'failed':
            print('first request failed, retry one more time')
            response = requests.get(tunnel_url(node, 'dht/value/get/v1?record_type=%s&key=%s' % (record_type, key, )))
            assert response.status_code == 200
            assert response.json()['status'] == 'OK', response.json()
        assert response.json()['result'][0]['read'] == 'success', response.json()
        assert 'value' in response.json()['result'][0], response.json()
        assert response.json()['result'][0]['value']['data'] == expected_data, response.json()
        assert response.json()['result'][0]['value']['key'] == key, response.json()
        assert response.json()['result'][0]['value']['type'] == record_type, response.json()


def write_value(node, key, new_data, record_type='skip_validation', ):
    response = requests.post(
        url=tunnel_url(node, 'dht/value/set/v1'),
        json={
            'key': key,
            'record_type': record_type,
            'value': {
                'data': new_data,
                'type': record_type,
                'key': key,
            },
        },
    )
    assert response.status_code == 200
    # print('\n\ndht/value/set/v1 key=%s value=%s from %s\n%s\n' % (key, new_data, node, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    assert len(response.json()['result']) > 0, response.json()
    assert response.json()['result'][0]['write'] == 'success', response.json()
    assert response.json()['result'][0]['key'] == key, response.json()
    assert response.json()['result'][0]['value']['data'] == new_data, response.json()
    assert response.json()['result'][0]['value']['key'] == key, response.json()
    assert response.json()['result'][0]['value']['type'] == record_type, response.json()
    assert len(response.json()['result'][0]['closest_nodes']) > 0, response.json()


def test_dht_get_value_not_exist_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    read_value(
        node='customer_1',
        key='value_not_exist_customer_1',
        expected_data='not_exist',
    )


def test_dht_set_value_customer_1_and_get_value_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    write_value(
        node='customer_1',
        key='test_key_1_customer_1',
        new_data='test_data_1_customer_1',
    )
    read_value(
        node='customer_1',
        key='test_key_1_customer_1',
        expected_data='test_data_1_customer_1',
    )


def test_dht_set_value_customer_2_and_get_value_customer_3():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    write_value(
        node='customer_2',
        key='test_key_1_customer_2',
        new_data='test_data_1_customer_2',
    )
    read_value(
        node='customer_3',
        key='test_key_1_customer_2',
        expected_data='test_data_1_customer_2',
    )


def test_dht_get_value_all_nodes():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    write_value(
        node='supplier_1',
        key='test_key_1_supplier_1',
        new_data='test_data_1_supplier_1',
    )
    write_value(
        node='supplier_1',
        key='test_key_2_supplier_1',
        new_data='test_data_2_supplier_1',
    )
    write_value(
        node='supplier_1',
        key='test_key_3_supplier_1',
        new_data='test_data_3_supplier_1',
    )
    write_value(
        node='supplier_1',
        key='test_key_4_supplier_1',
        new_data='test_data_4_supplier_1',
    )
    write_value(
        node='supplier_1',
        key='test_key_5_supplier_1',
        new_data='test_data_5_supplier_1',
    )
    for node in VALIDATORS_NODES:
        read_value(
            node=node,
            key='test_key_1_supplier_1',
            expected_data='test_data_1_supplier_1',
        )
        read_value(
            node=node,
            key='test_key_2_supplier_1',
            expected_data='test_data_2_supplier_1',
        )
        read_value(
            node=node,
            key='test_key_3_supplier_1',
            expected_data='test_data_3_supplier_1',
        )
        read_value(
            node=node,
            key='test_key_4_supplier_1',
            expected_data='test_data_4_supplier_1',
        )
        read_value(
            node=node,
            key='test_key_5_supplier_1',
            expected_data='test_data_5_supplier_1',
        )
