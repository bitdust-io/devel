import time
import requests
import pprint

from .testsupport import tunnel_url


def supplier_list_v1(customer: str, expected_min_suppliers=None, expected_max_suppliers=None, attempts=20, delay=5):
    count = 0
    while True:
        if count > attempts:
            assert False, f'{customer} failed to hire correct number of suppliers after many attempts'
        response = requests.get(url=tunnel_url(customer, 'supplier/list/v1'))
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        print('\n\nsupplier/list/v1 : %s\n' % response.json())
        if expected_min_suppliers is None and expected_max_suppliers is None:
            break
        num_connected = 0
        for s in response.json()['result']:
            if s['supplier_state'] == 'CONNECTED' and s['contact_state'] == 'CONNECTED':
                num_connected += 1
        print('\nfound %d connected suppliers at the moment\n' % num_connected)
        if expected_min_suppliers is not None and num_connected < expected_min_suppliers:
            count += 1
            time.sleep(delay)
            continue
        if expected_max_suppliers is not None and num_connected > expected_max_suppliers:
            count += 1
            time.sleep(delay)
            continue
        break
    return response.json()


def supplier_list_dht_v1(customer_node, observer_node, expected_ecc_map, expected_suppliers_number, retries=20, delay=3, accepted_mistakes=1):

    def _validate(obs):
        response = None
        count = 0
        while True:
            if count >= retries:
                print('\nfailed after %d retries' % count)
                return False
            response = requests.get(url=tunnel_url(obs, 'supplier/list/dht/v1?id=%s@is_8084' % customer_node))
            assert response.status_code == 200
            print('\nsupplier/list/dht/v1?id=%s from %s\n%s\n' % (customer_node, obs, pprint.pformat(response.json())))
            assert response.json()['status'] == 'OK', response.json()
            if not response.json()['result']:
                count += 1
                time.sleep(delay)
                continue
            ss = response.json()['result']['suppliers']
            if len(ss) != expected_suppliers_number or (ss.count('') > accepted_mistakes and expected_suppliers_number > 2):
                # print('\n%r' % response.json())
                count += 1
                time.sleep(delay)
                continue
            assert response.json()['result']['customer_idurl'] == 'http://is:8084/%s.xml' % customer_node, response.json()['result']['customer_idurl']
            assert response.json()['result']['ecc_map'] == expected_ecc_map, response.json()['result']['ecc_map']
            break
        return True

    if not _validate(observer_node):
        if not _validate('supplier_1'):
            assert False, 'customer family [%s] [%s] was not re-published correctly, observer [%s] and another node still see wrong info' % (
                customer_node, expected_ecc_map, observer_node, )

    return True


