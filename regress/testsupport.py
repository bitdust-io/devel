#!/usr/bin/env python
# testsupport.py
#
# Copyright (C) 2008 Stanislav Evseev, Veselin Penev  https://bitdust.io
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

import os
import time
import datetime
import subprocess
import asyncio
import json
import pprint

#------------------------------------------------------------------------------

import aiohttp  # @UnresolvedImport
import requests

#------------------------------------------------------------------------------

_SSHTunnels = {}
_NodeTunnelPort = {} 
_NextSSHTunnelPort = 10000
_SSLContexts = {}

#------------------------------------------------------------------------------

async def run_ssh_command_and_wait_async(host, cmd, loop, verbose=False):
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
        if verbose:
            print(f'STDERR at {host}: %r' % stderr.decode())
    if verbose:
        print(f'\nssh_command on [{host}] : {cmd}')
    return stdout.decode(), stderr.decode()


def run_ssh_command_and_wait(host, cmd, verbose=False) -> object:
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
        if verbose:
            print('\nSTDERR: %r' % err.decode())
    if verbose:
        print(f'\nssh_command on [{host}] : {cmd}')
    return output.decode(), err.decode()

#------------------------------------------------------------------------------

def request_get(node, url, timeout=None):
    resp = None
    err = None
    count = 0
    while True:
        if count > 3:
            print('\nGET request failed after few attempts :  node=%r   url=%r   err=%r\n' % (node, url, err))
            assert False, 'GET request failed after few attempts :  node=%r   url=%r    err=%r' % (node, url, err)
            break
        try:
            resp = requests.get(
                tunnel_url(node, url),
                timeout=timeout,
                # cert=(f'/app/certificates/{node}/apiclientcert', f'/app/certificates/{node}/apiclientcertkey'),
                # verify=f'/app/certificates/{node}/apiservercert',
            )
        except Exception as exc:
            resp = None
            err = exc
        if resp:
            break
        count += 1
    return resp


def request_post(node, url, json={}, timeout=None):
    resp = None
    err = None
    count = 0
    while True:
        if count > 3:
            print('\nPOST request failed after few attempts :  node=%r   url=%r   json=%r   err=%r\n' % (node, url, json, err))
            assert False, 'POST request failed after few attempts :  node=%r   url=%r   json=%r   err=%r' % (node, url, json, err)
            break
        try:
            resp = requests.post(
                url=tunnel_url(node, url),
                json=json,
                timeout=timeout,
                # cert=(f'/app/certificates/{node}/apiclientcert', f'/app/certificates/{node}/apiclientcertkey'),
                # verify=f'/app/certificates/{node}/apiservercert',
            )
        except Exception as exc:
            resp = None
            err = exc
        if resp:
            break
        count += 1
    return resp


def request_put(node, url, json={}, timeout=None):
    resp = None
    err = None
    count = 0
    while True:
        if count > 3:
            print('\nPUT request failed after few attempts :  node=%r   url=%r   json=%r   err=%r\n' % (node, url, json, err))
            assert False, 'PUT request failed after few attempts :  node=%r   url=%r   json=%r   err=%r' % (node, url, json, err)
            break
        try:
            resp = requests.put(
                url=tunnel_url(node, url),
                json=json,
                timeout=timeout,
                # cert=(f'/app/certificates/{node}/apiclientcert', f'/app/certificates/{node}/apiclientcertkey'),
                # verify=f'/app/certificates/{node}/apiservercert',
            )
        except Exception as exc:
            resp = None
            err = exc
        if resp:
            break
        count += 1
    return resp

#------------------------------------------------------------------------------

def ssl_connection(node):
    # ssl_ctx = ssl.create_default_context(cafile=f'/app/certificates/{node}/apiservercert')
    # ssl_ctx.load_cert_chain(f'/app/certificates/{node}/apiclientcert', f'/app/certificates/{node}/apiclientcertkey')
    # return aiohttp.TCPConnector(ssl=ssl_ctx)
    return None

#------------------------------------------------------------------------------

async def open_tunnel_async(node, local_port, loop):
    global _SSHTunnels
    global _NodeTunnelPort
    cmd_args = ['ssh', '-4', '-o', 'StrictHostKeyChecking=no', '-p', '22', '-N', '-L',
                '%d:localhost:%d' % (local_port, 8180, ), 'root@%s' % node, ]
    # print('\n[%s]:%s %s' % (node, time.time(), ' '.join(cmd_args), ))
    tunnel = asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        loop=loop,
    )
    ssh_proc = await tunnel
    _SSHTunnels[node] = ssh_proc
    _NodeTunnelPort[node] = local_port
    # print(f'\nopen_tunnel [{node}] on port {local_port} with {ssh_proc}')
    return ssh_proc


