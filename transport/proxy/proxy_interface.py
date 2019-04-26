#!/usr/bin/python
# proxy_interface.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (proxy_interface.py) is part of BitDust Software.
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
#
#
#
#

"""
.. module:: proxy_interface.

This is a client side part of the PROXY transport plug-in.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import six

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

from twisted.web import xmlrpc
from twisted.internet.defer import succeed, fail, Deferred
from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from logs import lg

from main import settings

from contacts import identitycache

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
        from transport.proxy import proxy_receiver
        from transport.proxy import proxy_sender
        if isinstance(xml_rpc_url_or_object, six.string_types):
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
        from transport.proxy import proxy_receiver
        from transport.proxy import proxy_sender
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
        from transport.proxy import proxy_receiver
        from transport.proxy import proxy_sender
        if settings.enablePROXYreceiving():
            proxy_receiver.A('start', options)
        else:
            lg.warn('proxy transport receiving is disabled')
            interface_receiving_failed()
            return False
        if settings.enablePROXYsending():
            proxy_sender.A('start', options)
        return succeed(True)

    def disconnect(self):
        """
        """
        if _Debug:
            lg.out(4, 'proxy_interface.disconnect')
        from transport.proxy import proxy_receiver
        from transport.proxy import proxy_sender
        if not proxy_receiver.A():
            lg.warn('proxy_receiver is not ready')
            interface_disconnected()
        elif proxy_receiver.A().state != 'LISTEN':
            lg.warn('proxy_receiver is not listening now')
            interface_disconnected()
        else:
            proxy_receiver.A('stop')
        proxy_sender.A('stop')
        return succeed(True)

    def build_contacts(self, id_obj):
        """
        """
        from transport.proxy import proxy_receiver
        # from userid import my_id
        # current_identity_contacts = my_id.getLocalIdentity().getContacts()
        if not proxy_receiver.GetRouterIdentity():
            # if not yet found one node to route your traffic - do nothing
            if _Debug:
                lg.out(4, 'proxy_interface.build_contacts SKIP, router not yet found')
            return []  # current_identity_contacts
        if not proxy_receiver.ReadMyOriginalIdentitySource():
            # if we did not save our original identity we will have troubles contacting remote node
            if _Debug:
                lg.out(4, 'proxy_interface.build_contacts SKIP, original identity was not saved')
            return []  # current_identity_contacts
        # switch contacts - use router contacts instead of my
        # he will receive all packets addressed to me and redirect to me
        result = proxy_receiver.GetRouterIdentity().getContacts()
        if _Debug:
            lg.out(4, 'proxy_interface.build_contacts %s : %r' % (
                proxy_receiver.GetRouterIdentity().getIDName(), result))
        return result

    def verify_contacts(self, id_obj):
        """
        Check if router is ready and his contacts exists in that identity.
        """
        from transport.proxy import proxy_receiver
        if not proxy_receiver.A() or not proxy_receiver.GetRouterIDURL() or not proxy_receiver.GetRouterIdentity():
            # if not yet found any node to route your traffic - do nothing
            if _Debug:
                lg.out(4, 'proxy_interface.verify_contacts returning True : router not yet found')
            return True
        if not proxy_receiver.ReadMyOriginalIdentitySource():
            if _Debug:
                lg.out(4, 'proxy_interface.verify_contacts returning False : my original identity is empty')
            return False
        result = Deferred()

        def _finish_verification(res):
            if _Debug:
                lg.out(4, 'proxy_interface._finish_verification')
            try:
                cached_id = identitycache.FromCache(proxy_receiver.GetRouterIDURL())
                if not cached_id:
                    if _Debug:
                        lg.out(4, '    returning False: router identity is not cached')
                    res.callback(False)
                    return False
                if not proxy_receiver.GetRouterIdentity():
                    if _Debug:
                        lg.out(4, '    returning False : router identity is None or router is not ready yet')
                    return True
                if cached_id.serialize() != proxy_receiver.GetRouterIdentity().serialize():
                    if _Debug:
                        lg.out(4, 'proxy_interface.verify_contacts return False: cached copy is different')
                        lg.out(20, '\n%s\n' % cached_id.serialize(as_text=True))
                        lg.out(20, '\n%s\n' % proxy_receiver.GetRouterIdentity().serialize(as_text=True))
                    res.callback(False)
                    return
                router_contacts = proxy_receiver.GetRouterIdentity().getContactsByProto()
                if len(router_contacts) != id_obj.getContactsNumber():
                    if _Debug:
                        lg.out(4, '    returning False: router contacts is different')
                    res.callback(False)
                    return False
                for proto, contact in id_obj.getContactsByProto().items():
                    if proto not in list(router_contacts.keys()):
                        if _Debug:
                            lg.out(4, '    returning False: [%s] is not present in router contacts' % proto)
                        res.callback(False)
                        return False
                    if router_contacts[proto] != contact:
                        if _Debug:
                            lg.out(4, '    returning False: [%s] contact is different in router id' % proto)
                        res.callback(False)
                        return False
                if _Debug:
                    lg.out(4, '    returning True : my contacts and router contacts is same')
                res.callback(True)
                return True
            except:
                lg.exc()
                res.callback(True)
                return True
        d = identitycache.immediatelyCaching(proxy_receiver.GetRouterIDURL())
        d.addCallback(lambda src: _finish_verification(result))
        d.addErrback(lambda err: result.callback(False))
        return result

    def list_sessions(self):
        """
        """
        from transport.proxy import proxy_receiver
        from transport.proxy import proxy_sender
        result = []
        if proxy_receiver.A():
            result.append(proxy_receiver.A())
        if proxy_sender.A():
            result.append(proxy_sender.A())
        return result

    def list_streams(self, sorted_by_time=True):
        """
        """
        return []

#------------------------------------------------------------------------------

def proxy_errback(x):
    if _Debug:
        lg.out(6, 'proxy_interface.proxy_errback ERROR %s' % x)
    return None

#------------------------------------------------------------------------------

def interface_transport_initialized(xmlrpcurl):
    if proxy():
        return proxy().callRemote(
            'transport_initialized', 'proxy', xmlrpcurl).addErrback(proxy_errback)
    lg.warn('transport_proxy is not ready')
    return fail(Exception('transport_proxy is not ready')).addErrback(proxy_errback)


def interface_receiving_started(host, new_options={}):
    if proxy():
        return proxy().callRemote(
            'receiving_started', 'proxy', host, new_options).addErrback(proxy_errback)
    lg.warn('transport_proxy is not ready')
    return fail(Exception('transport_proxy is not ready')).addErrback(proxy_errback)


def interface_receiving_failed(error_code=None):
    if proxy():
        return proxy().callRemote(
            'receiving_failed', 'proxy', error_code).addErrback(proxy_errback)
    lg.warn('transport_proxy is not ready')
    return fail(Exception('transport_proxy is not ready')).addErrback(proxy_errback)


def interface_disconnected(result=None):
    if proxy():
        return proxy().callRemote(
            'disconnected', 'proxy', result).addErrback(proxy_errback)
    lg.warn('transport_proxy is not ready')
    # return fail(Exception('transport_proxy is not ready')).addErrback(proxy_errback)
    return succeed(result)


def interface_register_file_sending(host, receiver_idurl, filename, size=0, description=''):
    """
    """
    if proxy():
        return proxy().callRemote(
            'register_file_sending', 'proxy', host, receiver_idurl, filename, size, description,
        ).addErrback(proxy_errback)
    lg.warn('transport_proxy is not ready')
    return fail(Exception('transport_proxy is not ready')).addErrback(proxy_errback)


def interface_register_file_receiving(host, sender_idurl, filename, size=0):
    """
    """
    if proxy():
        return proxy().callRemote(
            'register_file_receiving', 'proxy', host, sender_idurl, filename, size,
        ).addErrback(proxy_errback)
    lg.warn('transport_proxy is not ready')
    return fail(Exception('transport_proxy is not ready')).addErrback(proxy_errback)


def interface_unregister_file_sending(transfer_id, status, size=0, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote(
            'unregister_file_sending', transfer_id, status, size, error_message,
        ).addErrback(proxy_errback)
    lg.warn('transport_proxy is not ready')
    return fail(Exception('transport_proxy is not ready')).addErrback(proxy_errback)


def interface_unregister_file_receiving(transfer_id, status, size=0, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote(
            'unregister_file_receiving', transfer_id, status, size, error_message,
        ).addErrback(proxy_errback)
    lg.warn('transport_proxy is not ready')
    return fail(Exception('transport_proxy is not ready')).addErrback(proxy_errback)


def interface_cancelled_file_sending(host, filename, size=0, description=None, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote(
            'cancelled_file_sending', 'proxy', host, filename, size, description, error_message,
        ).addErrback(proxy_errback)
    lg.warn('transport_proxy is not ready')
    return fail(Exception('transport_proxy is not ready')).addErrback(proxy_errback)
