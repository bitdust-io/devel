#!/usr/bin/env python
# test_suppliers5.py
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
#
# This file (test_suppliers5.py) is part of BitDust Software.
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
SCENARIO 4: customer-1 share files to customer-2

SCENARIO 7: customer-1 upload and download file encrypted with his master key

SCENARIO 14: customer-1 replace supplier at position 0 by random node

SCENARIO 15: customer-1 switch supplier at position 1 to specific node

SCENARIO 16: customer-1 increase and decrease suppliers amount

SCENARIO 23: customer-1 able to upload/download files when one supplier is down

"""

import os
import pytest

from testsupport import set_active_scenario  # @UnresolvedImport

import keywords as kw  # @UnresolvedImport
import scenarios  # @UnresolvedImport


def test_suppliers5():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    prepare()

    #--- SCENARIO 7: customer-1 upload/download with master key
    customer_1_file_info = scenarios.scenario7()

    #--- SCENARIO 4: customer-1 share files to customer-2
    customer_1_shared_file_info, _ = scenarios.scenario4()

    #--- SCENARIO 23: customer-1 able to upload/download files when one supplier is down
    scenarios.scenario23(customer_1_file_info, customer_1_shared_file_info)

    #--- SCENARIO 14: customer-1 replace supplier at position 0 by random node
    scenarios.scenario14(customer_1_file_info, customer_1_shared_file_info)

    #--- SCENARIO 15: customer-1 switch supplier at position 1 to specific node
    scenarios.scenario15(customer_1_file_info, customer_1_shared_file_info)

    #--- SCENARIO 16: customer-1 increase and decrease suppliers amount
    scenarios.scenario16()


#------------------------------------------------------------------------------


def prepare():
    set_active_scenario('PREPARE')
    kw.wait_suppliers_connected(scenarios.CUSTOMERS_IDS_12, expected_min_suppliers=2, expected_max_suppliers=2)
    kw.wait_service_state(scenarios.SUPPLIERS_IDS, 'service_supplier', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_customer', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_shared_data', 'ON')
    # kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_personal_messages', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_private_groups', 'ON')
    kw.wait_service_state(scenarios.CUSTOMERS_IDS_12, 'service_message_history', 'ON')
    kw.wait_packets_finished(scenarios.PROXY_IDS + scenarios.CUSTOMERS_IDS_12 + scenarios.SUPPLIERS_IDS)
