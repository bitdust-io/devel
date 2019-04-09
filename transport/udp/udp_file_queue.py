#!/usr/bin/env python
# udp_file_queue.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (udp_file_queue.py) is part of BitDust Software.
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
..module:: udp_file_queue.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import open
from io import StringIO

#------------------------------------------------------------------------------

import os
import time
import struct
import random

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from lib import strng
from lib import udp

from system import tmpfile

from contacts import contactsdb

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

MAX_SIMULTANEOUS_STREAMS_PER_SESSION = 16
NUMBER_OF_STREAMS_TO_REMEMBER = MAX_SIMULTANEOUS_STREAMS_PER_SESSION * 8 * 2

#------------------------------------------------------------------------------

_StreamCounter = 0

#------------------------------------------------------------------------------


class FileQueue:

    def __init__(self, session):
        self.session = session
        self.streams = {}
        self.outboxFiles = {}
        self.inboxFiles = {}
        self.outboxQueue = []
        self.dead_streams = []

    def make_unique_stream_id(self):
        global _StreamCounter
        _StreamCounter += 1
        n = 10 + max(contactsdb.contact_position(self.session.peer_idurl), 0) % 89
        return n * 1000000 + random.randint(10, 99) * 10000 + _StreamCounter % 10000

    def report_failed_outbox_queue(self, error_message):
        for filename, description, result_defer, keep_alive in self.outboxQueue:
            self.on_failed_outbox_queue_item(filename, description, error_message, result_defer, keep_alive)

    def report_failed_outbox_files(self, error_message):
        for outfile in self.outboxFiles.values():
            outfile.status = 'failed'
            outfile.error_message = error_message
            self.report_outbox_file(outfile)

    def report_failed_inbox_files(self, error_message):
        for infile in self.inboxFiles.values():
            infile.status = 'failed'
            infile.error_message = error_message
            self.report_inbox_file(infile)

    def close(self):
        for stream in self.streams.values():
            stream.on_close()
        self.outboxQueue = []

    def do_send_data(self, stream_id, outfile, output):
        #         if _Debug:
        #             import random
        #             if random.randint(1, 100) > 90:
        #                 return True
        newoutput = ''.join((
            struct.pack('i', stream_id),
            struct.pack('i', outfile.size),
            output))
        return self.session.send_packet(udp.CMD_DATA, strng.to_bin(newoutput))

    def do_send_ack(self, stream_id, infile, ack_data):
        #         if _Debug:
        #             import random
        #             if random.randint(1, 100) > 90:
        #                 return True
        newoutput = ''.join((
            struct.pack('i', stream_id),
            ack_data))
        return self.session.send_packet(udp.CMD_ACK, strng.to_bin(newoutput))

    def append_outbox_file(self, filename, description='', result_defer=None, keep_alive=True):
        from transport.udp import udp_session
        self.outboxQueue.append((filename, description, result_defer, keep_alive))
        if _Debug:
            lg.out(18, 'udp_file_queue.append_outbox_file %s for %s : %s, streams=%d, queue=%d' % (
                os.path.basename(filename), self.session.peer_id, description, len(self.streams), len(self.outboxQueue)))
        udp_session.process_sessions([self.session, ])

    def insert_outbox_file(self, filename, description='', result_defer=None, keep_alive=True):
        from transport.udp import udp_session
        self.outboxQueue.insert(0, (filename, description, result_defer, keep_alive))
        if _Debug:
            lg.out(18, 'udp_file_queue.insert_outbox_file %s for %s : %s, streams=%d, queue=%d' % (
                os.path.basename(filename), self.session.peer_id, description, len(self.streams), len(self.outboxQueue)))
        udp_session.process_sessions([self.session, ])

    def process_outbox_queue(self):
        has_reads = False
        while len(self.outboxQueue) > 0:
            if len(self.streams) >= MAX_SIMULTANEOUS_STREAMS_PER_SESSION:
                # lg.warn('too much streams: %d' % len(self.streams))
                break
            filename, description, result_defer, keep_alive = self.outboxQueue.pop(0)
            has_reads = True
            # we have a queue of files to be sent
            # somehow file may be removed before we start sending it
            # so I check it here and skip not existed files
            if not os.path.isfile(filename):
                self.on_failed_outbox_queue_item(filename, description, 'file not exist', result_defer, keep_alive)
                continue
            try:
                filesize = os.path.getsize(filename)
            except:
                self.on_failed_outbox_queue_item(filename, description, 'can not get file size', result_defer, keep_alive)
                continue
            self.start_outbox_file(filename, filesize, description, result_defer, keep_alive)
        return has_reads

    def process_outbox_files(self):
        has_sends = False
        for outfile in self.outboxFiles.values():
            has_sends = has_sends or outfile.process()
        return has_sends

    def start_outbox_file(self, filename, filesize, description, result_defer, keep_alive):
        from transport.udp import udp_interface
        from transport.udp import udp_stream
        stream_id = self.make_unique_stream_id()
        if _Debug:
            lg.out(12, 'udp_file_queue.start_outbox_file %d %s %s %d %s' % (
                stream_id, description, os.path.basename(filename), filesize, self.session.peer_id))
        self.outboxFiles[stream_id] = OutboxFile(
            self, stream_id, filename, filesize, description, result_defer, keep_alive)
        self.streams[stream_id] = udp_stream.create(stream_id, self.outboxFiles[stream_id], self)
        if keep_alive:
            d = udp_interface.interface_register_file_sending(
                self.session.peer_id, self.session.peer_idurl, filename, description)
            d.addCallback(self.on_outbox_file_registered, stream_id)
            d.addErrback(self.on_outbox_file_register_failed, stream_id)
            self.outboxFiles[stream_id].registration = d

    def start_inbox_file(self, stream_id, data_size):
        from transport.udp import udp_interface
        from transport.udp import udp_stream
        if _Debug:
            lg.out(12, 'udp_file_queue.start_inbox_file %d %d %s' % (
                stream_id, data_size, self.session.peer_id))
        self.inboxFiles[stream_id] = InboxFile(self, stream_id, data_size)
        self.streams[stream_id] = udp_stream.create(stream_id, self.inboxFiles[stream_id], self)
        d = udp_interface.interface_register_file_receiving(
            self.session.peer_id, self.session.peer_idurl,
            self.inboxFiles[stream_id].filename, self.inboxFiles[stream_id].size)
        d.addCallback(self.on_inbox_file_registered, stream_id)
        d.addErrback(self.on_inbox_file_register_failed, stream_id)
        self.inboxFiles[stream_id].registration = d

    def erase_stream(self, stream_id):
        del self.streams[stream_id]
        self.dead_streams.append(stream_id)
        if len(self.dead_streams) > NUMBER_OF_STREAMS_TO_REMEMBER:
            self.dead_streams.pop(0)
        if _Debug:
            lg.out(18, 'udp_file_queue.erase_stream %s' % stream_id)

    def close_outbox_file(self, stream_id):
        # if _Debug:
        #     lg.out(18, 'close_outbox_file %r' % stream_id)
        if self.outboxFiles.get(stream_id):
            self.outboxFiles[stream_id].close()
            del self.outboxFiles[stream_id]
        else:
            lg.warn('outgoing UDP file %s not exist' % stream_id)

    def close_inbox_file(self, stream_id):
        # if _Debug:
        #     lg.out(18, 'close_inbox_file %r' % stream_id)
        if self.inboxFiles.get(stream_id):
            self.inboxFiles[stream_id].close()
            del self.inboxFiles[stream_id]
        else:
            lg.warn('incoming UDP file %s not exist' % stream_id)

    def report_outbox_file(self, outfile):
        from transport.udp import udp_interface
        if _Debug:
            lg.out(18, 'udp_file_queue.report_outbox_file %s %s %d bytes "%s"' % (
                outfile.transfer_id, outfile.status, outfile.bytes_delivered, outfile.error_message))
        udp_interface.interface_unregister_file_sending(
            outfile.transfer_id, outfile.status, outfile.bytes_delivered, outfile.error_message)

    def report_inbox_file(self, infile):
        from transport.udp import udp_interface
        if _Debug:
            lg.out(18, 'udp_file_queue.report_inbox_file {%s} %s %s %d bytes "%s"' % (
                os.path.basename(infile.filename), infile.transfer_id,
                infile.status, infile.bytes_received, infile.error_message))
        udp_interface.interface_unregister_file_receiving(
            infile.transfer_id, infile.status, infile.bytes_received, infile.error_message)

    #-------------------------------------------------------------------------

    def on_received_data_packet(self, payload):
        inp = StringIO(payload)
        try:
            stream_id = int(struct.unpack('i', inp.read(4))[0])
            data_size = int(struct.unpack('i', inp.read(4))[0])
        except:
            inp.close()
            lg.exc()
            return
        if not self.session.peer_id:
            inp.close()
            if _Debug:
                lg.warn('SEND ZERO ACK, peer id is unknown yet %s' % stream_id)
            self.do_send_ack(stream_id, None, '')
            return
        if stream_id not in list(self.streams.keys()):
            if stream_id in self.dead_streams:
                inp.close()
                # if _Debug:
                # lg.warn('SEND ZERO ACK, got old block %s' % stream_id)
                self.do_send_ack(stream_id, None, '')
                return
            if len(self.streams) >= 2 * MAX_SIMULTANEOUS_STREAMS_PER_SESSION:
                # too many incoming streams, seems remote side is cheating - drop that session!
                # TODO: need to add some protection - keep a list of bad guys?
                inp.close()
                # lg.warn('too many incoming files for session %s' % str(self.session))
                # self.session.automat('shutdown')
                if _Debug:
                    lg.warn('SEND ZERO ACK, too many active streams: %d  skipped: %s %s' % (
                        len(self.streams), stream_id, self.session.peer_id))
                self.do_send_ack(stream_id, None, '')
                return
            self.start_inbox_file(stream_id, data_size)
        try:
            self.streams[stream_id].on_block_received(inp)
        except:
            lg.exc()
        inp.close()

    def on_received_ack_packet(self, payload):
        inp = StringIO(payload)
        try:
            stream_id = int(struct.unpack('i', inp.read(4))[0])
        except:
            inp.close()
            lg.exc()
            # self.session.automat('shutdown')
            return
        if stream_id not in list(self.streams.keys()):
            inp.close()
            # if not self.receivedFiles.has_key(stream_id):
            # lg.warn('unknown stream_id=%d in ACK packet from %s' % (
            #     stream_id, self.session.peer_address))
            # self.session.automat('shutdown')
            if stream_id in self.dead_streams:
                # print 'old ack', stream_id
                pass
            else:
                if _Debug:
                    lg.warn('%s - what a stream ???' % stream_id)
            # self.session.automat('shutdown')
            return
        try:
            self.streams[stream_id].on_ack_received(inp)
        except:
            lg.exc()
            self.session.automat('shutdown')
        inp.close()

    def on_inbox_file_done(self, stream_id):
        assert stream_id in list(self.inboxFiles.keys())
        infile = self.inboxFiles[stream_id]
        if _Debug:
            lg.out(18, 'udp_file_queue.on_inbox_file_done %s (%d bytes) %s "%s" registration=%r' % (
                stream_id, infile.size, infile.status, infile.error_message, infile.registration))
        if infile.registration:
            return
        if infile.transfer_id:
            self.report_inbox_file(infile)
        s = self.streams[stream_id]
        s.on_close()
        s = None

    def on_outbox_file_done(self, stream_id):
        assert stream_id in list(self.outboxFiles.keys())
        outfile = self.outboxFiles[stream_id]
        if _Debug:
            lg.out(18, 'udp_file_queue.on_outbox_file_done %s (%d bytes) %s "%s" registration=%r' % (
                stream_id, outfile.size, outfile.status, outfile.error_message, outfile.registration))
        if outfile.registration:
            return
        if outfile.transfer_id:
            self.report_outbox_file(outfile)
        if outfile.result_defer:
            outfile.result_defer.callback((outfile, outfile.status, outfile.error_message))
            outfile.result_defer = None
        s = self.streams[stream_id]
        s.on_close()
        s = None
        reactor.callLater(0, self.process_outbox_queue)

    def on_inbox_file_registered(self, response, stream_id):
        if stream_id not in list(self.inboxFiles.keys()):
            lg.warn('stream %d not found in the inboxFiles' % stream_id)
            return
        try:
            transfer_id = int(response)
        except:
            transfer_id = None
        infile = self.inboxFiles[stream_id]
        infile.transfer_id = transfer_id
        infile.registration = None
        if _Debug:
            lg.out(
                18, 'udp_file_queue.on_inbox_file_registered %d transfer_id=%r status=%s' %
                (stream_id, transfer_id, infile.status))
        if infile.status:
            self.report_inbox_file(infile)
            s = self.streams[stream_id]
            s.on_close()
            s = None

    def on_inbox_file_register_failed(self, err, stream_id):
        lg.out(
            2, 'udp_file_queue.on_inbox_file_register_failed ERROR failed to register, stream_id=%s, err: %s' %
            (str(stream_id), err))
        self.session.automat('shutdown')

    def on_outbox_file_registered(self, response, stream_id):
        if stream_id not in list(self.outboxFiles.keys()):
            lg.warn('stream %d not found in the outboxFiles' % stream_id)
            return
        try:
            transfer_id = int(response)
        except:
            transfer_id = None
        outfile = self.outboxFiles[stream_id]
        outfile.transfer_id = transfer_id
        outfile.registration = None
        if _Debug:
            lg.out(
                18, 'udp_file_queue.on_outbox_file_registered %d transfer_id=%r status=%s' %
                (stream_id, transfer_id, outfile.status))
        if outfile.status:
            self.report_outbox_file(outfile)
            s = self.streams[stream_id]
            s.on_close()
            s = None

    def on_outbox_file_register_failed(self, err, stream_id):
        lg.out(2, 'udp_file_queue.on_outbox_file_register_failed ERROR failed to register, stream_id=%s :\n%s' % (
            str(stream_id), str(err)))
        lg.out(6, 'udp_file_queue.on_outbox_file_register_failed close session %s' % self.session)
        self.session.automat('shutdown')

    def on_failed_outbox_queue_item(self, filename, description='', error_message='', result_defer=None, keep_alive=True):
        from transport.udp import udp_interface
        if _Debug:
            lg.out(18, 'udp_file_queue.failed_outbox_queue_item %s because %s' % (filename, error_message))
        try:
            udp_interface.interface_cancelled_file_sending(
                self.session.peer_id, filename, 0, description, error_message).addErrback(lambda err: lg.exc(err))
        except Exception as exc:
            lg.warn(str(exc))
        if result_defer:
            result_defer.callback(
                ((filename, description), 'failed', error_message))

    def on_timeout_receiving(self, stream_id):
        assert stream_id in list(self.inboxFiles.keys())
        infile = self.inboxFiles[stream_id]
        if _Debug:
            lg.out(18, 'udp_file_queue.on_timeout_receiving stream_id=%s %d : %s' % (
                stream_id, infile.bytes_received, infile.error_message))
        if infile.registration:
            return
        if infile.transfer_id:
            self.report_inbox_file(infile)
        if _Debug:
            lg.out(2, '!' * 80)
        s = self.streams[stream_id]
        s.on_close()
        s = None

    def on_timeout_sending(self, stream_id):
        assert stream_id in list(self.outboxFiles.keys())
        outfile = self.outboxFiles[stream_id]
        if _Debug:
            lg.out(18, 'udp_file_queue.on_timeout_sending stream_id=%s %d/%d bytes sent : %s' % (
                stream_id, outfile.bytes_delivered, outfile.bytes_sent, outfile.error_message))
        if outfile.registration:
            return
        if outfile.transfer_id:
            self.report_outbox_file(outfile)
        if outfile.result_defer:
            outfile.result_defer.callback(
                (outfile, outfile.status, outfile.error_message))
            outfile.result_defer = None
        if _Debug:
            lg.out(2, '!' * 80)
        s = self.streams[stream_id]
        s.on_close()
        s = None

    def on_close_stream(self, stream_id):
        if _Debug:
            lg.out(18, 'udp_file_queue.on_close_stream %s' % stream_id)
        self.erase_stream(stream_id)

    def on_close_consumer(self, consumer):
        if isinstance(consumer, InboxFile):
            self.close_inbox_file(consumer.stream_id)
        elif isinstance(consumer, OutboxFile):
            self.close_outbox_file(consumer.stream_id)
        else:
            raise Exception('incorrect consumer object')

