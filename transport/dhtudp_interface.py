#!/usr/bin/python
#dhtudp_interface.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: dhtudp_interface

"""

import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in dhtudp_interface.py')

from twisted.web import xmlrpc
from twisted.internet import protocol
from twisted.internet.defer import Deferred, succeed

import lib.dhnio as dhnio
import lib.nameurl as nameurl

import dhtudp_node
import dhtudp_session

#------------------------------------------------------------------------------ 

_GateProxy = None

def proxy():
    global _GateProxy
    return _GateProxy

#------------------------------------------------------------------------------ 

def idurl_to_id(idurl):
    """
    """
    proto, host, port, filename = nameurl.UrlParse(idurl)
    assert proto == 'http'
    user_id = filename.replace('.xml', '') + '@' + host
    if port:
        user_id += ':' + port
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
        dhnio.Dprint(4, 'dhtudp_interface.init')
        _GateProxy = xmlrpc.Proxy(gate_xml_rpc_url, allowNone=True)
        _GateProxy.callRemote('transport_started', 'dhtudp')
        return True

    def shutdown(self):
        """
        """
        global _GateProxy
        dhnio.Dprint(4, 'dhtudp_interface.shutdown')
        ret = self.disconnect()
        if _GateProxy:
            del _GateProxy
            _GateProxy = None
        return ret

    def receive(self, options):
        """
        """
        dhtudp_node.A('go-online', options)
        # dhnio.Dprint(8, 'dhtudp_interface.receive')
        return True

    def disconnect(self):
        """
        """
        dhtudp_node.A('go-offline')
        # dhnio.Dprint(8, 'dhtudp_interface.disconnect')
        return succeed(True)

    def send_file(self, filename, host, description='', single=False):
        """
        """
        result_defer = Deferred()
        if dhtudp_node.A().state not in ['LISTEN', 'DHT_READ',]:
            result_defer.callback(False)
            return result_defer
        s = dhtudp_session.get_by_peer_id(host)
        if s:
            s.stream.append_outbox_file(filename, description, result_defer, single)
        else:
            dhtudp_session.add_pending_outbox_file(filename, host, description, result_defer, single)
            dhtudp_node.A('connect', host)
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
        dhnio.Dprint(12, 'dhtudp_interface.connect %s' % host)
        dhtudp_node.A('connect', host)

    def disconnect_from_host(self, host):
        """
        """

    def cancel_file_sending(self, transferID):
        """
        """
        for sess in dhtudp_session.sessions().values():
            for out_file in sess.stream.outboxFiles.values():
                if out_file.transfer_id and out_file.transfer_id == transferID:
                    out_file.cancel()
                    return True
        return False                
                
    def cancel_file_receiving(self, transferID):
        """
        """
        for sess in dhtudp_session.sessions().values():
            for in_file in sess.stream.inboxFiles.values():
                if in_file.transfer_id and in_file.transfer_id == transferID:
                    dhnio.Dprint(6, 'dhtudp_interface.cancel_file_receiving transferID=%s   want to close session' % transferID)
                    sess.automat('shutdown')
                    return True
        return False

    def cancel_outbox_file(self, host, filename):
        """
        """
        for sess in dhtudp_session.sessions().values():
            for fn, descr, result_defer, single in sess.stream.outboxQueue:
                if fn == filename and sess.peer_id == host:
                    dhnio.Dprint(6, 'dhtudp_interface.cancel_outbox_file    host=%s  want to close session' % host)
                    sess.automat('shutdown')
                    return True
        return False

#------------------------------------------------------------------------------ 
    
def interface_transport_started():
    """
    """
    if proxy():
        return proxy().callRemote('transport_started', 'dhtudp')


def interface_receiving_started(host, new_options=None):
    """
    """
    if proxy():
        return proxy().callRemote('receiving_started', 'dhtudp', host, new_options)


def interface_receiving_failed(error_code=None):
    """
    """
    if proxy():
        return proxy().callRemote('receiving_failed', 'dhtudp', error_code)


def interface_disconnected(result=None):
    """
    """
    if proxy():
        return proxy().callRemote('disconnected', 'dhtudp', result)
    

def interface_register_file_sending(host, receiver_idurl, filename, size, description=''):
    """
    """
    if proxy():
        return proxy().callRemote('register_file_sending', 'dhtudp', host, receiver_idurl, filename, size, description)


def interface_register_file_receiving(host, sender_idurl, filename, size):
    """
    """
    if proxy():
        return proxy().callRemote('register_file_receiving', 'dhtudp', host, sender_idurl, filename, size)


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


def interface_cancelled_file_sending(host, filename, size, description=None, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('cancelled_file_sending', 'dhtudp', host, filename, size, description, error_message)


def interface_cancelled_file_receiving(host, filename, size, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('cancelled_file_receiving', 'dhtudp', host, filename, size, error_message)


