#!/usr/bin/env python
# test_service_private_groups.py
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
#
# This file (test_service_private_groups.py) is part of BitDust Software.
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

import keywords as kw


def test_customers_1_2_3_communicate_via_message_broker():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    # prepare customers 1, 2 and 3
    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-1', 'service_private_groups', 'ON')

    kw.supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-2', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-2', 'service_private_groups', 'ON')

    kw.supplier_list_v1('customer-3', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-3', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-3', 'service_private_groups', 'ON')

    kw.packet_list_v1('customer-1', wait_all_finish=True)
    kw.transfer_list_v1('customer-1', wait_all_finish=True)
    kw.packet_list_v1('customer-2', wait_all_finish=True)
    kw.transfer_list_v1('customer-2', wait_all_finish=True)
    kw.packet_list_v1('customer-3', wait_all_finish=True)
    kw.transfer_list_v1('customer-3', wait_all_finish=True)

    assert kw.queue_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-2', extract_ids=True) == []

    # create group owned by customer-1 and join
    group_key_id = kw.group_create_v1('customer-1', label='TestGroup123')

    group_info_inactive = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_inactive['state'] == 'OFFLINE'
    assert group_info_inactive['label'] == 'TestGroup123'
    assert group_info_inactive['last_sequence_id'] == -1

    kw.group_join_v1('customer-1', group_key_id)

    group_info_active = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_active['state'] == 'IN_SYNC!'
    assert len(group_info_active['connected_brokers']) == 1
    assert group_info_active['last_sequence_id'] == -1

    active_queue_id = group_info_active['active_queue_id']
    active_broker_id = group_info_active['active_broker_id']
    active_broker_name = active_broker_id.split('@')[0]

    assert active_queue_id in kw.queue_list_v1(active_broker_name, extract_ids=True)

    broker_consumers = kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    broker_producers = kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert len(broker_consumers) == 1
    assert len(broker_producers) == 1
    assert 'customer-1@id-a_8084' in broker_consumers
    assert 'customer-1@id-a_8084' in broker_producers

    # share group key from customer-1 to customer-2, second member join the group
    kw.group_share_v1('customer-1', group_key_id, 'customer-2@id-b_8084')

    kw.group_join_v1('customer-2', group_key_id)

    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == -1

    kw.packet_list_v1('customer-1', wait_all_finish=True)
    kw.transfer_list_v1('customer-1', wait_all_finish=True)
    kw.packet_list_v1('customer-2', wait_all_finish=True)
    kw.transfer_list_v1('customer-2', wait_all_finish=True)
    kw.packet_list_v1('customer-3', wait_all_finish=True)
    kw.transfer_list_v1('customer-3', wait_all_finish=True)

    broker_consumers = kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    broker_producers = kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert len(broker_consumers) == 2
    assert len(broker_producers) == 2
    assert 'customer-1@id-a_8084' in broker_consumers
    assert 'customer-1@id-a_8084' in broker_producers
    assert 'customer-2@id-b_8084' in broker_consumers
    assert 'customer-2@id-b_8084' in broker_producers

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

    # customer-2 share group key to customer-3, third member join the group
    kw.group_share_v1('customer-2', group_key_id, 'customer-3@id-a_8084')

    kw.group_join_v1('customer-3', group_key_id)

    broker_consumers = kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    broker_producers = kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert len(broker_consumers) == 3
    assert len(broker_producers) == 3
    assert 'customer-1@id-a_8084' in broker_consumers
    assert 'customer-1@id-a_8084' in broker_producers
    assert 'customer-2@id-b_8084' in broker_consumers
    assert 'customer-2@id-b_8084' in broker_producers
    assert 'customer-3@id-a_8084' in broker_consumers
    assert 'customer-3@id-a_8084' in broker_producers

    kw.packet_list_v1('customer-1', wait_all_finish=True)
    kw.transfer_list_v1('customer-1', wait_all_finish=True)
    kw.packet_list_v1('customer-2', wait_all_finish=True)
    kw.transfer_list_v1('customer-2', wait_all_finish=True)
    kw.packet_list_v1('customer-3', wait_all_finish=True)
    kw.transfer_list_v1('customer-3', wait_all_finish=True)

    assert kw.group_info_v1('customer-3', group_key_id)['result']['last_sequence_id'] == 0

    # MESSAGE B: from customer 3 to the group, customers 1, 2 and 3 must receive the message
    b_message_sent_from_customer_3 = {'random_message': 'MESSAGE_B_%s' % base64.b32encode(os.urandom(20)).decode(), }
    b_customer_1_receive_result = [None, ]
    b_customer_2_receive_result = [None, ]
    b_customer_3_receive_result = [None, ]
    b_receive_customer_1 = threading.Timer(0, kw.message_receive_v1, [
        'customer-1', b_message_sent_from_customer_3, 'test_consumer', b_customer_1_receive_result, ])
    b_receive_customer_2 = threading.Timer(0, kw.message_receive_v1, [
        'customer-2', b_message_sent_from_customer_3, 'test_consumer', b_customer_2_receive_result, ])
    b_receive_customer_3 = threading.Timer(0, kw.message_receive_v1, [
        'customer-3', b_message_sent_from_customer_3, 'test_consumer', b_customer_3_receive_result, ])
    b_send_customer_3 = threading.Timer(0.2, kw.message_send_group_v1, [
        'customer-3', group_key_id, b_message_sent_from_customer_3, ])
    b_receive_customer_1.start()
    b_receive_customer_2.start()
    b_receive_customer_3.start()
    b_send_customer_3.start()
    b_receive_customer_1.join()
    b_receive_customer_2.join()
    b_receive_customer_3.join()
    b_send_customer_3.join()
    assert b_customer_1_receive_result[0]['result'][0]['data'] == b_message_sent_from_customer_3
    assert b_customer_2_receive_result[0]['result'][0]['data'] == b_message_sent_from_customer_3
    assert b_customer_3_receive_result[0]['result'][0]['data'] == b_message_sent_from_customer_3

    assert kw.group_info_v1('customer-1', group_key_id)['result']['last_sequence_id'] == 1
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 1
    assert kw.group_info_v1('customer-3', group_key_id)['result']['last_sequence_id'] == 1

    # customer-2 leave the group
    kw.group_leave_v1('customer-2', group_key_id)

    kw.packet_list_v1('customer-1', wait_all_finish=True)
    kw.transfer_list_v1('customer-1', wait_all_finish=True)
    kw.packet_list_v1('customer-2', wait_all_finish=True)
    kw.transfer_list_v1('customer-2', wait_all_finish=True)
    kw.packet_list_v1('customer-3', wait_all_finish=True)
    kw.transfer_list_v1('customer-3', wait_all_finish=True)

    group_info_offline = kw.group_info_v1('customer-2', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'TestGroup123'
    assert group_info_offline['last_sequence_id'] == 1

    assert 'customer-1@id-a_8084' in kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    assert 'customer-1@id-a_8084' in kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert 'customer-2@id-b_8084' not in kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    assert 'customer-2@id-b_8084' not in kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert 'customer-3@id-a_8084' in kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    assert 'customer-3@id-a_8084' in kw.queue_producer_list_v1(active_broker_name, extract_ids=True)

    # MESSAGE C: from customer 1 to the group, customers 1 and 3 must receive the message, customer 2 must not receive it
    c_message_sent_from_customer_1 = {'random_message': 'MESSAGE_C_%s' % base64.b32encode(os.urandom(20)).decode(), }
    c_customer_1_receive_result = [None, ]
    c_customer_2_receive_result = [None, ]
    c_customer_3_receive_result = [None, ]
    c_receive_customer_1 = threading.Timer(0, kw.message_receive_v1, [
        'customer-1', c_message_sent_from_customer_1, 'test_consumer', c_customer_1_receive_result, ])
    c_receive_customer_2 = threading.Timer(0, kw.message_receive_v1, [
        'customer-2', c_message_sent_from_customer_1, 'test_consumer', c_customer_2_receive_result, 10])
    c_receive_customer_3 = threading.Timer(0, kw.message_receive_v1, [
        'customer-3', c_message_sent_from_customer_1, 'test_consumer', c_customer_3_receive_result, ])
    c_send_customer_1 = threading.Timer(0.2, kw.message_send_group_v1, [
        'customer-1', group_key_id, c_message_sent_from_customer_1, ])
    c_receive_customer_1.start()
    c_receive_customer_2.start()
    c_receive_customer_3.start()
    c_send_customer_1.start()
    c_receive_customer_1.join()
    c_receive_customer_2.join()
    c_receive_customer_3.join()
    c_send_customer_1.join()
    assert c_customer_1_receive_result[0]['result'][0]['data'] == c_message_sent_from_customer_1
    assert c_customer_2_receive_result[0] is None
    assert c_customer_3_receive_result[0]['result'][0]['data'] == c_message_sent_from_customer_1

    assert kw.group_info_v1('customer-1', group_key_id)['result']['last_sequence_id'] == 2
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 1
    assert kw.group_info_v1('customer-3', group_key_id)['result']['last_sequence_id'] == 2

    # customer 1 and 3 also leave the group
    kw.group_leave_v1('customer-1', group_key_id)

    kw.group_leave_v1('customer-3', group_key_id)

    kw.packet_list_v1('customer-1', wait_all_finish=True)
    kw.transfer_list_v1('customer-1', wait_all_finish=True)
    kw.packet_list_v1('customer-2', wait_all_finish=True)
    kw.transfer_list_v1('customer-2', wait_all_finish=True)
    kw.packet_list_v1('customer-3', wait_all_finish=True)
    kw.transfer_list_v1('customer-3', wait_all_finish=True)

    group_info_offline = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'TestGroup123'
    assert group_info_offline['last_sequence_id'] == 2

    group_info_offline = kw.group_info_v1('customer-3', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'TestGroup123'
    assert group_info_offline['last_sequence_id'] == 2

    broker_consumers = kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    broker_producers = kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert len(broker_consumers) == 0
    assert len(broker_producers) == 0
