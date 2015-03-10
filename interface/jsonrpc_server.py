#!/usr/bin/python
#jsonrpc_server.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: jsonrpc_server
"""

from twisted.internet import reactor
from twisted.web import server

if __name__ == '__main__':
    import sys, os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from lib.fastjsonrpc.server import JSONRPCServer 

#------------------------------------------------------------------------------ 

from logs import lg

import api

#------------------------------------------------------------------------------ 

def init():
    lg.out(4, 'jsonrpc_server.init')
    from main import settings
    from system import bpio
    port = settings.DefaultJsonRPCPort()
    bpio.AtomicWriteFile(settings.LocalJsonRPCPortFilename(), str(port))
    reactor.listenTCP(port, server.Site(BitDustJsonRPCServer()))
    lg.out(4, '    started on port %d' % port)

#------------------------------------------------------------------------------ 

class BitDustJsonRPCServer(JSONRPCServer):
    def jsonrpc_stop(self):
        return api.stop()

    def jsonrpc_restart(self):
        return api.restart()
    
    def jsonrpc_backups_list(self):
        return {'backups': map(lambda x: {'data': '~%s~' % str(x)}, api.backups_list())}
    
#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    lg.set_debug_level(20)
    init()
    reactor.run()
    
        
