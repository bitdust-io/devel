#!/usr/bin/python
# jsonrpc_client.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (jsonrpc_client.py) is part of BitDust Software.
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
#
#
#
#

"""
..

module:: jsonrpc_client
"""

from __future__ import absolute_import
from __future__ import print_function
import time
import pprint

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from twisted.internet import reactor  # @UnresolvedImport

from main import settings

from lib.fastjsonrpc.client import Proxy

#------------------------------------------------------------------------------


def output(value):
    pprint.pprint(value)
    reactor.stop()

#------------------------------------------------------------------------------

def loop_network_connected():
    proxy = Proxy(b'http://localhost:%d' % settings.DefaultJsonRPCPort())

    def _call():
        print('_call', time.asctime())
        proxy.callRemote('network_connected', 3).addBoth(_loop)

    def _loop(x=None):
        reason = 'unknown'
        try:
            status = x['status']
            reason = x.get('reason')
        except:
            status = 'FAILED'
        print('_loop', 'status:', status, '   reason:', reason, ' ...')
        if status == 'OK':
            reactor.callLater(3, _call)
        else:
            reactor.callLater(1, _call)

    reactor.callLater(0, _loop)
    reactor.run()

#------------------------------------------------------------------------------

def loop_event_listen():
    proxy = Proxy(b'http://localhost:%d' % settings.DefaultJsonRPCPort())

    def _loop(x=None):
        if x:
            for evt in x.get('result', []):
                print('EVENT:', evt['id'])
                # pprint.pprint(evt)
        else:
            print('.', end=' ')
        d = proxy.callRemote('events_listen', 'test_event_consumer')
        d.addCallback(_loop)
        d.addErrback(lambda err: reactor.callLater(1, _loop))

    reactor.callLater(0, _loop)
    reactor.run()

#------------------------------------------------------------------------------

def test():
    proxy = Proxy(b'http://localhost:%d' % settings.DefaultJsonRPCPort())
    # proxy.callRemote('ping', 'http://p2p-id.ru/bitdust_j_vps1014.xml').addBoth(output)
    # proxy.callRemote('config_set', 'logs/debug-level', '20').addBoth(output)
    # proxy.callRemote('filemanager_list', 'path=/').addBoth(output)
    # proxy.callRemote('keys_list').addBoth(output)
    # proxy.callRemote('key_create', 'ccc2').addBoth(output)
    # proxy.callRemote('nickname_set', 'veselin').addBoth(output)
    # proxy.callRemote('key_get', key_id='cool$testveselin@p2p-id.ru', include_private=True).addBoth(output)
    # proxy.callRemote('event_send', 'existing-customer-accepted', '{"idurl": "abc123@def.net"}').addBoth(output)
    proxy.callRemote('automats_list').addBoth(output)
    reactor.run()

#------------------------------------------------------------------------------


if __name__ == '__main__':
    test()
    # loop_network_connected()
    # loop_event_listen()
