
import time
import cStringIO
import struct

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

BLOCKS_PER_ACK = 8

MAX_BUFFER_SIZE = 64*1024
BUFFER_SIZE = BLOCK_SIZE * BLOCKS_PER_ACK # BLOCK_SIZE * int(float(BLOCKS_PER_ACK)*0.8) - 20% extra space in ack packet

RTT_MIN_LIMIT = 0.0001
RTT_MAX_LIMIT = 0.5

#------------------------------------------------------------------------------ 

class UDPStream():
    def __init__(self, stream_id, consumer, producer):
        self.stream_id = stream_id
        self.consumer = consumer
        self.producer = producer
        self.consumer.stream = self
        # self.send_data_packet_func = send_data_packet_func
        # self.send_ack_packet_func = send_ack_packet_func
        # self.received_raw_data_callback = received_raw_data_callback
        # self.sent_raw_data_callback = sent_raw_data_callback
        self.output_buffer_size = 0
        self.output_blocks = {}
        self.output_blocks_acks = []
        self.output_block_id = 0
        self.output_blocks_counter = 0
        self.input_blocks = {}
        self.input_block_id = 0
        self.blocks_to_ack = set()
        self.bytes_in = 0
        self.bytes_in_acks = 0
        self.bytes_sent = 0
        self.bytes_acked = 0
        self.resend_bytes = 0
        self.last_ack_moment = 0
        self.rtt_avarage = RTT_MIN_LIMIT
        self.rtt_acks_counter = 1.0
        self.resend_task = None
        self.resend_inactivity_counter = 0
        self.resend_counter = 0
        self.limit_send_bytes_per_sec = 1 * 125000 # 1 Mbps limit ~ 122 KB/s 
        self.creation_time = time.time() 
        lg.out(18, 'udp_stream.__init__ %d' % self.stream_id)
        
    def __del__(self):
        lg.out(18, 'udp_stream.__del__ %d' % self.stream_id)
        
    def close(self):
        print 'udp_stream.close %d in:%d out:%d acked:%d resend:%d' % (
            self.stream_id, self.bytes_in, self.bytes_sent, self.bytes_acked, self.resend_bytes)
        self.stop_resending()
        self.consumer.stream = None
        self.consumer = None
        self.producer = None
        self.blocks_to_ack.clear()
        self.output_blocks.clear()
        # self.send_data_packet_func = None
        # self.send_ack_packet_func = None
        # self.received_raw_data_callback = None
        # self.sent_raw_data_callback = None
        
    def block_received(self, inpt):
        if self.consumer:
            block_id = struct.unpack('i', inpt.read(4))[0]
            data = inpt.read()
            self.input_blocks[block_id] = data
            self.bytes_in += len(data)
            self.blocks_to_ack.add(block_id)
            eof_state = False
            # print 'block', block_id, self.bytes_in, block_id % BLOCKS_PER_ACK
            if block_id == self.input_block_id + 1:
                newdata = []
                # print 'newdata',
                while True:
                    next_block_id = self.input_block_id + 1
                    try:
                        newdata.append(self.input_blocks.pop(next_block_id))
                    except:
                        break
                    self.input_block_id = next_block_id
                    # print next_block_id,
                num_blocks = len(newdata)
                newdata = ''.join(newdata)
                eof_state = self.consumer.on_received_raw_data(newdata)
                # print 'received %d bytes in %d blocks, eof=%r' % (len(newdata), num_blocks, eof_state)
            # want to send the first ack asap
            if time.time() - self.last_ack_moment > RTT_MAX_LIMIT \
                or block_id % BLOCKS_PER_ACK == 1 \
                or eof_state:
                    # self.send_ack()
                    self.resend()
    
    def ack_received(self, inpt):
        if self.consumer:
            acks = []
            eof = False
            raw_bytes = ''
            while True:
                raw_bytes = inpt.read(4)
                if not raw_bytes:
                    break
                block_id = struct.unpack('i', raw_bytes)[0]
                acks.append(block_id)
                try:
                    outblock = self.output_blocks.pop(block_id)
                except KeyError:
                    # lg.out(10, 'udp_stream.ack_received WARNING block %d not found' % (block_id))
                    continue
                block_size = len(outblock[0])
                self.output_buffer_size -= block_size 
                self.bytes_acked += block_size
                relative_time = time.time() - self.creation_time
                last_ack_rtt = relative_time - outblock[1]
                self.rtt_avarage += last_ack_rtt
                self.rtt_acks_counter += 1.0
                if self.rtt_acks_counter > 1000:
                    self.rtt_acks_counter = 5.0
                    self.rtt_avarage = (self.rtt_avarage / 1000.0) * 5.0 
                self.consumer.on_sent_raw_data(block_size)
                eof = self.consumer and self.consumer.size == self.bytes_acked
            if len(acks) > 0:
                print 'ack blocks:(%d|%d)' % (len(acks), len(self.output_blocks.keys())) 
                self.resend()
                return
            print 'STOP IT NOW!!!!, ZERO ACK!!!! SEEMS FINE.!!!'
            self.stop_resending()
            sum_not_acked_blocks = sum(map(lambda block: len(block[0]), 
                                           self.output_blocks.values()))
            self.output_blocks.clear()
            self.output_buffer_size = 0                
            self.bytes_acked += sum_not_acked_blocks
            relative_time = time.time() - self.creation_time
            self.consumer.on_zero_ack(sum_not_acked_blocks)
            return            

    def write(self, data):
        if self.output_buffer_size + len(data) > MAX_BUFFER_SIZE:
            raise BufferOverflow('buffer size is %d' % self.output_buffer_size)
        # print 'write', len(data)
        outp = cStringIO.StringIO(data)
        while True:
            piece = outp.read(BLOCK_SIZE)
            if not piece:
                break
            self.output_block_id += 1
            self.output_blocks[self.output_block_id] = (piece, -1)
            self.output_buffer_size += len(piece)
        outp.close()
        self.resend()
        
    def send_blocks(self):
        if self.consumer:
            relative_time = time.time() - self.creation_time
            current_rate = self.limit_send_bytes_per_sec
            rtt_current = self.rtt_avarage / self.rtt_acks_counter
            if relative_time > 0.0: 
                current_rate = self.bytes_sent / relative_time
            if current_rate > self.limit_send_bytes_per_sec:
                return
            resend_time_limit = 2 * BLOCKS_PER_ACK * rtt_current
            new_blocks_counter = 0 
            for block_id in self.output_blocks.keys():
                piece, time_sent = self.output_blocks[block_id]
                data_size = len(piece)
                if time_sent >= 0:
                    dt = relative_time - time_sent
                    if dt > resend_time_limit:
                        self.resend_bytes += data_size
                        # print 're -'s,
                    else:
                        # print 'skip', block_id, dt, self.last_ack_rtt 
                        continue
                else:
                    pass
                    # print 'go', block_id
                time_sent = relative_time
                self.output_blocks[block_id] = (piece, time_sent)
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
            if new_blocks_counter > 0:
                print 'send blocks:(%d|%d|%d)' % (new_blocks_counter, len(self.output_blocks.keys()), self.output_blocks_counter), 
                print 'bytes:(%d|%d|%d)' % (self.bytes_acked, self.bytes_sent, self.resend_bytes),  
                print 'time:(%s|%s)' % (str(rtt_current)[:8], str(relative_time)[:8]),
                print 'rate:(%r)' % current_rate

    def send_ack(self):
        if self.consumer:
            ack_data = ''.join(map(lambda bid: struct.pack('i', bid), self.blocks_to_ack))
            self.producer.do_send_ack(self.stream_id, self.consumer, ack_data)
            self.bytes_in_acks += len(ack_data)
            self.output_blocks_acks += list(self.blocks_to_ack)
            relative_time = time.time() - self.creation_time
            current_rate = 0.0
            if relative_time > 0.0: 
                current_rate = self.bytes_in / relative_time
            print 'send ack blocks:(%d|%d)' % (len(self.blocks_to_ack), len(self.output_blocks_acks)), 
            print 'bytes:(%d|%d)' % (self.bytes_in, self.bytes_in_acks),
            print 'time:(%r)' % relative_time,
            print 'rate:(%r)' % current_rate
            self.blocks_to_ack.clear()
            self.last_ack_moment = time.time()

    def resend(self):
        self.resend_counter += 1
        if not self.consumer:
            print 'stop resending, consumer is None'
            return
        activitiy = len(self.output_blocks.keys()) # + len(self.blocks_to_ack)
        if activitiy > 0:
            # print 'resend out:%s acks:%s' % (len(self.output_blocks.keys()), len(self.blocks_to_ack))
            self.resend_inactivity_counter = 0
        else:
            self.resend_inactivity_counter += 1
        rtt_current = self.rtt_avarage / self.rtt_acks_counter
        next_resend = max(min(rtt_current, RTT_MAX_LIMIT), RTT_MIN_LIMIT)
        if len(self.blocks_to_ack) > 0:
            if time.time() - self.last_ack_moment > next_resend:
                self.send_ack()
        if len(self.output_blocks):        
            self.send_blocks()
#        if self.resend_inactivity_counter > 5:
#            # if self.resend_inactivity_counter % 10 == 1:
#            #     print 'drop resend out:%s acks:%s' % (
#            #         len(self.output_blocks.keys()), len(self.blocks_to_ack))
#            next_resend = RTT_MAX_LIMIT * 4.0
#        if self.resend_inactivity_counter > 50:
#            next_resend = RTT_MAX_LIMIT * 16.0
        if self.resend_counter % 500 == 1:
            print 'resend out:%d acks:%d' % (len(self.output_blocks.keys()), len(self.blocks_to_ack)),
            print 'rtt=%r, next=%r, iterations=%d' % (rtt_current, next_resend, self.resend_counter)
        next_resend *= self.resend_inactivity_counter
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

