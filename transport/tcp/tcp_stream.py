#!/usr/bin/env python
# tcp_stream.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (tcp_stream.py) is part of BitDust Software.
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
..module:: tcp_stream
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import open
from io import BytesIO

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import time
import struct
import random

from twisted.internet import reactor
from twisted.protocols import basic

#------------------------------------------------------------------------------

from logs import lg

from system import tmpfile

from main import settings

from lib import misc

#------------------------------------------------------------------------------

MIN_PROCESS_STREAMS_DELAY = 0.1
MAX_PROCESS_STREAMS_DELAY = 1
# TODO: at the moment for TCP - only one file per connection at once
# need to switch from basic.FileSender to something more advanced
# consider using Twisted AMP
MAX_SIMULTANEOUS_OUTGOING_FILES = 1

#------------------------------------------------------------------------------

_LastFileID = None
_ProcessStreamsDelay = 0.01
_ProcessStreamsTask = None
_StreamCounter = 0

#------------------------------------------------------------------------------

def start_process_streams():
    reactor.callLater(0, process_streams)
    return True


def stop_process_streams():
    global _ProcessStreamsTask
    if _ProcessStreamsTask:
        if _ProcessStreamsTask.active():
            _ProcessStreamsTask.cancel()
        _ProcessStreamsTask = None
        return True
    return False


def process_streams():
    from transport.tcp import tcp_node
    global _ProcessStreamsDelay
    global _ProcessStreamsTask
    has_activity = False
    for connections in tcp_node.opened_connections().values():
        for connection in connections:
            has_timeouts = False  # connection.stream.timeout_incoming_files()
            has_sends = False  # connection.stream.process_sending_data()
            has_outbox = connection.process_outbox_queue()
            if has_timeouts or has_sends or has_outbox:
                has_activity = True
    _ProcessStreamsDelay = misc.LoopAttenuation(
        _ProcessStreamsDelay, has_activity,
        MIN_PROCESS_STREAMS_DELAY,
        MAX_PROCESS_STREAMS_DELAY,)
    # attenuation
    _ProcessStreamsTask = reactor.callLater(
        _ProcessStreamsDelay, process_streams)

#------------------------------------------------------------------------------


def list_input_streams(sorted_by_time=True):
    from transport.tcp import tcp_node
    streams = []
    for connections in tcp_node.opened_connections().values():
        for connection in connections:
            if connection.stream:
                streams.extend(list(connection.stream.inboxFiles.values()))
    if sorted_by_time:
        streams.sort(key=lambda stream: stream.started)
    return streams


def list_output_streams(sorted_by_time=True):
    from transport.tcp import tcp_node
    streams = []
    for connections in tcp_node.opened_connections().values():
        for connection in connections:
            if connection.stream:
                streams.extend(list(connection.stream.outboxFiles.values()))
    if sorted_by_time:
        streams.sort(key=lambda stream: stream.started)
    return streams


def find_stream(file_id=None, transfer_id=None):
    from transport.tcp import tcp_node
    for connections in tcp_node.opened_connections().values():
        for connection in connections:
            if connection.stream:
                for out_file in connection.stream.outboxFiles.values():
                    if file_id and out_file.file_id == file_id:
                        return out_file
                    if transfer_id and out_file.transfer_id == transfer_id:
                        return out_file
                for in_file in connection.stream.inboxFiles.values():
                    if file_id and in_file.file_id == file_id:
                        return in_file
                    if transfer_id and in_file.transfer_id == transfer_id:
                        return in_file
    return None

#------------------------------------------------------------------------------

def make_stream_id():
    """
    """
    global _StreamCounter
    _StreamCounter += 1
    return random.randint(10, 99) * 1000000 + random.randint(10, 99) * 10000 + _StreamCounter % 10000


def make_file_id():
    """
    Generate a unique file ID for OutboxFile.
    """
    global _LastFileID
    newid = int(str(int(time.time() * 100.0))[4:])
    if _LastFileID is None:
        _LastFileID = newid
    elif _LastFileID >= newid:
        _LastFileID += 1
    return _LastFileID

#------------------------------------------------------------------------------


