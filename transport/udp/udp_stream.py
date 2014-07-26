
import time
import cStringIO
import struct

from logs import lg

from lib import udp

#------------------------------------------------------------------------------ 

UDP_DATAGRAM_SIZE = 508
BLOCK_SIZE = UDP_DATAGRAM_SIZE-20
BLOCK_RETRIES = 999999
MAX_WINDOW_SIZE = 32
MIN_WINDOW_SIZE = 1
MAX_ACK_TIME_OUT = 4.0
MIN_ACK_TIME_OUT = 0.5
MAX_TIMEOUTS_RATIO = 0.5
FINE_TIMEOUTS_RATIO = 0.0
MAX_BUFFER_SIZE = 64*1024
BUFFER_SIZE = BLOCK_SIZE * 8
BLOCKS_PER_ACK = 16

#------------------------------------------------------------------------------ 

class UDPStream():
    def __init__(self, stream_id, consumer,
                 send_data_packet_func,
                 send_ack_packet_func, 
                 received_raw_data_callback,
                 received_ack_allback):
        self.stream_id = stream_id
        self.consumer = consumer
        self.consumer.stream = self
        self.send_data_packet_func = send_data_packet_func
        self.send_ack_packet_func = send_ack_packet_func
        self.received_raw_data_callback = received_raw_data_callback
        self.received_ack_allback = received_ack_allback
        # self.ack_timeout = MIN_ACK_TIME_OUT
        self.output_buffer_size = 0
        self.output_blocks = {}
        self.output_block_id = 0
        self.input_blocks = {}
        self.input_block_id = 0
        self.blocks_to_ack = set()
        self.bytes_in = 0
        self.bytes_sent = 0
        self.bytes_acked = 0
        self.creation_time = time.time() 
        lg.out(18, 'udp_stream.__init__ %d' % self.stream_id)
        
    def __del__(self):
        lg.out(18, 'udp_stream.__del__ %d' % self.stream_id)
        
    def close(self):
        self.consumer.stream = None
        self.consumer = None
        self.send_data_packet_func = None
        self.send_ack_packet_func = None
        self.received_raw_data_callback = None
        self.received_ack_allback = None
        
    def block_received(self, inpt):
        block_id = struct.unpack('i', inpt.read(4))[0]
        data = inpt.read()
        self.input_blocks[block_id] = data
        self.bytes_in += len(data)
        self.blocks_to_ack.add(block_id)
        eof_state = False
        if block_id == self.input_block_id + 1:
            newdata = [] 
            while True:
                try:
                    newdata.append(self.input_blocks.pop(self.input_block_id + 1))
                except:
                    break
                self.input_block_id += 1
            newdata = ''.join(newdata)
            if self.consumer:
                eof_state = self.received_raw_data_callback(self.consumer, newdata)
        if self.consumer:
            if block_id % BLOCKS_PER_ACK == 0 or eof_state:
                ack_data = ''.join(map(lambda bid: struct.pack('i', bid), self.blocks_to_ack))
                self.send_ack_packet_func(ack_data)
    
    def ack_received(self, inpt):
        print 'ack_received'
        if self.consumer:
            has_progress = False
            while True:
                raw_bytes = inpt.read(4)
                if not raw_bytes:
                    break
                block_id = struct.unpack('i', raw_bytes)[0]
                try:
                    outblock = self.output_blocks.pop(block_id)
                except KeyError:
                    continue
                self.bytes_acked = len(outblock[0])
                block_rtt = time.time() - outblock[1]
                print block_id, block_rtt
                has_progress = True
            if has_progress:
                self.received_ack_allback(self.consumer, self.bytes_acked)

    def write(self, data):
        if self.output_buffer_size + len(data) > MAX_BUFFER_SIZE:
            raise BufferOverflow('buffer size is %d' % self.output_buffer_size)
        outp = cStringIO.StringIO(data)
        while True:
            piece = outp.read(BLOCK_SIZE)
            if not piece:
                break
            self.output_block_id += 1
            relative_time = (time.time() - self.creation_time)
            self.output_blocks[self.output_block_id] = (piece, relative_time,)
            self.output_buffer_size += len(piece)
        outp.close()
        self.send_blocks()
        
    def send_blocks(self):
        if self.consumer:
            for unique_id, block in self.output_blocks.items():
                data_size = len(block[0])
                output = ''.join((
                    struct.pack('i', unique_id),
                    block[0]))
                self.send_data_packet_func(self.stream_id, self.consumer, output)
                self.bytes_sent += data_size

#------------------------------------------------------------------------------ 

class BufferOverflow(Exception):
    pass

