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

import time
import requests

from ..testsupport import tunnel_url


def test_customer_family_published_for_customer_1():
    count = 0
    while True:
        if count > 10:
            assert False, 'customer family was not published correctly in DHT after many attempts'
            return 
        response = requests.get(url=tunnel_url('customer_1', 'supplier/list/dht/v1'))
        assert response.status_code == 200
        print('\n\n%r' % response.json())
        assert response.json()['status'] == 'OK', response.json()
        if not response.json()['result']:
            count += 1
            time.sleep(5)
            continue
        if len(response.json()['result']['suppliers']) < 2 or '' in response.json()['result']['suppliers']:
            count += 1
            time.sleep(5)
            continue
        assert response.json()['result']['customer_idurl'] == 'http://is:8084/customer_1.xml', response.json()['result']['customer_idurl']
        assert response.json()['result']['ecc_map'] == 'ecc/2x2', response.json()['result']['ecc_map']
        break


def test_customer_family_increase_for_customer_4():
    count = 0
    while True:
        if count > 10:
            assert False, 'customer family was not published correctly in DHT after many attempts'
            return 
        response = requests.get(url=tunnel_url('customer_4', 'supplier/list/dht/v1'))
        assert response.status_code == 200
        print('\n\n%r' % response.json())
        assert response.json()['status'] == 'OK', response.json()
        if not response.json()['result']:
            count += 1
            time.sleep(5)
            continue
        if len(response.json()['result']['suppliers']) < 2 or '' in response.json()['result']['suppliers']:
            count += 1
            time.sleep(5)
            continue
        assert response.json()['result']['customer_idurl'] == 'http://is:8084/customer_4.xml', response.json()['result']['customer_idurl']
        assert response.json()['result']['ecc_map'] == 'ecc/2x2', response.json()['result']['ecc_map']
        break

    response = requests.post(
        url=tunnel_url('customer_4', '/config/set/v1'),
        json={
            'key': 'services/customer/suppliers-number',
            'value': '4',
        },
    )
    assert response.status_code == 200
    print('\n\n%r' % response.json())
    assert response.json()['status'] == 'OK', response.json()

    count = 0
    while True:
        if count > 60:
            assert False, 'customer family was not published correctly in DHT after many attempts'
            return 
        response = requests.get(url=tunnel_url('customer_4', 'supplier/list/dht/v1'))
        assert response.status_code == 200
        print('\n\n%r' % response.json())
        assert response.json()['status'] == 'OK', response.json()
        if not response.json()['result']:
            count += 1
            time.sleep(5)
            continue
        if len(response.json()['result']['suppliers']) < 4 or '' in response.json()['result']['suppliers']:
            count += 1
            time.sleep(5)
            continue
        assert response.json()['result']['customer_idurl'] == 'http://is:8084/customer_4.xml', response.json()['result']['customer_idurl']
        assert response.json()['result']['ecc_map'] == 'ecc/4x4', response.json()['result']['ecc_map']
        break
