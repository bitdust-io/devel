#!/usr/bin/env python
# keywords.py
#
# Copyright (C) 2008 Stanislav Evseev, Veselin Penev  https://bitdust.io
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

import os
import re
import time
import requests
import pprint
import base64
import threading

from testsupport import request_get, request_post, request_put, request_delete, run_ssh_command_and_wait  # @UnresolvedImport
from testsupport import dbg, warn  # @UnresolvedImport

#------------------------------------------------------------------------------


def supplier_list_v1(customer: str, expected_min_suppliers=None, expected_max_suppliers=None, attempts=20, delay=5, extract_suppliers=True, verbose=True):
    count = 0
    num_connected = 0
    while True:
        if count > attempts:
            assert False, f'{customer} failed to hire correct number of suppliers after many attempts. currently %d, expected min %d and max %d' % (
                num_connected,
                expected_min_suppliers,
                expected_max_suppliers,
            )
        response = request_get(customer, 'supplier/list/v1', timeout=20, verbose=verbose)
        assert response.status_code == 200
        if verbose:
            dbg('supplier/list/v1 : %s\n' % pprint.pformat(response.json()))
        assert response.json()['status'] == 'OK', response.json()
        if expected_min_suppliers is None and expected_max_suppliers is None:
            break
        num_connected = 0
        num_total = len(response.json()['result'])
        for s in response.json()['result']:
            if s['supplier_state'] == 'CONNECTED' and s['contact_state'] == 'CONNECTED':
                num_connected += 1
        if expected_min_suppliers is not None and (num_connected < expected_min_suppliers or num_total < expected_min_suppliers):
            if verbose:
                dbg('found %d connected suppliers at the moment, but expect at least %d\n' % (num_connected, expected_min_suppliers))
            count += 1
            time.sleep(delay)
            continue
        if expected_max_suppliers is not None and (num_connected > expected_max_suppliers or num_total > expected_max_suppliers):
            if verbose:
                dbg('found %d connected suppliers at the moment, but expect no more than %d\n' % (num_connected, expected_max_suppliers))
            count += 1
            time.sleep(delay)
            continue
        if verbose:
            dbg('found %d connected suppliers at the moment\n' % num_connected)
        break
    if not extract_suppliers:
        return response.json()
    return [s['idurl'] for s in response.json()['result']]


def supplier_list_dht_v1(customer_id, observers_ids, expected_ecc_map, expected_suppliers_number, retries=30, delay=3, accepted_mistakes=1):
    customer_node = customer_id.split('@')[0]

    def _validate(obs):
        response = None
        num_suppliers = 0
        count = 0
        while True:
            mistakes = 0
            if count >= retries:
                dbg('DHT info still wrong after %d retries, currently see %d suppliers, but expected %d' % (count, num_suppliers, expected_suppliers_number))
                return False
            try:
                response = request_get(obs, 'supplier/list/dht/v1?id=%s' % customer_id, timeout=20)
            except requests.exceptions.ConnectionError as exc:
                warn('connection error: %r' % exc)
                return False
            if response.status_code != 200:
                count += 1
                time.sleep(delay)
                continue
            dbg('supplier/list/dht/v1?id=%s from %s\n%s\n' % (customer_id, obs, pprint.pformat(response.json())))
            if not response.json()['status'] == 'OK':
                count += 1
                time.sleep(delay)
                continue
            if not response.json()['result']:
                count += 1
                time.sleep(delay)
                continue
            if not response.json()['result']['customer_idurl'].count('%s.xml' % customer_node):
                warn('currently see customer_idurl=%r, but expect family owner to be %r\n' % (response.json()['result']['customer_idurl'], customer_node))
                count += 1
                time.sleep(delay)
                continue
            ss = response.json()['result']['suppliers']
            num_suppliers = len(ss)
            if num_suppliers != expected_suppliers_number:
                warn('currently see %d suppliers but expected number is %d\n' % (num_suppliers, expected_suppliers_number))
                count += 1
                time.sleep(delay)
                continue
            if len(list(filter(None, ss))) != expected_suppliers_number:
                mistakes += abs(expected_suppliers_number - len(list(filter(None, ss))))
                warn('found missing suppliers\n')
            if not response.json()['result']['ecc_map'] == expected_ecc_map:
                mistakes += 1
                warn('currently see ecc_map=%r, but expect to be %r\n' % (response.json()['result']['ecc_map'], expected_ecc_map))
            if mistakes > accepted_mistakes:
                warn('currently see %d mistakes\n' % mistakes)
                count += 1
                time.sleep(delay)
                continue
            break
        return True

    count = 0
    for observer_id in observers_ids:
        observer_node = observer_id.split('@')[0]
        if _validate(observer_node):
            dbg(
                'customer family [%s] [%s] info is correct for observer [%s] count=%d\n' % (
                    customer_node,
                    expected_ecc_map,
                    observer_node,
                    count,
                )
            )
            return True
        count += 1

    assert False, 'customer family [%s] [%s] was not re-published correctly, %d observers still see a wrong info' % (
        customer_node,
        expected_ecc_map,
        count,
    )


