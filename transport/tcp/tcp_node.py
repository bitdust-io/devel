#!/usr/bin/python
#tcp_connection.py
#
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
.. module:: tcp_process

This is a 
This is a sub process to send/receive files between users over TCP protocol.
1) listen for incoming connections on a port 7771 (by default) 
2) establish connections to remote peers
3) keeps TCP session opened to be able to send asap 
"""

import os
import sys
import time
import optparse

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in tcp_connection.py')

from twisted.web import xmlrpc
from twisted.internet import task
from twisted.internet import protocol
from twisted.protocols import basic
from twisted.web import server
from twisted.internet.defer import Deferred, succeed 
from twisted.internet.error import ConnectionDone
from twisted.internet.error import CannotListenError

from logs import lg

from system import bpio

import tcp_interface
import tcp_connection
import tcp_stream

#------------------------------------------------------------------------------ 

_MyIDURL = None
_MyHost = None
_InternalPort = 7771
_Listener = None
_ByTransferID = {}
_OpenedConnections = {}
_StartedConnections = {}
_ConnectionsCounter = 0

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

def increase_connections_counter():
    global _ConnectionsCounter
    _ConnectionsCounter += 1

def decrease_connections_counter():
    global _ConnectionsCounter
    _ConnectionsCounter -= 1
    
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
    if _Listener:
        tcp_interface.interface_receiving_failed('already listening')
        return None
    try:
        _MyIDURL = options['idurl']
        _InternalPort = int(options['tcp_port'])
        _Listener = reactor.listenTCP(_InternalPort, TCPFactory(None))
        _MyHost = options['host'].split(':')[0]+':'+str(_InternalPort)
        tcp_interface.interface_receiving_started(_MyHost, options)
    except CannotListenError, ex:
        tcp_interface.interface_receiving_failed('port is busy')
    except Exception, ex:
        # print err, dir(err)
        try:
            e = ex.getErrorMessage()
        except:
            e = str(ex)
        tcp_interface.interface_receiving_failed(e)
        # lg.exc()
    return _Listener


def connect_to(host):
    """
    """
    if host in started_connections():
        return False
    for peeraddr, connections in opened_connections().items():
        if peeraddr == host:
            return True
        for connection in connections:
            if connection.getConnectionAddress():
                if connection.getConnectionAddress() == host:
                    return True
    connection = TCPFactory(host)
    connection.connector = reactor.connectTCP(host[0], host[1], connection)
    started_connections()[host] = connection
    return False
    

def disconnect_from(host):
    """
    """
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
    if not _Listener:
        tcp_interface.interface_disconnected(None)
        return True
    _Listener.stopListening().addBoth(tcp_interface.interface_disconnected)
    _Listener = None
    return True


def close_connections():
    """
    """
    for sc in started_connections().values():
        sc.connector.disconnect()
    for oclist in opened_connections().values():
        for oc in oclist:
            oc.automat('disconnect')
            oc.automat('connection-lost')


def send(filename, remoteaddress, description=None, single=False):
    """
    """
    result_defer = Deferred()
    if remoteaddress in started_connections():
        started_connections()[remoteaddress].add_outbox_file(filename, description, result_defer, single)
        if single:
            lg.out(6, 'tcp_node.send single, use started connection to %s, %d already started and %d opened' % (
                str(remoteaddress), len(started_connections()), len(opened_connections())))
        return result_defer
    for peeraddr, connections in opened_connections().items():
        for connection in connections:
            if peeraddr == remoteaddress:
                connection.append_outbox_file(filename, description, result_defer, single)
                if single:
                    lg.out(6, 'tcp_node.send single, use opened connection to %s, %d already started and %d opened' % (
                        str(remoteaddress), len(started_connections()), len(opened_connections())))
                return result_defer
            if connection.getConnectionAddress():
                if connection.getConnectionAddress() == remoteaddress:
                    connection.append_outbox_file(filename, description, result_defer, single)
                    if single:
                        lg.out(6, 'tcp_node.send single, use opened(2) connection to %s, %d already started and %d opened' % (
                            str(remoteaddress), len(started_connections()), len(opened_connections())))
                    return result_defer
    connection = TCPFactory(remoteaddress)
    connection.add_outbox_file(filename, description, result_defer, single)
    connection.connector = reactor.connectTCP(remoteaddress[0], remoteaddress[1], connection)
    started_connections()[remoteaddress] = connection
    if single:
        lg.out(6, 'tcp_node.send opened a single connection to %s, %d already started and %d opened' % (
            str(remoteaddress), len(started_connections()), len(opened_connections())))
    return result_defer


def start_streams():
    """
    """
    return tcp_stream.start_process_streams()


def stop_streams():
    """
    """
    return tcp_stream.stop_process_streams()


def cancel_file_receiving(transferID):
    """
    """
    for connections in opened_connections().values():
        for connection in connections:
            for in_file in connection.inboxFiles.values():
                if in_file.transfer_id and in_file.transfer_id == transferID:
                    connection.automat('disconnect')
                    return True
    lg.warn('%r not found' % transferID)
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
    for connections in opened_connections().values():
        for connection in connections:
            if  connection.peer_address and connection.peer_address == host or \
                connection.peer_external_address and connection.peer_external_address == host:
                i = 0
                while i < len(connection.outboxQueue):
                    fn, description, result_defer, single = connection.outboxQueue[i]
                    if fn == filename:
                        connection.outboxQueue.pop(i)
                        connection.failed_outbox_queue_item(fn, description, 'cancelled')
                        continue
                    i += 1
    for connection in started_connections().values():
        if connection.connection_address and connection.connection_address == host:
            i = 0
            while i < len(connection.pendingoutboxfiles):
                fn, description, result_defer, single = connection.pendingoutboxfiles[i]
                if fn == filename:
                    connection.pendingoutboxfiles.pop(i)
                    if not single:
                        tcp_interface.interface_cancelled_file_sending(
                            host, filename, 0, description, 'cancelled')
                    if result_defer:
                        result_defer.callback((filename, description, 'failed', 'cancelled'))
                    continue
                i += 1
                

def list_sessions():
    """
    """

#------------------------------------------------------------------------------ 

class TCPFactory(protocol.ClientFactory):
    protocol = tcp_connection.TCPConnection

    def __init__(self, connection_address):
        self.connection_address = connection_address
        self.pendingoutboxfiles = []
        self.connector = None

    def __repr__(self):
        return 'TCPFactory(%s)' % str(self.connection_address) 

    def clientConnectionFailed(self, connector, reason):
        protocol.ClientFactory.clientConnectionFailed(self, connector, reason)
        destaddress = (connector.getDestination().host, int(connector.getDestination().port))
        connection = started_connections().pop(self.connection_address, None)
        if connection:
            connection.connector = None
        for filename, description, result_defer, single in self.pendingoutboxfiles:
            if not single:
                tcp_interface.interface_cancelled_file_sending(
                    destaddress, filename, 0, description, 'connection failed')
            if result_defer:
                result_defer.callback((filename, description, 'failed', 'connection failed'))
        self.pendingoutboxfiles = []
        # lg.out(18, 'tcp_node.clientConnectionFailed from %s  :   %s closed, %d more started' % (
        #     str(destaddress), self, len(started_connections())))
        
    def add_outbox_file(self, filename, description='', result_defer=None, single=False):
        self.pendingoutboxfiles.append((filename, description, result_defer, single))
        tcp_stream.process_streams()
        
#------------------------------------------------------------------------------ 

def parseCommandLine():
    oparser = optparse.OptionParser()
    # oparser.add_option("-p", "--tcpport", dest="tcpport", type="int", help="specify port to listen for incoming TCP connections")
    oparser.add_option("-r", "--rooturl", dest="rooturl", help="specify XMLRPC server URL address in the main process")
    oparser.add_option("-x", "--xmlrpcport", dest="xmlrpcport", type="int", help="specify port for XMLRPC control")
    oparser.add_option("-d", "--debug", dest="debug", action="store_true", help="redirect output to stderr")
    # oparser.set_default('tcpport', 7771)
    oparser.set_default('rooturl', '')
    oparser.set_default('xmlrpcport', 0)
    oparser.set_default('debug', False)
    (options, args) = oparser.parse_args()
    options.xmlrpcport = int(options.xmlrpcport)
    # options.tcpport = int(options.tcpport)
    return options, args


def main():
    pass
    
if __name__ == "__main__":
    main()
    reactor.run()    
    
    

