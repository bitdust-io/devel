#!/usr/bin/env python
# test_service_my_ip_port.py
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
#
# This file (test_service_my_ip_port.py) is part of BitDust Software.
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

import keywords as kw


def test_customer_1_connect_to_message_broker():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)

    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')

    kw.service_info_v1('customer-1', 'service_private_groups', 'ON')

    group_key_id = kw.group_create_v1('customer-1')
    
    kw.group_open_v1('customer-1', group_key_id)
    
    kw.group_share_v1('customer-1', group_key_id, 'customer-2@id-b_8084')

    kw.group_open_v1('customer-2', group_key_id)
