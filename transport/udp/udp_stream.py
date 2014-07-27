
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

BLOCKS_PER_ACK = 16

MAX_BUFFER_SIZE = 64*1024
BUFFER_SIZE = BLOCK_SIZE * 8 # int(float(BLOCKS_PER_ACK)*0.8) - 20% extra space in ack packet

RTT_MIN_LIMIT = 0.001
RTT_MAX_LIMIT = 1.0

#------------------------------------------------------------------------------ 

class UDPStream():
    def __init__(self, stream_id, consumer,
                 send_data_packet_func,
                 send_ack_packet_func, 
                 received_raw_data_callback,
                 sent_raw_data_callback):
        self.stream_id = stream_id
        self.consumer = consumer
        self.consumer.stream = self
        self.send_data_packet_func = send_data_packet_func
        self.send_ack_packet_func = send_ack_packet_func
        self.received_raw_data_callback = received_raw_data_callback
        self.sent_raw_data_callback = sent_raw_data_callback
        self.output_buffer_size = 0
        self.output_blocks = {}
        self.output_blocks_acks = []
        self.output_block_id = 0
        self.input_blocks = {}
        self.input_block_id = 0
        self.blocks_to_ack = set()
        self.bytes_in = 0
        self.bytes_sent = 0
        self.bytes_acked = 0
        self.resend_bytes = 0
        self.last_ack_moment = 0
        self.last_ack_rtt = RTT_MIN_LIMIT
        self.resend_task = None
        self.resend_inactivity_counter = 0
        self.creation_time = time.time() 
        lg.out(18, 'udp_stream.__init__ %d' % self.stream_id)
        
    def __del__(self):
        lg.out(18, 'udp_stream.__del__ %d' % self.stream_id)
        
    def close(self):
        print 'udp_stream.close %d in:%d out:%d acked:%d resend:%d' % (
            self.stream_id, self.bytes_in, self.bytes_sent, self.bytes_acked, self.resend_bytes)
        self.consumer.stream = None
        self.consumer = None
        self.send_data_packet_func = None
        self.send_ack_packet_func = None
        self.received_raw_data_callback = None
        self.sent_raw_data_callback = None
        
    def block_received(self, inpt):
        if self.consumer:
            block_id = struct.unpack('i', inpt.read(4))[0]
            data = inpt.read()
            self.input_blocks[block_id] = data
            self.bytes_in += len(data)
            self.blocks_to_ack.add(block_id)
            eof_state = False
            print 'block', block_id, self.bytes_in, block_id % BLOCKS_PER_ACK
            if block_id == self.input_block_id + 1:
                newdata = []
                print 'newdata',
                while True:
                    next_block_id = self.input_block_id + 1
                    try:
                        newdata.append(self.input_blocks.pop(next_block_id))
                    except:
                        break
                    self.input_block_id = next_block_id
                    print next_block_id,
                newdata = ''.join(newdata)
                if self.consumer:
                    eof_state = self.received_raw_data_callback(self.consumer, newdata)
                print 'received %d bytes, eof=%r' % (len(newdata), eof_state)
            # want to send the first ack asap
            if time.time() - self.last_ack_moment > RTT_MAX_LIMIT \
                or block_id % BLOCKS_PER_ACK == 1 \
                or eof_state:
                    # self.send_ack()
                    self.resend()
    
    def ack_received(self, inpt):
        if self.consumer:
            acked_progress = 0
            while True:
                raw_bytes = inpt.read(4)
                if not raw_bytes:
                    break
                block_id = struct.unpack('i', raw_bytes)[0]
                try:
                    outblock = self.output_blocks.pop(block_id)
                except KeyError:
                    # lg.out(10, 'udp_stream.ack_received WARNING block %d not found' % (block_id))
                    continue
                acked_progress += 1
                block_size = len(outblock[0])
                self.output_buffer_size -= block_size 
                self.bytes_acked += block_size
                relative_time = time.time() - self.creation_time
                self.last_ack_rtt = relative_time - outblock[1]
                print 'ack', block_id, self.last_ack_rtt, self.bytes_acked
                self.sent_raw_data_callback(self.consumer, block_size)
            print 'ack progress:', acked_progress, 'blocks,   more:', len(self.output_blocks.keys())
#            self.output_blocks_not_acked.clear()
            self.resend()

    def write(self, data):
        if self.output_buffer_size + len(data) > MAX_BUFFER_SIZE:
            raise BufferOverflow('buffer size is %d' % self.output_buffer_size)
        print 'write', len(data)
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
            for block_id in self.output_blocks.keys():
                piece, time_sent = self.output_blocks[block_id]
                data_size = len(piece)
                if time_sent >= 0:
                    dt = relative_time - time_sent 
                    if dt > RTT_MAX_LIMIT:
                        self.resend_bytes += data_size
                        print 're -',
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
                import random
                if random.randint(0, 9) >= 1:
                    # 10 % percent lost
                    self.send_data_packet_func(self.stream_id, self.consumer, output)
                # DEBUG
                # self.send_data_packet_func(self.stream_id, self.consumer, output)
                self.bytes_sent += data_size
                # self.output_blocks_not_acked.add(block_id)
                print 'send block', block_id, self.bytes_sent, self.bytes_acked, self.resend_bytes

    def send_ack(self):
        ack_data = ''.join(map(lambda bid: struct.pack('i', bid), self.blocks_to_ack))
        self.send_ack_packet_func(self.stream_id, self.consumer, ack_data)
        self.output_blocks_acks += list(self.blocks_to_ack)
        print 'send ack', len(self.output_blocks_acks), self.blocks_to_ack
        self.blocks_to_ack.clear()
        self.last_ack_moment = time.time()

    def resend(self):
        print 'resend out:%s acks:%s' % (len(self.output_blocks.keys()), len(self.blocks_to_ack))
        activitiy = len(self.output_blocks.keys()) + len(self.blocks_to_ack)
        if activitiy > 0:
            self.resend_inactivity_counter = 0
        else:
            self.resend_inactivity_counter += 1
        next_resend = min(max(self.last_ack_rtt, RTT_MIN_LIMIT), RTT_MAX_LIMIT)
        if self.resend_inactivity_counter > 50:
            next_resend *= 100.0
        if len(self.blocks_to_ack) > 0:
            if time.time() - self.last_ack_moment > RTT_MAX_LIMIT:
                self.send_ack()
        if len(self.output_blocks):        
            self.send_blocks()
        if self.resend_task is None:
            self.resend_task = reactor.callLater(next_resend, self.resend) 
            return
        if self.resend_task.called:
            self.resend_task = reactor.callLater(next_resend, self.resend)
            return
        if self.resend_task.cancelled:
            self.resend_task = None
        
#------------------------------------------------------------------------------ 

class BufferOverflow(Exception):
    pass

