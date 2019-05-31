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


def test_identity_customer_backup_and_restore():
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

    count = 0
    while True:
        if count > 10:
            assert False, 'customer_backup failed to hire enough suppliers after many attempts'
            return
        response = requests.get(url=tunnel_url('customer_backup', 'supplier/list/v1'))
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        print('\n\nsupplier/list/v1 : %s\n' % response.json())
        if len(response.json()['result']) == 2:
            connected = False
            for s in response.json()['result']:
                if s['supplier_state'] == 'CONNECTED' and s['contact_state'] == 'CONNECTED':
                    connected = True
            if connected:
                assert True
                break
        count += 1
        time.sleep(5)

    response = requests.post(url=tunnel_url('customer_backup', 'file/create/v1'), json={'remote_path': remote_path}, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    response = requests.post(
        url=tunnel_url('customer_backup', 'file/upload/start/v1'),
        json={
            'remote_path': remote_path,
            'local_path': source_local_path,
            'wait_result': '1',
        },
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    time.sleep(3)

    for i in range(20):
        response = requests.post(
            url=tunnel_url('customer_backup', 'file/download/start/v1'),
            json={
                'remote_path': remote_path,
                'destination_folder': download_volume,
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

    source_local_file_src = run_ssh_command_and_wait('customer_backup', 'cat %s' % source_local_path)[0].strip()
    print('customer_backup:%s' % source_local_path, source_local_file_src)
    downloaded_file_src = run_ssh_command_and_wait('customer_backup', 'cat %s' % downloaded_file)[0].strip()
    print('customer_backup:%s' % downloaded_file, downloaded_file_src)
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
            # TODO: currently broken functionality. to be fixed
            # assert False, response.json()
            pass

    else:
        assert False, 'download was not successful: %r' % response.json()

    recovered_file_src = run_ssh_command_and_wait('customer_restore', 'cat %s' % recovered_file)[0].strip()
    print('customer_restore:%s' % recovered_file, recovered_file_src)
    # TODO: currently broken functionality. to be fixed
    # assert source_local_file_src == recovered_file_src, (source_local_file_src, recovered_file_src, )

    # TODO:
    # test my keys also recovered
    # test my message history also recovered



def test_identity_rotate_customer_5():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    OTHER_KNOWN_ID_SERVERS = [
        'is:8084:6661',
        'is_a:8084:6661',
        'is_b:8084:6661',
    #     'identity-server-a:8084:6661',
    #     'identity-server-b:8084:6661',
    ]

    # configure ID servers
    run_ssh_command_and_wait('customer_5', 'bitdust set services/identity-propagate/min-servers 2')
    run_ssh_command_and_wait('customer_5', 'bitdust set services/identity-propagate/max-servers 2')
    run_ssh_command_and_wait('customer_5', 'bitdust set services/identity-propagate/known-servers %s' % (','.join(OTHER_KNOWN_ID_SERVERS)))

    response = requests.get(
        url=tunnel_url('customer_5', 'identity/get/v1'),
    )
    print('\n\nidentity/get/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    old_sources = response.json()['result'][0]['sources']

    response = requests.put(
        url=tunnel_url('customer_5', 'identity/rotate/v1'),
    )
    print('\n\nidentity/rotate/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    time.sleep(1)

    response = requests.get(
        url=tunnel_url('customer_5', 'identity/get/v1'),
    )
    print('\n\nidentity/get/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result'][0]['sources'] != old_sources
