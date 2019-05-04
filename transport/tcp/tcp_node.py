#!/usr/bin/python
# tcp_node.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (tcp_node.py) is part of BitDust Software.
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
.. module:: tcp_node.

This is a This is a sub process to send/receive files between users over
TCP protocol. 1) listen for incoming connections on a port 7771 (by
default) 2) establish connections to remote peers 3) keeps TCP session
opened to be able to send asap
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 8

#------------------------------------------------------------------------------

import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in tcp_node.py')

from twisted.internet import protocol  # @UnresolvedImport
from twisted.internet.defer import Deferred  # @UnresolvedImport
from twisted.internet.error import CannotListenError  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from lib import net_misc

from transport.tcp import tcp_stream

#------------------------------------------------------------------------------

_MyIDURL = None
_MyHost = None
_InternalPort = 7771
_Listener = None
_ByTransferID = {}
_OpenedConnections = {}
_StartedConnections = {}
_ConnectionsCounter = 0
_ConnectionTimeout = 10

#------------------------------------------------------------------------------


def started_connections():
    global _StartedConnections
    return _StartedConnections


def opened_connections():
    global _OpenedConnections
    return _OpenedConnections


def opened_connections_count():
    global _ConnectionsCounter
    return _ConnectionsCounter

#------------------------------------------------------------------------------


def increase_connections_counter():
    global _ConnectionsCounter
    _ConnectionsCounter += 1


def decrease_connections_counter():
    global _ConnectionsCounter
    _ConnectionsCounter -= 1

#------------------------------------------------------------------------------


def get_internal_port():
    global _InternalPort
    return _InternalPort


def my_idurl():
    global _MyIDURL
    return _MyIDURL


def my_host():
    global _MyHost
    return _MyHost

#------------------------------------------------------------------------------


def receive(options):
    global _MyIDURL
    global _MyHost
    global _InternalPort
    global _Listener
    from transport.tcp import tcp_interface
    if _Debug:
        lg.out(_DebugLevel, 'tcp_node.receive %r' % options)
    if _Listener:
        lg.warn('listener already exist')
        tcp_interface.interface_receiving_started(_MyHost, options)
        return _Listener
    try:
        _MyIDURL = options['idurl']
        _InternalPort = int(options['tcp_port'])
    except:
        _MyIDURL = None
        _InternalPort = None
        lg.exc()
        return None
    try:
        _Listener = reactor.listenTCP(_InternalPort, TCPFactory(None, keep_alive=True))  # @UndefinedVariable
        _MyHost = net_misc.pack_address((options['host'].split(b':')[0], int(_InternalPort)))
        tcp_interface.interface_receiving_started(_MyHost, options)

    except CannotListenError as ex:
        lg.warn('port "%d" is busy' % _InternalPort)
        tcp_interface.interface_receiving_failed('port is busy')
        return None

    except Exception as ex:
        try:
            e = ex.getErrorMessage()
        except:
            e = str(ex)
        tcp_interface.interface_receiving_failed(e)
        lg.exc()
        return None

    return _Listener


def connect_to(host, keep_alive=True):
    """
    """
    host = net_misc.normalize_address(host)
    if host in started_connections():
        lg.warn('already connecting to "%s"' % host)
        return False
    for peeraddr, connections in opened_connections().items():
        if peeraddr == host:
            lg.warn('already connected to "%s" with %d connections' % (host, len(connections)))
            return True
        for connection in connections:
            if connection.getConnectionAddress():
                if connection.getConnectionAddress() == host:
                    lg.warn('already connected to "%s" with peer address: "%s"' % (host, peeraddr))
                    return True
    if _Debug:
        lg.out(_DebugLevel, 'tcp_node.connect_to "%s", keep_alive=%s' % (host, keep_alive))
    connection = TCPFactory(host, keep_alive=keep_alive)
    started_connections()[host] = connection
    connection.connector = reactor.connectTCP(host[0], host[1], connection, timeout=_ConnectionTimeout)  # @UndefinedVariable
    return False


