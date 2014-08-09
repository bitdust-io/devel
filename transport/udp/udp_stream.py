
import time
import cStringIO
import struct
import bisect

from twisted.internet import reactor

from logs import lg

from lib import udp

#------------------------------------------------------------------------------ 

"""
Datagram Format

[Data] packet

bytes:
  0        software version number
  1        command identifier, see ``lib.udp`` module
  2-5      stream_id 
  6-9      total data size to be transferred, peer must know when to stop receiving
  10-13    block_id, outgoing blocks are counted from 1
  from 14  payload data   
  
"""

UDP_DATAGRAM_SIZE = 508
BLOCK_SIZE = UDP_DATAGRAM_SIZE - 14 

BLOCKS_PER_ACK = 64

MAX_BUFFER_SIZE = 64*1024
BUFFER_SIZE = BLOCK_SIZE * BLOCKS_PER_ACK # BLOCK_SIZE * int(float(BLOCKS_PER_ACK)*0.8) - 20% extra space in ack packet

RTT_MIN_LIMIT = 0.002
RTT_MAX_LIMIT = 0.5

MAX_ACK_TIMEOUTS = 5

#------------------------------------------------------------------------------ 

class UDPStream():
    def __init__(self, stream_id, consumer, producer):
        self.stream_id = stream_id
        self.consumer = consumer
        self.producer = producer
        self.consumer.stream = self
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
        self.last_block_received_time = 0
        self.rtt_avarage = RTT_MIN_LIMIT # RTT_MAX_LIMIT
        self.rtt_acks_counter = 1.0
        self.resend_task = None
        self.resend_inactivity_counter = 0
        self.resend_counter = 0
        self.limit_send_bytes_per_sec = 10 * 125000 # 1 Mbps = 125000 B/s ~ 122 KB/s 
        self.creation_time = time.time()
        lg.out(18, 'udp_stream.__init__ %d peer_id:%s session:%s' % (
            self.stream_id, self.producer.session.peer_id, self.producer.session))
        
    def __del__(self):
        """
        """
        lg.out(18, 'udp_stream.__del__ %d' % self.stream_id)
        
    def close(self):
        try:
            pir_id = self.producer.session.peer_id
        except:
            pir_id = 'None'
        lg.out(18, 'udp_stream.close %d %s in:%d|%d acks:%d|%d dups:%d|%d out:%d|%d|%d|%d' % (
            self.stream_id, pir_id, self.input_blocks_counter, self.bytes_in,
            self.output_acks_counter, self.bytes_in_acks,
            self.input_duplicated_blocks, self.input_duplicated_bytes,
            self.output_blocks_counter, self.bytes_acked, 
            self.resend_blocks, self.resend_bytes,))
        self.stop_resending()
        self.consumer.stream = None
        self.consumer = None
        self.producer = None
        self.input_blocks.clear()
        self.blocks_to_ack = []
        self.output_blocks.clear()
        self.output_blocks_ids = []
        
    def block_received(self, inpt):
        if self.consumer:
            block_id = inpt.read(4)
            try:
                block_id = struct.unpack('i', block_id)[0]
            except:
                lg.exc()
                return
            data = inpt.read()
            if block_id in self.input_blocks.keys():
                self.input_duplicated_blocks += 1
                self.input_duplicated_bytes += len(data)
                lg.warn('duplicated %d %d' % (self.stream_id, block_id))
            self.input_blocks[block_id] = data
            self.input_blocks_counter += 1
            self.bytes_in += len(data)
            bisect.insort(self.blocks_to_ack, block_id)
            self.last_block_received_time = time.time() - self.creation_time
            eof_state = False
            if block_id == self.input_block_id + 1:
                newdata = cStringIO.StringIO()
                while True:
                    next_block_id = self.input_block_id + 1
                    try:
                        blockdata = self.input_blocks.pop(next_block_id)
                    except KeyError:
                        break
                    newdata.write(blockdata)
                    self.input_block_id = next_block_id
                try:
                    eof_state = self.consumer.on_received_raw_data(newdata.getvalue())
                except:
                    lg.exc()
                newdata.close()
            # want to send the first ack asap - started from 1
            is_ack_timed_out = (time.time() - self.last_ack_moment) > RTT_MAX_LIMIT
            is_first_block_in_group = ( (block_id % BLOCKS_PER_ACK) == 1)
            lg.out(18, 'in-> DATA %d %d %d %d %s %s %s' % (
                self.stream_id, block_id, len(self.blocks_to_ack), 
                self.input_block_id, is_ack_timed_out, is_first_block_in_group, eof_state))
            if is_ack_timed_out or is_first_block_in_group or eof_state:
                self.resend(need_to_ack=True)
            if eof_state:
                self.producer.do_send_ack(self.stream_id, self.consumer, '')
                self.producer.on_inbox_file_done(self.consumer, 'finished')
                
    
    def ack_received(self, inpt):
        if self.consumer:
            acks = []
            eof = False
            raw_bytes = ''
            self.last_ack_received_time = time.time() - self.creation_time
            while True:
                raw_bytes = inpt.read(4)
                if not raw_bytes:
                    break
                block_id = struct.unpack('i', raw_bytes)[0]
                acks.append(block_id)
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
                self.rtt_acks_counter += 1.0
                if self.rtt_avarage > 1000000 or self.rtt_acks_counter > 1000000:
                    rtt = self.rtt_avarage / self.rtt_acks_counter
                    self.rtt_acks_counter = BLOCKS_PER_ACK * 2
                    self.rtt_avarage = rtt * self.rtt_acks_counter 
                eof = self.consumer.on_sent_raw_data(block_size)
                # eof = self.consumer and (self.consumer.size == self.bytes_acked)
            try:
                sz = self.consumer.size
            except:
                sz = -1 
            lg.out(18, 'in-> ACK %d %s %d %s %d %d' % (
                self.stream_id, acks, len(self.output_blocks), eof,
                sz, self.bytes_acked))
            if eof:
                self.consumer.status = 'finished'
                self.producer.on_outbox_file_done(self.stream_id)
                return
            if len(acks) == 0:
                # print 'zero ack %s' % self.stream_id
                self.stop_resending()
                sum_not_acked_blocks = sum(map(lambda block: len(block[0]), 
                                               self.output_blocks.values()))
                self.output_blocks.clear()
                self.output_blocks_ids = []
                self.output_buffer_size = 0                
                self.bytes_acked += sum_not_acked_blocks
                relative_time = time.time() - self.creation_time
                self.consumer.on_zero_ack(sum_not_acked_blocks)
                return            
            self.input_acks_counter += 1
            # print 'ack %s blocks:(%d|%d)' % (self.stream_id, acks, len(self.output_blocks.keys())) 
            self.resend()

    def write(self, data):
        if self.output_buffer_size + len(data) > MAX_BUFFER_SIZE:
            raise BufferOverflow(self.output_buffer_size)
        # print 'write', len(data)
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
        lg.out(18, 'WRITE %r' % self.output_blocks_ids)
        self.resend()
        
    def send_blocks(self):
        if not self.consumer:
            return False
        relative_time = time.time() - self.creation_time
        rtt_current = self.rtt_avarage / self.rtt_acks_counter
        resend_time_limit = 2 * BLOCKS_PER_ACK * rtt_current
        new_blocks_counter = 0 
        for block_id in self.output_blocks_ids:
            if relative_time > 0.0: 
                if self.bytes_sent / relative_time > self.limit_send_bytes_per_sec:
                    break
            piece, time_sent = self.output_blocks[block_id]
            data_size = len(piece)
            if time_sent >= 0:
                dt = relative_time - time_sent
                if dt > resend_time_limit and self.last_ack_received_time > 0:
                    self.resend_bytes += data_size
                    self.resend_blocks += 1
                else:
                    continue
            time_sent = relative_time
            self.output_blocks[block_id][1] = time_sent
            output = ''.join((
                struct.pack('i', block_id),
                piece))
            # DEBUG
            # import random
            # if random.randint(0, 9) >= 1:
                # 10 % percent lost
                # self.producer.do_send_data(self.stream_id, self.consumer, output)
            self.producer.do_send_data(self.stream_id, self.consumer, output)
            self.bytes_sent += data_size
            self.output_blocks_counter += 1
            new_blocks_counter += 1
        # if new_blocks_counter > 0:
        #     print 'send blocks %d|%d|%d' % (new_blocks_counter, len(self.output_blocks.keys()), self.output_blocks_counter), 
        #     print 'bytes:(%d|%d|%d)' % (self.bytes_acked, self.bytes_sent, self.resend_bytes),  
        #     print 'time:(%s|%s)' % (str(rtt_current)[:8], str(relative_time)[:8]),
        #     print 'rate:(%r)' % current_rate
        return new_blocks_counter > 0

    def send_ack(self):
        if not self.consumer:
            return False
        ack_data = ''.join(map(lambda bid: struct.pack('i', bid), self.blocks_to_ack))
        ack_len = len(ack_data)
        self.producer.do_send_ack(self.stream_id, self.consumer, ack_data)
        self.bytes_in_acks += ack_len 
        # self.output_blocks_acks += list(self.blocks_to_ack)
        self.output_acks_counter += 1
        # if lg.is_debug(18):
        #     relative_time = time.time() - self.creation_time
        #     current_rate = 0.0
        #     if relative_time > 0.0: 
        #         current_rate = self.bytes_in / relative_time
        #     print 'send ack %d|%d|%d' % (len(self.blocks_to_ack), len(self.output_blocks_acks), self.output_acks_counter), 
        #     print 'bytes:(%d|%d)' % (self.bytes_in, self.bytes_in_acks),
        #     print 'time:(%r)' % relative_time,
        #     print 'rate:(%r)' % current_rate
        self.blocks_to_ack = []
        self.last_ack_moment = time.time()
        return ack_len > 0

    def resend(self, need_to_ack=False):
        if not self.consumer:
            # print 'stop resending, consumer is None'
            return
        self.resend_counter += 1
        rtt_current = self.rtt_avarage / self.rtt_acks_counter
        rtt_current = max(min(rtt_current, RTT_MAX_LIMIT), RTT_MIN_LIMIT)
        activity = False
        relative_time = time.time() - self.creation_time
        if len(self.blocks_to_ack) > 0:
            is_ack_timed_out = (time.time() - self.last_ack_moment) > rtt_current
            if need_to_ack or is_ack_timed_out:
                activity = activity or self.send_ack()
            if relative_time - self.last_block_received_time > RTT_MAX_LIMIT * 2.0:
                self.producer.on_timeout_receiving(self.stream_id)
        if len(self.output_blocks) > 0:
            last_ack_dt = relative_time - self.last_ack_received_time
            if last_ack_dt > RTT_MAX_LIMIT:
                self.input_acks_timeouts_counter += 1
                if self.input_acks_timeouts_counter < MAX_ACK_TIMEOUTS:
                    latest_block_id = self.output_blocks_ids[0]
                    self.output_blocks[latest_block_id][1] = -1
                    lg.out(18, 'RESEND ONE %d %d' % (self.stream_id, latest_block_id))
                else:
                    lg.out(18, 'rtt=%r, last ack at %r' % (
                        rtt_current, self.last_ack_received_time))
                    lg.out(18, ','.join(map(lambda bid: '%d:%d' % (bid, self.output_blocks[bid][1]), self.output_blocks_ids)))
                    if self.last_ack_received_time == 0:
                        self.consumer.error_message = 'sending failed'
                    else:
                        self.consumer.error_message = 'timeout sending'
                    self.consumer.status = 'failed'
                    self.consumer.timeout = True
                    self.producer.on_timeout_sending(self.stream_id)
                    return
            activity = activity or self.send_blocks()
            # elif last_ack_dt > rtt_current * 2.0:
            #     self.producer.do_send_data(self.stream_id, self.consumer, '')
            #     activity = True
        if activity:
            # print 'resend out:%s acks:%s' % (len(self.output_blocks.keys()), len(self.blocks_to_ack))
            self.resend_inactivity_counter = 0.0
        else:
            self.resend_inactivity_counter += 1.0
        next_resend = rtt_current * self.resend_inactivity_counter * 2.0
        if lg.is_debug(18) and self.resend_counter % 10 == 1 and self.producer:
            # DEBUG
            current_rate_in = 0.0
            current_rate_out = 0.0
            if relative_time > 0.0: 
                current_rate_in = self.bytes_in / relative_time
                current_rate_out = self.bytes_sent / relative_time
            try:
                rcv = self.consumer.bytes_received
            except:
                rcv = 0
            try:
                dlvr = self.consumer.bytes_delivered
            except:
                dlvr = 0
            s = ''
            s += '(%d:%d) ' % (len(self.output_blocks.keys()), len(self.blocks_to_ack))
            s += 'in:(%d|%d|%d|%d) ' % (self.input_blocks_counter, self.bytes_in, 
                                        rcv, self.bytes_in_acks)
            s += 'out:(%d|%d|%d|%d) ' % (self.output_blocks_counter, self.bytes_sent,
                                      dlvr, self.resend_bytes)
            s += 'rate:(%d|%d) ' % (int(current_rate_in), int(current_rate_out))  
            s += 'time:(%s|%s|%d|%d)' % (str(rtt_current)[:8], str(relative_time)[:6], 
                                          self.resend_counter, self.resend_inactivity_counter)
            lg.out(18, 'RESEND %d %s %s' % (
                self.stream_id, self.producer.session.peer_id, s))
        if self.resend_task is None:
            self.resend_task = reactor.callLater(next_resend, self.resend) 
            return
        if self.resend_task.called:
            self.resend_task = reactor.callLater(next_resend, self.resend)
            return
        if self.resend_task.cancelled:
            self.resend_task = None
            return
            
    def stop_resending(self):
        if self.resend_task:
            if self.resend_task.active():
                self.resend_task.cancel()
                self.resend_task = None
        
#------------------------------------------------------------------------------ 

class BufferOverflow(Exception):
    pass

