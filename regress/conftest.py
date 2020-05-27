#!/usr/bin/env python
# conftest.py
#
# Copyright (C) 2008 Stanislav Evseev, Veselin Penev  https://bitdust.io
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

import testsupport as tsup

#------------------------------------------------------------------------------

TEST_NAME = os.environ['TEST_NAME']

CONF = json.loads(open(f'/app/tests/{TEST_NAME}/conf.json', 'r').read())

PAUSE_BEFORE = 0  # int(os.environ.get('PAUSE_BEFORE', CONF.get('pause_before', '0')))

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
        tsup.open_one_tunnel_async(node, 9000+pos, event_loop) for pos, node in enumerate(ALL_NODES)
    ]))
    print('\nAll SSH tunnels opened in %5.3f seconds\n' % (time.time() - _begin))


def clean_all_nodes(event_loop, skip_checks=False, verbose=False):
    _begin = time.time()
    print('\nCleaning all nodes')
    event_loop.run_until_complete(asyncio.gather(*[
        tsup.clean_one_node_async(node, event_loop=event_loop, verbose=verbose) for node in ALL_NODES
    ]))
    event_loop.run_until_complete(asyncio.gather(*[
        tsup.clean_one_customer_async(node['name'], event_loop=event_loop, verbose=verbose) for node in ALL_ROLES['customer']
    ]))
    print('\n\nAll nodes cleaned in %5.3f seconds\n' % (time.time() - _begin))


def start_all_nodes(event_loop, verbose=False):
    _begin = time.time()
    if verbose:
        print('\nStarting nodes\n')

    for number, dhtseed in enumerate(ALL_ROLES.get('dht-seed', [])):
        # first seed to be started immediately, all other seeds must wait a bit before start
        tsup.start_one_dht_seed(dhtseed, wait_seconds=(3 if number > 0 else 0), verbose=verbose)
    if verbose:
        print('ALL DHT SEEDS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.start_one_identity_server_async(idsrv, event_loop) for idsrv in ALL_ROLES.get('identity-server', [])
    ]))
    if verbose:
        print(f'ALL ID SERVERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.start_one_stun_server_async(stunsrv, event_loop) for stunsrv in ALL_ROLES.get('stun-server', [])
    ]))
    if verbose:
        print(f'ALL STUN SERVERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.start_one_proxy_server_async(proxy_server, event_loop) for proxy_server in ALL_ROLES.get('proxy-server', [])
    ]))
    if verbose:
        print(f'ALL PROXY SERVERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.start_one_supplier_async(supplier, event_loop) for supplier in ALL_ROLES.get('supplier', [])
    ]))
    if verbose:
        print(f'ALL SUPPLIERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.start_one_message_broker_async(message_broker, event_loop) for message_broker in ALL_ROLES.get('message-broker', [])
    ]))
    if verbose:
        print(f'ALL MESSAGE BROKERS STARTED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.start_one_customer_async(customer, event_loop, sleep_before_start=i*3) for i, customer in enumerate(ALL_ROLES.get('customer', []))
    ]))
    if verbose:
        print(f'ALL CUSTOMERS STARTED\n')

    print('ALL NODES STARTED in %5.3f seconds\n' % (time.time() - _begin))