def supplier_switch_v1(customer: str, supplier_idurl: str, position: int, validate_retries=30, delay=3):
    response = request_put(
        customer,
        'supplier/switch/v1',
        json={
            'index': position,
            'new_idurl': supplier_idurl,
        },
        timeout=20,
    )
    assert response.status_code == 200
    dbg('supplier/switch/v1 [%s] with new supplier %s at position %r : %s\n' % (customer, supplier_idurl, position, pprint.pformat(response.json())))
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
            dbg('found supplier %r at position %d for customer %r' % (supplier_idurl, position, customer))
            return current_suppliers_idurls
        count += 1
        time.sleep(delay)
    assert False, 'failed to switch supplier at position %r to %r after %d retries' % (
        position,
        supplier_idurl,
        count,
    )
    return None


def share_create_v1(customer: str, key_size=1024, expected_reliable=100):
    response = request_post(
        customer,
        'share/create/v1',
        json={
            'key_size': key_size,
        },
        timeout=20,
    )
    assert response.status_code == 200
    dbg('share/create/v1 [%s] : %s\n' % (customer, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    packet_list_v1(customer, wait_all_finish=True)
    transfer_list_v1(customer, wait_all_finish=True)
    file_list_all_v1(customer, reliable_shares=False, expected_reliable=expected_reliable)
    return response.json()['result']['key_id']


def share_open_v1(customer: str, key_id):
    response = request_post(
        customer,
        'share/open/v1',
        json={
            'key_id': key_id,
        },
        timeout=60,
    )
    assert response.status_code == 200
    dbg('share/open/v1 [%s] key_id=%r : %s\n' % (customer, key_id, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    packet_list_v1(customer, wait_all_finish=True)
    transfer_list_v1(customer, wait_all_finish=True)
    return response.json()


def share_info_v1(node: str, key_id, wait_state=None, validate_retries=90, delay=2, stop_state=None, wait_suppliers=None):
    response = request_get(node, 'share/info/v1?key_id=%s' % key_id, timeout=20)
    assert response.status_code == 200
    dbg('share/info/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    if wait_state is None and wait_suppliers is None:
        return response.json()
    count = 0
    while True:
        if count >= validate_retries:
            dbg('share/info/v1 [%s] attempt %d : %s\n' % (node, count, pprint.pformat(response.json())))
            break
        response = request_get(node, 'share/info/v1?key_id=%s' % key_id, timeout=20)
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        # print('share/info/v1 [%s] attempt %d : %s\n' % (node, count, pprint.pformat(response.json())))
        dbg(
            '  share/info/v1 [%s] attempt %d : state=%s' % (
                node,
                count,
                response.json()['result']['state'],
            )
        )
        if wait_state is not None and wait_suppliers is None:
            if response.json()['result']['state'] == wait_state:
                dbg('share/info/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
                return response.json()
        if wait_suppliers is not None and wait_state is None:
            if len(response.json()['result']['suppliers']) == wait_suppliers:
                dbg('share/info/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
                return response.json()
        if wait_suppliers is not None and wait_state is not None:
            if len(response.json()['result']['suppliers']) == wait_suppliers:
                if response.json()['result']['state'] == wait_state:
                    dbg('share/info/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
                    return response.json()
        if stop_state and response.json()['result']['state'] == stop_state:
            dbg('share/info/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
            return response.json()
        count += 1
        time.sleep(delay)
    assert False, 'state:%s or suppliers:%s not detected for %r after %d retries' % (
        wait_state,
        wait_suppliers,
        key_id,
        count,
    )


def group_create_v1(customer: str, key_size=1024, label='', attempts=1):
    response = request_post(
        customer,
        'group/create/v1',
        json={
            'key_size': key_size,
            'label': label,
        },
        timeout=40,
        attempts=attempts,
    )
    assert response.status_code == 200
    dbg('group/create/v1 [%s] : %s\n' % (customer, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    packet_list_v1(customer, wait_all_finish=True)
    transfer_list_v1(customer, wait_all_finish=True)
    return response.json()['result']['group_key_id']


def group_info_v1(node: str, group_key_id, wait_state=None, validate_retries=90, delay=2, stop_state=None):
    response = request_get(node, 'group/info/v1?group_key_id=%s' % group_key_id, timeout=20)
    assert response.status_code == 200
    dbg('group/info/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    if wait_state is None:
        return response.json()
    count = 0
    while True:
        if count >= validate_retries:
            dbg('group/info/v1 [%s] attempt %d : %s\n' % (node, count, pprint.pformat(response.json())))
            break
        response = request_get(node, 'group/info/v1?group_key_id=%s' % group_key_id, timeout=20)
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        # print('group/info/v1 [%s] attempt %d : %s\n' % (node, count, pprint.pformat(response.json())))
        dbg(
            '  group/info/v1 [%s] attempt %d : state=%s' % (
                node,
                count,
                response.json()['result']['state'],
            )
        )
        if response.json()['result']['state'] == wait_state:
            dbg('group/info/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
            return response.json()
        if stop_state and response.json()['result']['state'] == stop_state:
            dbg('group/info/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
            return response.json()
        count += 1
        time.sleep(delay)
    assert False, 'state %r was not detected for %r after %d retries' % (
        wait_state,
        group_key_id,
        count,
    )


def group_info_dht_v1(node: str, customer_id, timeout=20, wait_records=None, retries=10, delay=3):
    response = request_get(node, 'group/info/dht/v1?group_creator_id=%s' % customer_id, timeout=timeout)
    assert response.status_code == 200
    dbg('group/info/dht/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    if wait_records is None:
        return response.json()
    count = 0
    while True:
        if len(response.json()['result']) == wait_records:
            dbg('group/info/dht/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
            return response.json()
        if count >= retries:
            dbg('group/info/dht/v1 [%s] attempt %d : %s\n' % (node, count, pprint.pformat(response.json())))
            break
        count += 1
        time.sleep(delay)
        dbg('retrying group/info/dht/v1?group_creator_id=%s' % customer_id)
        response = request_get(node, 'group/info/dht/v1?group_creator_id=%s' % customer_id, timeout=timeout)
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
    assert False, 'exactly %d dht records not detected for %r after %d retries' % (
        wait_records,
        customer_id,
        count,
    )


def group_join_v1(customer: str, group_key_id, attempts=1, timeout=120):
    response = request_post(
        customer,
        'group/join/v1',
        json={
            'group_key_id': group_key_id,
        },
        timeout=timeout,
        attempts=attempts,
    )
    assert response.status_code == 200
    dbg('group/join/v1 [%s] group_key_id=%r : %s\n' % (customer, group_key_id, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    packet_list_v1(customer, wait_all_finish=True)
    transfer_list_v1(customer, wait_all_finish=True)
    return response.json()


def group_leave_v1(customer: str, group_key_id, attempts=1):
    response = request_delete(
        customer,
        'group/leave/v1',
        json={
            'group_key_id': group_key_id,
        },
        timeout=20,
        attempts=attempts,
    )
    assert response.status_code == 200
    dbg('group/leave/v1 [%s] group_key_id=%r : %s\n' % (customer, group_key_id, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def group_reconnect_v1(customer: str, group_key_id, timeout=120):
    response = request_put(
        customer,
        'group/reconnect/v1',
        json={
            'group_key_id': group_key_id,
        },
        timeout=timeout,
    )
    assert response.status_code == 200
    dbg('group/reconnect/v1 [%s] group_key_id=%r : %s\n' % (customer, group_key_id, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    packet_list_v1(customer, wait_all_finish=True)
    transfer_list_v1(customer, wait_all_finish=True)
    return response.json()


def group_share_v1(customer: str, group_key_id, trusted_id, attempts=1, timeout=60):
    response = request_put(
        customer,
        'group/share/v1',
        json={
            'group_key_id': group_key_id,
            'trusted_id': trusted_id,
            'timeout': timeout,
        },
        timeout=timeout + 1,
        attempts=attempts,
    )
    assert response.status_code == 200
    dbg('group/share/v1 [%s] group_key_id=%r trusted_id=%r : %s\n' % (customer, group_key_id, trusted_id, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def file_sync_v1(node):
    response = request_get(node, 'file/sync/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'file/sync/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def file_list_all_v1(node, expected_reliable=100, reliable_shares=True, attempts=20, delay=5, verbose=False):
    if expected_reliable is None:
        response = request_get(node, 'file/list/all/v1', timeout=20)
        assert response.status_code == 200
        if verbose:
            dbg(
                'file/list/all/v1 [%s] : %s\n' % (
                    node,
                    pprint.pformat(response.json()),
                )
            )
        assert response.json()['status'] == 'OK', response.json()
        return response.json()

    response = None
    latest_reliable = None
    latest_reliable_fileinfo = None
    count = 0
    while latest_reliable is None or latest_reliable < expected_reliable:
        response = request_get(node, 'file/list/all/v1', timeout=20)
        assert response.status_code == 200
        if verbose:
            dbg(
                'file/list/all/v1 [%s] : %s\n' % (
                    node,
                    pprint.pformat(response.json()),
                )
            )
        assert response.json()['status'] == 'OK', response.json()
        lowest = 100
        lowest_file = None
        for fil in response.json()['result']:
            if fil['remote_path'].startswith('share_') and not reliable_shares:
                continue
            for ver in fil['versions']:
                reliable = int(ver['reliable'].replace('%', ''))
                if reliable < lowest:
                    lowest = reliable
                    lowest_file = fil
        latest_reliable = lowest
        latest_reliable_fileinfo = lowest_file
        if latest_reliable >= expected_reliable:
            break
        count += 1
        if count >= attempts:
            warn(f'    latest reliable item info: {pprint.pformat(latest_reliable_fileinfo)}')
            assert False, f'file {lowest_file} is not {expected_reliable} % reliable after {attempts} attempts'
            return
        time.sleep(delay)
    return response.json()


def file_create_v1(node, remote_path):
    response = request_post(node, 'file/create/v1', json={'remote_path': remote_path}, timeout=20)
    assert response.status_code == 200
    dbg(
        'file/create/v1 [%s] remote_path=%s : %s\n' % (
            node,
            remote_path,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def file_upload_start_v1(
    customer: str,
    remote_path: str,
    local_path: str,
    wait_result=True,
    wait_finish_attempts=20,
    delay=5,
    wait_job_finish=True,
    wait_packets_finish=True,
    wait_transfers_finish=True,
):
    response = request_post(
        customer,
        'file/upload/start/v1',
        json={
            'remote_path': remote_path,
            'local_path': local_path,
            'wait_result': '1' if wait_result else '0',
        },
        timeout=30,
    )
    assert response.status_code == 200
    dbg(
        'file/upload/start/v1 [%r] remote_path=%s local_path=%s : %s\n' % (
            customer,
            remote_path,
            local_path,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    if wait_job_finish:
        for _ in range(wait_finish_attempts):
            response = request_get(customer, 'file/upload/v1', timeout=20)
            assert response.status_code == 200
            dbg(
                'file/upload/v1 [%s] : %s\n' % (
                    customer,
                    pprint.pformat(response.json()),
                )
            )
            assert response.json()['status'] == 'OK', response.json()
            if len(response.json()['result']['pending']) == 0 and len(response.json()['result']['running']) == 0:
                break
            time.sleep(delay)
        else:
            assert False, 'some uploading tasks are still running on [%s]' % customer
    if wait_packets_finish:
        packet_list_v1(customer, wait_all_finish=True)
    if wait_transfers_finish:
        transfer_list_v1(customer, wait_all_finish=True)
    return response.json()


def file_download_start_v1(
    customer: str, remote_path: str, destination: str, wait_result=True, download_attempts=1, wait_finish_attempts=20, delay=5, wait_tasks_finish=True
):
    for _ in range(download_attempts):
        response = request_post(
            customer,
            'file/download/start/v1',
            json={
                'remote_path': remote_path,
                'destination_folder': destination,
                'wait_result': '1' if wait_result else '0',
            },
            timeout=30,
        )
        assert response.status_code == 200
        dbg(
            'file/download/start/v1 [%s] remote_path=%s destination_folder=%s : %s\n' % (
                customer,
                remote_path,
                destination,
                pprint.pformat(response.json()),
            )
        )
        if response.json()['status'] == 'OK':
            # print('file/download/start/v1 [%s] remote_path=%s destination_folder=%s : %s\n' % (
            #     customer, remote_path, destination, pprint.pformat(response.json()), ))
            break
        if response.json()['errors'][0].count('downloading') and response.json()['errors'][0].count('already scheduled'):
            # print('file/download/start/v1 [%s] remote_path=%s destination_folder=%s : %s\n' % (
            #     customer, remote_path, destination, 'ALREADY STARTED', ))
            break
        if (response.json()['errors'][0].count('failed') and
            response.json()['errors'][0].count('downloading')) or (response.json()['errors'][0].count('was not found in the catalog')):
            time.sleep(delay)
        else:
            assert False, response.json()
    else:
        assert False, 'failed to start downloading uploaded file on [%r]: %r' % (
            customer,
            response.json(),
        )
    if wait_tasks_finish:
        for _ in range(wait_finish_attempts):
            response = request_get(customer, 'file/download/v1', timeout=20)
            assert response.status_code == 200
            dbg(
                'file/download/v1 [%s] : %s\n' % (
                    customer,
                    pprint.pformat(response.json()),
                )
            )
            assert response.json()['status'] == 'OK', response.json()
            if len(response.json()['result']) == 0:
                break
            time.sleep(delay)
        else:
            assert False, 'some downloading tasks are still running on [%s]' % customer
    return response.json()


def config_set_v1(node, key, value):
    response = request_post(
        node,
        'config/set/v1',
        json={
            'key': key,
            'value': value,
        },
        timeout=20,
    )
    assert response.status_code == 200
    dbg('config/set/v1 [%s] key=%r value=%r : %s\n' % (node, key, value, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def dht_value_get_v1(node, key, expected_data, record_type='skip_validation', retries=2, fallback_observer=None):
    response = None
    for i in range(retries + 1):
        if i == retries - 1 and fallback_observer:
            node = fallback_observer
        response = request_get(
            node,
            'dht/value/get/v1?record_type=%s&key=%s' % (
                record_type,
                key,
            ),
            timeout=20,
        )
        try:
            assert response.status_code == 200
            dbg(
                'dht/value/get/v1 [%s] : %s\n' % (
                    node,
                    pprint.pformat(response.json()),
                )
            )
            assert response.json()['status'] == 'OK', response.json()
            assert len(response.json()['result']) > 0, response.json()
            assert response.json()['result']['key'] == key, response.json()
            if expected_data == 'not_exist':
                assert response.json()['result']['read'] == 'failed', response.json()
                assert 'value' not in response.json()['result'], response.json()
                assert len(response.json()['result']['closest_nodes']) > 0, response.json()
            else:
                if response.json()['result']['read'] == 'failed':
                    warn('first request failed, retry one more time')
                    response = request_get(
                        node,
                        'dht/value/get/v1?record_type=%s&key=%s' % (
                            record_type,
                            key,
                        ),
                        timeout=20,
                    )
                    assert response.status_code == 200
                    assert response.json()['status'] == 'OK', response.json()
                assert response.json()['result']['read'] == 'success', response.json()
                assert 'value' in response.json()['result'], response.json()
                assert response.json()['result']['value']['data'] in expected_data, response.json()
                assert response.json()['result']['value']['key'] == key, response.json()
                assert response.json()['result']['value']['type'] == record_type, response.json()
        except:
            time.sleep(2)
            if i == retries - 1:
                assert False, f'DHT value read validation failed: {node} {key} {expected_data} : {response.json()}'
    return response.json()


def dht_value_set_v1(
    node,
    key,
    new_data,
    record_type='skip_validation',
):
    response = request_post(
        node,
        'dht/value/set/v1',
        json={
            'key': key,
            'record_type': record_type,
            'value': {
                'data': new_data,
                'type': record_type,
                'key': key,
            },
        },
        timeout=20,
    )
    assert response.status_code == 200
    dbg(
        'dht/value/set/v1 [%s] key=%s : %s\n' % (
            node,
            key,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    assert len(response.json()['result']) > 0, response.json()
    assert response.json()['result']['write'] == 'success', response.json()
    assert response.json()['result']['key'] == key, response.json()
    assert response.json()['result']['value']['data'] == new_data, response.json()
    assert response.json()['result']['value']['key'] == key, response.json()
    assert response.json()['result']['value']['type'] == record_type, response.json()
    assert len(response.json()['result']['closest_nodes']) > 0, response.json()
    return response.json()


def dht_db_dump_v1(node):
    try:
        response = request_get(node, 'dht/db/dump/v1', timeout=20)
    except:
        return None
    dbg(
        'dht/db/dump/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    return response.json()


def message_send_v1(node, recipient, data, timeout=30, expect_consumed=True):
    response = request_post(
        node,
        'message/send/v1',
        json={
            'id': recipient,
            'data': data,
            'timeout': timeout,
        },
        timeout=timeout + 1,
    )
    assert response.status_code == 200
    dbg(f'message/send/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    if expect_consumed is not None:
        assert response.json()['result']['consumed'] is expect_consumed
    return response.json()


def message_send_group_v1(node, group_key_id, data, timeout=120):
    dbg(
        'message/send/group/v1 [%s] group_key_id=%r data=%r' % (
            node,
            group_key_id,
            data,
        )
    )
    response = request_post(
        node,
        'message/send/group/v1',
        json={
            'group_key_id': group_key_id,
            'data': data,
        },
        timeout=timeout,
    )
    assert response.status_code == 200
    dbg(f'message/send/group/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def message_receive_v1(node, expected_data=None, consumer='test_consumer', get_result=None, timeout=15, polling_timeout=10, attempts=1):
    response = request_get(node, f'message/receive/{consumer}/v1?polling_timeout=%d' % polling_timeout, timeout=timeout, attempts=attempts)
    assert response.status_code == 200
    dbg(f'message/receive/{consumer}/v1 [%s] : %s\n' % (node, pprint.pformat(response.json())))
    if get_result is not None:
        if response.json()['status'] == 'OK':
            get_result[0] = response.json()
        return get_result
    assert response.json()['status'] == 'OK', response.json()
    if expected_data is not None:
        received_result = response.json()['result']
        received_data = {} if not received_result else received_result[0]['data']
        received_data.pop('action', None)
        received_data.pop('msg_type', None)
        assert received_data == expected_data, response.json()
    return response.json()


def message_history_v1(node, recipient_id, message_type='private_message', timeout=15):
    response = request_get(node, f'message/history/v1?id={recipient_id}&message_type={message_type}', timeout=timeout)
    assert response.status_code == 200
    dbg(
        'message/history/v1 [%s] recipient_id=%s : %s\n' % (
            node,
            recipient_id,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def message_conversation_v1(node, message_types='private_message,group_message', timeout=15):
    response = request_get(node, f'message/conversation/v1?message_types={message_types}', timeout=timeout)
    assert response.status_code == 200
    dbg(
        'message/conversation/v1 [%s] message_types=%s : %s\n' % (
            node,
            message_types,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def user_ping_v1(node, remote_node_id, timeout=95, ack_timeout=30, retries=2):
    err = None
    try:
        response = request_get(node, f'user/ping/v1?id={remote_node_id}&timeout={ack_timeout}&retries={retries}', timeout=timeout)
    except Exception as exc:
        err = exc
        response = None
    if not response:
        assert False, f'ping {remote_node_id} failed : {err}'
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def service_info_v1(node, service_name, expected_state, attempts=90, delay=2, verbose=True):
    current_state = None
    count = 0
    while current_state is None or current_state != expected_state:
        response = request_get(node, f'service/info/{service_name}/v1', timeout=20, verbose=verbose)
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        current_state = response.json()['result']['state']
        if current_state == expected_state:
            if verbose:
                dbg(f'service/info/{service_name}/v1 [{node}] : %s' % pprint.pformat(response.json()))
            break
        if verbose:
            dbg(f'  service/info/{service_name}/v1 [{node}] : %s' % current_state)
        count += 1
        if count >= attempts:
            assert False, f'service {service_name} is not {expected_state} after {attempts} attempts'
            return
        time.sleep(delay)
    if verbose:
        dbg(f'service/info/{service_name}/v1 [{node}] : OK\n')


def service_start_v1(node, service_name, timeout=10):
    response = request_post(node, f'service/start/{service_name}/v1', json={}, timeout=timeout)
    assert response.status_code == 200
    dbg(
        'service/start/%s/v1 [%s]: %s\n' % (
            service_name,
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def service_stop_v1(node, service_name, timeout=10):
    response = request_post(node, f'service/stop/{service_name}/v1', json={}, timeout=timeout)
    assert response.status_code == 200
    dbg(
        'service/stop/%s/v1 [%s]: %s\n' % (
            service_name,
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def service_health_v1(node, service_name, timeout=30):
    response = request_get(node, f'service/health/{service_name}/v1', timeout=timeout)
    assert response.status_code == 200
    dbg(
        'service/health/%s/v1 [%s]: %s\n' % (
            service_name,
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def event_listen_v1(
    node,
    expected_event_id,
    consumer_id='regression_tests_wait_event',
    attempts=3,
    timeout=10,
):
    found = None
    count = 0
    while not found:
        response = request_get(node, f'event/listen/{consumer_id}/v1', timeout=timeout)
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        dbg(f'event/listen/{consumer_id}/v1 : %s\n' % pprint.pformat(response.json()))
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


def packet_list_v1(node, wait_all_finish=False, attempts=90, delay=2, verbose=False):
    if verbose:
        dbg('packet/list/v1 [%s]\n' % node)
    response = None
    for _ in range(attempts):
        response = request_get(node, 'packet/list/v1', timeout=20, verbose=verbose)
        assert response.status_code == 200
        if verbose:
            dbg(
                'packet/list/v1 [%s] : %s\n' % (
                    node,
                    pprint.pformat(response.json()),
                )
            )
        assert response.json()['status'] == 'OK', response.json()
        found_packet = False
        for r in response.json()['result']:
            if r.get('packet_id', '').count('idle_ping:'):
                continue
            # if r.get('command') == 'CancelService' and r.get('direction') == 'outgoing':
            #     continue
            if r.get('command') == 'Retrieve' and r.get('direction') == 'outgoing' and r.get('label', '').count('-rotated'):
                continue
            if r.get('command') == 'Data' and r.get('direction') == 'outgoing' and r.get('label', '').count('-rotated'):
                continue
            if r.get('command') == 'Identity' and r.get('direction') == 'outgoing' and r.get('label', '').count('-rotated'):
                continue
            found_packet = True
        if not found_packet or not wait_all_finish:
            break
        time.sleep(delay)
    else:
        warn(
            'packet/list/v1 [%s] : %s\n' % (
                node,
                pprint.pformat(response.json()),
            )
        )
        assert False, 'some packets are still have in/out progress on [%s]' % node
    return response.json()


def transfer_list_v1(node, wait_all_finish=False, attempts=90, delay=2, verbose=False):
    if verbose:
        dbg('transfer/list/v1 [%s]\n' % node)
    for _ in range(attempts):
        response = request_get(node, 'transfer/list/v1', timeout=20, verbose=verbose)
        assert response.status_code == 200
        if verbose:
            dbg(
                'transfer/list/v1 [%s] : %s\n' % (
                    node,
                    pprint.pformat(response.json()),
                )
            )
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
    response = request_get(node, 'identity/get/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'identity/get/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def identity_rotate_v1(node):
    response = request_put(node, 'identity/rotate/v1', timeout=30)
    assert response.status_code == 200
    dbg(
        'identity/rotate/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def network_reconnect_v1(node):
    response = request_get(node, 'network/reconnect/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'network/reconnect/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def network_info_v1(node):
    response = request_get(node, 'network/info/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'network/info/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def key_list_v1(node):
    response = request_get(node, 'key/list/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'key/list/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def automat_list_v1(node):
    response = request_get(node, 'automat/list/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'automat/list/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def automat_info_v1(node, automat_index, expected_state=None):
    response = request_get(node, 'automat/info/v1?index=%d' % int(automat_index), timeout=20)
    assert response.status_code == 200
    dbg(
        'automat/info/v1?index=%d [%s] : %s\n' % (
            int(automat_index),
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    if expected_state is not None:
        assert response.json()['result']['state'] == expected_state, response.json()
    return response.json()


def friend_add_v1(node, friend_idurl, friend_alias=''):
    response = request_post(
        node,
        'friend/add/v1',
        json={
            'idurl': friend_idurl,
            'alias': friend_alias,
        },
        timeout=20,
    )
    assert response.status_code == 200
    dbg(
        'friend/add/v1 [%s] idurl=%r alias=%r : %s\n' % (
            node,
            friend_idurl,
            friend_alias,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    return response.json()


def friend_list_v1(node, extract_idurls=False):
    response = request_get(node, 'friend/list/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'friend/list/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    if not extract_idurls:
        return response.json()
    return [f['idurl'] for f in response.json()['result']]


def queue_list_v1(node, extract_ids=False):
    response = request_get(node, 'queue/list/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'queue/list/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    if not extract_ids:
        return response.json()
    return [f['queue_id'] for f in response.json()['result']]


def queue_consumer_list_v1(node, extract_ids=False):
    response = request_get(node, 'queue/consumer/list/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'queue/consumer/list/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    if not extract_ids:
        return response.json()
    return [f['consumer_id'] for f in response.json()['result']]


def queue_producer_list_v1(node, extract_ids=False):
    response = request_get(node, 'queue/producer/list/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'queue/producer/list/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    if not extract_ids:
        return response.json()
    return [f['producer_id'] for f in response.json()['result']]


def queue_keeper_list_v1(node, extract_ids=False):
    response = request_get(node, 'queue/keeper/list/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'queue/keeper/list/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    if not extract_ids:
        return response.json()
    return [f['customer_id'] for f in response.json()['result']]


def queue_peddler_list_v1(node, extract_ids=False):
    response = request_get(node, 'queue/peddler/list/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'queue/peddler/list/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    if not extract_ids:
        return response.json()
    return [f['queue_id'] for f in response.json()['result']]


def queue_stream_list_v1(node, extract_ids=False):
    response = request_get(node, 'queue/stream/list/v1', timeout=20)
    assert response.status_code == 200
    dbg(
        'queue/stream/list/v1 [%s] : %s\n' % (
            node,
            pprint.pformat(response.json()),
        )
    )
    assert response.json()['status'] == 'OK', response.json()
    if not extract_ids:
        return response.json()
    return [f['queue_id'] for f in response.json()['result']]

#------------------------------------------------------------------------------


def wait_packets_finished(nodes, verbose=False):
    dbg('wait %d nodes to stop sending packets' % len(nodes))
    for node in nodes:
        packet_list_v1(node, wait_all_finish=True, verbose=verbose)
    dbg('')


def wait_service_state(nodes, service_name, state, verbose=False):
    dbg(
        'wait service %r state to become %r on %d nodes' % (
            service_name,
            state,
            len(nodes),
        )
    )
    for node in nodes:
        service_info_v1(node, service_name, state, verbose=verbose)
    dbg('')


def wait_suppliers_connected(nodes, expected_min_suppliers=2, expected_max_suppliers=2, verbose=False):
    dbg(
        'wait min %d and max %d suppliers to be connected on %d nodes' % (
            expected_min_suppliers,
            expected_max_suppliers,
            len(nodes),
        )
    )
    for node in nodes:
        supplier_list_v1(node, expected_min_suppliers=expected_min_suppliers, expected_max_suppliers=expected_max_suppliers, verbose=verbose)
    dbg('')


def wait_event(nodes, event, expected_count=1, attempts=10, delay=5, verbose=False):
    dbg(
        'wait event "%s" to occur %d times on %d nodes' % (
            event,
            expected_count,
            len(nodes),
        )
    )
    for node in nodes:
        for _ in range(attempts):
            event_log = run_ssh_command_and_wait(node, 'cat /root/.bitdust/logs/event.log', verbose=verbose)[0].strip()
            if event_log.count(event) == expected_count:
                break
            time.sleep(delay)
        else:
            assert False, f'event "{event}" did not occurred {expected_count} times on [{node}] after many attempts'
    dbg('')


def wait_specific_event(nodes, event, match_regex, expected_count=1, attempts=20, delay=5, verbose=False):
    dbg(
        'wait event "%s" with "%s" to occur %d times on %d nodes' % (
            event,
            match_regex,
            expected_count,
            len(nodes),
        )
    )
    for node in nodes:
        for _ in range(attempts):
            event_log = run_ssh_command_and_wait(node, 'cat /root/.bitdust/logs/event.log', verbose=verbose)[0].strip()
            captured = False
            for ln in event_log.split('\n'):
                if ln.count(event):
                    if re.match(match_regex, ln):
                        captured = True
                        break
            if captured:
                break
            time.sleep(delay)
        else:
            assert False, f'event "{event}" did not occurred {expected_count} times on [{node}] after many attempts'
    dbg('')


#------------------------------------------------------------------------------


def verify_message_sent_received(
    group_key_id, producer_id, consumers_ids, message_label='A', expected_results={}, expected_last_sequence_id={}, receive_timeout=31, polling_timeout=30
):
    sample_message = {
        'random_message': 'MESSAGE_%s_%s' % (
            message_label,
            base64.b32encode(os.urandom(8)).decode(),
        ),
    }
    consumer_results = {}
    consumer_threads = {}

    for consumer_id in consumers_ids:
        consumer_results[consumer_id] = [
            None,
        ]
        consumer_threads[consumer_id] = threading.Timer(
            0,
            message_receive_v1,
            [
                consumer_id,
                sample_message,
                'test_consumer',
                consumer_results[consumer_id],
                receive_timeout,
                polling_timeout,
            ],
        )

    producer_thread = threading.Timer(
        0.2,
        message_send_group_v1,
        [
            producer_id,
            group_key_id,
            sample_message,
        ],
    )

    for consumer_id in consumers_ids:
        consumer_threads[consumer_id].start()

    producer_thread.start()

    for consumer_id in consumers_ids:
        consumer_threads[consumer_id].join()

    producer_thread.join()

    if expected_results:
        for consumer_id, expected_result in expected_results.items():
            if expected_result:
                if not consumer_results[consumer_id][0] or not consumer_results[consumer_id][0]['result']:
                    assert False, 'consumer %r did not received expected message %r' % (consumer_id, sample_message)
                if consumer_results[consumer_id][0]['result'][0]['data'] != sample_message:
                    assert False, 'consumer %r received message %r, but expected is %r' % (
                        consumer_id, consumer_results[consumer_id][0]['result'][0]['data'], sample_message
                    )
            else:
                assert consumer_results[consumer_id][0][
                    'result'] == [], 'consumer %r received message while should not: %r' % (consumer_id, consumer_results[consumer_id])
            if consumer_id in expected_last_sequence_id:
                consumer_last_sequence_id = group_info_v1(consumer_id, group_key_id)['result']['last_sequence_id']
                assert consumer_last_sequence_id == expected_last_sequence_id[consumer_id], \
                    'consumer %r last_sequence_id is %r but expected is %r' % (
                        consumer_id, consumer_last_sequence_id, expected_last_sequence_id[consumer_id],
                    )

    return sample_message


#------------------------------------------------------------------------------


def verify_file_create_upload_start(
    node, key_id, volume_path, filename='cat.txt', randomize_bytes=0, verify_list_files=True, reliable_shares=True, expected_reliable=100
):
    virtual_filename = filename
    local_filepath = f'{volume_path}/{filename}'
    remote_path = f'{key_id}:{virtual_filename}'
    download_filepath = f'/tmp/{filename}'
    if randomize_bytes == 0:
        run_ssh_command_and_wait(node, f'echo "{node}" > {local_filepath}')
    else:
        run_ssh_command_and_wait(
            node, f'python -c "import os, base64; print(base64.b64encode(os.urandom({randomize_bytes})).decode()[:{randomize_bytes}])" > {local_filepath}'
        )
    if verify_list_files:
        file_list_all_v1(node, reliable_shares=reliable_shares, expected_reliable=expected_reliable)
    file_create_v1(node, remote_path)
    file_upload_start_v1(node, remote_path, local_filepath)
    if verify_list_files:
        file_list_all_v1(node, reliable_shares=reliable_shares, expected_reliable=expected_reliable)
    packet_list_v1(node, wait_all_finish=True)
    transfer_list_v1(node, wait_all_finish=True)
    return local_filepath, remote_path, download_filepath


def verify_file_download_start(
    node, remote_path, destination_path, verify_from_local_path=None, verify_list_files=True, reliable_shares=True, expected_reliable=100, download_attempts=1
):
    if verify_list_files:
        file_list_all_v1(node, reliable_shares=reliable_shares, expected_reliable=expected_reliable)
    file_download_start_v1(node, remote_path=remote_path, destination=os.path.dirname(destination_path), download_attempts=download_attempts)
    if verify_from_local_path is not None:
        file_body_source = run_ssh_command_and_wait(node, f'cat {verify_from_local_path}')[0].strip()
        file_body_downloaded = run_ssh_command_and_wait(node, f'cat {destination_path}')[0].strip()
        assert file_body_source == file_body_downloaded
    if verify_list_files:
        file_list_all_v1(node, reliable_shares=reliable_shares, expected_reliable=expected_reliable)