class TCPFileStream():

    def __init__(self, connection):
        self.stream_id = make_stream_id()  # not used at the moment, use file_id instead
        self.connection = connection
        self.outboxFiles = {}
        self.inboxFiles = {}
        self.started = time.time()

    def close(self):
        """
        """
        self.connection = None

    def abort_files(self, reason='connection closed'):
        from transport.tcp import tcp_connection
        file_ids_to_remove = list(self.inboxFiles.keys())
        for file_id in file_ids_to_remove:
            # self.send_data(tcp_connection.CMD_ABORT, struct.pack('i', file_id)+' '+reason)
            self.inbox_file_done(file_id, 'failed', reason)
        file_ids_to_remove = list(self.outboxFiles.keys())
        for file_id in file_ids_to_remove:
            self.send_data(
                tcp_connection.CMD_ABORT, struct.pack(
                    'i', file_id) + ' ' + reason)
            self.outbox_file_done(file_id, 'failed', reason)

    def data_received(self, payload):
        """
        """
        from transport.tcp import tcp_connection
        inp = BytesIO(payload)
        try:
            file_id = struct.unpack('i', inp.read(4))[0]
            file_size = struct.unpack('i', inp.read(4))[0]
        except:
            inp.close()
            lg.exc()
            return
        inp_data = inp.read()
        inp.close()
        if file_id not in self.inboxFiles:
            if len(self.inboxFiles) >= 2 * MAX_SIMULTANEOUS_OUTGOING_FILES:
                # too many incoming files, seems remote guy is cheating - drop
                # that session!
                lg.warn('too many incoming files, close connection %s' %
                        str(self.connection))
                self.connection.automat('disconnect')
                return
            self.create_inbox_file(file_id, file_size)
        self.inboxFiles[file_id].input_data(inp_data)
        if self.inboxFiles[file_id].is_done():
            self.send_data(tcp_connection.CMD_OK, struct.pack('i', file_id))
            self.inbox_file_done(file_id, 'finished')

    def ok_received(self, payload):
        inp = BytesIO(payload)
        try:
            file_id = struct.unpack('i', inp.read(4))[0]
        except:
            inp.close()
            lg.exc()
            return
        inp.close()
        self.outboxFiles[file_id].ok_received = True
        if not self.outboxFiles[file_id].registration:
            self.outbox_file_done(file_id, 'finished')

    def abort_received(self, payload):
        inp = BytesIO(payload)
        try:
            file_id = struct.unpack('i', inp.read(4))[0]
        except:
            inp.close()
            lg.exc()
            return
        reason = inp.read()
        inp.close()
        self.inbox_file_done(file_id, 'failed', reason)

    def send_data(self, command, payload):
        return self.connection.sendData(command, payload)

    def create_inbox_file(self, file_id, file_size):
        from transport.tcp import tcp_interface
        infile = InboxFile(self, file_id, file_size)
        d = tcp_interface.interface_register_file_receiving(
            self.connection.getAddress(), self.connection.peer_idurl, infile.filename)
        d.addCallback(self.on_inbox_file_registered, file_id)
        d.addErrback(self.on_inbox_file_register_failed, file_id)
        infile.registration = d
        self.inboxFiles[file_id] = infile

    def on_inbox_file_registered(self, response, file_id):
        try:
            transfer_id = int(response)
        except:
            transfer_id = None
        self.inboxFiles[file_id].transfer_id = transfer_id
        self.inboxFiles[file_id].registration = None
        if self.inboxFiles[file_id].is_done():
            infile = self.inboxFiles[file_id]
            self.close_inbox_file(file_id)
            self.report_inbox_file(
                infile.transfer_id,
                'finished',
                infile.get_bytes_received())

    def on_inbox_file_register_failed(self, err, file_id):
        if _Debug:
            lg.warn(
                'failed to register, file_id=%s err:\n%s' %
                (str(file_id), str(err)))
            lg.out(_DebugLevel - 8, '        close session %s' % self.session)
        self.connection.automat('disconnect')

    def create_outbox_file(self, filename, filesize, description, result_defer, keep_alive,):
        from transport.tcp import tcp_interface
        file_id = make_file_id()
        outfile = OutboxFile(self, filename, file_id, filesize, description, result_defer, keep_alive)
        if keep_alive:
            d = tcp_interface.interface_register_file_sending(
                self.connection.getAddress(), self.connection.peer_idurl, filename, description)
            d.addCallback(self.on_outbox_file_registered, file_id)
            d.addErrback(self.on_outbox_file_register_failed, file_id)
            outfile.registration = d
        self.outboxFiles[file_id] = outfile
        outfile.start()

    def on_outbox_file_registered(self, response, file_id):
        try:
            transfer_id = int(response)
        except:
            transfer_id = None
        self.outboxFiles[file_id].transfer_id = transfer_id
        self.outboxFiles[file_id].registration = None
        if self.outboxFiles[file_id].is_done():
            self.outbox_file_done(file_id, 'finished')

    def on_outbox_file_register_failed(self, err, file_id):
        if _Debug:
            lg.warn('failed to register, file_id=%s :\n%s' % (str(file_id), str(err)))
            lg.out(_DebugLevel - 8, '        close session %s' % self.connection)
        self.connection.automat('disconnect')

    def close_outbox_file(self, file_id):
        if self.outboxFiles.get(file_id):
            self.outboxFiles[file_id].close()
            del self.outboxFiles[file_id]
        else:
            lg.warn('outgoing TCP file %s not exist' % file_id)

    def close_inbox_file(self, file_id):
        if self.inboxFiles.get(file_id):
            self.inboxFiles[file_id].close()
            del self.inboxFiles[file_id]
        else:
            lg.warn('incoming TCP file %s not exist' % file_id)

    def report_outbox_file(
            self,
            transfer_id,
            status,
            bytes_sent,
            error_message=None):
        from transport.tcp import tcp_interface
        # lg.out(18, 'tcp_stream.report_outbox_file %s %s %d' % (transfer_id, status, bytes_sent))
        tcp_interface.interface_unregister_file_sending(
            transfer_id, status, bytes_sent, error_message)

    def report_inbox_file(
            self,
            transfer_id,
            status,
            bytes_received,
            error_message=None):
        from transport.tcp import tcp_interface
        # lg.out(18, 'tcp_stream.report_inbox_file %s %s %d' % (transfer_id, status, bytes_received))
        tcp_interface.interface_unregister_file_receiving(
            transfer_id, status, bytes_received, error_message)

    def inbox_file_done(self, file_id, status, error_message=None):
        """
        """
        try:
            infile = self.inboxFiles[file_id]
        except:
            lg.exc()
            return
        if infile.registration:
            return
        self.close_inbox_file(file_id)
        if infile.transfer_id:
            self.report_inbox_file(infile.transfer_id, status, infile.get_bytes_received(), error_message)
        else:
            lg.warn('transfer_id is None, file_id=%s' % (str(file_id)))
        del infile

    def outbox_file_done(self, file_id, status, error_message=None):
        """
        """
        try:
            outfile = self.outboxFiles[file_id]
        except:
            lg.exc()
            return
        if outfile.result_defer:
            outfile.result_defer.callback((outfile, status, error_message))
            outfile.result_defer = None
        if outfile.registration:
            return
        self.close_outbox_file(file_id)
        if outfile.transfer_id:
            self.report_outbox_file(outfile.transfer_id, status, outfile.get_bytes_sent(), error_message)
        if not outfile.keep_alive and not self.connection.factory.keep_alive:
            self.connection.automat('disconnect')
        del outfile

