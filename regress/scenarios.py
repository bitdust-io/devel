#!/usr/bin/env python
# scenarios.py
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
#
# This file (scenarios.py) is part of BitDust Software.
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

SCENARIO 8: customer-1 added routed API device and able to accept remote web-socket connections

SCENARIO 9: ID server id-dead is dead and few nodes has rotated identities

SCENARIO 10: customer-rotated IDURL was rotated but he can still download his files

SCENARIO 11: customer-2 and customer-rotated are friends and talk to each other after IDURL rotated

SCENARIO 12: customer-1 group chat with customer-2, but active queue supplier-rotated IDURL was rotated

SCENARIO 13: one of the suppliers of customer-3 has IDURL rotated

SCENARIO 14: customer-1 replace supplier at position 0 by random node

SCENARIO 15: customer-1 switch supplier at position 1 to specific node

SCENARIO 16: customer-4 increase and decrease suppliers amount

SCENARIO 17: customer-restore recover identity from customer-1

SCENARIO 18: customer-rotated IDURL was rotated but still able to comunicate in the group

SCENARIO 19: customer-2 added direct API device and able to accept remote web-socket connections

SCENARIO 23: customer-1 able to upload/download files when one supplier is down

SCENARIO 25: customer-3 receive all past messages from other group participants

SCENARIO 26: customer-3 stopped and started again but still connected to the group

SCENARIO 27: customer-2 sent message to the group but active supplier-1 is offline



TODO:

SCENARIO 24: customer-2 able to upload files into shared location created by customer-1


