#!/usr/bin/env python
# test_identity.py
#
# Copyright (C) 2008 Stanislav Evseev, Veselin Penev  https://bitdust.io
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

from testsupport import run_ssh_command_and_wait, request_get, request_post

from keywords import service_info_v1, file_create_v1, file_upload_start_v1, file_download_start_v1, \
    supplier_list_v1, transfer_list_v1, packet_list_v1, file_list_all_v1, supplier_list_dht_v1


def test_identity_recover_from_customer_backup_to_customer_restore():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    # step1: first upload/download one file on customer_backup
    key_id = 'master$customer-backup@id-a_8084'
    source_volume = '/customer_backup'
    origin_filename = 'file_customer_backup.txt'
    source_local_path = '%s/%s' % (source_volume, origin_filename)
    virtual_file = 'virtual_file.txt'
    remote_path = '%s:%s' % (key_id, virtual_file)
    download_volume = '/customer_backup'
    downloaded_file = '%s/%s' % (download_volume, virtual_file)

    supplier_list_v1('customer-backup', expected_min_suppliers=2, expected_max_suppliers=2)

    service_info_v1('customer-backup', 'service_shared_data', 'ON')

    supplier_list_dht_v1(
        customer_id='customer-backup@id-a_8084',
        observers_ids=['customer-backup@id-a_8084', 'supplier-1@id-a_8084', 'supplier-2@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    supplier_list_dht_v1(
        customer_id='customer-backup@id-a_8084',
        observers_ids=['supplier-1@id-a_8084', 'supplier-2@id-a_8084', 'customer-backup@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    supplier_list_dht_v1(
        customer_id='customer-backup@id-a_8084',
        observers_ids=['supplier-2@id-a_8084', 'customer-backup@id-a_8084', 'supplier-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    file_create_v1('customer-backup', remote_path)

    run_ssh_command_and_wait('customer-backup', f'python -c "import os, base64; print(base64.b64encode(os.urandom(30000)).decode())" > /customer_backup/{origin_filename}')

    file_upload_start_v1('customer-backup', remote_path, source_local_path)

    service_info_v1('customer-backup', 'service_shared_data', 'ON')
    
    file_download_start_v1('customer-backup', remote_path, download_volume, open_share=False)

    source_local_file_src = run_ssh_command_and_wait('customer-backup', 'cat %s' % source_local_path)[0].strip()
    print('customer-backup: file %s is %d bytes long' % (source_local_path, len(source_local_file_src)))
    
    downloaded_file_src = run_ssh_command_and_wait('customer-backup', 'cat %s' % downloaded_file)[0].strip()
    print('customer-backup: file %s is %d bytes long' % (downloaded_file, len(downloaded_file_src)))

    assert source_local_file_src == downloaded_file_src, (source_local_file_src, downloaded_file_src, )

    # step2: backup customer-backup private key and stop that container
    backup_file_directory_c2 = '/customer_backup/identity.backup'
    backup_file_directory_c3 = '/customer_restore/identity.backup'
    assert not os.path.exists(backup_file_directory_c2)

    response = request_post('customer-backup', 'identity/backup/v1',
        json={
            'destination_path': backup_file_directory_c2,
        },
    )
    print('\n\nidentity/backup/v1 : %s\n' % response.json())
    assert response.json()['status'] == 'OK', response.json()

    # copy private key from one container to another
    # just like when you backup your private key and restore it from USB stick on another device
    shutil.move(backup_file_directory_c2, backup_file_directory_c3)

    # to make sure all uploads to finish
    transfer_list_v1('customer-backup', wait_all_finish=True)
    packet_list_v1('customer-backup', wait_all_finish=True)
    file_list_all_v1('customer-backup')

    supplier_list_dht_v1(
        customer_id='customer-backup@id-a_8084',
        observers_ids=['customer-backup@id-a_8084', 'supplier-1@id-a_8084', 'supplier-2@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    supplier_list_dht_v1(
        customer_id='customer-backup@id-a_8084',
        observers_ids=['supplier-1@id-a_8084', 'supplier-2@id-a_8084', 'customer-backup@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    supplier_list_dht_v1(
        customer_id='customer-backup@id-a_8084',
        observers_ids=['supplier-2@id-a_8084', 'customer-backup@id-a_8084', 'supplier-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    try:
        response = request_get('customer-backup', 'process/stop/v1')
        assert response.json()['status'] == 'OK', response.json()
    except Exception as exc:
        print(f'\n\nprocess/stop/v1 failed with {exc}')

    # step3: recover key on customer-restore container and join network
    for _ in range(5):
        response = request_post('customer-restore', 'identity/recover/v1',
            json={
                'private_key_local_file': backup_file_directory_c3,
            },
        )
        print('\n\nidentity/recover/v1 : %s\n' % response.json())
        if response.json()['status'] == 'OK':
            break
        time.sleep(1)
    else:
        assert False, 'customer-restore was not able to recover identity after few seconds'

    response = request_get('customer-restore', 'network/connected/v1?wait_timeout=1')
    assert response.json()['status'] == 'ERROR'

    for _ in range(5):
        response = request_get('customer-restore', 'network/connected/v1?wait_timeout=5')
        if response.json()['status'] == 'OK':
            break
        time.sleep(5)
    else:
        assert False, 'customer-restore was not able to join the network after identity recover'

    supplier_list_v1('customer-restore', expected_min_suppliers=2, expected_max_suppliers=2)

    service_info_v1('customer-restore', 'service_shared_data', 'ON')

    supplier_list_dht_v1(
        customer_id='customer-backup@id-a_8084',
        observers_ids=['customer-restore@id-a_8084', 'supplier-3@id-a_8084', 'supplier-1@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    supplier_list_dht_v1(
        customer_id='customer-backup@id-a_8084',
        observers_ids=['supplier-3@id-a_8084', 'supplier-1@id-a_8084', 'customer-restore@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    supplier_list_dht_v1(
        customer_id='customer-backup@id-a_8084',
        observers_ids=['supplier-1@id-a_8084', 'customer-restore@id-a_8084', 'supplier-3@id-a_8084', ],
        expected_ecc_map='ecc/2x2',
        expected_suppliers_number=2,
    )

    file_list_all_v1('customer-restore')

    # step4: try to recover stored file again
    key_id = 'master$customer-backup@id-a_8084'
    recover_volume = '/customer_restore'
    virtual_file = 'virtual_file.txt'
    remote_path = '%s:%s' % (key_id, virtual_file)
    recovered_file = '%s/%s' % (recover_volume, virtual_file)
    for _ in range(20):
        response = request_post('customer-restore', 'file/download/start/v1',
            json={
                'remote_path': remote_path,
                'destination_folder': recover_volume,
                'wait_result': '1',
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
        assert False, 'download was not successful: %r' % response.json()

    recovered_file_src = run_ssh_command_and_wait('customer-restore', 'cat %s' % recovered_file)[0].strip()
    print('customer-restore:%s' % recovered_file, recovered_file_src)
    assert source_local_file_src == recovered_file_src, (source_local_file_src, recovered_file_src, )

    # TODO:
    # test my keys also recovered
    # test my message history also recovered (not implemented yet)

