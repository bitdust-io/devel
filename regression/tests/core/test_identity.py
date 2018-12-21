import time
import os
import shutil

import pytest
import requests

from ..utils import tunnel_url


@pytest.mark.skip(reason="rework identity restore method")
def test_identity_backup_restore():
    backup_file_directory_c2 = '/customer_backup/identity.backup'
    backup_file_directory_c3 = '/customer_restore/identity.backup'
    assert not os.path.exists(backup_file_directory_c2)

    response = requests.post(
        url=tunnel_url('customer_backup', 'identity/backup/v1'),
        json={
            'destination_path': backup_file_directory_c2,
        },
    )
    assert response.json()['status'] == 'OK', response.json()

    shutil.move(backup_file_directory_c2, backup_file_directory_c3)

    response = requests.get(url=tunnel_url('customer_backup', 'process/stop/v1'))
    assert response.json()['status'] == 'OK', response.json()

    response = requests.post(
        url=tunnel_url('customer_restore', 'identity/recover/v1'),
        json={
            'private_key_local_file': backup_file_directory_c3,
        },
    )
    assert response.json()['status'] == 'OK', response.json()

    response = requests.get(url=tunnel_url('customer_restore', 'network/connected/v1?wait_timeout=1'))
    assert response.json()['status'] == 'ERROR'

    for i in range(5):
        response = requests.get(url=tunnel_url('customer_restore', 'network/connected/v1?wait_timeout=1'))
        if response.json()['status'] == 'OK':
            break
        time.sleep(1)
    else:
        assert False, 'customer_restore was not able to join the network after identity recover'
