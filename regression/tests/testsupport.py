#!/usr/bin/env python
# testsupport.py
#
# Copyright (C) 2008-2018 Stanislav Evseev, Veselin Penev  https://bitdust.io
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


import subprocess
import asyncio
import json


#------------------------------------------------------------------------------

_SSHTunnels = {}
_NodeTunnelPort = {} 
_NextSSHTunnelPort = 10000

#------------------------------------------------------------------------------


async def run_ssh_command_and_wait_async(host, cmd, loop):
    if host in [None, '', b'', 'localhost', ]:
        cmd_args = cmd
    else:
        cmd_args = ['ssh', '-o', 'StrictHostKeyChecking=no', '-p', '22', 'root@%s' % host, cmd, ]

    create = asyncio.create_subprocess_exec(*cmd_args,
                                            stdout=asyncio.subprocess.PIPE,
                                            loop=loop)
    ssh_proc = await create
    stdout, stderr = await ssh_proc.communicate()
    if stderr:
        print('STDERR: %r' % stderr)
    assert not stderr
    return stdout.decode(), stderr


def run_ssh_command_and_wait(host, cmd):
    if host in [None, '', b'', 'localhost', ]:
        cmd_args = cmd
    else:
        cmd_args = ['ssh', '-o', 'StrictHostKeyChecking=no', '-p', '22', f'root@{host}', cmd, ]
    ssh_proc = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, shell=False)
    output, err = ssh_proc.communicate()
    if err:
        print('STDERR: %r' % err)
    assert not err
    return output.decode(), err


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
    print(f'open_tunnel [{node}] on port {local_port} with {ssh_proc}\n')


def close_tunnel(node):
    global _SSHTunnels
    if node == 'is':
        node = 'identity-server'
    if node not in _SSHTunnels:
        assert False, 'ssh tunnel process for that node was not found'
    close_ssh_port_forwarding(node, _SSHTunnels[node])
    _SSHTunnels.pop(node)
    print(f'close_tunnel [{node}] OK\n')


def open_ssh_port_forwarding(node, port1, port2):
    if node == 'is':
        node = 'identity-server'
    cmd_args = ['ssh', '-4', '-o', 'StrictHostKeyChecking=no', '-p', '22', '-N', '-L', '%d:localhost:%d' % (port1, port2, ), 'root@%s' % node, ]
    print('\n[%s] %s' % (node, ' '.join(cmd_args), ))
    ssh_proc = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, shell=False)
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
    return f'http://127.0.0.1:{tunnel_port(node)}/{endpoint.lstrip("/")}'