def disconnect_from(host):
    """
    """
    host = net_misc.normalize_address(host)
    ok = False
    for peeraddr, connections in opened_connections().items():
        alll = False
        if peeraddr == host:
            alll = True
        for connection in connections:
            if alll:
                connection.automat('disconnect')
                ok = True
                continue
            if connection.getConnectionAddress():
                if connection.getConnectionAddress() == host:
                    connection.automat('disconnect')
                    return True
    return ok


def disconnect():
    """
    """
    global _Listener
    from transport.tcp import tcp_interface
    if not _Listener:
        tcp_interface.interface_disconnected(None)
        return True
    d = _Listener.stopListening()
    d.addCallback(tcp_interface.interface_disconnected)
    d.addErrback(lambda *args: lg.warn(str(*args)))
    _Listener = None
    return True


def close_connections():
    """
    """
    for sc in list(started_connections().values()):
        sc.connector.disconnect()
    for oclist in list(opened_connections().values()):
        for oc in oclist:
            oc.automat('disconnect')
            oc.automat('connection-lost')


def send(filename, remoteaddress, description=None, keep_alive=True):
    """
    """
    remoteaddress = net_misc.normalize_address(remoteaddress)
    result_defer = Deferred()
    if remoteaddress in started_connections():
        started_connections()[remoteaddress].add_outbox_file(filename, description, result_defer, keep_alive)
        if not keep_alive:
            if _Debug:
                lg.out(_DebugLevel, 'tcp_node.send single, use started connection to %s, %d already started and %d opened' % (
                    str(remoteaddress), len(started_connections()), len(opened_connections())))
        return result_defer
    for peeraddr, connections in opened_connections().items():
        for connection in connections:
            if peeraddr == remoteaddress:
                connection.append_outbox_file(filename, description, result_defer, keep_alive)
                if not keep_alive:
                    if _Debug:
                        lg.out(_DebugLevel, 'tcp_node.send single, use opened connection to %s, %d already started and %d opened' % (
                            str(remoteaddress), len(started_connections()), len(opened_connections())))
                return result_defer
            if connection.getConnectionAddress():
                if connection.getConnectionAddress() == remoteaddress:
                    connection.append_outbox_file(filename, description, result_defer, keep_alive)
                    if not keep_alive:
                        if _Debug:
                            lg.out(_DebugLevel, 'tcp_node.send single, use opened connection to %s, %d already started and %d opened' % (
                                str(remoteaddress), len(started_connections()), len(opened_connections())))
                    return result_defer
    if _Debug:
        lg.out(_DebugLevel, 'tcp_node.send start connecting to "%s"' % str(remoteaddress))
    connection = TCPFactory(remoteaddress, keep_alive=keep_alive)
    started_connections()[remoteaddress] = connection
    connection.add_outbox_file(filename, description, result_defer, keep_alive)
    connection.connector = reactor.connectTCP(remoteaddress[0], remoteaddress[1], connection, timeout=_ConnectionTimeout)  # @UndefinedVariable
    if not keep_alive:
        if _Debug:
            lg.out(_DebugLevel, 'tcp_node.send opened a single connection to %s, %d already started and %d opened' % (
                str(remoteaddress), len(started_connections()), len(opened_connections())))
    return result_defer


def send_keep_alive(host):
    sent_something = False
    for channel in opened_connections().get(host, []):
        channel.automat('send-keep-alive')
        sent_something = True
    return sent_something


def start_streams():
    """
    """
    return tcp_stream.start_process_streams()


def stop_streams():
    """
    """
    return tcp_stream.stop_process_streams()


def list_input_streams(sorted_by_time=True):
    """
    """
    return tcp_stream.list_input_streams(sorted_by_time)


def list_output_streams(sorted_by_time=True):
    """
    """
    return tcp_stream.list_output_streams(sorted_by_time)


