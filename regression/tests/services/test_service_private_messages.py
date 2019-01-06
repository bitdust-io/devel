#!/usr/bin/env python
# test_service_private_messages.py
#
# Copyright (C) 2008-2018 Stanislav Evseev, Veselin Penev  https://bitdust.io
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
import base64
from threading import Timer
import requests

from ..testsupport import tunnel_url


def send_message(random_message):
    response = requests.post(
        url=tunnel_url('customer_1', 'message/send/v1'),
        json={
            'id': 'master$customer_2@is_8084',
            'data': {
                'random_message': random_message,
            },
        }
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()


def test_send_message_customer_1_to_customer_2():
    random_message = base64.b32encode(os.urandom(20)).decode()

    #: send message in different thread to get one in blocked `receive` call
    t = Timer(2.0, send_message, [random_message, ])
    t.start()

    response = requests.get(
        url=tunnel_url('customer_2', 'message/receive/test_consumer/v1'),
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result'][0]['data']['random_message'] == random_message, response.json()
