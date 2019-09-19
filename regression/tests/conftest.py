#!/usr/bin/env python
# conftest.py
#
# Copyright (C) 2008-2019 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (conftest.py) is part of BitDust Software.
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
import asyncio
import pprint


from .testsupport import open_one_tunnel_async, clean_one_node_async, clean_one_customer_async, \
    start_dht_seed, start_identity_server_async, start_stun_server_async, start_one_proxy_server_async, \
    start_one_supplier_async, start_one_customer_async, stop_daemon_async, run_ssh_command_and_wait, \
    print_exceptions_one_node, report_one_node

#------------------------------------------------------------------------------

# DHT_SEED_NODES = 'dht_seed_0:14441, dht_seed_1:14441, dht_seed_2:14441, dht_seed_3:14441, dht_seed_4:14441, stun_1:14441, stun_2:14441'
DHT_SEED_NODES = 'dht_seed_0:14441'

OTHER_KNOWN_ID_SERVERS = [
    'is:8084:6661',
    'identity-server-a:8084:6661',
    'identity-server-b:8084:6661',
]

# TODO: keep this list up to date with docker-compose links
ALL_NODES = [
    'customer_1',
    'customer_2',
    'customer_3',
    'customer_4',
    'customer_5',
    'customer_6',
    'customer_backup',
    'customer_restore',
    'supplier_1',
    'supplier_2',
    'supplier_3',
    'supplier_4',
    'supplier_5',
    'supplier_6',
    'proxy_server_1',
    'proxy_server_2',
    'stun_1',
    'stun_2',
    'is',
    'identity-server-a',
    'identity-server-b',
    'dht_seed_0',
    'dht_seed_1',
    'dht_seed_2',
    'dht_seed_3',
    'dht_seed_4',
]

# TODO: keep this list up to date with docker-compose links
ALL_ROLES = {
    'dht-seeds': [
        {'name': 'dht_seed_0', 'other_seeds': 'genesis', },
        {'name': 'dht_seed_1', 'other_seeds': 'dht_seed_0:14441', },
        {'name': 'dht_seed_2', 'other_seeds': 'dht_seed_0:14441', },
        {'name': 'dht_seed_3', 'other_seeds': 'dht_seed_0:14441', },
        {'name': 'dht_seed_4', 'other_seeds': 'dht_seed_0:14441', },
    ],
    'identity-servers': [
        'is',
        'identity-server-a',
        'identity-server-b',
    ],
    'stun-servers': [
        'stun_1',
        'stun_2',
    ],
    'proxy-servers': [
        'proxy_server_1',
        'proxy_server_2',
    ],
    'suppliers': [
        {'name': 'supplier_1', 'preferred_routers': 'http://is:8084/proxy_server_1.xml', },
        {'name': 'supplier_2', 'preferred_routers': 'http://is:8084/proxy_server_2.xml', },
        {'name': 'supplier_3', },
        {'name': 'supplier_4', },
        {'name': 'supplier_5', },
        {'name': 'supplier_6', 'join_network': False,
         'known_servers': OTHER_KNOWN_ID_SERVERS, 'max_servers': 2, 'min_servers': 2, },
    ],
    'customers': [
        {'name': 'customer_1', 'join_network': True, 'num_suppliers': 2, 'block_size': '10 KB',
         'supplier_candidates': 'http://is:8084/supplier_1.xml,http://is:8084/supplier_2.xml',
         'preferred_routers': 'http://is:8084/proxy_server_1.xml', },
        {'name': 'customer_2', 'join_network': True, 'num_suppliers': 2, 
         'supplier_candidates': 'http://is:8084/supplier_3.xml,http://is:8084/supplier_4.xml', },
        {'name': 'customer_3', 'join_network': True, 'num_suppliers': 2, },
        {'name': 'customer_4', 'join_network': True, 'num_suppliers': 2,
         'supplier_candidates': 'http://is:8084/supplier_3.xml,http://is:8084/supplier_4.xml', },
        {'name': 'customer_5', 'join_network': True, 'num_suppliers': 4,
         'supplier_candidates': 'http://is:8084/supplier_2.xml,http://is:8084/supplier_3.xml,http://is:8084/supplier_4.xml,http://is:8084/supplier_5.xml', },
        {'name': 'customer_6', 'join_network': True, 'num_suppliers': 2,
         'known_servers': OTHER_KNOWN_ID_SERVERS, 'max_servers': 2, 'min_servers': 2, },
        {'name': 'customer_backup', 'join_network': True, 'num_suppliers': 2,
         'preferred_routers': 'http://is:8084/proxy_server_1.xml', },
        {'name': 'customer_restore', 'join_network': False, 'num_suppliers': 2,
         'preferred_routers': 'http://is:8084/proxy_server_2.xml', },
    ],
}


