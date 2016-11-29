#!/usr/bin/env python
# udp_stream.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (udp_stream.py) is part of BitDust Software.
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
.. module:: udp_stream.

.. role:: red

BitDust udp_stream() Automat

.. raw:: html

    <a href="udp_stream.png" target="_blank">
    <img src="udp_stream.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`ack-received`
    * :red:`block-received`
    * :red:`close`
    * :red:`consume`
    * :red:`init`
    * :red:`iterate`
    * :red:`resume`
    * :red:`set-limits`
    * :red:`timeout`
"""

"""
TODO: Need to put small explanation here.

Datagrams format:

    DATA packet:

        bytes:
          0        software version number
          1        command identifier, see ``lib.udp`` module
          2-5      stream_id
          6-9      total data size to be transferred,
                   peer must know when to stop receiving
          10-13    block_id, outgoing blocks are counted from 1
          from 14  payload data


    ACK packet:

        bytes:
          0        software version number
          1        command identifier, see ``lib.udp`` module
          2-5      stream_id
          6-9      block_id1
          10-13    block_id2
          14-17    block_id3
          ...


"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 16

#------------------------------------------------------------------------------

import time
import cStringIO
import struct
import bisect

from twisted.internet import reactor

from logs import lg

from lib import misc

from automats import automat

#------------------------------------------------------------------------------

POOLING_INTERVAL = 0.1  # smaller pooling size will increase CPU load
UDP_DATAGRAM_SIZE = 508  # largest safe datagram size
BLOCK_SIZE = UDP_DATAGRAM_SIZE - 14  # 14 bytes - BitDust header

BLOCKS_PER_ACK = 16  # need to verify delivery get success
# ack packets will be sent as response,
# one output ack per every N data blocks received

OUTPUT_BUFFER_SIZE = 16 * 1024  # how many bytes to read from file at once
CHUNK_SIZE = BLOCK_SIZE * BLOCKS_PER_ACK  # so we know how much to read now
# BLOCK_SIZE * int(float(BLOCKS_PER_ACK)*0.8) - 20% extra space in ack packet

RTT_MIN_LIMIT = 0.004  # round trip time, this adjust how fast we try to send
RTT_MAX_LIMIT = 5.0    # set ack response timeout for sending

MAX_BLOCKS_INTERVAL = 3  # resending blocks at lease every N seconds
MAX_ACK_TIMEOUTS = 5  # if we get too much errors - connection will be closed
MAX_ACKS_INTERVAL = 5  # limit max delay between iterations in seconds.
RECEIVING_TIMEOUT = 10  # decide about the moment to kill the stream
MAX_RTT_COUNTER = 100  # used to calculate avarage RTT for this stream

#------------------------------------------------------------------------------

_Streams = {}
_ProcessStreamsTask = None

_GlobalLimitReceiveBytesPerSec = 1000.0 * 125000  # default receiveing limit bps
_GlobalLimitSendBytesPerSec = 1000.0 * 125000  # default sending limit bps

#------------------------------------------------------------------------------


def streams():
    global _Streams
    return _Streams


def create(stream_id, consumer, producer):
    """
    Creates a new UDP stream.
    """
    if _Debug:
        lg.out(_DebugLevel - 6, 'udp_stream.create stream_id=%s' % str(stream_id))
    s = UDPStream(stream_id, consumer, producer)
    streams()[s.stream_id] = s
    s.automat('init')
    reactor.callLater(0, balance_streams_limits)
    return s


def close(stream_id):
    """
    Close existing UDP stream.
    """
    s = streams().get(stream_id, None)
    if s is None:
        lg.warn('stream %d not exist')
        return False
    s.automat('close')
    if _Debug:
        lg.out(
            _DebugLevel -
            6,
            'udp_stream.close send "close" to stream %s' %
            str(stream_id))
    return True

#------------------------------------------------------------------------------


def get_global_input_limit_bytes_per_sec():
    global _GlobalLimitReceiveBytesPerSec
    return _GlobalLimitReceiveBytesPerSec


def set_global_input_limit_bytes_per_sec(bps):
    global _GlobalLimitReceiveBytesPerSec
    _GlobalLimitReceiveBytesPerSec = bps
    balance_streams_limits()


def get_global_output_limit_bytes_per_sec():
    global _GlobalLimitSendBytesPerSec
    return _GlobalLimitSendBytesPerSec


def set_global_output_limit_bytes_per_sec(bps):
    global _GlobalLimitSendBytesPerSec
    _GlobalLimitSendBytesPerSec = bps
    balance_streams_limits()


