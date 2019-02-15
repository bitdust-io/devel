#!/usr/bin/env python
# test_service_shared_data.py
#
# Copyright (C) 2008-2018 Veselin Penev  https://bitdust.io
#
# This file (test_service_shared_data.py) is part of BitDust Software.
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
import requests

from ..testsupport import tunnel_url, run_ssh_command_and_wait


def test_file_shared_from_customer_1_to_customer_4():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    response = requests.post(url=tunnel_url('customer_1', 'share/create/v1'), json={'key_size': 1024, }, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nshare/create/v1 : %s\n' % response.json())

    key_id = response.json()['result'][0]['key_id']
    shared_volume = '/customer_1'
    origin_filename = 'second_file_customer_1.txt'
    local_path = '%s/%s' % (shared_volume, origin_filename)
    virtual_file = 'second_virtual_file.txt'
    remote_path = '%s:%s' % (key_id, virtual_file)
    download_volume = '/customer_4'
    downloaded_file = '%s/%s' % (download_volume, virtual_file)
    assert not os.path.exists(downloaded_file)

    response = requests.post(url=tunnel_url('customer_1', 'file/create/v1'), json={'remote_path': remote_path}, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nfile/create/v1 remote_path=%s : %s\n' % (remote_path, response.json(), ))

    response = requests.post(
        url=tunnel_url('customer_1', 'file/upload/start/v1'),
        json={
            'remote_path': remote_path,
            'local_path': local_path,
            'wait_result': '1',
            'open_share': '1',
        },
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nfile/upload/start/v1 remote_path=%s local_path=%s : %r\n' % (remote_path, local_path, response.json(), ))

    time.sleep(5)

    for i in range(10):
        response = requests.post(
            url=tunnel_url('customer_1', 'file/download/start/v1'),
            json={
                'remote_path': remote_path,
                'destination_folder': '/customer_1',
                'wait_result': '1',
                'open_share': '1',
            },
        )
        assert response.status_code == 200
        print('\n\nfile/download/start/v1 remote_path=%s destination_folder=%s : %s\n' % (remote_path, '/customer_1', response.json(), ))

        if response.json()['status'] == 'OK':
            print('\n\nfile/download/start/v1 remote_path=%s destination_folder=%s : %r\n' % (remote_path, '/customer_1', response.json(), ))
            break

        if response.json()['errors'][0].count('failed') and response.json()['errors'][0].count('downloading'):
            time.sleep(5)
        else:
            assert False, response.json()

    else:
        assert False, 'failed to download uploaded file: %r' % response.json()

    time.sleep(1)

    response = requests.put(
        url=tunnel_url('customer_1', 'share/grant/v1'),
        json={
            'trusted_global_id': 'customer_4@is_8084',
            'key_id': key_id,
        },
        timeout=40,
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nshare/grant/v1 trusted_global_id=%s key_id=%s : %s\n' % ('customer_4@is_8084', key_id, response.json(), ))

    time.sleep(1)

    for i in range(10):
        response = requests.post(
            url=tunnel_url('customer_4', 'file/download/start/v1'),
            json={
                'remote_path': remote_path,
                'destination_folder': download_volume,
                'wait_result': '1',
                'open_share': '1',
            },
        )
        assert response.status_code == 200
        print('\n\nfile/download/start/v1 remote_path=%s destination_folder=%s : %s\n' % (remote_path, download_volume, response.json(), ))

        if response.json()['status'] == 'OK':
            print('\n\nfile/download/start/v1 remote_path=%s destination_folder=%s : %r\n' % (remote_path, download_volume, response.json(), ))
            break

        if response.json()['errors'][0].count('failed') and response.json()['errors'][0].count('downloading'):
            time.sleep(5)
        else:
            assert False, response.json()

    else:
        assert False, 'failed to download shared file: %r' % response.json()

    local_file_hash = run_ssh_command_and_wait('customer_1', 'sha1sum %s' % local_path)[0].strip().split(' ')[0].strip()
    downloaded_file_hash = run_ssh_command_and_wait('customer_4', 'sha1sum %s' % downloaded_file)[0].strip().split(' ')[0].strip()
    assert local_file_hash == downloaded_file_hash, (local_file_hash, downloaded_file_hash, )
