#!/usr/bin/env python
# test_identity_rotate_broker.py
#
# Copyright (C) 2008 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (test_identity_rotate_broker.py) is part of BitDust Software.
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
import threading

from testsupport import create_identity, connect_network

import keywords as kw


def test_identity_rotate_broker_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    # first create broker-1 identity and start the node, identity will be rotated later
    create_identity('broker-1', 'broker-1')

    connect_network('broker-1')

    r = kw.identity_get_v1('broker-1')
    broker_1_id = r['result']['global_id']
    broker_1_idurl = r['result']['idurl']

    kw.service_info_v1('broker-1', 'service_message_broker', 'ON')

    # prepare customer-1
    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-1', 'service_private_groups', 'ON')
    kw.packet_list_v1('customer-1', wait_all_finish=True)
    kw.transfer_list_v1('customer-1', wait_all_finish=True)

    # prepare customer-2
    kw.supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-2', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-2', 'service_private_groups', 'ON')
    kw.packet_list_v1('customer-2', wait_all_finish=True)
    kw.transfer_list_v1('customer-2', wait_all_finish=True)

    # disable broker-2 so that customer will only have choice to pick "desired" broker-1
    kw.service_stop_v1('broker-2', 'service_message_broker')

    # create group owned by customer-1 and join
    group_key_id = kw.group_create_v1('customer-1', label='TestGroup123')

    kw.group_join_v1('customer-1', group_key_id)

    group_info_active = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_active['state'] == 'IN_SYNC!'

    active_queue_id = group_info_active['active_queue_id']
    active_broker_id = group_info_active['active_broker_id']
    active_broker_name = active_broker_id.split('@')[0]

    assert active_broker_name == 'broker-1'
    assert active_broker_id == broker_1_id

    # enabled again broker-2 so that customers will be able to switch from broker-1 to broker-2
    kw.service_start_v1('broker-2', 'service_message_broker')

    assert active_queue_id in kw.queue_list_v1('broker-1', extract_ids=True)

    # share group key from customer-1 to customer-2, second member join the group
    kw.group_share_v1('customer-1', group_key_id, 'customer-2@id-b_8084')

    kw.group_join_v1('customer-2', group_key_id)

    assert kw.group_info_v1('customer-1', group_key_id)['result']['last_sequence_id'] == -1
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == -1

    # MESSAGE A: from customer 1 to the group, customers 1 and 2 must receive the message
    a_message_sent_from_customer_1 = {'random_message': 'MESSAGE_A_%s' % base64.b32encode(os.urandom(20)).decode(), }
    a_customer_1_receive_result = [None, ]
    a_customer_2_receive_result = [None, ]
    a_receive_customer_1 = threading.Timer(0, kw.message_receive_v1, [
        'customer-1', a_message_sent_from_customer_1, 'test_consumer', a_customer_1_receive_result, ])
    a_receive_customer_2 = threading.Timer(0, kw.message_receive_v1, [
        'customer-2', a_message_sent_from_customer_1, 'test_consumer', a_customer_2_receive_result, ])
    a_send_customer_1 = threading.Timer(0.2, kw.message_send_group_v1, [
        'customer-1', group_key_id, a_message_sent_from_customer_1, ])
    a_receive_customer_1.start()
    a_receive_customer_2.start()
    a_send_customer_1.start()
    a_receive_customer_1.join()
    a_receive_customer_2.join()
    a_send_customer_1.join()
    assert a_customer_1_receive_result[0]['result'][0]['data'] == a_message_sent_from_customer_1
    assert a_customer_2_receive_result[0]['result'][0]['data'] == a_message_sent_from_customer_1

    assert kw.group_info_v1('customer-1', group_key_id)['result']['last_sequence_id'] == 0
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 0

    # rotate identity sources on broker-1
    kw.identity_rotate_v1('broker-1')

    # MESSAGE B: from customer 2 to the group, customers 1 and 2 must switch to broker-2 and receive the message
    b_message_sent_from_customer_1 = {'random_message': 'MESSAGE_B_%s' % base64.b32encode(os.urandom(20)).decode(), }
    b_customer_1_receive_result = [None, ]
    b_customer_2_receive_result = [None, ]
    b_receive_customer_1 = threading.Timer(0, kw.message_receive_v1, [
        'customer-1', b_message_sent_from_customer_1, 'test_consumer', b_customer_1_receive_result, 60, ])
    b_receive_customer_2 = threading.Timer(0, kw.message_receive_v1, [
        'customer-2', b_message_sent_from_customer_1, 'test_consumer', b_customer_2_receive_result, 60, ])
    b_send_customer_1 = threading.Timer(0.2, kw.message_send_group_v1, [
        'customer-1', group_key_id, b_message_sent_from_customer_1, ])
    b_receive_customer_1.start()
    b_receive_customer_2.start()
    b_send_customer_1.start()
    b_receive_customer_1.join()
    b_receive_customer_2.join()
    b_send_customer_1.join()
    assert b_customer_1_receive_result[0]['result'][0]['data'] == b_message_sent_from_customer_1
    assert b_customer_2_receive_result[0]['result'][0]['data'] == b_message_sent_from_customer_1

    assert kw.group_info_v1('customer-1', group_key_id)['result']['last_sequence_id'] == 0
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 0
