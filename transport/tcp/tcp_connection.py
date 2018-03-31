#!/usr/bin/env python
# tcp_connection.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (tcp_connection.py) is part of BitDust Software.
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


"""
.. module:: tcp_connection.

.. role:: red

BitDust tcp_connection() Automat

EVENTS:
    * :red:`connection-lost`
    * :red:`connection-made`
    * :red:`data-received`
    * :red:`disconnect`
    * :red:`send-keep-alive`
    * :red:`timer-10sec`
"""
#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import time

from twisted.protocols import basic

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

#------------------------------------------------------------------------------

MAX_SIMULTANEOUS_CONNECTIONS = 250

CMD_HELLO = 'h'
CMD_WAZAP = 'w'
CMD_DATA = 'd'
CMD_OK = 'o'
CMD_ABORT = 'a'

#------------------------------------------------------------------------------


class TCPConnection(automat.Automat, basic.Int32StringReceiver):
    SoftwareVersion = '1'

    timers = {
        'timer-10sec': (10.0, ['CLIENT?', 'SERVER?']),
    }

    def __init__(self):
        self.stream = None
        self.peer_address = None
        self.peer_external_address = None
        self.peer_idurl = None
        self.total_bytes_received = 0
        self.total_bytes_sent = 0
        self.outboxQueue = []
        self.last_wazap_received = 0

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        if _Debug:
            self.log_events = True
            self.log_transitions = True

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'connection-made' and not self.isOutgoing(arg):
                self.state = 'SERVER?'
                self.doInit(arg)
            elif event == 'connection-made' and self.isOutgoing(arg):
                self.state = 'CLIENT?'
                self.doInit(arg)
                self.doCloseOutgoing(arg)
                self.doSendHello(arg)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'data-received':
                self.doReceiveData(arg)
            elif event == 'connection-lost':
                self.state = 'CLOSED'
                self.doStopInOutFiles(arg)
                self.doCloseStream(arg)
                self.doDestroyMe(arg)
            elif event == 'disconnect':
                self.state = 'DISCONNECT'
                self.doStopInOutFiles(arg)
                self.doCloseStream(arg)
                self.doDisconnect(arg)
            elif event == 'send-keep-alive':
                self.doSendWazap(arg)
        #---CLIENT?---
        elif self.state == 'CLIENT?':
            if event == 'connection-lost':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'data-received' and self.isWazap(arg) and self.isSomePendingFiles(arg):
                self.state = 'CONNECTED'
                self.doReadWazap(arg)
                self.doOpenStream(arg)
                self.doStartPendingFiles(arg)
            elif event == 'timer-10sec' or event == 'disconnect' or ( event == 'data-received' and not ( self.isWazap(arg) and self.isSomePendingFiles(arg) ) ):
                self.state = 'DISCONNECT'
                self.doDisconnect(arg)
        #---SERVER?---
        elif self.state == 'SERVER?':
            if event == 'connection-lost':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'data-received' and self.isHello(arg):
                self.state = 'CONNECTED'
                self.doReadHello(arg)
                self.doSendWazap(arg)
                self.doOpenStream(arg)
                self.doStartPendingFiles(arg)
            elif event == 'timer-10sec' or event == 'disconnect' or ( event == 'data-received' and not self.isHello(arg) ):
                self.state = 'DISCONNECT'
                self.doDisconnect(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---DISCONNECT---
        elif self.state == 'DISCONNECT':
            if event == 'connection-lost':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        return None

    def isHello(self, arg):
        """
        Condition method.
        """
        try:
            command, payload = arg
            peeraddress, peeridurl = payload.split(' ')
            peerip, peerport = peeraddress.split(':')
            peerport = int(peerport)
            peeraddress = (peerip, peerport)
        except:
            return False
        return command == CMD_HELLO

    def isWazap(self, arg):
        """
        Condition method.
        """
        try:
            command, payload = arg
        except:
            return False
        return command == CMD_WAZAP

    def isOutgoing(self, arg):
        """
        Condition method.
        """
        from transport.tcp import tcp_node
        if self.getConnectionAddress() is not None:
            if self.getConnectionAddress() in tcp_node.started_connections().keys():
                return True
        return False

    def isSomePendingFiles(self, arg):
        """
        Condition method.
        """
        return len(self.factory.pendingoutboxfiles) > 0

    def doInit(self, arg):
        """
        Action method.
        """
        from transport.tcp import tcp_node
        self.peer_address = self.getTransportAddress()
        self.peer_external_address = self.peer_address
        self.connected = time.time()
        if self.peer_address not in tcp_node.opened_connections():
            tcp_node.opened_connections()[self.peer_address] = []
        tcp_node.opened_connections()[self.peer_address].append(self)
        tcp_node.increase_connections_counter()

    def doCloseOutgoing(self, arg):
        """
        Action method.
        """
        from transport.tcp import tcp_node
        conn = tcp_node.started_connections().pop(self.getConnectionAddress())
        conn.connector = None
        # lg.out(18, 'tcp_connection.doCloseOutgoing    %s closed, %d more started' % (
        #     str(self.peer_address), len(tcp_node.started_connections())))

    def doReadHello(self, arg):
        """
        Action method.
        """
        from transport.tcp import tcp_node
        try:
            command, payload = arg
            peeraddress, peeridurl = payload.split(' ')
            peerip, peerport = peeraddress.split(':')
            peerport = int(peerport)
            peeraddress = (peerip, peerport)
        except:
            return
        # self.peer_external_address = (self.peer_external_address[0], peerport)
        self.peer_external_address = peeraddress
        self.peer_idurl = peeridurl
        if self.peer_address != self.peer_external_address:
            tcp_node.opened_connections()[self.peer_address].remove(self)
            if len(tcp_node.opened_connections()[self.peer_address]) == 0:
                tcp_node.opened_connections().pop(self.peer_address)
            self.peer_address = self.peer_external_address
            if self.peer_address not in tcp_node.opened_connections():
                tcp_node.opened_connections()[self.peer_address] = []
            tcp_node.opened_connections()[self.peer_address].append(self)
            lg.out(6, '%s : external peer address changed to %s' % (
                self, self.peer_address))
        # lg.out(18, 'tcp_connection.doReadHello from %s' % (self.peer_idurl))

    def doReadWazap(self, arg):
        """
        Action method.
        """
        try:
            command, payload = arg
        except:
            return
        self.peer_idurl = payload
        # lg.out(18, 'tcp_connection.doReadWazap from %s' % (self.peer_idurl))

    def doReceiveData(self, arg):
        """
        Action method.
        """
        try:
            command, payload = arg
        except:
            return
        if command == CMD_DATA:
            self.stream.data_received(payload)
        elif command == CMD_OK:
            self.stream.ok_received(payload)
        elif command == CMD_ABORT:
            self.stream.abort_received(payload)
        elif command == CMD_WAZAP:
            self.last_wazap_received = time.time()
        else:
            pass

    def doSendHello(self, arg):
        """
        Action method.
        """
        from transport.tcp import tcp_node
        host = tcp_node.my_host() or '127.0.0.1:7771'
        idurl = tcp_node.my_idurl() or 'None'
        payload = host + ' ' + idurl
        self.sendData(CMD_HELLO, payload)

    def doSendWazap(self, arg):
        """
        Action method.
        """
        from transport.tcp import tcp_node
        payload = tcp_node.my_idurl() or 'None'
        self.sendData(CMD_WAZAP, payload)

    def doStartPendingFiles(self, arg):
        """
        Action method.
        """
        for filename, description, result_defer, keep_alive in self.factory.pendingoutboxfiles:
            self.append_outbox_file(filename, description, result_defer, keep_alive)
        self.factory.pendingoutboxfiles = []

    def doStopInOutFiles(self, arg):
        """
        Action method.
        """
        self.stream.abort_files('disconnecting')

    def doOpenStream(self, arg):
        """
        Action method.
        """
        from transport.tcp import tcp_stream
        self.stream = tcp_stream.TCPFileStream(self)

    def doCloseStream(self, arg):
        """
        Action method.
        """
        self.stream.close()
        del self.stream
        self.stream = None

    def doDisconnect(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'tcp_connection.doDisconnect with %s' % str(self.peer_address))
        try:
            self.transport.stopListening()
        except:
            try:
                self.transport.loseConnection()
            except:
                lg.exc()

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        from transport.tcp import tcp_node
        # lg.out(18, 'tcp_connection.doDestroyMe %s' % str(self))
        self.destroy()
        if self.peer_address in tcp_node.opened_connections():
            tcp_node.opened_connections()[self.peer_address].remove(self)
            if len(tcp_node.opened_connections()[self.peer_address]) == 0:
                tcp_node.opened_connections().pop(self.peer_address)
            tcp_node.decrease_connections_counter()
        else:
            raise Exception('not found %s in the opened connections' % self.peer_address)
        self.stream = None
        self.peer_address = None
        self.peer_external_address = None
        self.peer_idurl = None
        self.outboxQueue = []

    def getTransportAddress(self):
        peer = self.transport.getPeer()
        return (peer.host, int(peer.port))

    def getConnectionAddress(self):
        return self.factory.connection_address

    def getAddress(self):
        addr = self.getConnectionAddress()
        if not addr:
            addr = self.getTransportAddress()
        return addr

    def connectionMade(self):
        if _Debug:
            lg.out(_DebugLevel, 'tcp_connection.connectionMade %s:%d' % self.getTransportAddress())
        address = self.getAddress()
        name = 'tcp_connection[%s:%d]' % (address[0], address[1])
        automat.Automat.__init__(self, name, 'AT_STARTUP', _DebugLevel)
        self.log_transitions = _Debug
        self.automat('connection-made')

    def connectionLost(self, reason):
        if _Debug:
            lg.out(_DebugLevel, 'tcp_connection.connectionLost with %s:%d' % self.getTransportAddress())
        self.automat('connection-lost')

    def sendData(self, command, payload):
        try:
            data = self.SoftwareVersion + str(command.lower())[0] + payload
            self.sendString(data)
        except:
            return False
        self.automat('data-sent', data)
        return True

    def stringReceived(self, data):
        try:
            version = data[0]
            command = data[1]
            payload = data[2:]
        except:
            lg.warn('invalid string received in tcp connection')
            try:
                self.transport.stopListening()
            except:
                try:
                    self.transport.loseConnection()
                except:
                    lg.exc()
            return
        # print '>>>>>> [%s] %d bytes' % (command, len(payload))
        self.automat('data-received', (command, payload))

    def append_outbox_file(self, filename, description='', result_defer=None, keep_alive=True):
        self.outboxQueue.append((filename, description, result_defer, keep_alive))

    def process_outbox_queue(self):
        if self.state != 'CONNECTED':
            return False
        if self.stream is None:
            return False
        from transport.tcp import tcp_stream
        has_reads = False
        while len(self.outboxQueue) > 0 and len(self.stream.outboxFiles) < tcp_stream.MAX_SIMULTANEOUS_OUTGOING_FILES:
            filename, description, result_defer, keep_alive = self.outboxQueue.pop(0)
            has_reads = True
            # we have a queue of files to be sent
            # somehow file may be removed before we start sending it
            # so we check it here and skip not existed files
            if not os.path.isfile(filename):
                self.failed_outbox_queue_item(filename, description, 'file not exist')
                if not keep_alive:
                    self.automat('shutdown')
                continue
            try:
                filesize = os.path.getsize(filename)
            except:
                self.failed_outbox_queue_item(filename, description, 'can not get file size')
                if not keep_alive:
                    self.automat('shutdown')
                continue
            self.stream.create_outbox_file(filename, filesize, description, result_defer, keep_alive)
        return has_reads

    def failed_outbox_queue_item(self, filename, description='', error_message=''):
        from transport.tcp import tcp_interface
        lg.out(6, 'tcp_connection.failed_outbox_queue_item %s because %s' % (filename, error_message))
        tcp_interface.interface_cancelled_file_sending(
            self.getAddress(), filename, 0, description, error_message)
