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

from testsupport import tunnel_url, run_ssh_command_and_wait
from keywords import supplier_list_v1, share_create_v1, file_upload_start_v1, file_download_start_v1, \
    service_info_v1, file_create_v1, transfer_list_v1, packet_list_v1


def test_customer_1_replace_supplier_at_position_0():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    return True

    supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
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

    file_download_start_v1('customer-1', remote_path=remote_path_customer_1, destination=volume_customer_1)

    response = requests.get(tunnel_url('customer-1', '/supplier/list/v1'))
    assert response.status_code == 200
    supplier_list = response.json()['result']
    suppliers = set(x['idurl'] for x in supplier_list)
    assert len(suppliers) == 2

    response = requests.post(tunnel_url('customer-1', '/supplier/replace/v1'), json={'position': '0'})

    # TODO: ...
