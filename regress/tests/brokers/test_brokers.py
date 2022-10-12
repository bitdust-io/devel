#!/usr/bin/env python
# test_brokers.py
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
#
# This file (test_brokers.py) is part of BitDust Software.
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
SCENARIO 3: customer-1 is able to send private message to customer-2

SCENARIO 22: broker-2 was restarted quickly but still is connected to the stream

SCENARIO 8: customer-3 receive all archived messages from message broker

SCENARIO 18: customer-2 sent message to the group but active broker-1 is offline

SCENARIO 21: broker-1 was stopped and started again but disconnected from previous streams

SCENARIO 20: customer-3 stopped and started again but still connected to the group

"""

import os
import pytest

from testsupport import set_active_scenario  # @UnresolvedImport
import keywords as kw  # @UnresolvedImport
import scenarios  # @UnresolvedImport


def test_brokers():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    prepare()

    #--- SCENARIO 3: customer-1 send private message to customer-2
    scenarios.scenario3()

    #--- SCENARIO 8: customer-3 receive all archived messages from message broker
    scenarios.scenario8()

    #--- SCENARIO 18: customer-2 sent message to the group but active broker-1 is offline
    scenarios.scenario18()

    #--- SCENARIO 21: broker-1 was stopped and started again but disconnected from previous streams
    scenarios.scenario21()

    #--- SCENARIO 20: customer-3 stopped and started again but still connected to the group
    scenarios.scenario20()

    #--- SCENARIO 22: customer-1 group chat with customer-2 but broker-2 was restarted quickly
    scenarios.scenario22()


#------------------------------------------------------------------------------


def prepare():
    set_active_scenario('PREPARE')
    kw.wait_suppliers_connected(scenarios.CUSTOMERS_IDS_123, expected_min_suppliers=2, expected_max_suppliers=2)
    kw.wait_service_state(scenarios.SUPPLIERS_IDS_12, 'service_supplier', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_123, 'service_customer', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_123, 'service_shared_data', 'ON')
    # kw.wait_service_state(scenarios.CUSTOMERS_IDS_123, 'service_personal_messages', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_123, 'service_private_groups', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_123, 'service_message_history', 'ON')
    kw.wait_service_state(scenarios.BROKERS_IDS, 'service_message_broker', 'ON')
    kw.wait_packets_finished(scenarios.CUSTOMERS_IDS_123 + scenarios.BROKERS_IDS + scenarios.SUPPLIERS_IDS_12)
