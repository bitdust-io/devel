#!/usr/bin/env python
# test_identity.py
#
# Copyright (C) 2008-2019 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (test_identity.py) is part of BitDust Software.
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
import sys
import pytest
import time
import base64
import threading

from testsupport import run_ssh_command_and_wait, stop_daemon

from keywords import service_info_v1, file_create_v1, file_upload_start_v1, file_download_start_v1, \
    supplier_list_v1, transfer_list_v1, packet_list_v1, config_set_v1, \
    user_ping_v1, identity_get_v1, identity_rotate_v1, key_list_v1, share_create_v1, share_open_v1, \
    friend_add_v1, friend_list_v1, message_send_v1, message_receive_v1


def test_identity_rotate_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    sys.stderr.write('\ntest_identity_rotate_customer_1\n')

    service_info_v1('customer-1', 'service_customer', 'ON')

    supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    # remember current ID sources
    r = identity_get_v1('customer-1')
    old_sources = r['result'][0]['sources']
    old_global_id = r['result'][0]['global_id']
    old_idurl = r['result'][0]['idurl']

    # test other nodes able to talk to customer-1 before identity get rotated
    user_ping_v1('customer-3', old_global_id)
    user_ping_v1('supplier-1', old_global_id)
    user_ping_v1('supplier-2', old_global_id)

    # test customer-3 can chat with customer-1 before identity get rotated
    service_info_v1('customer-3', 'service_private_messages', 'ON')
    service_info_v1('customer-1', 'service_private_messages', 'ON')
    random_string = base64.b32encode(os.urandom(20)).decode()
    random_message = {
        'random_message': random_string,
    }
    t = threading.Timer(2.0, message_send_v1, ['customer-3', 'master$%s' % old_global_id, random_message, ])
    t.start()
    message_receive_v1('customer-1', expected_data=random_message)

    # create one share and upload one file for customer-1
    share_id_customer_1 = share_create_v1('customer-1')
    filename = 'cat.txt'
    virtual_filename = filename
    volume_customer_1 = '/customer_1'
    filepath_customer_1 = f'{volume_customer_1}/{filename}'
    run_ssh_command_and_wait('customer-1', f'echo customer_1 > {filepath_customer_1}')

    remote_path_customer_1 = f'{share_id_customer_1}:{virtual_filename}'
    downloaded_filepath = f'/tmp/{filename}'
    local_file_src = run_ssh_command_and_wait('customer-1', 'cat %s' % filepath_customer_1)[0].strip()

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    packet_list_v1('customer-1', wait_all_finish=True)
    transfer_list_v1('customer-1', wait_all_finish=True)

    file_create_v1('customer-1', remote_path=remote_path_customer_1)
    file_upload_start_v1('customer-1', remote_path=remote_path_customer_1, local_path=filepath_customer_1)

    time.sleep(3)
    
    service_info_v1('customer-1', 'service_shared_data', 'ON')

    # make sure file is available before identity rotate
    share_open_v1('customer-1', share_id_customer_1)
    file_download_start_v1('customer-1', remote_path=remote_path_customer_1, destination='/tmp')

    # and make sure this is the same file
    downloaded_file_src = run_ssh_command_and_wait('customer-1', 'cat %s' % downloaded_filepath)[0].strip()
    assert local_file_src == downloaded_file_src, "source file and received file content is not equal"

    # remember list of existing keys
    old_keys = [k['key_id'] for k in key_list_v1('customer-1')['result']]
    assert f'master${old_global_id}' in old_keys
    assert f'messages${old_global_id}' in old_keys
    assert f'customer${old_global_id}' in old_keys

    # make customer-1 and customer-3 friends to each other
    friend_add_v1('customer-1', 'http://id-a:8084/customer-3.xml', 'friend2')
    friend_add_v1('customer-3', old_idurl, 'friend1')
    old_friends = friend_list_v1('customer-3', extract_idurls=True)
    assert old_idurl in old_friends

    # rotate identity sources
    identity_rotate_v1('customer-1')

    time.sleep(1)

    # and make sure ID sources were changed
    r = identity_get_v1('customer-1')
    new_sources = r['result'][0]['sources'] 
    new_global_id = r['result'][0]['global_id']
    new_idurl = r['result'][0]['idurl']
    assert new_sources != old_sources
    assert new_global_id != old_global_id
    assert new_idurl != old_idurl

    service_info_v1('customer-1', 'service_customer', 'ON')

    # remember current suppliers of customer-1
    customer_1_suppliers = supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2, extract_suppliers=True)
    first_supplier = customer_1_suppliers[0].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')
    second_supplier = customer_1_suppliers[1].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    # test other nodes able to talk to customer-1 again on new IDURL
    user_ping_v1('customer-3', new_global_id)
    user_ping_v1('supplier-1', new_global_id)
    user_ping_v1('supplier-2', new_global_id)

    # make sure keys are renamed on customer-1
    new_keys = [k['key_id'] for k in key_list_v1('customer-1')['result']]
    assert len(old_keys) == len(new_keys)
    assert f'master${new_global_id}' in new_keys
    assert f'messages${new_global_id}' in new_keys
    assert f'customer${new_global_id}' in new_keys
    assert f'master${old_global_id}' not in new_keys
    assert f'messages${old_global_id}' not in new_keys
    assert f'customer${old_global_id}' not in new_keys

    # make sure file is still available after identity rotate
    new_share_id_customer_1 = share_id_customer_1.replace(old_global_id, new_global_id)
    share_open_v1('customer-1', new_share_id_customer_1)
    new_remote_path_customer_1 = remote_path_customer_1.replace(old_global_id, new_global_id)
    run_ssh_command_and_wait('customer-1', 'rm -rfv %s' % downloaded_filepath)[0].strip()
    file_download_start_v1('customer-1', remote_path=new_remote_path_customer_1, destination='/tmp')

    # and make sure this is still the same file
    new_downloaded_file_src = run_ssh_command_and_wait('customer-1', 'cat %s' % downloaded_filepath)[0].strip()
    assert local_file_src == downloaded_file_src, "source file and received file content is not equal after identity rotate"
    assert new_downloaded_file_src == downloaded_file_src, "received file content before identity rotate is not equal to received file after identity rotate"

    # check again current suppliers of customer-1
    customer_1_suppliers = supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2, extract_suppliers=True)
    first_supplier = customer_1_suppliers[0].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')
    second_supplier = customer_1_suppliers[1].replace('http://id-a:8084/', '').replace('http://id-b:8084/', '').replace('.xml', '')

    # verify files on first supplier were moved to correct sub folder
    print(f'checking customer-1 files on {first_supplier}')
    old_folder_first_supplier = run_ssh_command_and_wait(first_supplier, f'ls -la ~/.bitdust/customers/{old_global_id}/')[0].strip()
    new_folder_first_supplier = run_ssh_command_and_wait(first_supplier, f'ls -la ~/.bitdust/customers/{new_global_id}/')[0].strip()
    assert old_folder_first_supplier == ''
    assert new_folder_first_supplier != ''
    print(f'first supplier {first_supplier} :\n', new_folder_first_supplier)

    # verify files on second supplier were moved to correct sub folder
    print(f'checking customer-1 files on {second_supplier}')
    old_folder_second_supplier = run_ssh_command_and_wait(second_supplier, f'ls -la ~/.bitdust/customers/{old_global_id}/')[0].strip()
    new_folder_second_supplier = run_ssh_command_and_wait(second_supplier, f'ls -la ~/.bitdust/customers/{new_global_id}/')[0].strip()
    assert old_folder_second_supplier == ''
    assert new_folder_second_supplier != ''
    print(f'second supplier {second_supplier} :\n', new_folder_second_supplier)

    # test that friend1 idurl changed for customer-3
    new_friends = friend_list_v1('customer-3', extract_idurls=True)
    assert new_idurl in new_friends
    assert old_idurl not in new_friends

    # test customer-3 can still chat with customer-1 after identity rotated
    service_info_v1('customer-3', 'service_private_messages', 'ON')
    service_info_v1('customer-1', 'service_private_messages', 'ON')
    random_string = base64.b32encode(os.urandom(20)).decode()
    random_message = {
        'random_message': random_string,
    }
    t = threading.Timer(1.0, message_send_v1, ['customer-3', 'master$%s' % new_global_id, random_message, ])
    t.start()
    message_receive_v1('customer-1', expected_data=random_message)



def test_identity_rotate_customer_2_when_id_server_is_dead():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    service_info_v1('customer-2', 'service_customer', 'ON')

    supplier_list_v1('customer-2', expected_min_suppliers=2, expected_max_suppliers=2)

    service_info_v1('customer-2', 'service_shared_data', 'ON')

    r = identity_get_v1('customer-2')
    old_idurl = r['result'][0]['idurl']

    config_set_v1('customer-2', 'services/identity-propagate/automatic-rotate-enabled', 'true')

    config_set_v1('customer-2', 'services/identity-propagate/known-servers',
                  'id-dead:8084:6661,id-a:8084:6661,id-b:8084:6661,id-c:8084:6661')

    stop_daemon('id-dead')

    for i in range(20):
        r = identity_get_v1('customer-2')
        new_idurl = r['result'][0]['idurl']
        if new_idurl != old_idurl:
            break
        time.sleep(5)
    else:
        assert False, 'customer-2 automatic identity rotate did not happen after many attempts'

