#!/usr/bin/env python
# keywords.py
#
# Copyright (C) 2008-2019 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (keywords.py) is part of BitDust Software.
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
import requests
import pprint

from .testsupport import tunnel_url


def supplier_list_v1(customer: str, expected_min_suppliers=None, expected_max_suppliers=None, attempts=30, delay=3, extract_suppliers=True):
    count = 0
    num_connected = 0
    while True:
        if count > attempts:
            assert False, f'{customer} failed to hire correct number of suppliers after many attempts. currently %d, expected min %d and max %d' % (
                num_connected, expected_min_suppliers, expected_max_suppliers, )
        response = requests.get(url=tunnel_url(customer, 'supplier/list/v1'))
        assert response.status_code == 200
        print('\nsupplier/list/v1 : %s\n' % pprint.pformat(response.json()))
        assert response.json()['status'] == 'OK', response.json()
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
    if not extract_suppliers:
        return response.json()
    return [s['idurl'] for s in response.json()['result']]


def supplier_list_dht_v1(customer_node, observer_node, expected_ecc_map, expected_suppliers_number, retries=30, delay=3, accepted_mistakes=0):

    def _validate(obs):
        response = None
        num_suppliers = 0
        count = 0
        while True:
            if count >= retries:
                print('\nDHT info still wrong after %d retries, currently see %d suppliers, but expected %d' % (
                    count, num_suppliers, expected_suppliers_number))
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
            num_suppliers = len(ss)
            if num_suppliers != expected_suppliers_number:
                print('\ncurrently see %d suppliers but expected number is %d\n' % (num_suppliers, expected_suppliers_number))
                count += 1
                time.sleep(delay)
                continue
            if ss.count('') > accepted_mistakes or len(list(filter(None, ss))) != expected_suppliers_number:
                print('\ncurrently see %d empty suppliers\n' % ss.count(''))
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


