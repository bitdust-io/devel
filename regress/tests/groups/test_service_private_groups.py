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
import threading

import keywords as kw


SUPPLIERS_IDS = ['supplier-1', 'supplier-2', 'supplier-3', 'supplier-4', ]
BROKERS_IDS = ['broker-1', 'broker-2', 'broker-3', 'broker-4', 'broker-5', ]
CUSTOMERS_IDS = ['customer-1', 'customer-2', 'customer-3', ]



def test_customer_3_receive_all_archived_messages():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    all_messages = []

    #--- prepare customers 1, 2 and 3
    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-1', 'service_private_groups', 'ON')

    kw.supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-2', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-2', 'service_private_groups', 'ON')

    kw.supplier_list_v1('customer-3', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-3', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-3', 'service_private_groups', 'ON')

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

#     assert kw.queue_list_v1('broker-1', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-2', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-3', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-4', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-5', extract_ids=True) == []

    assert kw.queue_consumer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-3', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-4', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-5', extract_ids=True) == []

    assert kw.queue_producer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-3', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-4', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-5', extract_ids=True) == []

    #--- create group owned by customer-1 and join
    group_key_id = kw.group_create_v1('customer-1', label='ArchivedGroupABC')

    group_info_inactive = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_inactive['state'] == 'OFFLINE'
    assert group_info_inactive['label'] == 'ArchivedGroupABC'
    assert group_info_inactive['last_sequence_id'] == -1

    kw.group_join_v1('customer-1', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    group_info_active = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_active['state'] == 'IN_SYNC!'
    assert len(group_info_active['connected_brokers']) >= 2
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

    #--- share group key from customer-1 to customer-2
    kw.group_share_v1('customer-1', group_key_id, 'customer-2@id-b_8084')

    #--- second member join the group
    kw.group_join_v1('customer-2', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == -1

    broker_consumers = kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    broker_producers = kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert len(broker_consumers) == 2
    assert len(broker_producers) == 2
    assert 'customer-1@id-a_8084' in broker_consumers
    assert 'customer-1@id-a_8084' in broker_producers
    assert 'customer-2@id-b_8084' in broker_consumers
    assert 'customer-2@id-b_8084' in broker_producers

    assert len(kw.message_history_v1('customer-1', group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-3', group_key_id, message_type='group_message')['result']) == 0

    #--- sending 11 messages to the group from customer 1
    for i in range(11):
        all_messages.append(kw.verify_message_sent_received(
            group_key_id,
            producer_id='customer-1',
            consumers_ids=['customer-1', 'customer-2', ],
            message_label='E%d' % (i + 1),
            expected_results={'customer-1': True, 'customer-2': True, },
            expected_last_sequence_id={},
        ))

    #--- must be 3 archive snapshots be created and 1 message not archived 
    assert kw.group_info_v1('customer-1', group_key_id)['result']['last_sequence_id'] == 10
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 10
    assert len(kw.message_history_v1('customer-1', group_key_id, message_type='group_message')['result']) == 11
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 11

    #--- customers 1 and 2 leave the group
    kw.group_leave_v1('customer-1', group_key_id)
    kw.group_leave_v1('customer-2', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    assert len(kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)) == 0
    assert len(kw.queue_producer_list_v1(active_broker_name, extract_ids=True)) == 0

    group_info_offline = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'ArchivedGroupABC'
    assert group_info_offline['last_sequence_id'] == 10

    group_info_offline = kw.group_info_v1('customer-2', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'ArchivedGroupABC'
    assert group_info_offline['last_sequence_id'] == 10

    #--- customer-2 share group key to customer-3
    kw.group_share_v1('customer-2', group_key_id, 'customer-3@id-a_8084')

    #--- customer-3 join the group, other group members are offline
    kw.group_join_v1('customer-3', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS + SUPPLIERS_IDS)

    broker_consumers = kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    broker_producers = kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert len(broker_consumers) == 1
    assert len(broker_producers) == 1
    assert 'customer-1@id-a_8084' not in broker_consumers
    assert 'customer-1@id-a_8084' not in broker_producers
    assert 'customer-2@id-b_8084' not in broker_consumers
    assert 'customer-2@id-b_8084' not in broker_producers
    assert 'customer-3@id-a_8084' in broker_consumers
    assert 'customer-3@id-a_8084' in broker_producers

    #--- customer-3 must also see all message that was sent to the group when he was not present yet
    assert kw.group_info_v1('customer-3', group_key_id)['result']['last_sequence_id'] == 10
    assert len(kw.message_history_v1('customer-3', group_key_id, message_type='group_message')['result']) == 11

    #--- customer-3 leave the group
    kw.group_leave_v1('customer-3', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    assert len(kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)) == 0
    assert len(kw.queue_producer_list_v1(active_broker_name, extract_ids=True)) == 0

    group_info_offline = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'ArchivedGroupABC'
    assert group_info_offline['last_sequence_id'] == 10

    group_info_offline = kw.group_info_v1('customer-2', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'ArchivedGroupABC'
    assert group_info_offline['last_sequence_id'] == 10

    group_info_offline = kw.group_info_v1('customer-3', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'ArchivedGroupABC'
    assert group_info_offline['last_sequence_id'] == 10

    #--- make sure brokers are cleaned up
#     assert kw.queue_list_v1('broker-1', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-2', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-3', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-4', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-5', extract_ids=True) == []

    assert kw.queue_consumer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-3', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-4', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-5', extract_ids=True) == []

    assert kw.queue_producer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-3', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-4', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-5', extract_ids=True) == []



def test_customers_1_2_3_communicate_via_message_brokers():
    return pytest.skip()  # @UndefinedVariable

    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    all_messages = []

    #--- prepare customers 1, 2 and 3
    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-1', 'service_private_groups', 'ON')

    kw.supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-2', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-2', 'service_private_groups', 'ON')

    kw.supplier_list_v1('customer-3', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.service_info_v1('customer-3', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-3', 'service_private_groups', 'ON')

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

#     assert kw.queue_list_v1('broker-1', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-2', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-3', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-4', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-5', extract_ids=True) == []

    assert kw.queue_consumer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-3', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-4', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-5', extract_ids=True) == []

    assert kw.queue_producer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-3', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-4', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-5', extract_ids=True) == []

    #--- remember suppliers of customer-1
    customer_1_suppliers = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2, extract_suppliers=True)
    first_supplier_customer_1 = customer_1_suppliers[0].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')
    second_supplier_customer_1 = customer_1_suppliers[1].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')

    #--- remember list of existing keys on suppliers
    old_keys_first_supplier_customer_1 = [k['key_id'] for k in kw.key_list_v1(first_supplier_customer_1)['result']]
    old_keys_second_supplier_customer_1 = [k['key_id'] for k in kw.key_list_v1(second_supplier_customer_1)['result']]

    #--- create group owned by customer-1 and join
    group_key_id = kw.group_create_v1('customer-1', label='TestGroup123')

    #--- make sure group key was delivered to suppliers
    new_keys_first_supplier_customer_1 = [k['key_id'] for k in kw.key_list_v1(first_supplier_customer_1)['result']]
    new_keys_second_supplier_customer_1 = [k['key_id'] for k in kw.key_list_v1(second_supplier_customer_1)['result']]
    assert group_key_id not in old_keys_first_supplier_customer_1
    assert group_key_id not in old_keys_second_supplier_customer_1
    assert group_key_id in new_keys_first_supplier_customer_1
    assert group_key_id in new_keys_second_supplier_customer_1

    group_info_inactive = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_inactive['state'] == 'OFFLINE'
    assert group_info_inactive['label'] == 'TestGroup123'
    assert group_info_inactive['last_sequence_id'] == -1

    kw.group_join_v1('customer-1', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    group_info_active = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_active['state'] == 'IN_SYNC!'
    assert len(group_info_active['connected_brokers']) >= 2
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

    #--- share group key from customer-1 to customer-2
    kw.group_share_v1('customer-1', group_key_id, 'customer-2@id-b_8084')

    #--- second member join the group
    kw.group_join_v1('customer-2', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == -1

    broker_consumers = kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    broker_producers = kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert len(broker_consumers) == 2
    assert len(broker_producers) == 2
    assert 'customer-1@id-a_8084' in broker_consumers
    assert 'customer-1@id-a_8084' in broker_producers
    assert 'customer-2@id-b_8084' in broker_consumers
    assert 'customer-2@id-b_8084' in broker_producers

    assert len(kw.message_history_v1('customer-1', group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-3', group_key_id, message_type='group_message')['result']) == 0

    #--- MESSAGE A: from customer 1 to the group, customers 1 and 2 must receive the message
    all_messages.append(kw.verify_message_sent_received(
        group_key_id,
        producer_id='customer-1',
        consumers_ids=['customer-1', 'customer-2', ],
        message_label='A',
        expected_results={'customer-1': True, 'customer-2': True, },
        expected_last_sequence_id={'customer-1': 0, 'customer-2': 0, },
    ))

    assert len(kw.message_history_v1('customer-1', group_key_id, message_type='group_message')['result']) == 1
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 1
    assert len(kw.message_history_v1('customer-3', group_key_id, message_type='group_message')['result']) == 0

    #--- customer-2 share group key to customer-3
    kw.group_share_v1('customer-2', group_key_id, 'customer-3@id-a_8084')

    #--- third member join the group
    kw.group_join_v1('customer-3', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS + SUPPLIERS_IDS)

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

    #--- customer-3 must also see the first message that was sent to the group when he was not present yet
    assert kw.group_info_v1('customer-3', group_key_id)['result']['last_sequence_id'] == 0
    assert len(kw.message_history_v1('customer-3', group_key_id, message_type='group_message')['result']) == 1

    #--- MESSAGE B: from customer 3 to the group, customers 1, 2 and 3 must receive the message
    all_messages.append(kw.verify_message_sent_received(
        group_key_id,
        producer_id='customer-3',
        consumers_ids=['customer-1', 'customer-2', 'customer-3', ],
        message_label='B',
        expected_results={'customer-1': True, 'customer-2': True, 'customer-3': True, },
        expected_last_sequence_id={'customer-1': 1, 'customer-2': 1, 'customer-3': 1, },
    ))

    #--- now all three members are online and must receive it
    assert kw.group_info_v1('customer-1', group_key_id)['result']['last_sequence_id'] == 1
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 1
    assert kw.group_info_v1('customer-3', group_key_id)['result']['last_sequence_id'] == 1
    assert len(kw.message_history_v1('customer-1', group_key_id, message_type='group_message')['result']) == 2
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 2
    assert len(kw.message_history_v1('customer-3', group_key_id, message_type='group_message')['result']) == 2

    #--- customer-2 leave the group
    kw.group_leave_v1('customer-2', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS + SUPPLIERS_IDS)

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

    #--- MESSAGE C: from customer 1 to the group, customers 1 and 3 must receive the message, customer 2 must not receive it
    all_messages.append(kw.verify_message_sent_received(
        group_key_id,
        producer_id='customer-1',
        consumers_ids=['customer-1', 'customer-2', 'customer-3', ],
        message_label='C',
        expected_results={'customer-1': True, 'customer-2': False, 'customer-3': True, },
        expected_last_sequence_id={'customer-1': 2, 'customer-2': 1, 'customer-3': 2, },
    ))

    assert len(kw.message_history_v1('customer-1', group_key_id, message_type='group_message')['result']) == 3
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 2
    assert len(kw.message_history_v1('customer-3', group_key_id, message_type='group_message')['result']) == 3

    #--- at that point 3 messages already passed thru the group and archive snapshot suppose to be triggered
    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS + SUPPLIERS_IDS)

    #--- sending 3 other messages to the group from customer 1
    for i in range(3):
        all_messages.append(kw.verify_message_sent_received(
            group_key_id,
            producer_id='customer-1',
            consumers_ids=['customer-1', 'customer-2', 'customer-3', ],
            message_label='D%d' % (i + 1),
            expected_results={'customer-1': True, 'customer-2': False, 'customer-3': True, },
            expected_last_sequence_id={},
        ))

    assert kw.group_info_v1('customer-1', group_key_id)['result']['last_sequence_id'] == 5
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 1
    assert kw.group_info_v1('customer-3', group_key_id)['result']['last_sequence_id'] == 5

    #--- customer-2 now join the group again... 
    customer_2_receive_result = [None, ]
    customer_2_receive_thread = threading.Timer(0, kw.message_receive_v1, [
        'customer-2', None, 'test_consumer', customer_2_receive_result, 25, 20, ])
    customer_2_receive_thread.start()

    #--- customer-2 missed some conversations : expect 4 messages to be received
    customer_2_join_thread = threading.Timer(0.1, kw.group_join_v1, [
        'customer-2', group_key_id, ])
    customer_2_join_thread.start()

    #--- message C suppose to be received first
    customer_2_receive_thread.join()
    customer_2_join_thread.join()

    print(customer_2_receive_result)
    assert customer_2_receive_result[0]['result'][0]['data'] == all_messages[2]

    #--- messages D1, D2 and D3 also must be received by customer-2
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 6

    #--- other group members must have all messages received as well
    assert len(kw.message_history_v1('customer-1', group_key_id, message_type='group_message')['result']) == 6
    assert len(kw.message_history_v1('customer-3', group_key_id, message_type='group_message')['result']) == 6

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    assert len(kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)) == 3
    assert len(kw.queue_producer_list_v1(active_broker_name, extract_ids=True)) == 3

    #--- all messages suppose to be restored from archive history
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 5

    #--- all customers leave the group, except customer-3
    kw.group_leave_v1('customer-1', group_key_id)
    kw.group_leave_v1('customer-2', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    assert len(kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)) == 1
    assert len(kw.queue_producer_list_v1(active_broker_name, extract_ids=True)) == 1

    group_info_offline = kw.group_info_v1('customer-1', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'TestGroup123'
    assert group_info_offline['last_sequence_id'] == 5

    group_info_offline = kw.group_info_v1('customer-2', group_key_id)['result']
    assert group_info_offline['state'] == 'OFFLINE'
    assert group_info_offline['label'] == 'TestGroup123'
    assert group_info_offline['last_sequence_id'] == 5

    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)

    kw.file_list_all_v1('customer-2')

    group_info_online = kw.group_info_v1('customer-3', group_key_id)['result']
    assert group_info_online['state'] == 'IN_SYNC!'
    assert group_info_online['label'] == 'TestGroup123'
    assert group_info_online['last_sequence_id'] == 5

    #--- make sure brokers are cleaned up
#     assert kw.queue_list_v1('broker-1', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-2', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-3', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-4', extract_ids=True) == []
#     assert kw.queue_list_v1('broker-5', extract_ids=True) == []

    assert kw.queue_consumer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-3', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-4', extract_ids=True) == []
    assert kw.queue_consumer_list_v1('broker-5', extract_ids=True) == []

    assert kw.queue_producer_list_v1('broker-1', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-2', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-3', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-4', extract_ids=True) == []
    assert kw.queue_producer_list_v1('broker-5', extract_ids=True) == []
