#!/usr/bin/env python
# udp_stream.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
    * :red:`pause`
    * :red:`resume`
    * :red:`set-limits`
    * :red:`timeout`



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

from __future__ import absolute_import
from six.moves import map
from io import StringIO

#------------------------------------------------------------------------------

import time
import struct
import bisect

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 16

#------------------------------------------------------------------------------

POOLING_INTERVAL = 0.1   # smaller pooling size will increase CPU load
UDP_DATAGRAM_SIZE = 508  # largest safe datagram size
BLOCK_SIZE = UDP_DATAGRAM_SIZE - 14  # 14 bytes - BitDust header

BLOCKS_PER_ACK = 8  # need to verify delivery get success
# ack packets will be sent as response,
# one output ack per every N data blocks received
WINDOW_SIZE = 10  # do not send next group of blocks
# until current group will be delivered

OUTPUT_BUFFER_SIZE = 16 * 1024  # how many bytes to read from file at once
CHUNK_SIZE = BLOCK_SIZE * BLOCKS_PER_ACK  # so we know how much to read now

RTT_MIN_LIMIT = 0.004  # round trip time, this adjust how fast we try to send
RTT_MAX_LIMIT = 3.0    # set ack response timeout for sending
MAX_RTT_COUNTER = 100  # used to calculate avarage RTT for this stream

MAX_BLOCKS_INTERVAL = 3  # resending blocks at lease every N seconds
MAX_ACK_TIMEOUTS = 5  # if we get too much errors - connection will be closed

# CHECK_ERRORS_INTERVAL = 20  # will verify sending errors every N iterations
ACCEPTABLE_ERRORS_RATE = 0.02  # 2% errors considered to be acceptable quality
SENDING_LIMIT_FACTOR_ON_START = 1.0  # idea was to decrease sending speed with factor

# decide about the moment to kill the stream
RECEIVING_TIMEOUT = RTT_MAX_LIMIT * (MAX_ACK_TIMEOUTS + 1)
SENDING_TIMEOUT = RTT_MAX_LIMIT * (MAX_ACK_TIMEOUTS + 1)

#------------------------------------------------------------------------------

_Streams = {}
_ProcessStreamsTask = None
_ProcessStreamsIterations = 0

_GlobalLimitReceiveBytesPerSec = 1000.0 * 125000  # default receiveing limit bps
_GlobalLimitSendBytesPerSec = 1000.0 * 125000  # default sending limit bps
_CurrentSendingAvarageRate = 0.0

#------------------------------------------------------------------------------

def streams():
    global _Streams
    return _Streams


def create(stream_id, consumer, producer):
    """
    Creates a new UDP stream.
    """
    if _Debug:
        lg.out(_DebugLevel, 'udp_stream.create stream_id=%s' % str(stream_id))
    s = UDPStream(stream_id, consumer, producer)
    streams()[s.stream_id] = s
    s.automat('init')
    reactor.callLater(0, balance_streams_limits)  # @UndefinedVariable
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
        lg.out(_DebugLevel, 'udp_stream.close send "close" to stream %s' % str(stream_id))
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

#------------------------------------------------------------------------------

def balance_streams_limits():
    global _CurrentSendingAvarageRate
    receive_limit_per_stream = float(get_global_input_limit_bytes_per_sec())
    send_limit_per_stream = float(get_global_output_limit_bytes_per_sec())
    num_streams = len(streams())
    if num_streams > 0:
        receive_limit_per_stream /= float(num_streams)
        send_limit_per_stream /= float(num_streams)
    if _Debug:
        lg.out(_DebugLevel, 'udp_stream.balance_streams_limits in:%r out:%r avarage:%r streams:%d' % (
            receive_limit_per_stream,
            send_limit_per_stream,
            int(_CurrentSendingAvarageRate),
            num_streams))
    for s in streams().values():
        s.automat('set-limits', (receive_limit_per_stream, send_limit_per_stream))

#------------------------------------------------------------------------------

def sort_method(stream_instance):
    if stream_instance.state == 'SENDING':
        return stream_instance.output_bytes_per_sec_current
    return stream_instance.input_bytes_per_sec_current

def process_streams():
    global _ProcessStreamsTask
    global _ProcessStreamsIterations
    global _CurrentSendingAvarageRate

    for s in streams().values():
        if s.state != 'RECEIVING':
            continue
        s.event('iterate')

    sending_streams_count = 0.0
    total_sending_rate = 0.0
    for s in sorted(list(streams().values()), key=lambda s: s.output_blocks_last_delta):
        if s.state != 'SENDING':
            continue
        s.event('iterate')
        if s.get_output_limit_from_remote() > 0:
            continue
        total_sending_rate += s.get_current_output_speed()
        sending_streams_count += 1.0

    if sending_streams_count > 0.0:
        _CurrentSendingAvarageRate = total_sending_rate / sending_streams_count
    else:
        _CurrentSendingAvarageRate = 0.0

    if _ProcessStreamsTask is None or _ProcessStreamsTask.called:
        _ProcessStreamsTask = reactor.callLater(  # @UndefinedVariable
            POOLING_INTERVAL, process_streams)


def stop_process_streams():
    global _ProcessStreamsTask
    if _ProcessStreamsTask:
        if _ProcessStreamsTask.active():
            _ProcessStreamsTask.cancel()
        _ProcessStreamsTask = None

#------------------------------------------------------------------------------

