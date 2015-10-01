#!/usr/bin/python
#proxy_interface.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: proxy_interface

This is a client side part of the PROXY transport plug-in. 
"""

#------------------------------------------------------------------------------ 

_Debug = True

#------------------------------------------------------------------------------ 


from twisted.web import xmlrpc
from twisted.internet.defer import succeed, fail, Deferred

from logs import lg

from main import settings

from contacts import identitycache

import proxy_receiver
import proxy_sender

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
        if _Debug:
            lg.out(4, 'proxy_interface.init')
        if type(xml_rpc_url_or_object) == str:
            _GateProxy = xmlrpc.Proxy(xml_rpc_url_or_object, allowNone=True)
        else:
            _GateProxy = xml_rpc_url_or_object
        proxy_receiver.A('init')
        proxy_sender.A('init')
        proxy().callRemote('transport_initialized', 'proxy')
        return True

    def shutdown(self):
        """
        """
        if _Debug:
            lg.out(4, 'proxy_interface.shutdown')
        ret = self.disconnect()
        proxy_receiver.A('shutdown')
        proxy_sender.A('shutdown')
        global _GateProxy
        if _GateProxy:
            _GateProxy = None
        return ret

    def connect(self, options):
        """
        """
        if _Debug:
            lg.out(4, 'proxy_interface.connect %s' % str(options))
        if settings.enablePROXYreceiving():
            proxy_receiver.A('start')
        if settings.enablePROXYsending():
            proxy_sender.A('start')
        return succeed(True)

    def disconnect(self):
        """
        """
        if _Debug:
            lg.out(4, 'proxy_interface.disconnect')
        proxy_receiver.A('stop')
        proxy_sender.A('stop')
        return succeed(True)
    
    def build_contacts(self, id_obj):
        """
        """
        if not proxy_receiver.A().router_identity:
            # if not yet found one node to route your traffic - do nothing
            if _Debug:
                lg.out(4, 'proxy_interface.build_contacts SKIP, router not yet found')
            return []
        # switch contacts - use router contacts instead of my 
        # he will get all packets sent to my and redirect to my
        result = proxy_receiver.A().router_identity.getContacts()
        if _Debug:
            lg.out(4, 'proxy_interface.build_contacts %s : %s' % (
                proxy_receiver.A().router_identity.getIDName(), str(result)))
        return result
    
    def verify_contacts(self, id_obj):
        """
        Check if router is ready and his contacts exists in that identity. 
        """
        if not proxy_receiver.A().router_idurl or not proxy_receiver.A().router_identity:
            # if not yet found one node to route your traffic - do nothing
            if _Debug:
                lg.out(4, 'proxy_interface.verify_contacts returning True : router not yet found')
            return True
        result = Deferred()
        def _finish_verification(res):
            cached_id = identitycache.FromCache(proxy_receiver.A().router_idurl)
            if not cached_id:
                if _Debug:
                    lg.out(4, 'proxy_interface.verify_contacts return False: router identity is not cached')
                res.callback(False) 
                return
            if cached_id.serialize() != proxy_receiver.A().router_identity.serialize():
                if _Debug:
                    lg.out(4, 'proxy_interface.verify_contacts return False: cached copy is different')
                    lg.out(20, '\n%s\n' % cached_id.serialize())
                    lg.out(20, '\n%s\n' % proxy_receiver.A().router_identity.serialize())
                res.callback(False) 
                return
            router_contacts = proxy_receiver.A().router_identity.getContacts()
            if len(router_contacts) != id_obj.getContactsNumber():
                if _Debug:
                    lg.out(4, 'proxy_interface.is_valid return False: router contacts is different') 
                res.callback(False) 
                return
            for proto, contact in id_obj.getContactsByProto().items():
                if proto not in router_contacts.keys():
                    if _Debug:
                        lg.out(4, 'proxy_interface.is_valid return False: [%s] is not present in router contacts' % proto) 
                    res.callback(False) 
                    return
                if router_contacts[proto] != contact:
                    if _Debug:
                        lg.out(4, 'proxy_interface.is_valid return False: [%s] contact is different in router id' % proto) 
                    res.callback(False) 
                    return
            # TODO: probably need to check the order also ... 
            res.callback(True) 
            return
        d = identitycache.immediatelyCaching(proxy_receiver.A().router_idurl)
        d.addCallback(lambda src: _finish_verification(result))
        d.addErrback(lambda err: result.callback(False))
        return result
    
    def send_file(self, remote_idurl, filename, host, description='', single=False):
        """
        """
        if _Debug:
            lg.out(4, 'proxy_interface.send_file')
        proxy_sender.A('send-file', (remote_idurl, filename, host, description, single))
        return succeed(True)

    def send_file_single(self, remote_idurl, filename, host, description='', single=True):
        return self.send_file(remote_idurl, filename, host, description, single)

#------------------------------------------------------------------------------ 

def interface_transport_initialized(xmlrpcurl):
    if proxy():
        return proxy().callRemote('transport_initialized', 'proxy', xmlrpcurl)
    lg.warn('transport_proxy is not ready')
    return fail('transport_proxy is not ready')
    
    
def interface_receiving_started(host, new_options=None):
    if proxy():
        return proxy().callRemote('receiving_started', 'proxy', host, new_options)
    lg.warn('transport_proxy is not ready')
    return fail('transport_proxy is not ready')


def interface_receiving_failed(error_code=None):
    if proxy():
        return proxy().callRemote('receiving_failed', 'proxy', error_code)
    lg.warn('transport_proxy is not ready')
    return fail('transport_proxy is not ready')


def interface_disconnected(result=None):
    if proxy():
        return proxy().callRemote('disconnected', 'proxy', result)
    lg.warn('transport_proxy is not ready')
    return fail('transport_proxy is not ready')


def interface_register_file_sending(host, receiver_idurl, filename, size=0, description=''):
    """
    """
    if proxy():
        return proxy().callRemote('register_file_sending', 'proxy', '%s:%d' % host, receiver_idurl, filename, size, description)
    lg.warn('transport_proxy is not ready')
    return fail('transport_proxy is not ready')


def interface_register_file_receiving(host, sender_idurl, filename, size=0):
    """
    """
    if proxy():
        return proxy().callRemote('register_file_receiving', 'proxy', '%s:%d' % host, sender_idurl, filename, size)
    lg.warn('transport_proxy is not ready')
    return fail('transport_proxy is not ready')


def interface_unregister_file_sending(transfer_id, status, size=0, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('unregister_file_sending', transfer_id, status, size, error_message)
    lg.warn('transport_proxy is not ready')
    return fail('transport_proxy is not ready')


def interface_unregister_file_receiving(transfer_id, status, size=0, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('unregister_file_receiving', transfer_id, status, size, error_message)
    lg.warn('transport_proxy is not ready')
    return fail('transport_proxy is not ready')


def interface_cancelled_file_sending(host, filename, size=0, description=None, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('cancelled_file_sending', 'proxy', '%s:%d' % host, filename, size, description, error_message)
    lg.warn('transport_proxy is not ready')
    return fail('transport_proxy is not ready')




