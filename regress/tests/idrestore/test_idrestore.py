#!/usr/bin/env python
# test_idrestore.py
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
#
# This file (test_idrestore.py) is part of BitDust Software.
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
SCENARIO 17: customer-restore recover identity from customer-2


"""

import os
import pytest

from testsupport import set_active_scenario  # @UnresolvedImport
import keywords as kw  # @UnresolvedImport
import scenarios  # @UnresolvedImport

PROXY_IDS = []
SUPPLIERS_IDS = ['supplier-1', 'supplier-2', ]
CUSTOMERS_IDS = ['customer-1', 'customer-2', ]

ssh_cmd_verbose = True


def test_idrestore():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    prepare()

    #--- SCENARIO 4: customer-1 share files to customer-2
    _, customer_2_shared_file_info = scenarios.scenario4()

    #--- SCENARIO 17: customer-2 went offline and customer-restore recover identity from customer-2
    scenarios.scenario17(customer_2_shared_file_info)

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
    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + SUPPLIERS_IDS)
