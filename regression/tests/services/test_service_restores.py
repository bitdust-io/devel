#!/usr/bin/env python
# test_service_restores.py
#
# Copyright (C) 2008-2019 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (test_service_restores.py) is part of BitDust Software.
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
from ..keywords import service_info_v1, file_create_v1, file_upload_start_v1


def test_upload_download_file_with_master_customer_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    key_id = 'master$customer_1@is_8084'
    shared_volume = '/customer_1'
    origin_filename = 'file_customer_1.txt'
    local_path = '%s/%s' % (shared_volume, origin_filename)
    virtual_file = 'virtual_file.txt'
    remote_path = '%s:%s' % (key_id, virtual_file)
    download_volume = '/customer_1'
    downloaded_file = '%s/%s' % (download_volume, virtual_file)

    count = 0
    while True:
        if count > 10:
            assert False, 'customer_1 failed to hire enough suppliers after many attempts'
            return 
        response = requests.get(url=tunnel_url('customer_1', 'supplier/list/v1'))
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        print('\n\nsupplier/list/v1 : %s\n' % response.json())
        if len(response.json()['result']) == 2:
            for s in response.json()['result']:
                assert s['supplier_state'] == 'CONNECTED'
                assert s['contact_state'] == 'CONNECTED'
            assert True
            break
        count += 1
        time.sleep(5)

    service_info_v1('customer_1', 'service_my_data', 'ON', attempts=30, delay=2)

    file_create_v1('customer_1', remote_path)

    file_upload_start_v1('customer_1', remote_path, local_path, wait_result=True, )
    
    for i in range(20):
        response = requests.post(
            url=tunnel_url('customer_1', 'file/download/start/v1'),
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

    local_file_src = run_ssh_command_and_wait('customer_1', 'cat %s' % local_path)[0].strip()
    print('customer_1: file %s is %d bytes long' % (local_path, len(local_file_src)))
    
    downloaded_file_src = run_ssh_command_and_wait('customer_1', 'cat %s' % downloaded_file)[0].strip()
    print('customer_1: file %s is %d bytes long' % (downloaded_file, len(downloaded_file_src)))

    assert local_file_src == downloaded_file_src, (local_file_src, downloaded_file_src, )
