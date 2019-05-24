#!/usr/bin/env python
# testsupport.py
#
# Copyright (C) 2008-2019 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (testsupport.py) is part of BitDust Software.
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
import datetime
import subprocess
import asyncio
import json


#------------------------------------------------------------------------------
import aiohttp  # @UnresolvedImport
import requests

PROXY_ROUTERS = 'http://is:8084/proxy_server_1.xml http://is:8084/proxy_server_2.xml'

_SSHTunnels = {}
_NodeTunnelPort = {} 
_NextSSHTunnelPort = 10000

#------------------------------------------------------------------------------


async def run_ssh_command_and_wait_async(host, cmd, loop):
    if host in [None, '', b'', 'localhost', ]:
        cmd_args = cmd
    else:
        cmd_args = ['ssh', '-o', 'StrictHostKeyChecking=no', '-p', '22', 'root@%s' % host, cmd, ]
    create = asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        loop=loop,
    )
    ssh_proc = await create
    stdout, stderr = await ssh_proc.communicate()
    if stderr:
        print('STDERR: %r' % stderr.decode())
    # assert not stderr
    print(f'\nssh_command on [{host}] : {cmd}')
    return stdout.decode(), stderr.decode()


def run_ssh_command_and_wait(host, cmd):
    if host in [None, '', b'', 'localhost', ]:
        cmd_args = cmd
    else:
        cmd_args = ['ssh', '-o', 'StrictHostKeyChecking=no', '-p', '22', f'root@{host}', cmd, ]
    ssh_proc = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    output, err = ssh_proc.communicate()
    if err:
        print('\nSTDERR: %r' % err.decode())
    # assert not err
    return output.decode(), err.decode()


async def open_tunnel_async(node, local_port, loop):
    global _SSHTunnels
    global _NodeTunnelPort
    # global _NextSSHTunnelPort
    if node == 'is':
        node = 'identity-server'
    # local_port = int(str(_NextSSHTunnelPort))
    cmd_args = ['ssh', '-4', '-o', 'StrictHostKeyChecking=no', '-p', '22', '-N', '-L', '%d:localhost:%d' % (local_port, 8180, ), 'root@%s' % node, ]
    print('\n[%s]:%s %s' % (node, time.time(), ' '.join(cmd_args), ))
    tunnel = asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        loop=loop,
    )
    ssh_proc = await tunnel
    _SSHTunnels[node] = ssh_proc
    _NodeTunnelPort[node] = local_port
    # _NextSSHTunnelPort += 1
    print(f'\nopen_tunnel [{node}] on port {local_port} with {ssh_proc}')
    return ssh_proc


# ===================================================== #

def open_tunnel(node):
    global _SSHTunnels
    global _NodeTunnelPort
    global _NextSSHTunnelPort
    if node == 'is':
        node = 'identity-server'
    local_port = int(str(_NextSSHTunnelPort))
    ssh_proc = open_ssh_port_forwarding(node, port1=local_port, port2=8180)
    _SSHTunnels[node] = ssh_proc
    _NodeTunnelPort[node] = local_port
    _NextSSHTunnelPort += 1
    print(f'\nopen_tunnel [{node}] on port {local_port} with {ssh_proc}')


async def open_one_tunnel_async(node, local_port, loop):
    await open_tunnel_async(node, local_port, loop)


# ===================================================== #


def close_tunnel(node):
    global _SSHTunnels
    if node == 'is':
        node = 'identity-server'
    if node not in _SSHTunnels:
        assert False, 'ssh tunnel process for that node was not found'
    close_ssh_port_forwarding(node, _SSHTunnels[node])
    _SSHTunnels.pop(node)
    print(f'\nclose_tunnel [{node}] OK')


def save_tunnels_ports():
    global _NodeTunnelPort
    open('/tunnels_ports.json', 'w').write(json.dumps(_NodeTunnelPort))


