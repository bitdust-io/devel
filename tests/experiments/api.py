#!/usr/bin/env python
# test_api.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (test_api.py) is part of BitDust Software.
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
from twisted.trial import unittest
from twisted.internet.defer import Deferred, succeed, fail
from twisted.internet import reactor

#------------------------------------------------------------------------------

try:
    from logs import lg
except:
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from system import bpio
from interface import cmd_line_json

#------------------------------------------------------------------------------


class BitDust_API_Methods(unittest.TestCase):

    def test_ping_failed(self):
        def _t(r):
            self.assertEqual(r['result'], 'ERROR')
            self.assertEqual(r['errors'][0], 'response was not received within 10 seconds')
            return r
        d = cmd_line_json.call_jsonrpc_method('ping', 'http://p2p-id.ru/atg314.xml', 10)
        d.addCallback(_t)
        return d

    def test_ping_success(self):
        def _t(r):
            self.assertEquals(r['result'], 'OK')
            self.assertEquals(len(r['items']), 1)
            return r
        d = cmd_line_json.call_jsonrpc_method('ping', 'http://p2p-id.ru/bitdust_j_vps1014.xml', 10)
        d.addCallback(_t)
        return d