"""

import os
import json
import shutil
import time
import base64
import threading
import pprint

from testsupport import (health_check, start_daemon, run_ssh_command_and_wait, request_get, request_post, request_put, set_active_scenario)
from testsupport import dbg, msg

import keywords as kw
from lib import ws_client

#------------------------------------------------------------------------------

PROXY_IDS = [
    'proxy-1',
]
PROXY_IDS_12 = [
    'proxy-1',
    'proxy-2',
]
SUPPLIERS_IDS = [
    'supplier-1',
    'supplier-2',
    'supplier-3',
    'supplier-4',
    'supplier-5',
]
SUPPLIERS_IDS_12 = [
    'supplier-1',
    'supplier-2',
]
SUPPLIERS_IDS_123 = [
    'supplier-1',
    'supplier-2',
    'supplier-3',
]
CUSTOMERS_IDS = [
    'customer-1',
    'customer-2',
    'customer-3',
    'customer-4',
    'customer-rotated',
]
CUSTOMERS_IDS_SHORT = [
    'customer-1',
    'customer-3',
    'customer-4',
]
CUSTOMERS_IDS_124 = [
    'customer-1',
    'customer-2',
    'customer-4',
]
CUSTOMERS_IDS_123 = [
    'customer-1',
    'customer-2',
    'customer-3',
]
CUSTOMERS_IDS_12 = [
    'customer-1',
    'customer-2',
]
CUSTOMERS_IDS_1 = [
    'customer-1',
]
ROTATED_NODES = [
    'supplier-rotated',
    'customer-rotated',
    'proxy-rotated',
]

#------------------------------------------------------------------------------

group_customers_1_rotated_messages = []
group_customers_1_2_3_messages = []

ssh_cmd_verbose = True

#------------------------------------------------------------------------------


def scenario1():
    set_active_scenario('SCENARIO 1')
    msg('\n\n============\n[SCENARIO 1] users are able to search each other by nickname')

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
    msg('\n[SCENARIO 1] : PASS\n\n')


def scenario2():
    set_active_scenario('SCENARIO 2')
    msg('\n\n============\n[SCENARIO 2] customer-1 is doing network stun')

    response = request_get('customer-1', 'network/stun/v1')
    assert response.status_code == 200
    dbg('\n\n%r' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result']['result'] == 'stun-success'
    ip_customer_1 = response.json()['result']['ip']

    response = request_get('customer-2', 'network/stun/v1')
    assert response.status_code == 200
    dbg('\n\n%r' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result']['result'] == 'stun-success'
    ip_customer_2 = response.json()['result']['ip']

    assert ip_customer_1 != ip_customer_2
    msg('\n[SCENARIO 2] : PASS\n\n')


def scenario3():
    set_active_scenario('SCENARIO 3')
    msg('\n\n============\n[SCENARIO 3] customer-1 sending a private message to customer-2')

    kw.service_info_v1('customer-1', 'service_private_messages', 'ON')
    kw.service_info_v1('customer-2', 'service_private_messages', 'ON')

    kw.service_info_v1('customer-1', 'service_message_history', 'ON')
    kw.service_info_v1('customer-2', 'service_message_history', 'ON')

    assert len(kw.message_conversation_v1('customer-1')['result']) == 0
    assert len(kw.message_conversation_v1('customer-2')['result']) == 0
    assert len(kw.message_history_v1('customer-1', 'master$customer-2@id-a_8084', message_type='private_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', 'master$customer-1@id-a_8084', message_type='private_message')['result']) == 0

    # send first message to customer-2 while he is not listening for messages, customer-1 still receives an Ack()
    random_message_2 = {
        'random_message_2': base64.b32encode(os.urandom(20)).decode(),
    }
    kw.message_send_v1('customer-1', 'master$customer-2@id-a_8084', random_message_2, expect_consumed=False)

    random_message_1 = {
        'random_message_1': base64.b32encode(os.urandom(20)).decode(),
    }
    # send another message in different thread to get one in blocked `receive` call, now customer-2 listen for new messages
    t = threading.Timer(
        1.0,
        kw.message_send_v1,
        [
            'customer-1',
            'master$customer-2@id-a_8084',
            random_message_1,
            30,
            True,
        ],
    )
    t.start()
    kw.message_receive_v1('customer-2', expected_data=random_message_1, timeout=16, polling_timeout=15)

    assert len(kw.message_conversation_v1('customer-1')['result']) == 1
    assert len(kw.message_conversation_v1('customer-2')['result']) == 1
    assert len(kw.message_history_v1('customer-1', 'master$customer-2@id-a_8084', message_type='private_message')['result']) == 2
    assert len(kw.message_history_v1('customer-2', 'master$customer-1@id-a_8084', message_type='private_message')['result']) == 2
    msg('\n[SCENARIO 3] : PASS\n\n')


def scenario4():
    set_active_scenario('SCENARIO 4')
    msg('\n\n============\n[SCENARIO 4] customer-1 share files to customer-2')

    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')
    kw.service_info_v1('customer-2', 'service_shared_data', 'ON')

    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-1@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=[
            'customer-2@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    # create share (logic unit to upload/download/share files) on customer-1
    customer_1_share_id_cat = kw.share_create_v1('customer-1')

    # make sure shared location is activated
    kw.share_open_v1('customer-1', customer_1_share_id_cat)
    customer_1_share_info = kw.share_info_v1('customer-1', customer_1_share_id_cat, wait_state='CONNECTED', wait_suppliers=2)
    assert len(customer_1_share_info['result']['suppliers']) == 2

    # create a virtual "cat.txt" file for customer-1 and upload a "garbage" bytes there
    customer_1_local_filepath_cat, customer_1_remote_path_cat, customer_1_download_filepath_cat = kw.verify_file_create_upload_start(
        node='customer-1',
        key_id=customer_1_share_id_cat,
        volume_path='/customer_1',
        filename='cat.txt',
        randomize_bytes=200,
        expected_reliable=100,
    )
    # make sure we can download the file back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_remote_path_cat,
        destination_path=customer_1_download_filepath_cat,
        verify_from_local_path=customer_1_local_filepath_cat,
        expected_reliable=100,
    )

    # customer-1 grant access to the share to customer-2
    response = request_put(
        'customer-1',
        'share/grant/v1',
        json={
            'trusted_global_id': 'customer-2@id-a_8084',
            'key_id': customer_1_share_id_cat,
            'timeout': 60,
        },
        timeout=30,
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    run_ssh_command_and_wait('customer-2', f'mkdir /customer_2/cat_mine/', verbose=ssh_cmd_verbose)
    run_ssh_command_and_wait('customer-2', f'mkdir /customer_2/cat_shared/', verbose=ssh_cmd_verbose)
    run_ssh_command_and_wait('customer-2', f'mkdir /customer_2/dog_shared/', verbose=ssh_cmd_verbose)

    # make sure private key for shared location was delivered from customer-1 to customer-2
    kw.service_info_v1('customer-2', 'service_keys_storage', 'ON')
    customer_2_keys = [k['key_id'] for k in kw.key_list_v1('customer-2')['result']]
    assert customer_1_share_id_cat in customer_2_keys

    # make sure shared location is activated on customer-2 node
    # kw.share_open_v1('customer-2', customer_1_share_id_cat)
    kw.file_sync_v1('customer-2')
    customer_1_share_info_2 = kw.share_info_v1('customer-2', customer_1_share_id_cat, wait_state='CONNECTED', wait_suppliers=2)
    assert len(customer_1_share_info_2['result']['suppliers']) == 2

    # now try to download shared by customer-1 cat.txt file on customer-2 and place it in a new local folder
    kw.verify_file_download_start(
        node='customer-2',
        remote_path=customer_1_remote_path_cat,
        destination_path='/customer_2/cat_shared/cat.txt',
        reliable_shares=False,
        expected_reliable=100,
    )

    # customer-2 upload a new file "dog.txt" to the share
    customer_2_local_filepath_dog, customer_2_remote_path_dog, customer_2_download_filepath_dog = kw.verify_file_create_upload_start(
        node='customer-2',
        key_id=customer_1_share_id_cat,
        volume_path='/customer_2',
        filename='dog.txt',
        randomize_bytes=200,
        expected_reliable=100,
    )
    # make sure we can download the file back on customer-2
    kw.verify_file_download_start(
        node='customer-2',
        remote_path=customer_2_remote_path_dog,
        destination_path=customer_2_download_filepath_dog,
        verify_from_local_path=customer_2_local_filepath_dog,
        expected_reliable=100,
    )

    # now try to download shared by customer-2 dog.txt file on customer-1 and place it in a new local folder
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_2_remote_path_dog,
        destination_path='/customer_2/dog_shared/dog.txt',
        reliable_shares=False,
        expected_reliable=100,
        download_attempts=30,
    )

    # vice versa: create new share on customer-2
    customer_2_share_id_cat = kw.share_create_v1('customer-2')

    # make sure shared location is activated
    kw.share_open_v1('customer-2', customer_2_share_id_cat)

    # create and upload another different virtual "cat.txt" file for customer-2
    customer_2_local_filepath_cat, customer_2_remote_path_cat, customer_2_download_filepath_cat = kw.verify_file_create_upload_start(
        node='customer-2',
        key_id=customer_2_share_id_cat,
        volume_path='/customer_2',
        filename='cat.txt',
        randomize_bytes=100,
        reliable_shares=False,
        expected_reliable=100,
    )

    # make sure we can download the file back on customer-2
    kw.verify_file_download_start(
        node='customer-2',
        remote_path=customer_2_remote_path_cat,
        destination_path=customer_2_download_filepath_cat,
        verify_from_local_path=customer_2_local_filepath_cat,
        reliable_shares=False,
        expected_reliable=100,
    )

    # also make sure customer-2 still able to download own cat.txt file after received access to another cat.txt shared by customer-1
    kw.verify_file_download_start(
        node='customer-2',
        remote_path=customer_2_remote_path_cat,
        destination_path='/customer_2/cat_mine/cat.txt',
        verify_from_local_path=customer_2_local_filepath_cat,
        reliable_shares=False,
        expected_reliable=100,
    )

    # make sure those are different files
    customer_2_cat_own = run_ssh_command_and_wait('customer-2', f'cat /customer_2/cat_mine/cat.txt', verbose=ssh_cmd_verbose)[0].strip()
    customer_2_cat_shared = run_ssh_command_and_wait('customer-2', f'cat /customer_2/cat_shared/cat.txt', verbose=ssh_cmd_verbose)[0].strip()
    assert customer_2_cat_own != customer_2_cat_shared
    assert len(customer_2_cat_own) == 100
    assert len(customer_2_cat_shared) == 200

    return (
        {
            'share_id': customer_1_share_id_cat,
            'local_filepath': customer_1_local_filepath_cat,
            'remote_path': customer_1_remote_path_cat,
            'download_filepath': customer_1_download_filepath_cat,
        },
        {
            'share_id': customer_2_share_id_cat,
            'local_filepath': customer_2_local_filepath_cat,
            'remote_path': customer_2_remote_path_cat,
            'download_filepath': customer_2_download_filepath_cat,
        },
    )
    msg('\n[SCENARIO 4] : PASS\n\n')


def scenario5():
    set_active_scenario('SCENARIO 5')
    msg('\n\n============\n[SCENARIO 5] users are able to connect to each other via proxy routers')

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
    msg('\n[SCENARIO 5] : PASS\n\n')


def scenario6():
    set_active_scenario('SCENARIO 6')
    msg('\n\n============\n[SCENARIO 6] users are able to use DHT network to store data')

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
        expected_data=[
            'test_data_1_customer_1',
        ],
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
        expected_data=[
            'test_data_2_customer_1',
        ],
    )
    # DHT write value customer-2 and read value customer-1
    kw.dht_value_set_v1(
        node='customer-2',
        key='test_key_1_customer_2',
        new_data='test_data_1_customer_2',
    )
    kw.dht_value_get_v1(
        node='customer-1',
        key='test_key_1_customer_2',
        expected_data=[
            'test_data_1_customer_2',
        ],
    )
    # DHT read value multiple nodes
    kw.dht_value_set_v1(
        node='supplier-1',
        key='test_key_1_supplier_1',
        new_data='test_data_1_supplier_1',
    )
    # time.sleep(2)
    for node in [
        'customer-1',
        'customer-2',
    ]:
        kw.dht_value_get_v1(
            node=node,
            key='test_key_1_supplier_1',
            expected_data=[
                'test_data_1_supplier_1',
            ],
        )
    # DHT write value multiple nodes
    for node in [
        'supplier-1',
        'supplier-2',
    ]:
        kw.dht_value_set_v1(
            node=node,
            key='test_key_2_shared',
            new_data=f'test_data_2_shared_%s' % (node.replace('-', '_')),
        )
        # time.sleep(2)
    for node in [
        'customer-1',
        'customer-2',
    ]:
        kw.dht_value_get_v1(
            node=node,
            key='test_key_2_shared',
            expected_data=[
                'test_data_2_shared_supplier_1',
                'test_data_2_shared_supplier_2',
            ],
        )
    msg('\n[SCENARIO 6] : PASS\n\n')


def scenario7():
    set_active_scenario('SCENARIO 7')
    msg('\n\n============\n[SCENARIO 7] customer-1 upload and download file encrypted with his master key')

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
    msg('\n[SCENARIO 7] : PASS\n\n')
    return {
        'local_filepath': customer_1_local_filepath,
        'remote_path': customer_1_remote_path,
        'download_filepath': customer_1_download_filepath,
    }


def scenario8():
    set_active_scenario('SCENARIO 8')
    msg('\n\n============\n[SCENARIO 8] customer-1 added routed API device and able to accept remote web-socket connections')

    response = request_post(
        'customer-1',
        'device/add/v1',
        json={
            'name': 'device_ABC',
            'routed': True,
            'activate': True,
            'wait_listening': False,
            'key_size': 1024,
        },
    )
    assert response.status_code == 200
    dbg('device/add/v1 [customer-1] name=device_ABC : %s\n' % pprint.pformat(response.json()))
    assert response.json()['status'] == 'OK', response.json()

    response = request_get('customer-1', 'device/info/v1?name=device_ABC')
    assert response.status_code == 200
    dbg('device/info/v1 [customer-1] name=device_ABC : %s\n' % pprint.pformat(response.json()))
    assert response.json()['status'] == 'OK', response.json()

    response = request_post(
        'customer-1',
        'device/start/v1',
        json={
            'name': 'device_ABC',
        },
    )
    assert response.status_code == 200
    dbg('device/start/v1 [customer-1] name=device_ABC : %s\n' % pprint.pformat(response.json()))
    assert response.json()['status'] == 'OK', response.json()

    target_web_socket_router_url = None
    connected_routers = None
    counter = 0
    while not target_web_socket_router_url and counter < 30:
        time.sleep(5)
        counter += 1
        response = request_get('customer-1', 'device/info/v1?name=device_ABC')
        assert response.status_code == 200
        dbg('device/info/v1 [customer-1] name=device_ABC : %s\n' % pprint.pformat(response.json()))
        assert response.json()['status'] == 'OK', response.json()
        target_web_socket_router_url = response.json()['result'].get('url')
        connected_routers = response.json()['result'].get('instance', {}).get('connected_routers')

    if counter >= 20:
        assert False, 'active web socket router was not found'

    connected_routers.insert(0, 'ws://failing-router:8282/?r=ABCDEFGH')

    open('client.json', 'w').write(json.dumps({
        'routers': connected_routers,
    }))
    def _test_client():
        counter = 0
        test_ws_app = ws_client.TestApp()
        test_ws_app.begin()
        while not test_ws_app.completed:
            time.sleep(1)
            counter += 1
            dbg('    ... %d' % counter)
        open('scenario8.txt', 'wt').write('completed')

    test_client_thread = threading.Thread(target=_test_client)
    test_client_thread.daemon = True
    test_client_thread.start()
    test_client_thread.join(timeout=30)
    assert 'completed' == open('scenario8.txt', 'rt').read()

    msg('\n[SCENARIO 8] : PASS\n\n')


def scenario9(target_nodes):
    set_active_scenario('SCENARIO 9')
    msg('\n\n============\n[SCENARIO 9] ID server id-dead is dead and few nodes has rotated identities')

    kw.wait_packets_finished(target_nodes)

    # remember old IDURL of the rotated nodes
    if 'proxy-rotated' in target_nodes:
        r = kw.identity_get_v1('proxy-rotated')
        old_proxy_idurl = r['result']['idurl']
        old_proxy_sources = r['result']['sources']
        old_proxy_global_id = r['result']['global_id']
    if 'customer-rotated' in target_nodes:
        r = kw.identity_get_v1('customer-rotated')
        old_customer_idurl = r['result']['idurl']
        old_customer_sources = r['result']['sources']
        old_customer_global_id = r['result']['global_id']
    if 'supplier-rotated' in target_nodes:
        r = kw.identity_get_v1('supplier-rotated')
        old_supplier_idurl = r['result']['idurl']
        old_supplier_sources = r['result']['sources']
        old_supplier_global_id = r['result']['global_id']
    if 'customer-rotated' in target_nodes:
        # remember list of existing keys on customer-rotated
        kw.service_info_v1('customer-rotated', 'service_customer', 'ON')
        kw.service_info_v1('customer-rotated', 'service_keys_storage', 'ON')
        old_customer_keys = [k['key_id'] for k in kw.key_list_v1('customer-rotated')['result']]
        assert f'master${old_customer_global_id}' in old_customer_keys
        # assert f'customer${old_customer_global_id}' in old_customer_keys
    else:
        old_customer_keys = []
    if 'proxy-rotated' in target_nodes:
        old_proxy_info = {
            'idurl': old_proxy_idurl,
            'sources': old_proxy_sources,
            'global_id': old_proxy_global_id,
        }
    else:
        old_proxy_info = {}
    if 'customer-rotated' in target_nodes:
        old_customer_info = {
            'idurl': old_customer_idurl,
            'sources': old_customer_sources,
            'global_id': old_customer_global_id,
        }
    else:
        old_customer_info = {}
    if 'supplier-rotated' in target_nodes:
        old_supplier_info = {
            'idurl': old_supplier_idurl,
            'sources': old_supplier_sources,
            'global_id': old_supplier_global_id,
        }
    else:
        old_supplier_info = {}
    if 'supplier-rotated' in target_nodes:
        # make sure event "identity-url-changed" is not yet triggered
        kw.wait_event(
            [
                'customer-1',
            ],
            'identity-url-changed',
            expected_count=0,
        )
    # preparation before switching of the ID server
    if 'proxy-rotated' in target_nodes:
        kw.config_set_v1('proxy-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
        kw.config_set_v1('proxy-rotated', 'services/identity-propagate/known-servers', 'id-a:8084,id-b:8084,id-c:8084')
        kw.config_set_v1('proxy-rotated', 'services/identity-propagate/preferred-servers', '')
    if 'customer-rotated' in target_nodes:
        kw.config_set_v1('customer-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
        kw.config_set_v1('customer-rotated', 'services/identity-propagate/known-servers', 'id-a:8084,id-b:8084,id-c:8084')
        kw.config_set_v1('customer-rotated', 'services/identity-propagate/preferred-servers', '')
    if 'supplier-rotated' in target_nodes:
        kw.config_set_v1('supplier-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
        kw.config_set_v1('supplier-rotated', 'services/identity-propagate/known-servers', 'id-a:8084,id-b:8084,id-c:8084')
        kw.config_set_v1('supplier-rotated', 'services/identity-propagate/preferred-servers', '')
    if 'supplier-rotated' in target_nodes:
        kw.config_set_v1('customer-1', 'services/employer/candidates', '')

    # put identity server offline
    request_get('id-dead', 'process/stop/v1', verbose=True, raise_error=False)

    if 'proxy-rotated' in target_nodes:
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

    if 'customer-rotated' in target_nodes:
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

    if 'supplier-rotated' in target_nodes:
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

    # make sure event "my-identity-rotate-complete" is triggered on rotated nodes
    kw.wait_event(target_nodes, 'my-identity-rotate-complete')

    # to make sure other nodes noticed the fact that identity was rotated
    if 'customer-rotated' in target_nodes:
        kw.user_ping_v1('customer-1', 'customer-rotated@id-dead_8084')
    # make sure event "identity-url-changed" is triggered on "affected" nodes
    if 'supplier-rotated' in target_nodes:
        kw.wait_specific_event(
            [
                'customer-1',
            ],
            'identity-url-changed',
            '^.*?%s.*?$' % new_supplier_idurl,
        )
    if 'customer-rotated' in target_nodes:
        kw.wait_specific_event(
            [
                'customer-1',
            ],
            'identity-url-changed',
            '^.*?%s.*?$' % new_customer_idurl,
        )
    if 'customer-rotated' in target_nodes:
        kw.wait_specific_event(
            [
                'supplier-2',
            ],
            'identity-url-changed',
            '^.*?%s.*?$' % new_customer_idurl,
        )

    if 'proxy-rotated' in target_nodes:
        # disable proxy-rotated so it will not affect other scenarios
        request_get('proxy-rotated', 'process/stop/v1', verbose=True, raise_error=False)
    if 'proxy-rotated' in target_nodes:
        new_proxy_info = {
            'idurl': new_proxy_idurl,
            'sources': new_proxy_sources,
            'global_id': new_proxy_global_id,
        }
    else:
        new_proxy_info = {}
    if 'customer-rotated' in target_nodes:
        new_customer_info = {
            'idurl': new_customer_idurl,
            'sources': new_customer_sources,
            'global_id': new_customer_global_id,
        }
    else:
        new_customer_info = {}
    if 'supplier-rotated' in target_nodes:
        new_supplier_info = {
            'idurl': new_supplier_idurl,
            'sources': new_supplier_sources,
            'global_id': new_supplier_global_id,
        }
    else:
        new_supplier_info = {}
    msg('\n[SCENARIO 9] : PASS\n\n')
    return old_proxy_info, old_customer_info, old_supplier_info, old_customer_keys, new_proxy_info, new_customer_info, new_supplier_info


def scenario10_begin():
    set_active_scenario('SCENARIO 10 begin')
    msg('\n\n============\n[SCENARIO 10] customer-rotated IDURL was rotated but he can still download his files')

    kw.service_info_v1('customer-rotated', 'service_shared_data', 'ON')

    # create new share
    old_share_id_customer_rotated = kw.share_create_v1('customer-rotated')

    # make sure shared location is activated
    kw.share_open_v1('customer-rotated', old_share_id_customer_rotated)

    # upload one file on customer-rotated
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
    msg('\n[SCENARIO 10 begin] : DONE\n\n')
    return {
        'share_id': old_share_id_customer_rotated,
        'local_filepath': customer_rotated_local_filepath,
        'remote_path': customer_rotated_remote_path,
        'download_filepath': customer_rotated_download_filepath,
    }


def scenario10_end(old_customer_rotated_info, old_customer_rotated_file_info, old_customer_rotated_keys, new_customer_rotated_info):
    set_active_scenario('SCENARIO 10 end')
    msg('\n\n============\n[SCENARIO 10] customer-rotated IDURL was rotated but he can still download his files')

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
    kw.service_info_v1('customer-rotated', 'service_keys_storage', 'ON')
    new_customer_keys = [k['key_id'] for k in kw.key_list_v1('customer-rotated')['result']]
    # assert len(old_customer_rotated_keys) == len(new_customer_keys)
    assert f'master${new_customer_global_id}' in new_customer_keys
    # assert f'customer${new_customer_global_id}' in new_customer_keys
    assert f'master${old_customer_global_id}' not in new_customer_keys
    # assert f'customer${old_customer_global_id}' not in new_customer_keys

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
    old_folder_first_supplier = run_ssh_command_and_wait(
        first_supplier, f'ls -la ~/.bitdust/customers/{old_customer_global_id}/master/', verbose=ssh_cmd_verbose
    )[0].strip()
    new_folder_first_supplier = run_ssh_command_and_wait(
        first_supplier, f'ls -la ~/.bitdust/customers/{new_customer_global_id}/master/', verbose=ssh_cmd_verbose
    )[0].strip()
    # assert old_folder_first_supplier == ''
    # assert new_folder_first_supplier != ''
    old_folder_second_supplier = run_ssh_command_and_wait(
        second_supplier, f'ls -la ~/.bitdust/customers/{old_customer_global_id}/master/', verbose=ssh_cmd_verbose
    )[0].strip()
    new_folder_second_supplier = run_ssh_command_and_wait(
        second_supplier, f'ls -la ~/.bitdust/customers/{new_customer_global_id}/master/', verbose=ssh_cmd_verbose
    )[0].strip()
    # assert old_folder_second_supplier == ''
    # assert new_folder_second_supplier != ''
    msg('\n[SCENARIO 10 end] : PASS\n\n')


def scenario11_begin():
    set_active_scenario('SCENARIO 11 begin')
    msg('\n\n============\n[SCENARIO 11] customer-1 and customer-rotated are friends and talk to each other after IDURL rotated')

    # make customer-rotated and customer-1 friends to each other
    kw.friend_add_v1('customer-rotated', 'http://id-a:8084/customer-1.xml', 'Alice')
    kw.friend_add_v1('customer-1', 'http://id-dead:8084/customer-rotated.xml', 'Bob')
    old_customer_1_friends = kw.friend_list_v1('customer-1', extract_idurls=True)
    assert 'http://id-dead:8084/customer-rotated.xml' in old_customer_1_friends

    # verify that customer-1 can chat with customer-rotated
    kw.service_info_v1('customer-1', 'service_private_messages', 'ON')
    kw.service_info_v1('customer-rotated', 'service_private_messages', 'ON')

    assert len(kw.message_conversation_v1('customer-rotated')['result']) == 0
    assert len(kw.message_conversation_v1('customer-1')['result']) == 0
    assert len(kw.message_history_v1('customer-rotated', 'master$customer-1@id-a_8084', message_type='private_message')['result']) == 0
    assert len(kw.message_history_v1('customer-1', 'master$customer-rotated@id-dead_8084', message_type='private_message')['result']) == 0

    random_string = base64.b32encode(os.urandom(20)).decode()
    random_message = {
        'random_message': random_string,
    }
    t = threading.Timer(
        1.0,
        kw.message_send_v1,
        [
            'customer-1',
            'master$customer-rotated@id-dead_8084',
            random_message,
        ],
    )
    t.start()
    kw.message_receive_v1('customer-rotated', expected_data=random_message, timeout=31, polling_timeout=30)

    assert len(kw.message_conversation_v1('customer-rotated')['result']) == 1
    assert len(kw.message_conversation_v1('customer-1')['result']) == 1
    assert len(kw.message_history_v1('customer-rotated', 'master$customer-1@id-a_8084', message_type='private_message')['result']) == 1
    assert len(kw.message_history_v1('customer-1', 'master$customer-rotated@id-dead_8084', message_type='private_message')['result']) == 1

    msg('\n[SCENARIO 11 begin] : DONE\n\n')
    return {
        'friends': old_customer_1_friends,
    }


def scenario11_end(old_customer_rotated_info, new_customer_rotated_info, old_customer_1_info):
    set_active_scenario('SCENARIO 11 end')
    msg('\n\n============\n[SCENARIO 11] customer-1 and customer-rotated are friends and talk to each other after IDURL rotated')

    # test customer-2 can still chat with customer-rotated
    kw.service_info_v1('customer-1', 'service_private_messages', 'ON')
    kw.service_info_v1('customer-rotated', 'service_private_messages', 'ON')

    assert len(kw.message_conversation_v1('customer-rotated')['result']) >= 1
    assert len(kw.message_conversation_v1('customer-1')['result']) >= 1
    assert len(kw.message_history_v1('customer-rotated', 'master$customer-1@id-a_8084', message_type='private_message')['result']) == 1
    assert len(kw.message_history_v1('customer-1', 'master$customer-rotated@id-dead_8084', message_type='private_message')['result']) == 1
    assert len(kw.message_history_v1('customer-1', 'master$customer-rotated@id-a_8084', message_type='private_message')['result']) == 1

    random_string = base64.b32encode(os.urandom(20)).decode()
    random_message = {
        'random_message': random_string,
    }
    t = threading.Timer(
        1.0,
        kw.message_send_v1,
        [
            'customer-1',
            'master$%s' % new_customer_rotated_info['global_id'],
            random_message,
            15,
        ],
    )
    t.start()
    kw.message_receive_v1('customer-rotated', expected_data=random_message, timeout=16, polling_timeout=15)
    kw.wait_packets_finished([
        'customer-1',
        'customer-rotated',
    ])

    assert len(kw.message_conversation_v1('customer-rotated')['result']) >= 1
    assert len(kw.message_conversation_v1('customer-1')['result']) >= 1
    assert len(kw.message_history_v1('customer-rotated', 'master$customer-1@id-a_8084', message_type='private_message')['result']) == 2
    assert len(kw.message_history_v1('customer-1', 'master$%s' % new_customer_rotated_info['global_id'], message_type='private_message')['result']) == 2
    assert len(kw.message_history_v1('customer-1', 'master$customer-rotated@id-dead_8084', message_type='private_message')['result']) == 2
    assert len(kw.message_history_v1('customer-1', 'master$customer-rotated@id-a_8084', message_type='private_message')['result']) == 2

    # test that friend's IDURL changed for customer-2
    new_customer_1_friends = kw.friend_list_v1('customer-1', extract_idurls=True)
    assert new_customer_rotated_info['idurl'] in new_customer_1_friends
    assert old_customer_rotated_info['idurl'] not in new_customer_1_friends
    assert new_customer_rotated_info['idurl'] not in old_customer_1_info['friends']
    msg('\n[SCENARIO 11 end] : PASS\n\n')


def scenario12_begin():
    global group_customers_1_rotated_messages
    set_active_scenario('SCENARIO 12 begin')
    msg('\n\n============\n[SCENARIO 12] customer-1 group chat with customer-2, but active queue supplier-rotated IDURL was rotated')

    # create group owned by customer-1 and join
    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_private_groups', 'ON')
    customer_1_group_key_id = kw.group_create_v1('customer-1', label='SCENARIO12_MyGroupABC')
    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_12)

    customer_1_group_info_inactive = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_inactive['state'] == 'DISCONNECTED'
    assert customer_1_group_info_inactive['label'] == 'SCENARIO12_MyGroupABC'
    assert customer_1_group_info_inactive['last_sequence_id'] == -1

    kw.group_join_v1('customer-1', customer_1_group_key_id)

    kw.wait_packets_finished(
        CUSTOMERS_IDS_12 + SUPPLIERS_IDS_12 + [
            'supplier-rotated',
        ],
    )

    customer_1_group_info_active = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_active['state'] == 'CONNECTED'
    assert customer_1_group_info_active['last_sequence_id'] == -1

    customer_1_active_queue_id = customer_1_group_info_active['active_queue_id']
    customer_1_active_supplier_name = customer_1_group_info_active['active_supplier_id'].split('@')[0]

    assert customer_1_active_queue_id in kw.queue_list_v1(customer_1_active_supplier_name, extract_ids=True)

    customer_1_supplier_consumers = kw.queue_consumer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    customer_1_supplier_producers = kw.queue_producer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    assert 'customer-1@id-a_8084' in customer_1_supplier_consumers
    assert 'customer-1@id-a_8084' in customer_1_supplier_producers
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)

    # share group key from customer-1 to customer-2
    kw.group_share_v1('customer-1', customer_1_group_key_id, 'customer-2@id-b_8084')

    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_12)

    # customer-2 joins the group
    kw.group_join_v1('customer-2', customer_1_group_key_id)
    kw.wait_packets_finished(
        CUSTOMERS_IDS_12 + SUPPLIERS_IDS_12 + [
            'supplier-rotated',
        ],
    )

    assert kw.group_info_v1('customer-2', customer_1_group_key_id)['result']['last_sequence_id'] == -1

    customer_1_supplier_consumers = kw.queue_consumer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    customer_1_supplier_producers = kw.queue_producer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    assert 'customer-1@id-a_8084' in customer_1_supplier_consumers
    assert 'customer-1@id-a_8084' in customer_1_supplier_producers
    assert 'customer-2@id-b_8084' in customer_1_supplier_consumers
    assert 'customer-2@id-b_8084' in customer_1_supplier_producers
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)

    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', customer_1_group_key_id, message_type='group_message')['result']) == 0

    # sending few messages to the group from customer-1
    for i in range(5):
        group_customers_1_rotated_messages.append(
            kw.verify_message_sent_received(
                customer_1_group_key_id,
                producer_id='customer-1',
                consumers_ids=[
                    'customer-1',
                    'customer-2',
                ],
                message_label='F%d' % (i + 1),
                expected_results={
                    'customer-1': True,
                    'customer-2': True,
                },
            )
        )

    assert kw.group_info_v1('customer-1', customer_1_group_key_id)['result']['last_sequence_id'] > 0
    assert kw.group_info_v1('customer-2', customer_1_group_key_id)['result']['last_sequence_id'] > 0
    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 5
    assert len(kw.message_history_v1('customer-2', customer_1_group_key_id, message_type='group_message')['result']) == 5
    assert len(group_customers_1_rotated_messages) == 5

    # create another group owned by customer-1 and join
    customer_1_group2_key_id = kw.group_create_v1('customer-1', label='SCENARIO12_MyGroupXYZ')
    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_12)

    kw.group_join_v1('customer-1', customer_1_group2_key_id)
    kw.wait_packets_finished(
        CUSTOMERS_IDS_12 + SUPPLIERS_IDS_12 + [
            'supplier-rotated',
        ],
    )

    # share second group key from customer-1 to customer-2
    kw.group_share_v1('customer-1', customer_1_group2_key_id, 'customer-2@id-b_8084')

    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_12 + SUPPLIERS_IDS_12)

    # customer-2 also joins the second group
    kw.group_join_v1('customer-2', customer_1_group2_key_id)
    kw.wait_packets_finished(
        CUSTOMERS_IDS_12 + SUPPLIERS_IDS_12 + [
            'supplier-rotated',
        ],
    )

    # sending few messages to the second group from customer-2
    for i in range(3):
        kw.verify_message_sent_received(
            customer_1_group2_key_id,
            producer_id='customer-2',
            consumers_ids=[
                'customer-1',
                'customer-2',
            ],
            message_label='J%d' % (i + 1),
            expected_results={
                'customer-1': True,
                'customer-2': True,
            },
        )

    # sending few messages to the second group from customer-1
    for i in range(3):
        kw.verify_message_sent_received(
            customer_1_group2_key_id,
            producer_id='customer-1',
            consumers_ids=[
                'customer-1',
                'customer-2',
            ],
            message_label='K%d' % (i + 1),
            expected_results={
                'customer-1': True,
                'customer-2': True,
            },
        )

    customer_1_supplier_consumers = kw.queue_consumer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    customer_1_supplier_producers = kw.queue_producer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    assert 'customer-1@id-a_8084' in customer_1_supplier_consumers
    assert 'customer-1@id-a_8084' in customer_1_supplier_producers
    assert 'customer-2@id-b_8084' in customer_1_supplier_consumers
    assert 'customer-2@id-b_8084' in customer_1_supplier_producers
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)

    assert kw.group_info_v1('customer-1', customer_1_group_key_id, wait_state='CONNECTED')['result']['state'] == 'CONNECTED'
    assert kw.group_info_v1('customer-1', customer_1_group2_key_id, wait_state='CONNECTED')['result']['state'] == 'CONNECTED'

    assert kw.group_info_v1('customer-1', customer_1_group_key_id)['result']['last_sequence_id'] > 0
    assert kw.group_info_v1('customer-1', customer_1_group2_key_id)['result']['last_sequence_id'] > 0
    assert kw.group_info_v1('customer-2', customer_1_group_key_id)['result']['last_sequence_id'] > 0
    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 5
    assert len(kw.message_history_v1('customer-1', customer_1_group2_key_id, message_type='group_message')['result']) == 6
    assert len(kw.message_history_v1('customer-2', customer_1_group_key_id, message_type='group_message')['result']) == 5

    kw.wait_packets_finished(CUSTOMERS_IDS_12)

    msg('\n[SCENARIO 12 begin] : DONE\n\n')
    return {
        'group_key_id': customer_1_group_key_id,
        'active_queue_id': customer_1_active_queue_id,
        'active_supplier_name': customer_1_active_supplier_name,
        'group2_key_id': customer_1_group2_key_id,
    }


def scenario12_end(old_customer_1_info):
    global group_customers_1_rotated_messages
    set_active_scenario('SCENARIO 12 end')
    msg('\n\n============\n[SCENARIO 12] customer-1 group chat with customer-2, but active queue supplier-rotated IDURL was rotated')

    customer_1_group_key_id = old_customer_1_info['group_key_id']
    customer_1_old_queue_id = old_customer_1_info['active_queue_id']
    customer_1_old_supplier_name = old_customer_1_info['active_supplier_name']
    customer_1_group2_key_id = old_customer_1_info['group2_key_id']

    # verify customer-2 group state before sending a new message - it suppose to trigger supplier rotation
    customer_2_group_info_before = kw.group_info_v1('customer-2', customer_1_group_key_id, wait_state='CONNECTED')['result']
    # if customer_2_group_info_before['state'] == 'DISCONNECTED':
    #     # should retry in case of supplier rotation failed
    #     kw.group_join_v1('customer-2', customer_1_group_key_id)
    #     kw.wait_packets_finished([
    #         'customer-2',
    #     ])
    #     customer_2_group_info_before = kw.group_info_v1('customer-2', customer_1_group_key_id, wait_state='CONNECTED')['result']

    assert customer_2_group_info_before['state'] == 'CONNECTED'
    assert customer_2_group_info_before['last_sequence_id'] > 0

    # verify also the second group info for customer-2
    customer_2_group2_info_before = kw.group_info_v1('customer-2', customer_1_group2_key_id, wait_state='CONNECTED')['result']
    assert customer_2_group2_info_before['state'] == 'CONNECTED'

    # same for customer-1, but it suppose to be already reconnected automatically
    customer_1_group_info_before = kw.group_info_v1('customer-1', customer_1_group_key_id, wait_state='CONNECTED')['result']
    assert customer_1_group_info_before['state'] == 'CONNECTED'
    customer_1_group2_info_before = kw.group_info_v1('customer-1', customer_1_group2_key_id, wait_state='CONNECTED')['result']
    assert customer_1_group2_info_before['state'] == 'CONNECTED'

    # send one message to the group after supplier rotated from customer-2
    group_customers_1_rotated_messages.append(
        kw.verify_message_sent_received(
            customer_1_group_key_id,
            producer_id='customer-2',
            consumers_ids=[
                'customer-1',
                'customer-2',
            ],
            message_label='G_active_queue_id_to_be_changed',
            expected_results={
                'customer-1': True,
                'customer-2': True,
            },
            polling_timeout=120,
            receive_timeout=121,
        )
    )

    # verify customer-2 is still connected to the group
    customer_2_group_info_rotated = kw.group_info_v1('customer-2', customer_1_group_key_id, wait_state='CONNECTED')['result']
    assert customer_2_group_info_rotated['state'] == 'CONNECTED'
    assert customer_2_group_info_rotated['last_sequence_id'] > 0
    customer_2_rotated_queue_id = customer_2_group_info_rotated['active_queue_id']
    customer_2_rotated_supplier_name = customer_2_group_info_rotated['active_supplier_id'].split('@')[0]
    assert customer_2_rotated_queue_id != customer_1_old_queue_id
    assert customer_2_rotated_queue_id in kw.queue_list_v1(customer_2_rotated_supplier_name, extract_ids=True)
    assert customer_1_old_queue_id not in kw.queue_list_v1(customer_2_rotated_supplier_name, extract_ids=True)

    # verify customer-1 is still connected to the group
    customer_1_group_info_rotated = kw.group_info_v1('customer-1', customer_1_group_key_id, wait_state='CONNECTED')['result']
    assert customer_1_group_info_rotated['state'] == 'CONNECTED'
    assert customer_1_group_info_rotated['last_sequence_id'] > 0
    customer_1_rotated_queue_id = customer_1_group_info_rotated['active_queue_id']
    customer_1_rotated_supplier_name = customer_1_group_info_rotated['active_supplier_id'].split('@')[0]
    assert customer_1_rotated_queue_id != customer_1_old_queue_id
    assert customer_1_rotated_queue_id in kw.queue_list_v1(customer_1_rotated_supplier_name, extract_ids=True)
    assert customer_1_old_queue_id not in kw.queue_list_v1(customer_1_rotated_supplier_name, extract_ids=True)
    assert customer_1_rotated_queue_id == customer_2_rotated_queue_id

    # verify new supplier accepted customer-2
    customer_2_rotated_supplier_consumers = kw.queue_consumer_list_v1(customer_2_rotated_supplier_name, extract_ids=True)
    assert 'customer-2@id-b_8084' in customer_2_rotated_supplier_consumers
    assert 'customer-1@id-a_8084' in customer_2_rotated_supplier_consumers
    customer_2_rotated_supplier_producers = kw.queue_producer_list_v1(customer_2_rotated_supplier_name, extract_ids=True)
    assert 'customer-2@id-b_8084' in customer_2_rotated_supplier_producers
    assert 'customer-1@id-a_8084' in customer_2_rotated_supplier_producers

    assert customer_1_old_queue_id not in kw.queue_stream_list_v1(customer_2_rotated_supplier_name, extract_ids=True)
    assert customer_1_rotated_queue_id in kw.queue_stream_list_v1(customer_2_rotated_supplier_name, extract_ids=True)

    # verify new supplier accepted customer-1
    customer_1_rotated_supplier_consumers = kw.queue_consumer_list_v1(customer_1_rotated_supplier_name, extract_ids=True)
    assert 'customer-2@id-b_8084' in customer_1_rotated_supplier_consumers
    assert 'customer-1@id-a_8084' in customer_1_rotated_supplier_consumers
    customer_1_rotated_supplier_producers = kw.queue_producer_list_v1(customer_1_rotated_supplier_name, extract_ids=True)
    assert 'customer-2@id-b_8084' in customer_1_rotated_supplier_producers
    assert 'customer-1@id-a_8084' in customer_1_rotated_supplier_producers

    assert customer_1_old_queue_id not in kw.queue_stream_list_v1(customer_1_rotated_supplier_name, extract_ids=True)
    assert customer_1_rotated_queue_id in kw.queue_stream_list_v1(customer_1_rotated_supplier_name, extract_ids=True)

    # send one message from customer-1 to the group after supplier IDURL was rotated
    group_customers_1_rotated_messages.append(
        kw.verify_message_sent_received(
            customer_1_group_key_id,
            producer_id='customer-1',
            consumers_ids=[
                'customer-1',
                'customer-2',
            ],
            message_label='H',
            expected_results={
                'customer-1': True,
                'customer-2': True,
            },
            polling_timeout=120,
            receive_timeout=121,
        )
    )

    customer_2_group_info_rotated = kw.group_info_v1('customer-2', customer_1_group_key_id, wait_state='CONNECTED')['result']
    assert customer_2_group_info_rotated['state'] == 'CONNECTED'
    assert customer_2_group_info_rotated['last_sequence_id'] > 0
    customer_1_group_info_rotated = kw.group_info_v1('customer-1', customer_1_group_key_id, wait_state='CONNECTED')['result']
    assert customer_1_group_info_rotated['state'] == 'CONNECTED'
    assert customer_1_group_info_rotated['last_sequence_id'] > 0

    # sending again few messages to the group from customer-1
    for i in range(5):
        group_customers_1_rotated_messages.append(
            kw.verify_message_sent_received(
                customer_1_group_key_id,
                producer_id='customer-1',
                consumers_ids=[
                    'customer-1',
                    'customer-2',
                ],
                message_label='I%d' % (i + 1),
                expected_results={
                    'customer-1': True,
                    'customer-2': True,
                },
            )
        )

    # verify groups info after supplier IDURL rotated
    assert kw.group_info_v1('customer-2', customer_1_group_key_id, wait_state='CONNECTED')['result']['state'] == 'CONNECTED'
    assert kw.group_info_v1('customer-2', customer_1_group2_key_id, wait_state='CONNECTED')['result']['state'] == 'CONNECTED'
    assert kw.group_info_v1('customer-1', customer_1_group_key_id, wait_state='CONNECTED')['result']['state'] == 'CONNECTED'
    assert kw.group_info_v1('customer-1', customer_1_group2_key_id, wait_state='CONNECTED')['result']['state'] == 'CONNECTED'

    assert kw.group_info_v1('customer-1', customer_1_group_key_id)['result']['last_sequence_id'] > 0
    assert kw.group_info_v1('customer-2', customer_1_group_key_id)['result']['last_sequence_id'] > 0
    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 12
    assert len(kw.message_history_v1('customer-2', customer_1_group_key_id, message_type='group_message')['result']) == 12

    # customer-2 and customer-1 leave from the both groups
    kw.group_leave_v1('customer-1', customer_1_group_key_id)
    kw.group_leave_v1('customer-2', customer_1_group_key_id)
    kw.group_leave_v1('customer-1', customer_1_group2_key_id)
    kw.group_leave_v1('customer-2', customer_1_group2_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS_12)

    assert customer_1_old_queue_id not in kw.queue_stream_list_v1(customer_1_old_supplier_name, extract_ids=True)
    assert customer_1_rotated_queue_id not in kw.queue_stream_list_v1(customer_1_old_supplier_name, extract_ids=True)

    customer_1_group_info_offline = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_offline['state'] == 'DISCONNECTED'
    assert customer_1_group_info_offline['label'] == 'SCENARIO12_MyGroupABC'
    assert customer_1_group_info_offline['last_sequence_id'] > 0

    customer_2_group_info_offline = kw.group_info_v1('customer-2', customer_1_group_key_id)['result']
    assert customer_2_group_info_offline['state'] == 'DISCONNECTED'
    assert customer_2_group_info_offline['label'] == 'SCENARIO12_MyGroupABC'
    assert customer_2_group_info_offline['last_sequence_id'] > 0
    msg('\n[SCENARIO 12 end] : PASS\n\n')


def scenario13_begin():
    set_active_scenario('SCENARIO 13 begin')
    msg('\n\n============\n[SCENARIO 13] one of the suppliers of customer-1 has IDURL rotated')

    # make sure supplier-rotated was hired by customer-1
    old_customer_1_suppliers_idurls = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert 'http://id-dead:8084/supplier-rotated.xml' in old_customer_1_suppliers_idurls
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-1@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
        accepted_mistakes=0,
    )

    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')

    # create a share
    old_share_id_customer_1 = kw.share_create_v1('customer-1')

    # make sure shared location is activated
    kw.share_open_v1('customer-1', old_share_id_customer_1)

    # upload some files for customer-1
    customer_1_local_filepath, customer_1_remote_path, customer_1_download_filepath = kw.verify_file_create_upload_start(
        node='customer-1',
        key_id=old_share_id_customer_1,
        volume_path='/customer_1',
        filename='file_encrypted_with_shared_key_customer_1.txt',
        randomize_bytes=300,
    )
    # make sure we can download the file back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_remote_path,
        destination_path=customer_1_download_filepath,
        verify_from_local_path=customer_1_local_filepath,
    )
    msg('\n[SCENARIO 13 begin] : DONE\n\n')
    return {
        'suppliers_idurls': old_customer_1_suppliers_idurls,
        'share_id': old_share_id_customer_1,
        'local_filepath': customer_1_local_filepath,
        'remote_path': customer_1_remote_path,
        'download_filepath': customer_1_download_filepath,
    }


def scenario13_end(old_customer_1_info):
    set_active_scenario('SCENARIO 13 end')
    msg('\n\n============\n[SCENARIO 13] one of the suppliers of customer-1 has IDURL rotated')

    # erase previous file on customer-1 and prepare to download it again
    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')
    kw.share_open_v1('customer-1', old_customer_1_info['share_id'])
    run_ssh_command_and_wait('customer-1', 'rm -rfv %s' % old_customer_1_info['download_filepath'], verbose=ssh_cmd_verbose)[0].strip()

    # verify customer-1 still able to download the files
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=old_customer_1_info['remote_path'],
        destination_path=old_customer_1_info['download_filepath'],
        verify_from_local_path=old_customer_1_info['local_filepath'],
    )
    kw.wait_packets_finished(
        CUSTOMERS_IDS_1 + SUPPLIERS_IDS_12 + [
            'supplier-rotated',
        ],
    )

    # disable supplier-rotated so it will not affect other scenarios
    request_get('supplier-rotated', 'process/stop/v1', verbose=True, raise_error=False)
    kw.wait_packets_finished(CUSTOMERS_IDS_1 + SUPPLIERS_IDS_12)

    # verify customer-1 still able to download the files
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=old_customer_1_info['remote_path'],
        destination_path=old_customer_1_info['download_filepath'],
        verify_from_local_path=old_customer_1_info['local_filepath'],
    )
    kw.wait_packets_finished(CUSTOMERS_IDS_1 + SUPPLIERS_IDS_12)
    msg('\n[SCENARIO 13 end] : PASS\n\n')


def scenario14(old_customer_1_info, customer_1_shared_file_info):
    set_active_scenario('SCENARIO 14')
    msg('\n\n============\n[SCENARIO 14] customer-1 replace supplier at position 0')

    kw.wait_packets_finished(PROXY_IDS + CUSTOMERS_IDS_12 + SUPPLIERS_IDS)

    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-1@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'supplier-2@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    customer_1_supplier_idurls_before = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert len(customer_1_supplier_idurls_before) == 2

    kw.file_list_all_v1('customer-1', reliable_shares=True, expected_reliable=100)

    possible_suppliers = set([
        'http://id-a:8084/supplier-1.xml',
        'http://id-a:8084/supplier-2.xml',
        'http://id-a:8084/supplier-3.xml',
        'http://id-a:8084/supplier-4.xml',
        'http://id-a:8084/supplier-5.xml',
    ])
    possible_suppliers.discard(customer_1_supplier_idurls_before[0])

    response = request_post('customer-1', 'supplier/change/v1', json={'position': '0'})
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    kw.wait_packets_finished(PROXY_IDS + SUPPLIERS_IDS + CUSTOMERS_IDS_12)

    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')

    # make sure supplier was replaced
    attempts = 1
    while True:
        success = False
        count = 0
        while True:
            if count > 20:
                break
            customer_1_supplier_idurls_after = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2, verbose=False)
            assert len(customer_1_supplier_idurls_after) == 2
            assert customer_1_supplier_idurls_after[1] == customer_1_supplier_idurls_after[1]
            if customer_1_supplier_idurls_before[0] != customer_1_supplier_idurls_after[0]:
                success = True
                break
            count += 1
            time.sleep(3)
        if success:
            break
        if attempts > 5:
            assert False, 'supplier was not replaced after many attempts'
        attempts += 1
        response = request_post('customer-1', 'supplier/change/v1', json={'position': '0'})
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        kw.wait_packets_finished(PROXY_IDS + SUPPLIERS_IDS + CUSTOMERS_IDS_12)
        kw.service_info_v1('customer-1', 'service_shared_data', 'ON')

    kw.wait_packets_finished(SUPPLIERS_IDS + CUSTOMERS_IDS_12)

    customer_1_supplier_idurls_after = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert customer_1_supplier_idurls_after != customer_1_supplier_idurls_before

    kw.file_sync_v1('customer-1')

    kw.wait_packets_finished(SUPPLIERS_IDS + CUSTOMERS_IDS_12)

    kw.file_list_all_v1('customer-1', reliable_shares=True, expected_reliable=100)

    # make sure we can still download the file back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=old_customer_1_info['remote_path'],
        destination_path=old_customer_1_info['download_filepath'],
        verify_from_local_path=old_customer_1_info['local_filepath'],
    )

    # make sure we can still download the file shared by customer-2 back on customer-1
    kw.share_info_v1('customer-1', customer_1_shared_file_info['share_id'], wait_state='CONNECTED')
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_shared_file_info['remote_path'],
        destination_path=customer_1_shared_file_info['download_filepath'],
        verify_from_local_path=customer_1_shared_file_info['local_filepath'],
    )
    msg('\n[SCENARIO 14 begin] : DONE\n\n')


def scenario15(old_customer_1_info, customer_1_shared_file_info):
    set_active_scenario('SCENARIO 15')
    msg('\n\n============\n[SCENARIO 15] customer-1 switch supplier at position 1 to specific node')

    customer_1_supplier_idurls_before = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert len(customer_1_supplier_idurls_before) == 2

    possible_suppliers = set([
        'http://id-a:8084/supplier-1.xml',
        'http://id-a:8084/supplier-2.xml',
        'http://id-a:8084/supplier-3.xml',
        'http://id-a:8084/supplier-4.xml',
        'http://id-a:8084/supplier-5.xml',
    ])
    possible_suppliers.difference_update(set(customer_1_supplier_idurls_before))
    new_supplier_idurl = list(possible_suppliers)[0]

    attempts = 0
    success = False
    while True:
        attempts += 1
        response = request_put(
            'customer-1',
            'supplier/switch/v1',
            json={
                'position': '1',
                'new_idurl': new_supplier_idurl,
            },
        )
        assert response.status_code == 200
    
        # make sure supplier was really switched
        count = 0
        while True:
            if count > 20:
                if attempts > 2:
                    assert False, 'supplier was not switched after %d attempts' % attempts
                break
            customer_1_supplier_idurls_after = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
            assert len(customer_1_supplier_idurls_after) == 2
            assert customer_1_supplier_idurls_after[0] == customer_1_supplier_idurls_after[0]
            if customer_1_supplier_idurls_before[1] != customer_1_supplier_idurls_after[1]:
                success = True
                break
            count += 1
            time.sleep(1)

        if success:
            break

    kw.wait_packets_finished(SUPPLIERS_IDS + CUSTOMERS_IDS_12)

    customer_1_supplier_idurls_after = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert customer_1_supplier_idurls_after != customer_1_supplier_idurls_before

    kw.file_sync_v1('customer-1')

    kw.wait_packets_finished(SUPPLIERS_IDS + CUSTOMERS_IDS_12)

    # make sure we can still download the file back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=old_customer_1_info['remote_path'],
        destination_path=old_customer_1_info['download_filepath'],
        verify_from_local_path=old_customer_1_info['local_filepath'],
    )

    # make sure we can still download the file shared by customer-2 back on customer-1
    kw.share_info_v1('customer-1', customer_1_shared_file_info['share_id'], wait_state='CONNECTED')
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_shared_file_info['remote_path'],
        destination_path=customer_1_shared_file_info['download_filepath'],
        verify_from_local_path=customer_1_shared_file_info['local_filepath'],
    )
    msg('\n[SCENARIO 15] : PASS\n\n')


def scenario16():
    set_active_scenario('SCENARIO 16')
    msg('\n\n============\n[SCENARIO 16] customer-1 increase and decrease suppliers amount')

    customer_1_supplier_idurls_before = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert len(customer_1_supplier_idurls_before) == 2

    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-1@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-2@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'supplier-2@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    kw.config_set_v1('customer-1', 'services/customer/suppliers-number', '4')

    kw.wait_packets_finished(SUPPLIERS_IDS + CUSTOMERS_IDS_12)

    customer_1_supplier_idurls_increase = kw.supplier_list_v1('customer-1', expected_min_suppliers=4, expected_max_suppliers=4)
    assert len(customer_1_supplier_idurls_increase) == 4

    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')

    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-1@id-a_8084',
        ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-2@id-a_8084',
        ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'supplier-2@id-a_8084',
        ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )

    kw.config_set_v1('customer-1', 'services/customer/suppliers-number', '2')

    kw.wait_packets_finished(SUPPLIERS_IDS + CUSTOMERS_IDS_12)

    customer_1_supplier_idurls_decrease = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert len(customer_1_supplier_idurls_decrease) == 2

    kw.service_info_v1('customer-1', 'service_shared_data', 'ON')

    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-1@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-2@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'supplier-2@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    msg('\n[SCENARIO 16] : PASS\n\n')


def scenario17(old_customer_1_info, old_customer_2_info):
    set_active_scenario('SCENARIO 17')
    msg('\n\n============\n[SCENARIO 17] customer-2 went offline and customer-restore recover identity from customer-2')

    # backup customer-2 private key
    backup_file_directory_c2 = '/customer_2/identity.backup'
    backup_file_directory_c3 = '/customer_restore/identity.backup'
    assert not os.path.exists(backup_file_directory_c2)

    response = request_post(
        'customer-2',
        'identity/backup/v1',
        json={
            'destination_filepath': backup_file_directory_c2,
        },
    )
    dbg('\nidentity/backup/v1 [customer-2] : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()

    # copy private key from one container to another
    # just like when you backup your private key and restore it from USB stick on another device
    shutil.move(backup_file_directory_c2, backup_file_directory_c3)

    # before start the restore make sure all files actually are delivered to suppliers
    kw.file_sync_v1('customer-1')
    kw.file_sync_v1('customer-2')
    kw.file_list_all_v1('customer-2', expected_reliable=100, reliable_shares=True, attempts=20)

    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_shared_data', 'ON')
    kw.wait_packets_finished(PROXY_IDS + SUPPLIERS_IDS_12 + CUSTOMERS_IDS_12)

    # now try to download again shared by customer-1 cat.txt file on customer-2
    kw.verify_file_download_start(
        node='customer-2',
        remote_path=old_customer_1_info['remote_path'],
        destination_path='/customer_2/cat_shared/cat_again.txt',
        reliable_shares=False,
        expected_reliable=100,
    )

    kw.file_sync_v1('customer-1')
    kw.file_sync_v1('customer-2')
    kw.file_list_all_v1('customer-2', expected_reliable=100, reliable_shares=True, attempts=20)

    kw.wait_service_state(CUSTOMERS_IDS_12, 'service_shared_data', 'ON')
    kw.wait_packets_finished(PROXY_IDS + SUPPLIERS_IDS_12 + CUSTOMERS_IDS_12)

    # stop customer-2 node
    request_get('customer-2', 'process/stop/v1', verbose=True, raise_error=False)

    kw.wait_service_state(CUSTOMERS_IDS_1, 'service_shared_data', 'ON')
    kw.wait_packets_finished(PROXY_IDS + SUPPLIERS_IDS_12 + CUSTOMERS_IDS_1)

    # recover key on customer-restore container and join network
    for _ in range(5):
        response = request_post(
            'customer-restore',
            'identity/recover/v1',
            json={
                'private_key_local_file': backup_file_directory_c3,
                'join_network': '1',
            },
        )
        dbg('\n\nidentity/recover/v1 : %s\n' % response.json())
        if response.json()['status'] == 'OK':
            break
        time.sleep(1)
    else:
        assert False, 'customer-restore was not able to recover identity after few attempts'

    kw.service_info_v1('customer-restore', 'service_customer', 'ON')
    kw.service_info_v1('customer-restore', 'service_keys_storage', 'ON')
    kw.service_info_v1('customer-restore', 'service_my_data', 'ON')
    kw.service_info_v1('customer-restore', 'service_shared_data', 'ON', attempts=20)

    kw.service_health_v1('customer-restore', 'service_keys_storage')

    kw.supplier_list_v1('customer-restore', expected_min_suppliers=2, expected_max_suppliers=2)

    kw.supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=[
            'customer-restore@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    kw.supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=[
            'supplier-1@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    kw.supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=[
            'supplier-2@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    # make sure both shared locations are activated
    kw.share_open_v1('customer-restore', old_customer_1_info['share_id'])
    kw.share_open_v1('customer-restore', old_customer_2_info['share_id'])

    kw.file_sync_v1('customer-restore')

    # TODO:
    # test my keys are also recovered
    # test my message history also recovered
    kw.file_list_all_v1('customer-restore', expected_reliable=100, reliable_shares=False, attempts=20)

    # try to recover stored file again
    kw.verify_file_download_start(
        node='customer-restore',
        remote_path=old_customer_2_info['remote_path'],
        destination_path=old_customer_2_info['download_filepath'],
        expected_reliable=100,
        reliable_shares=False,
        download_attempts=5,
    )
    msg('\n[SCENARIO 17] : PASS\n\n')



def scenario18_begin():
    set_active_scenario('SCENARIO 18')
    msg('\n\n============\n[SCENARIO 18] customer-rotated IDURL was rotated but still able to comunicate in the group')

    CUSTOMERS_IDS_1_ROTATED = CUSTOMERS_IDS_1 + ['customer-rotated', ]

    # create group owned by customer-1 and join
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_private_groups', 'ON')
    customer_1_group_key_id = kw.group_create_v1('customer-1', label='SCENARIO18_MyGroupABC')
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED)

    customer_1_group_info_inactive = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_inactive['state'] == 'DISCONNECTED'
    assert customer_1_group_info_inactive['label'] == 'SCENARIO18_MyGroupABC'
    assert customer_1_group_info_inactive['last_sequence_id'] == -1

    kw.group_join_v1('customer-1', customer_1_group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED + SUPPLIERS_IDS_12)

    customer_1_group_info_active = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_active['state'] == 'CONNECTED'
    assert customer_1_group_info_active['last_sequence_id'] == -1

    customer_1_active_queue_id = customer_1_group_info_active['active_queue_id']
    customer_1_active_supplier_name = customer_1_group_info_active['active_supplier_id'].split('@')[0]

    assert customer_1_active_queue_id in kw.queue_list_v1(customer_1_active_supplier_name, extract_ids=True)

    customer_1_supplier_consumers = kw.queue_consumer_list_v1(customer_1_active_supplier_name, extract_ids=True, ignore_aliases=['supplier-file-modified',])
    customer_1_supplier_producers = kw.queue_producer_list_v1(customer_1_active_supplier_name, extract_ids=True, ignore_aliases=['supplier-file-modified',])
    assert 'customer-1@id-a_8084' in customer_1_supplier_consumers
    assert 'customer-1@id-a_8084' in customer_1_supplier_producers
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)

    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 0

    # sending few messages to the group from customer-1
    for i in range(3):
        kw.verify_message_sent_received(
            customer_1_group_key_id,
            producer_id='customer-1',
            consumers_ids=[
                'customer-1',
            ],
            message_label='A%d' % (i + 1),
            expected_results={
                'customer-1': True,
            },
        )

    assert kw.group_info_v1('customer-1', customer_1_group_key_id)['result']['last_sequence_id'] > 0
    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 3

    # share group key from customer-1 to customer-rotated
    kw.group_share_v1('customer-1', customer_1_group_key_id, 'customer-rotated@id-dead_8084')

    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED)

    # customer-rotated joins the group
    kw.group_join_v1('customer-rotated', customer_1_group_key_id)
    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED + SUPPLIERS_IDS_12)

    # customer-rotated must also see all messages that were sent to the group
    for _ in range(15):
        time.sleep(1)
        last_sequence_id = kw.group_info_v1('customer-rotated', customer_1_group_key_id)['result']['last_sequence_id']
        if last_sequence_id > 0:
            break
    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 3
    assert len(kw.message_history_v1('customer-rotated', customer_1_group_key_id, message_type='group_message')['result']) == 3

    customer_1_supplier_consumers = kw.queue_consumer_list_v1(customer_1_active_supplier_name, extract_ids=True, ignore_aliases=['supplier-file-modified',])
    customer_1_supplier_producers = kw.queue_producer_list_v1(customer_1_active_supplier_name, extract_ids=True, ignore_aliases=['supplier-file-modified',])
    assert 'customer-1@id-a_8084' in customer_1_supplier_consumers
    assert 'customer-1@id-a_8084' in customer_1_supplier_producers
    assert 'customer-rotated@id-dead_8084' in customer_1_supplier_consumers
    assert 'customer-rotated@id-dead_8084' in customer_1_supplier_producers
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)

    # sending few more messages to the group from customer-rotated
    for i in range(3):
        kw.verify_message_sent_received(
            customer_1_group_key_id,
            producer_id='customer-rotated',
            consumers_ids=[
                'customer-1',
                'customer-rotated',
            ],
            message_label='B%d' % (i + 1),
            expected_results={
                'customer-1': True,
                'customer-rotated': True,
            },
        )

    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 6
    assert len(kw.message_history_v1('customer-rotated', customer_1_group_key_id, message_type='group_message')['result']) == 6

    customer_1_active_queue_id = customer_1_group_info_active['active_queue_id']
    customer_1_active_supplier_name = customer_1_group_info_active['active_supplier_id'].split('@')[0]
    assert customer_1_active_queue_id in kw.queue_list_v1(customer_1_active_supplier_name, extract_ids=True)
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)

    customer_rotated_group_info_active = kw.group_info_v1('customer-rotated', customer_1_group_key_id)['result']
    assert customer_rotated_group_info_active['state'] == 'CONNECTED'
    customer_rotated_active_queue_id = customer_rotated_group_info_active['active_queue_id']
    customer_rotated_active_supplier_name = customer_rotated_group_info_active['active_supplier_id'].split('@')[0]
    assert customer_rotated_active_queue_id in kw.queue_list_v1(customer_rotated_active_supplier_name, extract_ids=True)
    assert customer_rotated_active_queue_id in kw.queue_stream_list_v1(customer_rotated_active_supplier_name, extract_ids=True)

    # vice-versa, create group owned by customer-rotated and join
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_private_groups', 'ON')
    customer_rotated_group_key_id = kw.group_create_v1('customer-rotated', label='SCENARIO18_MyGroupDEF')
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED)

    customer_rotated_group_info_inactive = kw.group_info_v1('customer-rotated', customer_rotated_group_key_id)['result']
    assert customer_rotated_group_info_inactive['state'] == 'DISCONNECTED'
    assert customer_rotated_group_info_inactive['label'] == 'SCENARIO18_MyGroupDEF'
    assert customer_rotated_group_info_inactive['last_sequence_id'] == -1

    kw.group_join_v1('customer-rotated', customer_rotated_group_key_id)
    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED + SUPPLIERS_IDS_12)

    customer_rotated_group_info_active = kw.group_info_v1('customer-rotated', customer_rotated_group_key_id)['result']
    assert customer_rotated_group_info_active['state'] == 'CONNECTED'
    assert customer_rotated_group_info_active['last_sequence_id'] == -1

    customer_rotated_rotated_active_queue_id = customer_rotated_group_info_active['active_queue_id']
    customer_rotated_rotated_active_supplier_name = customer_rotated_group_info_active['active_supplier_id'].split('@')[0]

    assert customer_rotated_active_queue_id in kw.queue_list_v1(customer_rotated_active_supplier_name, extract_ids=True)

    customer_rotated_supplier_consumers = kw.queue_consumer_list_v1(customer_rotated_active_supplier_name, extract_ids=True, ignore_aliases=['supplier-file-modified',])
    customer_rotated_supplier_producers = kw.queue_producer_list_v1(customer_rotated_active_supplier_name, extract_ids=True, ignore_aliases=['supplier-file-modified',])
    assert 'customer-rotated@id-dead_8084' in customer_rotated_supplier_consumers
    assert 'customer-rotated@id-dead_8084' in customer_rotated_supplier_producers
    assert customer_rotated_active_queue_id in kw.queue_stream_list_v1(customer_rotated_active_supplier_name, extract_ids=True)

    assert len(kw.message_history_v1('customer-rotated', customer_rotated_group_key_id, message_type='group_message')['result']) == 0

    # sending few messages to the group from customer-rotated
    for i in range(3):
        kw.verify_message_sent_received(
            customer_rotated_group_key_id,
            producer_id='customer-rotated',
            consumers_ids=[
                'customer-rotated',
            ],
            message_label='C%d' % (i + 1),
            expected_results={
                'customer-rotated': True,
            },
        )

    assert kw.group_info_v1('customer-rotated', customer_rotated_group_key_id)['result']['last_sequence_id'] > 0
    assert len(kw.message_history_v1('customer-rotated', customer_rotated_group_key_id, message_type='group_message')['result']) == 3

    # share group key from customer-1 to customer-rotated
    kw.group_share_v1('customer-rotated', customer_rotated_group_key_id, 'customer-1@id-a_8084')

    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED)

    # customer-1 joins the second group
    kw.group_join_v1('customer-1', customer_rotated_group_key_id)
    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED + SUPPLIERS_IDS_12)

    kw.group_info_v1('customer-1', customer_rotated_group_key_id, wait_state='CONNECTED')['result']
    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED + SUPPLIERS_IDS_12)

    # customer-1 must also see all messages that were sent to the second group
    for _ in range(15):
        time.sleep(1)
        last_sequence_id = kw.group_info_v1('customer-1', customer_rotated_group_key_id)['result']['last_sequence_id']
        if last_sequence_id > 0:
            break
    assert len(kw.message_history_v1('customer-1', customer_rotated_group_key_id, message_type='group_message')['result']) == 3
    assert len(kw.message_history_v1('customer-rotated', customer_rotated_group_key_id, message_type='group_message')['result']) == 3

    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 6
    assert len(kw.message_history_v1('customer-rotated', customer_1_group_key_id, message_type='group_message')['result']) == 6

    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED)

    msg('\n[SCENARIO 18 begin] : DONE\n\n')
    return {
        'group_key_id': customer_1_group_key_id,
        'customer_1_active_queue_id': customer_1_active_queue_id,
        'customer_1_active_supplier_name': customer_1_active_supplier_name,
        'customer_rotated_active_queue_id': customer_rotated_active_queue_id,
        'customer_rotated_active_supplier_name': customer_rotated_active_supplier_name,
        'customer_rotated_group_key_id': customer_rotated_group_key_id,
        'customer_rotated_rotated_active_queue_id': customer_rotated_rotated_active_queue_id,
        'customer_rotated_rotated_active_supplier_name': customer_rotated_rotated_active_supplier_name,
    }



def scenario18_end(old_info):
    global group_customers_1_rotated_messages
    set_active_scenario('SCENARIO 18 end')
    msg('\n\n============\n[SCENARIO 18] customer-rotated IDURL was rotated but still able to comunicate in the group')

    customer_1_group_key_id = old_info['group_key_id']
    customer_rotated_group_key_id = old_info['customer_rotated_group_key_id']

    CUSTOMERS_IDS_1_ROTATED = CUSTOMERS_IDS_1 + ['customer-rotated', ]

    kw.wait_service_state(CUSTOMERS_IDS_1_ROTATED, 'service_private_groups', 'ON')

    # verify customer-rotated group state before sending a new message
    customer_rotated_group_info_after = kw.group_info_v1('customer-rotated', customer_1_group_key_id, wait_state='CONNECTED')['result']
    assert customer_rotated_group_info_after['state'] == 'CONNECTED'
    customer_rotated_active_queue_id_after = customer_rotated_group_info_after['active_queue_id']
    customer_rotated_active_supplier_name_after = customer_rotated_group_info_after['active_supplier_id'].split('@')[0]

    # verify customer-rotated second group state as well
    customer_rotated_group_rotated_info_after = kw.group_info_v1('customer-rotated', customer_rotated_group_key_id, wait_state='CONNECTED')['result']
    assert customer_rotated_group_rotated_info_after['state'] == 'CONNECTED'
    customer_rotated_rotated_active_queue_id_after = customer_rotated_group_rotated_info_after['active_queue_id']
    customer_rotated_rotated_active_supplier_name_after = customer_rotated_group_rotated_info_after['active_supplier_id'].split('@')[0]

    # the second group key ID must actualy be rotated already
    assert customer_rotated_group_key_id != customer_rotated_group_rotated_info_after['group_key_id']

    # also active queue id suppose to change
    assert old_info['customer_rotated_rotated_active_queue_id'] != customer_rotated_rotated_active_queue_id_after
    assert old_info['customer_rotated_rotated_active_supplier_name'] == customer_rotated_rotated_active_supplier_name_after
    
    # verify streams are still configured and connected
    assert customer_rotated_active_queue_id_after in kw.queue_list_v1(customer_rotated_active_supplier_name_after, extract_ids=True)
    assert customer_rotated_active_queue_id_after in kw.queue_stream_list_v1(customer_rotated_active_supplier_name_after, extract_ids=True)
    assert customer_rotated_rotated_active_queue_id_after in kw.queue_list_v1(customer_rotated_rotated_active_supplier_name_after, extract_ids=True)
    assert customer_rotated_rotated_active_queue_id_after in kw.queue_stream_list_v1(customer_rotated_rotated_active_supplier_name_after, extract_ids=True)

    customer_rotated_supplier_consumers_after = kw.queue_consumer_list_v1(customer_rotated_active_supplier_name_after, extract_ids=True, ignore_aliases=['supplier-file-modified',])
    customer_rotated_supplier_producers_after = kw.queue_producer_list_v1(customer_rotated_active_supplier_name_after, extract_ids=True, ignore_aliases=['supplier-file-modified',])
    assert 'customer-1@id-a_8084' in customer_rotated_supplier_consumers_after
    assert 'customer-1@id-a_8084' in customer_rotated_supplier_producers_after
    assert 'customer-rotated@id-a_8084' in customer_rotated_supplier_consumers_after
    assert 'customer-rotated@id-a_8084' in customer_rotated_supplier_producers_after
    assert 'customer-rotated@id-dead_8084' not in customer_rotated_supplier_consumers_after
    assert 'customer-rotated@id-dead_8084' not in customer_rotated_supplier_producers_after

    customer_1_group_info_before = kw.group_info_v1('customer-1', customer_1_group_key_id, wait_state='CONNECTED')['result']
    assert customer_1_group_info_before['state'] == 'CONNECTED'
    customer_rotated_group_info_before = kw.group_info_v1('customer-rotated', customer_1_group_key_id, wait_state='CONNECTED')['result']
    assert customer_rotated_group_info_before['state'] == 'CONNECTED'

    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 6
    assert len(kw.message_history_v1('customer-rotated', customer_1_group_key_id, message_type='group_message')['result']) == 6
    assert len(kw.message_history_v1('customer-1', customer_rotated_group_key_id, message_type='group_message')['result']) == 3
    assert len(kw.message_history_v1('customer-rotated', customer_rotated_group_key_id, message_type='group_message')['result']) == 3

    # sending few more messages to the group from customer-1
    for i in range(3):
        kw.verify_message_sent_received(
            customer_1_group_key_id,
            producer_id='customer-1',
            consumers_ids=[
                'customer-1',
                'customer-rotated',
            ],
            message_label='D%d' % (i + 1),
            expected_results={
                'customer-1': True,
                'customer-rotated': True,
            },
        )

    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 9
    assert len(kw.message_history_v1('customer-rotated', customer_1_group_key_id, message_type='group_message')['result']) == 9

    # sending few more messages to the second group from customer-1 as well
    for i in range(3):
        kw.verify_message_sent_received(
            customer_rotated_group_key_id,
            producer_id='customer-1',
            consumers_ids=[
                'customer-1',
                'customer-rotated',
            ],
            message_label='E%d' % (i + 1),
            expected_results={
                'customer-1': True,
                'customer-rotated': True,
            },
        )

    assert len(kw.message_history_v1('customer-1', customer_rotated_group_key_id, message_type='group_message')['result']) == 6
    assert len(kw.message_history_v1('customer-rotated', customer_rotated_group_key_id, message_type='group_message')['result']) == 6

    kw.wait_packets_finished(CUSTOMERS_IDS_1_ROTATED + SUPPLIERS_IDS_12)

    msg('\n[SCENARIO 18 end] : DONE\n\n')



def scenario19():
    set_active_scenario('SCENARIO 19')
    msg('\n\n============\n[SCENARIO 19] customer-2 added direct API device and able to accept remote web-socket connections')

    response = request_post(
        'customer-2',
        'device/add/v1',
        json={
            'name': 'device_DEF',
            'routed': False,
            'web_socket_host': 'customer-2',
            'web_socket_port': 8281,
            'activate': True,
            'wait_listening': False,
            'key_size': 1024,
        },
    )
    assert response.status_code == 200
    dbg('device/add/v1 [customer-2] name=device_DEF : %s\n' % pprint.pformat(response.json()))
    assert response.json()['status'] == 'OK', response.json()

    response = request_get('customer-2', 'device/info/v1?name=device_DEF')
    assert response.status_code == 200
    dbg('device/info/v1 [customer-2] name=device_DEF : %s\n' % pprint.pformat(response.json()))
    assert response.json()['status'] == 'OK', response.json()

    response = request_post(
        'customer-2',
        'device/start/v1',
        json={
            'name': 'device_DEF',
        },
    )
    assert response.status_code == 200
    dbg('device/start/v1 [customer-2] name=device_DEF : %s\n' % pprint.pformat(response.json()))
    assert response.json()['status'] == 'OK', response.json()

    ws_url = None
    counter = 0
    while counter < 30:
        time.sleep(5)
        counter += 1
        response = request_get('customer-2', 'device/info/v1?name=device_DEF')
        assert response.status_code == 200
        dbg('device/info/v1 [customer-2] name=device_DEF : %s\n' % pprint.pformat(response.json()))
        assert response.json()['status'] == 'OK', response.json()
        ws_url = response.json()['result'].get('url')
        if (response.json()['result'].get('instance') or {}).get('state') in ['CLIENT_PUB?', 'READY']:
            break

    if not ws_url:
        assert False, 'web socket url is unknown'

    if counter >= 20:
        assert False, 'web socket was not started'

    open('client.json', 'w').write(json.dumps({
        'routers': [ws_url, ],
    }))
    def _test_client():
        counter = 0
        test_ws_app = ws_client.TestApp()
        test_ws_app.begin()
        while not test_ws_app.completed:
            time.sleep(1)
            counter += 1
            dbg('    ... %d' % counter)
        open('scenario19.txt', 'wt').write('completed')

    test_client_thread = threading.Thread(target=_test_client)
    test_client_thread.daemon = True
    test_client_thread.start()
    test_client_thread.join(timeout=30)
    assert 'completed' == open('scenario19.txt', 'rt').read()

    msg('\n[SCENARIO 19] : PASS\n\n')



def scenario23(customer_1_file_info, customer_1_shared_file_info):
    set_active_scenario('SCENARIO 23')
    msg('\n\n============\n[SCENARIO 23] customer-1 able to upload/download files when one supplier is down')

    # cleanup first
    kw.config_set_v1('customer-1', 'services/employer/candidates', '')

    customer_1_suppliers = kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2, extract_suppliers=True)
    assert len(customer_1_suppliers) == 2

    first_supplier_name = customer_1_suppliers[0].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')
    other_suppliers = list(SUPPLIERS_IDS)
    other_suppliers.remove(first_supplier_name)

    # stop supplier node
    kw.wait_packets_finished(CUSTOMERS_IDS_12 + SUPPLIERS_IDS)
    request_get(first_supplier_name, 'process/stop/v1', verbose=True, raise_error=False)
    kw.wait_packets_finished(CUSTOMERS_IDS_12 + other_suppliers)

    # make sure we can still download the file back on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_file_info['remote_path'],
        destination_path=customer_1_file_info['download_filepath'],
        verify_from_local_path=customer_1_file_info['local_filepath'],
    )

    customer_1_share_info_after = kw.share_info_v1('customer-1', customer_1_shared_file_info['share_id'], wait_state='CONNECTED')
    assert len(customer_1_share_info_after['result']['suppliers']) == 2

    # make sure we can still download the shared file on customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_shared_file_info['remote_path'],
        destination_path=customer_1_shared_file_info['download_filepath'],
        verify_from_local_path=customer_1_shared_file_info['local_filepath'],
        expected_reliable=50,
    )

    # make sure we also able to download shared file on customer-2
    kw.verify_file_download_start(
        node='customer-2',
        remote_path=customer_1_shared_file_info['remote_path'],
        destination_path='/customer_2/cat_shared/cat_again.txt',
        reliable_shares=False,
        expected_reliable=50,
    )

    # start supplier node again
    start_daemon(first_supplier_name, skip_initialize=True, verbose=True)
    health_check(first_supplier_name, verbose=True)

    kw.wait_packets_finished(CUSTOMERS_IDS_12 + SUPPLIERS_IDS)
    kw.wait_service_state(
        [
            first_supplier_name,
        ],
        'service_supplier',
        'ON',
    )

    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)

    # make sure files are stored most reliable way again for customer-1
    kw.verify_file_download_start(
        node='customer-1',
        remote_path=customer_1_shared_file_info['remote_path'],
        destination_path=customer_1_shared_file_info['download_filepath'],
        verify_from_local_path=customer_1_shared_file_info['local_filepath'],
        expected_reliable=50,
    )

    msg('\n[SCENARIO 23] : PASS\n\n')


def scenario25():
    global group_customers_1_2_3_messages
    set_active_scenario('SCENARIO 25')
    msg('\n\n============\n[SCENARIO 25] customer-3 receive all past messages from other group participants')

    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    customer_1_conversations_count_before = len(kw.message_conversation_v1('customer-1')['result'])

    # create group owned by customer-1
    kw.service_info_v1('customer-1', 'service_private_groups', 'ON')
    customer_1_group_key_id = kw.group_create_v1('customer-1', label='SCENARIO25_ChatGroup')
    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    customer_1_conversations_count_after = len(kw.message_conversation_v1('customer-1')['result'])
    assert customer_1_conversations_count_before + 1 == customer_1_conversations_count_after

    customer_1_group_info_inactive = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_inactive['state'] == 'DISCONNECTED'
    assert customer_1_group_info_inactive['label'] == 'SCENARIO25_ChatGroup'
    assert customer_1_group_info_inactive['last_sequence_id'] == -1

    # first customer joins the group
    kw.group_join_v1('customer-1', customer_1_group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    customer_1_group_info_active = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_active['state'] == 'CONNECTED'
    assert customer_1_group_info_active['last_sequence_id'] == -1

    kw.automat_info_v1('customer-1', automat_index=customer_1_group_info_active['index'], expected_state='CONNECTED')

    customer_1_active_queue_id = customer_1_group_info_active['active_queue_id']
    customer_1_active_supplier_name = customer_1_group_info_active['active_supplier_id'].split('@')[0]

    assert customer_1_active_queue_id in kw.queue_list_v1(customer_1_active_supplier_name, extract_ids=True)

    customer_1_supplier_consumers = kw.queue_consumer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    customer_1_supplier_producers = kw.queue_producer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    assert len(customer_1_supplier_consumers) >= 1
    assert len(customer_1_supplier_producers) >= 1
    assert 'customer-1@id-a_8084' in customer_1_supplier_consumers
    assert 'customer-1@id-a_8084' in customer_1_supplier_producers
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)

    customer_2_conversations_count_before = len(kw.message_conversation_v1('customer-2')['result'])

    kw.file_list_all_v1('customer-2', expected_reliable=100, reliable_shares=True, attempts=20)

    # share group key from customer-1 to customer-2
    kw.group_share_v1('customer-1', customer_1_group_key_id, 'customer-2@id-a_8084')

    customer_2_conversations_count_after = len(kw.message_conversation_v1('customer-2')['result'])
    assert customer_2_conversations_count_before + 1 == customer_2_conversations_count_after

    # second member join the group
    kw.group_join_v1('customer-2', customer_1_group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    customer_2_group_info_active = kw.group_info_v1('customer-2', customer_1_group_key_id)['result']
    assert customer_2_group_info_active['state'] == 'CONNECTED'
    assert customer_2_group_info_active['last_sequence_id'] == -1

    customer_2_active_queue_id = customer_2_group_info_active['active_queue_id']
    customer_2_active_supplier_name = customer_2_group_info_active['active_supplier_id'].split('@')[0]

    customer_2_supplier_consumers = kw.queue_consumer_list_v1(customer_2_active_supplier_name, extract_ids=True)
    customer_2_supplier_producers = kw.queue_producer_list_v1(customer_2_active_supplier_name, extract_ids=True)
    assert 'customer-1@id-a_8084' in customer_2_supplier_consumers
    assert 'customer-1@id-a_8084' in customer_2_supplier_producers
    assert 'customer-2@id-a_8084' in customer_2_supplier_consumers
    assert 'customer-2@id-a_8084' in customer_2_supplier_producers
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)
    assert customer_2_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_2_active_supplier_name, extract_ids=True)
    assert customer_2_active_queue_id in kw.queue_stream_list_v1(customer_2_active_supplier_name, extract_ids=True)

    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', customer_1_group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-3', customer_1_group_key_id, message_type='group_message')['result']) == 0

    assert len(kw.message_conversation_v1('customer-1')['result']) == customer_1_conversations_count_after
    assert len(kw.message_conversation_v1('customer-2')['result']) == customer_2_conversations_count_after
    assert len(kw.message_conversation_v1('customer-3')['result']) == 0

    # sending messages to the group from customer-1
    for i in range(3):
        group_customers_1_2_3_messages.append(
            kw.verify_message_sent_received(
                customer_1_group_key_id,
                producer_id='customer-1',
                consumers_ids=[
                    'customer-1',
                    'customer-2',
                ],
                message_label='E%d' % (i + 1),
                expected_results={
                    'customer-1': True,
                    'customer-2': True,
                },
            )
        )

    # must be 3 archive snapshots created and 1 message not archived
    assert kw.group_info_v1('customer-1', customer_1_group_key_id)['result']['last_sequence_id'] > 0
    assert kw.group_info_v1('customer-2', customer_1_group_key_id)['result']['last_sequence_id'] > 0
    assert len(kw.message_history_v1('customer-1', customer_1_group_key_id, message_type='group_message')['result']) == 3
    assert len(kw.message_history_v1('customer-2', customer_1_group_key_id, message_type='group_message')['result']) == 3

    assert len(kw.message_conversation_v1('customer-1')['result']) == customer_1_conversations_count_after
    assert len(kw.message_conversation_v1('customer-2')['result']) == customer_2_conversations_count_after
    assert len(kw.message_conversation_v1('customer-3')['result']) == 0

    # customer 1 leave the group
    kw.group_leave_v1('customer-1', customer_1_group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    customer_1_supplier_consumers = kw.queue_consumer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    customer_1_supplier_producers = kw.queue_producer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    assert 'customer-1@id-a_8084' not in customer_1_supplier_producers
    assert 'customer-2@id-a_8084' in customer_1_supplier_consumers
    assert 'customer-2@id-a_8084' in customer_1_supplier_producers
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)

    customer_1_group_info_offline = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_offline['state'] == 'DISCONNECTED'
    assert customer_1_group_info_offline['label'] == 'SCENARIO25_ChatGroup'
    assert customer_1_group_info_offline['last_sequence_id'] > 0

    assert kw.group_info_v1('customer-2', customer_1_group_key_id)['result']['state'] == 'CONNECTED'

    assert len(kw.message_conversation_v1('customer-1')['result']) == customer_1_conversations_count_after
    assert len(kw.message_conversation_v1('customer-2')['result']) == customer_2_conversations_count_after
    assert len(kw.message_conversation_v1('customer-3')['result']) == 0

    # customer-2 share group key to customer-3
    kw.group_share_v1('customer-2', customer_1_group_key_id, 'customer-3@id-a_8084')

    assert len(kw.message_conversation_v1('customer-3')['result']) == 1

    # customer-3 join the group, other group members are offline
    kw.group_join_v1('customer-3', customer_1_group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS_123 + SUPPLIERS_IDS_12)

    customer_1_supplier_consumers = kw.queue_consumer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    customer_1_supplier_producers = kw.queue_producer_list_v1(customer_1_active_supplier_name, extract_ids=True)
    assert 'customer-3@id-a_8084' in customer_1_supplier_consumers
    assert 'customer-3@id-a_8084' in customer_1_supplier_producers
    assert customer_1_active_queue_id in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)

    # customer-3 must also see all messages that were sent to the group
    for _ in range(15):
        time.sleep(1)
        last_sequence_id = kw.group_info_v1('customer-3', customer_1_group_key_id)['result']['last_sequence_id']
        if last_sequence_id > 0:
            break
    assert len(kw.message_history_v1('customer-3', customer_1_group_key_id, message_type='group_message')['result']) == 3
    assert len(kw.message_conversation_v1('customer-3')['result']) == 1

    # now we send few more messages from customer-3
    for i in range(3):
        group_customers_1_2_3_messages.append(
            kw.verify_message_sent_received(
                customer_1_group_key_id,
                producer_id='customer-3',
                consumers_ids=[
                    'customer-3',
                    'customer-2',
                ],
                message_label='D%d' % (i + 1),
                expected_results={
                    'customer-3': True,
                    'customer-2': True,
                },
            )
        )

    # customers 2 and 3 leave the group
    kw.group_leave_v1('customer-2', customer_1_group_key_id)
    kw.group_leave_v1('customer-3', customer_1_group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    customer_1_group_info_offline = kw.group_info_v1('customer-1', customer_1_group_key_id)['result']
    assert customer_1_group_info_offline['state'] == 'DISCONNECTED'
    assert customer_1_group_info_offline['label'] == 'SCENARIO25_ChatGroup'
    assert customer_1_group_info_offline['last_sequence_id'] > 0

    customer_2_group_info_offline = kw.group_info_v1('customer-2', customer_1_group_key_id)['result']
    assert customer_2_group_info_offline['state'] == 'DISCONNECTED'
    assert customer_2_group_info_offline['label'] == 'SCENARIO25_ChatGroup'
    assert customer_2_group_info_offline['last_sequence_id'] > 0

    customer_3_group_info_offline = kw.group_info_v1('customer-3', customer_1_group_key_id)['result']
    assert customer_3_group_info_offline['state'] == 'DISCONNECTED'
    assert customer_3_group_info_offline['label'] == 'SCENARIO25_ChatGroup'
    assert customer_3_group_info_offline['last_sequence_id'] > 0

    assert len(kw.message_conversation_v1('customer-1')['result']) == customer_1_conversations_count_after
    assert len(kw.message_conversation_v1('customer-2')['result']) == customer_2_conversations_count_after
    assert len(kw.message_conversation_v1('customer-3')['result']) == 1

    assert customer_1_active_queue_id not in kw.queue_stream_list_v1(customer_1_active_supplier_name, extract_ids=True)
    msg('\n[SCENARIO 25] : PASS\n\n')



def scenario26():
    set_active_scenario('SCENARIO 26')
    msg('\n\n============\n[SCENARIO 26] customer-3 stopped and started again but still connected to the group')

    # create new group by customer-2
    customer_2_groupA_key_id = kw.group_create_v1('customer-2', label='SCENARIO20_MyGroupFFF')
    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    # customer-2 join the group
    kw.group_join_v1('customer-2', customer_2_groupA_key_id)
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    # share group key from customer-2 to customer-3
    kw.group_share_v1('customer-2', customer_2_groupA_key_id, 'customer-3@id-a_8084')

    # customer-3 also join the group
    kw.group_join_v1('customer-3', customer_2_groupA_key_id)
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    # sending few messages to the group from customer-2
    for i in range(2):
        kw.verify_message_sent_received(
            customer_2_groupA_key_id,
            producer_id='customer-2',
            consumers_ids=[
                'customer-3',
                'customer-2',
            ],
            message_label='X%d' % (i + 1),
            expected_results={
                'customer-3': True,
                'customer-2': True,
            },
        )

    # sending few messages to the group from customer-3
    for i in range(2):
        kw.verify_message_sent_received(
            customer_2_groupA_key_id,
            producer_id='customer-3',
            consumers_ids=[
                'customer-3',
                'customer-2',
            ],
            message_label='Y%d' % (i + 1),
            expected_results={
                'customer-3': True,
                'customer-2': True,
            },
        )

    customer_2_groupA_info_before = kw.group_info_v1('customer-3', customer_2_groupA_key_id)['result']
    assert customer_2_groupA_info_before['state'] == 'CONNECTED'

    # stop customer-3 node
    kw.wait_packets_finished(CUSTOMERS_IDS_123)
    request_get('customer-3', 'process/stop/v1', verbose=True, raise_error=False)
    kw.wait_packets_finished(CUSTOMERS_IDS_12)

    # start customer-3 node again
    start_daemon('customer-3', skip_initialize=True, verbose=True)
    health_check('customer-3', verbose=True)

    kw.wait_service_state(
        [
            'customer-3',
        ],
        'service_shared_data',
        'ON'
    )
    kw.wait_service_state(
        [
            'customer-3',
        ],
        'service_private_groups',
        'ON'
    )

    customer_2_groupA_info_after = kw.group_info_v1('customer-3', customer_2_groupA_key_id, wait_state='CONNECTED')['result']
    assert customer_2_groupA_info_after['state'] == 'CONNECTED'

    # sending a message again to the group from customer-2 and customer-3 must receive it
    for i in range(1):
        kw.verify_message_sent_received(
            customer_2_groupA_key_id,
            producer_id='customer-2',
            consumers_ids=[
                'customer-3',
                'customer-2',
            ],
            message_label='X%d' % (i + 1),
            expected_results={
                'customer-3': True,
                'customer-2': True,
            },
        )
    msg('\n[SCENARIO 26] : PASS\n\n')


def scenario27():
    set_active_scenario('SCENARIO 27')
    msg('\n\n============\n[SCENARIO 27] customer-2 sent message to the group but active supplier-1 is offline')

    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=[
            'customer-1@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
        accepted_mistakes=0,
    )
    kw.supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=[
            'customer-2@id-a_8084',
        ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
        accepted_mistakes=0,
    )

    # create new group by customer-2
    customer_2_groupA_key_id = kw.group_create_v1('customer-2', label='SCENARIO18_MyGroupAAA')
    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    # customer-2 join the group
    kw.group_join_v1('customer-2', customer_2_groupA_key_id)
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    # share group key from customer-2 to customer-1
    kw.group_share_v1('customer-2', customer_2_groupA_key_id, 'customer-1@id-a_8084')

    # customer-1 also join the group
    kw.group_join_v1('customer-1', customer_2_groupA_key_id)
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    # sending few messages to the group from customer-2
    for i in range(2):
        kw.verify_message_sent_received(
            customer_2_groupA_key_id,
            producer_id='customer-2',
            consumers_ids=[
                'customer-1',
                'customer-2',
            ],
            message_label='AA_%d' % (i + 1),
            expected_results={
                'customer-1': True,
                'customer-2': True,
            },
        )

    # sending few messages to the group from customer-1
    for i in range(2):
        kw.verify_message_sent_received(
            customer_2_groupA_key_id,
            producer_id='customer-1',
            consumers_ids=[
                'customer-1',
                'customer-2',
            ],
            message_label='BB_%d' % (i + 1),
            expected_results={
                'customer-1': True,
                'customer-2': True,
            },
        )

    # create second group by customer-2
    customer_2_groupB_key_id = kw.group_create_v1('customer-2', label='SCENARIO18_MyGroupBBB')
    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS_123, 'service_private_groups', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    # customer-2 join the second group
    kw.group_join_v1('customer-2', customer_2_groupB_key_id)
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    # share second group key from customer-2 to customer-1
    kw.group_share_v1('customer-2', customer_2_groupB_key_id, 'customer-1@id-a_8084')

    # customer-1 also joins the second group
    kw.group_join_v1('customer-1', customer_2_groupB_key_id)
    kw.wait_packets_finished(CUSTOMERS_IDS_123)

    # sending few messages to the second group from customer-2
    for i in range(1):
        kw.verify_message_sent_received(
            customer_2_groupB_key_id,
            producer_id='customer-2',
            consumers_ids=[
                'customer-1',
                'customer-2',
            ],
            message_label='CC_%d' % (i + 1),
            expected_results={
                'customer-1': True,
                'customer-2': True,
            },
        )

    # sending few messages to the second group from customer-1
    for i in range(1):
        kw.verify_message_sent_received(
            customer_2_groupB_key_id,
            producer_id='customer-1',
            consumers_ids=[
                'customer-1',
                'customer-2',
            ],
            message_label='DD_%d' % (i + 1),
            expected_results={
                'customer-1': True,
                'customer-2': True,
            },
        )

    # verify active queue supplier for customer-1
    customer_1_groupA_info_before = kw.group_info_v1('customer-1', customer_2_groupA_key_id)['result']
    assert customer_1_groupA_info_before['state'] == 'CONNECTED'
    customer_1_active_queueA_id = customer_1_groupA_info_before['active_queue_id']
    customer_1_groupA_active_supplier_name_before = customer_1_groupA_info_before['active_supplier_id'].split('@')[0]
    assert customer_1_groupA_active_supplier_name_before == 'supplier-1'

    # also check the second group have similar info for customer-1
    customer_1_groupB_info_before = kw.group_info_v1('customer-1', customer_2_groupB_key_id)['result']
    assert customer_1_groupB_info_before['state'] == 'CONNECTED'
    customer_1_active_queueB_id = customer_1_groupB_info_before['active_queue_id']
    customer_1_groupB_active_supplier_name_before = customer_1_groupB_info_before['active_supplier_id'].split('@')[0]
    assert customer_1_groupB_active_supplier_name_before == 'supplier-1'

    # verify active queue supplier for customer-2
    customer_2_groupA_info_before = kw.group_info_v1('customer-2', customer_2_groupA_key_id)['result']
    assert customer_2_groupA_info_before['state'] == 'CONNECTED'
    customer_2_active_queueA_id = customer_1_groupA_info_before['active_queue_id']
    customer_2_groupA_active_supplier_name_before = customer_2_groupA_info_before['active_supplier_id'].split('@')[0]
    assert customer_2_groupA_active_supplier_name_before == 'supplier-1'

    # also check the second group have similar info for customer-2
    customer_2_groupB_info_before = kw.group_info_v1('customer-2', customer_2_groupB_key_id)['result']
    assert customer_2_groupB_info_before['state'] == 'CONNECTED'
    customer_2_active_queueB_id = customer_2_groupB_info_before['active_queue_id']
    customer_2_groupB_active_supplier_name_before = customer_2_groupB_info_before['active_supplier_id'].split('@')[0]
    assert customer_2_groupB_active_supplier_name_before == 'supplier-1'

    # verify supplier-1 details before it goes offline
    supplier_1_consumers = kw.queue_consumer_list_v1('supplier-1', extract_ids=True)
    supplier_1_producers = kw.queue_producer_list_v1('supplier-1', extract_ids=True)
    supplier_1_streams = kw.queue_stream_list_v1('supplier-1', extract_ids=True)
    assert 'customer-1@id-a_8084' in supplier_1_consumers
    assert 'customer-1@id-a_8084' in supplier_1_producers
    assert 'customer-2@id-a_8084' in supplier_1_consumers
    assert 'customer-2@id-a_8084' in supplier_1_producers
    assert customer_1_active_queueA_id in supplier_1_streams
    assert customer_1_active_queueB_id in supplier_1_streams
    assert customer_2_active_queueA_id in supplier_1_streams
    assert customer_2_active_queueB_id in supplier_1_streams

    # verify messages
    customer_1_conversations_count_before = len(kw.message_conversation_v1('customer-1')['result'])
    customer_2_conversations_count_before = len(kw.message_conversation_v1('customer-2')['result'])
    customer_1_groupA_messages_before = len(kw.message_history_v1('customer-1', customer_2_groupA_key_id, message_type='group_message')['result'])
    customer_2_groupA_messages_before = len(kw.message_history_v1('customer-2', customer_2_groupA_key_id, message_type='group_message')['result'])
    customer_1_groupB_messages_before = len(kw.message_history_v1('customer-1', customer_2_groupB_key_id, message_type='group_message')['result'])
    customer_2_groupB_messages_before = len(kw.message_history_v1('customer-2', customer_2_groupB_key_id, message_type='group_message')['result'])
    assert customer_1_groupA_messages_before > 0
    assert customer_2_groupA_messages_before > 0
    assert customer_1_groupB_messages_before > 0
    assert customer_2_groupB_messages_before > 0

    # prepare customers before supplier-1 goes offline, replace supplier-1 with supplier-3
    kw.config_set_v1('customer-1', 'services/employer/candidates', 'http://id-a:8084/supplier-3.xml,http://id-a:8084/supplier-2.xml')
    kw.config_set_v1('customer-2', 'services/employer/candidates', 'http://id-a:8084/supplier-3.xml,http://id-a:8084/supplier-2.xml')
    kw.config_set_v1('customer-3', 'services/employer/candidates', 'http://id-a:8084/supplier-3.xml,http://id-a:8084/supplier-2.xml')

    # stop supplier-1
    kw.wait_packets_finished(CUSTOMERS_IDS_123 + SUPPLIERS_IDS_12)
    kw.config_set_v1('supplier-1', 'services/network/enabled', 'false')
    kw.wait_packets_finished(CUSTOMERS_IDS_123 + ['supplier-2', 'supplier-3', ])

    # make sure customers are all switched to the new supplier
    kw.supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)
    kw.supplier_list_v1('customer-3', expected_min_suppliers=2, expected_max_suppliers=2)

    # send again a message to the second group from customer-1
    # this should rotate active queue supplier for customer-1 in the second group only
    kw.verify_message_sent_received(
        customer_2_groupB_key_id,
        producer_id='customer-1',
        consumers_ids=[
            'customer-1',
            'customer-2',
        ],
        message_label='MUST_ROTATE_SUPPLIER_1_NOW',
        expected_results={
            'customer-1': True,
            'customer-2': True,
        },
        polling_timeout=180,
        receive_timeout=181,
    )

    # verify active queue supplier for customer-1 again - must not be changed
    customer_1_groupA_info_after = kw.group_info_v1('customer-1', customer_2_groupA_key_id, wait_state='CONNECTED')['result']
    assert customer_1_groupA_info_after['state'] == 'CONNECTED'
    assert customer_1_groupA_info_after['active_supplier_id'].split('@')[0] == customer_1_groupA_active_supplier_name_before

    # then check active queue supplier and group state of the second group on customer-1 - this suppose to change
    customer_1_groupB_info_after = kw.group_info_v1('customer-1', customer_2_groupB_key_id, wait_state='CONNECTED')['result']
    assert customer_1_groupB_info_after['state'] == 'CONNECTED'
    assert customer_1_groupB_info_after['active_supplier_id'].split('@')[0] != customer_1_groupB_active_supplier_name_before

    # check the first group have similar info on customer-2 node - this group must also not be updated
    customer_2_groupA_info_after = kw.group_info_v1('customer-2', customer_2_groupA_key_id, wait_state='CONNECTED')['result']
    assert customer_2_groupA_info_after['state'] == 'CONNECTED'
    assert customer_2_groupA_info_after['active_supplier_id'].split('@')[0] == customer_2_groupA_active_supplier_name_before

    # now check the second group have similar info on customer-2 node - this group must also not be updated
    customer_2_groupB_info_after = kw.group_info_v1('customer-2', customer_2_groupB_key_id, wait_state='CONNECTED')['result']
    assert customer_2_groupB_info_after['state'] == 'CONNECTED'
    assert customer_2_groupB_info_after['active_supplier_id'].split('@')[0] == customer_2_groupB_active_supplier_name_before

    # verify messages again
    assert len(kw.message_history_v1('customer-1', customer_2_groupA_key_id, message_type='group_message')['result']) == customer_1_groupA_messages_before
    assert len(kw.message_history_v1('customer-2', customer_2_groupA_key_id, message_type='group_message')['result']) == customer_2_groupA_messages_before
    assert len(kw.message_history_v1('customer-1', customer_2_groupB_key_id, message_type='group_message')['result']) == customer_1_groupB_messages_before + 1
    assert len(kw.message_history_v1('customer-2', customer_2_groupB_key_id, message_type='group_message')['result']) == customer_2_groupB_messages_before + 1
    assert len(kw.message_conversation_v1('customer-1')['result']) == customer_1_conversations_count_before
    assert len(kw.message_conversation_v1('customer-2')['result']) == customer_2_conversations_count_before

    # start the supplier-1 again
    kw.wait_packets_finished(CUSTOMERS_IDS_123 + ['supplier-2', ])
    kw.config_set_v1('supplier-1', 'services/network/enabled', 'true')
    kw.wait_packets_finished(CUSTOMERS_IDS_123 + SUPPLIERS_IDS_12)
    health_check('supplier-1', verbose=True)
    kw.wait_service_state(
        [
            'supplier-1',
        ],
        'service_joint_postman',
        'ON',
    )
    kw.wait_packets_finished(CUSTOMERS_IDS_123 + SUPPLIERS_IDS_12)

    msg('\n[SCENARIO 27] : PASS\n\n')

