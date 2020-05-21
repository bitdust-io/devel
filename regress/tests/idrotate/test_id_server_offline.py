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

import os
import pytest
import time
import base64
import threading

from testsupport import stop_daemon, run_ssh_command_and_wait

import keywords as kw

SUPPLIERS_IDS = ['supplier-rotated', 'supplier-2', 'supplier-3', 'supplier-4', 'supplier-5', ]
BROKERS_IDS = ['broker-rotated', 'broker-2', 'broker-3', 'broker-4', 'broker-5', ]
CUSTOMERS_IDS = ['customer-rotated', 'customer-2', 'customer-3', 'customer-4', ]


def test_id_server_is_dead():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    #--- wait all nodes to be ready
    kw.wait_suppliers_connected(CUSTOMERS_IDS, expected_min_suppliers=2, expected_max_suppliers=2)
    kw.wait_service_state(CUSTOMERS_IDS, 'service_customer', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_shared_data', 'ON')
    kw.wait_service_state(CUSTOMERS_IDS, 'service_private_groups', 'ON')
    kw.wait_service_state(BROKERS_IDS, 'service_message_broker', 'ON')
    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS + SUPPLIERS_IDS)

    #--- make sure supplier-rotated was hired by customer-2
    old_customer_2_suppliers_idurls = kw.supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)

    #--- create group owned by customer-4 and join
    group_key_id = kw.group_create_v1('customer-4', label='MyGroupABC')

    group_info_inactive = kw.group_info_v1('customer-4', group_key_id)['result']
    assert group_info_inactive['state'] == 'OFFLINE'
    assert group_info_inactive['label'] == 'MyGroupABC'
    assert group_info_inactive['last_sequence_id'] == -1

    kw.group_join_v1('customer-4', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    group_info_active = kw.group_info_v1('customer-4', group_key_id)['result']
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
    assert 'customer-4@id-b_8084' in broker_consumers
    assert 'customer-4@id-b_8084' in broker_producers

    #--- share group key from customer-4 to customer-2
    kw.group_share_v1('customer-4', group_key_id, 'customer-2@id-b_8084')

    #--- customer-2 joins the group
    kw.group_join_v1('customer-2', group_key_id)

    kw.wait_packets_finished(CUSTOMERS_IDS + BROKERS_IDS)

    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == -1

    broker_consumers = kw.queue_consumer_list_v1(active_broker_name, extract_ids=True)
    broker_producers = kw.queue_producer_list_v1(active_broker_name, extract_ids=True)
    assert len(broker_consumers) == 2
    assert len(broker_producers) == 2
    assert 'customer-4@id-b_8084' in broker_consumers
    assert 'customer-4@id-b_8084' in broker_producers
    assert 'customer-2@id-b_8084' in broker_consumers
    assert 'customer-2@id-b_8084' in broker_producers

    assert len(kw.message_history_v1('customer-4', group_key_id, message_type='group_message')['result']) == 0
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 0

    #--- sending few messages to the group from customer-4
    all_messages = []
    for i in range(5):
        all_messages.append(kw.verify_message_sent_received(
            group_key_id,
            producer_id='customer-4',
            consumers_ids=['customer-4', 'customer-2', ],
            message_label='F%d' % (i + 1),
            expected_results={'customer-4': True, 'customer-2': True, },
            expected_last_sequence_id={},
        ))

    assert kw.group_info_v1('customer-4', group_key_id)['result']['last_sequence_id'] == 4
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 4
    assert len(kw.message_history_v1('customer-4', group_key_id, message_type='group_message')['result']) == 5
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 5

    #--- remember old IDURL of the rotated nodes
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

    #--- upload one file for customer-rotated
    share_id_customer_rotated = kw.share_create_v1('customer-rotated')
    filename = 'cat.txt'
    virtual_filename = filename
    volume_customer_rotated = '/customer_rotated'
    filepath_customer_rotated = f'{volume_customer_rotated}/{filename}'
    run_ssh_command_and_wait('customer-rotated', f'echo customer_rotated > {filepath_customer_rotated}')
    remote_path_customer_rotated = f'{share_id_customer_rotated}:{virtual_filename}'
    downloaded_filepath = f'/tmp/{filename}'
    local_file_src = run_ssh_command_and_wait('customer-rotated', 'cat %s' % filepath_customer_rotated)[0].strip()

    kw.service_info_v1('customer-rotated', 'service_shared_data', 'ON')
    kw.packet_list_v1('customer-rotated', wait_all_finish=True)
    kw.transfer_list_v1('customer-rotated', wait_all_finish=True)

    kw.file_create_v1('customer-rotated', remote_path=remote_path_customer_rotated)
    kw.file_upload_start_v1('customer-rotated', remote_path=remote_path_customer_rotated, local_path=filepath_customer_rotated)

    kw.service_info_v1('customer-rotated', 'service_shared_data', 'ON')

    kw.share_open_v1('customer-rotated', share_id_customer_rotated)
    kw.file_download_start_v1('customer-rotated', remote_path=remote_path_customer_rotated, destination='/tmp')
    downloaded_file_src = run_ssh_command_and_wait('customer-rotated', 'cat %s' % downloaded_filepath)[0].strip()
    assert local_file_src == downloaded_file_src, "source file and received file content is not equal"

    #--- remember list of existing keys on customer-rotated
    old_customer_keys = [k['key_id'] for k in kw.key_list_v1('customer-rotated')['result']]
    assert f'master${old_customer_global_id}' in old_customer_keys
    assert f'customer${old_customer_global_id}' in old_customer_keys

    #--- make customer-rotated and customer-2 friends to each other
    kw.friend_add_v1('customer-rotated', 'http://id-a:8084/customer-2.xml', 'Alice')
    kw.friend_add_v1('customer-2', old_customer_idurl, 'Bob')
    old_customer_2_friends = kw.friend_list_v1('customer-2', extract_idurls=True)
    assert old_customer_idurl in old_customer_2_friends

    #--- verify that customer-2 can chat with customer-rotated
    kw.service_info_v1('customer-2', 'service_private_messages', 'ON')
    kw.service_info_v1('customer-rotated', 'service_private_messages', 'ON')
    random_string = base64.b32encode(os.urandom(20)).decode()
    random_message = {
        'random_message': random_string,
    }
    t = threading.Timer(1.0, kw.message_send_v1, ['customer-2', 'master$%s' % old_customer_global_id, random_message, ])
    t.start()
    kw.message_receive_v1('customer-rotated', expected_data=random_message, timeout=31, polling_timeout=30)

    #--- preparation before switching of the ID server
    kw.config_set_v1('proxy-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
    kw.config_set_v1('proxy-rotated', 'services/identity-propagate/known-servers',
                     'id-a:8084:6661,id-b:8084:6661,id-c:8084:6661')
    kw.config_set_v1('customer-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
    kw.config_set_v1('customer-rotated', 'services/identity-propagate/known-servers',
                     'id-a:8084:6661,id-b:8084:6661,id-c:8084:6661')
    kw.config_set_v1('supplier-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
    kw.config_set_v1('supplier-rotated', 'services/identity-propagate/known-servers',
                     'id-a:8084:6661,id-b:8084:6661,id-c:8084:6661')
    kw.config_set_v1('broker-rotated', 'services/identity-propagate/automatic-rotate-enabled', 'true')
    kw.config_set_v1('broker-rotated', 'services/identity-propagate/known-servers',
                     'id-a:8084:6661,id-b:8084:6661,id-c:8084:6661')
    kw.config_set_v1('customer-3', 'services/employer/candidates', '')

    #--- put identity server offline
    stop_daemon('id-dead')

    #--- test proxy-rotated new IDURL
    r = None
    for i in range(20):
        r = kw.identity_get_v1('proxy-rotated')
        new_idurl = r['result']['idurl']
        if new_idurl != old_proxy_idurl:
            break
        time.sleep(5)
    else:
        assert False, 'broker-rotated automatic identity rotate did not happen after many attempts'

    #--- test customer-rotated new IDURL
    for i in range(20):
        r = kw.identity_get_v1('customer-rotated')
        new_idurl = r['result']['idurl']
        if new_idurl != old_customer_idurl:
            break
        time.sleep(5)
    else:
        assert False, 'customer-rotated automatic identity rotate did not happen after many attempts'
    new_customer_sources = r['result']['sources'] 
    new_customer_global_id = r['result']['global_id']
    new_customer_idurl = r['result']['idurl']
    assert new_customer_sources != old_customer_sources
    assert new_customer_global_id != old_customer_global_id
    assert new_customer_idurl != old_customer_idurl

    #--- test supplier-rotated new IDURL
    for i in range(20):
        r = kw.identity_get_v1('supplier-rotated')
        new_idurl = r['result']['idurl']
        if new_idurl != old_supplier_idurl:
            break
        time.sleep(5)
    else:
        assert False, 'supplier-rotated automatic identity rotate did not happen after many attempts'

    #--- test broker-rotated new IDURL
    for i in range(20):
        r = kw.identity_get_v1('broker-rotated')
        new_idurl = r['result']['idurl']
        if new_idurl != old_broker_idurl:
            break
        time.sleep(5)
    else:
        assert False, 'broker-rotated automatic identity rotate did not happen after many attempts'

    #--- check current suppliers of customer-rotated
    kw.service_info_v1('customer-rotated', 'service_gateway', 'ON')
    kw.service_info_v1('customer-rotated', 'service_customer', 'ON')
    customer_rotated_suppliers = kw.supplier_list_v1('customer-rotated', expected_min_suppliers=2, expected_max_suppliers=2, extract_suppliers=True)
    first_supplier = customer_rotated_suppliers[0].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')
    second_supplier = customer_rotated_suppliers[1].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')

    #--- make sure keys are renamed on customer-rotated
    new_customer_keys = [k['key_id'] for k in kw.key_list_v1('customer-rotated')['result']]
    assert len(old_customer_keys) == len(new_customer_keys)
    assert f'master${new_customer_global_id}' in new_customer_keys
    assert f'customer${new_customer_global_id}' in new_customer_keys
    assert f'master${old_customer_global_id}' not in new_customer_keys
    assert f'customer${old_customer_global_id}' not in new_customer_keys

    #--- make sure file is still available after identity rotate
    kw.service_info_v1('customer-rotated', 'service_shared_data', 'ON')
    new_share_id_customer_rotated = share_id_customer_rotated.replace(old_customer_global_id, new_customer_global_id)
    kw.share_open_v1('customer-rotated', new_share_id_customer_rotated)
    new_remote_path_customer_rotated = remote_path_customer_rotated.replace(old_customer_global_id, new_customer_global_id)
    run_ssh_command_and_wait('customer-rotated', 'rm -rfv %s' % downloaded_filepath)[0].strip()
    kw.file_download_start_v1('customer-rotated', remote_path=new_remote_path_customer_rotated, destination='/tmp')
    new_downloaded_file_src = run_ssh_command_and_wait('customer-rotated', 'cat %s' % downloaded_filepath)[0].strip()
    assert local_file_src == downloaded_file_src, "source file and received file content is not equal after identity rotate"
    assert new_downloaded_file_src == downloaded_file_src, "received file content before identity rotate is not equal to received file after identity rotate"

    #--- verify files on first supplier were moved to correct sub folder
    old_folder_first_supplier = run_ssh_command_and_wait(first_supplier, f'ls -la ~/.bitdust/customers/{old_customer_global_id}/')[0].strip()
    new_folder_first_supplier = run_ssh_command_and_wait(first_supplier, f'ls -la ~/.bitdust/customers/{new_customer_global_id}/')[0].strip()
    assert old_folder_first_supplier == ''
    assert new_folder_first_supplier != ''

    #--- verify files on second supplier were moved to correct sub folder
    old_folder_second_supplier = run_ssh_command_and_wait(second_supplier, f'ls -la ~/.bitdust/customers/{old_customer_global_id}/')[0].strip()
    new_folder_second_supplier = run_ssh_command_and_wait(second_supplier, f'ls -la ~/.bitdust/customers/{new_customer_global_id}/')[0].strip()
    assert old_folder_second_supplier == ''
    assert new_folder_second_supplier != ''

    #--- send one message to the group after brokers rotated
    kw.config_set_v1('customer-4', 'services/private-groups/preferred-brokers',
                     'http://id-b:8084/broker-2.xml,http://id-a:8084/broker-3.xml,http://id-b:8084/broker-4.xml,http://id-a:8084/broker-5.xml')
    all_messages.append(kw.verify_message_sent_received(
        group_key_id,
        producer_id='customer-4',
        consumers_ids=['customer-4', 'customer-2', ],
        message_label='G',
        expected_results={'customer-4': True, 'customer-2': True, },
        expected_last_sequence_id={'customer-4': 5, 'customer-2': 5, },
        polling_timeout=90,
        receive_timeout=91,
    ))

    #--- verify group queue ID suppose to be changed
    group_info_rotated = kw.group_info_v1('customer-4', group_key_id)['result']
    assert group_info_rotated['state'] == 'IN_SYNC!'
    assert group_info_rotated['last_sequence_id'] == 5

    rotated_queue_id = group_info_rotated['active_queue_id']
    rotated_broker_id = group_info_rotated['active_broker_id']
    rotated_broker_name = rotated_broker_id.split('@')[0]

    assert rotated_queue_id != active_queue_id
    assert rotated_broker_id != active_broker_id
    assert rotated_queue_id in kw.queue_list_v1(rotated_broker_name, extract_ids=True)
    assert active_queue_id not in kw.queue_list_v1(rotated_broker_name, extract_ids=True)

    rotated_broker_consumers = kw.queue_consumer_list_v1(rotated_broker_name, extract_ids=True)
    rotated_broker_producers = kw.queue_producer_list_v1(rotated_broker_name, extract_ids=True)
    assert len(rotated_broker_consumers) == 2
    assert len(rotated_broker_producers) == 2
    assert 'customer-2@id-b_8084' in rotated_broker_consumers
    assert 'customer-2@id-b_8084' in rotated_broker_producers
    assert 'customer-4@id-b_8084' in rotated_broker_consumers
    assert 'customer-4@id-b_8084' in rotated_broker_producers

    #--- sending again few messages to the group from customer-4
    all_messages = []
    for i in range(5):
        all_messages.append(kw.verify_message_sent_received(
            group_key_id,
            producer_id='customer-4',
            consumers_ids=['customer-4', 'customer-2', ],
            message_label='H%d' % (i + 1),
            expected_results={'customer-4': True, 'customer-2': True, },
            expected_last_sequence_id={},
        ))

    assert kw.group_info_v1('customer-4', group_key_id)['result']['last_sequence_id'] == 10
    assert kw.group_info_v1('customer-2', group_key_id)['result']['last_sequence_id'] == 10
    assert len(kw.message_history_v1('customer-4', group_key_id, message_type='group_message')['result']) == 11
    assert len(kw.message_history_v1('customer-2', group_key_id, message_type='group_message')['result']) == 11

    #--- test customer-2 can still chat with customer-rotated
    kw.service_info_v1('customer-2', 'service_private_messages', 'ON')
    kw.service_info_v1('customer-rotated', 'service_private_messages', 'ON')
    random_string = base64.b32encode(os.urandom(20)).decode()
    random_message = {
        'random_message': random_string,
    }
    t = threading.Timer(1.0, kw.message_send_v1, ['customer-2', 'master$%s' % old_customer_global_id, random_message, ])
    t.start()
    kw.message_receive_v1('customer-rotated', expected_data=random_message, timeout=31, polling_timeout=30)

    #--- test that friend's IDURL changed for customer-2
    new_customer_2_friends = kw.friend_list_v1('customer-2', extract_idurls=True)
    assert new_customer_idurl in new_customer_2_friends
    assert old_customer_idurl not in new_customer_2_friends
