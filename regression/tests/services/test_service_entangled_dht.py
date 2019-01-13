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

import requests

from ..testsupport import tunnel_url


def read_value(node, key, expected_value, ):
    response = requests.get(tunnel_url(node, 'dht/value/get/v1?key=%s' % key))
    assert response.json()['status'] == 'OK', response.json()
    assert len(response.json()['result']) > 0, response.json()
    assert response.json()['result'][0]['key'] == key, response.json()
    if expected_value == 'not_exist':
        assert 'value' not in response.json()['result'][0], response.json()
        assert len(response.json()['result'][0]['nodes']) > 0, response.json()
    else:
        assert 'value' in response.json()['result'][0], response.json()
        assert response.json()['result'][0]['value'] == expected_value, response.json()


def write_value(node, key, value):
    response = requests.post(
        url=tunnel_url(node, 'dht/value/set/v1'),
        json={
            'key': key,
            'value': value,
        },
    )
    assert response.json()['status'] == 'OK', response.json()
    assert len(response.json()['result']) > 0, response.json()
    assert response.json()['result'][0]['key'] == key, response.json()
    assert 'value' in response.json()['result'][0], response.json()
    assert response.json()['result'][0]['value'] == value, response.json()
    assert len(response.json()['result'][0]['nodes']) > 0, response.json()


def test_get_value_not_exist_customer_1():
    read_value(
        node='customer_1',
        key='value_not_exist_customer_1',
        expected_value='not_exist',
    )


def test_set_value_customer_1_and_get_value_customer_1():
    write_value(
        node='customer_1',
        key='test_key_1_customer_1',
        value={'data': 'test_data_1_customer_1', },
    )
    read_value(
        node='customer_1',
        key='test_key_1_customer_1',
        expected_value={'data': 'test_data_1_customer_1', },
    )


def test_set_value_customer_2_and_get_value_customer_3():
    write_value(
        node='customer_2',
        key='test_key_1_customer_2',
        value={'data': 'test_data_1_customer_2', },
    )
    read_value(
        node='customer_3',
        key='test_key_1_customer_2',
        expected_value={'data': 'test_data_1_customer_2', },
    )
