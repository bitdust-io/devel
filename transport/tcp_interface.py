#!/usr/bin/python
#tcp_interface.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: tcp_interface

This is a client side part of the TCP plug-in. 
The server side part is placed in the file tcp_process.py. 
"""

import os
import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in t_tcp.py')

from twisted.web import xmlrpc

from logs import lg

from lib import bpio

import tcp_node

#------------------------------------------------------------------------------ 

_GateProxy = None

#------------------------------------------------------------------------------ 

def proxy():
    global _GateProxy
    return _GateProxy

#------------------------------------------------------------------------------ 

class GateInterface():
    
    def init(self, xml_rpc_url_or_object):
        """
        """
        global _GateProxy
        lg.out(4, 'tcp_interface.init')
        if type(xml_rpc_url_or_object) == str:
            _GateProxy = xmlrpc.Proxy(xml_rpc_url_or_object, allowNone=True)
        else:
            _GateProxy = xml_rpc_url_or_object
        proxy().callRemote('transport_started', 'tcp')
        return True

    def shutdown(self):
        """
        """
        lg.out(4, 'tcp_interface.shutdown')
        ret = self.disconnect()
        global _GateProxy
        if _GateProxy:
            # del _GateProxy
            _GateProxy = None
        return ret

    def receive(self, options):
        lg.out(4, 'tcp_interface.receive')
        tcp_node.start_streams()
        return tcp_node.receive(options)

    def disconnect(self):
        lg.out(4, 'tcp_interface.disconnect')
        tcp_node.stop_streams()
        tcp_node.close_connections()
        return tcp_node.disconnect()
    
    def send_file(self, filename, host, description=''):
        host = host.split(':')
        host = (host[0], int(host[1]))
        return tcp_node.send(filename, host, description, False)

    def send_file_single(self, filename, host, description=''):
        host = host.split(':')
        host = (host[0], int(host[1]))
        return tcp_node.send(filename, host, description, True)
    
    def connect_to(self, host):
        """
        """
        return tcp_node.connect_to(host) 

    def disconnect_from(self, host):
        """
        """
        return tcp_node.disconnect_from(host) 
    
    def cancel_file_sending(self, transferID):
        """
        """
        return tcp_node.cancel_file_sending(transferID)

    def cancel_file_receiving(self, transferID):
        """
        """
        return tcp_node.cancel_file_receiving(transferID)
    
    def cancel_outbox_file(self, host, filename):
        """
        """
        return tcp_node.cancel_outbox_file(host, filename)

#------------------------------------------------------------------------------ 

def interface_transport_started(xmlrpcurl):
    if proxy():
        return proxy().callRemote('transport_started', 'tcp', xmlrpcurl)
    
    
def interface_receiving_started(host, new_options=None):
    if proxy():
        return proxy().callRemote('receiving_started', 'tcp', host, new_options)


def interface_receiving_failed(error_code=None):
    if proxy():
        return proxy().callRemote('receiving_failed', 'tcp', error_code)


def interface_disconnected(result=None):
    if proxy():
        return proxy().callRemote('disconnected', 'tcp', result)


def interface_register_file_sending(host, receiver_idurl, filename, size=0, description=''):
    """
    """
    if proxy():
        return proxy().callRemote('register_file_sending', 'tcp', '%s:%d' % host, receiver_idurl, filename, size, description)


def interface_register_file_receiving(host, sender_idurl, filename, size=0):
    """
    """
    if proxy():
        return proxy().callRemote('register_file_receiving', 'tcp', '%s:%d' % host, sender_idurl, filename, size)


def interface_unregister_file_sending(transfer_id, status, size=0, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('unregister_file_sending', transfer_id, status, size, error_message)


def interface_unregister_file_receiving(transfer_id, status, size=0, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('unregister_file_receiving', transfer_id, status, size, error_message)


def interface_cancelled_file_sending(host, filename, size=0, description=None, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('cancelled_file_sending', 'tcp', '%s:%d' % host, filename, size, description, error_message)


