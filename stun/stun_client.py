#!/usr/bin/env python
# stun_client.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
    * :red:`timer-1sec`
    * :red:`timer-2sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import sys
import random
import re

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from automats import automat

from lib import strng
from lib import udp
from lib import net_misc
from lib import nameurl

from main import settings

from services import driver

#------------------------------------------------------------------------------

_StunClient = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _StunClient
    if _StunClient is None:
        # set automat name and starting state here
        _StunClient = StunClient(
            name='stun_client',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _StunClient.automat(event, *args, **kwargs)
    return _StunClient


class StunClient(automat.Automat):
    """
    This class implements all the functionality of the ``stun_client()`` state
    machine.
    """
    # fast = True

    timers = {
        'timer-1sec': (1.0, ['REQUEST']),
        'timer-2sec': (2.0, ['REQUEST']),
        'timer-10sec': (10.0, ['PORT_NUM?', 'REQUEST']),
    }

    MESSAGES = {
        'MSG_01': 'not found any DHT nodes',
        'MSG_02': 'not found any available stun servers',
        'MSG_03': 'timeout responding from stun servers',
    }

    def msg(self, msgid, *args, **kwargs):
        return self.MESSAGES.get(msgid, '')

    def init(self):
        self.listen_port = None
        self.callbacks = []
        self.find_nodes_attempts = 1
        self.minimum_needed_servers = 1
        self.minimum_needed_results = 1
        self.stun_nodes = []
        self.stun_servers = []
        self.stun_results = {}
        self.my_address = None
        self.deferreds = {}

    def getMyExternalAddress(self):
        return self.my_address

    def dropMyExternalAddress(self):
        self.my_address = None

    def A(self, event, *args, **kwargs):
        #---STOPPED---
        if self.state == 'STOPPED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'start':
                self.state = 'RANDOM_NODES'
                self.doAddCallback(*args, **kwargs)
                self.doDHTFindRandomNode(*args, **kwargs)
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-2sec':
                self.doStun(*args, **kwargs)
            elif event == 'timer-10sec' and not self.isSomeServersResponded(*args, **kwargs):
                self.state = 'STOPPED'
                self.doReportFailed(self.msg('MSG_03', *args, **kwargs))
                self.doClearResults(*args, **kwargs)
            elif event == 'start':
                self.doAddCallback(*args, **kwargs)
            elif event == 'datagram-received' and self.isMyIPPort(*args, **kwargs) and self.isNeedMoreResults(*args, **kwargs):
                self.doRecordResult(*args, **kwargs)
            elif event == 'port-number-received':
                self.doAddStunServer(*args, **kwargs)
                self.doStun(*args, **kwargs)
            elif ( event == 'timer-1sec' and self.isSomeServersResponded(*args, **kwargs) ) or ( event == 'datagram-received' and self.isMyIPPort(*args, **kwargs) and not self.isNeedMoreResults(*args, **kwargs) ):
                self.state = 'KNOW_MY_IP'
                self.doRecordResult(*args, **kwargs)
                self.doReportSuccess(*args, **kwargs)
                self.doClearResults(*args, **kwargs)
        #---KNOW_MY_IP---
        elif self.state == 'KNOW_MY_IP':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'start':
                self.state = 'RANDOM_NODES'
                self.doAddCallback(*args, **kwargs)
                self.doDHTFindRandomNode(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---RANDOM_NODES---
        elif self.state == 'RANDOM_NODES':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-nodes-not-found':
                self.state = 'STOPPED'
                self.doReportFailed(self.msg('MSG_01', *args, **kwargs))
            elif event == 'start':
                self.doAddCallback(*args, **kwargs)
            elif event == 'found-some-nodes' and self.isNeedMoreNodes(*args, **kwargs):
                self.doRememberStunNodes(*args, **kwargs)
                self.doDHTFindRandomNode(*args, **kwargs)
            elif event == 'found-some-nodes' and not self.isNeedMoreNodes(*args, **kwargs):
                self.state = 'PORT_NUM?'
                self.doRememberStunNodes(*args, **kwargs)
                self.doRequestStunPortNumbers(*args, **kwargs)
        #---PORT_NUM?---
        elif self.state == 'PORT_NUM?':
            if event == 'start':
                self.doAddCallback(*args, **kwargs)
            elif event == 'timer-10sec':
                self.state = 'STOPPED'
                self.doReportFailed(self.msg('MSG_02', *args, **kwargs))
                self.doClearResults(*args, **kwargs)
            elif event == 'port-number-received':
                self.state = 'REQUEST'
                self.doAddStunServer(*args, **kwargs)
                self.doStun(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        return None

    def isMyIPPort(self, *args, **kwargs):
        """
        Condition method.
        """
        try:
            datagram, address = args[0]
            command, payload = datagram
        except:
            return False
        return command == udp.CMD_MYIPPORT

    def isSomeServersResponded(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.stun_results) > 0

    def isNeedMoreResults(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.stun_results) <= self.minimum_needed_results

    def isNeedMoreNodes(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.stun_nodes) + len(*args, **kwargs) < self.minimum_needed_servers

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.listen_port = args[0]
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.doInit on port %d' % self.listen_port)
        if udp.proto(self.listen_port):
            udp.proto(self.listen_port).add_callback(self._datagram_received)
        else:
            lg.warn('udp port %s is not opened' % self.listen_port)

    def doAddCallback(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0]:
            self.callbacks.append(args[0])

    def doDHTFindRandomNode(self, *args, **kwargs):
        """
        Action method.
        """
        self._find_random_node()

    def doRememberStunNodes(self, *args, **kwargs):
        """
        Action method.
        """
        nodes = args[0]
        for node in nodes:
            if node not in self.stun_nodes:
                self.stun_nodes.append(node)

    def doRequestStunPortNumbers(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel + 4, 'stun_client.doRequestStunPortNumbers')
        for node in self.stun_nodes:
            if node.id in self.deferreds:
                lg.warn('Already requested stun_port from %r' % node)
                continue
            if _Debug:
                lg.out(_DebugLevel + 4, '    from %s' % node)
            d = node.request('stun_port')
            d.addBoth(self._stun_port_received, node)
            self.deferreds[node.id] = d

    def doAddStunServer(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel + 4, 'stun_client.doAddStunServer %s' % str(*args, **kwargs))
        self.stun_servers.append(args[0])

    def doStun(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0] is not None:
            if _Debug:
                lg.out(_DebugLevel + 4, 'stun_client.doStun to one stun_server: %s' % str(*args, **kwargs))
            udp.send_command(self.listen_port, udp.CMD_STUN, b'', *args, **kwargs)
            return
        if _Debug:
            lg.out(_DebugLevel + 4, 'stun_client.doStun to %d stun_servers' % (
                len(self.stun_servers)))  # , self.stun_servers))
        for address in self.stun_servers:
            if address is None:
                continue
            if address in list(self.stun_results.keys()):
                continue
            udp.send_command(self.listen_port, udp.CMD_STUN, b'', address)

    def doRecordResult(self, *args, **kwargs):
        """
        Action method.
        """
        if not args or args[0] is None:
            return
        try:
            datagram, address = args[0]
            command, payload = datagram
            ip, port = payload.split(b':')
            port = int(port)
        except:
            lg.exc()
        self.stun_results[address] = (ip, port)
        # if len(self.stun_results) >= len(self.stun_servers):
        #     self.automat('all-responded')

    def doClearResults(self, *args, **kwargs):
        """
        Action method.
        """
        self.stun_nodes = []
        self.stun_servers = []
        self.stun_results = {}

    def doReportSuccess(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            min_port = min([addr[1] for addr in list(self.stun_results.values())])
            max_port = max([addr[1] for addr in list(self.stun_results.values())])
            my_ip = strng.to_text(list(self.stun_results.values())[0][0])
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
            bpio.WriteTextFile(settings.ExternalIPFilename(), self.my_address[0])
            bpio.WriteTextFile(settings.ExternalUDPPortFilename(), str(self.my_address[1]))
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.doReportSuccess based on %d nodes: %s' % (
                len(self.stun_results), str(self.my_address)))
        if _Debug:
            lg.out(_DebugLevel + 4, '    %s' % str(result))
        for cb in self.callbacks:
            cb(result[0], result[1], result[2], result[3])
        self.callbacks = []

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        self.my_address = None
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.doReportFailed : %s' % args[0])
        for cb in self.callbacks:
            cb('stun-failed', None, None, [])
        self.callbacks = []

    def doDestroyMe(self, *args, **kwargs):
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
        self.automat('datagram-received', (datagram, address, ))
        return False

    def _find_random_nodes(self, tries, result_list, prev_key=None):
        if prev_key and prev_key in self.deferreds:
            self.deferreds.pop(prev_key)
        if _Debug:
            lg.out(_DebugLevel + 4, 'stun_client._find_random_nodes tries=%d result_list=%d' % (tries, len(result_list)))
        if tries <= 0 or len(result_list) >= self.minimum_needed_servers:
            if len(result_list) > 0:
                self.automat('found-some-nodes', result_list)
            else:
                self.automat('dht-nodes-not-found')
            return
        from dht import dht_service
        new_key = dht_service.random_key()
        d = dht_service.find_node(new_key)
        d.addCallback(lambda nodes: self._find_random_nodes(tries - 1, list(set(result_list + nodes)), new_key))
        d.addErrback(lambda x: self._find_random_nodes(tries - 1, result_list, new_key))
        self.deferreds[new_key] = d

    def _find_random_node(self):
        if _Debug:
            lg.out(_DebugLevel + 4, 'stun_client._find_random_node')
        from dht import dht_service
        new_key = dht_service.random_key()
        d = dht_service.find_node(new_key)
        d.addCallback(self._some_nodes_found)
        d.addErrback(self._nodes_not_found)
        # self.deferreds[new_key] = d

    def _some_nodes_found(self, nodes):
        if _Debug:
            lg.out(_DebugLevel + 4, 'stun_client._some_nodes_found : %r' % nodes)
        if len(nodes) > 0:
            self.automat('found-some-nodes', nodes)
        else:
            self.automat('dht-nodes-not-found')

    def _nodes_not_found(self, err):
        if _Debug:
            lg.out(_DebugLevel, 'stun_client._nodes_not_found err=%s' % str(err))
        self.automat('dht-nodes-not-found')

    def _stun_port_received(self, result, node):
        if _Debug:
            lg.out(_DebugLevel, 'stun_client._stun_port_received  %r from %s' % (result, node, ))
        self.deferreds.pop(node.id, None)
        if not isinstance(result, dict):
            return
        try:
            port = int(result['stun_port'])
            address = node.address
        except:
            lg.exc()
            return
        if _Debug:
            lg.out(_DebugLevel, '        new stun port server found  %s:%s' % (address, port, ))
        self.automat('port-number-received', (address, port))

#------------------------------------------------------------------------------

def udp_dht_stun(udp_port=None, dht_port=None, result_defer=None):
    if not driver.is_on('service_my_ip_port'):
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.udp_dht_stun   SKIP because service_my_ip_port() is not started')
        if result_defer:
            result_defer.errback(Exception('service_my_ip_port() is not started'))
        return False

    from dht import dht_service

    if dht_service.node()._joinDeferred and not dht_service.node()._joinDeferred.called:
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.udp_dht_stun   SKIP and run later because dht_service is still joining the network')
        dht_service.node()._joinDeferred.addCallback(lambda ok: udp_dht_stun(udp_port=udp_port, dht_port=dht_port, result_defer=result_defer))
        if result_defer:
            dht_service.node()._joinDeferred.addErrback(result_defer.errback)
        return True

    dht_port = dht_port or settings.getDHTPort()
    udp_port = udp_port or settings.getUDPPort()
    if dht_port:
        dht_service.init(dht_port)
    d = dht_service.connect()
    if udp_port:
        udp.listen(udp_port)

    def _cb(cod, typ, ip, details):
        # A('shutdown')
        ret = {
            'result': cod,  # 'stun-success' or 'stun-failed'
            'type': typ,
            'ip': ip,
            'details': details,
        }
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.udp_dht_stun   result : %r' % ret)
        result_defer.callback(ret)
        return None

    def _go(live_nodes):
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.udp_dht_stun   GO with nodes: %r' % live_nodes)
        A('init', udp_port)
        A('start', _cb)

    d.addCallback(_go)
    if result_defer:
        d.addErrback(result_defer.errback)
        # d.addErrback(lambda err: result_defer.callback(dict(ip='127.0.0.1', errors=[str(err), ])))
    return True


def http_stun(result_defer=None):
    from userid import known_servers
    identity_servers = known_servers.by_host()
    if not identity_servers:
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.http_stun   SKIP, no known identity servers found')
        return False
    one_host = random.choice(list(identity_servers.keys()))
    one_port = identity_servers[one_host][0]
    one_url = nameurl.UrlMake('http', one_host, one_port)
    if _Debug:
        lg.out(_DebugLevel, 'stun_client.http_stun   GO with one node : %r' % one_url)

    def _check_body(html_response):
        ret = {
            'result': 'stun-failed',
            'type': None,
            'ip': None,
            'details': ['unknown client host from response', ],
        }
        mo = re.search(b'\<\!\-\-CLIENT_HOST\=([\d\.]+):(\d+)\-\-\>', html_response)
        if not mo:
            if _Debug:
                lg.out(_DebugLevel, 'stun_client.http_stun   FAILED : unknown client host from response')
            if result_defer:
                result_defer.callback(ret)      
            return None
        ret = {
            'result': 'stun-success',
            'type': 'unknown',
            'ip': strng.to_text(mo.group(1)),
            'details': [],
        }
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.http_stun   SUCCESS : %r' % ret)
        if result_defer:
            result_defer.callback(ret)
        return None

    def _request_failed(err):
        if _Debug:
            lg.out(_DebugLevel, 'stun_client.http_stun   FAILED : %r' % err)
        ret = {
            'result': 'stun-failed',
            'type': None,
            'ip': None,
            'details': [err.getErrorMessage(), ],
        }
        if result_defer:
            result_defer.callback(ret)
        return None

    d = net_misc.getPageTwisted(one_url)
    d.addCallback(_check_body)
    d.addErrback(_request_failed)
    return True


def safe_stun(udp_port=None, dht_port=None, result_defer=None):
    from twisted.internet.defer import Deferred
    result = result_defer or Deferred()

    def _check_response(response):
        if response.get('result') == 'stun-success':
            result.callback(response)
            return None
        http_stun(result_defer=result)
        return None

    def _fallback(err):
        http_stun(result_defer=result)
        return None

    settings.init()
    first_result = Deferred()
    first_result.addCallback(_check_response)
    first_result.addErrback(_fallback)
    udp_dht_stun(udp_port, dht_port, result_defer=first_result)

    return result


def test_safe_stun():
    from twisted.internet import reactor  # @UnresolvedImport

    def _cb(res):
        print(res)
        reactor.stop()  # @UndefinedVariable

    def _eb(err):
        print(err)
        reactor.stop()  # @UndefinedVariable

    lg.set_debug_level(30)
    safe_stun().addCallbacks(_cb, _eb)
    reactor.run()  # @UndefinedVariable

#------------------------------------------------------------------------------

def main():
    from twisted.internet import reactor  # @UnresolvedImport
    from dht import dht_service
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
        print(result, typ, ip, details)
        A('shutdown')
        reactor.stop()  # @UndefinedVariable

    A('init', (udp_port))
    A('start', _cb)
    reactor.run()  # @UndefinedVariable

#------------------------------------------------------------------------------


if __name__ == '__main__':
    from twisted.internet.defer import setDebugging
    setDebugging(True)
    # main()
    test_safe_stun()
