#!/usr/bin/env python
# test_service_restores.py
#
# Copyright (C) 2008-2018 Stanislav Evseev, Veselin Penev  https://bitdust.io
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


import time
import os
import requests

from ..testsupport import tunnel_url, run_ssh_command_and_wait


def test_upload_download_file_with_master_customer_1():
    shared_volume = '/customer_1'
    origin_filename = 'file_customer_1.txt'

    local_file = '%s/%s' % (shared_volume, origin_filename)

    key_id = 'master$customer_1@is_8084'
    virtual_file = 'virtual_file.txt'

    remote_path = '%s:%s' % (key_id, virtual_file)

    download_volume = '/customer_1'

    downloaded_file = '%s/%s' % (download_volume, virtual_file)

    assert not os.path.exists(downloaded_file)

    response = requests.post(url=tunnel_url('customer_1', 'file/create/v1'), json={'remote_path': remote_path}, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    response = requests.post(
        url=tunnel_url('customer_1', 'file/upload/start/v1'),
        json={
            'remote_path': remote_path,
            'local_path': local_file,
            'wait_result': True,
        },
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    for i in range(20):
        response = requests.post(
            url=tunnel_url('customer_1', 'file/download/start/v1'),
            json={
                'remote_path': remote_path,
                'destination_folder': download_volume,
                'wait_result': True,
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
        assert False, 'download was not successful: ' + response.json()

    local_file_hash = run_ssh_command_and_wait('customer_1', 'sha1sum %s' % local_file)[0].strip().split(' ')[0].strip()
    downloaded_file_hash = run_ssh_command_and_wait('customer_1', 'sha1sum %s' % downloaded_file)[0].strip().split(' ')[0].strip()
    assert local_file_hash == downloaded_file_hash, (local_file_hash, downloaded_file_hash, )
