import time
import requests

from .testsupport import tunnel_url


def prepare_connection(customer: str):
    count = 0
    while True:
        if count > 10:
            assert False, f'{customer} failed to hire enough suppliers after many attempts'

        response = requests.get(url=tunnel_url(customer, 'supplier/list/v1'))
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        print('\n\nsupplier/list/v1 : %s\n' % response.json())
        num_connected = 0
        for s in response.json()['result']:
            if s['supplier_state'] == 'CONNECTED' and s['contact_state'] == 'CONNECTED':
                num_connected += 1
        if num_connected == 2:
            break

        count += 1
        time.sleep(5)


def create_share(customer: str):
    response = requests.post(url=tunnel_url(customer, 'share/create/v1'), json={'key_size': 1024, }, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nshare/create/v1 : %s\n' % response.json())
    return response.json()['result'][0]['key_id']


def upload_file(customer: str, remote_path: str, local_path: str):
    response = requests.post(
        url=tunnel_url(customer, 'file/upload/start/v1'),
        json={
            'remote_path': remote_path,
            'local_path': local_path,
            'wait_result': '1',
            'open_share': '1',
        },
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nfile/upload/start/v1 remote_path=%s local_path=%s : %r\n' % (remote_path, local_path, response.json(),))


def download_file(customer: str, remote_path: str, destination: str):
    for i in range(50):
        response = requests.post(
            url=tunnel_url(customer, 'file/download/start/v1'),
            json={
                'remote_path': remote_path,
                'destination_folder': destination,
                'wait_result': '1',
                'open_share': '1',
            },
        )
        assert response.status_code == 200
        print('\n\nfile/download/start/v1 remote_path=%s destination_folder=%s : %s\n' % (remote_path, destination, response.json(), ))

        if response.json()['status'] == 'OK':
            print('\n\nfile/download/start/v1 remote_path=%s destination_folder=%s : %r\n' % (remote_path, destination, response.json(), ))
            break

        if response.json()['errors'][0].count('failed') and response.json()['errors'][0].count('downloading'):
            time.sleep(5)
        else:
            assert False, response.json()

    else:
        assert False, 'failed to download uploaded file: %r' % response.json()