class BufferOverflow(Exception):
    pass

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
                                 _DebugLevel,
                                 _Debug and lg.is_debug(_DebugLevel + 8),
                                 )
        self.log_transitions = _Debug

    def __del__(self):
        if _Debug:
            lg.out(_DebugLevel, 'udp_stream.__del__ %d' % self.stream_id)
        automat.Automat.__del__(self)

    def init(self):
        self.output_acks_counter = 0
        self.output_acks_reasons = {}
        self.output_iterations_results = {}
        self.output_ack_last_time = 0
        self.output_block_id_current = 0
        self.output_acked_block_id_current = 0
        self.output_acked_blocks_ids = set()
        self.output_block_last_time = 0
        self.output_blocks = {}
        self.output_blocks_ids = []
        self.output_blocks_counter = 0
        self.output_blocks_last_delta = 0
        self.output_blocks_reasons = {}
        self.output_blocks_acked = 0
        self.output_blocks_success_counter = 0.0
        self.output_blocks_errors_counter = 0
        self.output_quality_counter = 0.0
        self.output_error_last_time = 0.0
        self.output_bytes_in_acks = 0
        self.output_bytes_sent = 0
        self.output_bytes_sent_period = 0
        self.output_bytes_acked = 0
        self.output_bytes_per_sec_current = 0
        self.output_bytes_per_sec_last = 0
        self.output_buffer_size = 0
        self.output_limit_bytes_per_sec = 0
        self.output_limit_factor = SENDING_LIMIT_FACTOR_ON_START
        self.output_limit_bytes_per_sec_from_remote = 0.0
        self.output_limit_iteration_last_time = 0
        self.output_rtt_avarage = 0.0
        self.output_rtt_counter = 1.0
        self.input_ack_last_time = 0
        self.input_ack_error_last_check = 0
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
        self.input_bytes_received_period = 0
        self.input_bytes_per_sec_current = 0
        self.input_duplicated_blocks = 0
        self.input_duplicated_bytes = 0
        self.input_old_blocks = 0
        self.input_limit_bytes_per_sec = 0
        self.input_limit_iteration_last_time = 0
        self.last_progress_report = 0
        self.eof = False

    def A(self, event, *args, **kwargs):
        newstate = self.state
        #---SENDING---
        if self.state == 'SENDING':
            if event == 'iterate':
                self.doResendBlocks(*args, **kwargs)
                self.doSendingLoop(*args, **kwargs)
            elif event == 'consume':
                self.doPushBlocks(*args, **kwargs)
                self.doResendBlocks(*args, **kwargs)
            elif event == 'set-limits':
                self.doUpdateLimits(*args, **kwargs)
            elif event == 'ack-received' and not self.isEOF(*args, **kwargs) and not self.isPaused(*args, **kwargs):
                self.doResendBlocks(*args, **kwargs)
            elif event == 'ack-received' and self.isEOF(*args, **kwargs):
                self.doReportSendDone(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                newstate = 'COMPLETION'
            elif event == 'pause' or ( event == 'ack-received' and self.isPaused(*args, **kwargs) ):
                self.doResumeLater(*args, **kwargs)
                newstate = 'PAUSE'
            elif event == 'timeout':
                self.doReportSendTimeout(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                newstate = 'COMPLETION'
            elif event == 'close':
                self.doReportClosed(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
                newstate = 'CLOSED'
        #---DOWNTIME---
        elif self.state == 'DOWNTIME':
            if event == 'set-limits':
                self.doUpdateLimits(*args, **kwargs)
            elif event == 'consume':
                self.doPushBlocks(*args, **kwargs)
                self.doResendBlocks(*args, **kwargs)
                newstate = 'SENDING'
            elif event == 'block-received':
                self.doResendAck(*args, **kwargs)
                newstate = 'RECEIVING'
            elif event == 'ack-received':
                self.doReportError(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                newstate = 'COMPLETION'
            elif event == 'close':
                self.doReportClosed(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
                newstate = 'CLOSED'
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.doInit(*args, **kwargs)
                newstate = 'DOWNTIME'
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---RECEIVING---
        elif self.state == 'RECEIVING':
            if event == 'set-limits':
                self.doUpdateLimits(*args, **kwargs)
            elif event == 'iterate':
                self.doResendAck(*args, **kwargs)
                self.doReceivingLoop(*args, **kwargs)
            elif event == 'block-received' and not self.isEOF(*args, **kwargs):
                self.doResendAck(*args, **kwargs)
            elif event == 'timeout':
                self.doReportReceiveTimeout(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                newstate = 'COMPLETION'
            elif event == 'close':
                self.doReportClosed(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
                newstate = 'CLOSED'
            elif event == 'block-received' and self.isEOF(*args, **kwargs):
                self.doResendAck(*args, **kwargs)
                self.doReportReceiveDone(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                newstate = 'COMPLETION'
        #---COMPLETION---
        elif self.state == 'COMPLETION':
            if event == 'close':
                self.doDestroyMe(*args, **kwargs)
                newstate = 'CLOSED'
        #---PAUSE---
        elif self.state == 'PAUSE':
            if event == 'consume':
                self.doPushBlocks(*args, **kwargs)
            elif event == 'timeout':
                self.doReportSendTimeout(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                newstate = 'COMPLETION'
            elif event == 'ack-received' and self.isEOF(*args, **kwargs):
                self.doReportSendDone(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                newstate = 'COMPLETION'
            elif event == 'resume':
                self.doResendBlocks(*args, **kwargs)
                newstate = 'SENDING'
            elif event == 'close':
                self.doReportClosed(*args, **kwargs)
                self.doCloseStream(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
                newstate = 'CLOSED'
        return newstate

    def isEOF(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.eof

    def isPaused(self, *args, **kwargs):
        """
        Condition method.
        """
        _, pause, _ = args[0]
        return pause > 0

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.creation_time = time.time()
        self.period_time = time.time()
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

    def doPushBlocks(self, *args, **kwargs):
        """
        Action method.
        """
        self._push_blocks(args[0])

    def doResendBlocks(self, *args, **kwargs):
        """
        Action method.
        """
        current_blocks = self.output_blocks_counter
        self._resend_blocks()
        self.output_blocks_last_delta = self.output_blocks_counter - current_blocks

    def doResendAck(self, *args, **kwargs):
        """
        Action method.
        """
        self._resend_ack()

    def doSendingLoop(self, *args, **kwargs):
        """
        Action method.
        """
        self._sending_loop()

    def doReceivingLoop(self, *args, **kwargs):
        """
        Action method.
        """
        self._receiving_loop()

    def doResumeLater(self, *args, **kwargs):
        """
        Action method.
        """
        if isinstance(args[0], float):
            reactor.callLater(args[0], self.automat, 'resume')  # @UndefinedVariable
            return
        _, pause, remote_side_limit_receiving = args[0]
        if pause > 0:
            reactor.callLater(pause, self.automat, 'resume')  # @UndefinedVariable
        if remote_side_limit_receiving > 0:
            self.output_limit_bytes_per_sec_from_remote = remote_side_limit_receiving
        else:
            self.output_limit_bytes_per_sec_from_remote = 0.0

    def doReportSendDone(self, *args, **kwargs):
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

    def doReportSendTimeout(self, *args, **kwargs):
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

    def doReportReceiveDone(self, *args, **kwargs):
        """
        Action method.
        """
        self.consumer.status = 'finished'
        self.producer.on_inbox_file_done(self.stream_id)

    def doReportReceiveTimeout(self, *args, **kwargs):
        """
        Action method.
        """
        self.consumer.error_message = 'receiving timeout'
        self.consumer.status = 'failed'
        self.consumer.timeout = True
        self.producer.on_timeout_receiving(self.stream_id)

    def doReportClosed(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(self.debug_level, 'CLOSED %s' % self.stream_id)

    def doReportError(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(2, 'udp_stream.doReportError')

    def doCloseStream(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            self.last_progress_report = 0
            self._sending_loop()
            self._receiving_loop()
            pir_id = self.producer.session.peer_id
            dt = time.time() - self.creation_time
            if dt == 0:
                dt = 1.0
            ratein = self.input_bytes_received / dt
            rateout = self.output_bytes_sent / dt
            lg.out(
                self.debug_level, 'udp_stream.doCloseStream %d %s' %
                (self.stream_id, pir_id))
            lg.out(self.debug_level, '    in:%d|%d|%r acks:%d|%d dups:%d|%d out:%d|%d|%d|%d rate:%r|%r' % (
                self.input_blocks_counter,
                self.input_bytes_received,
                self._block_period_avarage(),
                self.output_acks_counter,
                self.output_bytes_in_acks,
                self.input_duplicated_blocks,
                self.input_duplicated_bytes,
                self.output_blocks_counter,
                self.output_bytes_acked,
                self.output_blocks_errors_counter,
                self.input_acks_garbage_counter,
                int(ratein), int(rateout),
            ))
            lg.out(self.debug_level, '    ACK REASONS: %r' % self.output_acks_reasons)
            del pir_id
        self.input_blocks.clear()
        self.input_blocks_to_ack = []
        self.output_blocks.clear()
        self.output_blocks_ids = []

    def doUpdateLimits(self, *args, **kwargs):
        """
        Action method.
        """
        new_limit_receive, new_limit_send = args[0]
        self.input_limit_bytes_per_sec = new_limit_receive
        self.output_limit_bytes_per_sec = new_limit_send
        self.output_limit_factor = SENDING_LIMIT_FACTOR_ON_START
        if _Debug:
            lg.out(self.debug_level + 6, 'udp_stream[%d].doUpdateLimits in=%r out=%r (remote=%r)' % (
                self.stream_id,
                self.input_limit_bytes_per_sec, self.output_limit_bytes_per_sec,
                self.output_limit_bytes_per_sec_from_remote))

    def doDestroyMe(self, *args, **kwargs):
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
        reactor.callLater(0, balance_streams_limits)  # @UndefinedVariable

    def on_block_received(self, inpt):
        if not (self.consumer and getattr(self.consumer, 'on_received_raw_data', None)):
            return
            #--- RECEIVE DATA HERE!
        block_id = inpt.read(4)
        try:
            block_id = int(struct.unpack('i', block_id)[0])
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
            #--- not empty block received
            self.input_bytes_received += len(data)
            self.input_block_id_last = block_id
            eof = False
            raw_size = 0
            if block_id in list(self.input_blocks.keys()):
            #--- duplicated block received
                self.input_duplicated_blocks += 1
                self.input_duplicated_bytes += len(data)
                bisect.insort(self.input_blocks_to_ack, block_id)
            else:
                if block_id < self.input_block_id_current:
            #--- old block (already processed) received
                    self.input_old_blocks += 1
                    self.input_duplicated_bytes += len(data)
                    bisect.insort(self.input_blocks_to_ack, block_id)
                else:
            #--- GOOD BLOCK RECEIVED
                    self.input_blocks[block_id] = data
                    bisect.insort(self.input_blocks_to_ack, block_id)
            if block_id == self.input_block_id_current + 1:
            #--- receiving data and check every next block one by one
                newdata = StringIO()
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
            #--- consume data and get EOF state
                    eof = self.consumer.on_received_raw_data(newdata.getvalue())
                except:
                    lg.exc()
                newdata.close()
            #--- remember EOF state
            if eof and not self.eof:
                self.eof = eof
                if _Debug:
                    lg.out(self.debug_level, '    EOF flag set !!!!!!!! : %d' % self.stream_id)
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
            #--- raise 'block-received' event
        self.event('block-received', (block_id, data))

    def on_ack_received(self, inpt):
        if not (self.consumer and getattr(self.consumer, 'on_sent_raw_data', None)):
            return
            #--- read ACK
        eof = False
        eof_flag = None
        acks = []
        pause_time = 0.0
        remote_side_limit_receiving = -1
        self.input_ack_last_time = time.time() - self.creation_time
        raw_bytes = inpt.read(1)
        if len(raw_bytes) > 0:
            #--- read EOF state from ACK
            eof_flag = bool(struct.unpack('?', raw_bytes)[0])
        if True:
            while True:
                raw_bytes = inpt.read(4)
                if len(raw_bytes) == 0:
                    break
            #--- read block id from ACK
                block_id = int(struct.unpack('i', raw_bytes)[0])
                if block_id >= 0:
                    acks.append(block_id)
                elif block_id == -1:
            #--- read PAUSE TIME from ACK
                    raw_bytes = inpt.read(4)
                    if not raw_bytes:
                        lg.warn('wrong ack: not found pause time')
                        break
                    pause_time = float(struct.unpack('f', raw_bytes)[0])
            #--- read remote bandwith limit from ACK
                    raw_bytes = inpt.read(4)
                    if not raw_bytes:
                        lg.warn('wrong ack: not found remote bandwith limit')
                        break
                    remote_side_limit_receiving = float(struct.unpack('f', raw_bytes)[0])
                else:
                    lg.warn('incorrect block_id received: %r' % block_id)
        if len(acks) > 0:
            #--- some blocks was received fine
            self.input_acks_counter += 1
        if pause_time == 0.0 and eof_flag:
            #--- EOF state found in the ACK
            if _Debug:
                sum_not_acked_blocks = sum([len(block[0]) for block in list(self.output_blocks.values())])
                try:
                    sz = self.consumer.size
                except:
                    sz = -1
                lg.out(self.debug_level, '    EOF state found in ACK %d acked:%d not acked:%d total:%d' % (
                    self.stream_id, self.output_bytes_acked, sum_not_acked_blocks, sz))
        for block_id in acks:
            #--- mark this block as acked
            if block_id >= self.output_acked_block_id_current:
                if block_id not in self.output_acked_blocks_ids:
                    # bisect.insort(self.output_acked_blocks_ids, block_id)
                    self.output_acked_blocks_ids.add(block_id)
            if block_id not in self.output_blocks_ids or block_id not in self.output_blocks:
            #--- garbage, block was already acked
                self.input_acks_garbage_counter += 1
                if _Debug:
                    lg.out(self.debug_level + 6, '    GARBAGE ACK, block %d not found, stream_id=%d' % (
                        block_id, self.stream_id))
                continue
            #--- mark block as acked
            self.output_blocks_ids.remove(block_id)
            outblock = self.output_blocks.pop(block_id)
            block_size = len(outblock[0])
            self.output_bytes_acked += block_size
            self.output_buffer_size -= block_size
            self.output_blocks_success_counter += 1.0
            self.output_quality_counter += 1.0
            relative_time = time.time() - self.creation_time
            last_ack_rtt = relative_time - outblock[1]
            self.output_rtt_avarage += last_ack_rtt
            self.output_rtt_counter += 1.0
            #--- drop avarage RTT
            if self.output_rtt_counter > MAX_RTT_COUNTER:
                rtt_avarage_dropped = self.output_rtt_avarage / self.output_rtt_counter
                self.output_rtt_counter = round(MAX_RTT_COUNTER / 2.0, 0)
                self.output_rtt_avarage = rtt_avarage_dropped * self.output_rtt_counter
            #--- process delivered data
            eof = self.consumer.on_sent_raw_data(block_size)
        for block_id in self.output_blocks_ids:
            #--- mark blocks was not acked at this time
            self.output_blocks[block_id][2] += 1
        while True:
            next_block_id = self.output_acked_block_id_current + 1
            try:
                self.output_acked_blocks_ids.remove(next_block_id)
            except KeyError:
                break
            self.output_acked_block_id_current = next_block_id
            self.output_blocks_acked += 1
        eof = eof or eof_flag
        if not self.eof and eof:
            #--- remember EOF state
            self.eof = eof
            if _Debug:
                lg.out(self.debug_level, '    in-> ACK %d : EOF RICHED !!!!!!!!' % self.stream_id)
        if eof_flag is None and len(acks) == 0 and pause_time == 0.0:
            #--- stream was closed on remote side, probably EOF
            self.eof = True
            if _Debug:
                lg.out(self.debug_level, '    in-> ACK %d : REMOTE SIDE CLOSED STREAM !!!!!!!!' % self.stream_id)
        if _Debug:
            try:
                sz = self.consumer.size
            except:
                sz = -1
            if pause_time > 0:
                lg.out(self.debug_level + 6, 'in-> ACK %d PAUSE:%r %s %d %s %d %d %r' % (
                    self.stream_id, pause_time, acks, len(self.output_blocks),
                    eof, sz, self.output_bytes_acked, acks))
                lg.out(self.debug_level + 6, '    %r' % self.output_acked_blocks_ids)
            else:
                lg.out(self.debug_level + 6, 'in-> ACK %d %d %d %s %d %d %r' % (
                    self.stream_id, self.output_acked_block_id_current,
                    len(self.output_blocks), eof, self.output_bytes_acked, sz, acks))
        self.event('ack-received', (acks, pause_time, remote_side_limit_receiving))

    def on_consume(self, data):
        if self.consumer:
            if self.output_buffer_size + len(data) > OUTPUT_BUFFER_SIZE:
                raise BufferOverflow(self.output_buffer_size)
            if self.output_quality_counter > BLOCKS_PER_ACK * WINDOW_SIZE:
                error_rate = float(self.output_blocks_errors_counter) / (self.output_quality_counter)
                if error_rate > ACCEPTABLE_ERRORS_RATE:
                    current_window = self.output_block_id_current - self.output_acked_block_id_current
                    if current_window > BLOCKS_PER_ACK * WINDOW_SIZE:
                        raise BufferOverflow(self.output_buffer_size)
            self.event('consume', data)

    def on_close(self):
        if _Debug:
            lg.out(self.debug_level, 'udp_stream.UDPStream[%d].on_close, send "close" event to the stream, state=%s' % (self.stream_id, self.state))
            lg.out(self.debug_level, '    %r' % self.output_iterations_results)
        if self.consumer:
            reactor.callLater(0, self.automat, 'close')  # @UndefinedVariable

    def _push_blocks(self, data):
        outp = StringIO(data)
        while True:
            piece = outp.read(BLOCK_SIZE)
            if not piece:
                break
            self.output_block_id_current += 1
            #--- prepare block to be send
            bisect.insort(self.output_blocks_ids, self.output_block_id_current)
            # data, time_sent, acks missed, number of attempts
            self.output_blocks[self.output_block_id_current] = [piece, -1, 0, 0]
            self.output_buffer_size += len(piece)
        outp.close()
        if _Debug:
            lg.out(self.debug_level + 6, 'PUSH %d [%s]' % (
                self.output_block_id_current, ','.join(map(str, self.output_blocks_ids)), ))

    def _sending_loop(self):
        total_rate_out = 0.0
        relative_time = time.time() - self.creation_time
        if relative_time > 0:
            total_rate_out = self.output_bytes_sent / float(relative_time)
        if lg.is_debug(self.debug_level):
            if self.output_quality_counter and relative_time - self.last_progress_report > POOLING_INTERVAL * 50.0:
                if _Debug:
                    lg.out(self.debug_level, 'udp_stream[%d]|%d/%r%%|garb.:%d/%d|err.:%r%%/%r%%|%rbps|pkt:%d/%d|RTT:%r|lag:%d|last:%r/%r|buf:%d|N:%d' % (
                        self.stream_id,
                        #--- current block acked/percent sent
                        self.output_acked_block_id_current,
                        round(100.0 * (float(self.output_bytes_acked) / self.consumer.size), 2),
                        #--- garbage blocks out/garbacge acks in
                        self.output_blocks_errors_counter,
                        self.input_acks_garbage_counter,
                        #--- errors timeouts/lagged/success %/error %
                        round(100.0 * (self.output_blocks_errors_counter / self.output_quality_counter), 2),
                        round(100.0 * (self.output_blocks_success_counter / self.output_quality_counter), 2),
                        #--- sending speed current/total
                        int(total_rate_out),
                        #--- blocks out/acks in
                        self.output_blocks_counter,
                        self.input_acks_counter,
                        #--- current avarage RTT
                        round(self.output_rtt_avarage / self.output_rtt_counter, 4),
                        #--- current lag
                        (self.output_block_id_current - self.output_acked_block_id_current),
                        #--- last BLOCK sent/ACK received
                        round(relative_time - self.output_block_last_time, 4),
                        round(relative_time - self.input_ack_last_time, 4),
                        #--- packets in buffer/window size
                        len(self.output_blocks),
                        #--- number of streams
                        len(streams()),
                    ))
                    lg.out(self.debug_level, '    %r' % self.output_iterations_results)
                self.last_progress_report = relative_time

    def _receiving_loop(self):
        if lg.is_debug(self.debug_level):
            relative_time = time.time() - self.creation_time
            if relative_time - self.last_progress_report > POOLING_INTERVAL * 50.0:
                if _Debug:
                    lg.out(self.debug_level, 'udp_stream[%d] | %d/%r%% | garb.:%d/%d/%r%% | %d bps | b.:%d/%d | pkt.:%d/%d | last: %r | buf: %d | N:%d' % (
                        self.stream_id,
                        #--- percent received
                        self.input_block_id_current,
                        round(100.0 * (float(self.consumer.bytes_received) / self.consumer.size), 2),
                        #--- garbage blocks duplicated/old/ratio
                        self.input_duplicated_blocks,  # VARY BAD!!!
                        self.input_old_blocks,  # not so bad
                        round(100.0 * (float(self.input_duplicated_blocks + self.input_old_blocks) / float(self.input_block_id_current + 1)), 2),
                        #--- receiving speed
                        int(self.input_bytes_per_sec_current),
                        #--- bytes in/consumed
                        self.input_bytes_received,
                        self.consumer.bytes_received,
                        #--- blocks in/acks out
                        self.input_blocks_counter,
                        self.output_acks_counter,
                        #--- last BLOCK received
                        round(relative_time - self.input_block_last_time, 4),
                        #--- input buffer
                        len(self.input_blocks),
                        #--- number of streams
                        len(streams()),
                    ))
                self.last_progress_report = relative_time

    def _add_iteration_result(self, result):
        if _Debug and lg.is_debug(self.debug_level):
            if result not in self.output_iterations_results:
                self.output_iterations_results[result] = 1
            else:
                self.output_iterations_results[result] += 1

    def _resend_blocks(self):
        if len(self.output_blocks) == 0:
            #--- nothing to send right now
            return
        relative_time = time.time() - self.creation_time
        last_block_sent_delta = relative_time - self.output_block_last_time
        current_limit = self.calculate_real_output_limit()
        if current_limit > 0 and relative_time > 0:
            possible_bytes_more = BLOCKS_PER_ACK * BLOCK_SIZE
            current_rate = (self.output_bytes_sent + possible_bytes_more) / relative_time
            if current_rate > current_limit and last_block_sent_delta < RTT_MAX_LIMIT / 2.0:
            #--- skip sending : bandwidth limit reached
                self.output_limit_iteration_last_time = relative_time
                if _Debug:
                    lg.out(self.debug_level + 6, 'SKIP RESENDING %d, bandwidth limit : %r>%r, factor: %r, remote: %r' % (
                        self.stream_id,
                        int(current_rate),
                        int(self.output_limit_bytes_per_sec * self.output_limit_factor),
                        self.output_limit_factor,
                        self.output_limit_bytes_per_sec_from_remote))
                self._add_iteration_result('limit')
                return
        if self.state == 'SENDING' or self.state == 'PAUSE':
            sending_was_limited = relative_time - self.output_limit_iteration_last_time < SENDING_TIMEOUT
            input_ack_timed_out = relative_time - self.input_ack_last_time > SENDING_TIMEOUT
            if not sending_was_limited and input_ack_timed_out:
            #--- no responding activity at all - TIMEOUT
                if _Debug:
                    lg.out(self.debug_level, 'TIMEOUT SENDING rtt=%r, last ack:%r, last block sent:%r, reltime:%r, avarage speed: %r' % (
                        round(self.output_rtt_avarage / self.output_rtt_counter, 6),
                        round(self.input_ack_last_time, 4),
                        round(self.output_block_last_time, 4),
                        relative_time,
                        int(_CurrentSendingAvarageRate)))
                    speeds = []
                    for s in streams().values():
                        stream_relative_time = time.time() - s.creation_time
                        if stream_relative_time > 0:
                            speeds.append(int(s.output_bytes_sent / float(relative_time)))
                    lg.out(self.debug_level, '%r' % speeds)
                reactor.callLater(0, self.automat, 'timeout')  # @UndefinedVariable
                return
        if self.input_acks_counter > 0:
            if last_block_sent_delta < RTT_MAX_LIMIT:
                current_out_in_rate = self.output_blocks_counter / float(self.input_acks_counter)
                if current_out_in_rate > float(BLOCKS_PER_ACK) * 1.5:
                #--- too many blocks sent but few acks, skip sending
                    if _Debug:
                        lg.out(self.debug_level + 6, 'SKIP SENDING %d, too few acks:%d blocks:%d' % (
                            self.stream_id, self.input_acks_counter, self.output_blocks_counter))
                    self._add_iteration_result('fewacks')
                    return
            #--- normal sending, check all pending blocks
        rtt_current = self._rtt_current()
        blocks_to_send_now = []
        for block_id in self.output_blocks_ids:
            if len(blocks_to_send_now) >= BLOCKS_PER_ACK:
            #--- do not send too much blocks at once
                break
            time_sent = self.output_blocks[block_id][1]
            if time_sent != -1:
                continue
            #--- send this block first time
            blocks_to_send_now.append(block_id)
        if len(blocks_to_send_now) >= BLOCKS_PER_ACK:
            #--- full group of blocks sending first time, GO!
            self._send_blocks(blocks_to_send_now)
            self._add_iteration_result('fullgroup')
            return
        bytes_left = self.consumer.size - self.output_bytes_acked
        if len(blocks_to_send_now) > 0 and bytes_left < BLOCKS_PER_ACK * BLOCK_SIZE:
            #--- not full group, but almost finished
            self._send_blocks(blocks_to_send_now)
            self._add_iteration_result('finishing')
            return
        if last_block_sent_delta < RTT_MAX_LIMIT:
            if self.input_acks_counter == 0:
            #--- no acks received yet, skip sending
                self._add_iteration_result('noackyet')
                return
            possible_blocks_out = self.output_blocks_counter + len(blocks_to_send_now)
            possible_out_in_ratio = float(possible_blocks_out) / float(self.input_acks_counter)
            if possible_out_in_ratio > float(BLOCKS_PER_ACK) * (1.0 + ACCEPTABLE_ERRORS_RATE):
            #--- sent more blocks, than needed, skip sending
                self._add_iteration_result('needmoreacks')
                return
            #--- last block was sent long ago, need to resend now
        blocks_not_acked = sorted(self.output_blocks_ids)
        block_position = 0
        too_much_errors = False
        for block_id in blocks_not_acked:
            block_position += 1
            if block_id in blocks_to_send_now:
                continue
            if len(blocks_to_send_now) >= BLOCKS_PER_ACK:
                # do not send too much blocks at once
                break
            time_sent = self.output_blocks[block_id][1]
            if time_sent < 0:
                continue
            if relative_time - time_sent < block_position * rtt_current:
                continue
            error_rate = float(self.output_blocks_errors_counter + 1) / (self.output_quality_counter + 1.0)
            if error_rate > ACCEPTABLE_ERRORS_RATE:
                too_much_errors = True
                break
            #--- this block was timed out, resending
            blocks_to_send_now.insert(0, block_id)
            self.output_blocks_errors_counter += 1
            self.output_quality_counter += 1.0
            self.output_error_last_time = relative_time
        if len(blocks_to_send_now) >= BLOCKS_PER_ACK:
            #--- full group of blocks with timeouts
            self._send_blocks(blocks_to_send_now)
            self._add_iteration_result('fullgroup2')
            return
        if len(blocks_to_send_now) > 0 and bytes_left < BLOCKS_PER_ACK * BLOCK_SIZE:
            #--- not full group, but almost finished
            self._send_blocks(blocks_to_send_now)
            self._add_iteration_result('finishing2')
            return
        if too_much_errors and last_block_sent_delta < RTT_MAX_LIMIT / 2.0:
            #--- too much errors, send not full group
            self._send_blocks(blocks_to_send_now)
            self._add_iteration_result('errors')
            return
        blocks_not_acked = sorted(
            self.output_blocks_ids,
            key=lambda bid: self.output_blocks[bid][2],
            reverse=True,
        )
        for block_id in blocks_not_acked:
            if block_id in blocks_to_send_now:
                continue
            if len(blocks_to_send_now) >= BLOCKS_PER_ACK:
                # do not send too much blocks at once
                break
            missed_acks = self.output_blocks[block_id][2]
            if missed_acks < int(WINDOW_SIZE):
                continue
            error_rate = float(self.output_blocks_errors_counter + 1) / float(self.output_quality_counter + 1.0)
            if error_rate > ACCEPTABLE_ERRORS_RATE:
                too_much_errors = True
                break
            blocks_to_send_now.insert(0, block_id)
            self.output_blocks_errors_counter += 1
            self.output_quality_counter += 1.0
            self.output_error_last_time = relative_time
        if len(blocks_to_send_now) >= BLOCKS_PER_ACK:
            #--- full group of blocks with missed acks
            self._send_blocks(blocks_to_send_now)
            self._add_iteration_result('fullgroup3')
            return
            #--- no activity for some time, send some timed out blocks
        if too_much_errors and last_block_sent_delta < RTT_MAX_LIMIT / 2.0:
            #--- too much errors, send not full group
            self._send_blocks(blocks_to_send_now)
            self._add_iteration_result('errors2')
            return
        for block_id in blocks_not_acked:
            if block_id in blocks_to_send_now:
                continue
            if len(blocks_to_send_now) >= BLOCKS_PER_ACK:
                # do not send too much blocks at once
                break
            time_sent = self.output_blocks[block_id][1]
            if time_sent < 0:
                continue
            if relative_time - time_sent < RTT_MAX_LIMIT:
                continue
            if self.output_error_last_time < RTT_MAX_LIMIT:
                if self.output_quality_counter > BLOCKS_PER_ACK:
                    error_rate = float(self.output_blocks_errors_counter) / float(self.output_quality_counter)
                    if error_rate > ACCEPTABLE_ERRORS_RATE:
                        too_much_errors = True
                        break
            blocks_to_send_now.insert(0, block_id)
            self.output_blocks_errors_counter += 1
            self.output_quality_counter += 1.0
            self.output_error_last_time = relative_time
        if len(blocks_to_send_now) >= BLOCKS_PER_ACK:
            #--- full group of blocks with big timeouts
            self._send_blocks(blocks_to_send_now)
            self._add_iteration_result('fullgroup4')
            return
        if len(blocks_to_send_now) > 0:
            #--- not full group, bad situation
            self._send_blocks(blocks_to_send_now)
            self._add_iteration_result('badgroup')
            return
        if last_block_sent_delta > RECEIVING_TIMEOUT / 3.0 and len(self.output_blocks_ids) > 0:
            #--- keep alive, send one block
            oldest_block_id = sorted(self.output_blocks_ids)[0]
            self._send_blocks([oldest_block_id, ])
            self._add_iteration_result('alive')
            return
            #--- skip sending, no blocks ready to be sent
        self._add_iteration_result('skip')

    def _send_blocks(self, blocks_to_send):
        relative_time = time.time() - self.creation_time
        current_limit = self.calculate_real_output_limit()
        new_blocks_counter = 0
        for block_id in blocks_to_send:
            piece = self.output_blocks[block_id][0]
            data_size = len(piece)
            if current_limit > 0 and relative_time > 0:
            #--- limit sending, current rate is too big
                current_rate = (self.output_bytes_sent + data_size) / relative_time
                if current_rate > current_limit:
                    last_block_sent_delta = relative_time - self.output_block_last_time
                    if new_blocks_counter > 0 and last_block_sent_delta < RTT_MAX_LIMIT / 2.0:
                        self._add_iteration_result('limit1')
                        break
                    last_ack_received_delta = relative_time - self.output_ack_last_time
                    if last_ack_received_delta < RTT_MAX_LIMIT:
                        self._add_iteration_result('limit3')
                        break
            output = ''.join((struct.pack('i', block_id), piece))
            #--- SEND DATA HERE!
            if not self.producer.do_send_data(self.stream_id, self.consumer, output):
                self._add_iteration_result('limit4')
                break
            #--- mark block as sent
            self.output_blocks[block_id][1] = relative_time
            # erase acks missed for this block
            self.output_blocks[block_id][2] = 0
            # but increase number of attempts made
            self.output_blocks[block_id][3] += 1
            self.output_bytes_sent += data_size
            self.output_bytes_sent_period += data_size
            self.output_blocks_counter += 1
            new_blocks_counter += 1
            self.output_block_last_time = relative_time
            if _Debug:
                lg.out(self.debug_level + 8, '<-out BLOCK %d %r %r %d/%d' % (
                    self.stream_id,
                    self.eof,
                    block_id,
                    self.output_bytes_sent,
                    self.output_bytes_acked))
        if relative_time > 0:
            #--- recalculate current sending speed
            self.output_bytes_per_sec_current = self.output_bytes_sent / relative_time
        return new_blocks_counter > 0

    def _resend_ack(self):
        if self.output_acks_counter == 0:
            #--- do send first ACK
            self._send_ack(self.input_blocks_to_ack)
            return
        if self._block_period_avarage() == 0:
            #--- SKIP: block frequency is unknown
            # that means no input block was received yet
            return
        relative_time = time.time() - self.creation_time
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
        if pause_time > 0:
            self.input_limit_iteration_last_time = relative_time
        receiving_was_limited = relative_time - self.input_limit_iteration_last_time < RECEIVING_TIMEOUT
        input_block_timed_out = relative_time - self.input_block_last_time > RECEIVING_TIMEOUT
        if not receiving_was_limited and input_block_timed_out:
            #--- last block came long time ago, timeout receiving
            if _Debug:
                lg.out(self.debug_level, 'TIMEOUT RECEIVING %d rtt=%r, last block:%r, last limit:%r reltime:%r, eof:%r, blocks to ack:%d' % (
                    self.stream_id, self._rtt_current(),
                    round(relative_time - self.input_block_last_time, 4),
                    round(relative_time - self.input_limit_iteration_last_time, 4),
                    relative_time, self.eof, len(self.input_blocks_to_ack),))
            reactor.callLater(0, self.automat, 'timeout')  # @UndefinedVariable
            return
        if len(self.input_blocks_to_ack) >= BLOCKS_PER_ACK:
            #--- received enough blocks to make a group, send ACK
            self._send_ack(self.input_blocks_to_ack, pause_time, why=1)
            return
        if self.eof:
            #--- at EOF state, send ACK
            self._send_ack(self.input_blocks_to_ack, pause_time, why=3)
            return
        if self._last_ack_timed_out() and len(self.input_blocks_to_ack) > 0:
            #--- last ack has been long time ago, send ACK
            self._send_ack(self.input_blocks_to_ack, pause_time, why=4)
            return
        if _Debug and lg.is_debug(self.debug_level):
            why = 6
            if why not in self.output_acks_reasons:
                self.output_acks_reasons[why] = 1
            else:
                self.output_acks_reasons[why] += 1

    def _send_ack(self, acks, pause_time=0.0, why=0):
        if _Debug and lg.is_debug(self.debug_level):
            if why not in self.output_acks_reasons:
                self.output_acks_reasons[why] = 1
            else:
                self.output_acks_reasons[why] += 1
        if len(acks) == 0 and pause_time == 0.0 and not self.eof:
        #--- SKIP: no pending ACKS, no PAUSE, no EOF
            return
        #--- prepare EOF state in ACK
        ack_data = struct.pack('?', self.eof)
        #--- prepare ACKS
        ack_data += ''.join([struct.pack('i', bid) for bid in acks])
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
                lg.out(self.debug_level + 8, '<-out ACK %d %r %r %d/%d' % (
                    self.stream_id, self.eof, acks,
                    self.input_bytes_received,
                    self.consumer.bytes_received))
            else:
                lg.out(self.debug_level + 8, '<-out ACK %d %r PAUSE:%r LIMIT:%r %r' % (
                    self.stream_id, self.eof, pause_time, self.input_limit_bytes_per_sec, acks))
        self.producer.do_send_ack(self.stream_id, self.consumer, ack_data)
        return ack_len > 0

    def _rtt_current(self):
        rtt_current = self.output_rtt_avarage / self.output_rtt_counter
        return rtt_current

    def _block_period_avarage(self):
        if self.input_blocks_counter == 0:
            return 0
        return (time.time() - self.creation_time) / float(self.input_blocks_counter)

    def _last_ack_timed_out(self):
        return time.time() - self.output_ack_last_time > RTT_MAX_LIMIT / 2.0

    def _last_block_timed_out(self):
        return time.time() - self.input_block_last_time > RTT_MAX_LIMIT

    def get_output_limit_from_remote(self):
        return self.output_limit_bytes_per_sec_from_remote

    def get_output_limit(self):
        return self.output_limit_bytes_per_sec * self.output_limit_factor

    def calculate_real_output_limit(self):
        global _CurrentSendingAvarageRate
        own_limit = self.get_output_limit()
        avarage_limit = _CurrentSendingAvarageRate * 1.5
        remote_limit = self.get_output_limit_from_remote()
        return min(own_limit, avarage_limit, remote_limit)

    def get_current_output_speed(self):
        relative_time = time.time() - self.creation_time
        if relative_time < 0.5:
            return 0.0
        return self.output_bytes_sent / relative_time
