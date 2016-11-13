#!/usr/bin/env python
#udp_stream.py
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
.. module:: udp_stream
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

_Debug = False
_DebugLevel = 20

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

# depend on your network it can be 504 or bigger, 8K seems max.
UDP_DATAGRAM_SIZE = 500 
BLOCK_SIZE = UDP_DATAGRAM_SIZE - 14 # 14 bytes - BitDust header

BLOCKS_PER_ACK = 4  # need to verify delivery get success
                    # ack packets will be sent as response,
                    # one output ack per every N data blocks received 

OUTPUT_BUFFER_SIZE = 16*1024 # how many bytes to read from file at once
CHUNK_SIZE = BLOCK_SIZE * BLOCKS_PER_ACK # so we know how much to read now
# BLOCK_SIZE * int(float(BLOCKS_PER_ACK)*0.8) - 20% extra space in ack packet

RTT_MIN_LIMIT = 0.004 # round trip time, this adjust how fast we try to send
RTT_MAX_LIMIT = 4 # also affect pooling, but also set a time out for responses

MAX_BLOCKS_INTERVAL = 5 # resending blocks at lease every N seconds     
MAX_ACK_TIMEOUTS = 5  # if we get too much errors - connection will be closed
MAX_ACKS_INTERVAL = 5 # limit max delay between iterations in seconds.
RECEIVING_TIMEOUT = 15

#------------------------------------------------------------------------------ 

_Streams = {}
_GlobalLimitReceiveBytesPerSec = 1000.0 * 125000
_GlobalLimitSendBytesPerSec = 1000.0 * 125000

#------------------------------------------------------------------------------ 

def streams():
    global _Streams
    return _Streams

def create(stream_id, consumer, producer):
    """
    """
    if _Debug:
        lg.out(_DebugLevel-6, 'udp_stream.create stream_id=%s' % str(stream_id))
    s = UDPStream(stream_id, consumer, producer)
    streams()[s.stream_id] = s
    s.automat('init')
    reactor.callLater(0, balance_streams_limits)
    return s

def close(stream_id):
    """
    """
    s = streams().get(stream_id, None)
    if s is None:
        lg.warn('stream %d not exist')
        return False
    s.automat('close')
    if _Debug:
        lg.out(_DebugLevel-6, 'udp_stream.close send "close" to stream %s' % str(stream_id))
    return True    

#------------------------------------------------------------------------------ 

def get_global_limit_receive_bytes_per_sec():
    global _GlobalLimitReceiveBytesPerSec
    return _GlobalLimitReceiveBytesPerSec

def set_global_limit_receive_bytes_per_sec(bps):
    global _GlobalLimitReceiveBytesPerSec
    _GlobalLimitReceiveBytesPerSec = bps

def get_global_limit_send_bytes_per_sec():
    global _GlobalLimitSendBytesPerSec
    return _GlobalLimitSendBytesPerSec

def set_global_limit_send_bytes_per_sec(bps):
    global _GlobalLimitSendBytesPerSec
    _GlobalLimitSendBytesPerSec = bps
    
def balance_streams_limits():
    receive_limit_per_stream = get_global_limit_receive_bytes_per_sec()
    send_limit_per_stream = get_global_limit_send_bytes_per_sec()
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

class UDPStream(automat.Automat):
    """
    This class implements all the functionality of the ``udp_stream()`` state machine.
    """

    fast = True
    
    post = True

    def __init__(self, stream_id, consumer, producer):
        self.stream_id = stream_id
        self.consumer = consumer
        self.producer = producer
        self.consumer.set_stream_callback(self.on_consume)
        if _Debug:
            lg.out(_DebugLevel, 'udp_stream.__init__ %d peer_id:%s session:%s' % (
                self.stream_id, self.producer.session.peer_id, self.producer.session))
        name = 'udp_stream[%s]' % (self.stream_id)
        automat.Automat.__init__(self, name, 'AT_STARTUP', _DebugLevel, _Debug)
        