def open_tunnel(node):
    global _SSHTunnels
    global _NodeTunnelPort
    global _NextSSHTunnelPort
    local_port = int(str(_NextSSHTunnelPort))
    ssh_proc = open_ssh_port_forwarding(node, port1=local_port, port2=8180)
    _SSHTunnels[node] = ssh_proc
    _NodeTunnelPort[node] = local_port
    _NextSSHTunnelPort += 1
    # print(f'\nopen_tunnel [{node}] on port {local_port} with {ssh_proc}')


async def open_one_tunnel_async(node, local_port, loop):
    await open_tunnel_async(node, local_port, loop)


def close_tunnel(node):
    global _SSHTunnels
    if node not in _SSHTunnels:
        assert False, 'ssh tunnel process for that node was not found'
    close_ssh_port_forwarding(node, _SSHTunnels[node])
    _SSHTunnels.pop(node)
    # print(f'\nclose_tunnel [{node}] OK')


def save_tunnels_ports():
    global _NodeTunnelPort
    open('/tunnels_ports.json', 'w').write(json.dumps(_NodeTunnelPort))


def load_tunnels_ports():
    global _NodeTunnelPort
    _NodeTunnelPort = json.loads(open('/tunnels_ports.json', 'r').read())

#------------------------------------------------------------------------------

def open_ssh_port_forwarding(node, port1, port2):
    cmd_args = ['ssh', '-4', '-o', 'StrictHostKeyChecking=no', '-p', '22', '-N', '-L',
                '%d:localhost:%d' % (port1, port2, ), 'root@%s' % node, ]
    print('\n[%s] %s' % (node, ' '.join(cmd_args), ))
    ssh_proc = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    return ssh_proc


def close_ssh_port_forwarding(node, ssh_proc):
    print(f'\n[{node}] closing {ssh_proc}')
    ssh_proc.kill()
    return True

#------------------------------------------------------------------------------

def open_all_tunnels(nodes):
    for node in nodes:
        open_tunnel(node)


def close_all_tunnels():
    global _SSHTunnels
    for node in list(_SSHTunnels.keys()):
        close_tunnel(node)

#------------------------------------------------------------------------------

def tunnel_port(node):
    global _NodeTunnelPort
    return _NodeTunnelPort[node]


def tunnel_url(node, endpoint):
    print('\n%s [%s]   /%s   %s' % (
        datetime.datetime.now().strftime("%H:%M:%S.%f"), node, endpoint,
        os.environ['PYTEST_CURRENT_TEST'].replace(' (setup)', '').replace(' (call)', ''), ))
    return f'http://127.0.0.1:{tunnel_port(node)}/{endpoint.lstrip("/")}'

#------------------------------------------------------------------------------

def start_daemon(node):
    run_ssh_command_and_wait(node, 'mkdir -pv /root/.bitdust/metadata/')
    if os.environ.get('_DEBUG', '0') == '0':
        run_ssh_command_and_wait(node, "find /app/bitdust -type f -name '*.py' -exec sed -i -e 's/_Debug = True/_Debug = False/g' {} +")
    bitdust_daemon = run_ssh_command_and_wait(node, 'BITDUST_LOG_USE_COLORS=0 COVERAGE_PROCESS_START=/app/bitdust/.coverage_config bitdust daemon')
    print('\n' + bitdust_daemon[0].strip())
    assert (
        bitdust_daemon[0].strip().startswith('main BitDust process already started') or
        bitdust_daemon[0].strip().startswith('new BitDust process will be started in daemon mode')
    )
    print(f'\nstart_daemon [{node}] OK\n')

async def start_daemon_async(node, loop):
    await run_ssh_command_and_wait_async(node, 'mkdir -pv /root/.bitdust/metadata/', loop)
    if os.environ.get('_DEBUG', '0') == '0':
        await run_ssh_command_and_wait_async(node, "find /app/bitdust -type f -name '*.py' -exec sed -i -e 's/_Debug = True/_Debug = False/g' {} +", loop)
    bitdust_daemon = await run_ssh_command_and_wait_async(node, 'BITDUST_LOG_USE_COLORS=0 COVERAGE_PROCESS_START=/app/bitdust/.coverage_config bitdust daemon', loop)
    print('\n' + bitdust_daemon[0].strip())
    assert (
        bitdust_daemon[0].strip().startswith('main BitDust process already started') or
        bitdust_daemon[0].strip().startswith('new BitDust process will be started in daemon mode')
    )
    print(f'\nstart_daemon_async [{node}] OK\n')

#------------------------------------------------------------------------------

