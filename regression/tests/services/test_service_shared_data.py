#!/usr/bin/env python
# test_service_shared_data.py
#
# Copyright (C) 2008-2019 Veselin Penev  https://bitdust.io
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

from ..testsupport import tunnel_url, run_ssh_command_and_wait, wait_service_state
from ..utils import prepare_connection, create_share, upload_file, download_file


def test_replace_supplier():
    #: TODO: investigate why files were not transfered
    return True

    prepare_connection('customer_1')
    share_id_customer_1 = create_share('customer_1')

    filename = 'file_to_be_distributed.txt'
    virtual_filename = filename

    volume_customer_1 = '/customer_1'
    filepath_customer_1 = f'{volume_customer_1}/{filename}'

    remote_path_customer_1 = f'{share_id_customer_1}:{virtual_filename}'

    run_ssh_command_and_wait('customer_1', f'echo customer_1 > {filepath_customer_1}')

    response = requests.post(url=tunnel_url('customer_1', 'file/create/v1'),
                             json={'remote_path': remote_path_customer_1}, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nfile/create/v1 remote_path=%s : %s\n' % (remote_path_customer_1, response.json(),))

    upload_file('customer_1', remote_path_customer_1, filepath_customer_1)

    time.sleep(15)

    download_file('customer_1', remote_path=remote_path_customer_1, destination=volume_customer_1)

    response = requests.get(tunnel_url('customer_1', '/supplier/list/v1'))
    assert response.status_code == 200
    supplier_list = response.json()['result']
    suppliers = set(x['idurl'] for x in supplier_list)
    assert len(suppliers) == 2

    response = requests.post(tunnel_url('customer_1', '/supplier/replace/v1'), json={'position': '0'})

    time.sleep(15)

    # import pdb; pdb.set_trace()


def test_sharedfile_same_name_as_existing():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    prepare_connection('customer_1')
    prepare_connection('customer_2')

    wait_service_state('customer_1', 'service_shared_data', 'ON', attempts=30, delay=2)
    wait_service_state('customer_2', 'service_shared_data', 'ON', attempts=30, delay=2)

    # create shares (logic unit to upload/download/share files)
    share_id_customer_1 = create_share('customer_1')
    share_id_customer_2 = create_share('customer_2')

    filename = 'cat.txt'
    virtual_filename = filename

    volume_customer_1 = '/customer_1'
    filepath_customer_1 = f'{volume_customer_1}/{filename}'

    volume_customer_2 = '/customer_2'
    filepath_customer_2 = f'{volume_customer_2}/{filename}'

    run_ssh_command_and_wait('customer_1', f'echo customer_1 > {filepath_customer_1}')
    run_ssh_command_and_wait('customer_2', f'echo customer_2 > {filepath_customer_2}')

    remote_path_customer_1 = f'{share_id_customer_1}:{virtual_filename}'
    remote_path_customer_2 = f'{share_id_customer_2}:{virtual_filename}'

    # create virtual file for customer_1
    response = requests.post(url=tunnel_url('customer_1', 'file/create/v1'), json={'remote_path': remote_path_customer_1}, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nfile/create/v1 remote_path=%s : %s\n' % (remote_path_customer_1, response.json(),))

    # create virtual file for customer_2
    response = requests.post(url=tunnel_url('customer_2', 'file/create/v1'), json={'remote_path': remote_path_customer_2}, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nfile/create/v1 remote_path=%s : %s\n' % (remote_path_customer_2, response.json(),))

    # upload file for customer_1
    upload_file('customer_1', remote_path_customer_1, filepath_customer_1)

    # upload file for customer_2
    upload_file('customer_2', remote_path_customer_2, filepath_customer_2)

    # wait for quite a while to allow files to be uploaded
    time.sleep(5)

    download_file('customer_1', remote_path=remote_path_customer_1, destination=volume_customer_1)
    download_file('customer_2', remote_path=remote_path_customer_2, destination=volume_customer_2)

    response = requests.put(
        url=tunnel_url('customer_1', 'share/grant/v1'),
        json={
            'trusted_global_id': 'customer_2@is_8084',
            'key_id': share_id_customer_1,
        },
        timeout=40,
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nshare/grant/v1 trusted_global_id=%s key_id=%s : %s\n' % ('customer_4@is_8084', share_id_customer_1, response.json(),))

    response = requests.get(tunnel_url('customer_2', 'file/list/all/v1'))
    assert response.status_code == 200, response.json()

    run_ssh_command_and_wait('customer_2', f'mkdir {volume_customer_2}/sharesamename')
    run_ssh_command_and_wait('customer_2', f'mkdir {volume_customer_2}/sharesamename2')

    download_file('customer_2', remote_path=remote_path_customer_1, destination=f'{volume_customer_2}/sharesamename')
    download_file('customer_2', remote_path=remote_path_customer_2, destination=f'{volume_customer_2}/sharesamename2')

    file_1 = run_ssh_command_and_wait('customer_2', f'cat {volume_customer_2}/sharesamename/cat.txt')[0].strip()
    file_2 = run_ssh_command_and_wait('customer_2', f'cat {volume_customer_2}/sharesamename2/cat.txt')[0].strip()

    assert file_1 != file_2


def test_file_shared_from_customer_1_to_customer_4():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    prepare_connection('customer_1')

    key_id = create_share('customer_1')

    origin_volume = '/customer_1'
    origin_filename = 'second_file_customer_1.txt'
    local_path = '%s/%s' % (origin_volume, origin_filename)

    virtual_file = 'second_virtual_file.txt'
    remote_path = '%s:%s' % (key_id, virtual_file)

    download_volume = '/customer_4'
    downloaded_file = '%s/%s' % (download_volume, virtual_file)

    wait_service_state('customer_1', 'service_shared_data', 'ON', attempts=30, delay=2)
    wait_service_state('customer_4', 'service_shared_data', 'ON', attempts=30, delay=2)

    response = requests.post(url=tunnel_url('customer_1', 'file/create/v1'), json={'remote_path': remote_path}, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nfile/create/v1 remote_path=%s : %s\n' % (remote_path, response.json(), ))

    upload_file('customer_1', remote_path, local_path)

    time.sleep(5)

    download_file('customer_1', remote_path=remote_path, destination='/customer_1')

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

    download_file('customer_4', remote_path=remote_path, destination=download_volume)

    local_file_src = run_ssh_command_and_wait('customer_1', 'cat %s' % local_path)[0].strip()
    print('customer_1:%s' % local_path, local_file_src)
    downloaded_file_src = run_ssh_command_and_wait('customer_4', 'cat %s' % downloaded_file)[0].strip()
    print('customer_4:%s' % downloaded_file, downloaded_file_src)
    assert local_file_src == downloaded_file_src, (local_file_src, downloaded_file_src, )