#    def __del__(self):
#        """
#        """
#        if _Debug:
#            lg.out(18, 'udp_stream.__del__ %d' % self.stream_id)
#        automat.Automat.__del__(self)

    def init(self):
        """
        """
        self.output_buffer_size = 0
        self.output_blocks = {}
        self.output_blocks_ids = []
        self.output_block_id = 0
        self.output_blocks_counter = 0
        self.output_acks_counter = 0
        self.input_blocks = {}
        self.input_block_id = 0
        self.input_blocks_counter = 0
        self.input_acks_counter = 0
        self.input_acks_timeouts_counter = 0
        self.input_acks_garbage_counter = 0
        self.input_duplicated_blocks = 0
        self.input_duplicated_bytes = 0
        self.blocks_to_ack = []
        self.bytes_in = 0
        self.bytes_in_acks = 0
        self.bytes_sent = 0
        self.bytes_acked = 0
        self.blocks_acked = 0
        self.resend_blocks = 0
        self.last_ack_moment = 0
        self.last_ack_received_time = 0
        self.last_received_block_time = 0
        self.last_received_block_id = 0
        self.last_block_sent_time = 0
        self.rtt_avarage = 0.0 
        self.rtt_counter = 0.0
        self.loop = None
        self.resend_inactivity_counter = 1
        self.current_send_bytes_per_sec = 0
        self.current_receive_bytes_per_sec = 0
        self.eof = False
        self.last_progress_report = 0

    def A(self, event, arg):
        newstate = self.state
        #---SENDING---
        if self.state == 'SENDING':
            if event == 'iterate' :
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
            elif event == 'consume' :
                self.doPushBlocks(arg)
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
            elif event == 'set-limits' :
                self.doUpdateLimits(arg)
            elif event == 'ack-received' and not self.isEOF(arg) and not self.isPaused(arg) :
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
            elif event == 'ack-received' and self.isEOF(arg) :
                self.doReportSendDone(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'ack-received' and self.isPaused(arg) :
                self.doResumeLater(arg)
                newstate = 'PAUSE'
            elif event == 'timeout' :
                self.doReportSendTimeout(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'close' :
                self.doReportClosed(arg)
                self.doCloseStream(arg)
                self.doDestroyMe(arg)
                newstate = 'CLOSED'
        #---DOWNTIME---
        elif self.state == 'DOWNTIME':
            if event == 'set-limits' :
                self.doUpdateLimits(arg)
            elif event == 'block-received' :
                self.doResendAck(arg)
                self.doReceivingLoop(arg)
                newstate = 'RECEIVING'
            elif event == 'close' :
                self.doReportClosed(arg)
                self.doCloseStream(arg)
                self.doDestroyMe(arg)
                newstate = 'CLOSED'
            elif event == 'ack-received' :
                self.doReportError(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'consume' :
                self.doPushBlocks(arg)
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
                newstate = 'SENDING'
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init' :
                self.doInit(arg)
                newstate = 'DOWNTIME'
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---RECEIVING---
        elif self.state == 'RECEIVING':
            if event == 'set-limits' :
                self.doUpdateLimits(arg)
            elif event == 'iterate' :
                self.doResendAck(arg)
                self.doReceivingLoop(arg)
            elif event == 'block-received' and not self.isEOF(arg) :
                self.doResendAck(arg)
                self.doReceivingLoop(arg)
            elif event == 'timeout' :
                self.doReportReceiveTimeout(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'close' :
                self.doReportClosed(arg)
                self.doCloseStream(arg)
                self.doDestroyMe(arg)
                newstate = 'CLOSED'
            elif event == 'block-received' and self.isEOF(arg) :
                self.doResendAck(arg)
                self.doReportReceiveDone(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
        #---COMPLETION---
        elif self.state == 'COMPLETION':
            if event == 'close' :
                self.doDestroyMe(arg)
                newstate = 'CLOSED'
        #---PAUSE---
        elif self.state == 'PAUSE':
            if event == 'consume' :
                self.doPushBlocks(arg)
            elif event == 'timeout' :
                self.doReportSendTimeout(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'ack-received' and self.isEOF(arg) :
                self.doReportSendDone(arg)
                self.doCloseStream(arg)
                newstate = 'COMPLETION'
            elif event == 'resume' :
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
                newstate = 'SENDING'
            elif event == 'close' :
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
        acks, pause = arg
        return pause > 0

    def doInit(self, arg):
        """
        Action method.
        """
        self.creation_time = time.time()
        self.limit_send_bytes_per_sec = get_global_limit_send_bytes_per_sec() / len(streams())
        self.limit_receive_bytes_per_sec = get_global_limit_receive_bytes_per_sec() / len(streams())
        if self.producer.session.min_rtt is not None:
            self.rtt_avarage = self.producer.session.min_rtt
        else:
            self.rtt_avarage = (RTT_MIN_LIMIT + RTT_MAX_LIMIT) / 2.0
        self.rtt_counter = 1.0
        if _Debug:
            lg.out(self.debug_level, 'udp_stream.doInit %d with %s limits: (in=%r|out=%r)  rtt=%r' % (
                self.stream_id, self.producer.session.peer_id,
                self.limit_receive_bytes_per_sec, self.limit_send_bytes_per_sec,
                self.rtt_avarage))

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
            self.output_block_id += 1
            bisect.insort(self.output_blocks_ids, self.output_block_id)
            # data, time_sent, acks_missed
            self.output_blocks[self.output_block_id] = [piece, -1, 0]
            self.output_buffer_size += len(piece)
        outp.close()
        if _Debug:
            lg.out(self.debug_level+6, 'PUSH %r' % self.output_blocks_ids)

#    def doPopBlocks(self, arg):
#        """
#        Action method.
#        """

    def doResendBlocks(self, arg):
        """
        Action method.
        """
#        lg.out(24, 'doResendBlocks %d %d %r %r %s' % (
#            self.input_acks_counter,
#            self.output_blocks_counter,
#            self.last_block_sent_time,
#            self.last_ack_received_time,
#            self.output_blocks.keys(), 
#            ))
        relative_time = time.time() - self.creation_time
        if len(self.output_blocks) == 0:
        #--- nothing to send
            self.resend_inactivity_counter +=1
            self.resend_blocks += 1
            self._send_blocks([]) 
            return
        if self.limit_send_bytes_per_sec > 0:
        #--- skip sending : limit reached 
            if relative_time > 0.0: 
                current_rate = self.bytes_sent / relative_time
                if current_rate > self.limit_send_bytes_per_sec:
                    if _Debug:
                        lg.out(self.debug_level, 'SKIP BLOCK LIMIT SENDING %d : %r>%r' % (
                            self.stream_id, current_rate, self.limit_send_bytes_per_sec))
                    self.resend_inactivity_counter += 1
                    return
        if self.input_acks_counter > 0:
        #--- got some response!
            if self.output_blocks_counter / self.input_acks_counter > BLOCKS_PER_ACK * 2:
        #--- too many blocks sent but few acks - check time out sending
                if self.state == 'SENDING' or self.state == 'PAUSE':
                    if relative_time - self.last_ack_received_time > RTT_MAX_LIMIT * 4:
        #--- no responding activity at all
                        if _Debug:
                            lg.out(self.debug_level, 'TIMEOUT SENDING rtt=%r, last ack at %r, last block was %r, reltime is %r' % (
                                self.rtt_avarage / self.rtt_counter,
                                self.last_ack_received_time, self.last_block_sent_time, relative_time))
                        reactor.callLater(0, self.automat, 'timeout')
                        return
        #--- skip sending : too few acks (seems like sending too fast)
                if _Debug:
                    lg.out(self.debug_level+6, 'SKIP SENDING %d, too few acks:%d blocks:%d' % (
                        self.stream_id, self.input_acks_counter, self.output_blocks_counter))
                self.resend_inactivity_counter += 1
                self.resend_blocks += 1
                self._send_blocks([]) 
                return
        if self.last_block_sent_time - self.last_ack_received_time > RTT_MAX_LIMIT * 2:
        #--- last ack is timed out
            self.input_acks_timeouts_counter += 1
            if self.input_acks_timeouts_counter >= MAX_ACK_TIMEOUTS:
        #--- timeout sending : too many timed out acks
                if _Debug:
                    lg.out(self.debug_level, 'SENDING BROKEN %d rtt=%r, last ack at %r, last block was %r' % (
                        self.stream_id, self.rtt_avarage / self.rtt_counter, 
                        self.last_ack_received_time, self.last_block_sent_time))
                reactor.callLater(0, self.automat, 'timeout')
            else:
        #--- resend one "oldest" block
                latest_block_id = self.output_blocks_ids[0]
                # self.output_blocks[latest_block_id][1] = -2
                # self.last_ack_received_time = relative_time # fake ack
                self.resend_inactivity_counter += 1
                self.resend_blocks += 1
                if _Debug:
                    lg.out(self.debug_level, 'RESEND ONE %d %d' % (self.stream_id, latest_block_id))
                self._send_blocks([latest_block_id,])
            return
        #--- no activity at all
#            if _Debug:
#                lg.out(18, 'TIMEOUT SENDING %d rtt=%r, last ack at %r, last block was %r, reltime is %r' % (
#                    self.stream_id, self.rtt_avarage / self.rtt_counter, 
#                    self.last_ack_received_time, self.last_block_sent_time, relative_time))
#            reactor.callLater(0, self.automat, 'timeout')
#            return
        #--- normal sending, check all pending blocks
        rtt_current = self.rtt_avarage / self.rtt_counter
        resend_time_limit = BLOCKS_PER_ACK * rtt_current
        blocks_to_send_now = []
        for block_id in self.output_blocks_ids:
            time_sent, acks_missed = self.output_blocks[block_id][1:3]
            timed_out = time_sent >= 0 and (relative_time - time_sent > resend_time_limit)
        #--- decide to send the block now
            if time_sent == -1 or timed_out or (acks_missed > 2 and ((acks_missed % 3) == 0)):
                blocks_to_send_now.append(block_id)
                if time_sent > 0:
                    self.resend_blocks += 1
                # if _Debug:
                #     lg.out(24, 'SENDING BLOCK %d %r %r %r' % (
                #         block_id, time_sent, relative_time - time_sent, acks_missed))
            # else:
                # if _Debug:
                #     lg.out(24, 'SKIP SENDING BLOCK %d %r %r %r' % (
                #         block_id, time_sent, relative_time - time_sent, acks_missed))
                    # this block is not yet timed out ...
                    # and just a fiew acks were received after it was sent ... 
                    # skip now, not need to resend
        self.resend_inactivity_counter = 1
        self._send_blocks(blocks_to_send_now)
        del blocks_to_send_now

    def doResendAck(self, arg):
        """
        Action method.
        """
        some_blocks_to_ack = len(self.blocks_to_ack) > 0
        relative_time = time.time() - self.creation_time
        period_avarage = self._block_period_avarage()
        first_block_in_group = (self.last_received_block_id % BLOCKS_PER_ACK) == 1
        pause_time = 0.0
        if relative_time > 0:
            self.current_receive_bytes_per_sec = self.bytes_in / relative_time
        #--- limit receiving, calculate pause time
        if self.limit_receive_bytes_per_sec > 0 and relative_time > 0:
            #current_rate = self.bytes_in / relative_time
            max_receive_available = self.limit_receive_bytes_per_sec * relative_time
            if self.bytes_in > max_receive_available:
                #pause_time = ( self.bytes_in / self.limit_receive_bytes_per_sec ) - relative_time
                pause_time = (self.bytes_in - max_receive_available) / self.limit_receive_bytes_per_sec
                if pause_time < 0:
                    lg.warn('pause is %r, stream_id=%d' % (pause_time, self.stream_id)) 
                    pause_time = 0.0
        # if not some_blocks_to_ack and pause_time == 0.0 and not self.eof:
        #--- no blocks to ack now, no need to pause and not rich EOF
        if relative_time - self.last_received_block_time > RECEIVING_TIMEOUT:
        #--- and last block has been long ago
                if _Debug:
                    lg.out(self.debug_level, 'TIMEOUT RECEIVING %d rtt=%r, last block in %r, reltime: %r, eof: %r, blocks to ack: %d' % (
                        self.stream_id, self._rtt_current(), self.last_received_block_time,
                        relative_time, self.eof, len(self.blocks_to_ack),))
                reactor.callLater(0, self.automat, 'timeout')
                return
            # self.resend_inactivity_counter += 1
        activity = False
        #--- need to send some acks
        if period_avarage == 0 or self.output_acks_counter == 0:
        #--- nothing was send, do send first ack now
            activity = self._send_ack(self.blocks_to_ack)
        else:
        #--- last ack has been long ago or
        # need to send ack now because too many blocks was received at once
            last_ack_timeout = self._last_ack_timed_out()
        #--- EOF state
            if last_ack_timeout or first_block_in_group or self.eof:
                activity = self._send_ack(self.blocks_to_ack, pause_time)
        if activity:
            self.resend_inactivity_counter = 1
        else:
            self.resend_inactivity_counter += 1

    def doSendingLoop(self, arg):
        """
        Action method.
        """
        if lg.is_debug(self.debug_level):
            relative_time = time.time() - self.creation_time
            if relative_time - self.last_progress_report > 1.0:
                self.last_progress_report = relative_time
                if _Debug:
                    lg.out(self.debug_level, 'udp_stream[%d] | %r%% sent | %d/%d/%d | %r bps | %r sec dt' % (
                        self.stream_id, round(100.0*(float(self.bytes_acked)/self.consumer.size),2),
                        self.bytes_sent, self.bytes_acked,
                        self.consumer.size, int(self.current_send_bytes_per_sec),
                        round(relative_time-self.last_ack_received_time,4)))
        if self.loop is None:
            next_iteration = min(MAX_BLOCKS_INTERVAL, 
                                 self._rtt_current() * self.resend_inactivity_counter)
            self.loop = reactor.callLater(next_iteration, self.automat, 'iterate') 
            return
        if self.loop.called:
            next_iteration = min(MAX_BLOCKS_INTERVAL, 
                                 self._rtt_current() * self.resend_inactivity_counter)
            self.loop = reactor.callLater(next_iteration, self.automat, 'iterate') 
            return
        if self.loop.cancelled:
            self.loop = None
            return

    def doReceivingLoop(self, arg):
        """
        Action method.
        """
        if lg.is_debug(self.debug_level):
            relative_time = time.time() - self.creation_time
            if relative_time - self.last_progress_report > 1.0:
                self.last_progress_report = relative_time
                if _Debug:
                    lg.out(self.debug_level, 'udp_stream[%d] | %r%% received | %d/%d/%d | %dbps | %r sec dt | from %s' % (self.stream_id, 
                        round(100.0*(float(self.consumer.bytes_received)/self.consumer.size),2), 
                        self.bytes_in, self.consumer.bytes_received, 
                        self.consumer.size, int(self.current_receive_bytes_per_sec),
                        round(relative_time-self.last_received_block_time, 4),
                        self.producer.session.peer_id))
        if self.loop is None:
            next_iteration = min(MAX_ACKS_INTERVAL, 
                             max(RTT_MIN_LIMIT/2.0, 
                             self._block_period_avarage() * self.resend_inactivity_counter))
            self.loop = reactor.callLater(next_iteration, self.automat, 'iterate') 
            return
        if self.loop.called:
            next_iteration = min(MAX_ACKS_INTERVAL, 
                             max(RTT_MIN_LIMIT/2.0, 
                             self._block_period_avarage() * self.resend_inactivity_counter))
            self.loop = reactor.callLater(next_iteration, self.automat, 'iterate') 
            return
        if self.loop.cancelled:
            self.loop = None
            return

    def doResumeLater(self, arg):
        """
        Action method.
        """
        acks, pause = arg
        if pause > 0:
            reactor.callLater(pause, self.automat, 'resume')

    def doReportSendDone(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(self.debug_level, 'udp_stream.doReportSendDone %r %r' % (self.consumer, self.consumer.is_done()))
        if self.consumer.is_done():
            self.consumer.status = 'finished'
        else:
            self.consumer.status = 'failed'
            self.consumer.error_message = 'sending was not finished correctly'
        # reactor.callLater(0, self.producer.on_outbox_file_done, self.stream_id)
        self.producer.on_outbox_file_done(self.stream_id)
        # reactor.callLater(0, self.automat, 'close')
        # self.automat('close')

    def doReportSendTimeout(self, arg):
        """
        Action method.
        """
        if self.last_ack_received_time == 0:
            self.consumer.error_message = 'sending failed'
        else:
            self.consumer.error_message = 'remote side stopped responding'
        self.consumer.status = 'failed'
        self.consumer.timeout = True
        # reactor.callLater(0, self.producer.on_timeout_sending, self.stream_id)
        self.producer.on_timeout_sending(self.stream_id)
        # reactor.callLater(0, self.automat, 'close')        
        # self.automat('close')
        
    def doReportReceiveDone(self, arg):
        """
        Action method.
        """
        # Send Zero ack
        self.consumer.status = 'finished'
        # reactor.callLater(0, self.producer.on_inbox_file_done, self.stream_id)
        self.producer.on_inbox_file_done(self.stream_id) 
        # reactor.callLater(0, self.automat, 'close')
        # self.automat('close')
        

    def doReportReceiveTimeout(self, arg):
        """
        Action method.
        """
        self.consumer.error_message = 'receiving timeout'
        self.consumer.status = 'failed'
        self.consumer.timeout = True
        # reactor.callLater(0, self.producer.on_timeout_receiving, self.stream_id)
        self.producer.on_timeout_receiving(self.stream_id)
        # reactor.callLater(0, self.automat, 'close')
        # self.automat('close')

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
            ratein = self.bytes_in / dt
            rateout = self.bytes_sent / dt
            extra_acks_perc = 100.0 * self.input_acks_garbage_counter / float(self.blocks_acked+1)
            extra_blocks_perc = 100.0 * self.resend_blocks / float(self.output_block_id+1)
            lg.out(self.debug_level, 'udp_stream.doCloseStream %d %s' % (self.stream_id, pir_id))
            lg.out(self.debug_level, '    in:%d|%d acks:%d|%d dups:%d|%d out:%d|%d|%d|%d rate:%r|%r extra:A%s|B%s' % (
                self.input_blocks_counter, self.bytes_in,
                self.output_acks_counter, self.bytes_in_acks,
                self.input_duplicated_blocks, self.input_duplicated_bytes,
                self.output_blocks_counter, self.bytes_acked, 
                self.resend_blocks, self.input_acks_garbage_counter,
                int(ratein), int(rateout),
                misc.percent2string(extra_acks_perc), misc.percent2string(extra_blocks_perc)))
            del pir_id
        self._stop_resending()
        # self.consumer.clear_stream()
        self.input_blocks.clear()
        self.blocks_to_ack = []
        self.output_blocks.clear()
        self.output_blocks_ids = []
        # reactor.callLater(0, self.automat, 'close')
        # self.automat('close')

    def doUpdateLimits(self, arg):
        """
        Action method.
        """
        new_limit_receive, new_limit_send = arg
#        if  new_limit_receive > self.limit_receive_bytes_per_sec or \
#            new_limit_send > self.limit_send_bytes_per_sec: 
#            reactor.callLater(0, self.automat, 'iterate')
        self.limit_receive_bytes_per_sec = new_limit_receive
        self.limit_send_bytes_per_sec = new_limit_send
  
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
        # lg.out(18, 'doDestroyMe %s' % (str(self.stream_id)))

    def on_block_received(self, inpt):
        if self.consumer and getattr(self.consumer, 'on_received_raw_data', None):
            block_id = inpt.read(4)
            try:
                block_id = struct.unpack('i', block_id)[0]
            except:
                lg.exc()
                if _Debug:
                    lg.out(self.debug_level, 'ERROR receiving, stream_id=%s' % self.stream_id)
                return
            data = inpt.read()
            self.last_received_block_time = time.time() - self.creation_time
            self.input_blocks_counter += 1
            if block_id != -1:
                self.bytes_in += len(data)
                self.last_received_block_id = block_id
                eof = False
                raw_size = 0
                if block_id in self.input_blocks.keys():
                    self.input_duplicated_blocks += 1
                    self.input_duplicated_bytes += len(data)
                    # lg.warn('duplicated %d %d' % (self.stream_id, block_id))
                elif block_id < self.input_block_id:
                    self.input_duplicated_blocks += 1
                    self.input_duplicated_bytes += len(data)
                    # lg.warn('old %d %d current: %d' % (self.stream_id, block_id, self.input_block_id))
                else:                
                    self.input_blocks[block_id] = data
                    bisect.insort(self.blocks_to_ack, block_id)
                if block_id == self.input_block_id + 1:
                    newdata = cStringIO.StringIO()
                    while True:
                        next_block_id = self.input_block_id + 1
                        try:
                            blockdata = self.input_blocks.pop(next_block_id)
                        except KeyError:
                            break
                        newdata.write(blockdata)
                        raw_size += len(blockdata)
                        self.input_block_id = next_block_id
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
                    lg.out(self.debug_level+6, 'in-> BLOCK %d %r %d-%d %d %d %d' % (
                        self.stream_id, self.eof, block_id, self.input_block_id,
                        self.bytes_in, self.input_blocks_counter, 
                        len(self.blocks_to_ack)))
            else:
                if _Debug:
                    lg.out(self.debug_level+6, 'in-> BLOCK %d %r EMPTY %d %d' % (
                        self.stream_id, self.eof, 
                        self.bytes_in, self.input_blocks_counter))
            # self.automat('input-data-collected', (block_id, raw_size, eof_state))
            # reactor.callLater(0, self.automat, 'block-received', (block_id, raw_size, eof_state))
            self.automat('block-received', (block_id, data))
            # self.event('block-received', inpt)
    
    def on_ack_received(self, inpt):
        if self.consumer and getattr(self.consumer, 'on_sent_raw_data', None):
            try:
                eof_flag = None
                acks = []
                pause_time = 0.0
                eof = False
                raw_bytes = ''
                self.last_ack_received_time = time.time() - self.creation_time
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
                            # lg.out(24, 'in-> ACK %d' % (self.stream_id))
                            # self.sending_speed_factor *= 0.9
                            # lg.out(18, 'SPEED DOWN: %r' % self.sending_speed_factor)
                            # reactor.callLater(0, self.automat, 'iterate')
                if len(acks) > 0:
                    self.input_acks_counter += 1
                else:
                    if pause_time == 0.0 and eof_flag is not None and eof_flag:
                        sum_not_acked_blocks = sum(map(lambda block: len(block[0]),
                                                       self.output_blocks.values()))
                        self.bytes_acked += sum_not_acked_blocks
                        eof = self.consumer.on_sent_raw_data(sum_not_acked_blocks)
                        if _Debug:
                            lg.out(self.debug_level, '    ZERO FINISH %d eof:%r acked:%d tail:%d' % (
                                self.stream_id, eof, self.bytes_acked, sum_not_acked_blocks))
                for block_id in acks:                
                    try:
                        self.output_blocks_ids.remove(block_id)
                        outblock = self.output_blocks.pop(block_id)
                    except:
                        self.input_acks_garbage_counter += 1
                        if _Debug:
                            lg.out(self.debug_level+6, '    ack received but block %d not found, stream_id=%d' % (block_id, self.stream_id))
                        continue
                    block_size = len(outblock[0])
                    self.output_buffer_size -= block_size 
                    self.bytes_acked += block_size
                    self.blocks_acked += 1
                    relative_time = time.time() - self.creation_time
                    last_ack_rtt = relative_time - outblock[1]
                    self.rtt_avarage += last_ack_rtt
                    self.rtt_counter += 1.0
                    if self.rtt_counter > BLOCKS_PER_ACK * 100:
                        rtt = self.rtt_avarage / self.rtt_counter
                        self.rtt_counter = BLOCKS_PER_ACK
                        self.rtt_avarage = rtt * self.rtt_counter 
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
                        lg.out(self.debug_level+6, 'in-> ACK %d PAUSE:%r %s %d %s %d %d' % (
                            self.stream_id, pause_time, acks, len(self.output_blocks), 
                            eof, sz, self.bytes_acked))
                    else:
                        lg.out(self.debug_level+6, 'in-> ACK %d %s %d %s %d %d' % (
                            self.stream_id, acks, len(self.output_blocks), eof, sz, self.bytes_acked))
                # self.automat('output-data-acked', (acks, eof))
                # reactor.callLater(0, self.automat, 'ack-received', (acks, eof))
                self.automat('ack-received', (acks, pause_time))
    #            if pause_time > 0:
    #                self.automat('suspend')
    #                reactor.callLater(pause_time, self.automat, 'resume')
            except:
                lg.exc()

    def on_consume(self, data):
        if self.consumer:
            if self.output_buffer_size + len(data) > OUTPUT_BUFFER_SIZE:
                raise BufferOverflow(self.output_buffer_size)
            self.event('consume', data)
        
    def on_close(self):
        if _Debug:
            lg.out(self.debug_level, 
                'udp_stream.UDPStream[%d].on_close, send "close" to self.A()' % self.stream_id)
        if self.consumer:
            reactor.callLater(0, self.automat, 'close')

    def _send_blocks(self, blocks_to_send):
        relative_time = time.time() - self.creation_time
        new_blocks_counter = 0
        for block_id in blocks_to_send:
            piece = self.output_blocks[block_id][0]
            data_size = len(piece)
            if self.limit_send_bytes_per_sec > 0 and relative_time > 0:
                current_rate = (self.bytes_sent + data_size) / relative_time
                if current_rate > self.limit_send_bytes_per_sec:
                    continue
            self.output_blocks[block_id][1] = relative_time
            output = ''.join((struct.pack('i', block_id), piece))
            self.producer.do_send_data(self.stream_id, self.consumer, output)
            self.bytes_sent += data_size
            self.output_blocks_counter += 1
            new_blocks_counter += 1
            self.last_block_sent_time = relative_time
            if _Debug:
                lg.out(self.debug_level+6, '<-out BLOCK %d %r %r %d/%d' % (
                    self.stream_id, self.eof, block_id, self.bytes_sent, self.bytes_acked))
        if new_blocks_counter == 0:
            if relative_time - self.last_block_sent_time > MAX_BLOCKS_INTERVAL:
                output = ''.join((struct.pack('i', -1), ''))
                self.producer.do_send_data(self.stream_id, self.consumer, output)
                self.output_blocks_counter += 1
                if _Debug:
                    lg.out(self.debug_level+6, '<-out BLOCK %d %r EMPTY dt=%r' % (
                        self.stream_id, self.eof, relative_time - self.last_block_sent_time))
                self.last_block_sent_time = relative_time
        if relative_time > 0:
            self.current_send_bytes_per_sec = self.bytes_sent / relative_time

    def _send_ack(self, acks, pause_time=0.0):
        if len(acks) == 0 and pause_time == 0.0 and not self.eof:
#            if _Debug:
#                lg.out(24, 'X-out ACK SKIP %d %d %r %r' % (
#                    self.stream_id, len(acks), pause_time, self.eof))
            return
        ack_data = struct.pack('?', self.eof)
        ack_data += ''.join(map(lambda bid: struct.pack('i', bid), acks))
        if pause_time > 0:
            ack_data += struct.pack('i', -1)
            ack_data += struct.pack('f', pause_time)
        ack_len = len(ack_data)
        self.bytes_in_acks += ack_len 
        self.output_acks_counter += 1
        self.blocks_to_ack = []
        self.last_ack_moment = time.time()
        if _Debug:
            if pause_time <= 0.0:
                lg.out(self.debug_level+6, '<-out ACK %d %r %r %d/%d' % (
                    self.stream_id, self.eof, acks, self.bytes_in, self.consumer.bytes_received))
            else:
                lg.out(self.debug_level+6, '<-out ACK %d %r PAUSE:%r %r' % (
                    self.stream_id, self.eof, pause_time, acks))
        self.producer.do_send_ack(self.stream_id, self.consumer, ack_data)
        return ack_len > 0
            
    def _stop_resending(self):
        if self.loop:
            if self.loop.active():
                self.loop.cancel()
            self.loop = None

    def _rtt_current(self):
        rtt_current = self.rtt_avarage / self.rtt_counter
        rtt_current = max(min(rtt_current, RTT_MAX_LIMIT), RTT_MIN_LIMIT)
        return rtt_current
    
    def _block_period_avarage(self):
        if self.input_blocks_counter == 0:
            return 0  
        return (time.time() - self.creation_time) / self.input_blocks_counter

    def _last_ack_timed_out(self):
        return time.time() - self.last_ack_moment > RTT_MAX_LIMIT
        
