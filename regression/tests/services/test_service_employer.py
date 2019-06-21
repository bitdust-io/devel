#!/usr/bin/env python
# test_service_employer.py
#
# Copyright (C) 2008-2019 Veselin Penev, Stanislav Evseev  https://bitdust.io
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
import time
import requests

from ..testsupport import tunnel_url, run_ssh_command_and_wait
from ..keywords import supplier_list_v1, share_create_v1, file_upload_start_v1, file_download_start_v1, \
    service_info_v1, file_create_v1, transfer_list_v1, packet_list_v1


def idurl_to_name(idurl: str) -> str:
    return idurl.rsplit('/', 1)[1].replace('.xml', '')


def test_customer_1_replace_supplier_at_position_0():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    supplier_list_v1('customer_1', expected_min_suppliers=2, expected_max_suppliers=2)
    share_id_customer_1 = share_create_v1('customer_1')

    filename = 'file_to_be_distributed.txt'
    virtual_filename = filename

    volume_customer_1 = '/customer_1'
    filepath_customer_1 = f'{volume_customer_1}/{filename}'

    remote_path_customer_1 = f'{share_id_customer_1}:{virtual_filename}'

    run_ssh_command_and_wait('customer_1', f'echo customer_1 > {filepath_customer_1}')

    file_create_v1('customer_1', remote_path_customer_1)

    file_upload_start_v1('customer_1', remote_path_customer_1, filepath_customer_1)

    service_info_v1('customer_1', 'service_restores', 'ON')

    file_download_start_v1('customer_1', remote_path=remote_path_customer_1, destination=volume_customer_1)

    response = requests.get(tunnel_url('customer_1', '/supplier/list/v1'))
    assert response.status_code == 200
    supplier_list = response.json()['result']
    suppliers = set(x['idurl'] for x in supplier_list)
    assert len(suppliers) == 2

    response = requests.post(tunnel_url('customer_1', '/supplier/replace/v1'), json={'position': '0'})
    assert response.status_code == 200

    # wait for a while to redistribute files
    time.sleep(15)

    response = requests.get(tunnel_url('customer_1', '/supplier/list/v1'))
    assert response.status_code == 200
    new_supplier_list = response.json()['result']
    new_suppliers = set(x['idurl'] for x in new_supplier_list)
    assert len(suppliers) == 2

    assert new_suppliers != suppliers
    prev_supplier_idurl = suppliers.difference(new_suppliers).pop()
    prev_supplier = idurl_to_name(prev_supplier_idurl)

    space_donated_response = requests.get(tunnel_url(prev_supplier, '/space/donated/v1'))
    assert space_donated_response.status_code == 200

    space_donated_json = space_donated_response.json()['result'][0]
    old_customers = set(idurl_to_name(x['idurl']) for x in space_donated_json['old_customers'])
    assert 'customer_1' in old_customers

    run_ssh_command_and_wait('customer_1', f'mkdir {volume_customer_1}/tmp/')[0].strip()

    file_download_start_v1('customer_1', remote_path=remote_path_customer_1, destination=f'{volume_customer_1}/tmp/')

    file_content = run_ssh_command_and_wait('customer_1', f'cat {volume_customer_1}/tmp/file_to_be_distributed.txt')[0].strip()

    assert file_content == 'customer_1'