def balance_streams_limits():
    receive_limit_per_stream = get_global_input_limit_bytes_per_sec()
    send_limit_per_stream = get_global_output_limit_bytes_per_sec()
    num_streams = len(streams())
    if num_streams > 0:
        receive_limit_per_stream /= num_streams
        send_limit_per_stream /= num_streams
    if _Debug:
        lg.out(_DebugLevel, 'udp_stream.balance_streams_limits in:%r out:%r total:%d' % (
            receive_limit_per_stream, send_limit_per_stream, num_streams))
    for s in streams().values():
        s.automat('set-limits', (receive_limit_per_stream, send_limit_per_stream))

#------------------------------------------------------------------------------

class BufferOverflow(Exception):
    pass

#------------------------------------------------------------------------------

def process_streams():
    global _ProcessStreamsTask
    for s in streams().values():
        if s.state == 'SENDING' or s.state == 'RECEIVING':
            s.event('iterate')
    if _ProcessStreamsTask is None or _ProcessStreamsTask.called:
        _ProcessStreamsTask = reactor.callLater(
            POOLING_INTERVAL, process_streams)


def stop_process_streams():
    global _ProcessSessionsTask
    if _ProcessSessionsTask:
        if _ProcessSessionsTask.active():
            _ProcessSessionsTask.cancel()
        _ProcessSessionsTask = None

#------------------------------------------------------------------------------