#------------------------------------------------------------------------------


class InboxFile():

    def __init__(self, queue, stream_id, size):
        """
        """
        self.typ = 'udp-in'
        self.transfer_id = None
        self.registration = None
        self.queue = queue
        self.stream_callback = None
        self.stream_id = stream_id
        self.fd, self.filename = tmpfile.make("udp-in", extension='.udp')
        self.size = size
        self.bytes_received = 0
        self.started = time.time()
        self.cancelled = False
        self.timeout = False
        self.status = None
        self.error_message = ''
        if _Debug:
            lg.out(
                18, 'udp_file_queue.InboxFile.__init__ {%s} [%d] from %s with %d bytes' %
                (os.path.basename(
                    self.filename), self.stream_id, str(
                    self.queue.session.peer_address), self.size))

    def __del__(self):
        """
        
        """
        if _Debug:
            lg.out(18, 'udp_file_queue.InboxFile.__del__ {%s} [%d]' % (
                os.path.basename(self.filename), self.stream_id,))

    def set_stream_callback(self, stream_callback):
        self.stream_callback = stream_callback

    def clear_stream_callback(self):
        self.stream_callback = None

    def close(self):
        if _Debug:
            lg.out(18, 'udp_file_queue.InboxFile.close %d : %d received' % (
                self.stream_id, self.bytes_received))
        self.close_file()
        self.queue = None
        self.stream_callback = None

    def close_file(self):
        os.close(self.fd)
        self.fd = None

    def process(self, newdata):
        os.write(self.fd, newdata)
        self.bytes_received += len(newdata)

    def is_done(self):
        return self.bytes_received == self.size

    def is_timed_out(self):
        return self.timeout

    def on_received_raw_data(self, newdata):
        self.process(newdata)
        return self.is_done()

