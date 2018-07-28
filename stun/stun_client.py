#!/usr/bin/env python
# stun_client.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (stun_client.py) is part of BitDust Software.
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


"""
.. module:: stun_client.

.. role:: red

BitDust ``stun_client()`` Automat


EVENTS:
    * :red:`datagram-received`
    * :red:`dht-nodes-not-found`
    * :red:`found-some-nodes`
    * :red:`init`
    * :red:`port-number-received`
    * :red:`shutdown`
    * :red:`start`
    * :red:`timer-10sec`
    * :red:`timer-2sec`
"""

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

import sys

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from automats import automat

from lib import udp

from main import settings

from dht import dht_service

#------------------------------------------------------------------------------

_StunClient = None

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _StunClient
    if _StunClient is None:
        # set automat name and starting state here
        _StunClient = StunClient('stun_client', 'AT_STARTUP', 8)
    if event is not None:
        _StunClient.automat(event, arg)
    return _StunClient


class StunClient(automat.Automat):
    """
    This class implements all the functionality of the ``stun_client()`` state
    machine.
    """
    # fast = True

    timers = {
        'timer-2sec': (2.0, ['REQUEST']),
        'timer-10sec': (10.0, ['PORT_NUM?', 'REQUEST']),
    }

    MESSAGES = {
        'MSG_01': 'not found any DHT nodes',
        'MSG_02': 'not found any available stun servers',
        'MSG_03': 'timeout responding from stun servers',
    }

    def msg(self, msgid, arg=None):
        return self.MESSAGES.get(msgid, '')

    def init(self):
        self.listen_port = None
        self.callbacks = []
        self.find_nodes_attempts = 1
        self.minimum_needed_servers = 3
        self.minimum_needed_results = 3
        self.stun_nodes = []
        self.stun_servers = []
        self.stun_results = {}
        self.my_address = None
        self.deferreds = {}

    def getMyExternalAddress(self):
        return self.my_address

    def dropMyExternalAddress(self):
        self.my_address = None

    def A(self, event, arg):
        #---STOPPED---
        if self.state == 'STOPPED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start':
                self.state = 'RANDOM_NODES'
                self.doAddCallback(arg)
                self.doDHTFindRandomNode(arg)
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'timer-2sec':
                self.doStun(arg)
            elif event == 'timer-10sec' and not self.isSomeServersResponded(arg):
                self.state = 'STOPPED'
                self.doReportFailed(self.msg('MSG_03', arg))
                self.doClearResults(arg)
            elif event == 'start':
                self.doAddCallback(arg)
            elif event == 'datagram-received' and self.isMyIPPort(arg) and self.isNeedMoreResults(arg):
                self.doRecordResult(arg)
            elif (event == 'timer-10sec' and self.isSomeServersResponded(arg)) or (event == 'datagram-received' and self.isMyIPPort(arg) and not self.isNeedMoreResults(arg)):
                self.state = 'KNOW_MY_IP'
                self.doRecordResult(arg)
                self.doReportSuccess(arg)
                self.doClearResults(arg)
            elif event == 'port-number-received':
                self.doAddStunServer(arg)
                self.doStun(arg)
        #---KNOW_MY_IP---
        elif self.state == 'KNOW_MY_IP':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start':
                self.state = 'RANDOM_NODES'
                self.doAddCallback(arg)
                self.doDHTFindRandomNode(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---RANDOM_NODES---
        elif self.state == 'RANDOM_NODES':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'dht-nodes-not-found':
                self.state = 'STOPPED'
                self.doReportFailed(self.msg('MSG_01', arg))
            elif event == 'start':
                self.doAddCallback(arg)
            elif event == 'found-some-nodes' and self.isNeedMoreNodes(arg):
                self.doRememberStunNodes(arg)
                self.doDHTFindRandomNode(arg)
            elif event == 'found-some-nodes' and not self.isNeedMoreNodes(arg):
                self.state = 'PORT_NUM?'
                self.doRememberStunNodes(arg)
                self.doRequestStunPortNumbers(arg)
        #---PORT_NUM?---
        elif self.state == 'PORT_NUM?':
            if event == 'start':
                self.doAddCallback(arg)
            elif event == 'timer-10sec':
                self.state = 'STOPPED'
                self.doReportFailed(self.msg('MSG_02', arg))
                self.doClearResults(arg)
            elif event == 'port-number-received':
                self.state = 'REQUEST'
                self.doAddStunServer(arg)
                self.doStun(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        return None

    def isMyIPPort(self, arg):
        """
        Condition method.
        """
        try:
            datagram, address = arg
            command, payload = datagram
        except:
            return False
        return command == udp.CMD_MYIPPORT

    def isSomeServersResponded(self, arg):
        """
        Condition method.
        """
        return len(self.stun_results) > 0

    def isNeedMoreResults(self, arg):
        """
        Condition method.
        """
        return len(self.stun_results) <= self.minimum_needed_results

    def isNeedMoreNodes(self, arg):
        """
        Condition method.
        """
        return len(self.stun_nodes) + len(arg) < self.minimum_needed_servers

    def doInit(self, arg):
        """
        Action method.
        """
        self.listen_port = arg
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.doInit on port %d' % self.listen_port)
        if udp.proto(self.listen_port):
            udp.proto(self.listen_port).add_callback(self._datagram_received)
        else:
            lg.warn('udp port %s is not opened' % self.listen_port)

    def doAddCallback(self, arg):
        """
        Action method.
        """
        if arg:
            self.callbacks.append(arg)

    def doDHTFindRandomNode(self, arg):
        """
        Action method.
        """
        self._find_random_node()

    def doRememberStunNodes(self, arg):
        """
        Action method.
        """
        nodes = arg
        for node in nodes:
            if node not in self.stun_nodes:
                self.stun_nodes.append(node)

    def doRequestStunPortNumbers(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel + 10, 'stun_client.doRequestStunPortNumbers')
        nodes = arg
        for node in nodes:
            if _Debug:
                lg.out(_DebugLevel + 10, '    %s' % node)
            d = node.request('stun_port')
            d.addBoth(self._stun_port_received, node)
            self.deferreds[node] = d

    def doAddStunServer(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel + 10, 'stun_client.doAddStunServer %s' % str(arg))
        self.stun_servers.append(arg)

    def doStun(self, arg):
        """
        Action method.
        """
        if arg is not None:
            if _Debug:
                lg.out(_DebugLevel + 10, 'stun_client.doStun to one stun_server: %s' % str(arg))
            udp.send_command(self.listen_port, udp.CMD_STUN, '', arg)
            return
        if _Debug:
            lg.out(_DebugLevel + 10, 'stun_client.doStun to %d stun_servers' % (
                len(self.stun_servers)))  # , self.stun_servers))
        for address in self.stun_servers:
            if address is None:
                continue
            if address in self.stun_results.keys():
                continue
            udp.send_command(self.listen_port, udp.CMD_STUN, '', address)

    def doRecordResult(self, arg):
        """
        Action method.
        """
        if arg is None:
            return
        try:
            datagram, address = arg
            command, payload = datagram
            ip, port = payload.split(':')
            port = int(port)
        except:
            lg.exc()
        self.stun_results[address] = (ip, port)
        # if len(self.stun_results) >= len(self.stun_servers):
        #     self.automat('all-responded')

    def doClearResults(self, arg):
        """
        Action method.
        """
        self.stun_nodes = []
        self.stun_servers = []
        self.stun_results = {}

    def doReportSuccess(self, arg):
        """
        Action method.
        """
        try:
            min_port = min(map(lambda addr: addr[1], self.stun_results.values()))
            max_port = max(map(lambda addr: addr[1], self.stun_results.values()))
            my_ip = self.stun_results.values()[0][0]
            if min_port == max_port:
                result = ('stun-success', 'non-symmetric', my_ip, min_port)
            else:
                result = ('stun-success', 'symmetric', my_ip, self.stun_results)
            self.my_address = (my_ip, min_port)
        except:
            lg.exc()
            result = ('stun-failed', None, None, [])
            self.my_address = None
        if self.my_address:
            bpio.WriteFile(settings.ExternalIPFilename(), self.my_address[0])
            bpio.WriteFile(settings.ExternalUDPPortFilename(), str(self.my_address[1]))
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.doReportSuccess based on %d nodes: %s' % (
                len(self.stun_results), str(self.my_address)))
        if _Debug:
            lg.out(_DebugLevel + 10, '    %s' % str(result))
        for cb in self.callbacks:
            cb(result[0], result[1], result[2], result[3])
        self.callbacks = []

    def doReportFailed(self, arg):
        """
        Action method.
        """
        self.my_address = None
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.doReportFailed : %s' % arg)
        for cb in self.callbacks:
            cb('stun-failed', None, None, [])
        self.callbacks = []

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        global _StunClient
        _StunClient = None
        for d in self.deferreds.values():
            d.cancel()
        self.deferreds.clear()
        if udp.proto(self.listen_port):
            udp.proto(self.listen_port).remove_callback(self._datagram_received)
        self.destroy()

    def _datagram_received(self, datagram, address):
        self.automat('datagram-received', (datagram, address))
        return False

    def _find_random_nodes(self, tries, result_list, prev_key=None):
        if prev_key and prev_key in self.deferreds:
            self.deferreds.pop(prev_key)
        if _Debug:
            lg.out(_DebugLevel + 10, 'stun_client._find_random_nodes tries=%d result_list=%d' % (tries, len(result_list)))
        if tries <= 0 or len(result_list) >= self.minimum_needed_servers:
            if len(result_list) > 0:
                self.automat('found-some-nodes', result_list)
            else:
                self.automat('dht-nodes-not-found')
            return
        new_key = dht_service.random_key()
        d = dht_service.find_node(new_key)
        d.addCallback(lambda nodes: self._find_random_nodes(tries - 1, list(set(result_list + nodes)), new_key))
        d.addErrback(lambda x: self._find_random_nodes(tries - 1, result_list, new_key))
        self.deferreds[new_key] = d

    def _find_random_node(self):
        if _Debug:
            lg.out(_DebugLevel + 10, 'stun_client._find_random_node')
        new_key = dht_service.random_key()
        d = dht_service.find_node(new_key)
        d.addCallback(self._some_nodes_found)
        d.addErrback(self._nodes_not_found)
        # self.deferreds[new_key] = d

    def _some_nodes_found(self, nodes):
        if _Debug:
            lg.out(_DebugLevel + 10, 'stun_client._some_nodes_found : %d' % len(nodes))
        if len(nodes) > 0:
            self.automat('found-some-nodes', nodes)
        else:
            self.automat('dht-nodes-not-found')

    def _nodes_not_found(self, err):
        if _Debug:
            lg.out(_DebugLevel + 10, 'stun_client._nodes_not_found err=%s' % str(err))
        self.automat('dht-nodes-not-found')

    def _stun_port_received(self, result, node):
        self.deferreds.pop(node)
        if not isinstance(result, dict):
            return
        try:
            port = int(result['stun_port'])
            address = node.address
        except:
            if _Debug:
                lg.out(_DebugLevel, 'stun_client._stun_port_received ERROR result=%s from node: %s' % (
                    str(result), node))
            return
        self.automat('port-number-received', (address, port))

