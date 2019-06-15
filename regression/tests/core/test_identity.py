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

from ..testsupport import tunnel_url, run_ssh_command_and_wait
from ..keywords import service_info_v1, file_create_v1, file_upload_start_v1, file_download_start_v1, \
    supplier_list_v1, config_set_v1, transfer_list_v1, packet_list_v1


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

    service_info_v1('customer_backup', 'service_my_data', 'ON', attempts=30, delay=2)

    file_create_v1('customer_backup', remote_path)

    file_upload_start_v1('customer_backup', remote_path, source_local_path)

    service_info_v1('customer_backup', 'service_restores', 'ON')
    
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
    # time.sleep(5)

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

    # TODO: currently broken functionality. to be fixed
    # service_info_v1('customer_restore', 'service_my_data', 'ON', attempts=30, delay=2)

    # step4: try to recover stored file again
    key_id = 'master$customer_backup@is_8084'
    recover_volume = '/customer_restore'
    virtual_file = 'virtual_file.txt'
    remote_path = '%s:%s' % (key_id, virtual_file)
    recovered_file = '%s/%s' % (recover_volume, virtual_file)
    # TODO: currently broken functionality. to be fixed
    if False:
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
                # TODO: currently broken functionality. to be fixed
                # assert False, response.json()
                pass
    
        else:
            # TODO: currently broken functionality. to be fixed
            # assert False, 'download was not successful: %r' % response.json()
            pass

    # TODO: currently broken functionality. to be fixed
    # recovered_file_src = run_ssh_command_and_wait('customer_restore', 'cat %s' % recovered_file)[0].strip()
    # print('customer_restore:%s' % recovered_file, recovered_file_src)
    # assert source_local_file_src == recovered_file_src, (source_local_file_src, recovered_file_src, )

    # TODO:
    # test my keys also recovered
    # test my message history also recovered



def test_identity_rotate_customer_5():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    return True

    # configure ID servers
    preferred_servers = [
        'is:8084:6661',
        'identity-server-a:8084:6661',
        'identity-server-b:8084:6661',
    ]
    run_ssh_command_and_wait('customer_5', 'bitdust set services/identity-propagate/min-servers 1')
    run_ssh_command_and_wait('customer_5', 'bitdust set services/identity-propagate/max-servers 2')
    run_ssh_command_and_wait('customer_5', 'bitdust set services/identity-propagate/preferred-servers %s' % (','.join(preferred_servers)))

    # remember my current ID sources
    response = requests.get(
        url=tunnel_url('customer_5', 'identity/get/v1'),
    )
    print('\n\nidentity/get/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    old_sources = response.json()['result'][0]['sources']

    # rotate my identity
    response = requests.put(
        url=tunnel_url('customer_5', 'identity/rotate/v1'),
    )
    print('\n\nidentity/rotate/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    time.sleep(1)

    # and make sure my ID sources were changed
    response = requests.get(
        url=tunnel_url('customer_5', 'identity/get/v1'),
    )
    print('\n\nidentity/get/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result'][0]['sources'] != old_sources

    # now change back to original identity server to not brake other tests
    preferred_servers = [
        'is:8084:6661',
    ]
    run_ssh_command_and_wait('customer_5', 'bitdust set services/identity-propagate/min-servers 1')
    run_ssh_command_and_wait('customer_5', 'bitdust set services/identity-propagate/max-servers 1')
    run_ssh_command_and_wait('customer_5', 'bitdust set services/identity-propagate/preferred-servers %s' % (','.join(preferred_servers)))
    # rotate my identity
    response = requests.put(
        url=tunnel_url('customer_5', 'identity/rotate/v1'),
    )
    print('\n\nidentity/rotate/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    time.sleep(1)

    # and make sure my ID source is reverted
    response = requests.get(
        url=tunnel_url('customer_5', 'identity/get/v1'),
    )
    print('\n\nidentity/get/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result'][0]['sources'] == old_sources
