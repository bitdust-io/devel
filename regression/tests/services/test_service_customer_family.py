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
import time
import requests

from ..testsupport import tunnel_url


def validate_customer_family(customer_node, observer_node, expected_ecc_map, expected_suppliers_number, retries=10, sleep_sec=3, accepted_mistakes=0):

    def _validate(obs):
        response = None
        count = 0
        while True:
            if count >= retries:
                print('\nfailed after %d retries' % count)
                return False
            response = requests.get(url=tunnel_url(obs, 'supplier/list/dht/v1?id=%s@is_8084' % customer_node))
            assert response.status_code == 200
            assert response.json()['status'] == 'OK', response.json()
            # print('\nsupplier/list/dht/v1?id=%s from %s\n%s\n' % (customer_node, obs, pprint.pformat(response.json())))
            if not response.json()['result']:
                count += 1
                time.sleep(sleep_sec)
                continue
            ss = response.json()['result']['suppliers']
            if len(ss) != expected_suppliers_number or (ss.count('') > accepted_mistakes and expected_suppliers_number > 2):
                print('\n%r' % response.json())
                count += 1
                time.sleep(sleep_sec)
                continue
            assert response.json()['result']['customer_idurl'] == 'http://is:8084/%s.xml' % customer_node, response.json()['result']['customer_idurl']
            assert response.json()['result']['ecc_map'] == expected_ecc_map, response.json()['result']['ecc_map']
            break
        return True

    if not _validate(observer_node):
        if not _validate('supplier_1'):
            assert False, 'customer family [%s] [%s] was not re-published correctly, observer [%s] and another node still see wrong info' % (
                customer_node, expected_ecc_map, observer_node, )

    return True


def test_customer_family_published_for_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    validate_customer_family(
        customer_node='customer_1',
        observer_node='customer_1',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    validate_customer_family(
        customer_node='customer_1',
        observer_node='customer_2',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )


def test_customer_family_increase_for_customer_4():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    validate_customer_family(
        customer_node='customer_4',
        observer_node='customer_4',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    validate_customer_family(
        customer_node='customer_4',
        observer_node='customer_1',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    response = requests.post(
        url=tunnel_url('customer_4', '/config/set/v1'),
        json={
            'key': 'services/customer/suppliers-number',
            'value': '4',
        },
    )

    assert response.status_code == 200
    print('\n/config/set/v1 services/customer/suppliers-number 4\n%r' % response.json())
    assert response.json()['status'] == 'OK', response.json()

    validate_customer_family(
        customer_node='customer_4',
        observer_node='customer_4',
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    validate_customer_family(
        customer_node='customer_4',
        observer_node='customer_1',
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )


def test_customer_family_decrease_for_customer_5():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    validate_customer_family(
        customer_node='customer_5',
        observer_node='customer_5',
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    validate_customer_family(
        customer_node='customer_5',
        observer_node='customer_3',
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    response = requests.post(
        url=tunnel_url('customer_5', '/config/set/v1'),
        json={
            'key': 'services/customer/suppliers-number',
            'value': '2',
        },
    )

    assert response.status_code == 200
    print('\n/config/set/v1 services/customer/suppliers-number 2\n%r' % response.json())
    assert response.json()['status'] == 'OK', response.json()

    validate_customer_family(
        customer_node='customer_5',
        observer_node='customer_5',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    validate_customer_family(
        customer_node='customer_5',
        observer_node='customer_3',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
