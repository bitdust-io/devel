#!/usr/bin/python
# http_interface.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (http_interface.py) is part of BitDust Software.
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
.. module:: http_interface.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

import six
import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in http_interface.py')

from twisted.web import xmlrpc
from twisted.internet.defer import succeed, fail
from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from logs import lg

from main import settings

from lib import misc
from lib import strng
from lib import net_misc

from transport.http import http_node

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
        if _Debug:
            lg.out(4, 'http_interface.init')
        if not proxy():
            global _GateProxy
            if isinstance(xml_rpc_url_or_object, six.string_types):
                _GateProxy = xmlrpc.Proxy(xml_rpc_url_or_object, allowNone=True)
            else:
                _GateProxy = xml_rpc_url_or_object
        proxy().callRemote('transport_initialized', 'http')
        return True

    def shutdown(self):
        """
        """
        if _Debug:
            lg.out(4, 'http_interface.shutdown')
        if proxy():
            global _GateProxy
            del _GateProxy
            _GateProxy = None
        return True

    def connect(self, options):
        """
        """
        if _Debug:
            lg.out(4, 'http_interface.connect %s' % str(options))
        if settings.enableHTTPreceiving():
            http_node.start_receiving()
        else:
            lg.warn('transport_http receiving is disabled')
            interface_receiving_failed()
            return False
        if settings.enableHTTPsending():
            http_node.start_sending(port=options['http_port'])
        return succeed(True)

    def disconnect(self):
        """
        """
        if _Debug:
            lg.out(4, 'http_interface.disconnect')
        http_node.stop_sending()
        http_node.stop_receiving()
        return succeed(True)

    def build_contacts(self, id_obj):
        """
        """
        result = []
        nowip = strng.to_bin(misc.readExternalIP())
        result.append(b'http://%s:%d' % (nowip, settings.getHTTPPort()))
        if _Debug:
            lg.out(4, 'http_interface.build_contacts : %s' % result)
        return result

    def verify_contacts(self, id_obj):
        """
        """
        nowip = strng.to_bin(misc.readExternalIP())
        http_contact = 'http://%s:%s' % (nowip, str(settings.getHTTPPort()))
        if id_obj.getContactIndex(contact=http_contact) < 0:
            if _Debug:
                lg.out(4, 'http_interface.verify_contacts returning False: http contact not found or changed')
            return False
#         if http_node.get_internal_port() != settings.getHTTPPort():
#             if _Debug:
#                 lg.out(4, 'http_interface.verify_contacts returning False: http port has been changed')
#             return False
        if _Debug:
            lg.out(4, 'http_interface.verify_contacts returning True')
        return True

    def send_file(self, remote_idurl, filename, host, description='', keep_alive=True):
        """
        """
        return http_node.send_file(remote_idurl, filename)

    def send_file_single(self, remote_idurl, filename, host, description='', keep_alive=False):
        """
        """
        return http_node.send_file(remote_idurl, filename)

#     def connect_to(self, host):
#         """
#         """
#         return http_node.connect_to(host)

#     def disconnect_from(self, host):
#         """
#         """
#         return http_node.disconnect_from(host)

#     def cancel_file_sending(self, transferID):
#         """
#         """
#         return http_node.cancel_file_sending(transferID)

#     def cancel_file_receiving(self, transferID):
#         """
#         """
#         return http_node.cancel_file_receiving(transferID)

#     def cancel_outbox_file(self, host, filename):
#         """
#         """
#         return http_node.cancel_outbox_file(host, filename)

#     def list_sessions(self):
#         """
#         """
#         result = []
#         for opened_connection in http_node.opened_connections().values():
#             for channel in opened_connection:
#                 result.append(channel)
#         for started_connection in http_node.started_connections():
#             result.append(started_connection)
#         return result

#     def list_streams(self, sorted_by_time=True):
#         """
#         """
#         result = []
#         result.extend(http_node.list_input_streams(sorted_by_time))
#         result.extend(http_node.list_output_streams(sorted_by_time))
#         return result

#------------------------------------------------------------------------------


def interface_transport_initialized(xmlrpcurl):
    """
    """
    if proxy():
        return proxy().callRemote('transport_initialized', 'http', xmlrpcurl)
    lg.warn('transport_http is not ready')
    return fail(Exception('transport_http is not ready'))


def interface_receiving_started(host, new_options={}):
    """
    """
    if proxy():
        return proxy().callRemote('receiving_started', 'http', net_misc.pack_address(host), new_options)
    lg.warn('transport_http is not ready')
    return fail(Exception('transport_http is not ready'))


def interface_receiving_failed(error_code=None):
    """
    """
    if proxy():
        return proxy().callRemote('receiving_failed', 'http', error_code)
    lg.warn('transport_http is not ready')
    return fail(Exception('transport_http is not ready'))


def interface_disconnected(result=None):
    """
    """
    if proxy():
        return proxy().callRemote('disconnected', 'http', result)
    lg.warn('transport_http is not ready')
    return fail(Exception('transport_http is not ready'))


def interface_register_file_sending(host, receiver_idurl, filename, size=0, description=''):
    """
    """
    if proxy():
        return proxy().callRemote(
            'register_file_sending', 'http', net_misc.pack_address(host), receiver_idurl, filename, size, description)
    lg.warn('transport_http is not ready')
    return fail(Exception('transport_http is not ready'))


def interface_register_file_receiving(host, sender_idurl, filename, size=0):
    """
    """
    if proxy():
        return proxy().callRemote(
            'register_file_receiving', 'http', net_misc.pack_address(host), sender_idurl, filename, size)
    lg.warn('transport_http is not ready')
    return fail(Exception('transport_http is not ready'))


def interface_unregister_file_sending(transfer_id, status, size=0, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('unregister_file_sending', transfer_id, status, size, error_message)
    lg.warn('transport_http is not ready')
    return fail(Exception('transport_http is not ready'))


def interface_unregister_file_receiving(transfer_id, status, size=0, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote('unregister_file_receiving', transfer_id, status, size, error_message)
    lg.warn('transport_http is not ready')
    return fail(Exception('transport_http is not ready'))


def interface_cancelled_file_sending(host, filename, size=0, description=None, error_message=None):
    """
    """
    if proxy():
        return proxy().callRemote(
            'cancelled_file_sending', 'http', net_misc.pack_address(host), filename, size, description, error_message)
    lg.warn('transport_http is not ready')
    return fail(Exception('transport_http is not ready'))