#------------------------------------------------------------------------------


class OutboxFile():

    def __init__(self, queue, stream_id, filename, size, description='', result_defer=None, keep_alive=True):
        """
        """
        self.typ = 'udp-out'
        self.transfer_id = None
        self.registration = None
        self.queue = queue
        self.stream_callback = None
        self.stream_id = stream_id
        self.filename = filename
        self.size = size
        self.description = description
        self.result_defer = result_defer
        self.keep_alive = keep_alive
        self.bytes_sent = 0
        self.bytes_delivered = 0
        self.buffer = b''
        self.eof = False
        self.cancelled = False
        self.timeout = False
        self.status = None
        self.error_message = ''
        self.started = time.time()
        self.fileobj = open(self.filename, 'rb')
        if _Debug:
            lg.out(18, 'udp_file_queue.OutboxFile.__init__ {%s} [%d] to %s with %d bytes' % (
                os.path.basename(self.filename), self.stream_id, str(self.queue.session.peer_address), self.size))

    def __del__(self):
        """
        """
        if _Debug:
            lg.out(18, 'udp_file_queue.OutboxFile.__del__ {%s} [%d] file:%r' % (
                os.path.basename(self.filename), self.stream_id, self.fileobj))

    def set_stream_callback(self, stream_callback):
        self.stream_callback = stream_callback

    def clear_stream_callback(self):
        self.stream_callback = None

    def close(self):
        if _Debug:
            lg.out(18, 'udp_file_queue.OutboxFile.close %s %d/%d' % (
                self.stream_id, self.bytes_sent, self.bytes_delivered))
        self.close_file()
        self.queue = None
        self.stream_callback = None
        self.buffer = b''
        self.description = None
        self.result_defer = None

    def close_file(self):
        self.fileobj.close()
        self.fileobj = None

    def is_eof(self):
        return self.eof

    def is_done(self):
        return self.eof and self.size == self.bytes_delivered

    def is_cancelled(self):
        return self.cancelled

    def is_timed_out(self):
        return self.timeout

    def count_size(self, more_bytes_delivered):
        self.bytes_delivered += more_bytes_delivered

    def cancel(self):
        if _Debug:
            lg.out(18, 'udp_file_queue.OutboxFile.cancel %s %d/%d' % (
                self.stream_id, self.bytes_sent, self.bytes_delivered))
        self.cancelled = True
        self.status = 'failed'
        self.error_message = 'transfer cancelled'

    def process(self):
        if self.eof:
            return False
        from transport.udp import udp_stream
        has_sends = False
        while True:
            if not self.buffer:
                if not self.fileobj:
                    return False
                data = self.fileobj.read(udp_stream.CHUNK_SIZE)
                if not data:
                    if _Debug:
                        lg.out(18, 'udp_file_queue.OutboxFile.process reach EOF state %d' % self.stream_id)
                    self.eof = True
                    break
                self.buffer = data
            if not self.stream_callback:
                break
            try:
                self.stream_callback(self.buffer)
            except udp_stream.BufferOverflow:
                break
            self.bytes_sent += len(self.buffer)
            self.buffer = b''
            has_sends = True
        return has_sends

    def on_sent_raw_data(self, bytes_delivered):
        self.count_size(bytes_delivered)
        if self.is_done():
            return True
        if self.is_timed_out():
            return True
        if self.is_cancelled():
            return True
        self.process()
        return False