def load_tunnels_ports():
    global _NodeTunnelPort
    _NodeTunnelPort = json.loads(open('/tunnels_ports.json', 'r').read())


def open_ssh_port_forwarding(node, port1, port2):
    if node == 'is':
        node = 'identity-server'
    cmd_args = ['ssh', '-4', '-o', 'StrictHostKeyChecking=no', '-p', '22', '-N', '-L', '%d:localhost:%d' % (port1, port2, ), 'root@%s' % node, ]
    print('\n[%s] %s' % (node, ' '.join(cmd_args), ))
    ssh_proc = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    return ssh_proc


def close_ssh_port_forwarding(node, ssh_proc):
    if node == 'is':
        node = 'identity-server'
    print(f'\n[{node}] closing {ssh_proc}')
    ssh_proc.kill()
    return True


def open_all_tunnels(nodes):
    for node in nodes:
        open_tunnel(node)


def close_all_tunnels():
    global _SSHTunnels
    for node in list(_SSHTunnels.keys()):
        if node == 'is':
            node = 'identity-server'
        close_tunnel(node)


def tunnel_port(node):
    global _NodeTunnelPort
    if node == 'is':
        node = 'identity-server'
    return _NodeTunnelPort[node]


def tunnel_url(node, endpoint):
    print('\n%s [%s]: tunnel_url - %s' % (datetime.datetime.now().strftime("%H:%M:%S.%f"), node, endpoint, ))
    return f'http://127.0.0.1:{tunnel_port(node)}/{endpoint.lstrip("/")}'


