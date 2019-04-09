#!/usr/bin/python
# udp_interface.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (udp_interface.py) is part of BitDust Software.
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
..

module:: udp_interface
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

import six

#------------------------------------------------------------------------------

import os
import sys

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in udp_interface.py')

from twisted.web import xmlrpc
from twisted.internet.defer import Deferred, succeed, fail

#------------------------------------------------------------------------------

from logs import lg

from lib import nameurl

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

_GateProxy = None

#------------------------------------------------------------------------------


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

    def init(self, xml_rpc_url_or_object):
        """
        """
        global _GateProxy
        if _Debug:
            lg.out(4, 'udp_interface.init %s' % xml_rpc_url_or_object)
        if isinstance(xml_rpc_url_or_object, six.string_types):
            _GateProxy = xmlrpc.Proxy(xml_rpc_url_or_object, allowNone=True)
        else:
            _GateProxy = xml_rpc_url_or_object
        _GateProxy.callRemote('transport_initialized', 'udp')
        return True

    def shutdown(self):
        """
        """
        from transport.udp import udp_node
        global _GateProxy
        if _Debug:
            lg.out(4, 'udp_interface.shutdown')
        udp_node.Destroy()
        if _GateProxy:
            # del _GateProxy
            _GateProxy = None
        return succeed(True)

    def connect(self, options):
        """
        """
        from transport.udp import udp_node
        if _Debug:
            lg.out(8, 'udp_interface.connect %s' % str(options))
        udp_node.A('go-online', options)
        return True

    def disconnect(self):
        """
        """
        from transport.udp import udp_node
        if _Debug:
            lg.out(4, 'udp_interface.disconnect')
        udp_node.A('go-offline')
        return succeed(True)

    def build_contacts(self, id_obj):
        """
        """
        result = []
        result.append(
            'udp://%s@%s' %
            (id_obj.getIDName().lower(),
             id_obj.getIDHost()))
        if _Debug:
            lg.out(4, 'udp_interface.build_contacts : %s' % str(result))
        return result

    def verify_contacts(self, id_obj):
        """
        """
        udp_contact = 'udp://%s@%s' % (id_obj.getIDName().lower(),
                                       id_obj.getIDHost())
        if id_obj.getContactIndex(contact=udp_contact) < 0:
            if _Debug:
                lg.out(
                    4,
                    'udp_interface.verify_contacts returning False: udp contact not found or changed')
            return False
        if _Debug:
            lg.out(4, 'udp_interface.verify_contacts returning True')
        return True

    def send_file(self, remote_idurl, filename, host, description=''):
        """
        """
        from transport.udp import udp_session
        from transport.udp import udp_node
        # lg.out(20, 'udp_interface.send_file %s %s %s' % (filename, host, description))
        result_defer = Deferred()
#        if udp_node.A().state not in ['LISTEN', 'DHT_READ',]:
#            result_defer.callback(False)
#            lg.out(4, 'udp_interface.send_file WARNING udp_node state is %s' % udp_node.A().state)
#            return result_defer
        active_sessions = udp_session.get_by_peer_id(host)
        if active_sessions:
            if description.startswith('Identity') or description.startswith('Ack'):
                active_sessions[0].file_queue.insert_outbox_file(
                    filename, description, result_defer, keep_alive=True)
            else:
                active_sessions[0].file_queue.append_outbox_file(
                    filename, description, result_defer, keep_alive=True)
        else:
            udp_session.add_pending_outbox_file(
                filename, host, description, result_defer, keep_alive=True)
            udp_node.A('connect', host)
        return result_defer

    def send_file_single(self, remote_idurl, filename, host, description=''):
        """
        """
        return self.send_file(self, remote_idurl, filename, host, description, keep_alive=False)

    def send_keep_alive(self, host):
        """
        """
        from transport.udp import udp_session
        for sess in udp_session.sessions_by_peer_id().get(host, []):
            sess.automat('send-keep-alive')

    def connect_to_host(self, host=None, idurl=None):
        """
        """
        from transport.udp import udp_node
        if not host:
            host = idurl_to_id(idurl)
        if _Debug:
            lg.out(12, 'udp_interface.connect %s' % host)
        udp_node.A('connect', host)

    def disconnect_from_host(self, host):
        """
        """

    def cancel_outbox_file(self, host, filename):
        """
        """
        from transport.udp import udp_session
        ok = False
        for sess in udp_session.sessions().values():
            if sess.peer_id != host:
                continue
            i = 0
            while i < len(sess.file_queue.outboxQueue):
                fn, descr, result_defer, keep_alive = sess.file_queue.outboxQueue[i]
                if fn == filename:
                    if _Debug:
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
        from transport.udp import udp_session
        for sess in udp_session.sessions().values():
            for out_file in sess.file_queue.outboxFiles.values():
                if out_file.transfer_id and out_file.transfer_id == transferID:
                    out_file.cancel()
                    return True
        return False

    def cancel_file_receiving(self, transferID):
        """
        """
        # at the moment for UDP transport we can not stop particular file transfer
        # we can only close the whole session which is not we really want