def supplier_switch_v1(customer: str, supplier_idurl: str, position: int, validate_retries=30, delay=3):
    response = requests.put(url=tunnel_url(customer, 'supplier/switch/v1'), json={
        'index': position,
        'new_idurl': supplier_idurl,
    }, )
    assert response.status_code == 200
    print('\nsupplier/switch/v1 [%s] with new supplier %s at position %r : %s\n' % (
        customer, supplier_idurl, position, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    if not validate_retries:
        return response.json()
    count = 0
    while True:
        if count >= validate_retries:
            break
        current_suppliers_idurls = supplier_list_v1(customer, expected_min_suppliers=None, expected_max_suppliers=None, attempts=1)
        if supplier_idurl in current_suppliers_idurls:
            _pos = current_suppliers_idurls.index(supplier_idurl)
            assert position == _pos
            print('\nfound supplier %r at position %d for customer %r' % (supplier_idurl, position, customer))
            return current_suppliers_idurls
        count += 1
        time.sleep(delay)
    assert False, 'failed to switch supplier at position %r to %r after %d retries' % ( position, supplier_idurl, count, )
    return None
        

def share_create_v1(customer: str, key_size=1024):
    response = requests.post(url=tunnel_url(customer, 'share/create/v1'), json={'key_size': key_size, }, )
    assert response.status_code == 200
    print('\nshare/create/v1 [%s] : %s\n' % (customer, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()['result'][0]['key_id']


def share_open_v1(customer: str, key_id):
    response = requests.post(url=tunnel_url(customer, 'share/open/v1'), json={'key_id': key_id, }, )
    assert response.status_code == 200
    print('\nshare/open/v1 [%s] key_id=%r : %s\n' % (customer, key_id, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def file_sync_v1(node):
    response = requests.get(
        url=tunnel_url(node, 'file/sync/v1'),
    )
    assert response.status_code == 200
    print('\nfile/sync/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def file_list_all_v1(node, expected_reliable=100, attempts=30, delay=3):
    if not expected_reliable:
        response = requests.get(
            url=tunnel_url(node, 'file/list/all/v1'),
        )
        assert response.status_code == 200
        print('\nfile/list/all/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
        assert response.json()['status'] == 'OK', response.json()
        return response.json()

    response = None
    latest_reliable = None
    count = 0
    while latest_reliable is None or latest_reliable <= expected_reliable:
        response = requests.get(
            url=tunnel_url(node, 'file/list/all/v1'),
        )
        assert response.status_code == 200
        print('\nfile/list/all/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
        assert response.json()['status'] == 'OK', response.json()
        lowest = 100
        lowest_file = None
        for fil in response.json()['result']:
            for ver in fil['versions']:
                reliable = int(ver['reliable'].replace('%', ''))
                if reliable < lowest:
                    lowest = reliable
                    lowest_file = fil
        latest_reliable = lowest
        if latest_reliable >= expected_reliable:
            break
        count += 1
        if count >= attempts:
            assert False, f"file {lowest_file} is not {expected_reliable} % reliable after {attempts} attempts"
            return
        time.sleep(delay)
    return response.json()


def file_create_v1(node, remote_path):
    response = requests.post(url=tunnel_url(node, 'file/create/v1'), json={'remote_path': remote_path}, )
    assert response.status_code == 200
    print('\nfile/create/v1 [%s] remote_path=%s : %s\n' % (node, remote_path, pprint.pformat(response.json()), ))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def file_upload_start_v1(customer: str, remote_path: str, local_path: str,
                         open_share=True, wait_result=True,
                         attempts=30, delay=3,
                         wait_job_finish=True,
                         wait_packets_finish=True,
                         wait_transfers_finish=True,
                         ):
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
    print('\nfile/upload/start/v1 [%r] remote_path=%s local_path=%s : %s\n' % (customer, remote_path, local_path, pprint.pformat(response.json()),))
    assert response.json()['status'] == 'OK', response.json()
    if wait_job_finish:
        for i in range(attempts):
            response = requests.get(
                url=tunnel_url(customer, 'file/upload/v1'),
            )
            assert response.status_code == 200
            print('\nfile/upload/v1 [%s] : %s\n' % (customer, pprint.pformat(response.json()), ))
            assert response.json()['status'] == 'OK', response.json()
            if len(response.json()['result']['pending']) == 0 and len(response.json()['result']['running']) == 0:
                break
            time.sleep(delay)
        else:
            assert False, 'some uploading tasks are still running on [%s]' % customer
    if wait_packets_finish:
        packet_list_v1(customer, wait_all_finish=True, attempts=attempts, delay=delay)
    if wait_transfers_finish:
        transfer_list_v1(customer, wait_all_finish=True, attempts=attempts, delay=delay)
    return response.json()


def file_download_start_v1(customer: str, remote_path: str, destination: str,
                           open_share=True, wait_result=True,
                           attempts=30, delay=3,
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
        print('\nfile/download/start/v1 [%s] remote_path=%s destination_folder=%s : %s\n' % (
            customer, remote_path, destination, pprint.pformat(response.json()), ))
        if response.json()['status'] == 'OK':
            print('\nfile/download/start/v1 [%s] remote_path=%s destination_folder=%s : %s\n' % (
                customer, remote_path, destination, pprint.pformat(response.json()), ))
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
            print('\nfile/download/v1 [%s] : %s\n' % (customer, pprint.pformat(response.json()), ))
            assert response.json()['status'] == 'OK', response.json()
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
    print('\nconfig/set/v1 [%s] key=%r value=%r : %s\n' % (
        node, key, value, pprint.pformat(response.json())))
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
            print('\ndht/value/get/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
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
    print('\ndht/value/set/v1 [%s] key=%s : %s\n' % (node, key, pprint.pformat(response.json()), ))
    assert response.json()['status'] == 'OK', response.json()
    assert len(response.json()['result']) > 0, response.json()
    assert response.json()['result'][0]['write'] == 'success', response.json()
    assert response.json()['result'][0]['key'] == key, response.json()
    assert response.json()['result'][0]['value']['data'] == new_data, response.json()
    assert response.json()['result'][0]['value']['key'] == key, response.json()
    assert response.json()['result'][0]['value']['type'] == record_type, response.json()
    assert len(response.json()['result'][0]['closest_nodes']) > 0, response.json()
    return response.json()


def dht_db_dump_v1(node):
    try:
        response = requests.get(tunnel_url(node, 'dht/db/dump/v1'))
    except:
        return None
    print('\ndht/db/dump/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
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
    print(f'\nmessage/send/v1 [%s] : %s\n' % (
        node, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def message_receive_v1(node, expected_data, consumer='test_consumer',):
    response = requests.get(
        url=tunnel_url(node, f'message/receive/{consumer}/v1'),
    )
    assert response.status_code == 200
    print(f'\nmessage/receive/{consumer}/v1 [%s] : %s\n' % (
        node, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result'][0]['data'] == expected_data, response.json()


def user_ping_v1(node, remote_node_id, timeout=30):
    err = None
    try:
        response = requests.get(tunnel_url(node, f'user/ping/v1?id={remote_node_id}'), timeout=timeout)
    except Exception as exc:
        err = exc
        response = None
    if not response:
        assert False, f'ping {remote_node_id} failed : {err}'
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def service_info_v1(node, service_name, expected_state, attempts=30, delay=3):
    current_state = None
    count = 0
    while current_state is None or current_state != expected_state:
        response = requests.get(url=tunnel_url(node, f'service/info/{service_name}/v1'))
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        current_state = response.json()['result'][0]['state']
        print(f'\nservice/info/{service_name}/v1 [{node}] : %s' % pprint.pformat(response.json()))
        if current_state == expected_state:
            break
        count += 1
        if count >= attempts:
            assert False, f"service {service_name} is not {expected_state} after {attempts} attempts"
            return
        time.sleep(delay)
    print(f'service/info/{service_name}/v1 [{node}] : OK\n')


def event_listen_v1(node, expected_event_id, consumer_id='regression_tests_wait_event', attempts=3, timeout=10,):
    found = None
    count = 0
    while not found:
        response = requests.get(url=tunnel_url(node, f'event/listen/{consumer_id}/v1'), timeout=timeout)
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        print(f'\nevent/listen/{consumer_id}/v1 : %s\n' % pprint.pformat(response.json()))
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


def packet_list_v1(node, wait_all_finish=False, attempts=60, delay=3):
    for i in range(attempts):
        response = requests.get(
            url=tunnel_url(node, 'packet/list/v1'),
        )
        assert response.status_code == 200
        print('\npacket/list/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
        assert response.json()['status'] == 'OK', response.json()
        if len(response.json()['result']) == 0 or not wait_all_finish:
            break
        time.sleep(delay)
    else:
        assert False, 'some packets are still have in/out progress on [%s]' % node
    return response.json()


def transfer_list_v1(node, wait_all_finish=False, attempts=60, delay=3):
    for i in range(attempts):
        response = requests.get(
            url=tunnel_url(node, 'transfer/list/v1'),
        )
        assert response.status_code == 200
        print('\ntransfer/list/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
        assert response.json()['status'] == 'OK', response.json()
        if not wait_all_finish:
            break
        some_incoming = False
        some_outgoing = False
        for r in response.json()['result']:
            if r.get('incoming', []):
                some_incoming = True
                break
            if r.get('outgoing', []):
                some_outgoing = True
                break
        if not some_incoming and not some_outgoing:
            break
        time.sleep(delay)
    else:
        assert False, 'some transfers are still running on [%s]' % node
    return response.json()


def identity_get_v1(node):
    response = requests.get(url=tunnel_url(node, 'identity/get/v1'))
    assert response.status_code == 200
    print('\nidentity/get/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def identity_rotate_v1(node):
    response = requests.put(url=tunnel_url(node, 'identity/rotate/v1'))
    assert response.status_code == 200
    print('\nidentity/rotate/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def key_list_v1(node):
    response = requests.get(
        url=tunnel_url(node, 'key/list/v1'),
    )
    assert response.status_code == 200
    print('\nkey/list/v1 [%s] : %s\n' % (node, pprint.pformat(response.json()), ))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()

