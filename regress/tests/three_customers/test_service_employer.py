#!/usr/bin/env python
# test_service_employer.py
#
# Copyright (C) 2008 Veselin Penev, Stanislav Evseev  https://bitdust.io
#
# This file (test_service_employer.py) is part of BitDust Software.
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

from testsupport import request_get, request_post, request_put, run_ssh_command_and_wait
from keywords import supplier_list_v1, share_create_v1, file_upload_start_v1, file_download_start_v1, \
    service_info_v1, file_create_v1, supplier_list_dht_v1, packet_list_v1, transfer_list_v1


def test_customer_1_replace_supplier_at_position_0():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    packet_list_v1('customer-1', wait_all_finish=True)

    transfer_list_v1('customer-1', wait_all_finish=True)

    supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)

    supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=['customer-1@id-a_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=['customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=['supplier-2@id-a_8084', 'customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    share_id_customer_1 = share_create_v1('customer-1')

    filename = 'file_to_be_distributed.txt'
    virtual_filename = filename

    volume_customer_1 = '/customer_1'
    filepath_customer_1 = f'{volume_customer_1}/{filename}'

    remote_path_customer_1 = f'{share_id_customer_1}:{virtual_filename}'

    run_ssh_command_and_wait('customer-1', f'echo customer_1 > {filepath_customer_1}')

    file_create_v1('customer-1', remote_path_customer_1)

    file_upload_start_v1('customer-1', remote_path_customer_1, filepath_customer_1)

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    packet_list_v1('customer-1', wait_all_finish=True)

    transfer_list_v1('customer-1', wait_all_finish=True)

    file_download_start_v1('customer-1', remote_path=remote_path_customer_1, destination=volume_customer_1)

    response_before = request_get('customer-1', '/supplier/list/v1')
    assert response_before.status_code == 200
    supplier_list_before = response_before.json()['result']
    suppliers_before = list([x['global_id'] for x in supplier_list_before])
    assert len(suppliers_before) == 2

    response = request_post('customer-1', '/supplier/replace/v1', json={'position': '0'})
    assert response.status_code == 200

    supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=['customer-1@id-a_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=['customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )
    supplier_list_dht_v1(
        customer_id='customer-1@id-a_8084',
        observers_ids=['supplier-2@id-a_8084', 'customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    response_after = request_get('customer-1', '/supplier/list/v1')
    assert response_after.status_code == 200
    supplier_list_after = response_after.json()['result']
    suppliers_after = list([x['global_id'] for x in supplier_list_after])
    assert len(suppliers_after) == 2

    assert suppliers_after[0] != suppliers_before[0]
    assert suppliers_after[1] == suppliers_before[1]


def test_customer_2_switch_supplier_at_position_0():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    packet_list_v1('customer-2', wait_all_finish=True)

    transfer_list_v1('customer-2', wait_all_finish=True)

    supplier_list_v1('customer-2', expected_min_suppliers=4, expected_max_suppliers=4)

    response_before = request_get('customer-2', '/supplier/list/v1')
    assert response_before.status_code == 200
    supplier_list_before = response_before.json()['result']
    suppliers_before = list([x['global_id'] for x in supplier_list_before])
    assert len(suppliers_before) == 4

    possible_suppliers = set([
        'supplier-1@id-a_8084',
        'supplier-2@id-a_8084',
        'supplier-3@id-a_8084',
        'supplier-4@id-a_8084',
        'supplier-5@id-a_8084',
        'supplier-6@id-a_8084',
        'supplier-7@id-a_8084',
        'supplier-8@id-a_8084',
    ])
    possible_suppliers.difference_update(set(suppliers_before))
    new_supplier = list(possible_suppliers)[0]

    supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=[new_supplier, 'customer-2@id-a_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=['customer-2@id-a_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=['customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=['supplier-2@id-a_8084', 'customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )

    share_id_customer_2 = share_create_v1('customer-2')

    filename = 'file_to_be_distributed.txt'
    virtual_filename = filename

    volume_customer_2 = '/customer_2'
    filepath_customer_2 = f'{volume_customer_2}/{filename}'

    remote_path_customer_2 = f'{share_id_customer_2}:{virtual_filename}'

    run_ssh_command_and_wait('customer-2', f'echo customer_2 > {filepath_customer_2}')

    file_create_v1('customer-2', remote_path_customer_2)

    file_upload_start_v1('customer-2', remote_path_customer_2, filepath_customer_2)

    service_info_v1('customer-2', 'service_shared_data', 'ON')

    packet_list_v1('customer-2', wait_all_finish=True)

    transfer_list_v1('customer-2', wait_all_finish=True)

    file_download_start_v1('customer-2', remote_path=remote_path_customer_2, destination=volume_customer_2)

    response = request_put('customer-2', '/supplier/switch/v1', json={
        'position': '0',
        'new_global_id': new_supplier,
    })
    assert response.status_code == 200

    supplier_list_v1('customer-2', expected_min_suppliers=4, expected_max_suppliers=4)

    service_info_v1('customer-2', 'service_shared_data', 'ON')

    supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=[new_supplier, 'customer-2@id-a_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=['customer-2@id-a_8084', 'customer-3@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=['customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )
    supplier_list_dht_v1(
        customer_id='customer-2@id-a_8084',
        observers_ids=['supplier-2@id-a_8084', 'customer-3@id-a_8084', 'customer-1@id-a_8084', ],
        expected_ecc_map='ecc/4x4',
        expected_suppliers_number=4,
    )

    response_after = request_get('customer-2', '/supplier/list/v1')
    assert response_after.status_code == 200
    supplier_list_after = response_after.json()['result']
    suppliers_after = list([x['global_id'] for x in supplier_list_after])
    assert len(suppliers_after) == 4

    assert suppliers_after[0] == new_supplier
    assert suppliers_after[0] != suppliers_before[0]
    assert suppliers_after[1] == suppliers_before[1]
    assert suppliers_after[2] == suppliers_before[2]
    assert suppliers_after[3] == suppliers_before[3]