def get_client_certificate(node):
    print(f'\nget_client_certificate [{node}]\n')
    if not os.path.isdir(f'/app/certificates/{node}/'):
        os.makedirs(f'/app/certificates/{node}/')
    while True:
        print(f'\nchecking /root/.bitdust/metadata/apiclientcert from [{node}]\n')
        apiclientcert = run_ssh_command_and_wait(node, 'cat /root/.bitdust/metadata/apiclientcert')[0]
        if not apiclientcert:
            time.sleep(0.5)
            continue
        open(f'/app/certificates/{node}/apiclientcert', 'w').write(apiclientcert)
        break
    while True:
        print(f'\nchecking /root/.bitdust/metadata/apiclientcertkey from [{node}]\n')
        apiclientcertkey = run_ssh_command_and_wait(node, 'cat /root/.bitdust/metadata/apiclientcertkey')[0]
        if not apiclientcertkey:
            time.sleep(0.5)
            continue
        open(f'/app/certificates/{node}/apiclientcertkey', 'w').write(apiclientcertkey)
        break
    while True:
        print(f'\nchecking /root/.bitdust/metadata/apiservercert from [{node}]\n')
        apiservercert = run_ssh_command_and_wait(node, 'cat /root/.bitdust/metadata/apiservercert')[0]
        if not apiservercert:
            time.sleep(0.5)
            continue
        open(f'/app/certificates/{node}/apiservercert', 'w').write(apiservercert)
        break
    print(f'\nget_client_certificate [{node}] OK\n')


async def get_client_certificate_async(node, loop):
    print(f'\nget_client_certificate_async [{node}]\n')
    if not os.path.isdir(f'/app/certificates/{node}/'):
        os.makedirs(f'/app/certificates/{node}/')
    while True:
        print(f'\nchecking /root/.bitdust/metadata/apiclientcert from [{node}]\n')
        apiclientcert = (await run_ssh_command_and_wait_async(node, 'cat /root/.bitdust/metadata/apiclientcert', loop))[0]
        if not apiclientcert:
            await asyncio.sleep(0.5)
            continue
        open(f'/app/certificates/{node}/apiclientcert', 'w').write(apiclientcert)
        break
    while True:
        print(f'\nchecking /root/.bitdust/metadata/apiclientcertkey from [{node}]\n')
        apiclientcertkey = (await run_ssh_command_and_wait_async(node, 'cat /root/.bitdust/metadata/apiclientcertkey', loop))[0]
        if not apiclientcertkey:
            await asyncio.sleep(0.5)
            continue
        open(f'/app/certificates/{node}/apiclientcertkey', 'w').write(apiclientcertkey)
        break
    while True:
        print(f'\nchecking /root/.bitdust/metadata/apiservercert from [{node}]\n')
        apiservercert = (await run_ssh_command_and_wait_async(node, 'cat /root/.bitdust/metadata/apiservercert', loop))[0]
        if not apiservercert:
            await asyncio.sleep(0.5)
            continue
        open(f'/app/certificates/{node}/apiservercert', 'w').write(apiservercert)
        break
    print(f'\nget_client_certificate_async [{node}] OK\n')

#------------------------------------------------------------------------------

def health_check(node, verbose=False):
    count = 0
    while True:
        if count > 60:
            assert False, f'node {node} is not healthy after many attempts'
        try:
            response = request_get(node, 'process/health/v1')
        except Exception as exc:
            response = None
            if verbose:
                print(f'node {node} is not started yet, count={count} : {exc}\n')
        if response and response.status_code == 200 and response.json()['status'] == 'OK':
            break
        if verbose:
            print(f'\nnode {node} process not started yet, try again after 1 sec.\n')
        time.sleep(1)
        count += 1
    print(f'\nprocess/health/v1 [{node}] : OK')


async def health_check_async(node, event_loop):
    async with aiohttp.ClientSession(loop=event_loop, connector=ssl_connection(node)) as client:
        count = 0
        while True:
            print(f'health_check_async {node}  with count={count}\n')
            if count > 60:
                print(f'node {node} is not healthy after many attempts')
                assert False, f'node {node} is not healthy after many attempts'
            try:
                response = await client.get(tunnel_url(node, 'process/health/v1'))
                response_json = await response.json()
            except (
                aiohttp.ServerDisconnectedError,
                aiohttp.client_exceptions.ClientOSError,
            ) as exc:
                print(f'node {node} is not started yet, count={count} : {exc}\n')
            else:
                if response.status == 200 and response_json['status'] == 'OK':
                    break
                print(f'node {node} process not started yet, try again after 1 sec.\n')
            await asyncio.sleep(1)
            count += 1
    print(f'process/health/v1 [{node}] : OK\n')

#------------------------------------------------------------------------------

def create_identity(node, identity_name):
    count = 0
    while True:
        if count > 60:
            assert False, f'node {node} failed to create identity after many retries'
        response = request_post(node, 'identity/create/v1', json={
            'username': identity_name,
        })
        if response.json()['status'] == 'OK':
            break
        if not response.status_code == 200 or (
            response.json()['status'] == 'ERROR' and response.json()['errors'][0] == 'network connection error'
        ):
            count += 1
            continue
        assert False, f'[{node}] bad response from /identity/create/v1'
    print(f'identity/create/v1 [{node}] with name {identity_name} : OK\n')


