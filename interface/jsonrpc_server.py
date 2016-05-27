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

import time
import pprint
import traceback

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.web import server

if __name__ == '__main__':
    import sys, os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from lib.fastjsonrpc.server import JSONRPCServer
from lib.fastjsonrpc.jsonrpc import JSONRPCError

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
    # TODO: add protection: accept connections only from local host: 127.0.0.1
    reactor.listenTCP(port, server.Site(BitDustJsonRPCServer()))
    lg.out(4, '    started on port %d' % port)

#------------------------------------------------------------------------------ 

class BitDustJsonRPCServer(JSONRPCServer):
    
    def _register_execution(self, request_dict, result):
        result['execution'] = '%3.6f' % (time.time() - request_dict['_executed'])
        lg.out(4, "jsontpc_server._register_execution : %s sec. ,  started at %d" % (result['execution'], request_dict['_executed']))
        return result

    def _convert_filemanager_response(self, result):
        if 'status' not in result:
            result['status'] = 'OK'
        if 'result' in result and isinstance(result['result'], dict):
            if 'success' in result['result'] and not result['result']['success']:
                result['status'] = 'ERROR'
                result['errors'] = [result['result']['error'],]
                del result['result']
            else:
                result['result'] = [result['result'],]
        return result
    
    def _catch_filemanager_methods(self, request_dict):
        if not request_dict['method'].startswith('filemanager_'):
            return None
        try:
            fm_method = request_dict['method'].replace('filemanager_', '')
            fm_request = {}
            params = [] if 'params' not in request_dict else request_dict['params']
            fm_request['params'] = {
                i[0]:i[1] for i in map(lambda p: p.split("=", 1), params)}
            fm_request['params']['mode'] = fm_method
            request_dict = {'_executed': time.time(),}
        except Exception as exc:
            lg.exc()
            return api.ERROR(exc.message)
        try:
            fm_result = api.filemanager(fm_request)
            if isinstance(fm_result, Deferred):
                fm_result.addCallback(self._convert_filemanager_response)
            else:
                fm_result = self._convert_filemanager_response(fm_result)
        except Exception as exc:
            lg.exc()
            fm_result = api.ERROR(exc.message)
        return fm_result
    
    def _callMethod(self, request_dict):
        lg.out(12, 'jsontpc_server._callMethod:\n%s' % pprint.pformat(request_dict))
        request_dict['_executed'] = time.time()
        try:
            fm_result = self._catch_filemanager_methods(request_dict)
            if fm_result is None:
                result = fm_result or JSONRPCServer._callMethod(self, request_dict)
            else:
                result = fm_result
        except JSONRPCError as exc:
            result = api.ERROR(exc.strerror)
        except Exception as exc:
            result = api.ERROR(traceback.format_exc(), message=exc.message)
        if isinstance(result, Deferred):
            result.addCallback(
               lambda result: self._register_execution(request_dict, result))
        else:
            result = self._register_execution(request_dict, result)
        return result
        
    def jsonrpc_stop(self):
        return api.stop()

    def jsonrpc_show(self):
        return api.show()

    def jsonrpc_restart(self, show=False):
        return api.restart(show)
    
    def jsonrpc_reconnect(self):
        return api.reconnect()

    def jsonrpc_filemanager(self, json_request):
        return api.filemanager(json_request)

    def jsonrpc_backups_update(self):
        return api.backups_update()

    def jsonrpc_backups_list(self):
        return api.backups_list()

    def jsonrpc_backups_id_list(self):
        return api.backups_id_list()
        
    def jsonrpc_backup_start_path(self, path):
        return api.backup_start_path(path)

    def jsonrpc_backup_start_id(self, pathID):
        return api.backup_start_id(pathID)
    
    def jsonrpc_backup_dir_add(self, dirpath):
        return api.backup_dir_add(dirpath)
    
    def jsonrpc_backup_file_add(self, filepath):
        return api.backup_file_add(filepath)

    def jsonrpc_backup_tree_add(self, dirpath):
        return api.backup_tree_add(dirpath)

    def jsonrpc_backup_delete_local(self, backupID):
        return api.backup_delete_local(backupID)

    def jsonrpc_backup_delete_id(self, pathID):
        return api.backup_delete_id(pathID)

    def jsonrpc_backup_delete_path(self, path):
        return api.backup_delete_path(path)
    
    def jsonrpc_restore_single(self, pathID_or_backupID_or_localPath, destinationPath=None):
        return api.restore_single(pathID_or_backupID_or_localPath, destinationPath)
    
    def jsonrpc_backups_queue(self):
        return api.backups_queue()
    
    def jsonrpc_backups_running(self):
        return api.backups_running()
    
    def jsonrpc_backup_cancel_pending(self, path_id):
        return api.backup_cancel_pending(path_id)

    def jsonrpc_backup_abort_running(self, backup_id):
        return api.backup_abort_running(backup_id)

    def jsonrpc_restores_running(self):
        return api.restores_running()
    
    def jsonrpc_restore_abort(self, backup_id):
        return api.restore_abort(backup_id)

    def jsonrpc_suppliers_list(self):
        return api.suppliers_list()

    def jsonrpc_supplier_replace(self, index_or_idurl):
        return api.supplier_replace(index_or_idurl)

    def jsonrpc_supplier_change(self, index_or_idurl, new_idurl):
        return api.supplier_change(index_or_idurl, new_idurl)

    def jsonrpc_suppliers_ping(self):
        return api.suppliers_ping()
 
    def jsonrpc_customers_list(self):
        return api.customers_list()

    def jsonrpc_customer_reject(self, idurl):
        return api.customer_reject(idurl)

    def jsonrpc_customers_ping(self):
        return api.customers_ping()
 
    def jsonrpc_space_donated(self):
        return api.space_donated()
 
    def jsonrpc_space_consumed(self):
        return api.space_consumed()

    def jsonrpc_automats_list(self):
        return api.automats_list()

    def jsonrpc_ping(self, idurl, timeout=10):
        return api.ping(str(idurl), timeout)

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
    
        
