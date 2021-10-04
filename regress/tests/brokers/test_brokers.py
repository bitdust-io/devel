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

SCENARIO 8: customer-3 receive all archived messages from message broker


"""

import os
import pytest

from testsupport import set_active_scenario  # @UnresolvedImport
import keywords as kw  # @UnresolvedImport
import scenarios  # @UnresolvedImport

PROXY_IDS = []  # ['proxy-1', 'proxy-2', 'proxy-3', ]
SUPPLIERS_IDS = ['supplier-1', 'supplier-2', ]
CUSTOMERS_IDS = ['customer-1', 'customer-2', 'customer-3', ]
CUSTOMERS_IDS_SHORT = ['customer-1', 'customer-3', ]
BROKERS_IDS = ['broker-1', 'broker-2', 'broker-3', 'broker-4', ]

group_customers_2_4_messages = []
group_customers_1_2_3_messages = []

ssh_cmd_verbose = True


def test_brokers():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    prepare()

    #--- SCENARIO 3: customer-1 send private message to customer-2
    scenarios.scenario3()

    #--- SCENARIO 8: customer-3 receive all archived messages from message broker
    scenarios.scenario8()

#------------------------------------------------------------------------------

def prepare():
    set_active_scenario('PREPARE')
    kw.wait_suppliers_connected(CUSTOMERS_IDS, expected_min_suppliers=2, expected_max_suppliers=2)
    kw.wait_service_state(SUPPLIERS_IDS, 'service_supplier', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_customer', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_personal_messages', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_private_groups', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_message_history', 'ON')
    kw.wait_service_state(BROKERS_IDS, 'service_message_broker', 'ON')
    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS + SUPPLIERS_IDS)