async def create_identity_async(node, identity_name, event_loop):
    async with aiohttp.ClientSession(loop=event_loop, connector=ssl_connection(node)) as client:
        for i in range(60):
            response_identity = await client.post(tunnel_url(node, 'identity/create/v1'), json={'username': identity_name})
            assert response_identity.status == 200
            response_json = await response_identity.json()
            if response_json['status'] == 'OK':
                break
            else:
                assert response_json['errors'] == ['network connection error'], response_json
            print('[%s] retry %d   POST:identity/create/v1  username=%s  after 1 sec.' % (
                node, i + 1, identity_name,))
            await asyncio.sleep(1)
        else:
            print(f'identity/create/v1 [{node}] with name {identity_name} : FAILED\n')
            assert False
    print(f'identity/create/v1 [{node}] with name {identity_name} : OK\n')


def connect_network(node):
    count = 0
    response = request_get(node, 'network/connected/v1?wait_timeout=1')
    assert response.json()['status'] == 'ERROR'
    while True:
        if count > 60:
            assert False, f'node {node} failed to connect to the network after many retries'
        response = request_get(node, 'network/connected/v1?wait_timeout=5')
        if response.json()['status'] == 'OK':
            break
        count += 1
        time.sleep(1)
    print(f'network/connected/v1 [{node}] : OK\n')


async def connect_network_async(node, loop, attempts=30, delay=1, timeout=10, verbose=False):
    async with aiohttp.ClientSession(loop=loop, connector=ssl_connection(node)) as client:
        response = await client.get(tunnel_url(node, 'network/connected/v1?wait_timeout=1'), timeout=timeout)
        response_json = await response.json()
        if verbose:
            print(f'\nnetwork/connected/v1 [{node}] : %s' % pprint.pformat(response_json))
        if response_json['status'] == 'OK':
            print(f"network/connected/v1 {node}: got status OK from the first call\n")
            return
        counter = 0
        for i in range(attempts):
            counter += 1
            response = await client.get(tunnel_url(node, 'network/connected/v1?wait_timeout=1'), timeout=timeout)
            response_json = await response.json()
            if verbose:
                print(f'\nnetwork/connected/v1 [{node}] : %s' % pprint.pformat(response_json))
            if response_json['status'] == 'OK':
                print(f"network/connected/v1 {node}: got status OK\n")
                break
            if verbose:
                print(f"connect network attempt {counter} at {node}: sleep 1 sec\n")
            await asyncio.sleep(delay)
        else:
            print(f"connect network {node}: FAILED\n")
            assert False


async def service_started_async(node, service_name, loop, expected_state='ON', attempts=60, delay=3, verbose=False):
    async with aiohttp.ClientSession(loop=loop, connector=ssl_connection(node)) as client:
        current_state = None
        count = 0
        while current_state is None or current_state != expected_state:
            response = await client.get(tunnel_url(node, f'service/info/{service_name}/v1'))
            response_json = await response.json()
            assert response_json['status'] == 'OK', response_json
            current_state = response_json['result'][0]['state']
            if verbose:
                print(f'\nservice/info/{service_name}/v1 [{node}] : %s' % pprint.pformat(response_json))
            if current_state == expected_state:
                break
            count += 1
            if count >= attempts:
                assert False, f"service {service_name} is not {expected_state} after {attempts} attempts"
                return
            await asyncio.sleep(delay)
        print(f'service/info/{service_name}/v1 [{node}] : OK\n')


async def packet_list_async(node, loop, wait_all_finish=True, attempts=60, delay=3, verbose=False):
    async with aiohttp.ClientSession(loop=loop, connector=ssl_connection(node)) as client:
        for i in range(attempts):
            response = await client.get(tunnel_url(node, 'packet/list/v1'), timeout=20)
            response_json = await response.json()
            if verbose:
                print('\npacket/list/v1 [%s] : %s\n' % (node, pprint.pformat(response_json), ))
            assert response_json['status'] == 'OK', response_json
            if len(response_json['result']) == 0 or not wait_all_finish:
                break
            await asyncio.sleep(delay)
        else:
            assert False, 'some packets are still have in/out progress on [%s]' % node

#------------------------------------------------------------------------------

def stop_daemon(node, skip_checks=False):
    bitdust_stop = run_ssh_command_and_wait(node, 'bitdust stop', verbose=False)
    # print('\n' + bitdust_stop[0].strip())
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
    # print(f'stop_daemon [{node}] OK\n')