def open_all_tunnels(event_loop):
    _begin = time.time()
    print('\nStarting all SSH tunnels\n')
    event_loop.run_until_complete(asyncio.gather(*[
        open_one_tunnel_async(node, 10000+pos, event_loop) for pos, node in enumerate(ALL_NODES)
    ]))
    print('\nAll SSH tunnels opened in %5.3f seconds\n' % (time.time() - _begin))


def clean_all_nodes(event_loop, skip_checks=False):
    _begin = time.time()
    print('\nCleaning all nodes')
    event_loop.run_until_complete(asyncio.gather(*[
        clean_one_node_async(node, event_loop=event_loop) for node in ALL_NODES
    ]))
    event_loop.run_until_complete(asyncio.gather(*[
        clean_one_customer_async(node['name'], event_loop=event_loop) for node in ALL_ROLES['customers']
    ]))
    print('\n\nAll nodes cleaned in %5.3f seconds\n' % (time.time() - _begin))


def start_all_nodes(event_loop):
    _begin = time.time()
    print('\nStarting nodes\n')

    for number, dhtseed in enumerate(ALL_ROLES['dht-seeds']):
        # first seed to be started immediately, all other seeds must wait a bit before start
        start_dht_seed(
            node=dhtseed['name'],
            other_seeds=dhtseed['other_seeds'],
            wait_seconds=(15 if number > 0 else 0),
            # wait_seconds=5,
        )
    print('\nALL DHT SEEDS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_identity_server_async(idsrv, event_loop) for idsrv in ALL_ROLES['identity-servers']
    ]))
    print(f'\nALL ID SERVERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_stun_server_async(stunsrv, event_loop) for stunsrv in ALL_ROLES['stun-servers']
    ]))
    print(f'\nALL STUN SERVERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_one_proxy_server_async(proxy_server, event_loop) for proxy_server in ALL_ROLES['proxy-servers']
    ]))
    print(f'\nALL PROXY SERVERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_one_supplier_async(supplier, event_loop) for supplier in ALL_ROLES['suppliers']
    ]))
    print(f'\nALL SUPPLIERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_one_customer_async(customer, event_loop) for customer in ALL_ROLES['customers']
    ]))
    print(f'\nALL CUSTOMERS STARTED\n')

    print('\nDONE! ALL NODES STARTED in %5.3f seconds\n' % (time.time() - _begin))


def stop_all_nodes(event_loop):
    _begin = time.time()
    print('\nstop all nodes\n')
    event_loop.run_until_complete(asyncio.gather(*[
        stop_daemon_async(node, event_loop) for node in ALL_NODES
    ]))
    print('\nALL NODES STOPPED in %5.3f seconds\n' % (time.time() - _begin))


def kill_all_nodes():
    for node in ALL_NODES:
        print('Shutdown %s' % node)
        run_ssh_command_and_wait(node, 'pkill -e sshd')
    print('All nodes stopped')


def report_all_nodes(event_loop):
    print('\n\nSTDOUT:')
    # for node in ['customer_restore', ]:
    #     print('\n\nSTDOUT on [%s]:' % node)
    #     ts.print_stdout_one_node(node)

    # print('\n\nDHT records:')
    # for node in ALL_NODES:
    #     print('\n\nDHT records on [%s]:' % node)
    #     keywords.dht_db_dump_v1(node)

    print('\n\nALL EXCEPTIONS:')
    failed = False 
    for node in ALL_NODES:
        failed = failed or print_exceptions_one_node(node)

    for node in ALL_NODES:
        report_one_node(node)

    assert not failed, 'found some critical errors'

#------------------------------------------------------------------------------


@pytest.yield_fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

#------------------------------------------------------------------------------


@pytest.yield_fixture(scope='session', autouse=True)
def global_wrapper(event_loop):
    print('\n\nENV:\n%s' % pprint.pformat(dict(os.environ)))
    print ('\n\nALL NODES:\n%s' % pprint.pformat(ALL_NODES))

    _begin = time.time()

    if os.environ.get('OPEN_TUNNELS', '1') == '1':
        open_all_tunnels(event_loop)

    if os.environ.get('STOP_NODES', '0') == '1':
        stop_all_nodes(event_loop)

    if os.environ.get('CLEAN_NODES', '0') == '1':
        clean_all_nodes(event_loop, skip_checks=True)

    if os.environ.get('START_NODES', '1') == '1':
        start_all_nodes(event_loop)

    print('\nTest network prepared in %5.3f seconds\n' % (time.time() - _begin))
 
    yield

    # stop_all_nodes(event_loop)
    report_all_nodes(event_loop)
    # TODO: use ENV variables to control cleanup
    # clean_all_nodes()
    # close_all_tunnels()
    # kill_all_nodes()

    print('\nTest suite completed in %5.3f seconds\n' % (time.time() - _begin))