#------------------------------------------------------------------------------

def safe_stun(udp_port=None, dht_port=None, ):
    from twisted.internet.defer import Deferred
    result = Deferred()
    try:
        settings.init()
        dht_port = dht_port  # or settings.getDHTPort()
        udp_port = udp_port  # or settings.getUDPPort()
        if dht_port:
            dht_service.init(dht_port)
        d = dht_service.connect()
        if udp_port:
            udp.listen(udp_port)

        def _cb(cod, typ, ip, details):
            # A('shutdown')
            result.callback({
                'result': cod,  # 'stun-success' or 'stun-failed'
                'type': typ,
                'ip': ip,
                'details': details,
            })

        def _go(live_nodes):
            A('init', (udp_port))
            A('start', _cb)

        d.addCallback(_go)
        d.addErrback(lambda err: result.callback(dict(ip='127.0.0.1', errors=[str(err), ])))

    except Exception as exc:
        lg.exc()
        result.callback(dict(ip='127.0.0.1', errors=[str(exc), ]))
        return result
    return result


def test_safe_stun():
    from twisted.internet import reactor

    def _cb(res):
        print res
        reactor.stop()

    def _eb(err):
        print err
        reactor.stop()

    lg.set_debug_level(30)
    safe_stun().addCallbacks(_cb, _eb)
    reactor.run()

#------------------------------------------------------------------------------

def main():
    from twisted.internet import reactor
    settings.init()
    lg.set_debug_level(30)
    dht_port = settings.getDHTPort()
    udp_port = settings.getUDPPort()
    if len(sys.argv) > 1:
        dht_port = int(sys.argv[1])
    if len(sys.argv) > 2:
        udp_port = int(sys.argv[2])
    dht_service.init(dht_port)
    dht_service.connect()
    udp.listen(udp_port)

    def _cb(result, typ, ip, details):
        print result, typ, ip, details
        A('shutdown')
        reactor.stop()

    A('init', (udp_port))
    A('start', _cb)
    reactor.run()

#------------------------------------------------------------------------------


if __name__ == '__main__':
    # main()
    test_safe_stun()