def find_stream(file_id=None, transfer_id=None):
    """
    """
    return tcp_stream.find_stream(file_id=file_id, transfer_id=transfer_id)


def cancel_file_receiving(transferID):
    """
    """
    # at the moment for TCP transport we can not stop particular file transfer
    # we can only close connection itself, which is not we really want
    # need to find a way to notify remote side about to stop
#     for connections in opened_connections().values():
#         for connection in connections:
#             for in_file in connection.stream.inboxFiles.values():
#                 if in_file.transfer_id and in_file.transfer_id == transferID:
#                     connection.automat('disconnect')
#                     return True
#     lg.warn('%r not found' % transferID)
#     return False
    return False


def cancel_file_sending(transferID):
    """
    """
    for connections in opened_connections().values():
        for connection in connections:
            if connection.stream:
                for out_file in connection.stream.outboxFiles.values():
                    if out_file.transfer_id and out_file.transfer_id == transferID:
                        out_file.cancel()
                        return True
    lg.warn('%r not found' % transferID)
    return False


def cancel_outbox_file(host, filename):
    """
    """
    host = net_misc.normalize_address(host)
    from transport.tcp import tcp_interface
    for connections in opened_connections().values():
        for connection in connections:
            if connection.peer_address and connection.peer_address == host or \
                    connection.peer_external_address and connection.peer_external_address == host:
                i = 0
                while i < len(connection.outboxQueue):
                    fn, description, result_defer, keep_alive = connection.outboxQueue[i]
                    if fn == filename:
                        connection.outboxQueue.pop(i)
                        connection.failed_outbox_queue_item(fn, description, 'cancelled')
                        continue
                    i += 1
    for connection in started_connections().values():
        if connection.connection_address and connection.connection_address == host:
            i = 0
            while i < len(connection.pendingoutboxfiles):
                fn, description, result_defer, keep_alive = connection.pendingoutboxfiles[i]
                if fn == filename:
                    connection.pendingoutboxfiles.pop(i)
                    try:
                        tcp_interface.interface_cancelled_file_sending(
                            host, filename, 0, description, 'cancelled')
                    except Exception as exc:
                        lg.warn(str(exc))
                    if result_defer:
                        result_defer.callback((filename, description, 'failed', 'cancelled'))
                    continue
                i += 1

#------------------------------------------------------------------------------


class TCPFactory(protocol.ClientFactory):
    protocol = None

    def __init__(self, connection_address, keep_alive=True):
        from transport.tcp import tcp_connection
        self.protocol = tcp_connection.TCPConnection
        self.connection_address = connection_address
        self.keep_alive = keep_alive
        self.pendingoutboxfiles = []
        self.connector = None

    def __repr__(self):
        return 'TCPFactory(%s)' % str(self.connection_address)

    def clientConnectionFailed(self, connector, reason):
        from transport.tcp import tcp_interface
        protocol.ClientFactory.clientConnectionFailed(self, connector, reason)
        destaddress = (connector.getDestination().host, int(connector.getDestination().port))
        connection = started_connections().pop(self.connection_address, None)
        if connection:
            connection.connector = None
        if _Debug:
            lg.out(_DebugLevel, 'tcp_node.clientConnectionFailed with %s, %d more connections started' % (
                str(destaddress), len(started_connections())))
        for filename, description, result_defer, keep_alive in self.pendingoutboxfiles:
            try:
                tcp_interface.interface_cancelled_file_sending(
                    destaddress, filename, 0, description, 'connection failed'
                ).addErrback(lambda err: lg.exc(err))
            except Exception as exc:
                lg.warn(str(exc))
            if result_defer:
                result_defer.callback((filename, description, 'failed', 'connection failed'))
        self.pendingoutboxfiles = []

    def add_outbox_file(self, filename, description='', result_defer=None, keep_alive=True):
        self.pendingoutboxfiles.append((filename, description, result_defer, keep_alive))
        tcp_stream.process_streams()

