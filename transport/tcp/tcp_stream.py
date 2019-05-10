#!/usr/bin/env python
# tcp_stream.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import time
import struct
import random

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet import defer, interfaces

from zope.interface import implementer

#------------------------------------------------------------------------------

from logs import lg

from system import tmpfile

from main import settings

from lib import misc
from lib import strng

#------------------------------------------------------------------------------

MIN_PROCESS_STREAMS_DELAY = 0.1
MAX_PROCESS_STREAMS_DELAY = 1

MAX_SIMULTANEOUS_OUTGOING_FILES = 10

#------------------------------------------------------------------------------

_LastFileID = None
_ProcessStreamsDelay = 0.01
_ProcessStreamsTask = None
_StreamCounter = 0

#------------------------------------------------------------------------------

def start_process_streams():
    reactor.callLater(0, process_streams)  # @UndefinedVariable
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
    _ProcessStreamsTask = reactor.callLater(  # @UndefinedVariable
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
    else:
        _LastFileID = newid
    return _LastFileID

#------------------------------------------------------------------------------


class TCPFileStream():

    def __init__(self, connection):
        self.stream_id = make_stream_id()  # not used at the moment, use file_id instead
        self.connection = connection
        self.outboxFiles = {}
        self.inboxFiles = {}
        self.started = time.time()
        self.sender = MultipleFilesSender(self.connection.transport)

    def close(self):
        """
        """
        self.sender.close()
        self.sender = None
        self.connection = None

    def abort_files(self, reason='connection closed'):
        from transport.tcp import tcp_connection
        inbox_file_ids_to_remove = [fid for fid in self.inboxFiles.keys()]
        outbox_file_ids_to_remove = [fid for fid in self.outboxFiles.keys()]
        if _Debug:
            lg.args(_DebugLevel, inbox_file_ids_to_remove, outbox_file_ids_to_remove)
        for file_id in inbox_file_ids_to_remove:
            # self.send_data(tcp_connection.CMD_ABORT, struct.pack('i', file_id) + b' ' + strng.to_bin(reason))
            self.inbox_file_done(file_id, 'failed', reason)
        for file_id in outbox_file_ids_to_remove:
            self.send_data(tcp_connection.CMD_ABORT, struct.pack('i', file_id) + b' ' + strng.to_bin(reason))
            if self.sender.is_sending(file_id):
                self.sender.stopFileTransfer(file_id, reason=reason)
            # self.outbox_file_done(file_id, 'failed', reason)

    def data_received(self, payload):
        """
        """
        from transport.tcp import tcp_connection
        inp = BytesIO(payload)
        try:
            file_id = int(struct.unpack('i', inp.read(4))[0])
            file_size = int(struct.unpack('i', inp.read(4))[0])
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
                lg.warn('too many incoming files, close connection %s' % str(self.connection))
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
            file_id = int(struct.unpack('i', inp.read(4))[0])
        except:
            inp.close()
            lg.exc()
            return
        inp.close()
        if file_id not in self.outboxFiles:
            lg.warn('did not found %r in outboxFiles: %r' % (file_id, self.outboxFiles.keys()))
            return
        self.outboxFiles[file_id].ok_received = True
        if _Debug:
            lg.args(_DebugLevel * 2, file_id)
        if not self.outboxFiles[file_id].registration:
            self.outbox_file_done(file_id, 'finished')

    def abort_received(self, payload):
        inp = BytesIO(payload)
        try:
            file_id = int(struct.unpack('i', inp.read(4))[0])
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
            self.report_inbox_file(infile.transfer_id, 'finished', infile.get_bytes_received())

    def on_inbox_file_register_failed(self, err, file_id):
        lg.warn('failed to register file_id=%r session=%r err: %s' % (file_id, self.session, str(err)))
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
        lg.warn('failed to register file_id=%r connection=%r err: %s' % (str(file_id), self.connection, str(err)))
        self.connection.automat('disconnect')

    def close_outbox_file(self, file_id):
        if file_id in self.outboxFiles:
            self.outboxFiles[file_id].close()
            self.outboxFiles.pop(file_id, None)
        else:
            lg.warn('outgoing TCP file %s not exist' % file_id)

    def close_inbox_file(self, file_id):
        if self.inboxFiles.get(file_id):
            self.inboxFiles[file_id].close()
            self.inboxFiles.pop(file_id, None)
        else:
            lg.warn('incoming TCP file %s not exist' % file_id)

    def report_outbox_file(self, transfer_id, status, bytes_sent, error_message=None):
        from transport.tcp import tcp_interface
        tcp_interface.interface_unregister_file_sending(
            transfer_id, status, bytes_sent, error_message)

    def report_inbox_file(self, transfer_id, status, bytes_received, error_message=None):
        from transport.tcp import tcp_interface
        tcp_interface.interface_unregister_file_receiving(
            transfer_id, status, bytes_received, error_message)

    def inbox_file_done(self, file_id, status, error_message=None):
        if _Debug:
            lg.args(_DebugLevel * 2, file_id, status, error_message)
        if file_id not in self.inboxFiles:
            lg.warn('file_id=%r not exist' % file_id)
            return
        infile = self.inboxFiles[file_id]
        if infile.registration:
            return
        self.close_inbox_file(file_id)
        if infile.transfer_id:
            self.report_inbox_file(infile.transfer_id, status, infile.get_bytes_received(), error_message)
        else:
            lg.warn('transfer_id is None, file_id=%r' % file_id)
        del infile

    def outbox_file_done(self, file_id, status, error_message=None):
        if _Debug:
            lg.args(_DebugLevel * 2, file_id, status, error_message)
        if file_id not in self.outboxFiles:
            lg.warn('file_id=%r not exist' % file_id)
            return
        outfile = self.outboxFiles[file_id]
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
        if self.fin:
            os.close(self.fin)
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
        if _Debug:
            lg.out(
                _DebugLevel, '>>>TCP-OUT %s with %d bytes reading from %s' %
                (self.file_id, self.size, self.filename))

    def close(self):
        if _Debug:
            lg.out(_DebugLevel, '>>>TCP-OUT %s CLOSED with %s | %s' % (
                self.file_id, self.stream.connection.peer_address, self.stream.connection.peer_external_address))
        self.stop()
        if self.fout:
            self.fout.close()
            self.fout = None
        self.stream = None
        self.result_defer = None

    def start(self):
        d = self.stream.sender.startFileTransfer(self.file_id, self.fout, self.send_chunk, self.transform_data)
        d.addCallback(self.transfer_finished)
        d.addErrback(self.transfer_failed)

    def stop(self):
        if self.stream.sender.is_sending(self.file_id):
            self.stream.sender.stopFileTransfer(self.file_id)

    def cancel(self):
        if _Debug:
            lg.out(_DebugLevel, 'tcp_stream.OutboxFile.cancel timeout=%d' % self.timeout)
        self.stop()

    def get_bytes_sent(self):
        return self.bytes_sent

    def is_done(self):
        return self.get_bytes_sent() == self.size and self.ok_received

    def is_timed_out(self):
        return time.time() - self.started > self.timeout

    def transfer_finished(self, last_byte):
        if self.ok_received:
            self.stream.outbox_file_done(self.file_id, 'finished')
        else:
            if _Debug:
                lg.args(_DebugLevel * 2, self.file_id)

    def transfer_failed(self, err):
        try:
            e = err.getErrorMessage()
        except:
            e = str(err)
        lg.warn('file_id=%r err: %r' % (self.file_id, e))
        self.stream.outbox_file_done(self.file_id, 'failed', e)
        return None

    def send_chunk(self, chunk):
        from transport.tcp import tcp_connection
        self.stream.connection.sendData(tcp_connection.CMD_DATA, chunk)

    def transform_data(self, data):
        data = strng.to_bin(data)
        datalength = len(data)
        datagram = b''
        datagram += struct.pack('i', self.file_id)
        datagram += struct.pack('i', self.size)
        datagram += data
        self.bytes_sent += datalength
        self.stream.connection.total_bytes_sent += datalength
        return datagram

#------------------------------------------------------------------------------

@implementer(interfaces.IProducer)
class MultipleFilesSender:
    """
    """

    CHUNK_SIZE = 2 ** 14

    def __init__(self, consumer):
        self.active_files = {}
        self.consumer = consumer
        self.consumer.registerProducer(self, False)

    def close(self):
        self.consumer.unregisterProducer()
        self.consumer = None
        self.active_files.clear()

    def is_sending(self, file_id):
        return file_id in self.active_files

    def startFileTransfer(self, file_id, file_object, writer, transform):
        """
        """
        if file_id in self.active_files:
            raise ValueError('file_id=%r already registered for transfer' % file_id)
        deferred = defer.Deferred()
        self.active_files[file_id] = (deferred, file_object, writer, transform)
        if _Debug:
            lg.args(_DebugLevel * 2, file_id, file_object, [fid for fid in self.active_files.keys()])
        if not self.consumer.producerPaused:
            self.resumeProducing()
        return deferred

    def stopFileTransfer(self, file_id, reason='cancelled'):
        if file_id not in self.active_files:
            raise ValueError('file_id=%r is not registered for transfer' % file_id)
        deferred, _, _, _ = self.active_files.pop(file_id, (None, None, None, None, ))
        if _Debug:
            lg.args(_DebugLevel * 2, file_id, [fid for fid in self.active_files.keys()])
        if deferred:
            deferred.errback(Exception(reason))

    def resumeProducing(self):
        if _Debug:
            lg.args(_DebugLevel * 2, [fid for fid in self.active_files.keys()])
        files_to_be_removed = []
        for file_id in self.active_files.keys():
            deferred, file_object, writer, transform = self.active_files.get(file_id, (None, None, None, None, ))
            if not file_object:
                lg.warn('did not found file object for file_id=%r' % file_id)
                files_to_be_removed.append(file_id)
                continue
            chunk = b''
            err = False
            if file_object:
                try:
                    chunk = file_object.read(self.CHUNK_SIZE)
                except Exception as exc:
                    lg.exc()
                    chunk = None
                    err = exc
            if not chunk:
                files_to_be_removed.append(file_id)
                if deferred:
                    if err:
                        deferred.errback(err)
                    else:
                        deferred.callback(True)
                continue
            chunk = transform(chunk)
            writer(chunk)
        for file_id in files_to_be_removed:
            self.active_files.pop(file_id)

    def pauseProducing(self):
        if _Debug:
            lg.args(_DebugLevel * 2, [fid for fid in self.active_files.keys()])

    def stopProducing(self):
        if _Debug:
            lg.args(_DebugLevel * 2, [fid for fid in self.active_files.keys()])