def stop_all_nodes(event_loop, verbose=False):
    _begin = time.time()
    if verbose:
        print('\nstop all nodes\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.stop_daemon_async(customer['name'], event_loop, verbose=verbose) for customer in ALL_ROLES.get('customer', [])
    ]))
    if verbose:
        print(f'ALL CUSTOMERS STOPPED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.stop_daemon_async(message_broker['name'], event_loop, verbose=verbose) for message_broker in ALL_ROLES.get('message-broker', [])
    ]))
    if verbose:
        print(f'ALL MESSAGE BROKERS STOPPED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.stop_daemon_async(supplier['name'], event_loop, verbose=verbose) for supplier in ALL_ROLES.get('supplier', [])
    ]))
    if verbose:
        print(f'ALL SUPPLIERS STOPPED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.stop_daemon_async(proxy_server['name'], event_loop, verbose=verbose) for proxy_server in ALL_ROLES.get('proxy-server', [])
    ]))
    if verbose:
        print(f'ALL PROXY SERVERS STOPPED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.stop_daemon_async(stunsrv['name'], event_loop, verbose=verbose) for stunsrv in ALL_ROLES.get('stun-server', [])
    ]))
    if verbose:
        print(f'ALL STUN SERVERS STOPPED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.stop_daemon_async(idsrv['name'], event_loop, verbose=verbose) for idsrv in ALL_ROLES.get('identity-server', [])
    ]))
    if verbose:
        print(f'ALL ID SERVERS STOPPED\n')

    event_loop.run_until_complete(asyncio.gather(*[
        tsup.stop_daemon_async(dhtseed['name'], event_loop, verbose=verbose) for dhtseed in ALL_ROLES.get('dht-seed', [])
    ]))
    if verbose:
        print('ALL DHT SEEDS STOPPED\n')

    print('\nALL NODES STOPPED in %5.3f seconds\n' % (time.time() - _begin))


def log_network_info_all_nodes(event_loop):
    _begin = time.time()
    print('\nget network info from all nodes\n')
    event_loop.run_until_complete(asyncio.gather(*[
        tsup.log_network_info_one_node_async(node, event_loop) for node in ALL_NODES
    ]))
    print('\nALL NODES STOPPED in %5.3f seconds\n' % (time.time() - _begin))


def kill_all_nodes():
    for node in ALL_NODES:
        print('Shutdown %s' % node)
        tsup.run_ssh_command_and_wait(node, 'pkill -e sshd')
    print('All nodes stopped')


def report_all_nodes(event_loop):
    # print('\n\nSTDOUT:')
    # for node in ['customer_restore', ]:
    #     print('\n\nSTDOUT on [%s]:' % node)
    #     ts.print_stdout_one_node(node)

    # print('\n\nDHT records:')
    # for node in ALL_NODES:
    #     print('\n\nDHT records on [%s]:' % node)
    #     keywords.dht_db_dump_v1(node)

    print('\n\nEXCEPTIONS:')
    failed = False 
    for node in ALL_NODES:
        failed = failed or tsup.print_exceptions_one_node(node)

    print('\n\nREPORT:')
    for node in ALL_NODES:
        tsup.report_one_node(node)

    assert not failed, 'found some critical errors'


def collect_coverage_all_nodes(event_loop):
    _begin = time.time()
    print('\nCollecting coverage from all nodes')
    event_loop.run_until_complete(asyncio.gather(*[
        tsup.collect_coverage_one_node_async(node, event_loop=event_loop) for node in ALL_NODES
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
    print('\n\nPAUSE_BEFORE: %d' % PAUSE_BEFORE)
    print('\n\nENV:\n%s' % pprint.pformat(dict(os.environ)))
    print('\n\nALL NODES:\n%s' % pprint.pformat(ALL_NODES))

    time.sleep(PAUSE_BEFORE)

    verbose = True

    _begin = time.time()

    if os.environ.get('OPEN_TUNNELS', '1') == '1':
        open_all_tunnels(event_loop)

    if os.environ.get('STOP_NODES', '0') == '1':
        stop_all_nodes(event_loop, verbose=verbose)

    if os.environ.get('CLEAN_NODES', '0') == '1':
        clean_all_nodes(event_loop, skip_checks=True, verbose=verbose)

    if os.environ.get('START_NODES', '1') == '1':
        try:
            start_all_nodes(event_loop, verbose=verbose)
        except Exception as exc:
            report_all_nodes(event_loop)
            raise exc

    print('\nTest network prepared in %5.3f seconds\n' % (time.time() - _begin))
 
    yield

    print('\nTest suite completed in %5.3f seconds\n' % (time.time() - _begin))

    # TODO: use ENV variables to control stop / coverage / report / cleanup

    # log_network_info_all_nodes(event_loop)
    stop_all_nodes(event_loop)
    collect_coverage_all_nodes(event_loop)
    report_all_nodes(event_loop)

    # clean_all_nodes()
    # close_all_tunnels()
    # kill_all_nodes()

    print('\nAll done in %5.3f seconds\n' % (time.time() - _begin))
