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

from keywords import user_ping_v1


def test_ping_proxy_1_towards_proxy_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('proxy-1', 'proxy-2@id-b_8084')


def test_ping_proxy_2_towards_proxy_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('proxy-2', 'proxy-1@id-a_8084')


def test_ping_proxy_1_towards_customer_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('proxy-1', 'customer-2@id-b_8084')


def test_ping_customer_1_towards_proxy_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('customer-1', 'proxy-2@id-b_8084')


def test_ping_supplier_1_towards_supplier_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('supplier-1', 'supplier-2@id-b_8084')


def test_ping_supplier_2_towards_supplier_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('supplier-2', 'supplier-1@id-a_8084')


def test_ping_customer_1_towards_customer_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('customer-1', 'customer-2@id-b_8084')


def test_ping_customer_2_towards_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('customer-2', 'customer-1@id-a_8084')


def test_ping_customer_1_towards_supplier_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('customer-1', 'supplier-1@id-a_8084')


def test_ping_customer_1_towards_supplier_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('customer-1', 'supplier-2@id-b_8084')


def test_ping_supplier_2_towards_customer_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('supplier-2', 'customer-2@id-b_8084')


def test_ping_supplier_2_towards_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('supplier-2', 'customer-1@id-a_8084')


def test_ping_supplier_1_towards_customer_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    user_ping_v1('supplier-1', 'customer-2@id-b_8084')
