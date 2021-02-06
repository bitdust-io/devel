#!/usr/bin/env python
# test_id_server_offline.py
#
# Copyright (C) 2008 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (test_id_server_offline.py) is part of BitDust Software.
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
SCENARIO 1: user can search another user by nickname

SCENARIO 2: user is able to detect external IP

SCENARIO 3: customer-1 is able to send private message to customer-2

SCENARIO 4: customer-1 share files to customer-2

SCENARIO 5: users are able to use proxy nodes to route the traffic

SCENARIO 6: users are able to use DHT network to store data

SCENARIO 7: customer-1 upload and download file encrypted with his master key

SCENARIO 8: customer-3 receive all archived messages

SCENARIO 9: ID server id-dead is dead and few nodes has rotated identities

SCENARIO 10: customer-rotated IDURL was rotated but he can still download his files

SCENARIO 11: customer-2 and customer-rotated are friends and talk to each other after IDURL rotated

SCENARIO 12: customer-4 chat with customer-2 via broker-rotated, but his IDURL was rotated

SCENARIO 13: one of the suppliers of customer-3 has IDURL rotated

SCENARIO 14: customer-1 replace supplier at position 0 by random node

SCENARIO 15: customer-1 switch supplier at position 1 to specific node

SCENARIO 16: customer-4 increase and decrease suppliers amount

SCENARIO 17: customer-restore recover identity from customer-1


TODO:

SCENARIO 18: customer-4 able to upload/download files when one supplier is down