#------------------------------------------------------------------------------


class InboxFile():

    def __init__(self, stream, file_id, file_size):
        self.typ = 'tcp-in'
        self.transfer_id = None
        self.registration = None
        self.stream = stream
        self.file_id = file_id
        self.size = file_size
        self.fin, self.filename = tmpfile.make("tcp-in", extension='.tcp')
        self.bytes_received = 0
        self.started = time.time()
        self.last_block_time = time.time()
        self.timeout = max(int(self.size / settings.SendingSpeedLimit()), 3)
        if _Debug:
            lg.out(_DebugLevel, '<<<TCP-IN %s with %d bytes write to %s' % (
                self.file_id, self.size, self.filename))

    def close(self):
        if _Debug:
            lg.out(_DebugLevel, '<<<TCP-IN %s CLOSED with %s | %s' % (
                self.file_id, self.stream.connection.peer_address, self.stream.connection.peer_external_address))
        try:
            os.close(self.fin)
        except:
            lg.exc()
        self.fin = None
        self.stream = None

    def get_bytes_received(self):
        return self.bytes_received

    def input_data(self, data):
        os.write(self.fin, data)
        self.bytes_received += len(data)
        self.stream.connection.total_bytes_received += len(data)
        self.last_block_time = time.time()

    def is_done(self):
        return self.bytes_received == self.size

    def is_timed_out(self):
        return time.time() - self.started > self.timeout

