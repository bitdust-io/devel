#!/usr/bin/python
#api.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: xmlrpc_server
"""

from twisted.internet import reactor
from twisted.web import server
from twisted.web import xmlrpc

#------------------------------------------------------------------------------ 

from logs import lg

import api

#------------------------------------------------------------------------------ 

def init():
    lg.out(4, 'xmlrpc_server.init')
    from main import settings
    port = settings.DefaultXMLRPCPort()
    reactor.listenTCP(port, server.Site(XMLRPCServer()))

#------------------------------------------------------------------------------ 

class XMLRPCServer(xmlrpc.XMLRPC):
    def __init__(self):
        xmlrpc.XMLRPC.__init__(self, allowNone=True)
        self.methods = {
            'stop':                     api.stop,
            'restart':                  api.restart,
            'show':                     api.show,
            
            'backups_list':             api.backups_list,
            'backups_id_list':          api.backups_id_list,
            'backup_start_id':          api.backup_start_id,
            'backup_start_path':        api.backup_start_path, 
            'backup_dir_add':           api.backup_dir_add,
            'backup_file_add':          api.backup_file_add,
            'backup_tree_add':          api.backup_tree_add,
#            'backup_delete_local':      api.backup_delete_local,
#            'backup_delete_id':         api.backup_delete_id,
#            'backup_delete_path':       api.backup_delete_path,
#            'backups_update':           api.backups_update,
#            
#            'restore_single':           api.restore_single,

            'list_messages':            api.list_messages,
            'send_message':             api.send_message,
            
            'find_peer_by_nickname':    api.find_peer_by_nickname,
            'list_correspondents':      api.list_correspondents,
        }

    def lookupProcedure(self, procedurePath):
        try:
            return self.methods[procedurePath]
        except KeyError, e:
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                        "procedure %s not found" % procedurePath)

    def listProcedures(self):
        return self.methods.keys()    

        
