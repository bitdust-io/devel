#!/usr/bin/env python
# test_identity_rotate_supplier.py
#
# Copyright (C) 2008-2019 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (test_identity_rotate_supplier.py) is part of BitDust Software.
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
import requests
import base64
import threading

from testsupport import tunnel_url, run_ssh_command_and_wait, create_identity, connect_network, stop_daemon

from keywords import service_info_v1, file_create_v1, file_upload_start_v1, file_download_start_v1, \
    supplier_list_v1, transfer_list_v1, packet_list_v1, file_list_all_v1, supplier_list_dht_v1, \
    user_ping_v1, identity_get_v1, identity_rotate_v1, key_list_v1, share_create_v1, share_open_v1, \
    supplier_switch_v1, file_sync_v1, friend_add_v1, friend_list_v1, message_send_v1, message_receive_v1, \
    config_set_v1, network_reconnect_v1


def test_identity_rotate_supplier_1():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    # first create supplier-1 identity and start the node, identity will be rotated later
    create_identity('supplier-1', 'supplier-1')

    connect_network('supplier-1')

    r = identity_get_v1('supplier-1')
    supplier_1_global_id = r['result'][0]['global_id']
    supplier_1_idurl = r['result'][0]['idurl']

    service_info_v1('supplier-1', 'service_supplier', 'ON')

    # make sure supplier-1 was hired by customer-1
    current_suppliers_idurls = supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    # if he is not hired yet, we switch our first supplier to supplier-1
    if supplier_1_idurl not in current_suppliers_idurls:
        supplier_switch_v1('customer-1', supplier_idurl=supplier_1_idurl, position=0)

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    current_suppliers_idurls = supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    assert supplier_1_idurl in current_suppliers_idurls

    share_id_customer_1 = share_create_v1('customer-1')

    filename = 'cat.txt'
    virtual_filename = filename
    volume_customer_1 = '/customer_1'
    filepath_customer_1 = f'{volume_customer_1}/{filename}'
    remote_path_customer_1 = f'{share_id_customer_1}:{virtual_filename}'
    download_filepath_customer_1 = f'/tmp/{filename}'
    run_ssh_command_and_wait('customer-1', f'echo "customer_1" > {filepath_customer_1}')

    file_create_v1('customer-1', remote_path_customer_1)

    file_upload_start_v1('customer-1', remote_path_customer_1, filepath_customer_1)

    packet_list_v1('customer-1', wait_all_finish=True)

    transfer_list_v1('customer-1', wait_all_finish=True)

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    file_download_start_v1('customer-1', remote_path=remote_path_customer_1, destination='/tmp')

    file_1 = run_ssh_command_and_wait('customer-1', f'cat {filepath_customer_1}')[0].strip()
    file_2 = run_ssh_command_and_wait('customer-1', f'cat {download_filepath_customer_1}')[0].strip()
    assert file_1 == file_2

    # rotate identity sources on supplier-1
    identity_rotate_v1('supplier-1')

    time.sleep(1)

    r = identity_get_v1('supplier-1')
    supplier_1_global_id_new = r['result'][0]['global_id']
    supplier_1_idurl_new = r['result'][0]['idurl']
    assert supplier_1_global_id_new != supplier_1_global_id
    assert supplier_1_idurl_new != supplier_1_idurl

    service_info_v1('supplier-1', 'service_supplier', 'ON')

    file_sync_v1('customer-1')

    time.sleep(1)

    packet_list_v1('customer-1', wait_all_finish=True)

    transfer_list_v1('customer-1', wait_all_finish=True)

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    file_list_all_v1('customer-1')

    # step3: recover key on customer_restore container and join network
    for i in range(10):
        new_suppliers_idurls = supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
        if supplier_1_idurl not in new_suppliers_idurls and supplier_1_idurl_new in new_suppliers_idurls:
            break
        time.sleep(1)
    else:
        assert False, 'customer-1 still see old idurl of supplier-1 in supplier/list/v1'

