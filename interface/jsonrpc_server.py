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

import pprint

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
    def _callMethod(self, request_dict):
        lg.out(6, 'jsontpc_server._callMethod:\n%s' % pprint.pformat(request_dict))
        return JSONRPCServer._callMethod(self, request_dict)
    
    def jsonrpc_stop(self):
        return api.stop()

    def jsonrpc_show(self):
        return api.show()

    def jsonrpc_restart(self, show=False):
        return api.restart(show)

    def jsonrpc_backups_list(self):
        return { 'backups': map(
                    lambda x: {'data': '<%s>' % str(x)},
                        api.backups_list()) }
        
    def jsonrpc_config_list(self, sort=False):
        return api.config_list(sort)

    def jsonrpc_config_get(self, key, default=None):
        return api.config_get(key, default)

    def jsonrpc_config_set(self, key, value, typ=None):
        return api.config_set(key, value, typ)
    
    def jsonrpc_list_messages(self):
        return api.list_messages()
    
    def jsonrpc_send_message(self, recipient, message_body):
        return api.send_message(recipient, message_body)
    
    def jsonrpc_list_correspondents(self):
        return api.list_correspondents()
    
    def jsonrpc_add_correspondent(self, idurl, nickname=''):
        return api.add_correspondent(idurl, nickname)

    def jsonrpc_remove_correspondent(self, idurl):
        return api.remove_correspondent(idurl)

    def jsonrpc_find_peer_by_nickname(self, nickname):
        return api.find_peer_by_nickname(nickname)
    
    # def jsonrpc_:
    #     return api.
    
#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    lg.set_debug_level(20)
    init()
    reactor.run()
    
        
