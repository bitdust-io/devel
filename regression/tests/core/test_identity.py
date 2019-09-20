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
import pytest
import time
import shutil
import requests

from ..testsupport import tunnel_url, run_ssh_command_and_wait, create_identity, connect_network, stop_daemon

from ..keywords import service_info_v1, file_create_v1, file_upload_start_v1, file_download_start_v1, \
    supplier_list_v1, config_set_v1, transfer_list_v1, packet_list_v1, file_list_all_v1, supplier_list_dht_v1, \
    user_ping_v1, identity_get_v1, identity_rotate_v1, key_list_v1, share_create_v1, share_open_v1, \
    supplier_switch_v1, file_sync_v1, friend_add_v1, friend_list_v1


def test_identity_recover_from_customer_backup_to_customer_restore():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    # step1: first upload/download one file on customer_backup
    key_id = 'master$customer_backup@is_8084'
    source_volume = '/customer_backup'
    origin_filename = 'file_customer_backup.txt'
    source_local_path = '%s/%s' % (source_volume, origin_filename)
    virtual_file = 'virtual_file.txt'
    remote_path = '%s:%s' % (key_id, virtual_file)
    download_volume = '/customer_backup'
    downloaded_file = '%s/%s' % (download_volume, virtual_file)

    supplier_list_v1('customer_backup', expected_min_suppliers=2, expected_max_suppliers=2)

    service_info_v1('customer_backup', 'service_shared_data', 'ON')

    supplier_list_dht_v1(
        customer_node='customer_backup',
        observer_node='customer_backup',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    supplier_list_dht_v1(
        customer_node='customer_backup',
        observer_node='customer_1',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    file_create_v1('customer_backup', remote_path)

    file_upload_start_v1('customer_backup', remote_path, source_local_path)

    service_info_v1('customer_backup', 'service_shared_data', 'ON')
    
    file_download_start_v1('customer_backup', remote_path, download_volume, open_share=False)

    source_local_file_src = run_ssh_command_and_wait('customer_backup', 'cat %s' % source_local_path)[0].strip()
    print('customer_backup: file %s is %d bytes long' % (source_local_path, len(source_local_file_src)))
    
    downloaded_file_src = run_ssh_command_and_wait('customer_backup', 'cat %s' % downloaded_file)[0].strip()
    print('customer_backup: file %s is %d bytes long' % (downloaded_file, len(downloaded_file_src)))

    assert source_local_file_src == downloaded_file_src, (source_local_file_src, downloaded_file_src, )

    # step2: backup customer_backup private key and stop that container
    backup_file_directory_c2 = '/customer_backup/identity.backup'
    backup_file_directory_c3 = '/customer_restore/identity.backup'
    assert not os.path.exists(backup_file_directory_c2)

    response = requests.post(
        url=tunnel_url('customer_backup', 'identity/backup/v1'),
        json={
            'destination_path': backup_file_directory_c2,
        },
    )
    print('\n\nidentity/backup/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()

    # copy private key from one container to another
    # same when you backup your key and restore it from USB stick on another PC
    shutil.move(backup_file_directory_c2, backup_file_directory_c3)

    # to make sure all uploads to finish
    transfer_list_v1('customer_backup', wait_all_finish=True)
    packet_list_v1('customer_backup', wait_all_finish=True)

    file_list_all_v1('customer_backup')

    try:
        response = requests.get(url=tunnel_url('customer_backup', 'process/stop/v1'))
        assert response.json()['status'] == 'OK', response.json()
    except Exception as exc:
        print('\n\nprocess/stop/v1 failed with ')

    # step3: recover key on customer_restore container and join network
    for i in range(5):
        response = requests.post(
            url=tunnel_url('customer_restore', 'identity/recover/v1'),
            json={
                'private_key_local_file': backup_file_directory_c3,
            },
        )
        print('\n\nidentity/recover/v1 : %s\n' % response.json())
        if response.json()['status'] == 'OK':
            break
        time.sleep(1)
    else:
        assert False, 'customer_restore was not able to recover identity after few seconds'

    response = requests.get(url=tunnel_url('customer_restore', 'network/connected/v1?wait_timeout=1'))
    assert response.json()['status'] == 'ERROR'

    for i in range(5):
        response = requests.get(url=tunnel_url('customer_restore', 'network/connected/v1?wait_timeout=5'))
        if response.json()['status'] == 'OK':
            break
        time.sleep(5)
    else:
        assert False, 'customer_restore was not able to join the network after identity recover'

    supplier_list_v1('customer_restore', expected_min_suppliers=2, expected_max_suppliers=2)

    service_info_v1('customer_restore', 'service_shared_data', 'ON')

    supplier_list_dht_v1(
        customer_node='customer_backup',
        observer_node='customer_restore',
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    file_list_all_v1('customer_restore')

    # step4: try to recover stored file again
    key_id = 'master$customer_backup@is_8084'
    recover_volume = '/customer_restore'
    virtual_file = 'virtual_file.txt'
    remote_path = '%s:%s' % (key_id, virtual_file)
    recovered_file = '%s/%s' % (recover_volume, virtual_file)
    for i in range(20):
        response = requests.post(
            url=tunnel_url('customer_restore', 'file/download/start/v1'),
            json={
                'remote_path': remote_path,
                'destination_folder': recover_volume,
                'wait_result': '1',
            },
        )
        assert response.status_code == 200

        if response.json()['status'] == 'OK':
            break

        if response.json()['errors'][0].startswith('download not possible, uploading'):
            time.sleep(1)
        else:
            assert False, response.json()

    else:
        assert False, 'download was not successful: %r' % response.json()

    recovered_file_src = run_ssh_command_and_wait('customer_restore', 'cat %s' % recovered_file)[0].strip()
    print('customer_restore:%s' % recovered_file, recovered_file_src)
    assert source_local_file_src == recovered_file_src, (source_local_file_src, recovered_file_src, )

    # TODO:
    # test my keys also recovered
    # test my message history also recovered



def test_identity_rotate_customer_6():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    service_info_v1('customer_6', 'service_customer', 'ON')

    supplier_list_v1('customer_6', expected_min_suppliers=2, expected_max_suppliers=2)

    service_info_v1('customer_6', 'service_shared_data', 'ON')

    # remember current ID sources
    r = identity_get_v1('customer_6')
    old_sources = r['result'][0]['sources']
    old_global_id = r['result'][0]['global_id']
    old_idurl = r['result'][0]['idurl']

    # test other nodes able to talk to customer_6 before identity get rotated
    user_ping_v1('customer_1', old_global_id)
    user_ping_v1('customer_2', old_global_id)
    user_ping_v1('supplier_1', old_global_id)
    user_ping_v1('supplier_2', old_global_id)

    # create one share and upload one file for customer_6
    share_id_customer_6 = share_create_v1('customer_6')
    filename = 'cat.txt'
    virtual_filename = filename
    volume_customer_6 = '/customer_6'
    filepath_customer_6 = f'{volume_customer_6}/{filename}'
    run_ssh_command_and_wait('customer_6', f'echo customer_6 > {filepath_customer_6}')
    remote_path_customer_6 = f'{share_id_customer_6}:{virtual_filename}'
    downloaded_filepath = f'/tmp/{filename}'
    local_file_src = run_ssh_command_and_wait('customer_6', 'cat %s' % filepath_customer_6)[0].strip()

    file_create_v1('customer_6', remote_path=remote_path_customer_6)
    file_upload_start_v1('customer_6', remote_path=remote_path_customer_6, local_path=filepath_customer_6)

    packet_list_v1('customer_6', wait_all_finish=True)
    transfer_list_v1('customer_6', wait_all_finish=True)

    time.sleep(5)
    
    service_info_v1('customer_6', 'service_shared_data', 'ON')

    # make sure file is available before identity rotate
    share_open_v1('customer_6', share_id_customer_6)
    file_download_start_v1('customer_6', remote_path=remote_path_customer_6, destination='/tmp')

    # and make sure this is the same file
    downloaded_file_src = run_ssh_command_and_wait('customer_6', 'cat %s' % downloaded_filepath)[0].strip()
    assert local_file_src == downloaded_file_src, "source file and received file content is not equal"

    # remember list of existing keys
    old_keys = [k['key_id'] for k in key_list_v1('customer_6')['result']]
    assert f'master${old_global_id}' in old_keys
    assert f'messages${old_global_id}' in old_keys
    assert f'customer${old_global_id}' in old_keys

    # make customer_6 and customer_1 friends to each other
    friend_add_v1('customer_6', 'http://is:8084/customer_1.xml', 'friend1')
    friend_add_v1('customer_1', old_idurl, 'friend6')
    old_friends = friend_list_v1('customer_1', extract_idurls=True)
    assert old_idurl in old_friends

    # rotate identity sources
    identity_rotate_v1('customer_6')

    time.sleep(1)

    # and make sure ID sources were changed
    r = identity_get_v1('customer_6')
    new_sources = r['result'][0]['sources'] 
    new_global_id = r['result'][0]['global_id']
    new_idurl = r['result'][0]['idurl']
    assert new_sources != old_sources
    assert new_global_id != old_global_id
    assert new_idurl != old_idurl

    service_info_v1('customer_6', 'service_customer', 'ON')

    customer6_suppliers = supplier_list_v1('customer_6', expected_min_suppliers=2, expected_max_suppliers=2, extract_suppliers=True)

    service_info_v1('customer_6', 'service_shared_data', 'ON')

    # test other nodes able to talk to customer_6 again on new IDURL
    user_ping_v1('customer_1', new_global_id)
    user_ping_v1('customer_2', new_global_id)
    user_ping_v1('supplier_1', new_global_id)
    user_ping_v1('supplier_2', new_global_id)

    # make sure keys are renamed on customer_6
    new_keys = [k['key_id'] for k in key_list_v1('customer_6')['result']]
    assert len(old_keys) == len(new_keys)
    assert f'master${new_global_id}' in new_keys
    assert f'messages${new_global_id}' in new_keys
    assert f'customer${new_global_id}' in new_keys
    assert f'master${old_global_id}' not in new_keys
    assert f'messages${old_global_id}' not in new_keys
    assert f'customer${old_global_id}' not in new_keys

    # make sure file is still available after identity rotate
    new_share_id_customer_6 = share_id_customer_6.replace(old_global_id, new_global_id)
    share_open_v1('customer_6', new_share_id_customer_6)
    new_remote_path_customer_6 = remote_path_customer_6.replace(old_global_id, new_global_id)
    run_ssh_command_and_wait('customer_6', 'rm -rfv %s' % downloaded_filepath)[0].strip()
    file_download_start_v1('customer_6', remote_path=new_remote_path_customer_6, destination='/tmp')

    # and make sure this is still the same file
    new_downloaded_file_src = run_ssh_command_and_wait('customer_6', 'cat %s' % downloaded_filepath)[0].strip()
    assert local_file_src == downloaded_file_src, "source file and received file content is not equal after identity rotate"
    assert new_downloaded_file_src == downloaded_file_src, "received file content before identity rotate is not equal to received file after identity rotate"

    first_supplier = customer6_suppliers[0].replace('http://is:8084/', '').replace('.xml', '')
    old_folder_first_supplier = run_ssh_command_and_wait(first_supplier, f'ls -la ~/.bitdust/customers/{old_global_id}/')[0].strip()
    new_folder_first_supplier = run_ssh_command_and_wait(first_supplier, f'ls -la ~/.bitdust/customers/{new_global_id}/')[0].strip()
    assert old_folder_first_supplier == ''
    assert new_folder_first_supplier != ''
    print(f'first supplier {first_supplier} :\n', new_folder_first_supplier)

    second_supplier = customer6_suppliers[1].replace('http://is:8084/', '').replace('.xml', '')
    old_folder_second_supplier = run_ssh_command_and_wait(second_supplier, f'ls -la ~/.bitdust/customers/{old_global_id}/')[0].strip()
    new_folder_second_supplier = run_ssh_command_and_wait(second_supplier, f'ls -la ~/.bitdust/customers/{new_global_id}/')[0].strip()
    assert old_folder_second_supplier == ''
    assert new_folder_second_supplier != ''
    print(f'second supplier {second_supplier} :\n', new_folder_second_supplier)

    # test that friend6 idurl changed for customer_1
    new_friends = friend_list_v1('customer_1', extract_idurls=True)
    assert new_idurl in new_friends
    assert old_idurl not in new_friends



def test_identity_rotate_supplier_6_with_customer_3():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    # first start supplier_6 - his identity will be rotated later
    create_identity('supplier_6', 'supplier_6')

    connect_network('supplier_6')

    r = identity_get_v1('supplier_6')
    supplier_6_global_id = r['result'][0]['global_id']
    supplier_6_idurl = r['result'][0]['idurl']

    service_info_v1('supplier_6', 'service_supplier', 'ON')

    # make sure supplier_6 was hired by customer_3
    current_suppliers_idurls = supplier_list_v1('customer_3', expected_min_suppliers=2, expected_max_suppliers=2)

    # if he is not hired yet, we switch our first supplier to supplier_6
    if supplier_6_idurl not in current_suppliers_idurls:
        supplier_switch_v1('customer_3', supplier_idurl=supplier_6_idurl, position=0)

    current_suppliers_idurls = supplier_list_v1('customer_3', expected_min_suppliers=2, expected_max_suppliers=2)
    assert supplier_6_idurl in current_suppliers_idurls

    service_info_v1('customer_3', 'service_shared_data', 'ON')

    share_id_customer_3 = share_create_v1('customer_3')

    filename = 'cat.txt'
    virtual_filename = filename
    volume_customer_3 = '/customer_3'
    filepath_customer_3 = f'{volume_customer_3}/{filename}'
    remote_path_customer_3 = f'{share_id_customer_3}:{virtual_filename}'
    download_filepath_customer_3 = f'/tmp/{filename}'

    run_ssh_command_and_wait('customer_3', f'echo customer_3 > {filepath_customer_3}')

    file_create_v1('customer_3', remote_path_customer_3)

    file_upload_start_v1('customer_3', remote_path_customer_3, filepath_customer_3)

    packet_list_v1('customer_3', wait_all_finish=True)

    transfer_list_v1('customer_3', wait_all_finish=True)

    service_info_v1('customer_3', 'service_shared_data', 'ON')

    file_download_start_v1('customer_3', remote_path=remote_path_customer_3, destination='/tmp')

    file_1 = run_ssh_command_and_wait('customer_3', f'cat {filepath_customer_3}')[0].strip()
    file_2 = run_ssh_command_and_wait('customer_3', f'cat {download_filepath_customer_3}')[0].strip()
    assert file_1 == file_2

    # rotate identity sources on supplier_6
    identity_rotate_v1('supplier_6')

    time.sleep(1)

    r = identity_get_v1('supplier_6')
    supplier_6_global_id_new = r['result'][0]['global_id']
    supplier_6_idurl_new = r['result'][0]['idurl']
    assert supplier_6_global_id_new != supplier_6_global_id
    assert supplier_6_idurl_new != supplier_6_idurl

    service_info_v1('supplier_6', 'service_supplier', 'ON')

    file_sync_v1('customer_3')

    time.sleep(1)

    file_list_all_v1('customer_3')

    new_suppliers_idurls = supplier_list_v1('customer_3', expected_min_suppliers=2, expected_max_suppliers=2)
    assert supplier_6_idurl not in new_suppliers_idurls
    assert supplier_6_idurl_new in new_suppliers_idurls

    # to make sure other customers do not take that supplier need to stop it here
    stop_daemon('supplier_6')

    time.sleep(2)