async def stop_daemon_async(node, loop, skip_checks=False):
    bitdust_stop = await run_ssh_command_and_wait_async(node, 'bitdust stop', loop, verbose=False)
    # print('\n' + bitdust_stop[0].strip())
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
    # print(f'stop_daemon [{node}] OK\n')

#------------------------------------------------------------------------------

async def start_identity_server_async(node, loop):
    print(f'\nNEW IDENTITY SERVER at [{node}]\n')
    cmd = ''
    cmd += 'bitdust set logs/debug-level 18;'
    cmd += 'bitdust set logs/api-enabled true;'
    cmd += 'bitdust set logs/automat-events-enabled true;'
    cmd += 'bitdust set logs/automat-transitions-enabled true;'
    cmd += 'bitdust set logs/packet-enabled true;'
    cmd += 'bitdust set personal/private-key-size 1024;'
    cmd += 'bitdust set services/customer/enabled false;'
    cmd += 'bitdust set services/supplier/enabled false;'
    cmd += 'bitdust set services/proxy-transport/enabled false;'
    cmd += 'bitdust set services/proxy-server/enabled false;'
    cmd += 'bitdust set services/private-messages/enabled false;'
    cmd += 'bitdust set services/nodes-lookup/enabled false;'
    cmd += 'bitdust set services/identity-propagate/enabled false;'
    cmd += 'bitdust set services/entangled-dht/enabled false;'
    cmd += 'bitdust set services/entangled-dht/udp-port "14441";'
    cmd += f'bitdust set services/identity-server/host "{node}";'
    cmd += 'bitdust set services/identity-server/enabled true;'
    await run_ssh_command_and_wait_async(node, cmd, loop)
    await start_daemon_async(node, loop)
    # await get_client_certificate_async(node, loop)
    await health_check_async(node, loop)
    print(f'\nSTARTED IDENTITY SERVER [{node}]\n')


def start_dht_seed(node, wait_seconds=0, dht_seeds='', attached_layers=''):
    print(f'\nNEW DHT SEED (with STUN SERVER) at [{node}]\n')
    cmd = ''
    cmd += 'bitdust set logs/debug-level 18;'
    cmd += 'bitdust set logs/api-enabled true;'
    cmd += 'bitdust set logs/automat-events-enabled true;'
    cmd += 'bitdust set logs/automat-transitions-enabled true;'
    cmd += 'bitdust set logs/packet-enabled true;'
    # use shorter key to run tests faster
    cmd += 'bitdust set personal/private-key-size 1024;'
    # disable unrelated services
    cmd += 'bitdust set services/customer/enabled false;'
    cmd += 'bitdust set services/supplier/enabled false;'
    cmd += 'bitdust set services/proxy-transport/enabled false;'
    cmd += 'bitdust set services/proxy-server/enabled false;'
    cmd += 'bitdust set services/private-messages/enabled false;'
    cmd += 'bitdust set services/nodes-lookup/enabled false;'
    cmd += 'bitdust set services/identity-propagate/enabled false;'
    # configure DHT udp port and seed nodes
    cmd += 'bitdust set services/entangled-dht/udp-port "14441";'
    if dht_seeds:
        cmd += f'bitdust set services/entangled-dht/known-nodes "{dht_seeds}";'
    if attached_layers:
        cmd += f'bitdust set services/entangled-dht/attached-layers "{attached_layers}";'
    # enable Stun server
    cmd += 'bitdust set services/ip-port-responder/enabled true;'
    run_ssh_command_and_wait(node, cmd)
    # start BitDust daemon
    print(f'sleep {wait_seconds} seconds')
    time.sleep(wait_seconds)
    start_daemon(node)
    # get_client_certificate(node)
    health_check(node)
    print(f'\nSTARTED DHT SEED (with STUN SERVER) [{node}]\n')


async def start_stun_server_async(node, loop, dht_seeds=''):
    print(f'\nNEW STUN SERVER at [{node}]\n')
    cmd = ''
    cmd += 'bitdust set logs/debug-level 18;'
    cmd += 'bitdust set logs/api-enabled true;'
    cmd += 'bitdust set logs/automat-events-enabled true;'
    cmd += 'bitdust set logs/automat-transitions-enabled true;'
    cmd += 'bitdust set logs/packet-enabled true;'
    # use short key to run tests faster
    cmd += 'bitdust set personal/private-key-size 1024;'
    # disable unrelated services
    cmd += 'bitdust set services/customer/enabled false;'
    cmd += 'bitdust set services/supplier/enabled false;'
    cmd += 'bitdust set services/proxy-transport/enabled false;'
    cmd += 'bitdust set services/proxy-server/enabled false;'
    cmd += 'bitdust set services/private-messages/enabled false;'
    cmd += 'bitdust set services/nodes-lookup/enabled false;'
    cmd += 'bitdust set services/identity-propagate/enabled false;'
    # configure DHT udp port and node ID
    cmd += 'bitdust set services/entangled-dht/udp-port "14441";'
    if dht_seeds:
        cmd += f'bitdust set services/entangled-dht/known-nodes "{dht_seeds}";'
    # enable Stun server
    cmd += 'bitdust set services/ip-port-responder/enabled true;'
    await run_ssh_command_and_wait_async(node, cmd, loop)
    # start BitDust daemon
    await start_daemon_async(node, loop)
    # await get_client_certificate_async(node, loop)
    await health_check_async(node, loop)
    print(f'\nSTARTED STUN SERVER [{node}]\n')


