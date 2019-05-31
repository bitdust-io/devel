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

from ..testsupport import tunnel_url


def test_identity_customer_backup_and_restore():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    # TODO: ...
    return True

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

    shutil.move(backup_file_directory_c2, backup_file_directory_c3)

    try:
        response = requests.get(url=tunnel_url('customer_backup', 'process/stop/v1'))
        assert response.json()['status'] == 'OK', response.json()
    except Exception as exc:
        print('\n\nprocess/stop/v1 failed with ')

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
    # TODO:
    # also check if I my files are available and I can download
    # my message history also recovered
    # my keys also recovered


def test_identity_rotate_customer_5():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    # TODO: ...
    return True

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