#------------------------------------------------------------------------------


class OutboxFile():

    def __init__(self, stream, filename, file_id, filesize, description='', result_defer=None, keep_alive=True):
        self.typ = 'tcp-out'
        self.transfer_id = None
        self.registration = None
        self.stream = stream
        self.file_id = file_id
        self.filename = filename
        self.size = filesize
        self.description = description
        self.keep_alive = keep_alive
        self.result_defer = result_defer
        self.ok_received = False
        self.bytes_sent = 0
        self.bytes_out = 0
        self.started = time.time()
        self.timeout = max(int(self.size / settings.SendingSpeedLimit()), 6)
        self.fout = open(self.filename, 'rb')
        self.sender = None
        if _Debug:
            lg.out(
                _DebugLevel, '>>>TCP-OUT %s with %d bytes reading from %s' %
                (self.file_id, self.size, self.filename))

    def close(self):
        if _Debug:
            lg.out(_DebugLevel, '>>>TCP-OUT %s CLOSED with %s | %s' % (
                self.file_id, self.stream.connection.peer_address, self.stream.connection.peer_external_address))
        self.stop()
        try:
            self.fout.close()
        except:
            lg.exc()
        self.fout = None
        self.stream = None
        self.result_defer = None

    def start(self):
        self.sender = FileSender(self)
        d = self.sender.beginFileTransfer(
            self.fout,
            self.stream.connection.transport,
            self.sender.transform_data)
        d.addCallback(self.transfer_finished)
        d.addErrback(self.transfer_failed)

    def stop(self):
        if not self.sender:
            return
        if not self.sender.deferred:
            return
        if self.sender.deferred.called:
            return
        self.sender.stopProducing()

    def cancel(self):
        lg.out(6, 'tcp_stream.OutboxFile.cancel timeout=%d' % self.timeout)
        self.stop()

    def get_bytes_sent(self):
        return self.bytes_sent

    def is_done(self):
        return self.get_bytes_sent() == self.size and self.ok_received

    def is_timed_out(self):
        return time.time() - self.started > self.timeout

    def transfer_finished(self, last_byte):
        if not self.sender:
            return
        self.sender.close()
        del self.sender
        self.sender = None
        if self.ok_received:
            self.stream.outbox_file_done(self.file_id, 'finished')

    def transfer_failed(self, err):
        lg.out(18, 'tcp_stream.transfer_failed:   %r' % (err))
        if not self.sender:
            return None
        self.sender.close()
        del self.sender
        self.sender = None
        try:
            e = err.getErrorMessage()
        except:
            e = str(err)
        self.stream.outbox_file_done(self.file_id, 'failed', e)
        return None

#------------------------------------------------------------------------------


class FileSender(basic.FileSender):

    def __init__(self, parent):
        self.parent = parent
        from transport.tcp import tcp_connection
        self.CMD_DATA = tcp_connection.CMD_DATA

    def close(self):
        self.parent = None

    def transform_data(self, data):
        # if isinstance(data, six.binary_type):
        #     data = data.decode('utf-8')
        datalength = len(data)
        datagram = ''
        datagram += struct.pack('i', self.parent.file_id)
        datagram += struct.pack('i', self.parent.size)
        datagram += data
        self.parent.bytes_sent += datalength
        self.parent.stream.connection.total_bytes_sent += datalength
        return datagram

    def resumeProducing(self):
        chunk = ''
        if self.file:
            #             try:
            chunk = self.file.read(self.CHUNK_SIZE)
#             except:
#                 lg.exc()
#                 return
#                 chunk = None
#                 self.file = None
#                 self.consumer.unregisterProducer()
#                 if self.deferred:
#                     self.deferred.errback(self.lastSent)
#                     self.deferred = None
#                 lg.exc()
#                 return
        if not chunk:
            self.file = None
            self.consumer.unregisterProducer()
            if self.deferred:
                self.deferred.callback(self.lastSent)
                self.deferred = None
            return
        if self.transform:
            chunk = self.transform(chunk)
        self.parent.stream.connection.sendData(self.CMD_DATA, chunk)
        self.lastSent = chunk[-1:]
