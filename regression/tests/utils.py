import time
import requests

from .testsupport import tunnel_url


def supplier_list_v1(customer: str, expected_connected_number=2, attempts=20, delay=5):
    count = 0
    while True:
        if count > attempts:
            assert False, f'{customer} failed to hire enough suppliers after many attempts'

        response = requests.get(url=tunnel_url(customer, 'supplier/list/v1'))
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        print('\n\nsupplier/list/v1 : %s\n' % response.json())
        if expected_connected_number is None:
            return response.json()
        num_connected = 0
        for s in response.json()['result']:
            if s['supplier_state'] == 'CONNECTED' and s['contact_state'] == 'CONNECTED':
                num_connected += 1
        if num_connected == expected_connected_number:
            break

        count += 1
        time.sleep(delay)


def share_create_v1(customer: str, key_size=1024):
    response = requests.post(url=tunnel_url(customer, 'share/create/v1'), json={'key_size': key_size, }, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nshare/create/v1 : %s\n' % response.json())
    return response.json()['result'][0]['key_id']


def file_upload_start_v1(customer: str, remote_path: str, local_path: str, open_share=True, wait_result=True):
    response = requests.post(
        url=tunnel_url(customer, 'file/upload/start/v1'),
        json={
            'remote_path': remote_path,
            'local_path': local_path,
            'wait_result': '1' if wait_result else '0',
            'open_share': '1' if open_share else '0',
        },
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nfile/upload/start/v1 remote_path=%s local_path=%s : %r\n' % (remote_path, local_path, response.json(),))


def file_download_start_v1(customer: str, remote_path: str, destination: str,
                           open_share=True, wait_result=True,
                           attempts=50, delay=5,
                           wait_tasks_finish=True):
    for i in range(attempts):
        response = requests.post(
            url=tunnel_url(customer, 'file/download/start/v1'),
            json={
                'remote_path': remote_path,
                'destination_folder': destination,
                'wait_result': '1' if wait_result else '0',
                'open_share': '1' if open_share else '0',
            },
        )
        assert response.status_code == 200
        print('\n\nfile/download/start/v1 [%s] remote_path=%s destination_folder=%s : %s\n' % (customer, remote_path, destination, response.json(), ))

        if response.json()['status'] == 'OK':
            print('\n\nfile/download/start/v1 [%s] remote_path=%s destination_folder=%s : %r\n' % (customer, remote_path, destination, response.json(), ))
            break

        if response.json()['errors'][0].count('failed') and response.json()['errors'][0].count('downloading'):
            time.sleep(delay)
        else:
            assert False, response.json()

    else:
        assert False, 'failed to start downloading uploaded file on [%r]: %r' % (customer, response.json(), )

    if wait_tasks_finish:
        for i in range(attempts):
            response = requests.get(
                url=tunnel_url(customer, 'file/download/v1'),
            )
            assert response.status_code == 200
            assert response.json()['status'] == 'OK', response.json()
            print('\n\nfile/download/v1 [%s] : %r\n' % (customer, response.json(), ))
    
            if len(response.json()['result']) == 0:
                break
    
            time.sleep(delay)
    
        else:
            assert False, 'some downloading tasks are still running on [%s]' % customer
