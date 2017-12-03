#!/usr/bin/python
# jsonrpc_client.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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


if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from twisted.internet import reactor

from main import settings

from lib.fastjsonrpc.client import Proxy

#------------------------------------------------------------------------------


def output(value):
    import pprint
    pprint.pprint(value)
    reactor.stop()

#------------------------------------------------------------------------------

def main():
    proxy = Proxy('http://localhost:%d' % settings.DefaultJsonRPCPort())
    # proxy.callRemote('ping', 'http://p2p-id.ru/bitdust_j_vps1014.xml').addBoth(output)
    # proxy.callRemote('config_set', 'logs/debug-level', '20').addBoth(output)
    # proxy.callRemote('filemanager_list', 'path=/').addBoth(output)
    # proxy.callRemote('keys_list').addBoth(output)
    # proxy.callRemote('key_create', 'ccc2').addBoth(output)
    # proxy.callRemote('key_get', key_id='cool$testveselin@p2p-id.ru', include_private=True).addBoth(output)
    proxy.callRemote('event_send', 'existing-customer-accepted', '{"idurl": "abc123@def.net"}').addBoth(output)
    reactor.run()


if __name__ == '__main__':
    main()