async def start_proxy_server_async(node, identity_name, loop, known_servers='', dht_seeds=''):
    print(f'\nNEW PROXY SERVER {identity_name} at [{node}]\n')
    cmd = ''
    cmd += 'bitdust set logs/debug-level 18;'
    cmd += 'bitdust set logs/api-enabled true;'
    cmd += 'bitdust set logs/automat-events-enabled true;'
    cmd += 'bitdust set logs/automat-transitions-enabled true;'
    cmd += 'bitdust set logs/packet-enabled true;'
    # use short key to run tests faster
    cmd += 'bitdust set personal/private-key-size 1024;'
    # disable unrelated services
    cmd += 'bitdust set services/customer/enabled false;'
    cmd += 'bitdust set services/supplier/enabled false;'
    cmd += 'bitdust set services/proxy-transport/enabled false;'
    # configure ID servers
    cmd += 'bitdust set services/identity-propagate/min-servers 1;'
    cmd += 'bitdust set services/identity-propagate/max-servers 1;'
    if known_servers:
        cmd += f'bitdust set services/identity-propagate/known-servers "{known_servers}";'
    # configure DHT udp port and node ID
    cmd += 'bitdust set services/entangled-dht/udp-port "14441";'
    if dht_seeds:
        cmd += f'bitdust set services/entangled-dht/known-nodes "{dht_seeds}";'
    # enable ProxyServer service
    cmd += 'bitdust set services/proxy-server/enabled true;'
    await run_ssh_command_and_wait_async(node, cmd, loop)
    # start BitDust daemon and create new identity for proxy server
    await start_daemon_async(node, loop)
    # await get_client_certificate_async(node, loop)
    await health_check_async(node, loop)
    await create_identity_async(node, identity_name, loop)
    await connect_network_async(node, loop)
    print(f'\nSTARTED PROXY SERVER [{node}]\n')


async def start_supplier_async(node, identity_name, loop, join_network=True,
                               min_servers=1, max_servers=1, known_servers='', dht_seeds='',
                               preferred_servers='', preferred_routers=''):
    print(f'\nNEW SUPPLIER {identity_name} at [{node}]\n')
    cmd = ''
    cmd += 'bitdust set logs/debug-level 18;'
    cmd += 'bitdust set logs/api-enabled true;'
    cmd += 'bitdust set logs/automat-events-enabled true;'
    cmd += 'bitdust set logs/automat-transitions-enabled true;'
    cmd += 'bitdust set logs/packet-enabled true;'
    # use short key to run tests faster
    cmd += 'bitdust set personal/private-key-size 1024;'
    # disable unrelated services
    cmd += 'bitdust set services/customer/enabled false;'
    cmd += 'bitdust set services/proxy-server/enabled false;'
    # configure ID servers
    if min_servers is not None:
        cmd += f'bitdust set services/identity-propagate/min-servers "{min_servers}";'
    if max_servers is not None:
        cmd += f'bitdust set services/identity-propagate/max-servers "{max_servers}";'
    if known_servers:
        cmd += f'bitdust set services/identity-propagate/known-servers "{known_servers}";'
    if preferred_servers:
        cmd += f'bitdust set services/identity-propagate/preferred-servers "{preferred_servers}";'
    # configure DHT udp port and node ID
    cmd += 'bitdust set services/entangled-dht/udp-port "14441";'
    if dht_seeds:
        cmd += f'bitdust set services/entangled-dht/known-nodes "{dht_seeds}";'
    # set desired Proxy router
    if preferred_routers:
        cmd += f'bitdust set services/proxy-transport/preferred-routers "{preferred_routers}";'
    # enable supplier service
    cmd += 'bitdust set services/supplier/enabled true;'
    await run_ssh_command_and_wait_async(node, cmd, loop)
    # start BitDust daemon and create new identity for supplier
    await start_daemon_async(node, loop)
    # await get_client_certificate_async(node, loop)
    await health_check_async(node, loop)
    if join_network:
        await create_identity_async(node, identity_name, loop)
        await connect_network_async(node, loop)
        await service_started_async(node, 'service_supplier', loop)
        await packet_list_async(node, loop)
    print(f'\nSTARTED SUPPLIER [{node}]\n')