class UDPStream(automat.Automat):
    """
    This class implements all the functionality of the ``udp_stream()`` state
    machine.
    """

    fast = True

    post = True

    def __init__(self, stream_id, consumer, producer):
        self.stream_id = stream_id
        self.consumer = consumer
        self.producer = producer
        self.started = time.time()
        self.consumer.set_stream_callback(self.on_consume)
        if _Debug:
            lg.out(_DebugLevel, 'udp_stream.__init__ %d peer_id:%s session:%s' % (
                self.stream_id, self.producer.session.peer_id, self.producer.session))
        name = 'udp_stream[%s]' % (self.stream_id)
        automat.Automat.__init__(self, name, 'AT_STARTUP',
                                 _DebugLevel, _Debug and lg.is_debug(_DebugLevel + 8))

    def __del__(self):
        if _Debug:
            lg.out(_DebugLevel, 'udp_stream.__del__ %d' % self.stream_id)
        automat.Automat.__del__(self)

    def init(self):
        self.output_acks_counter = 0
        self.output_ack_last_time = 0
        self.output_block_id_current = 0
        self.output_block_last_time = 0
        self.output_blocks = {}
        self.output_blocks_ids = []
        self.output_blocks_counter = 0
        self.output_blocks_acked = 0
        self.output_blocks_retries = 0
        self.output_blocks_timed_out = 0
        self.output_blocks_success_counter = 0.0
        self.output_blocks_errors_counter = 0.0
        self.output_blocks_quality_counter = 0.0
        self.output_bytes_in_acks = 0
        self.output_bytes_sent = 0
        self.output_bytes_acked = 0
        self.output_bytes_per_sec_current = 0
        self.output_buffer_size = 0
        self.output_limit_bytes_per_sec = 0
        self.output_limit_factor = 0.5
        self.output_limit_bytes_per_sec_from_remote = -1
        self.output_rtt_avarage = 0.0
        self.output_rtt_counter = 1.0
        self.input_ack_last_time = 0
        self.input_acks_counter = 0
        self.input_acks_timeouts_counter = 0
        self.input_acks_garbage_counter = 0
        self.input_blocks = {}
        self.input_block_id_current = 0
        self.input_block_last_time = 0
        self.input_block_id_last = 0
        self.input_blocks_counter = 0
        self.input_blocks_to_ack = []
        self.input_bytes_received = 0
        self.input_bytes_per_sec_current = 0
        self.input_duplicated_blocks = 0
        self.input_duplicated_bytes = 0
        self.input_old_blocks = 0
        self.input_limit_bytes_per_sec = 0
        self.last_progress_report = 0
        self.eof = False

    def A(self, event, arg):
        newstate = self.state
        #---SENDING---
        if self.state == 'SENDING':
            if event == 'iterate':
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
            elif event == 'consume':
                self.doPushBlocks(arg)
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
            elif event == 'set-limits':
                self.doUpdateLimits(arg)
            elif event == 'ack-received' and not self.isEOF(arg) and not self.isPaused(arg):
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
            elif event == 'ack-received' and self.isEOF(arg):
                self.doReportSendDone(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'ack-received' and self.isPaused(arg):
                self.doResumeLater(arg)
                newstate = 'PAUSE'
            elif event == 'timeout':
                self.doReportSendTimeout(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'close':
                self.doReportClosed(arg)
                self.doCloseStream(arg)
                self.doDestroyMe(arg)
                newstate = 'CLOSED'
        #---DOWNTIME---
        elif self.state == 'DOWNTIME':
            if event == 'set-limits':
                self.doUpdateLimits(arg)
            elif event == 'block-received':
                self.doResendAck(arg)
                self.doReceivingLoop(arg)
                newstate = 'RECEIVING'
            elif event == 'close':
                self.doReportClosed(arg)
                self.doCloseStream(arg)
                self.doDestroyMe(arg)
                newstate = 'CLOSED'
            elif event == 'ack-received':
                self.doReportError(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'consume':
                self.doPushBlocks(arg)
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
                newstate = 'SENDING'
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.doInit(arg)
                newstate = 'DOWNTIME'
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---RECEIVING---
        elif self.state == 'RECEIVING':
            if event == 'set-limits':
                self.doUpdateLimits(arg)
            elif event == 'iterate':
                self.doResendAck(arg)
                self.doReceivingLoop(arg)
            elif event == 'block-received' and not self.isEOF(arg):
                self.doResendAck(arg)
                self.doReceivingLoop(arg)
            elif event == 'timeout':
                self.doReportReceiveTimeout(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'close':
                self.doReportClosed(arg)
                self.doCloseStream(arg)
                self.doDestroyMe(arg)
                newstate = 'CLOSED'
            elif event == 'block-received' and self.isEOF(arg):
                self.doResendAck(arg)
                self.doReportReceiveDone(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
        #---COMPLETION---
        elif self.state == 'COMPLETION':
            if event == 'close':
                self.doDestroyMe(arg)
                newstate = 'CLOSED'
        #---PAUSE---
        elif self.state == 'PAUSE':
            if event == 'consume':
                self.doPushBlocks(arg)
            elif event == 'timeout':
                self.doReportSendTimeout(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'ack-received' and self.isEOF(arg):
                self.doReportSendDone(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'resume':
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
                newstate = 'SENDING'
            elif event == 'close':
                self.doReportClosed(arg)
                self.doCloseStream(arg)
                self.doDestroyMe(arg)
                newstate = 'CLOSED'
        return newstate

    def isEOF(self, arg):
        """
        Condition method.
        """
        return self.eof

    def isPaused(self, arg):
        """
        Condition method.
        """
        _, pause, _ = arg
        return pause > 0

    def doInit(self, arg):
        """
        Action method.
        """
        self.creation_time = time.time()
        self.output_limit_bytes_per_sec = get_global_output_limit_bytes_per_sec() / \
            len(streams())
        self.input_limit_bytes_per_sec = get_global_input_limit_bytes_per_sec() / \
            len(streams())
        if self.producer.session.min_rtt is not None:
            self.output_rtt_avarage = self.producer.session.min_rtt
        else:
            self.output_rtt_avarage = (RTT_MIN_LIMIT + RTT_MAX_LIMIT) / 2.0
        if _Debug:
            lg.out(self.debug_level, 'udp_stream.doInit %d with %s limits: (in=%r|out=%r)  rtt=%r' % (
                self.stream_id,
                self.producer.session.peer_id,
                self.input_limit_bytes_per_sec,
                self.output_limit_bytes_per_sec,
                self.output_rtt_avarage))

    def doPushBlocks(self, arg):
        """
        Action method.
        """
        data = arg
        outp = cStringIO.StringIO(data)
        while True:
            piece = outp.read(BLOCK_SIZE)
            if not piece:
                break
            self.output_block_id_current += 1
            bisect.insort(self.output_blocks_ids, self.output_block_id_current)
            # data, time_sent, acks_missed
            self.output_blocks[self.output_block_id_current] = [piece, -1, 0]
            self.output_buffer_size += len(piece)
        outp.close()
        if _Debug:
            lg.out(self.debug_level + 6, 'PUSH %r' % self.output_blocks_ids)

    def doResendBlocks(self, arg):
        """
        Action method.
        """
        self._resend_blocks()

    def doResendAck(self, arg):
        """
        Action method.
        """
        self._resend_ack()

    def doSendingLoop(self, arg):
        """
        Action method.
        """
        self._sending_loop()

    def doReceivingLoop(self, arg):
        """
        Action method.
        """
        self._receiving_loop()

    def doResumeLater(self, arg):
        """
        Action method.
        """
        _, pause, remote_side_limit_receiving = arg
        if pause > 0:
            reactor.callLater(pause, self.automat, 'resume')
        if remote_side_limit_receiving > 0:
            self.output_limit_bytes_per_sec_from_remote = remote_side_limit_receiving

    def doReportSendDone(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(
                self.debug_level, 'udp_stream.doReportSendDone %r %r' %
                (self.consumer, self.consumer.is_done()))
        if self.consumer.is_done():
            self.consumer.status = 'finished'
        else:
            self.consumer.status = 'failed'
            self.consumer.error_message = 'sending was not finished correctly'
        self.producer.on_outbox_file_done(self.stream_id)

    def doReportSendTimeout(self, arg):
        """
        Action method.
        """
        if self.input_ack_last_time == 0:
            self.consumer.error_message = 'sending failed'
        else:
            self.consumer.error_message = 'remote side stopped responding'
        self.consumer.status = 'failed'
        self.consumer.timeout = True
        self.producer.on_timeout_sending(self.stream_id)

    def doReportReceiveDone(self, arg):
        """
        Action method.
        """
        self.consumer.status = 'finished'
        self.producer.on_inbox_file_done(self.stream_id)

    def doReportReceiveTimeout(self, arg):
        """
        Action method.
        """
        self.consumer.error_message = 'receiving timeout'
        self.consumer.status = 'failed'
        self.consumer.timeout = True
        self.producer.on_timeout_receiving(self.stream_id)

    def doReportClosed(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(self.debug_level, 'CLOSED %s' % self.stream_id)

    def doReportError(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(2, 'udp_stream.doReportError')

    def doCloseStream(self, arg):
        """
        Action method.
        """
        if _Debug:
            pir_id = self.producer.session.peer_id
            dt = time.time() - self.creation_time
            if dt == 0:
                dt = 1.0
            ratein = self.input_bytes_received / dt
            rateout = self.output_bytes_sent / dt
            extra_acks_perc = 100.0 * self.input_acks_garbage_counter / \
                float(self.output_blocks_acked + 1)
            extra_blocks_perc = 100.0 * self.output_blocks_retries / \
                float(self.output_block_id_current + 1)
            lg.out(
                self.debug_level, 'udp_stream.doCloseStream %d %s' %
                (self.stream_id, pir_id))
            lg.out(self.debug_level, '    in:%d|%d acks:%d|%d dups:%d|%d out:%d|%d|%d|%d rate:%r|%r extra:A%s|B%s' % (
                self.input_blocks_counter,
                self.input_bytes_received,
                self.output_acks_counter,
                self.output_bytes_in_acks,
                self.input_duplicated_blocks,
                self.input_duplicated_bytes,
                self.output_blocks_counter,
                self.output_bytes_acked,
                self.output_blocks_retries,
                self.input_acks_garbage_counter,
                int(ratein), int(rateout),
                misc.percent2string(extra_acks_perc),
                misc.percent2string(extra_blocks_perc)))
            del pir_id
        self.input_blocks.clear()
        self.input_blocks_to_ack = []
        self.output_blocks.clear()
        self.output_blocks_ids = []

    def doUpdateLimits(self, arg):
        """
        Action method.
        """
        new_limit_receive, new_limit_send = arg
        self.input_limit_bytes_per_sec = new_limit_receive
        self.output_limit_bytes_per_sec = new_limit_send

    def doDestroyMe(self, arg):
        """
        Action method.
        Remove all references to the state machine object to destroy it.
        """
        self.consumer.clear_stream_callback()
        self.producer.on_close_consumer(self.consumer)
        self.consumer = None
        self.producer.on_close_stream(self.stream_id)
        self.producer = None
        streams().pop(self.stream_id)
        self.destroy()
        reactor.callLater(0, balance_streams_limits)

    def on_block_received(self, inpt):
        if self.consumer and getattr(self.consumer, 'on_received_raw_data', None):
            #--- RECEIVE DATA HERE!
            block_id = inpt.read(4)
            try:
                block_id = struct.unpack('i', block_id)[0]
            except:
                lg.exc()
                if _Debug:
                    lg.out(self.debug_level, 'ERROR receiving, stream_id=%s' % self.stream_id)
                return
            #--- read block data
            data = inpt.read()
            self.input_block_last_time = time.time() - self.creation_time
            self.input_blocks_counter += 1
            if block_id != -1:
            #--- not empty block
                self.input_bytes_received += len(data)
                self.input_block_id_last = block_id
                eof = False
                raw_size = 0
                if block_id in self.input_blocks.keys():
            #--- duplicated block
                    self.input_duplicated_blocks += 1
                    self.input_duplicated_bytes += len(data)
                    bisect.insort(self.input_blocks_to_ack, block_id)
                else:
                    if block_id < self.input_block_id_current:
                        self.input_old_blocks += 1
                        self.input_duplicated_bytes += len(data)
                        bisect.insort(self.input_blocks_to_ack, block_id)
                    else:
                        self.input_blocks[block_id] = data
                        bisect.insort(self.input_blocks_to_ack, block_id)
                if block_id == self.input_block_id_current + 1:
                    newdata = cStringIO.StringIO()
                    while True:
                        next_block_id = self.input_block_id_current + 1
                        try:
                            blockdata = self.input_blocks.pop(next_block_id)
                        except KeyError:
                            break
                        newdata.write(blockdata)
                        raw_size += len(blockdata)
                        self.input_block_id_current = next_block_id
                    try:
                        eof = self.consumer.on_received_raw_data(newdata.getvalue())
                    except:
                        lg.exc()
                    newdata.close()
                if self.eof != eof:
                    self.eof = eof
                    if _Debug:
                        lg.out(self.debug_level, '    EOF : %d' % self.stream_id)
                if _Debug:
                    lg.out(self.debug_level + 6, 'in-> BLOCK %d %r %d-%d %d %d %d' % (
                        self.stream_id,
                        self.eof,
                        block_id,
                        self.input_block_id_current,
                        self.input_bytes_received,
                        self.input_blocks_counter,
                        len(self.input_blocks_to_ack)))
            else:
                if _Debug:
                    lg.out(self.debug_level, 'in-> BLOCK %d %r EMPTY %d %d' % (
                        self.stream_id, self.eof, self.input_bytes_received, self.input_blocks_counter))
            self.automat('block-received', (block_id, data))

    def on_ack_received(self, inpt):
        if self.consumer and getattr(self.consumer, 'on_sent_raw_data', None):
            try:
                eof_flag = None
                acks = []
                pause_time = 0.0
                remote_side_limit_receiving = -1
                eof = False
                raw_bytes = ''
                self.input_ack_last_time = time.time() - self.creation_time
                raw_bytes = inpt.read(1)
                if len(raw_bytes) > 0:
                    eof_flag = struct.unpack('?', raw_bytes)[0]
                else:
                    eof_flag = True
                if not eof_flag:
                    while True:
                        raw_bytes = inpt.read(4)
                        if len(raw_bytes) == 0:
                            break
                        block_id = struct.unpack('i', raw_bytes)[0]
                        if block_id >= 0:
                            acks.append(block_id)
                        else:
                            raw_bytes = inpt.read(4)
                            if not raw_bytes:
                                lg.warn('wrong ack: not found pause time')
                                break
                            pause_time = struct.unpack('f', raw_bytes)[0]
                            remote_side_limit_receiving = struct.unpack('f', raw_bytes)[0]
                if len(acks) > 0:
                    self.input_acks_counter += 1
                else:
                    if pause_time == 0.0 and eof_flag is not None and eof_flag:
                        sum_not_acked_blocks = sum(map(lambda block: len(block[0]),
                                                       self.output_blocks.values()))
                        self.output_bytes_acked += sum_not_acked_blocks
                        eof = self.consumer.on_sent_raw_data(
                            sum_not_acked_blocks)
                        if _Debug:
                            lg.out(
                                self.debug_level, '    ZERO ACK %d eof:%r acked:%d tail:%d' %
                                (self.stream_id, eof, self.output_bytes_acked, sum_not_acked_blocks))
                for block_id in acks:
                    if block_id not in self.output_blocks_ids or block_id not in self.output_blocks:
                        self.input_acks_garbage_counter += 1
                        if _Debug:
                            lg.out(self.debug_level + 6, '    GARBAGE ACK, block %d not found, stream_id=%d' % (
                                block_id, self.stream_id))
                        continue
                    self.output_blocks_ids.remove(block_id)
                    outblock = self.output_blocks.pop(block_id)
                    block_size = len(outblock[0])
                    self.output_buffer_size -= block_size
                    self.output_bytes_acked += block_size
                    self.output_blocks_acked += 1
                    self.output_blocks_success_counter += 1.0
                    self.output_blocks_quality_counter += 1.0
                    self.output_limit_factor = (self.output_blocks_success_counter + 1.0) / (self.output_blocks_quality_counter + 1.0)
                    relative_time = time.time() - self.creation_time
                    last_ack_rtt = relative_time - outblock[1]
                    self.output_rtt_avarage += last_ack_rtt
                    self.output_rtt_counter += 1.0
            #--- drop avarage RTT
                    if self.output_rtt_counter > MAX_RTT_COUNTER:
                        rtt_avarage_dropped = self.output_rtt_avarage / self.output_rtt_counter
                        self.output_rtt_counter = round(MAX_RTT_COUNTER / 2.0)
                        self.output_rtt_avarage = rtt_avarage_dropped * self.output_rtt_counter
                    eof = self.consumer.on_sent_raw_data(block_size)
                for block_id in self.output_blocks_ids:
                    self.output_blocks[block_id][2] += 1
                if eof_flag is not None:
                    eof = eof and eof_flag
                if self.eof != eof:
                    self.eof = eof
                    if _Debug:
                        lg.out(self.debug_level, '    EOF : %d' % self.stream_id)
                if _Debug:
                    try:
                        sz = self.consumer.size
                    except:
                        sz = -1
                    if pause_time > 0:
                        lg.out(self.debug_level + 6, 'in-> ACK %d PAUSE:%r %s %d %s %d %d' % (
                            self.stream_id, pause_time, acks, len(self.output_blocks),
                            eof, sz, self.output_bytes_acked))
                    else:
                        lg.out(self.debug_level + 6, 'in-> ACK %d %s %d %s %d %d' % (
                            self.stream_id, acks, len(self.output_blocks),
                            eof, sz, self.output_bytes_acked))
                self.automat('ack-received', (acks, pause_time, remote_side_limit_receiving))
            except:
                lg.exc()

    def on_consume(self, data):
        if self.consumer:
            if self.output_buffer_size + len(data) > OUTPUT_BUFFER_SIZE:
                raise BufferOverflow(self.output_buffer_size)
            self.event('consume', data)

    def on_close(self):
        if _Debug:
            lg.out(self.debug_level, 'udp_stream.UDPStream[%d].on_close, send "close" event to the stream' % self.stream_id)
        if self.consumer:
            reactor.callLater(0, self.automat, 'close')

    def _sending_loop(self):
        if lg.is_debug(self.debug_level):
            relative_time = time.time() - self.creation_time
            if relative_time - self.last_progress_report > POOLING_INTERVAL * 20.0:
                if _Debug:
                    lg.out(self.debug_level, 'udp_stream[%d]|%r%%|garb.:%d/%d|err.:%d/%r%%/%r%%|%rbps|b.:%d/%d|pkt:%d/%d|RTT:%r|last:%r' % (
                        self.stream_id,
                        #--- percent sent
                        round(100.0 * (float(self.output_bytes_acked) / self.consumer.size), 2),
                        #--- garbage blocks out/garbacge acks in
                        self.output_blocks_retries, self.input_acks_garbage_counter,
                        #--- errors timeouts/%/%
                        self.output_blocks_timed_out,
                        round(100.0 * (self.output_blocks_success_counter / (self.output_blocks_quality_counter + 1)), 2),
                        round(100.0 * (self.output_blocks_errors_counter / (self.output_blocks_quality_counter + 1)), 2),
                        #--- sending speed
                        int(self.output_bytes_per_sec_current),
                        #--- bytes out/in
                        self.output_bytes_sent, self.output_bytes_acked,
                        #--- blocks out/acks in
                        self.output_blocks_counter, self.input_acks_counter,
                        #--- current avarage RTT
                        round(self.output_rtt_avarage / self.output_rtt_counter, 4),
                        #--- last ACK received
                        round(relative_time - self.input_ack_last_time, 4),
                    ))
                self.last_progress_report = relative_time

    def _receiving_loop(self):
        if lg.is_debug(self.debug_level):
            relative_time = time.time() - self.creation_time
            if relative_time - self.last_progress_report > POOLING_INTERVAL * 20.0:
                if _Debug:
                    lg.out(self.debug_level, 'udp_stream[%d] | %r%% | garb.:%d/%d | %d bps | b.:%d/%d | pkt.:%d/%d | last: %r sec dt' % (
                        self.stream_id,
                        #--- percent received
                        round(100.0 * (float(self.consumer.bytes_received) / self.consumer.size), 2),
                        #--- garbage blocks duplicated/old
                        self.input_duplicated_blocks, self.input_old_blocks,
                        #--- receiving speed
                        int(self.input_bytes_per_sec_current),
                        #--- bytes in/out
                        self.input_bytes_received, self.consumer.bytes_received,
                        #--- blocks in/acks out
                        self.input_blocks_counter, self.output_acks_counter,
                        #--- last BLOCK received
                        round(relative_time - self.input_block_last_time, 4),))
                self.last_progress_report = relative_time

    def _resend_blocks(self):
        relative_time = time.time() - self.creation_time
        if len(self.output_blocks) == 0:
            #--- nothing to send
            return
        current_limit = self._get_output_limit_bytes_per_sec()
        if current_limit > 0:
            if relative_time > 0.5:
                current_rate = self.output_bytes_sent / relative_time
                if current_rate > current_limit:
            #--- skip sending : bandwidth limit reached
                    if _Debug:
                        lg.out(self.debug_level, 'SKIP RESENDING %d, bandwidth limit : %r>%r, factor: %r, remote: %r' % (
                            self.stream_id, current_rate,
                            self.output_limit_bytes_per_sec * self.output_limit_factor,
                            self.output_limit_factor,
                            self.output_limit_bytes_per_sec_from_remote))
                    return
        if self.input_acks_counter > 0:
            #--- got some acks already
            if self.output_blocks_counter / float(self.input_acks_counter) > BLOCKS_PER_ACK * 2:
            #--- too many blocks sent but few acks
                if self.state == 'SENDING' or self.state == 'PAUSE':
            #--- check sending timeout
                    if relative_time - self.input_ack_last_time > RTT_MAX_LIMIT * 2:
            #--- no responding activity at all
                        if _Debug:
                            lg.out(
                                self.debug_level,
                                'TIMEOUT SENDING rtt=%r, last ack at %r, last block was %r, reltime is %r' %
                                (self.output_rtt_avarage /
                                 self.output_rtt_counter,
                                 self.input_ack_last_time,
                                 self.output_block_last_time,
                                 relative_time))
                        reactor.callLater(0, self.automat, 'timeout')
                        return
            #--- skip sending : too few acks
                if _Debug:
                    lg.out(self.debug_level + 6, 'SKIP SENDING %d, too few acks:%d blocks:%d' % (
                        self.stream_id, self.input_acks_counter, self.output_blocks_counter))
                # seems like sending too fast
                return
        if self.output_block_last_time - self.input_ack_last_time > RTT_MAX_LIMIT:
            #--- last ack was timed out
            self.input_acks_timeouts_counter += 1
            if self.input_acks_timeouts_counter >= MAX_ACK_TIMEOUTS:
            #--- timeout sending : too many timed out acks
                if _Debug:
                    lg.out(self.debug_level, 'SENDING BROKEN %d rtt=%r, last ack at %r, last block was %r' % (
                        self.stream_id,
                        self.output_rtt_avarage /
                        self.output_rtt_counter,
                        self.input_ack_last_time,
                        self.output_block_last_time))
                reactor.callLater(0, self.automat, 'timeout')
            else:
                if self.output_blocks_ids:
            #--- resend one "oldest" block
                    latest_block_id = self.output_blocks_ids[0]
                    self.output_blocks_retries += 1
                    if _Debug:
                        lg.out(self.debug_level, 'RESEND ONE %d %d' % (
                            self.stream_id, latest_block_id))
                    self._send_blocks([latest_block_id, ])
                else:
            #--- no activity at all
                    if _Debug:
                        lg.out(self.debug_level, 'SKIP SENDING %d, no blocks to send now' % self.stream_id)
            return
            #--- normal sending, check all pending blocks
        rtt_current = self.output_rtt_avarage / self.output_rtt_counter
        resend_time_limit = BLOCKS_PER_ACK * rtt_current
        blocks_to_send_now = []
        for block_id in self.output_blocks_ids:
            #--- decide to send the block now
            time_sent, _ = self.output_blocks[block_id][1:3]
            timed_out = time_sent >= 0 and (
                relative_time - time_sent > resend_time_limit)
            if time_sent == -1:
                blocks_to_send_now.append(block_id)
            else:
                if timed_out:
            #--- this block was timed out, resending
                    blocks_to_send_now.append(block_id)
                    self.output_blocks_retries += 1
                    self.output_blocks_timed_out += 1
                    self.output_blocks_errors_counter += 1.0
                    self.output_blocks_quality_counter += 1.0
            #--- adjust sending limit factor
                    self.output_limit_factor = (self.output_blocks_success_counter + 1.0) / (self.output_blocks_quality_counter + 1.0)
        if blocks_to_send_now:
            #--- send blocks now
            self._send_blocks(blocks_to_send_now)
        del blocks_to_send_now

    def _send_blocks(self, blocks_to_send):
        relative_time = time.time() - self.creation_time
        new_blocks_counter = 0
        for block_id in blocks_to_send:
            piece = self.output_blocks[block_id][0]
            data_size = len(piece)
            current_limit = self._get_output_limit_bytes_per_sec()
            if current_limit > 0 and relative_time > 0:
            #--- limit sending, current rate is too big
                current_rate = (self.output_bytes_sent + data_size) / relative_time
                if current_rate > current_limit:
                    if _Debug:
                        lg.out(self.debug_level, 'SKIP SENDING %d, bandwidth limit : %r>%r, factor: %r, remote: %r' % (
                            self.stream_id, current_rate,
                            self.output_limit_bytes_per_sec * self.output_limit_factor,
                            self.output_limit_factor,
                            self.output_limit_bytes_per_sec_from_remote))
                    continue
            self.output_blocks[block_id][1] = relative_time
            output = ''.join((struct.pack('i', block_id), piece))
            #--- SEND DATA HERE!
            self.producer.do_send_data(self.stream_id, self.consumer, output)
            self.output_bytes_sent += data_size
            self.output_blocks_counter += 1
            new_blocks_counter += 1
            self.output_block_last_time = relative_time
            if _Debug:
                lg.out(self.debug_level + 6, '<-out BLOCK %d %r %r %d/%d' % (
                    self.stream_id,
                    self.eof,
                    block_id,
                    self.output_bytes_sent,
                    self.output_bytes_acked))
        if relative_time > 0:
            #--- calculate current sending speed
            self.output_bytes_per_sec_current = self.output_bytes_sent / relative_time

    def _resend_ack(self):
        relative_time = time.time() - self.creation_time
        period_avarage = self._block_period_avarage()
        first_block_in_group = (self.input_block_id_last % BLOCKS_PER_ACK) == 1
        pause_time = 0.0
        if relative_time > 0:
            #--- calculate current receiving speed
            self.input_bytes_per_sec_current = self.input_bytes_received / relative_time
        if self.input_limit_bytes_per_sec > 0 and relative_time > 0:
            max_receive_available = self.input_limit_bytes_per_sec * relative_time
            if self.input_bytes_received > max_receive_available:
            #--- limit receiving, calculate pause time
                pause_time = (self.input_bytes_received - max_receive_available) / self.input_limit_bytes_per_sec
                if pause_time < 0:
                    lg.warn('pause is %r, stream_id=%d' % (pause_time, self.stream_id))
                    pause_time = 0.0
        if relative_time - self.input_block_last_time > RECEIVING_TIMEOUT:
        #--- last block came long time ago, timeout receiving
            if _Debug:
                lg.out(self.debug_level, 'TIMEOUT RECEIVING %d rtt=%r, last block in %r, reltime: %r, eof: %r, blocks to ack: %d' % (
                    self.stream_id, self._rtt_current(), self.input_block_last_time,
                    relative_time, self.eof, len(self.input_blocks_to_ack),))
            reactor.callLater(0, self.automat, 'timeout')
            return
        #--- need to send some acks now
        if period_avarage == 0 or self.output_acks_counter == 0:
        #--- nothing was send yet, do send first ack now
            self._send_ack(self.input_blocks_to_ack)
        else:
            if self.input_block_id_current > 0 and self.input_block_id_last < self.input_block_id_current:
        #--- last block received was already processed
                self._send_ack(self.input_blocks_to_ack, pause_time)
            else:
        #--- last ack has been long ago
                # need to send ack now because too many blocks was received at once
                last_ack_timeout = self._last_ack_timed_out()
                if last_ack_timeout or first_block_in_group or self.eof:
        #--- EOF state or first block in group received, send normal ACK
                    self._send_ack(self.input_blocks_to_ack, pause_time)

    def _send_ack(self, acks, pause_time=0.0):
        if len(acks) == 0 and pause_time == 0.0 and not self.eof:
            return
        ack_data = struct.pack('?', self.eof)
        #--- prepare ACKS
        ack_data += ''.join(map(lambda bid: struct.pack('i', bid), acks))
        if pause_time > 0:
        #--- add extra "PAUSE REQUIRED" ACK
            ack_data += struct.pack('i', -1)
            ack_data += struct.pack('f', pause_time)
            ack_data += struct.pack('f', self.input_limit_bytes_per_sec)
        ack_len = len(ack_data)
        self.output_bytes_in_acks += ack_len
        self.output_acks_counter += 1
        self.input_blocks_to_ack = []
        self.output_ack_last_time = time.time()
        if _Debug:
            if pause_time <= 0.0:
                lg.out(self.debug_level + 6, '<-out ACK %d %r %r %d/%d' % (
                    self.stream_id, self.eof, acks,
                    self.input_bytes_received,
                    self.consumer.bytes_received))
            else:
                lg.out(self.debug_level + 6, '<-out ACK %d %r PAUSE:%r %r' % (
                    self.stream_id, self.eof, pause_time, acks))
        self.producer.do_send_ack(self.stream_id, self.consumer, ack_data)
        return ack_len > 0

    def _rtt_current(self):
        rtt_current = self.output_rtt_avarage / self.output_rtt_counter
        return rtt_current

    def _block_period_avarage(self):
        if self.input_blocks_counter == 0:
            return 0
        return (time.time() - self.creation_time) / self.input_blocks_counter

    def _last_ack_timed_out(self):
        return time.time() - self.output_ack_last_time > RTT_MAX_LIMIT

    def _get_output_limit_bytes_per_sec(self):
        own_limit = self.output_limit_bytes_per_sec * self.output_limit_factor
        if self.output_limit_bytes_per_sec_from_remote < 0:
            return own_limit
        return min(own_limit, self.output_limit_bytes_per_sec_from_remote)
