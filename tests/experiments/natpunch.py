#!/usr/bin/env python
# natpunch.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (natpunch.py) is part of BitDust Software.
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

from __future__ import absolute_import
from __future__ import print_function
import sys

from twisted.internet import reactor  # @UnresolvedImport
from six.moves import range

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from bitdust.logs import lg

from bitdust.system import bpio
from bitdust.lib import udp

#------------------------------------------------------------------------------


def listen(local_port, servers, incomings_filename):

    def _loop():
        incomings = []
        for line in open(incomings_filename).read().split('\n'):
            addr = line.strip().split(':')
            addr[1] = int(addr[1])
            incomings.append(tuple(addr))
        if len(incomings):
            for inc in incomings:
                udp.send_command(local_port, udp.CMD_PING, 'ping', inc)
        reactor.callLater(5, _loop)

    for srv in servers:
        udp.send_command(local_port, udp.CMD_PING, 'ping', srv)
    _loop()


def connect(local_port, remote_ip, servers, min_port, max_port):

    def _loop():
        for port_num in range(min_port, max_port + 1):
            udp.send_command(local_port, udp.CMD_PING, 'ping', (remote_ip, port_num))
        reactor.callLater(5, _loop)

    for srv in servers:
        udp.send_command(local_port, udp.CMD_PING, 'ping', srv)
    _loop()


def datagram_received(datagram, address, local_port):
    try:
        cmd, payload = datagram
    except:
        return
    if sys.argv[1] == 'server':
        udp.send_command(local_port, udp.CMD_PING, 'stun %s:%d' % address, address)
    elif sys.argv[1] == 'listen':
        if payload.startswith('stun'):
            print(payload)
        elif payload.startswith('ping'):
            udp.send_command(local_port, udp.CMD_PING, 'ok', address)
    elif sys.argv[1] == 'connect':
        if payload.startswith('stun'):
            print(payload)
        elif payload.startswith('ping'):
            udp.send_command(local_port, udp.CMD_PING, 'ok', address)
            if address[0] == sys.argv[3]:
                print('OKAY!!!!!!!!!!!!!!', address)
                reactor.stop()


def main():
    if len(sys.argv) <= 1:
        print('usage:')
        print('    natpunch.py server [min port] [max port]')
        print('    natpunch.py listen [local port] [servers list filename] [incoming connections filename]')
        print('    natpunch.py connect [local port] [remote IP] [servers list file] [min port] [max port]')
        return

    lg.set_debug_level(24)
    bpio.init()

    if sys.argv[1] == 'server':
        min_port = int(sys.argv[2])
        max_port = int(sys.argv[3])
        for port_num in range(min_port, max_port + 1):
            udp.listen(port_num)
            udp.proto(port_num).add_callback(lambda d, a: datagram_received(d, a, port_num))

    elif sys.argv[1] == 'listen':
        port_num = int(sys.argv[2])
        udp.listen(port_num)
        udp.proto(port_num).add_callback(lambda d, a: datagram_received(d, a, port_num))
        servers = []
        for line in open(sys.argv[3]).read().split('\n'):
            addr = line.strip().split(':')
            addr[1] = int(addr[1])
            servers.append(tuple(addr))
        listen(port_num, servers, sys.argv[4])

    elif sys.argv[1] == 'connect':
        port_num = int(sys.argv[2])
        remote_ip = sys.argv[3]
        udp.listen(port_num)
        udp.proto(port_num).add_callback(lambda d, a: datagram_received(d, a, port_num))
        servers = []
        for line in open(sys.argv[4]).read().split('\n'):
            addr = line.strip().split(':')
            addr[1] = int(addr[1])
            servers.append(tuple(addr))
        min_port = int(sys.argv[5])
        max_port = int(sys.argv[6])
        connect(port_num, remote_ip, servers, min_port, max_port)

    reactor.run()


if __name__ == '__main__':
    main()
