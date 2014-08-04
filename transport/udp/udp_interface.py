#!/usr/bin/python
#udp_interface.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: udp_interface

"""

import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in udp_interface.py')

from twisted.web import xmlrpc
from twisted.internet import protocol
from twisted.internet.defer import Deferred, succeed

from logs import lg

from lib import bpio
from lib import nameurl

import udp_node
import udp_session

#------------------------------------------------------------------------------ 

_GateProxy = None

#------------------------------------------------------------------------------ 

def proxy():
    global _GateProxy
    return _GateProxy

def idurl_to_id(idurl):
    """
    """
    proto, host, port, filename = nameurl.UrlParse(idurl)
    assert proto == 'http'
    user_id = filename.replace('.xml', '') + '@' + host
    if port and port not in ['80', 80, ]:
        user_id += ':%s' % str(port)
    return user_id

def id_to_idurl(user_id):
    try:
        filename, host = user_id.split('@')
        filename += '.xml'
    except:
        return None
    return 'http://%s/%s' % (host, filename) 

#------------------------------------------------------------------------------ 

class GateInterface():

    def init(self, gate_xml_rpc_url):
        """
        """
        global _GateProxy
        lg.out(4, 'udp_interface.init')
        _GateProxy = xmlrpc.Proxy(gate_xml_rpc_url, allowNone=True)
        _GateProxy.callRemote('transport_started', 'udp')
        return True

    def shutdown(self):
        """
        """
        global _GateProxy
        lg.out(4, 'udp_interface.shutdown')
        ret = self.disconnect()
        if _GateProxy:
            del _GateProxy
            _GateProxy = None
        return ret

    def receive(self, options):
        """
        """
        udp_node.A('go-online', options)
        # lg.out(8, 'udp_interface.receive')
        return True

    def disconnect(self):
        """
        """
        udp_node.A('go-offline')
        # lg.out(8, 'udp_interface.disconnect')
        return succeed(True)

    def send_file(self, filename, host, description='', single=False):
        """
        """
        result_defer = Deferred()
        if udp_node.A().state not in ['LISTEN', 'DHT_READ',]:
            result_defer.callback(False)
            return result_defer
        s = udp_session.get_by_peer_id(host)
        if s:
            s.file_queue.append_outbox_file(filename, description, result_defer, single)
        else:
            udp_session.add_pending_outbox_file(filename, host, description, result_defer, single)
            udp_node.A('connect', host)
        return result_defer

    def send_file_single(self, filename, host, description='', single=True):
        """
        """
        return self.send_file(self, filename, host, description, single)

    def connect_to_host(self, host=None, idurl=None):
        """
        """
        if not host:
            host = idurl_to_id(idurl)
        lg.out(12, 'udp_interface.connect %s' % host)
        udp_node.A('connect', host)

    def disconnect_from_host(self, host):
        """
        """

    def cancel_outbox_file(self, host, filename):
        """
        """
        ok = False
        for sess in udp_session.sessions().values():
            if sess.peer_id != host:
                continue
            i = 0
            while i < len(sess.file_queue.outboxQueue):
                fn, descr, result_defer, single = sess.file_queue.outboxQueue[i]
                if fn == filename:
                    lg.out(14, 'udp_interface.cancel_outbox_file removed %s in %s' % (os.path.basename(fn), sess))
                    sess.file_queue.outboxQueue.pop(i)
                    ok = True
                else:
                    i += 1
        udp_session.remove_pending_outbox_file(host, filename)
#        for fn, descr, result_defer, single in sess.file_queue.outboxQueue:
#            if fn == filename and sess.peer_id == host:
#                lg.out(6, 'udp_interface.cancel_outbox_file    host=%s  want to close session' % host)
#                sess.automat('shutdown')
#                return True
        return ok

    def cancel_file_sending(self, transferID):
        """
        """
        for sess in udp_session.sessions().values():
            for out_file in sess.file_queue.outboxFiles.values():
                if out_file.transfer_id and out_file.transfer_id == transferID:
                    out_file.cancel()
                    return True
        return False                
                
    def cancel_file_receiving(self, transferID):
        """
        """
        for sess in udp_session.sessions().values():
            for in_file in sess.file_queue.inboxFiles.values():
                if in_file.transfer_id and in_file.transfer_id == transferID:
                    lg.out(6, 'udp_interface.cancel_file_receiving transferID=%s   want to close session' % transferID)
                    sess.automat('shutdown')
                    return True
        return False

#------------------------------------------------------------------------------ 
    
def interface_transport_started():
    """
    """
    if proxy():
        return proxy().callRemote('transport_started', 'udp')


def interface_receiving_started(host, new_options=None):
    """
    """
    if proxy():
        return proxy().callRemote('receiving_started', 'udp', host, new_options)


def interface_receiving_failed(error_code=None):
    """
    """
    if proxy():
        return proxy().callRemote('receiving_failed', 'udp', error_code)


def interface_disconnected(result=None):
    """
    """
    if proxy():
        return proxy().callRemote('disconnected', 'udp', result)
    

def interface_register_file_sending(host, receiver_idurl, filename, size, description=''):
    """
    """
    if proxy():
        return proxy().callRemote('register_file_sending', 'udp', host, receiver_idurl, filename, size, description)


def interface_register_file_receiving(host, sender_idurl, filename, size):
    """
    """
    if proxy():
        return proxy().callRemote('register_file_receiving', 'udp', host, sender_idurl, filename, size)
    else:
        lg.warn('proxy is none')


def interface_unregister_file_sending(transfer_id, status, bytes_sent, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('unregister_file_sending', transfer_id, status, bytes_sent, error_message)


def interface_unregister_file_receiving(transfer_id, status, bytes_received, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('unregister_file_receiving', transfer_id, status, bytes_received, error_message)
    else:
        lg.warn('proxy is none')


def interface_cancelled_file_sending(host, filename, size, description=None, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('cancelled_file_sending', 'udp', host, filename, size, description, error_message)


def interface_cancelled_file_receiving(host, filename, size, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('cancelled_file_receiving', 'udp', host, filename, size, error_message)