def start_stun_server(node):
    print(f'\nNEW STUN SERVER at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # enable Stun server
    run_ssh_command_and_wait(node, 'bitdust set services/ip-port-responder/enabled true')
    # start BitDust daemon
    start_daemon(node)
    health_check(node)
    print(f'\nSTARTED STUN SERVER [{node}]\n')


async def start_stun_server_async(node, event_loop):
    print(f'\nNEW STUN SERVER at [{node}]\n')
    # use short key to run tests faster
    await run_ssh_command_and_wait_async(node, 'bitdust set personal/private-key-size 1024', event_loop)
    # disable unwanted services
    await run_ssh_command_and_wait_async(node, 'bitdust set services/customer/enabled false', event_loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/supplier/enabled false', event_loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/proxy-transport/enabled false', event_loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/proxy-server/enabled false', event_loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/private-messages/enabled false', event_loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/nodes-lookup/enabled false', event_loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/identity-propagate/enabled false', event_loop)
    # configure DHT udp port
    await run_ssh_command_and_wait_async(node, 'bitdust set services/entangled-dht/udp-port "14441"', event_loop)
    # enable Stun server
    await run_ssh_command_and_wait_async(node, 'bitdust set services/ip-port-responder/enabled true', event_loop)
    # start BitDust daemon
    await start_daemon_async(node, event_loop)
    await health_check_async(node, event_loop)
    print(f'\nSTARTED STUN SERVER [{node}]\n')


def start_daemon(node):
    run_ssh_command_and_wait(node, 'mkdir -pv /root/.bitdust/metadata/')
    run_ssh_command_and_wait(node, 'echo "docker" > /root/.bitdust/metadata/networkname')
    bitdust_daemon = run_ssh_command_and_wait(node, 'bitdust daemon')
    print('\n' + bitdust_daemon[0].strip())
    assert (
        bitdust_daemon[0].strip().startswith('main BitDust process already started') or
        bitdust_daemon[0].strip().startswith('new BitDust process will be started in daemon mode')
    )
    print(f'\nstart_daemon [{node}] OK\n')


async def start_daemon_async(node, loop):
    await run_ssh_command_and_wait_async(node, 'mkdir -pv /root/.bitdust/metadata/', loop)
    await run_ssh_command_and_wait_async(node, 'echo "docker" > /root/.bitdust/metadata/networkname', loop)
    bitdust_daemon = await run_ssh_command_and_wait_async(node, 'bitdust daemon', loop)
    print('\n' + bitdust_daemon[0].strip())
    assert (
        bitdust_daemon[0].strip().startswith('main BitDust process already started') or
        bitdust_daemon[0].strip().startswith('new BitDust process will be started in daemon mode')
    )
    print(f'\nstart_daemon_async [{node}] OK\n')


def health_check(node):
    count = 0
    while True:
        if count > 60:
            assert False, f'node {node} is not healthy after many attempts'
        try:
            response = requests.get(tunnel_url(node, 'process/health/v1'))
        except Exception as exc:
            # print(f'[{node}] retry {count}   GET:process/health/v1  :  {exc}')
            response = None
        if response and response.status_code == 200 and response.json()['status'] == 'OK':
            break
        print(f'\nnode {node} process not started yet, try again after 1 sec.\n')
        time.sleep(1)
        count += 1
    print(f'\nprocess/health/v1 [{node}] : OK')


async def health_check_async(node, event_loop):
    async with aiohttp.ClientSession(loop=event_loop) as client:
        count = 0
        while True:
            print(f'health_check_async {node}  with count={count}\n')
            if count > 60:
                print(f'node {node} is not healthy after many attempts')
                assert False, f'node {node} is not healthy after many attempts'
            try:
                response = await client.get(tunnel_url(node, 'process/health/v1'))
                response_json = await response.json()
            except aiohttp.ServerDisconnectedError:
                print(f'node {node} is not started yet, count={count}\n')
            else:
                if response.status == 200 and response_json['status'] == 'OK':
                    break
                print(f'node {node} process not started yet, try again after 1 sec.\n')
            await asyncio.sleep(1)
            count += 1
    print(f'process/health/v1 [{node}] : OK\n')


def create_identity(node, identity_name):
    count = 0
    while True:
        if count > 60:
            assert False, f'node {node} failed to create identity after many retries'
        response = requests.post(
            url=tunnel_url(node, 'identity/create/v1'),
            json={
                'username': identity_name,
            },
        )
        if response.json()['status'] == 'OK':
            # print('\n' + response.json()['result'][0]['xml'] + '\n')
            break
        if not response.status_code == 200 or (response.json()['status'] == 'ERROR' and response.json()['errors'][0] == 'network connection error'):
            count += 1
            # print('[%s] retry %d   POST:identity/create/v1  username=%s     network connection error' % (node, count, identity_name, ))
            continue

        assert False, f'[{node}] bad response from /identity/create/v1'

    print(f'identity/create/v1 [{node}] with name {identity_name} : OK\n')


async def create_identity_async(node, identity_name, event_loop):
    async with aiohttp.ClientSession(loop=event_loop) as client:
        for i in range(60):
            response_identity = await client.post(tunnel_url(node, 'identity/create/v1'), json={'username': identity_name})
            assert response_identity.status == 200

            response_json = await response_identity.json()

            if response_json['status'] == 'OK':
                # print('\n' + response_json['result'][0]['xml'] + '\n')
                break
            else:
                assert response_json['errors'] == ['network connection error'], response_json

            print('[%s] retry %d   POST:identity/create/v1  username=%s    after 1 sec.' % (node, i + 1, identity_name,))
            await asyncio.sleep(1)
        else:
            print(f'identity/create/v1 [{node}] with name {identity_name} : FAILED\n')
            assert False

    print(f'identity/create/v1 [{node}] with name {identity_name} : OK\n')


def connect_network(node):
    count = 0
    response = requests.get(url=tunnel_url(node, 'network/connected/v1?wait_timeout=1'))
    assert response.json()['status'] == 'ERROR'
    while True:
        if count > 60:
            assert False, f'node {node} failed to connect to the network after many retries'
        response = requests.get(tunnel_url(node, 'network/connected/v1?wait_timeout=5'))
        if response.json()['status'] == 'OK':
            break
        count += 1
        # print('[%s] retry %d   GET:network/connected/v1' % (node, count, ))
        time.sleep(1)
    print(f'network/connected/v1 [{node}] : OK\n')


async def connect_network_async(node, loop):
    async with aiohttp.ClientSession(loop=loop) as client:
        response = await client.get(tunnel_url(node, 'network/connected/v1?wait_timeout=1'))
        response_json = await response.json()
        assert response_json['status'] == 'ERROR'

        counter = 0
        for i in range(60):
            counter += 1
            response = await client.get(tunnel_url(node, '/network/connected/v1?wait_timeout=1'))
            response_json = await response.json()
            if response_json['status'] == 'OK':
                print(f"network/connected/v1 {node}: got status OK\n")
                break

            print(f"connect_network_async attempt {counter} at {node}: sleep 1 sec\n")
            await asyncio.sleep(1)
        else:
            print(f"connect_network_async {node}: FAILED\n")
            assert False


def stop_daemon(node, skip_checks=False):
    bitdust_stop = run_ssh_command_and_wait(node, 'bitdust stop')
    print('\n' + bitdust_stop[0].strip())
    if not skip_checks:
        assert (
            (
                bitdust_stop[0].strip().startswith('BitDust child processes found') and
                bitdust_stop[0].strip().endswith('BitDust stopped')
            ) or (
                bitdust_stop[0].strip().startswith('found main BitDust process:') and
                bitdust_stop[0].strip().endswith('BitDust process finished correctly')
            )
        )
    print(f'stop_daemon [{node}] OK\n')


async def stop_daemon_async(node, loop, skip_checks=False):
    bitdust_stop = await run_ssh_command_and_wait_async(node, 'bitdust stop', loop)
    print('\n' + bitdust_stop[0].strip())
    if not skip_checks:
        assert (
            (
                bitdust_stop[0].strip().startswith('BitDust child processes found') and
                bitdust_stop[0].strip().endswith('BitDust stopped')
            ) or (
                bitdust_stop[0].strip().startswith('found main BitDust process:') and
                bitdust_stop[0].strip().endswith('BitDust process finished correctly')
            ) or (
                bitdust_stop[0].strip() == 'BitDust is not running at the moment'
            )
        )
    print(f'stop_daemon [{node}] OK\n')


def start_proxy_server(node, identity_name):
    print(f'\nNEW PROXY SERVER {identity_name} at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')

    # configure ID servers
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/min-servers 1')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/max-servers 1')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # enable ProxyServer service
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled true')
    # start BitDust daemon and create new identity for proxy server
    start_daemon(node)
    health_check(node)
    create_identity(node, identity_name)
    connect_network(node)
    print(f'\nSTARTED PROXY SERVER [{node}]\n')