async def start_customer_async(node, identity_name, loop, join_network=True, num_suppliers=2, block_size=None,
                               min_servers=1, max_servers=1, known_servers='', preferred_servers='', dht_seeds='',
                               supplier_candidates='', preferred_routers='', health_check_interval_seconds=None,
                               sleep_before_start=None, ):
    if sleep_before_start:
        print('\nsleep %d seconds before start customer %r\n' % (sleep_before_start, identity_name))
        await asyncio.sleep(sleep_before_start)
    print('\nNEW CUSTOMER %r at [%s]\n' % (identity_name, node, ))
    cmd = ''
    cmd += 'bitdust set logs/debug-level 18;'
    cmd += 'bitdust set logs/api-enabled true;'
    cmd += 'bitdust set logs/automat-events-enabled true;'
    cmd += 'bitdust set logs/automat-transitions-enabled true;'
    cmd += 'bitdust set logs/packet-enabled true;'
    # use short key to run tests faster
    cmd += 'bitdust set personal/private-key-size 1024;'
    # disable unrelated services
    cmd += 'bitdust set services/supplier/enabled false;'
    cmd += 'bitdust set services/proxy-server/enabled false;'
    # configure ID servers
    if min_servers is not None:
        cmd += f'bitdust set services/identity-propagate/min-servers "{min_servers}";'
    if max_servers is not None:
        cmd += f'bitdust set services/identity-propagate/max-servers "{max_servers}";'
    if known_servers:
        cmd += f'bitdust set services/identity-propagate/known-servers "{known_servers}";'
    if preferred_servers:
        cmd += f'bitdust set services/identity-propagate/preferred-servers "{preferred_servers}";'
    if health_check_interval_seconds:
        cmd += f'bitdust set services/identity-propagate/health-check-interval-seconds "{health_check_interval_seconds}";'
    # configure DHT udp and seed nodes
    cmd += 'bitdust set services/entangled-dht/udp-port "14441";'
    if dht_seeds:
        cmd += f'bitdust set services/entangled-dht/known-nodes "{dht_seeds}";'
    # set desired Proxy router
    if preferred_routers:
        cmd += f'bitdust set services/proxy-transport/preferred-routers "{preferred_routers}";'
    # enable customer service and prepare tests
    cmd += 'bitdust set services/customer/enabled true;'
    cmd += f'bitdust set services/customer/suppliers-number "{num_suppliers}";'
    if block_size:
        cmd += f'bitdust set services/backups/block-size "{block_size}";'
    if supplier_candidates:
        cmd += f'bitdust set services/employer/candidates "{supplier_candidates}";'
    await run_ssh_command_and_wait_async(node, cmd, loop)
    # start BitDust daemon and create new identity for supplier
    await start_daemon_async(node, loop)
    # await get_client_certificate_async(node, loop)
    await health_check_async(node, loop)
    if join_network:
        await create_identity_async(node, identity_name, loop)
        await connect_network_async(node, loop)
        await service_started_async(node, 'service_shared_data', loop)
        await packet_list_async(node, loop)
    print(f'\nSTARTED CUSTOMER [{node}]\n')

#------------------------------------------------------------------------------


async def start_one_identity_server_async(identity_server, loop):
    await start_identity_server_async(
        node=identity_server['name'],
        loop=loop,
    )


def start_one_dht_seed(dht_seed, wait_seconds):
    start_dht_seed(
        node=dht_seed['name'],
        dht_seeds=dht_seed.get('known_dht_seeds', ''),
        attached_layers=dht_seed.get('attached_layers', '2,3'),
        wait_seconds=wait_seconds,
    )


async def start_one_stun_server_async(stun_server, loop):
    await start_stun_server_async(
        node=stun_server['name'],
        dht_seeds=stun_server.get('known_dht_seeds', ''),
        loop=loop,
    )


async def start_one_proxy_server_async(proxy_server, loop):
    await start_proxy_server_async(
        node=proxy_server['name'],
        identity_name=proxy_server['name'],
        known_servers=proxy_server.get('known_id_servers', ''),
        dht_seeds=proxy_server.get('known_dht_seeds', ''),
        loop=loop,
    )


async def start_one_supplier_async(supplier, loop):
    await start_supplier_async(
        node=supplier['name'],
        identity_name=supplier['name'],
        join_network=supplier.get('join_network', True),
        min_servers=supplier.get('min_servers'),
        max_servers=supplier.get('max_servers'),
        known_servers=supplier.get('known_id_servers', ''),
        dht_seeds=supplier.get('known_dht_seeds', ''),
        preferred_routers=supplier.get('preferred_routers', ''),
        loop=loop,
    )


