#!/usr/bin/env python
# test_dht.py
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
#
# This file (test_dht.py) is part of BitDust Software.
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
"""
SCENARIO 1: user can search another user by nickname

SCENARIO 2: user is able to detect external IP

SCENARIO 6: users are able to use DHT network to store data

"""

import os
import pytest

from testsupport import set_active_scenario  # @UnresolvedImport
import keywords as kw  # @UnresolvedImport
import scenarios  # @UnresolvedImport


def test_dht():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    prepare()

    #--- SCENARIO 1: user can search another user by nickname
    scenarios.scenario1()

    #--- SCENARIO 2: user is able to detect external IP
    scenarios.scenario2()

    #--- SCENARIO 6: users are able to use DHT network to store data
    scenarios.scenario6()


#------------------------------------------------------------------------------


def prepare():
    set_active_scenario('PREPARE')
    kw.wait_suppliers_connected(scenarios.CUSTOMERS_IDS_12, expected_min_suppliers=2, expected_max_suppliers=2)
    kw.wait_service_state(scenarios.SUPPLIERS_IDS_12, 'service_supplier', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_customer', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_shared_data', 'ON')
    # kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_personal_messages', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_private_groups', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_message_history', 'ON')
    kw.wait_packets_finished(scenarios.CUSTOMERS_IDS_12 + scenarios.SUPPLIERS_IDS_12)
