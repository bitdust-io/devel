


"""
.. module:: udp_stream
.. role:: red

BitPie.NET udp_stream() Automat

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


import sys
import time
import cStringIO
import struct
import bisect

from twisted.internet import reactor

from logs import lg

from lib import udp
from lib import automat

#------------------------------------------------------------------------------ 

_Debug = True

#------------------------------------------------------------------------------ 

UDP_DATAGRAM_SIZE = 508
BLOCK_SIZE = UDP_DATAGRAM_SIZE - 14 

BLOCKS_PER_ACK = 16

OUTPUT_BUFFER_SIZE = 16*1024
CHUNK_SIZE = BLOCK_SIZE * BLOCKS_PER_ACK # BLOCK_SIZE * int(float(BLOCKS_PER_ACK)*0.8) - 20% extra space in ack packet

RTT_MIN_LIMIT = 0.002
RTT_MAX_LIMIT = 3

MAX_ACK_TIMEOUTS = 3

#------------------------------------------------------------------------------ 

_Streams = {}
_GlobalLimitReceiveBytesPerSec = 1.0 * 125000
_GlobalLimitSendBytesPerSec = 100.0 * 125000

#------------------------------------------------------------------------------ 

def streams():
    global _Streams
    return _Streams

def create(stream_id, consumer, producer):
    """
    """
    lg.out(14, 'udp_stream.create stream_id=%s' % str(stream_id))
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
        return False
    s.automat('close')
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
    lg.out(18, 'udp_stream.balance_streams_limits in:%r out:%r total:%d' % (
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
            lg.out(18, 'udp_stream.__init__ %d peer_id:%s session:%s' % (
                self.stream_id, self.producer.session.peer_id, self.producer.session))
        name = 'udp_stream[%s]' % (self.stream_id)
        automat.Automat.__init__(self, name, 'AT_STARTUP', 8)
        
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
        self.input_duplicated_blocks = 0
        self.input_duplicated_bytes = 0
        self.blocks_to_ack = []
        self.bytes_in = 0
        self.bytes_in_acks = 0
        self.bytes_sent = 0
        self.bytes_acked = 0
        self.resend_bytes = 0
        self.resend_blocks = 0
        self.last_ack_moment = 0
        self.last_ack_received_time = 0
        self.last_received_block_time = 0
        self.last_received_block_id = 0
        self.last_block_sent_time = 0
        self.rtt_avarage = 0.0 
        self.rtt_counter = 0.0
        self.resend_task = None
        self.resend_inactivity_counter = 1
        self.current_send_bytes_per_sec = 0
        # self.sending_speed_factor = 1.0
        self.need_to_ack_this_block = False

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
            elif event == 'ack-received' and not self.isPaused(arg) and not ( self.isZeroAck(arg) or self.isWriteEOF(arg) ) :
                self.doResendBlocks(arg)
                self.doSendingLoop(arg)
            elif event == 'ack-received' and ( self.isZeroAck(arg) or self.isWriteEOF(arg) ) :
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
            if event == 'block-received' and not self.isReadEOF(arg) :
                self.doResendAck(arg)
                self.doReceivingLoop(arg)
            elif event == 'set-limits' :
                self.doUpdateLimits(arg)
            elif event == 'iterate' :
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
            elif event == 'block-received' and self.isReadEOF(arg) :
                self.doResendAck(arg)
                self.doSendZeroAck(arg)
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
            elif event == 'ack-received' and ( self.isZeroAck(arg) or self.isWriteEOF(arg) ) :
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

    def isReadEOF(self, arg):
        """
        Condition method.
        """
        block_id, raw_size, eof_state = arg
        return eof_state

    def isWriteEOF(self, arg):
        """
        Condition method.
        """
        acks, eof, pause = arg
        return eof
    
    def isZeroAck(self, arg):
        acks, eof, pause = arg
        return len(acks) == 0

    def isPaused(self, arg):
        """
        Condition method.
        """
        acks, eof, pause = arg
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
        lg.out(18, 'udp_stream.doInit limits: (in=%r|out=%r)  rtt=%r' % (
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
            self.output_blocks[self.output_block_id] = [piece, -1]
            self.output_buffer_size += len(piece)
        outp.close()
        if _Debug:
            lg.out(24, 'PUSH %r' % self.output_blocks_ids)

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
        if len(self.output_blocks) == 0:
            #---nothing to send
            self.resend_inactivity_counter +=1 
            return
        relative_time = time.time() - self.creation_time
        if self.limit_send_bytes_per_sec > 0:
            #---skip sending : limit reached 
            if relative_time > 0.0: 
                current_rate = self.bytes_sent / relative_time
                current_limit = self.limit_send_bytes_per_sec #  * self.sending_speed_factor
                if current_rate > current_limit:
                    if _Debug:
                        lg.out(18, 'SKIP BLOCK LIMIT SENDING %d : %r>%r' % (
                            self.stream_id, current_rate, self.limit_send_bytes_per_sec))
                    self.resend_inactivity_counter += 1
                    return
        if self.input_acks_counter > 0:
            if self.output_blocks_counter / self.input_acks_counter > BLOCKS_PER_ACK * 2:
                #---too many blocks sent but few acks - check time out sending
                if self.state == 'SENDING' or self.state == 'PAUSE':
                    if relative_time - self.last_ack_received_time > RTT_MAX_LIMIT * 4:
                        #---no responding activity at all
                        if _Debug:
                            lg.out(18, 'TIMEOUT SENDING rtt=%r, last ack at %r, last block was %r, reltime is %r' % (
                                self.rtt_avarage / self.rtt_counter,
                                self.last_ack_received_time, self.last_block_sent_time, relative_time))
                        # reactor.callLater(0, self.automat, 'timeout')
                        # return
                #---skip sending : too few acks
                if _Debug:
                    lg.out(18, 'SKIP SENDING %d, too few acks:%d blocks:%d' % (
                        self.stream_id, self.input_acks_counter, self.output_blocks_counter))
                self.resend_inactivity_counter += 1
                return
        if self.last_block_sent_time - self.last_ack_received_time > RTT_MAX_LIMIT * 2:
            #---last ack is timed out
            self.input_acks_timeouts_counter += 1
            if self.input_acks_timeouts_counter >= MAX_ACK_TIMEOUTS:
                #---timeout sending : too many timed out acks
                if _Debug:
                    lg.out(18, 'SENDING BROKEN %d rtt=%r, last ack at %r, last block was %r' % (
                        self.stream_id, self.rtt_avarage / self.rtt_counter, 
                        self.last_ack_received_time, self.last_block_sent_time))
                reactor.callLater(0, self.automat, 'timeout')
            else:
                #---resend one "oldest" block
                latest_block_id = self.output_blocks_ids[0]
                # self.output_blocks[latest_block_id][1] = -2
                # self.last_ack_received_time = relative_time # fake ack
                self.resend_inactivity_counter += 1
                if _Debug:
                    lg.out(18, 'RESEND ONE %d %d' % (self.stream_id, latest_block_id))
                self._send_blocks([latest_block_id,])
            return
#        if relative_time - self.last_ack_received_time > RTT_MAX_LIMIT * 3 and \
#                relative_time - self.last_block_sent_time > RTT_MAX_LIMIT * 3 and \
#                    self.state == 'SENDING':
#            #---no activity at all
#            if _Debug:
#                lg.out(18, 'TIMEOUT SENDING %d rtt=%r, last ack at %r, last block was %r, reltime is %r' % (
#                    self.stream_id, self.rtt_avarage / self.rtt_counter, 
#                    self.last_ack_received_time, self.last_block_sent_time, relative_time))
#            reactor.callLater(0, self.automat, 'timeout')
#            return
        #---normal sending, check all pending blocks
        rtt_current = self.rtt_avarage / self.rtt_counter
        resend_time_limit = 2 * BLOCKS_PER_ACK * rtt_current
        blocks_to_send_now = []
        for block_id in self.output_blocks_ids:
            time_sent = self.output_blocks[block_id][1]
            if time_sent >= 0: # already sent that block at least one time
                if relative_time - time_sent < resend_time_limit:
                    # this block is not yet timed out - skip, not need to resend
                    continue
            blocks_to_send_now.append(block_id)
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
        # limit receiving, calculate pause time
        if self.limit_receive_bytes_per_sec > 0 and relative_time > 0:
            # current_rate = self.bytes_in / relative_time
            max_receive_available = self.limit_receive_bytes_per_sec * relative_time
            if self.bytes_in > max_receive_available:
                # pause_time = ( self.bytes_in / self.limit_receive_bytes_per_sec ) - relative_time
                pause_time = (self.bytes_in - max_receive_available) / self.limit_receive_bytes_per_sec
                if pause_time < 0:
                    lg.warn('pause is %r, stream_id=%d' % (pause_time, self.stream_id)) 
                    pause_time = 0.0
        if not some_blocks_to_ack:
            # no blocks to ack now
            if relative_time - self.last_received_block_time > RTT_MAX_LIMIT * 2:
                # and last block has been long ago 
                if _Debug:
                    lg.out(18, 'TIMEOUT RECEIVING rtt=%r, last block in %r, stream_id=%s' % (
                        self._rtt_current(), self.last_received_block_time, self.stream_id))
                reactor.callLater(0, self.automat, 'timeout')
            self.resend_inactivity_counter += 1
            return
        activity = False
        # need to send some acks
        if period_avarage == 0 or self.output_acks_counter == 0:
            # nothing was send, do send first ack now
            activity = self._send_ack()
        else:
            # last ack has been long ago or
            # need to send ack now because too many blocks was received at once
            last_ack_timeout = self._last_ack_timed_out()
            if last_ack_timeout or first_block_in_group:
                activity = self._send_ack(pause_time)
        if activity:
            self.resend_inactivity_counter = 1
        else:
            self.resend_inactivity_counter += 1
        
    def doSendZeroAck(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(24, '<-out ACK %d ZERO' % self.stream_id)
        self.producer.do_send_ack(self.stream_id, self.consumer, '')

    def doSendingLoop(self, arg):
        """
        Action method.
        """
        if self.resend_task is None:
            next_resend = self._rtt_current() * self.resend_inactivity_counter
            self.resend_task = reactor.callLater(next_resend, self.automat, 'iterate') 
            return
        if self.resend_task.called:
            next_resend = self._rtt_current() * self.resend_inactivity_counter
            self.resend_task = reactor.callLater(next_resend, self.automat, 'iterate') 
            return
        if self.resend_task.cancelled:
            self.resend_task = None
            return

    def doReceivingLoop(self, arg):
        """
        Action method.
        """
        if self.resend_task is None:
            next_resend = max(0.001, self._block_period_avarage() * self.resend_inactivity_counter)
            self.resend_task = reactor.callLater(next_resend, self.automat, 'iterate') 
            return
        if self.resend_task.called:
            next_resend = max(0.001, self._block_period_avarage() * self.resend_inactivity_counter)
            self.resend_task = reactor.callLater(next_resend, self.automat, 'iterate') 
            return
        if self.resend_task.cancelled:
            self.resend_task = None
            return

    def doResumeLater(self, arg):
        """
        Action method.
        """
        acks, eof, pause = arg
        if pause > 0:
            reactor.callLater(pause, self.automat, 'resume')

    def doReportSendDone(self, arg):
        """
        Action method.
        """
        lg.out(18, 'udp_stream.doReportSendDone %r %r' % (self.consumer, self.consumer.is_done()))
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
            lg.out(18, 'CLOSED %s' % self.stream_id)

    def doReportError(self, arg):
        """
        Action method.
        """
        lg.out(2, 'udp_stream.doReportError')

    def doCloseStream(self, arg):
        """
        Action method.
        """
        if _Debug:
            try:
                pir_id = self.producer.session.peer_id
            except:
                pir_id = 'None'
            lg.out(24, 'doCloseStream %d %s in:%d|%d acks:%d|%d dups:%d|%d out:%d|%d|%d|%d rate:%r|%r' % (
                self.stream_id, pir_id, self.input_blocks_counter, self.bytes_in,
                self.output_acks_counter, self.bytes_in_acks,
                self.input_duplicated_blocks, self.input_duplicated_bytes,
                self.output_blocks_counter, self.bytes_acked, 
                self.resend_blocks, self.resend_bytes,
                self.bytes_in / (time.time() - self.creation_time),
                self.bytes_sent / (time.time() - self.creation_time),))
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
        automat.objects().pop(self.index)
        reactor.callLater(0, balance_streams_limits)
        # lg.out(18, 'doDestroyMe %s' % (str(self.stream_id)))

    def on_block_received(self, inpt):
        if self.consumer:
            block_id = inpt.read(4)
            try:
                block_id = struct.unpack('i', block_id)[0]
            except:
                lg.exc()
                if _Debug:
                    lg.out(18, 'ERROR receiving, stream_id=%s' % self.stream_id)
                return
            data = inpt.read()
            self.input_blocks_counter += 1
            self.bytes_in += len(data)
            self.last_received_block_time = time.time() - self.creation_time
            self.last_received_block_id = block_id
            eof_state = False
            raw_size = 0
            if block_id in self.input_blocks.keys():
                self.input_duplicated_blocks += 1
                self.input_duplicated_bytes += len(data)
                lg.warn('duplicated %d %d' % (self.stream_id, block_id))
            elif block_id < self.input_block_id:
                self.input_duplicated_blocks += 1
                self.input_duplicated_bytes += len(data)
                lg.warn('old %d %d current: %d' % (self.stream_id, block_id, self.input_block_id))
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
                    eof_state = self.consumer.on_received_raw_data(newdata.getvalue())
                except:
                    lg.exc()
                newdata.close()
            if _Debug:
                lg.out(24, 'in-> DATA %d %d-%d %d %d %s %s' % (
                    self.stream_id, block_id, self.input_block_id,
                    self.bytes_in, self.input_blocks_counter, eof_state, 
                    len(self.blocks_to_ack)))
            # self.automat('input-data-collected', (block_id, raw_size, eof_state))
            # reactor.callLater(0, self.automat, 'block-received', (block_id, raw_size, eof_state))
            self.automat('block-received', (block_id, raw_size, eof_state))
            # self.event('block-received', inpt)
    
    def on_ack_received(self, inpt):
        if self.consumer:
            acks = []
            pause_time = 0.0
            eof = False
            raw_bytes = ''
            self.last_ack_received_time = time.time() - self.creation_time
            while True:
                raw_bytes = inpt.read(4)
                if not raw_bytes:
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
            for block_id in acks:                
                try:
                    self.output_blocks_ids.remove(block_id)
                    outblock = self.output_blocks.pop(block_id)
                except:
                    lg.warn('block %d not found, stream_id=%d' % (block_id, self.stream_id))
                    continue
                block_size = len(outblock[0])
                self.output_buffer_size -= block_size 
                self.bytes_acked += block_size
                relative_time = time.time() - self.creation_time
                last_ack_rtt = relative_time - outblock[1]
                self.rtt_avarage += last_ack_rtt
                self.rtt_counter += 1.0
                if self.rtt_counter > BLOCKS_PER_ACK * 100:
                    rtt = self.rtt_avarage / self.rtt_counter
                    self.rtt_counter = BLOCKS_PER_ACK
                    self.rtt_avarage = rtt * self.rtt_counter 
                eof = self.consumer.on_sent_raw_data(block_size)
            if len(acks) > 0:
                self.input_acks_counter += 1
#                if self.input_acks_counter % int(BLOCKS_PER_ACK / 2) == 1:
#                    self.sending_speed_factor *= 1.05
#                    if self.sending_speed_factor > 1.0:
#                        self.sending_speed_factor = 1.0
#                    if _Debug:
#                        lg.out(18, 'SPEED UP: %r' % self.sending_speed_factor)
            else:
                if pause_time == 0.0:
                    sum_not_acked_blocks = sum(map(lambda block: len(block[0]),
                                                   self.output_blocks.values()))
                    self.bytes_acked += sum_not_acked_blocks
                    eof = self.consumer.on_sent_raw_data(sum_not_acked_blocks)
                    if _Debug:
                        lg.out(18, '    ZERO FINISH %d eof:%r acked:%d tail:%d' % (
                            self.stream_id, eof, self.bytes_acked, sum_not_acked_blocks))
            if _Debug:
                try:
                    sz = self.consumer.size
                except:
                    sz = -1
                if pause_time > 0:
                    lg.out(24, 'in-> ACK %d PAUSE:%r %s %d %s %d %d' % (
                        self.stream_id, pause_time, acks, len(self.output_blocks), 
                        eof, sz, self.bytes_acked))
                else:
                    lg.out(24, 'in-> ACK %d %s %d %s %d %d' % (
                        self.stream_id, acks, len(self.output_blocks), eof, sz, self.bytes_acked))
            # self.automat('output-data-acked', (acks, eof))
            # reactor.callLater(0, self.automat, 'ack-received', (acks, eof))
            self.automat('ack-received', (acks, eof, pause_time))
#            if pause_time > 0:
#                self.automat('suspend')
#                reactor.callLater(pause_time, self.automat, 'resume')

    def on_consume(self, data):
        if self.consumer:
            if self.output_buffer_size + len(data) > OUTPUT_BUFFER_SIZE:
                raise BufferOverflow(self.output_buffer_size)
            self.event('consume', data)
        
    def on_close(self):
        lg.out(18, 'udp_stream.on_close %s' % self.stream_id)
        if self.consumer:
            reactor.callLater(0, self.automat, 'close')

    def _send_blocks(self, blocks_to_send):
        relative_time = time.time() - self.creation_time
        new_blocks_counter = 0
        for block_id in blocks_to_send:
            piece = self.output_blocks[block_id][0]
            data_size = len(piece)
            self.output_blocks[block_id][1] = relative_time
            output = ''.join((struct.pack('i', block_id), piece))
            self.producer.do_send_data(self.stream_id, self.consumer, output)
            self.bytes_sent += data_size
            self.output_blocks_counter += 1
            self.last_block_sent_time = relative_time
            new_blocks_counter += 1
        if relative_time > 0:
            self.current_send_bytes_per_sec = self.bytes_sent / relative_time

    def _send_ack(self, pause_time=0.0):
        ack_data = ''.join(map(lambda bid: struct.pack('i', bid), self.blocks_to_ack))
        if pause_time > 0:
            ack_data += struct.pack('i', -1)
            ack_data += struct.pack('f', pause_time)
        ack_len = len(ack_data)
        self.bytes_in_acks += ack_len 
        self.output_acks_counter += 1
        self.blocks_to_ack = []
        self.last_ack_moment = time.time()
        if _Debug:
            if ack_len > 0:
                if pause_time <= 0.0:
                    lg.out(24, '<-out ACK %d %s' % (self.stream_id,
                        ','.join(map(lambda x: str(struct.unpack('i', x)[0]), 
                                     [ack_data[i:i+4] for i in range(0, len(ack_data), 4)]))))
                else:
                    lg.out(24, '<-out ACK %d PAUSE:%r %s' % (self.stream_id,
                        pause_time, ','.join(map(lambda x: str(struct.unpack('i', x)[0]), 
                                     [ack_data[i:i+4] for i in range(0, len(ack_data)-8, 4)]))))
            else:
                lg.out(24, '<-out ACK %d ZERO' % self.stream_id)
        self.producer.do_send_ack(self.stream_id, self.consumer, ack_data)
        return ack_len > 0
            
    def _stop_resending(self):
        if self.resend_task:
            if self.resend_task.active():
                self.resend_task.cancel()
            self.resend_task = None

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
        
