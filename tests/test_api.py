
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


