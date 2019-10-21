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
import json

#------------------------------------------------------------------------------

from testsupport import open_one_tunnel_async, clean_one_node_async, clean_one_customer_async, \
    start_one_dht_seed, start_one_identity_server_async, start_one_stun_server_async, start_one_proxy_server_async, \
    start_one_supplier_async, start_one_customer_async, stop_daemon_async, run_ssh_command_and_wait, \
    print_exceptions_one_node, report_one_node, collect_coverage_one_node_async

#------------------------------------------------------------------------------

TEST_NAME = os.environ['TEST_NAME']

CONF = json.loads(open(f'/app/tests/{TEST_NAME}/conf.json', 'r').read())

ALL_NODES = list(CONF['containers'].keys())

ALL_ROLES = {}
for container in CONF['containers'].values():
    role = container['node']['role']
    if role not in ALL_ROLES:
        ALL_ROLES[role] = []
    ALL_ROLES[role].append(container['node'])

#------------------------------------------------------------------------------

def open_all_tunnels(event_loop):
    _begin = time.time()
    print('\nStarting all SSH tunnels\n')
    event_loop.run_until_complete(asyncio.gather(*[
        open_one_tunnel_async(node, 9000+pos, event_loop) for pos, node in enumerate(ALL_NODES)
    ]))
    print('\nAll SSH tunnels opened in %5.3f seconds\n' % (time.time() - _begin))


def clean_all_nodes(event_loop, skip_checks=False):
    _begin = time.time()
    print('\nCleaning all nodes')
    event_loop.run_until_complete(asyncio.gather(*[
        clean_one_node_async(node, event_loop=event_loop) for node in ALL_NODES
    ]))
    event_loop.run_until_complete(asyncio.gather(*[
        clean_one_customer_async(node['name'], event_loop=event_loop) for node in ALL_ROLES['customer']
    ]))
    print('\n\nAll nodes cleaned in %5.3f seconds\n' % (time.time() - _begin))


def start_all_nodes(event_loop):
    _begin = time.time()
    print('\nStarting nodes\n')

    for number, dhtseed in enumerate(ALL_ROLES['dht-seed']):
        # first seed to be started immediately, all other seeds must wait a bit before start
        start_one_dht_seed(dhtseed, wait_seconds=(5 if number > 0 else 0))
    print('\nALL DHT SEEDS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_one_identity_server_async(idsrv, event_loop) for idsrv in ALL_ROLES['identity-server']
    ]))
    print(f'\nALL ID SERVERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_one_stun_server_async(stunsrv, event_loop) for stunsrv in ALL_ROLES['stun-server']
    ]))
    print(f'\nALL STUN SERVERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_one_proxy_server_async(proxy_server, event_loop) for proxy_server in ALL_ROLES['proxy-server']
    ]))
    print(f'\nALL PROXY SERVERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_one_supplier_async(supplier, event_loop) for supplier in ALL_ROLES['supplier']
    ]))
    print(f'\nALL SUPPLIERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        start_one_customer_async(customer, event_loop, sleep_before_start=i*10) for i, customer in enumerate(ALL_ROLES['customer'])
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


def collect_coverage_all_nodes(event_loop):
    _begin = time.time()
    print('\nCollecting coverage from all nodes')
    event_loop.run_until_complete(asyncio.gather(*[
        collect_coverage_one_node_async(node, event_loop=event_loop) for node in ALL_NODES
    ]))
    print('\n\nAll coverage files received in  %5.3f seconds\n' % (time.time() - _begin))

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

    print('\nTest suite completed in %5.3f seconds\n' % (time.time() - _begin))

    # TODO: use ENV variables to control stop / coverage / report / cleanup

    stop_all_nodes(event_loop)
    collect_coverage_all_nodes(event_loop)
    report_all_nodes(event_loop)

    # clean_all_nodes()
    # close_all_tunnels()
    # kill_all_nodes()

    print('\nAll done in %5.3f seconds\n' % (time.time() - _begin))