def share_create_v1(customer: str, key_size=1024):
    response = requests.post(url=tunnel_url(customer, 'share/create/v1'), json={'key_size': key_size, }, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nshare/create/v1 : %s\n' % response.json())
    return response.json()['result'][0]['key_id']


def file_create_v1(node, remote_path):
    response = requests.post(url=tunnel_url(node, 'file/create/v1'), json={'remote_path': remote_path}, )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nfile/create/v1 [%s] remote_path=%s : %s\n' % (node, remote_path, response.json(), ))
    return response.json()


def file_upload_start_v1(customer: str, remote_path: str, local_path: str,
                         open_share=True, wait_result=True,
                         attempts=50, delay=5,
                         wait_job_finish=True):
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
    print('\n\nfile/upload/start/v1 [%r] remote_path=%s local_path=%s : %r\n' % (customer, remote_path, local_path, response.json(),))
    if wait_job_finish:
        for i in range(attempts):
            response = requests.get(
                url=tunnel_url(customer, 'file/upload/v1'),
            )
            assert response.status_code == 200
            assert response.json()['status'] == 'OK', response.json()
            print('\n\nfile/upload/v1 [%s] : %r\n' % (customer, response.json(), ))
            if len(response.json()['result']['pending']) == 0 and len(response.json()['result']['running']) == 0:
                break
            time.sleep(delay)
        else:
            assert False, 'some uploading tasks are still running on [%s]' % customer
    return response.json()


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
    return response.json()


def config_set_v1(node, key, value):
    response = requests.post(
        url=tunnel_url(node, 'config/set/v1'),
        json={
            'key': key,
            'value': value,
        },
    )
    assert response.status_code == 200
    print('\n\nconfig/set/v1 [%s] key=%r value=%r : %s\n' % (node, key, value, response.json()))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def dht_value_get_v1(node, key, expected_data, record_type='skip_validation', retries=2, fallback_observer = 'supplier_1'):
    response = None
    for i in range(retries + 1):
        if i == retries - 1:
            node = fallback_observer
        response = requests.get(tunnel_url(node, 'dht/value/get/v1?record_type=%s&key=%s' % (record_type, key, )))
        try:
            assert response.status_code == 200
            assert response.json()['status'] == 'OK', response.json()
            assert len(response.json()['result']) > 0, response.json()
            assert response.json()['result'][0]['key'] == key, response.json()
            if expected_data == 'not_exist':
                assert response.json()['result'][0]['read'] == 'failed', response.json()
                assert 'value' not in response.json()['result'][0], response.json()
                assert len(response.json()['result'][0]['closest_nodes']) > 0, response.json()
            else:
                if response.json()['result'][0]['read'] == 'failed':
                    print('first request failed, retry one more time')
                    response = requests.get(tunnel_url(node, 'dht/value/get/v1?record_type=%s&key=%s' % (record_type, key, )))
                    assert response.status_code == 200
                    assert response.json()['status'] == 'OK', response.json()
                assert response.json()['result'][0]['read'] == 'success', response.json()
                assert 'value' in response.json()['result'][0], response.json()
                assert response.json()['result'][0]['value']['data'] in expected_data, response.json()
                assert response.json()['result'][0]['value']['key'] == key, response.json()
                assert response.json()['result'][0]['value']['type'] == record_type, response.json()
        except:
            time.sleep(2)
            if i == retries - 1:
                assert False, f'DHT value read validation failed: {node} {key} {expected_data} : {response.json()}'
    return response.json()


def dht_value_set_v1(node, key, new_data, record_type='skip_validation', ):
    response = requests.post(
        url=tunnel_url(node, 'dht/value/set/v1'),
        json={
            'key': key,
            'record_type': record_type,
            'value': {
                'data': new_data,
                'type': record_type,
                'key': key,
            },
        },
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    assert len(response.json()['result']) > 0, response.json()
    assert response.json()['result'][0]['write'] == 'success', response.json()
    assert response.json()['result'][0]['key'] == key, response.json()
    assert response.json()['result'][0]['value']['data'] == new_data, response.json()
    assert response.json()['result'][0]['value']['key'] == key, response.json()
    assert response.json()['result'][0]['value']['type'] == record_type, response.json()
    assert len(response.json()['result'][0]['closest_nodes']) > 0, response.json()
    return response.json()


def message_send_v1(node, recipient, data):
    response = requests.post(
        url=tunnel_url(node, 'message/send/v1'),
        json={
            'id': recipient,
            'data': data,
        },
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def message_receive_v1(node, expected_data, consumer='test_consumer',):
    response = requests.get(
        url=tunnel_url(node, f'message/receive/{consumer}/v1'),
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result'][0]['data'] == expected_data, response.json()


def user_ping_v1(node, remote_node_id, timeout=30):
    response = requests.get(tunnel_url(node, f'user/ping/v1?id={remote_node_id}'), timeout=timeout)
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def service_info_v1(node, service_name, expected_state, attempts=5, delay=1):
    current_state = None
    count = 0
    while current_state is None or current_state != expected_state:
        response = requests.get(url=tunnel_url(node, f'service/info/{service_name}/v1'))
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        current_state = response.json()['result'][0]['state']
        print(f'\n\nservice/info/{service_name}/v1 [{node}] : %s' % response.json())
        if current_state == expected_state:
            break
        count += 1
        if count >= attempts:
            assert False, f"service {service_name} is not {expected_state} after {attempts} attempts"
            return
        time.sleep(delay)
    print(f'service/info/{service_name}/v1 [{node}] : OK\n')


def wait_event(node, expected_event_id, consumer_id='regression_tests_wait_event', timeout=10, attempts=5):
    found = None
    count = 0
    while not found:
        response = requests.get(url=tunnel_url(node, f'event/listen/{consumer_id}/v1'), timeout=timeout)
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        print(f'\n\nevent/listen/{consumer_id}/v1 : %s\n' % response.json())
        for e in response.json()['result']:
            if e['id'] == expected_event_id:
                found = e
                break
        if found:
            break
        count += 1
        if count >= attempts:
            assert False, f'event "{expected_event_id}" was not raised on node [{node}]'
    return found

