#!/usr/bin/env python
# test_service_private_messages.py
#
# Copyright (C) 2008-2019 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (test_service_private_messages.py) is part of BitDust Software.
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
import base64
from threading import Timer

from ..keywords import message_send_v1, message_receive_v1, service_info_v1


def test_customer_1_send_message_to_customer_2():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    service_info_v1('customer_1', 'service_private_messages', 'ON')

    random_string = base64.b32encode(os.urandom(20)).decode()
    random_message = {
        'random_message': random_string,
    }
    # send message in different thread to get one in blocked `receive` call
    t = Timer(2.0, message_send_v1, ['customer_1', 'master$customer_2@is_8084', random_message, ])
    t.start()
    message_receive_v1('customer_2', expected_data=random_message)