"""

import os
import shutil
import pytest
import time
import base64
import threading

from testsupport import stop_daemon, run_ssh_command_and_wait, request_get, request_post, request_put, set_active_scenario  # @UnresolvedImport

import keywords as kw  # @UnresolvedImport

PROXY_IDS = []  # ['proxy-1', 'proxy-2', 'proxy-3', ]
SUPPLIERS_IDS = ['supplier-1', 'supplier-2', 'supplier-3', 'supplier-4', 'supplier-5', ]
CUSTOMERS_IDS = ['customer-1', 'customer-2', 'customer-3', 'customer-4', 'customer-rotated', ]
CUSTOMERS_IDS_SHORT = ['customer-1', 'customer-3', 'customer-4', ]
BROKERS_IDS = ['broker-1', 'broker-2', 'broker-3', 'broker-4', ]
ROTATED_NODES = ['supplier-rotated', 'customer-rotated', 'broker-rotated', 'proxy-rotated', ]

group_customers_2_4_messages = []
group_customers_1_2_3_messages = []

ssh_cmd_verbose = True


def test_alpha():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    prepare()

    #--- SCENARIO 1: users are able to search each other by nickname
    scenario1()

    #--- SCENARIO 2: customer-1 is doing network stun
    scenario2()

    #--- SCENARIO 3: customer-1 send private message to customer-2
    scenario3()

    #--- SCENARIO 5: users are able to talk via proxy routers
    scenario5()

    #--- SCENARIO 6: users read/write from DHT
    scenario6()

    #--- SCENARIO 7: customer-1 upload/download with master key
    old_customer_1_info = scenario7()

    #--- SCENARIO 12 begin: customer-4 group chat with customer-2
    old_customer_4_info = scenario12_begin()

    #--- SCENARIO 13 begin: supplier of customer-3 has IDURL rotated
    old_customer_3_info = scenario13_begin()

    #--- SCENARIO 10 begin: customer-rotated IDURL was rotated
    old_customer_rotated_file_info = scenario10_begin()

    #--- SCENARIO 11 begin: customer-2 talk to customer-rotated
    old_customer_2_info = scenario11_begin()

    #--- SCENARIO 9: ID server id-dead is dead
    old_proxy_rotated_info, old_customer_rotated_info, old_rotated_supplier_info, old_broker_rotated_info, old_customer_rotated_keys, \
    new_proxy_rotated_info, new_customer_rotated_info, new_rotated_supplier_info, new_broker_rotated_info = scenario9()

    #--- SCENARIO 10 end: customer-rotated IDURL was rotated
    scenario10_end(old_customer_rotated_info, old_customer_rotated_file_info, old_customer_rotated_keys, new_customer_rotated_info)

    #--- SCENARIO 13 end: supplier of customer-3 has IDURL rotated
    scenario13_end(old_customer_3_info)

    #--- SCENARIO 12 end: customer-4 group chat with customer-2
    scenario12_end(old_customer_4_info)

    #--- SCENARIO 11 end: customer-2 talk to customer-rotated
    scenario11_end(old_customer_rotated_info, new_customer_rotated_info, old_customer_2_info)

    #--- SCENARIO 8: customer-3 receive all archived messages
    scenario8()

    #--- SCENARIO 4: customer-1 share files to customer-2
    customer_1_shared_file_info, customer_2_shared_file_info = scenario4()

    #--- SCENARIO 14: customer-1 replace supplier at position 0 by random node
    scenario14(old_customer_1_info, customer_1_shared_file_info)

    #--- SCENARIO 15: customer-1 switch supplier at position 1 to specific node
    scenario15(old_customer_1_info, customer_1_shared_file_info)

    #--- SCENARIO 16: customer-4 increase and decrease suppliers amount
    scenario16()

    #--- SCENARIO 17: customer-restore recover identity from customer-2
    scenario17(customer_2_shared_file_info)


#------------------------------------------------------------------------------

def prepare():
    set_active_scenario('PREPARE')
    kw.wait_suppliers_connected(CUSTOMERS_IDS, expected_min_suppliers=2, expected_max_suppliers=2)
    kw.wait_service_state(SUPPLIERS_IDS + ['supplier-rotated', ], 'service_supplier', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_customer', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_private_groups', 'ON')
    kw.wait_service_state(BROKERS_IDS + ['broker-rotated', ], 'service_message_broker', 'ON')
    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS + ['broker-rotated', ] + SUPPLIERS_IDS + ['supplier-rotated', ])

    customer_1_supplier_idurls = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert len(customer_1_supplier_idurls) == 2
    if 'http://id-dead:8084/supplier-rotated.xml' in customer_1_supplier_idurls:
        pos = customer_1_supplier_idurls.index('http://id-dead:8084/supplier-rotated.xml')
        print('customer-1 is going to replace supplier at position %d because found supplier-rotated there' % pos)
        response = request_post('customer-1', 'supplier/change/v1', json={'position': pos, })
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        kw.wait_service_state(['customer-1', ], 'service_shared_data', 'ON')
        kw.wait_packets_finished(['customer-1', ])


def scenario1():
    set_active_scenario('SCENARIO 1')
    print('\n\n============\n[SCENARIO 1] users are able to search each other by nickname')

    response = request_get('customer-1', f'user/search/customer-2/v1', timeout=30)
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result']['nickname'] == 'customer-2'
    assert response.json()['result']['result'] == 'exist'
    response = request_get('customer-1', f'user/search/user_name_not_exist/v1', timeout=30)
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result']['nickname'] == 'user_name_not_exist'
    assert response.json()['result']['result'] == 'not exist'
    response = request_get('customer-1', f'user/observe/customer-2/v1', timeout=30)
    assert response.json()['status'] == 'OK', response.json()
    assert len(response.json()['result']) == 1
    assert response.json()['result'][0]['nickname'] == 'customer-2'
    assert response.json()['result'][0]['result'] == 'exist'


def scenario2():
    set_active_scenario('SCENARIO 2')
    print('\n\n============\n[SCENARIO 2] customer-1 is doing network stun')

    response = request_get('customer-1', 'network/stun/v1')
    assert response.status_code == 200
    print('\n\n%r' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result']['result'] == 'stun-success'


def scenario3():
    set_active_scenario('SCENARIO 3')
    print('\n\n============\n[SCENARIO 3] customer-1 sending a private message to customer-2')

    kw.service_info_v1('customer-1', 'service_private_messages', 'ON')
    kw.service_info_v1('customer-2', 'service_private_messages', 'ON')

    kw.service_info_v1('customer-1', 'service_message_history', 'ON')
    kw.service_info_v1('customer-2', 'service_message_history', 'ON')

    assert len(kw.message_conversation_v1('customer-1')['result']) == 0
    assert len(kw.message_conversation_v1('customer-2')['result']) == 0
    assert len(kw.message_history_v1('customer-1', 'master$customer-2@id-b_8084', message_type='private_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', 'master$customer-1@id-a_8084', message_type='private_message')['result']) == 0

    # send first message to customer-2 while he is not listening for messages, customer-1 still receives an Ack()
    random_message_2 = {
        'random_message_2': base64.b32encode(os.urandom(20)).decode(),
    }
    kw.message_send_v1('customer-1', 'master$customer-2@id-b_8084', random_message_2, expect_consumed=False)

    random_message_1 = {
        'random_message_1': base64.b32encode(os.urandom(20)).decode(),
    }
    # send another message in different thread to get one in blocked `receive` call, now customer-2 listen for new messages
    t = threading.Timer(1.0, kw.message_send_v1, ['customer-1', 'master$customer-2@id-b_8084', random_message_1, 30, True, ])
    t.start()
    kw.message_receive_v1('customer-2', expected_data=random_message_1, timeout=16, polling_timeout=15)

    assert len(kw.message_conversation_v1('customer-1')['result']) == 1
    assert len(kw.message_conversation_v1('customer-2')['result']) == 1
    assert len(kw.message_history_v1('customer-1', 'master$customer-2@id-b_8084', message_type='private_message')['result']) == 2
    assert len(kw.message_history_v1('customer-2', 'master$customer-1@id-a_8084', message_type='private_message')['result']) == 2


def scenario4():
    set_active_scenario('SCENARIO 4')
    print('\n\n============\n[SCENARIO 4] customer-1 share files to customer-2')

    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-2', 'service_shared_data', 'ON')

    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)

    # create shares (logic unit to upload/download/share files) on customer-1 and customer-2
    customer_1_share_id_cat = kw.share_create_v1('customer-1')
    customer_2_share_id_cat = kw.share_create_v1('customer-2')

    # upload "cat.txt" for customer-1
    customer_1_local_filepath_cat, customer_1_remote_path_cat, customer_1_download_filepath_cat = kw.verify_file_create_upload_start(
        node='customer-1',
        key_id=customer_1_share_id_cat,
        volume_path='/customer_1',
        filename='cat.txt',
        randomize_bytes=200,
        expected_reliable=50,
    )
    # make sure we can download the file back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_remote_path_cat,
        destination_path=customer_1_download_filepath_cat,
        verify_from_local_path=customer_1_local_filepath_cat,
        expected_reliable=50,
    )

    # upload another different "cat.txt" for customer-2
    customer_2_local_filepath_cat, customer_2_remote_path_cat, customer_2_download_filepath_cat = kw.verify_file_create_upload_start(
        node='customer-2',
        key_id=customer_2_share_id_cat,
        volume_path='/customer_2',
        filename='cat.txt',
        randomize_bytes=100,
        expected_reliable=50,
    )
    # make sure we can download the file back on customer-2
    kw.verify_file_download_start(
        node='customer-2',
        remote_path=customer_2_remote_path_cat,
        destination_path=customer_2_download_filepath_cat,
        verify_from_local_path=customer_2_local_filepath_cat,
        expected_reliable=50,
    )

    response = request_put('customer-1', 'share/grant/v1',
        json={
            'trusted_global_id': 'customer-2@id-b_8084',
            'key_id': customer_1_share_id_cat,
        },
        timeout=30,
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    run_ssh_command_and_wait('customer-2', f'mkdir /customer_2/cat_mine/', verbose=ssh_cmd_verbose)
    run_ssh_command_and_wait('customer-2', f'mkdir /customer_2/cat_shared/', verbose=ssh_cmd_verbose)

    # now try to download shared by customer-1 cat.txt file on customer-2 to another local folder
    kw.verify_file_download_start(
        node='customer-2',
        remote_path=customer_1_remote_path_cat,
        destination_path='/customer_2/cat_shared/cat.txt',
        reliable_shares=False,
        expected_reliable=50,
    )

    # also make sure customer-2 still able to download own cat.txt file after received access to another cat.txt shared by customer-1
    kw.verify_file_download_start(
        node='customer-2',
        remote_path=customer_2_remote_path_cat,
        destination_path='/customer_2/cat_mine/cat.txt',
        verify_from_local_path=customer_2_local_filepath_cat,
        reliable_shares=False,
        expected_reliable=50,
    )

    # make sure those are different files
    customer_2_cat_own = run_ssh_command_and_wait('customer-2', f'cat /customer_2/cat_mine/cat.txt', verbose=ssh_cmd_verbose)[0].strip()
    customer_2_cat_shared = run_ssh_command_and_wait('customer-2', f'cat /customer_2/cat_shared/cat.txt', verbose=ssh_cmd_verbose)[0].strip()
    assert customer_2_cat_own != customer_2_cat_shared
    assert len(customer_2_cat_own) == 100
    assert len(customer_2_cat_shared) == 200

    return ({
        'share_id': customer_1_share_id_cat,
        'local_filepath': customer_1_local_filepath_cat,
        'remote_path': customer_1_remote_path_cat,
        'download_filepath': customer_1_download_filepath_cat,
    }, {
        'share_id': customer_2_share_id_cat,
        'local_filepath': customer_2_local_filepath_cat,
        'remote_path': customer_2_remote_path_cat,
        'download_filepath': customer_2_download_filepath_cat,
    })


def scenario5():
    set_active_scenario('SCENARIO 5')
    print('\n\n============\n[SCENARIO 5] users are able to connect to each other via proxy routers')

    kw.user_ping_v1('proxy-1', 'proxy-2@id-b_8084')
    kw.user_ping_v1('proxy-2', 'proxy-1@id-a_8084')
    kw.user_ping_v1('proxy-1', 'customer-2@id-b_8084')
    kw.user_ping_v1('customer-1', 'proxy-2@id-b_8084')
    kw.user_ping_v1('supplier-1', 'supplier-2@id-b_8084')
    kw.user_ping_v1('supplier-2', 'supplier-1@id-a_8084')
    kw.user_ping_v1('customer-1', 'customer-2@id-b_8084')
    kw.user_ping_v1('customer-2', 'customer-1@id-a_8084')
    kw.user_ping_v1('customer-1', 'supplier-2@id-b_8084')
    kw.user_ping_v1('customer-1', 'supplier-1@id-a_8084')
    kw.user_ping_v1('supplier-2', 'customer-2@id-b_8084')
    kw.user_ping_v1('supplier-2', 'customer-1@id-a_8084')
    kw.user_ping_v1('supplier-1', 'customer-2@id-b_8084')


def scenario6():
    set_active_scenario('SCENARIO 6')
    print('\n\n============\n[SCENARIO 6] users are able to use DHT network to store data')

    # DHT value not exist customer-1
    kw.dht_value_get_v1(
        node='customer-1',
        key='value_not_exist_customer_1',
        expected_data='not_exist',
    )
    # DHT write value customer-1 and read value customer-1
    kw.dht_value_set_v1(
        node='customer-1',
        key='test_key_1_customer_1',
        new_data='test_data_1_customer_1',
    )
    kw.dht_value_get_v1(
        node='customer-1',
        key='test_key_1_customer_1',
        expected_data=['test_data_1_customer_1', ],
    )
    # DHT write value customer-1 and read value supplier-1
    kw.dht_value_set_v1(
        node='customer-1',
        key='test_key_2_customer_1',
        new_data='test_data_2_customer_1',
    )
    kw.dht_value_get_v1(
        node='supplier-1',
        key='test_key_2_customer_1',
        expected_data=['test_data_2_customer_1', ],
    )
    # DHT write value customer-2 and read value customer-3
    kw.dht_value_set_v1(
        node='customer-2',
        key='test_key_1_customer_2',
        new_data='test_data_1_customer_2',
    )
    kw.dht_value_get_v1(
        node='customer-3',
        key='test_key_1_customer_2',
        expected_data=['test_data_1_customer_2', ],
    )
    # DHT read value multiple nodes
    kw.dht_value_set_v1(
        node='supplier-1',
        key='test_key_1_supplier_1',
        new_data='test_data_1_supplier_1',
    )
    # time.sleep(2)
    for node in ['customer-1', 'customer-2', 'customer-3', ]:
        kw.dht_value_get_v1(
            node=node,
            key='test_key_1_supplier_1',
            expected_data=['test_data_1_supplier_1', ],
        )
    # DHT write value multiple nodes
    for node in ['supplier-1', 'supplier-2', ]:
        kw.dht_value_set_v1(
            node=node,
            key='test_key_2_shared',
            new_data=f'test_data_2_shared_%s' % (node.replace('-', '_')),
        )
        # time.sleep(2)
    for node in ['customer-1', 'customer-2', 'customer-3', ]:
        kw.dht_value_get_v1(
            node=node,
            key='test_key_2_shared',
            expected_data=['test_data_2_shared_supplier_1', 'test_data_2_shared_supplier_2', 'test_data_2_shared_supplier_3'],
        )


def scenario7():
    set_active_scenario('SCENARIO 7')
    print('\n\n============\n[SCENARIO 7] customer-1 upload and download file encrypted with his master key')

    # create and upload file for customer-1
    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')
    customer_1_local_filepath, customer_1_remote_path, customer_1_download_filepath = kw.verify_file_create_upload_start(
        node='customer-1',
        key_id='master$customer-1@id-a_8084',
        volume_path='/customer_1',
        filename='file_encrypted_with_master_key_customer_1.txt',
        randomize_bytes=300,
    )
    # make sure we can download the file back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_remote_path,
        destination_path=customer_1_download_filepath,
        verify_from_local_path=customer_1_local_filepath,
    )
    return {
        'local_filepath': customer_1_local_filepath,
        'remote_path': customer_1_remote_path,
        'download_filepath': customer_1_download_filepath,
    }


def scenario8():
    global group_customers_1_2_3_messages
    set_active_scenario('SCENARIO 8')
    print('\n\n============\n[SCENARIO 8] customer-3 receive all archived messages')

    kw.wait_service_state(CUSTOMERS_IDS, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_private_groups', 'ON')
    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS)

#     assert kw.queue_consumer_list_v1('broker-1', extract_ids=True) == []
#     assert kw.queue_consumer_list_v1('broker-2', extract_ids=True) == []
#     assert kw.queue_consumer_list_v1('broker-3', extract_ids=True) == []
#     assert kw.queue_consumer_list_v1('broker-4', extract_ids=True) == []
#     assert kw.queue_producer_list_v1('broker-1', extract_ids=True) == []
#     assert kw.queue_producer_list_v1('broker-2', extract_ids=True) == []
#     assert kw.queue_producer_list_v1('broker-3', extract_ids=True) == []
#     assert kw.queue_producer_list_v1('broker-4', extract_ids=True) == []

    assert len(kw.message_conversation_v1('customer-1')['result']) == 1

    # create group owned by customer-1 and join
    kw.service_info_v1('customer-1', 'service_private_groups', 'ON')
    customer_1_group_key_id = kw.group_create_v1('customer-1', label='ArchivedGroupABC')

    assert len(kw.message_conversation_v1('customer-1')['result']) == 2

    customer_1_group_info_inactive = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_inactive['state'] == 'OFFLINE'
    assert customer_1_group_info_inactive['label'] == 'ArchivedGroupABC'
    assert customer_1_group_info_inactive['last_sequence_id'] == -1

    kw.group_join_v1('customer-1', customer_1_group_key_id)

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS)

    customer_1_group_info_active = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_active['state'] == 'IN_SYNC!'
    assert len(customer_1_group_info_active['connected_brokers']) >= 2
    assert customer_1_group_info_active['last_sequence_id'] == -1

    customer_1_active_queue_id = customer_1_group_info_active['active_queue_id']
    customer_1_active_broker_id = customer_1_group_info_active['active_broker_id']
    customer_1_active_broker_name = customer_1_active_broker_id.split('@')[0]

    assert customer_1_active_queue_id in kw.queue_list_v1(customer_1_active_broker_name, extract_ids=True)

    customer_1_broker_consumers = kw.queue_consumer_list_v1(customer_1_active_broker_name, extract_ids=True)
    customer_1_broker_producers = kw.queue_producer_list_v1(customer_1_active_broker_name, extract_ids=True)
    assert len(customer_1_broker_consumers) >= 1
    assert len(customer_1_broker_producers) >= 1
    assert 'customer-1@id-a_8084' in customer_1_broker_consumers
    assert 'customer-1@id-a_8084' in customer_1_broker_producers

    assert len(kw.message_conversation_v1('customer-2')['result']) == 3

    # share group key from customer-1 to customer-2
    kw.group_share_v1('customer-1', customer_1_group_key_id, 'customer-2@id-b_8084')

    assert len(kw.message_conversation_v1('customer-2')['result']) == 4

    # second member join the group
    kw.group_join_v1('customer-2', customer_1_group_key_id)

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS)

    assert kw.group_info_v1('customer-2', customer_1_group_key_id)['result']['last_sequence_id'] == -1

    customer_1_broker_consumers = kw.queue_consumer_list_v1(customer_1_active_broker_name, extract_ids=True)
    customer_1_broker_producers = kw.queue_producer_list_v1(customer_1_active_broker_name, extract_ids=True)
    assert len(customer_1_broker_consumers) >= 2
    assert len(customer_1_broker_producers) >= 2
    assert 'customer-1@id-a_8084' in customer_1_broker_consumers
    assert 'customer-1@id-a_8084' in customer_1_broker_producers
    assert 'customer-2@id-b_8084' in customer_1_broker_consumers
    assert 'customer-2@id-b_8084' in customer_1_broker_producers

    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', customer_1_group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-3', customer_1_group_key_id, message_type='group_message')['result']) == 0

    assert len(kw.message_conversation_v1('customer-1')['result']) == 2
    assert len(kw.message_conversation_v1('customer-2')['result']) == 4
    assert len(kw.message_conversation_v1('customer-3')['result']) == 0

    # sending 11 messages to the group from customer 1
    for i in range(11):
        group_customers_1_2_3_messages.append(kw.verify_message_sent_received(
            customer_1_group_key_id,
            producer_id='customer-1',
            consumers_ids=['customer-1', 'customer-2', ],
            message_label='E%d' % (i + 1),
            expected_results={'customer-1': True, 'customer-2': True, },
            expected_last_sequence_id={},
        ))

    # must be 3 archive snapshots be created and 1 message not archived 
    assert kw.group_info_v1('customer-1', customer_1_group_key_id)['result']['last_sequence_id'] == 10
    assert kw.group_info_v1('customer-2', customer_1_group_key_id)['result']['last_sequence_id'] == 10
    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 11
    assert len(kw.message_history_v1('customer-2', customer_1_group_key_id, message_type='group_message')['result']) == 11

    assert len(kw.message_conversation_v1('customer-1')['result']) == 2
    assert len(kw.message_conversation_v1('customer-2')['result']) == 4
    assert len(kw.message_conversation_v1('customer-3')['result']) == 0

    # customers 1 and 2 leave the group
    kw.group_leave_v1('customer-1', customer_1_group_key_id)
    kw.group_leave_v1('customer-2', customer_1_group_key_id)

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS)

    customer_1_broker_consumers = kw.queue_consumer_list_v1(customer_1_active_broker_name, extract_ids=True)
    customer_1_broker_producers = kw.queue_producer_list_v1(customer_1_active_broker_name, extract_ids=True)
    # assert 'customer-1@id-a_8084' not in customer_1_broker_consumers
    # assert 'customer-1@id-a_8084' not in customer_1_broker_producers
    # assert 'customer-2@id-b_8084' not in customer_1_broker_consumers
    # assert 'customer-2@id-b_8084' not in customer_1_broker_producers

    customer_1_group_info_offline = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_offline['state'] == 'OFFLINE'
    assert customer_1_group_info_offline['label'] == 'ArchivedGroupABC'
    assert customer_1_group_info_offline['last_sequence_id'] == 10

    customer_2_group_info_offline = kw.group_info_v1('customer-2', customer_1_group_key_id)['result']
    assert customer_2_group_info_offline['state'] == 'OFFLINE'
    assert customer_2_group_info_offline['label'] == 'ArchivedGroupABC'
    assert customer_2_group_info_offline['last_sequence_id'] == 10

    assert len(kw.message_conversation_v1('customer-1')['result']) == 2
    assert len(kw.message_conversation_v1('customer-2')['result']) == 4
    assert len(kw.message_conversation_v1('customer-3')['result']) == 0

    # customer-2 share group key to customer-3
    kw.group_share_v1('customer-2', customer_1_group_key_id, 'customer-3@id-a_8084')

    assert len(kw.message_conversation_v1('customer-3')['result']) == 1

    # customer-3 join the group, other group members are offline
    kw.group_join_v1('customer-3', customer_1_group_key_id)

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS + SUPPLIERS_IDS)

    customer_1_broker_consumers = kw.queue_consumer_list_v1(customer_1_active_broker_name, extract_ids=True)
    customer_1_broker_producers = kw.queue_producer_list_v1(customer_1_active_broker_name, extract_ids=True)
    # assert len(customer_1_broker_consumers) >= 1
    # assert len(customer_1_broker_producers) >= 1
    # assert 'customer-1@id-a_8084' not in customer_1_broker_consumers
    # assert 'customer-1@id-a_8084' not in customer_1_broker_producers
    # assert 'customer-2@id-b_8084' not in customer_1_broker_consumers
    # assert 'customer-2@id-b_8084' not in customer_1_broker_producers
    # assert 'customer-3@id-a_8084' in customer_1_broker_consumers
    # assert 'customer-3@id-a_8084' in customer_1_broker_producers

    # customer-3 must also see all message that was sent to the group when he was not present yet
    assert kw.group_info_v1('customer-3', customer_1_group_key_id)['result']['last_sequence_id'] == 10
    assert len(kw.message_history_v1('customer-3', customer_1_group_key_id, message_type='group_message')['result']) == 11
    assert len(kw.message_conversation_v1('customer-3')['result']) == 1

    # customer-3 leave the group
    kw.group_leave_v1('customer-3', customer_1_group_key_id)

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS)

    # assert len(kw.queue_consumer_list_v1(customer_1_active_broker_name, extract_ids=True)) == 0
    # assert len(kw.queue_producer_list_v1(customer_1_active_broker_name, extract_ids=True)) == 0

    customer_1_group_info_offline = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_offline['state'] == 'OFFLINE'
    assert customer_1_group_info_offline['label'] == 'ArchivedGroupABC'
    assert customer_1_group_info_offline['last_sequence_id'] == 10

    customer_2_group_info_offline = kw.group_info_v1('customer-2', customer_1_group_key_id)['result']
    assert customer_2_group_info_offline['state'] == 'OFFLINE'
    assert customer_2_group_info_offline['label'] == 'ArchivedGroupABC'
    assert customer_2_group_info_offline['last_sequence_id'] == 10

    customer_3_group_info_offline = kw.group_info_v1('customer-3', customer_1_group_key_id)['result']
    assert customer_3_group_info_offline['state'] == 'OFFLINE'
    assert customer_3_group_info_offline['label'] == 'ArchivedGroupABC'
    assert customer_3_group_info_offline['last_sequence_id'] == 10

    assert len(kw.message_conversation_v1('customer-1')['result']) == 2
    assert len(kw.message_conversation_v1('customer-2')['result']) == 4
    assert len(kw.message_conversation_v1('customer-3')['result']) == 1

    # make sure brokers are cleaned up
#     assert kw.queue_consumer_list_v1('broker-1', extract_ids=True) == []
#     assert kw.queue_consumer_list_v1('broker-2', extract_ids=True) == []
#     assert kw.queue_consumer_list_v1('broker-3', extract_ids=True) == []
#     assert kw.queue_consumer_list_v1('broker-4', extract_ids=True) == []
#     assert kw.queue_producer_list_v1('broker-1', extract_ids=True) == []
#     assert kw.queue_producer_list_v1('broker-2', extract_ids=True) == []
#     assert kw.queue_producer_list_v1('broker-3', extract_ids=True) == []
#     assert kw.queue_producer_list_v1('broker-4', extract_ids=True) == []


def scenario9(): 
    set_active_scenario('SCENARIO 9')
    print('\n\n============\n[SCENARIO 9] ID server id-dead is dead and few nodes has rotated identities')

    # remember old IDURL of the rotated nodes
    r = kw.identity_get_v1('proxy-rotated')
    old_proxy_idurl = r['result']['idurl']
    old_proxy_sources = r['result']['sources']
    old_proxy_global_id = r['result']['global_id']
    r = kw.identity_get_v1('customer-rotated')
    old_customer_idurl = r['result']['idurl']
    old_customer_sources = r['result']['sources']
    old_customer_global_id = r['result']['global_id']
    r = kw.identity_get_v1('supplier-rotated')
    old_supplier_idurl = r['result']['idurl']
    old_supplier_sources = r['result']['sources']
    old_supplier_global_id = r['result']['global_id']
    r = kw.identity_get_v1('broker-rotated')
    old_broker_idurl = r['result']['idurl']
    old_broker_sources = r['result']['sources']
    old_broker_global_id = r['result']['global_id']

    # remember list of existing keys on customer-rotated
    old_customer_keys = [k['key_id'] for k in kw.key_list_v1('customer-rotated')['result']]
    assert f'master${old_customer_global_id}' in old_customer_keys
    assert f'customer${old_customer_global_id}' in old_customer_keys

    old_proxy_info = {'idurl': old_proxy_idurl, 'sources': old_proxy_sources, 'global_id': old_proxy_global_id, }
    old_customer_info = {'idurl': old_customer_idurl, 'sources': old_customer_sources, 'global_id': old_customer_global_id, }
    old_supplier_info = {'idurl': old_supplier_idurl, 'sources': old_supplier_sources, 'global_id': old_supplier_global_id, }
    old_broker_info = {'idurl': old_broker_idurl, 'sources': old_broker_sources, 'global_id': old_broker_global_id, }

    # preparation before switching of the ID server
    kw.config_set_v1('proxy-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
    kw.config_set_v1('proxy-rotated', 'services/identity-propagate/known-servers',
                     'id-a:8084:6661,id-b:8084:6661,id-c:8084:6661')
    kw.config_set_v1('proxy-rotated', 'services/identity-propagate/preferred-servers', '')

    kw.config_set_v1('customer-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
    kw.config_set_v1('customer-rotated', 'services/identity-propagate/known-servers',
                     'id-a:8084:6661,id-b:8084:6661,id-c:8084:6661')
    kw.config_set_v1('customer-rotated', 'services/identity-propagate/preferred-servers', '')

    kw.config_set_v1('supplier-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
    kw.config_set_v1('supplier-rotated', 'services/identity-propagate/known-servers',
                     'id-a:8084:6661,id-b:8084:6661,id-c:8084:6661')
    kw.config_set_v1('supplier-rotated', 'services/identity-propagate/preferred-servers', '')

    kw.config_set_v1('broker-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
    kw.config_set_v1('broker-rotated', 'services/identity-propagate/known-servers',
                     'id-a:8084:6661,id-b:8084:6661,id-c:8084:6661')
    kw.config_set_v1('broker-rotated', 'services/identity-propagate/preferred-servers', '')

    kw.config_set_v1('customer-3', 'services/employer/candidates', '')

    # put identity server offline
    stop_daemon('id-dead')

    # test proxy-rotated new IDURL
    r = None
    for _ in range(20):
        r = kw.identity_get_v1('proxy-rotated')
        new_idurl = r['result']['idurl']
        if new_idurl != old_proxy_info['idurl']:
            break
        time.sleep(5)
    else:
        assert False, 'proxy-rotated automatic identity rotate did not happen after many attempts'
    new_proxy_sources = r['result']['sources'] 
    new_proxy_global_id = r['result']['global_id']
    new_proxy_idurl = r['result']['idurl']
    assert new_proxy_sources != old_proxy_info['sources']
    assert new_proxy_global_id != old_proxy_info['global_id']
    assert new_proxy_idurl != old_proxy_info['idurl']

    # test customer-rotated new IDURL
    for _ in range(20):
        r = kw.identity_get_v1('customer-rotated')
        new_idurl = r['result']['idurl']
        if new_idurl != old_customer_info['idurl']:
            break
        time.sleep(5)
    else:
        assert False, 'customer-rotated automatic identity rotate did not happen after many attempts'
    new_customer_sources = r['result']['sources'] 
    new_customer_global_id = r['result']['global_id']
    new_customer_idurl = r['result']['idurl']
    assert new_customer_sources != old_customer_info['sources']
    assert new_customer_global_id != old_customer_info['global_id']
    assert new_customer_idurl != old_customer_info['idurl']
    for _ in range(20):
        customer_rotated_event_log = run_ssh_command_and_wait('customer-rotated', 'cat /root/.bitdust/logs/event.log', verbose=ssh_cmd_verbose)[0]
        if customer_rotated_event_log.count('my-identity-rotate-complete'):
            break
        time.sleep(3)
    else:
        assert False, 'event "my-identity-rotate-complete" was not triggered on customer-rotated after many attempts'

    # test supplier-rotated new IDURL
    for _ in range(20):
        r = kw.identity_get_v1('supplier-rotated')
        new_idurl = r['result']['idurl']
        if new_idurl != old_supplier_info['idurl']:
            break
        time.sleep(5)
    else:
        assert False, 'supplier-rotated automatic identity rotate did not happen after many attempts'
    new_supplier_sources = r['result']['sources'] 
    new_supplier_global_id = r['result']['global_id']
    new_supplier_idurl = r['result']['idurl']
    assert new_supplier_sources != old_supplier_info['sources']
    assert new_supplier_global_id != old_supplier_info['global_id']
    assert new_supplier_idurl != old_supplier_info['idurl']

    # test broker-rotated new IDURL
    for _ in range(20):
        r = kw.identity_get_v1('broker-rotated')
        new_idurl = r['result']['idurl']
        if new_idurl != old_broker_info['idurl']:
            break
        time.sleep(5)
    else:
        assert False, 'broker-rotated automatic identity rotate did not happen after many attempts'
    new_broker_sources = r['result']['sources'] 
    new_broker_global_id = r['result']['global_id']
    new_broker_idurl = r['result']['idurl']
    assert new_broker_sources != old_broker_info['sources']
    assert new_broker_global_id != old_broker_info['global_id']
    assert new_broker_idurl != old_broker_info['idurl']

    # make sure event "my-identity-rotate-complete" is triggered on rotated nodes
    kw.wait_event(ROTATED_NODES, 'my-identity-rotate-complete')

    # disable proxy-rotated so it will not affect other scenarios
    stop_daemon('proxy-rotated')

    new_proxy_info = {'idurl': new_proxy_idurl, 'sources': new_proxy_sources, 'global_id': new_proxy_global_id, }
    new_customer_info = {'idurl': new_customer_idurl, 'sources': new_customer_sources, 'global_id': new_customer_global_id, }
    new_supplier_info = {'idurl': new_supplier_idurl, 'sources': new_supplier_sources, 'global_id': new_supplier_global_id, }
    new_broker_info = {'idurl': new_broker_idurl, 'sources': new_broker_sources, 'global_id': new_broker_global_id, }

    return old_proxy_info, old_customer_info, old_supplier_info, old_broker_info, old_customer_keys, \
           new_proxy_info, new_customer_info, new_supplier_info, new_broker_info


def scenario10_begin():
    set_active_scenario('SCENARIO 10 begin')
    print('\n\n============\n[SCENARIO 10] customer-rotated IDURL was rotated but he can still download his files')

    # create new share and upload one file on customer-rotated
    kw.service_info_v1('customer-3', 'service_shared_data', 'ON')
    old_share_id_customer_rotated = kw.share_create_v1('customer-rotated')
    customer_rotated_local_filepath, customer_rotated_remote_path, customer_rotated_download_filepath = kw.verify_file_create_upload_start(
        node='customer-rotated',
        key_id=old_share_id_customer_rotated,
        volume_path='/customer_rotated',
        filename='file_encrypted_with_shared_key_customer_rotated.txt',
        randomize_bytes=300,
    )

    # make sure file is available to download on customer-rotated
    kw.verify_file_download_start(
        node='customer-rotated',
        remote_path=customer_rotated_remote_path,
        destination_path=customer_rotated_download_filepath,
        verify_from_local_path=customer_rotated_local_filepath,
    )

    return {
        'share_id': old_share_id_customer_rotated,
        'local_filepath': customer_rotated_local_filepath,
        'remote_path': customer_rotated_remote_path,
        'download_filepath': customer_rotated_download_filepath,
    }


def scenario10_end(old_customer_rotated_info, old_customer_rotated_file_info, old_customer_rotated_keys, new_customer_rotated_info):
    set_active_scenario('SCENARIO 10 end')
    print('\n\n============\n[SCENARIO 10] customer-rotated IDURL was rotated but he can still download his files')

    old_customer_global_id = old_customer_rotated_info['global_id']
    old_share_id_customer_rotated = old_customer_rotated_file_info['share_id']
    customer_rotated_remote_path = old_customer_rotated_file_info['remote_path']
    customer_rotated_download_filepath = old_customer_rotated_file_info['download_filepath']
    customer_rotated_local_filepath = old_customer_rotated_file_info['local_filepath']
    new_customer_global_id = new_customer_rotated_info['global_id']

    # check current suppliers of customer-rotated
    kw.service_info_v1('customer-rotated', 'service_gateway', 'ON')
    kw.service_info_v1('customer-rotated', 'service_customer', 'ON')
    customer_rotated_suppliers = kw.supplier_list_v1('customer-rotated', expected_min_suppliers=2, expected_max_suppliers=2, extract_suppliers=True)
    first_supplier = customer_rotated_suppliers[0].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')
    second_supplier = customer_rotated_suppliers[1].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')

    # make sure keys are renamed on customer-rotated
    new_customer_keys = [k['key_id'] for k in kw.key_list_v1('customer-rotated')['result']]
    # assert len(old_customer_rotated_keys) == len(new_customer_keys)
    assert f'master${new_customer_global_id}' in new_customer_keys
    assert f'customer${new_customer_global_id}' in new_customer_keys
    assert f'master${old_customer_global_id}' not in new_customer_keys
    assert f'customer${old_customer_global_id}' not in new_customer_keys

    # erase previous file on customer-rotated and prepare to download it again
    kw.service_info_v1('customer-rotated', 'service_shared_data', 'ON')
    new_share_id_customer_rotated = old_share_id_customer_rotated.replace(old_customer_global_id, new_customer_global_id)
    kw.share_open_v1('customer-rotated', new_share_id_customer_rotated)
    new_remote_path_customer_rotated = customer_rotated_remote_path.replace(old_customer_global_id, new_customer_global_id)
    run_ssh_command_and_wait('customer-rotated', 'rm -rfv %s' % customer_rotated_download_filepath, verbose=ssh_cmd_verbose)[0].strip()

    # make sure file is still available after identity rotate on customer-rotated
    kw.verify_file_download_start(
        node='customer-rotated',
        remote_path=new_remote_path_customer_rotated,
        destination_path=customer_rotated_download_filepath,
        verify_from_local_path=customer_rotated_local_filepath,
        verify_list_files=False,
    )

    # verify files on suppliers were moved to correct sub folder
    # TODO:
    old_folder_first_supplier = run_ssh_command_and_wait(first_supplier, f'ls -la ~/.bitdust/customers/{old_customer_global_id}/master/', verbose=ssh_cmd_verbose)[0].strip()
    new_folder_first_supplier = run_ssh_command_and_wait(first_supplier, f'ls -la ~/.bitdust/customers/{new_customer_global_id}/master/', verbose=ssh_cmd_verbose)[0].strip()
    # assert old_folder_first_supplier == ''
    # assert new_folder_first_supplier != ''
    old_folder_second_supplier = run_ssh_command_and_wait(second_supplier, f'ls -la ~/.bitdust/customers/{old_customer_global_id}/master/', verbose=ssh_cmd_verbose)[0].strip()
    new_folder_second_supplier = run_ssh_command_and_wait(second_supplier, f'ls -la ~/.bitdust/customers/{new_customer_global_id}/master/', verbose=ssh_cmd_verbose)[0].strip()
    # assert old_folder_second_supplier == ''
    # assert new_folder_second_supplier != ''


def scenario11_begin():
    set_active_scenario('SCENARIO 11 begin')
    print('\n\n============\n[SCENARIO 11] customer-2 and customer-rotated are friends and talk to each other after IDURL rotated')

    # make customer-rotated and customer-2 friends to each other
    kw.friend_add_v1('customer-rotated', 'http://id-b:8084/customer-2.xml', 'Alice')
    kw.friend_add_v1('customer-2', 'http://id-dead:8084/customer-rotated.xml', 'Bob')
    old_customer_2_friends = kw.friend_list_v1('customer-2', extract_idurls=True)
    assert 'http://id-dead:8084/customer-rotated.xml' in old_customer_2_friends

    # verify that customer-2 can chat with customer-rotated
    kw.service_info_v1('customer-2', 'service_private_messages', 'ON')
    kw.service_info_v1('customer-rotated', 'service_private_messages', 'ON')

    assert len(kw.message_conversation_v1('customer-rotated')['result']) == 0
    assert len(kw.message_conversation_v1('customer-2')['result']) == 2
    assert len(kw.message_history_v1('customer-rotated', 'master$customer-2@id-b_8084', message_type='private_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', 'master$customer-rotated@id-dead_8084', message_type='private_message')['result']) == 0

    random_string = base64.b32encode(os.urandom(20)).decode()
    random_message = {
        'random_message': random_string,
    }
    t = threading.Timer(1.0, kw.message_send_v1, ['customer-2', 'master$customer-rotated@id-dead_8084', random_message, ])
    t.start()
    kw.message_receive_v1('customer-rotated', expected_data=random_message, timeout=31, polling_timeout=30)

    assert len(kw.message_conversation_v1('customer-rotated')['result']) == 1
    assert len(kw.message_conversation_v1('customer-2')['result']) == 3
    assert len(kw.message_history_v1('customer-rotated', 'master$customer-2@id-b_8084', message_type='private_message')['result']) == 1
    assert len(kw.message_history_v1('customer-2', 'master$customer-rotated@id-dead_8084', message_type='private_message')['result']) == 1

    return {
        'friends': old_customer_2_friends,
    }


def scenario11_end(old_customer_rotated_info, new_customer_rotated_info, old_customer_2_info):
    set_active_scenario('SCENARIO 11 end')
    print('\n\n============\n[SCENARIO 11] customer-2 and customer-rotated are friends and talk to each other after IDURL rotated')

    # test customer-2 can still chat with customer-rotated
    kw.service_info_v1('customer-2', 'service_private_messages', 'ON')
    kw.service_info_v1('customer-rotated', 'service_private_messages', 'ON')

    assert len(kw.message_conversation_v1('customer-rotated')['result']) == 1
    assert len(kw.message_conversation_v1('customer-2')['result']) == 3
    assert len(kw.message_history_v1('customer-rotated', 'master$customer-2@id-b_8084', message_type='private_message')['result']) == 1
    assert len(kw.message_history_v1('customer-2', 'master$customer-rotated@id-dead_8084', message_type='private_message')['result']) == 1

    random_string = base64.b32encode(os.urandom(20)).decode()
    random_message = {
        'random_message': random_string,
    }
    t = threading.Timer(1.0, kw.message_send_v1, ['customer-2', 'master$%s' % new_customer_rotated_info['global_id'], random_message, 15, ])
    t.start()
    kw.message_receive_v1('customer-rotated', expected_data=random_message, timeout=16, polling_timeout=15)
    kw.wait_packets_finished(['customer-2', 'customer-rotated', ])

    assert len(kw.message_conversation_v1('customer-rotated')['result']) == 1
    assert len(kw.message_conversation_v1('customer-2')['result']) == 3
    assert len(kw.message_history_v1('customer-rotated', 'master$customer-2@id-b_8084', message_type='private_message')['result']) == 2
    assert len(kw.message_history_v1('customer-2', 'master$%s' % new_customer_rotated_info['global_id'], message_type='private_message')['result']) == 2
    assert len(kw.message_history_v1('customer-2', 'master$customer-rotated@id-dead_8084', message_type='private_message')['result']) == 2

    # test that friend's IDURL changed for customer-2
    new_customer_2_friends = kw.friend_list_v1('customer-2', extract_idurls=True)
    assert new_customer_rotated_info['idurl'] in new_customer_2_friends
    assert old_customer_rotated_info['idurl'] not in new_customer_2_friends
    assert new_customer_rotated_info['idurl'] not in old_customer_2_info['friends']


def scenario12_begin():
    global group_customers_2_4_messages
    set_active_scenario('SCENARIO 12 begin')
    print('\n\n============\n[SCENARIO 12] customer-4 chat with customer-2 via broker-rotated, but broker IDURL was rotated')

    # create group owned by customer-4 and join
    customer_4_group_key_id = kw.group_create_v1('customer-4', label='MyGroupABC')

    customer_4_group_info_inactive = kw.group_info_v1('customer-4', customer_4_group_key_id)['result']
    assert customer_4_group_info_inactive['state'] == 'OFFLINE'
    assert customer_4_group_info_inactive['label'] == 'MyGroupABC'
    assert customer_4_group_info_inactive['last_sequence_id'] == -1

    kw.group_join_v1('customer-4', customer_4_group_key_id)

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS + ['broker-rotated', ])

    customer_4_group_info_active = kw.group_info_v1('customer-4', customer_4_group_key_id)['result']
    assert customer_4_group_info_active['state'] == 'IN_SYNC!'
    assert len(customer_4_group_info_active['connected_brokers']) >= 2
    assert customer_4_group_info_active['last_sequence_id'] == -1

    customer_4_active_queue_id = customer_4_group_info_active['active_queue_id']
    customer_4_active_broker_id = customer_4_group_info_active['active_broker_id']
    customer_4_active_broker_name = customer_4_active_broker_id.split('@')[0]

    assert customer_4_active_queue_id in kw.queue_list_v1(customer_4_active_broker_name, extract_ids=True)

    customer_4_broker_consumers = kw.queue_consumer_list_v1(customer_4_active_broker_name, extract_ids=True)
    customer_4_broker_producers = kw.queue_producer_list_v1(customer_4_active_broker_name, extract_ids=True)
    # assert len(customer_4_broker_consumers) == 4
    # assert len(customer_4_broker_producers) == 4
    assert 'customer-4@id-b_8084' in customer_4_broker_consumers
    assert 'customer-4@id-b_8084' in customer_4_broker_producers

    # share group key from customer-4 to customer-2
    kw.group_share_v1('customer-4', customer_4_group_key_id, 'customer-2@id-b_8084')

    # customer-2 joins the group
    kw.group_join_v1('customer-2', customer_4_group_key_id)

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS + ['broker-rotated', ])

    assert kw.group_info_v1('customer-2', customer_4_group_key_id)['result']['last_sequence_id'] == -1

    customer_4_broker_consumers = kw.queue_consumer_list_v1(customer_4_active_broker_name, extract_ids=True)
    customer_4_broker_producers = kw.queue_producer_list_v1(customer_4_active_broker_name, extract_ids=True)
    # assert len(customer_4_broker_consumers) == 5
    # assert len(customer_4_broker_producers) == 5
    assert 'customer-4@id-b_8084' in customer_4_broker_consumers
    assert 'customer-4@id-b_8084' in customer_4_broker_producers
    assert 'customer-2@id-b_8084' in customer_4_broker_consumers
    assert 'customer-2@id-b_8084' in customer_4_broker_producers

    assert len(kw.message_history_v1('customer-4', customer_4_group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', customer_4_group_key_id, message_type='group_message')['result']) == 0

    # sending few messages to the group from customer-4
    for i in range(5):
        group_customers_2_4_messages.append(kw.verify_message_sent_received(
            customer_4_group_key_id,
            producer_id='customer-4',
            consumers_ids=['customer-4', 'customer-2', ],
            message_label='F%d' % (i + 1),
            expected_results={'customer-4': True, 'customer-2': True, },
            expected_last_sequence_id={},
        ))

    assert kw.group_info_v1('customer-4', customer_4_group_key_id)['result']['last_sequence_id'] == 4
    assert kw.group_info_v1('customer-2', customer_4_group_key_id)['result']['last_sequence_id'] == 4
    assert len(kw.message_history_v1('customer-4', customer_4_group_key_id, message_type='group_message')['result']) == 5
    assert len(kw.message_history_v1('customer-2', customer_4_group_key_id, message_type='group_message')['result']) == 5
    assert len(group_customers_2_4_messages) == 5

    # clean preferred brokers on customer-4 so he can select another broker except broker-rotated
    kw.config_set_v1('customer-4', 'services/private-groups/preferred-brokers',
                     'http://id-a:8084/broker-1.xml,http://id-b:8084/broker-2.xml,http://id-a:8084/broker-3.xml,http://id-b:8084/broker-4.xml')

    return {
        'group_key_id': customer_4_group_key_id,
        'active_queue_id': customer_4_active_queue_id,
        'active_broker_id': customer_4_active_broker_id,
        'active_broker_name': customer_4_active_broker_name,
    }


def scenario12_end(old_customer_4_info):
    global group_customers_2_4_messages
    set_active_scenario('SCENARIO 12 end')
    print('\n\n============\n[SCENARIO 12] customer-4 chat with customer-2 via broker-rotated, but broker IDURL was rotated')

    # just to make sure customer-2 or customer-4 to not pick up rotated broker again
    kw.config_set_v1('customer-2', 'services/private-groups/preferred-brokers',
                     'http://id-a:8084/broker-1.xml,http://id-b:8084/broker-2.xml,http://id-a:8084/broker-3.xml,http://id-b:8084/broker-4.xml')
    kw.config_set_v1('customer-4', 'services/private-groups/preferred-brokers',
                     'http://id-a:8084/broker-1.xml,http://id-b:8084/broker-2.xml,http://id-a:8084/broker-3.xml,http://id-b:8084/broker-4.xml')

    customer_4_group_key_id = old_customer_4_info['group_key_id']
    customer_4_active_queue_id = old_customer_4_info['active_queue_id']
    customer_4_active_broker_id = old_customer_4_info['active_broker_id']
    customer_4_active_broker_name = old_customer_4_info['active_broker_name']

    # send one message to the group after brokers rotated from customer-4
    group_customers_2_4_messages.append(kw.verify_message_sent_received(
        customer_4_group_key_id,
        producer_id='customer-4',
        consumers_ids=['customer-4', 'customer-2', ],
        message_label='G',
        expected_results={'customer-4': True, 'customer-2': True, },
        expected_last_sequence_id={'customer-4': 5, 'customer-2': 5, },
        polling_timeout=90,
        receive_timeout=91,
    ))

    # verify group queue ID suppose to be changed
    customer_4_group_info_rotated = kw.group_info_v1('customer-4', customer_4_group_key_id, wait_state='IN_SYNC!')['result']
    assert customer_4_group_info_rotated['state'] == 'IN_SYNC!'
    assert customer_4_group_info_rotated['last_sequence_id'] == 5

    customer_4_rotated_queue_id = customer_4_group_info_rotated['active_queue_id']
    customer_4_rotated_broker_id = customer_4_group_info_rotated['active_broker_id']
    customer_4_rotated_broker_name = customer_4_rotated_broker_id.split('@')[0]

    assert customer_4_rotated_queue_id != customer_4_active_queue_id
    assert customer_4_rotated_broker_id != customer_4_active_broker_id
    assert customer_4_rotated_queue_id in kw.queue_list_v1(customer_4_rotated_broker_name, extract_ids=True)
    assert customer_4_active_queue_id not in kw.queue_list_v1(customer_4_rotated_broker_name, extract_ids=True)

    customer_4_rotated_broker_consumers = kw.queue_consumer_list_v1(customer_4_rotated_broker_name, extract_ids=True)
    customer_4_rotated_broker_producers = kw.queue_producer_list_v1(customer_4_rotated_broker_name, extract_ids=True)
    # assert len(customer_4_rotated_broker_consumers) == 4
    # assert len(customer_4_rotated_broker_producers) == 4
    assert 'customer-2@id-b_8084' in customer_4_rotated_broker_consumers
    assert 'customer-2@id-b_8084' in customer_4_rotated_broker_producers
    assert 'customer-4@id-b_8084' in customer_4_rotated_broker_consumers
    assert 'customer-4@id-b_8084' in customer_4_rotated_broker_producers

    # same for customer-2 group queue ID suppose to be changed
    customer_2_group_info_rotated = kw.group_info_v1('customer-2', customer_4_group_key_id, wait_state='IN_SYNC!', stop_state='DISCONNECTED')['result']
    if customer_2_group_info_rotated['state'] == 'DISCONNECTED':
        # try to reconnect - it is fine to be disconnected when top broker's IDURL was rotated
        kw.group_join_v1('customer-2', customer_4_group_key_id)
        kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS + ['broker-rotated', ])
        customer_2_group_info_rotated = kw.group_info_v1('customer-2', customer_4_group_key_id, wait_state='IN_SYNC!')['result']

    assert customer_2_group_info_rotated['state'] == 'IN_SYNC!'
    assert customer_2_group_info_rotated['last_sequence_id'] == 5

    customer_2_rotated_queue_id = customer_2_group_info_rotated['active_queue_id']
    customer_2_rotated_broker_id = customer_2_group_info_rotated['active_broker_id']

    customer_4_group_info_rotated = kw.group_info_v1('customer-4', customer_4_group_key_id, wait_state='IN_SYNC!')['result']
    assert customer_4_group_info_rotated['state'] == 'IN_SYNC!'
    assert customer_4_group_info_rotated['last_sequence_id'] == 5

    customer_4_rotated_queue_id = customer_4_group_info_rotated['active_queue_id']
    customer_4_rotated_broker_id = customer_4_group_info_rotated['active_broker_id']
    customer_4_rotated_broker_name = customer_4_rotated_broker_id.split('@')[0]

    assert customer_2_rotated_queue_id == customer_4_rotated_queue_id
    assert customer_2_rotated_broker_id == customer_4_rotated_broker_id
    assert customer_2_rotated_queue_id != customer_4_active_queue_id
    assert customer_2_rotated_broker_id != customer_4_active_broker_id

    # sending again few messages to the group from customer-4
    for i in range(5):
        group_customers_2_4_messages.append(kw.verify_message_sent_received(
            customer_4_group_key_id,
            producer_id='customer-4',
            consumers_ids=['customer-4', 'customer-2', ],
            message_label='H%d' % (i + 1),
            expected_results={'customer-4': True, 'customer-2': True, },
            expected_last_sequence_id={},
        ))

    assert kw.group_info_v1('customer-4', customer_4_group_key_id)['result']['last_sequence_id'] == 10
    assert kw.group_info_v1('customer-2', customer_4_group_key_id)['result']['last_sequence_id'] == 10
    assert len(kw.message_history_v1('customer-4', customer_4_group_key_id, message_type='group_message')['result']) == 11
    assert len(kw.message_history_v1('customer-2', customer_4_group_key_id, message_type='group_message')['result']) == 11

    kw.group_leave_v1('customer-4', customer_4_group_key_id)
    kw.group_leave_v1('customer-2', customer_4_group_key_id)

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + BROKERS_IDS)

    customer_4_broker_consumers = kw.queue_consumer_list_v1(customer_4_active_broker_name, extract_ids=True)
    customer_4_broker_producers = kw.queue_producer_list_v1(customer_4_active_broker_name, extract_ids=True)
    assert 'customer-4@id-b_8084' not in customer_4_broker_consumers
    assert 'customer-4@id-b_8084' not in customer_4_broker_producers
    # assert 'customer-2@id-b_8084' not in customer_4_broker_consumers
    # assert 'customer-2@id-b_8084' not in customer_4_broker_producers

    customer_4_group_info_offline = kw.group_info_v1('customer-4', customer_4_group_key_id)['result']
    assert customer_4_group_info_offline['state'] == 'OFFLINE'
    assert customer_4_group_info_offline['label'] == 'MyGroupABC'
    assert customer_4_group_info_offline['last_sequence_id'] == 10

    customer_2_group_info_offline = kw.group_info_v1('customer-2', customer_4_group_key_id)['result']
    assert customer_2_group_info_offline['state'] == 'OFFLINE'
    assert customer_2_group_info_offline['label'] == 'MyGroupABC'
    assert customer_2_group_info_offline['last_sequence_id'] == 10

    # disable broker-rotated so it will not affect other scenarios
    stop_daemon('broker-rotated')


def scenario13_begin():
    set_active_scenario('SCENARIO 13 begin')
    print('\n\n============\n[SCENARIO 13] one of the suppliers of customer-3 has IDURL rotated')

    # make sure supplier-rotated was hired by customer-3
    old_customer_3_suppliers_idurls = kw.supplier_list_v1('customer-3', expected_min_suppliers=2, expected_max_suppliers=2)
    assert 'http://id-dead:8084/supplier-rotated.xml' in old_customer_3_suppliers_idurls
    # create share and upload some files for customer-3
    kw.service_info_v1('customer-3', 'service_shared_data', 'ON')
    old_share_id_customer_3 = kw.share_create_v1('customer-3')
    customer_3_local_filepath, customer_3_remote_path, customer_3_download_filepath = kw.verify_file_create_upload_start(
        node='customer-3',
        key_id=old_share_id_customer_3,
        volume_path='/customer_3',
        filename='file_encrypted_with_shared_key_customer_3.txt',
        randomize_bytes=300,
    )
    # make sure we can download the file back on customer-3
    kw.verify_file_download_start(
        node='customer-3',
        remote_path=customer_3_remote_path,
        destination_path=customer_3_download_filepath,
        verify_from_local_path=customer_3_local_filepath,
    )
    return {
        'suppliers_idurls': old_customer_3_suppliers_idurls,
        'share_id': old_share_id_customer_3,
        'local_filepath': customer_3_local_filepath,
        'remote_path': customer_3_remote_path,
        'download_filepath': customer_3_download_filepath,
    }


def scenario13_end(old_customer_3_info):
    set_active_scenario('SCENARIO 13 end')
    print('\n\n============\n[SCENARIO 13] one of the suppliers of customer-3 has IDURL rotated')

    # erase previous file on customer-3 and prepare to download it again
    kw.service_info_v1('customer-3', 'service_shared_data', 'ON')
    kw.share_open_v1('customer-3', old_customer_3_info['share_id'])
    run_ssh_command_and_wait('customer-3', 'rm -rfv %s' % old_customer_3_info['download_filepath'], verbose=ssh_cmd_verbose)[0].strip()

    # verify customer-3 still able to download the files
    kw.verify_file_download_start(
        node='customer-3',
        remote_path=old_customer_3_info['remote_path'],
        destination_path=old_customer_3_info['download_filepath'],
        verify_from_local_path=old_customer_3_info['local_filepath'],
    )

    # disable supplier-rotated so it will not affect other scenarios
    # kw.config_set_v1('supplier-rotated', 'services/supplier/enabled', 'false')
    stop_daemon('supplier-rotated')

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + SUPPLIERS_IDS)


def scenario14(old_customer_1_info, customer_1_shared_file_info):
    set_active_scenario('SCENARIO 14')
    print('\n\n============\n[SCENARIO 14] customer-1 replace supplier at position 0')

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS + SUPPLIERS_IDS)

    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=['customer-1@id-a_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=['customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=['supplier-2@id-b_8084', 'customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    customer_1_supplier_idurls_before = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert len(customer_1_supplier_idurls_before) == 2

    possible_suppliers = set([
        'http://id-a:8084/supplier-1.xml',
        'http://id-b:8084/supplier-2.xml',
        'http://id-a:8084/supplier-3.xml',
        'http://id-b:8084/supplier-4.xml',
        'http://id-a:8084/supplier-5.xml',
    ])
    possible_suppliers.discard(customer_1_supplier_idurls_before[0])
    kw.config_set_v1('customer-1', 'services/employer/candidates', ','.join(possible_suppliers))

    response = request_post('customer-1', 'supplier/change/v1', json={'position': '0'})
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    kw.wait_packets_finished(PROXY_IDS + SUPPLIERS_IDS + CUSTOMERS_IDS)

    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')

    # make sure supplier was replaced
    count = 0
    while True:
        if count > 20:
            assert False, 'supplier was not replaced after many attempts'
            break
        customer_1_supplier_idurls_after = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2, verbose=False)
        # customer_1_supplier_ids_after = list([x['global_id'] for x in customer_1_supplier_idurls_after])
        assert len(customer_1_supplier_idurls_after) == 2
        assert customer_1_supplier_idurls_after[1] == customer_1_supplier_idurls_after[1]
        if customer_1_supplier_idurls_before[0] != customer_1_supplier_idurls_after[0]:
            break
        count += 1
        time.sleep(3)

    kw.wait_packets_finished(SUPPLIERS_IDS + ['customer-1', ])

    # make sure we can still download the file back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=old_customer_1_info['remote_path'],
        destination_path=old_customer_1_info['download_filepath'],
        verify_from_local_path=old_customer_1_info['local_filepath'],
    )

    # make sure we can still download the file shared by customer-2 back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_shared_file_info['remote_path'],
        destination_path=customer_1_shared_file_info['download_filepath'],
        verify_from_local_path=customer_1_shared_file_info['local_filepath'],
    )


def scenario15(old_customer_1_info, customer_1_shared_file_info):
    set_active_scenario('SCENARIO 15')
    print('\n\n============\n[SCENARIO 15] customer-1 switch supplier at position 1 to specific node')

    customer_1_supplier_idurls_before = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert len(customer_1_supplier_idurls_before) == 2

    possible_suppliers = set([
        'http://id-a:8084/supplier-1.xml',
        'http://id-b:8084/supplier-2.xml',
        'http://id-a:8084/supplier-3.xml',
        'http://id-b:8084/supplier-4.xml',
        'http://id-a:8084/supplier-5.xml',
    ])
    possible_suppliers.difference_update(set(customer_1_supplier_idurls_before))
    new_supplier_idurl = list(possible_suppliers)[0]

    response = request_put('customer-1', 'supplier/switch/v1', json={
        'position': '1',
        'new_idurl': new_supplier_idurl,
    })
    assert response.status_code == 200

    # make sure supplier was really switched
    count = 0
    while True:
        if count > 20:
            assert False, 'supplier was not switched after many attempts'
            break
        customer_1_supplier_idurls_after = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
        assert len(customer_1_supplier_idurls_after) == 2
        assert customer_1_supplier_idurls_after[0] == customer_1_supplier_idurls_after[0]
        if customer_1_supplier_idurls_before[1] != customer_1_supplier_idurls_after[1]:
            break
        count += 1
        time.sleep(3)

    kw.wait_packets_finished(SUPPLIERS_IDS + ['customer-1', ])

    # make sure we can still download the file back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=old_customer_1_info['remote_path'],
        destination_path=old_customer_1_info['download_filepath'],
        verify_from_local_path=old_customer_1_info['local_filepath'],
    )

    # make sure we can still download the file shared by customer-2 back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_shared_file_info['remote_path'],
        destination_path=customer_1_shared_file_info['download_filepath'],
        verify_from_local_path=customer_1_shared_file_info['local_filepath'],
    )


def scenario16():
    set_active_scenario('SCENARIO 16')
    print('\n\n============\n[SCENARIO 16] customer-4 increase and decrease suppliers amount')

    customer_4_supplier_idurls_before = kw.supplier_list_v1('customer-4', expected_min_suppliers=2, expected_max_suppliers=2)
    assert len(customer_4_supplier_idurls_before) == 2

    kw.supplier_list_dht_v1(
        customer_id='customer-4@id-b_8084',
        observers_ids=['customer-4@id-b_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-4@id-b_8084',
        observers_ids=['customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-4@id-b_8084',
        observers_ids=['supplier-2@id-b_8084', 'customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    kw.config_set_v1('customer-4', 'services/customer/suppliers-number', '4')

    kw.wait_packets_finished(SUPPLIERS_IDS + ['customer-4'])

    customer_4_supplier_idurls_increase = kw.supplier_list_v1('customer-4', expected_min_suppliers=4, expected_max_suppliers=4)
    assert len(customer_4_supplier_idurls_increase) == 4

    kw.service_info_v1('customer-4', 'service_shared_data', 'ON')

    kw.supplier_list_dht_v1(
        customer_id='customer-4@id-b_8084',
        observers_ids=['customer-4@id-b_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-4@id-b_8084',
        observers_ids=['customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-4@id-b_8084',
        observers_ids=['supplier-2@id-b_8084', 'customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )

    kw.config_set_v1('customer-4', 'services/customer/suppliers-number', '2')

    kw.wait_packets_finished(SUPPLIERS_IDS + ['customer-4'])

    customer_4_supplier_idurls_decrease = kw.supplier_list_v1('customer-4', expected_min_suppliers=2, expected_max_suppliers=2)
    assert len(customer_4_supplier_idurls_decrease) == 2

    kw.service_info_v1('customer-4', 'service_shared_data', 'ON')

    kw.supplier_list_dht_v1(
        customer_id='customer-4@id-b_8084',
        observers_ids=['customer-1@id-a_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-4@id-b_8084',
        observers_ids=['customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-4@id-b_8084',
        observers_ids=['supplier-2@id-b_8084', 'customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )


def scenario17(old_customer_2_info):
    set_active_scenario('SCENARIO 17')
    print('\n\n============\n[SCENARIO 17] customer-restore recover identity from customer-2')

    # backup customer-2 private key
    backup_file_directory_c2 = '/customer_2/identity.backup'
    backup_file_directory_c3 = '/customer_restore/identity.backup'
    assert not os.path.exists(backup_file_directory_c2)

    response = request_post('customer-2', 'identity/backup/v1',
        json={
            'destination_filepath': backup_file_directory_c2,
        },
    )
    print('\nidentity/backup/v1 [customer-2] : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()

    # copy private key from one container to another
    # just like when you backup your private key and restore it from USB stick on another device
    shutil.move(backup_file_directory_c2, backup_file_directory_c3)

    # before start the restore make sure all files actually are delivered to suppliers
    kw.file_list_all_v1('customer-2', expected_reliable=100, reliable_shares=False, attempts=20)

    # stop customer-2 node
    response = request_get('customer-2', 'process/stop/v1')
    print('\nprocess/stop/v1 [customer-2] : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()

    kw.wait_service_state(CUSTOMERS_IDS_SHORT, 'service_shared_data', 'ON')
    kw.wait_packets_finished(PROXY_IDS + SUPPLIERS_IDS + CUSTOMERS_IDS_SHORT)

    # recover key on customer-restore container and join network
    for _ in range(5):
        response = request_post('customer-restore', 'identity/recover/v1',
            json={
                'private_key_local_file': backup_file_directory_c3,
                'join_network': '1',
            },
        )
        print('\n\nidentity/recover/v1 : %s\n' % response.json())
        if response.json()['status'] == 'OK':
            break
        time.sleep(1)
    else:
        assert False, 'customer-restore was not able to recover identity after few attempts'

    kw.service_info_v1('customer-restore', 'service_customer', 'ON')
    kw.service_info_v1('customer-restore', 'service_shared_data', 'ON', attempts=20)

    kw.supplier_list_v1('customer-restore', expected_min_suppliers=2, expected_max_suppliers=2)

    kw.supplier_list_dht_v1(
        customer_id='customer-2@id-b_8084',
        observers_ids=['customer-restore@id-a_8084', 'supplier-3@id-a_8084', 'supplier-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    kw.supplier_list_dht_v1(
        customer_id='customer-2@id-b_8084',
        observers_ids=['supplier-3@id-a_8084', 'supplier-1@id-a_8084', 'customer-restore@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    kw.supplier_list_dht_v1(
        customer_id='customer-2@id-b_8084',
        observers_ids=['supplier-1@id-a_8084', 'customer-restore@id-a_8084', 'supplier-3@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    # TODO:
    # test my keys also recovered
    # test my message history also recovered (not implemented yet)
    kw.file_list_all_v1('customer-restore', expected_reliable=50, reliable_shares=False, attempts=20)

    # try to recover stored file again
    kw.verify_file_download_start(
        node='customer-restore',
        remote_path=old_customer_2_info['remote_path'],
        destination_path=old_customer_2_info['download_filepath'],
        expected_reliable=50,
        reliable_shares=False,
    )
