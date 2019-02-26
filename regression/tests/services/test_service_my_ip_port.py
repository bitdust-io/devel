#!/usr/bin/env python
# test_service_my_ip_port.py
#
# Copyright (C) 2008-2018 Veselin Penev  https://bitdust.io
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
import requests

from ..testsupport import tunnel_url


def test_network_stun_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable
    response = requests.get(url=tunnel_url('customer_1', 'network/stun/v1'))
    assert response.status_code == 200
    print('\n\n%r' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result'][0]['result'] == 'stun-success'