async def start_one_customer_async(customer, loop, sleep_before_start=None):
    await start_customer_async(
        node=customer['name'],
        identity_name=customer['name'],
        join_network=customer['join_network'],
        num_suppliers=customer['num_suppliers'],
        block_size=customer.get('block_size'),
        min_servers=customer.get('min_servers'),
        max_servers=customer.get('max_servers'),
        known_servers=customer.get('known_id_servers', ''),
        dht_seeds=customer.get('known_dht_seeds', ''),
        supplier_candidates=customer.get('supplier_candidates', ''),
        preferred_routers=customer.get('preferred_routers', ''),
        health_check_interval_seconds=customer.get('health_check_interval_seconds', None),
        sleep_before_start=sleep_before_start,
        loop=loop,
    )


#------------------------------------------------------------------------------

def report_one_node(node):
    main_log = run_ssh_command_and_wait(node, 'cat /root/.bitdust/logs/main.log', verbose=False)[0].strip()
    num_warnings = main_log.count('WARNING')
    num_errors = main_log.count('ERROR!!!')
    num_exceptions = main_log.count('Exception:')
    num_tracebacks = main_log.count('Traceback')
    num_failures = main_log.count('Failure')
    print(f'[{node}]  Warnings: {num_warnings}     Errors: {num_errors}    Tracebacks: {num_tracebacks}     '
          f'Failures: {num_failures}    Exceptions: {num_exceptions}')
    return num_exceptions


async def report_one_node_async(node, event_loop):
    main_log = await run_ssh_command_and_wait_async(node, 'cat /root/.bitdust/logs/main.log', event_loop)
    main_log = main_log[0].strip()
    num_warnings = main_log.count('WARNING')
    num_errors = main_log.count('ERROR!!!')
    num_exceptions = main_log.count('Exception:')
    num_tracebacks = main_log.count('Traceback')
    num_failures = main_log.count('Failure')
    print(f'[{node}]  Warnings: {num_warnings}     Errors: {num_errors}    Tracebacks: {num_tracebacks}     '
          f'Failures: {num_failures}    Exceptions: {num_exceptions}')
    return num_exceptions

#------------------------------------------------------------------------------

def print_exceptions_one_node(node):
    #TODO: find the root cause of invalid signature
    # run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/logs/exception*invalid*signature.log')[0].strip()
    exceptions_out = run_ssh_command_and_wait(node, 'cat /root/.bitdust/logs/exception_*.log 2>/dev/null', verbose=False)[0].strip()
    if exceptions_out:
        print(f'\n[{node}]:\n\n{exceptions_out}\n\n')
    # else:
    #     print(f'\n[{node}]: no exceptions found\n')
    return exceptions_out


async def print_exceptions_one_node_async(node, event_loop):
    print(f'\nsearching errors at {node} in the folder: /root/.bitdust/logs/exception_*.log')
    #TODO: find the root cause of invalid signature
    # await run_ssh_command_and_wait_async(node, 'rm -rf /root/.bitdust/logs/exception*invalid*signature.log', event_loop)
    exceptions_out = await run_ssh_command_and_wait_async(node, 'cat /root/.bitdust/logs/exception_*.log 2>/dev/null', event_loop, verbose=False)
    exceptions_out = exceptions_out[0].strip()
    if exceptions_out:
        print(f'\n[{node}]:\n\n{exceptions_out}\n\n')
    # else:
    #     print(f'\n[{node}]: no exceptions found\n')
    return exceptions_out


def print_stdout_one_node(node):
    std_out = run_ssh_command_and_wait(node, 'cat /root/.bitdust/logs/stdout.log')[0].strip()
    if std_out:
        print(f'\n[{node}]:\n\n{std_out}\n\n')
    else:
        print(f'\n[{node}]: file /root/.bitdust/logs/stdout.log not found\n')
    return std_out

#------------------------------------------------------------------------------

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


async def collect_coverage_one_node_async(node, event_loop, wait_before=3):
    if wait_before:
        # make sure all coverage files are written before collecting them
        await asyncio.sleep(wait_before)
    await run_ssh_command_and_wait_async('localhost', ['mkdir', '-p', '/app/coverage/%s' % node, ], event_loop)
    await run_ssh_command_and_wait_async(
        'localhost',
        ['scp', '-o', 'StrictHostKeyChecking=no', '-P', '22', 'root@%s:/tmp/.coverage.*' % node, '/app/coverage/%s/.' % node, ],
        event_loop,
    )

#------------------------------------------------------------------------------

async def log_network_info_one_node_async(node, event_loop):
    async with aiohttp.ClientSession(loop=event_loop, connector=ssl_connection(node)) as client:
        response = await client.get(tunnel_url(node, 'network/info/v1'), timeout=20)
        response_json = await response.json()
        print('\nnetwork/info/v1 [%s] : %s\n' % (node, pprint.pformat(response_json), ))
        assert response_json['status'] == 'OK', response_json
