#!/usr/bin/env python
# test_service_proxy_server.py
#
# Copyright (C) 2008 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (test_service_proxy_server.py) is part of BitDust Software.
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

from testsupport import request_get


def test_customer_1_search_customer_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    response = request_get('customer-1', f'user/search/customer-2/v1', timeout=30)
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result']['nickname'] == 'customer-2'
    assert response.json()['result']['result'] == 'exist'


def test_customer_1_search_user_doesnt_exists():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    response = request_get('customer-1', f'user/search/user_name_not_exist/v1', timeout=30)
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result']['nickname'] == 'user_name_not_exist'
    assert response.json()['result']['result'] == 'not exist'


def test_customer_1_observe_customer_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    response = request_get('customer-1', f'user/observe/customer-2/v1', timeout=30)
    assert response.json()['status'] == 'OK', response.json()
    assert len(response.json()['result']) == 1
    assert response.json()['result'][0]['nickname'] == 'customer-2'
    assert response.json()['result'][0]['result'] == 'exist'