async def start_proxy_server_async(node, identity_name, loop):
    print(f'\nNEW PROXY SERVER {identity_name} at [{node}]\n')
    # use short key to run tests faster
    await run_ssh_command_and_wait_async(node, 'bitdust set personal/private-key-size 1024', loop)
    # disable unwanted services
    await run_ssh_command_and_wait_async(node, 'bitdust set services/customer/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/supplier/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/proxy-transport/enabled false', loop)

    # configure ID servers
    await run_ssh_command_and_wait_async(node, 'bitdust set services/identity-propagate/min-servers 1', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/identity-propagate/max-servers 1', loop)
    # configure DHT udp port
    await run_ssh_command_and_wait_async(node, 'bitdust set services/entangled-dht/udp-port "14441"', loop)
    # enable ProxyServer service
    await run_ssh_command_and_wait_async(node, 'bitdust set services/proxy-server/enabled true', loop)
    # start BitDust daemon and create new identity for proxy server
    await start_daemon_async(node, loop)
    await health_check_async(node, loop)
    await create_identity_async(node, identity_name, loop)
    await connect_network_async(node, loop)
    print(f'\nSTARTED PROXY SERVER [{node}]\n')


def start_identity_server(node):
    print(f'\nNEW IDENTITY SERVER at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # configure and enable ID server
    run_ssh_command_and_wait(node, f'bitdust set services/identity-server/host {node}')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-server/enabled true')
    # start BitDust daemon
    start_daemon(node)
    health_check(node)
    print(f'\nSTARTED IDENTITY SERVER [{node}]\n')


async def start_identity_server_async(node, loop):
    print(f'\nNEW IDENTITY SERVER at [{node}]\n')
    # use short key to run tests faster
    await run_ssh_command_and_wait_async(node, 'bitdust set personal/private-key-size 1024', loop)
    # disable unwanted services
    await run_ssh_command_and_wait_async(node, 'bitdust set services/customer/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/supplier/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/proxy-transport/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/proxy-server/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/private-messages/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/nodes-lookup/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/identity-propagate/enabled false', loop)
    # configure DHT udp port
    await run_ssh_command_and_wait_async(node, 'bitdust set services/entangled-dht/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/entangled-dht/udp-port "14441"', loop)
    # configure and enable ID server
    await run_ssh_command_and_wait_async(node, f'bitdust set services/identity-server/host {node}', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/identity-server/enabled true', loop)
    # start BitDust daemon
    await start_daemon_async(node, loop)
    await health_check_async(node, loop)
    print(f'\nSTARTED IDENTITY SERVER [{node}]\n')


def start_dht_seed(node, wait_seconds=0, other_seeds=''):
    print(f'\nNEW DHT SEED (with STUN SERVER) at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')
    # configure DHT udp port and seed nodes
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "%s"' % other_seeds)

    # enable Stun server
    run_ssh_command_and_wait(node, 'bitdust set services/ip-port-responder/enabled true')
    # start BitDust daemon
    print(f'sleep {wait_seconds} seconds')
    time.sleep(wait_seconds)
    start_daemon(node)
    health_check(node)
    print(f'\nSTARTED DHT SEED (with STUN SERVER) [{node}]\n')


def start_supplier(node, identity_name):
    print(f'\nNEW SUPPLIER {identity_name} at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    # configure ID servers
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/min-servers 1')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/max-servers 1')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # set desired Proxy router
    run_ssh_command_and_wait(node, f'bitdust set services/proxy-transport/preferred-routers "{PROXY_ROUTERS}"')
    # enable supplier service
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled true')
    # start BitDust daemon and create new identity for supplier
    start_daemon(node)
    health_check(node)
    create_identity(node, identity_name)
    connect_network(node)
    print(f'\nSTARTED SUPPLIER [{node}]\n')


async def start_supplier_async(node, identity_name, loop):
    print(f'\nNEW SUPPLIER {identity_name} at [{node}]\n')
    # use short key to run tests faster
    await run_ssh_command_and_wait_async(node, 'bitdust set personal/private-key-size 1024', loop)
    # disable unwanted services
    await run_ssh_command_and_wait_async(node, 'bitdust set services/customer/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/proxy-server/enabled false', loop)
    # configure ID servers
    await run_ssh_command_and_wait_async(node, 'bitdust set services/identity-propagate/min-servers 1', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/identity-propagate/max-servers 1', loop)
    # configure DHT udp port
    await run_ssh_command_and_wait_async(node, 'bitdust set services/entangled-dht/udp-port "14441"', loop)
    # set desired Proxy router
    await run_ssh_command_and_wait_async(node, f'bitdust set services/proxy-transport/preferred-routers "{PROXY_ROUTERS}"', loop)
    # enable supplier service
    await run_ssh_command_and_wait_async(node, 'bitdust set services/supplier/enabled true', loop)
    # start BitDust daemon and create new identity for supplier
    await start_daemon_async(node, loop)
    await health_check_async(node, loop)
    await create_identity_async(node, identity_name, loop)
    await connect_network_async(node, loop)
    print(f'\nSTARTED SUPPLIER [{node}]\n')


def start_customer(node, identity_name, join_network=True, num_suppliers=2, block_size=None):
    print(f'\nNEW CUSTOMER {identity_name} at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    # configure ID servers
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/min-servers 1')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/max-servers 1')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # set desired Proxy router
    run_ssh_command_and_wait(node, f'bitdust set services/proxy-transport/preferred-routers "{PROXY_ROUTERS}"')
    # enable customer service and prepare tests
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled true')
    run_ssh_command_and_wait(node, f'bitdust set services/customer/suppliers-number {num_suppliers}')
    if block_size:
        run_ssh_command_and_wait(node, f'bitdust set services/backups/block-size {block_size}')
    # create randomized file to test file upload/download
    run_ssh_command_and_wait(node, f'python -c "import os, base64; print(base64.b64encode(os.urandom(30000)).decode())" > /{node}/file_{node}.txt')
    run_ssh_command_and_wait(node, f'python -c "import os, base64; print(base64.b64encode(os.urandom(24)).decode())" > /{node}/second_file_{node}.txt')
    # start BitDust daemon and create new identity for supplier
    start_daemon(node)
    health_check(node)
    if join_network:
        create_identity(node, identity_name)
        connect_network(node)
    print(f'\nSTARTED CUSTOMER [{node}]\n')


async def start_customer_async(node, identity_name, loop, join_network=True, num_suppliers=2, block_size=None):
    print('\nNEW CUSTOMER %r at [%s]\n' % (identity_name, node, ))
    # use short key to run tests faster
    await run_ssh_command_and_wait_async(node, 'bitdust set personal/private-key-size 1024', loop)
    # disable unwanted services
    await run_ssh_command_and_wait_async(node, 'bitdust set services/supplier/enabled false', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/proxy-server/enabled false', loop)
    # configure ID servers
    await run_ssh_command_and_wait_async(node, 'bitdust set services/identity-propagate/min-servers 1', loop)
    await run_ssh_command_and_wait_async(node, 'bitdust set services/identity-propagate/max-servers 1', loop)
    # configure DHT udp port
    await run_ssh_command_and_wait_async(node, 'bitdust set services/entangled-dht/udp-port "14441"', loop)
    # set desired Proxy router
    await run_ssh_command_and_wait_async(node, f'bitdust set services/proxy-transport/preferred-routers "{PROXY_ROUTERS}"', loop)
    # enable customer service and prepare tests
    await run_ssh_command_and_wait_async(node, 'bitdust set services/customer/enabled true', loop)
    await run_ssh_command_and_wait_async(node, f'bitdust set services/customer/suppliers-number {num_suppliers}', loop)
    if block_size:
        await run_ssh_command_and_wait_async(node, f'bitdust set services/backups/block-size {block_size}', loop)
    # create randomized file to test file upload/download
    await run_ssh_command_and_wait_async(node, f'python -c "import os, base64; print(base64.b64encode(os.urandom(30000)).decode())" > /{node}/file_{node}.txt', loop)
    await run_ssh_command_and_wait_async(node, f'python -c "import os, base64; print(base64.b64encode(os.urandom(24)).decode())" > /{node}/second_file_{node}.txt', loop)
    # start BitDust daemon and create new identity for supplier
    await start_daemon_async(node, loop)
    await health_check_async(node, loop)
    if join_network:
        await create_identity_async(node, identity_name, loop)
        await connect_network_async(node, loop)
    print(f'\nSTARTED CUSTOMER [{node}]\n')


def start_one_supplier(supplier):
    start_supplier(node=supplier, identity_name=supplier)


async def start_one_supplier_async(supplier, loop):
    await start_supplier_async(node=supplier, identity_name=supplier, loop=loop)


def start_one_customer(customer):
    start_customer(
        node=customer['name'],
        identity_name=customer['name'],
        join_network=customer['join_network'],
        num_suppliers=customer['num_suppliers'],
    )


async def start_one_customer_async(customer, loop):
    await start_customer_async(
        node=customer['name'],
        identity_name=customer['name'],
        join_network=customer['join_network'],
        num_suppliers=customer['num_suppliers'],
        block_size=customer.get('block_size'),
        loop=loop,
    )


def start_one_proxy_server(proxy_server):
    start_proxy_server(node=proxy_server, identity_name=proxy_server)


async def start_one_proxy_server_async(proxy_server, loop):
    await start_proxy_server_async(node=proxy_server, identity_name=proxy_server, loop=loop)


def stop_one_node(node):
    stop_daemon(node, skip_checks=True)


def report_one_node(node):
    main_log = run_ssh_command_and_wait(node, 'cat /root/.bitdust/logs/main.log')[0].strip()
    num_warnings = main_log.count('WARNING')
    num_errors = main_log.count('ERROR!!!')
    num_exceptions = main_log.count('Exception:')
    num_tracebacks = main_log.count('Traceback')
    num_failures = main_log.count('Failure')
    # assert num_exceptions == 0, 'found some critical errors in the log file on node %s' % node
    print(f'[{node}]  Warnings: {num_warnings}     Errors: {num_errors}    Tracebacks: {num_tracebacks}     '
          f'Failures: {num_failures}    Exceptions: {num_exceptions}')


async def report_one_node_async(node, event_loop):
    main_log = await run_ssh_command_and_wait_async(node, 'cat /root/.bitdust/logs/main.log', event_loop)
    main_log = main_log[0].strip()
    num_warnings = main_log.count('WARNING')
    num_errors = main_log.count('ERROR!!!')
    num_exceptions = main_log.count('Exception:')
    num_tracebacks = main_log.count('Traceback')
    num_failures = main_log.count('Failure')
    # assert num_exceptions == 0, 'found some critical errors in the log file on node %s' % node
    print(f'[{node}]  Warnings: {num_warnings}     Errors: {num_errors}    Tracebacks: {num_tracebacks}     '
          f'Failures: {num_failures}    Exceptions: {num_exceptions}')


def print_exceptions_one_node(node):
    exceptions_out = run_ssh_command_and_wait(node, 'cat /root/.bitdust/logs/exception_*.log')[0].strip()
    if exceptions_out:
        print(f'\n[{node}]:\n\n{exceptions_out}\n\n')


async def print_exceptions_one_node_async(node, event_loop):
    exceptions_out = await run_ssh_command_and_wait_async(node, 'cat /root/.bitdust/logs/exception_*.log', event_loop)
    exceptions_out = exceptions_out[0].strip()
    if exceptions_out:
        print(f'\n[{node}]:\n\n{exceptions_out}\n\n')


async def clean_one_node_async(node, event_loop):
    await run_ssh_command_and_wait_async(node, 'rm -rf /root/.bitdust/metadata', event_loop)
    await run_ssh_command_and_wait_async(node, 'rm -rf /root/.bitdust/identitycache', event_loop)
    await run_ssh_command_and_wait_async(node, 'rm -rf /root/.bitdust/identityserver', event_loop)
    await run_ssh_command_and_wait_async(node, 'rm -rf /root/.bitdust/keys', event_loop)
    await run_ssh_command_and_wait_async(node, 'rm -rf /root/.bitdust/customers', event_loop)
    await run_ssh_command_and_wait_async(node, 'rm -rf /root/.bitdust/suppliers', event_loop)
    await run_ssh_command_and_wait_async(node, 'rm -rf /root/.bitdust/backups', event_loop)
    await run_ssh_command_and_wait_async(node, 'rm -rf /root/.bitdust/messages', event_loop)


async def clean_one_customer_async(node, event_loop):
    await run_ssh_command_and_wait_async(node, 'rm -rf /%s/*' % node, event_loop)


def clean_one_node(node):
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/metadata')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/identitycache')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/identityserver')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/keys')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/customers')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/suppliers')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/backups')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/messages')


def clean_one_customer(node):
    run_ssh_command_and_wait(node, 'rm -rf /%s/*' % node)