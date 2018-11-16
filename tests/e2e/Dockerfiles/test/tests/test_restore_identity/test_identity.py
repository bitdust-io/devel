import time
import os
import shutil
import requests


def test_customer_2_backup_restore():
    backup_file_directory_c2 = '/customer_2/identity.backup'
    backup_file_directory_c3 = '/customer_3/identity.backup'
    assert not os.path.exists(backup_file_directory_c2)

    response = requests.post('http://customer_2:8180/identity/backup/v1', json={'destination_path': backup_file_directory_c2})
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    response = requests.get('http://customer_2:8180/process/stop/v1')
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    shutil.move(backup_file_directory_c2, backup_file_directory_c3)

    response = requests.post('http://customer_3:8180/identity/recover/v1',
                             json={'private_key_local_file': backup_file_directory_c3})

    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    response = requests.get('http://customer_3:8180/network/connected/v1?wait_timeout=1')
    response_json = response.json()
    assert response_json['status'] == 'ERROR'

    for i in range(5):
        response = requests.get('http://customer_3:8180/network/connected/v1?wait_timeout=1')
        response_json = response.json()
        if response_json['status'] == 'OK':
            break
        time.sleep(1)
    else:
        assert False