#         for sess in udp_session.sessions().values():
#             for in_file in sess.file_queue.inboxFiles.values():
#                 if in_file.transfer_id and in_file.transfer_id == transferID:
#                     if _Debug:
#                         lg.out(6, 'udp_interface.cancel_file_receiving transferID=%s   want to close session' % transferID)
#                     sess.automat('shutdown')
#                     return True
#         return False
        return False

    def list_sessions(self):
        """
        """
        from transport.udp import udp_session
        return list(udp_session.sessions().values())

    def list_streams(self, sorted_by_time=True):
        """
        """
        from transport.udp import udp_stream
        result = []
        for stream in udp_stream.streams().values():
            result.append(stream.consumer)
        if sorted_by_time:
            result.sort(key=lambda stream: stream.started)
        return result

    def find_session(self, host):
        """
        """
        from transport.udp import udp_session
        return udp_session.sessions_by_peer_id().get(host, [])

    def find_stream(self, stream_id=None, transfer_id=None):
        """
        """
        from transport.udp import udp_stream
        for stream in udp_stream.streams().values():
            if stream_id and stream_id == stream.consumer.stream_id:
                return stream.consumer
            if transfer_id and transfer_id == stream.consumer.transfer_id:
                return stream.consumer
        return None

#------------------------------------------------------------------------------

def proxy_errback(x):
    if _Debug:
        lg.out(6, 'udp_interface.proxy_errback ERROR %s' % x)
    return None

#------------------------------------------------------------------------------


def interface_transport_initialized():
    """
    """
    if proxy():
        return proxy().callRemote('transport_initialized', 'udp').addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)


def interface_receiving_started(host, new_options={}):
    """
    """
    if proxy():
        return proxy().callRemote('receiving_started', 'udp', host, new_options).addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)


def interface_receiving_failed(error_code=None):
    """
    """
    if proxy():
        return proxy().callRemote('receiving_failed', 'udp', error_code).addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)


def interface_disconnected(result=None):
    """
    """
    if proxy():
        return proxy().callRemote('disconnected', 'udp', result).addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    # return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)
    return succeed(result)


def interface_register_file_sending(host, receiver_idurl, filename, size, description=''):
    """
    """
    if proxy():
        return proxy().callRemote(
            'register_file_sending', 'udp', host, receiver_idurl, filename, size, description).addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)


def interface_register_file_receiving(host, sender_idurl, filename, size):
    """
    """
    if proxy():
        return proxy().callRemote(
            'register_file_receiving', 'udp', host, sender_idurl, filename, size).addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)


def interface_unregister_file_sending(transfer_id, status, bytes_sent, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote(
            'unregister_file_sending', transfer_id, status,
            bytes_sent, error_message).addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)


def interface_unregister_file_receiving(transfer_id, status, bytes_received, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote(
            'unregister_file_receiving', transfer_id, status,
            bytes_received, error_message).addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)


def interface_cancelled_file_sending(host, filename, size, description=None, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote(
            'cancelled_file_sending', 'udp', host, filename,
            size, description, error_message).addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)


def interface_cancelled_file_receiving(host, filename, size, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote(
            'cancelled_file_receiving', 'udp', host, filename, size, error_message).addErrback(proxy_errback)
    lg.warn('transport_udp is not ready')
    return fail(Exception('transport_udp is not ready')).addErrback(proxy_errback)
