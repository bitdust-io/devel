
"""
..module:: file_queue
"""

import os
import time
import struct
import cStringIO
import random 

from twisted.internet import reactor

from logs import lg

from lib import udp
from lib import tmpfile
from lib import settings
from lib import misc

import udp_interface
import udp_session
import udp_stream

#------------------------------------------------------------------------------ 

MAX_SIMULTANEOUS_STREAMS = 4

#------------------------------------------------------------------------------ 

class FileQueue:
    def __init__(self, session):
        self.session = session
        self.streams = {}
        self.outboxFiles = {}
        self.inboxFiles = {}
        self.outboxQueue = []
        
    def make_unique_stream_id(self):
        return int(str(random.randint(100,999))+str(int(time.time() * 100.0))[7:])
        
    def close(self):
        for stream in self.streams.values():
            stream.close()
        self.streams.clear()
        self.outboxFiles.clear()
        self.inboxFiles.clear()
        for filename, description, result_defer, single in self.outboxQueue:
            self.failed_outbox_queue_item(filename, description, 'session was closed', result_defer, single)
        self.outboxQueue = []

    def do_send_data(self, stream_id, outfile, output):
        newoutput = ''.join((
            struct.pack('i', stream_id),
            struct.pack('i', outfile.size),
            output))
        return self.session.send_packet(udp.CMD_DATA, newoutput)
    
    def do_send_ack(self, stream_id, infile, ack_data):
        newoutput = ''.join((
            struct.pack('i', stream_id),
            ack_data))
        return self.session.send_packet(udp.CMD_ACK, newoutput)


    def append_outbox_file(self, filename, description='', result_defer=None, single=False):
        self.outboxQueue.append((filename, description, result_defer, single))
        
    def insert_outbox_file(self, filename, description='', result_defer=None, single=False):
        self.outboxQueue.insert(0, (filename, description, result_defer, single))    
        
    def process_outbox_queue(self):
        has_reads = False
        while len(self.outboxQueue) > 0 and len(self.streams) < MAX_SIMULTANEOUS_STREAMS:        
            filename, description, result_defer, single = self.outboxQueue.pop(0)
            has_reads = True
            # we have a queue of files to be sent
            # somehow file may be removed before we start sending it
            # so I check it here and skip not existed files
            if not os.path.isfile(filename):
                self.failed_outbox_queue_item(filename, description, 'file not exist', result_defer, single)
                continue
            try:
                filesize = os.path.getsize(filename)
            except:
                self.failed_outbox_queue_item(filename, description, 'can not get file size', result_defer, single)
                continue
            self.start_outbox_file(filename, filesize, description, result_defer, single)
        return has_reads
    
    def process_outbox_files(self):
        has_sends = False
        for outfile in self.outboxFiles.values():
            has_sends = has_sends or outfile.process()
        return has_sends

    def start_outbox_file(self, filename, filesize, description, result_defer, single):
        stream_id = self.make_unique_stream_id()
        outfile = OutboxFile(self, stream_id, filename, filesize, description, result_defer, single)
        if not single:
            d = udp_interface.interface_register_file_sending(
                self.session.peer_id, self.session.peer_idurl, filename, description)
            d.addCallback(self.on_outbox_file_registered, stream_id)
            d.addErrback(self.on_outbox_file_register_failed, stream_id)
            outfile.registration = d
        self.outboxFiles[stream_id] = outfile
        self.streams[stream_id] = udp_stream.UDPStream(
            stream_id, outfile, 
            self.do_send_data, self.do_send_ack, 
            self.on_received_raw_data, self.on_sent_raw_data)
        
    def start_inbox_file(self, stream_id, data_size):
        infile = InboxFile(self, stream_id, data_size)
        d = udp_interface.interface_register_file_receiving(
            self.session.peer_id, self.session.peer_idurl, infile.filename, 0)
        d.addCallback(self.on_inbox_file_registered, stream_id)
        d.addErrback(self.on_inbox_file_register_failed, stream_id)
        infile.registration = d
        self.inboxFiles[stream_id] = infile
        self.streams[stream_id] = udp_stream.UDPStream(
            stream_id, infile,  
            self.do_send_data, self.do_send_ack, 
            self.on_received_raw_data, self.on_sent_raw_data)

    def inbox_file_done(self, infile, status, error_message=None):
        stream_id = infile.stream_id
        if infile.registration:
            return
        if infile.transfer_id:
            self.report_inbox_file(infile.transfer_id, status, infile.get_bytes_received(), error_message)
        else:
            lg.out(6, 'udp_stream.file_received WARNING transfer_id is None, stream_id=%d' % stream_id)
        self.close_inbox_file(stream_id)
        # self.receivedFiles[stream_id] = time.time()
        # self.erase_old_stream_ids()

    def outbox_file_done(self, outfile, status, error_message=None):
        stream_id = outfile.stream_id
        lg.out(18, 'udp_stream.outbox_file_done %s %s because %s' % (stream_id, status, error_message))
        if outfile.result_defer:
            outfile.result_defer.callback((outfile, status, error_message))
            outfile.result_defer = None
        if outfile.registration:
            return
        if outfile.transfer_id:
            self.report_outbox_file(outfile.transfer_id, 'finished', outfile.size)
        self.close_outbox_file(stream_id)

    def failed_outbox_queue_item(self, filename, description='', error_message='', result_defer=None, single=False):
        lg.out(18, 'udp_stream.failed_outbox_queue_item %s because %s' % (filename, error_message))
        if not single:
            udp_interface.interface_cancelled_file_sending(
                self.session.peer_id, filename, 0, description, error_message)
        if result_defer:
            result_defer.callback(((filename, description), 'failed', error_message))
        
    def close_outbox_file(self, stream_id):
        self.outboxFiles[stream_id].close()
        del self.outboxFiles[stream_id]

    def close_inbox_file(self, stream_id):
        self.inboxFiles[stream_id].close()   
        del self.inboxFiles[stream_id]   

    def report_outbox_file(self, transfer_id, status, bytes_sent, error_message=None):    
        lg.out(18, 'udp_stream.report_outbox_file %s %s %d' % (transfer_id, status, bytes_sent))
        udp_interface.interface_unregister_file_sending(
            transfer_id, status, bytes_sent, error_message)

    def report_inbox_file(self, transfer_id, status, bytes_received, error_message=None):
        lg.out(18, 'udp_stream.report_inbox_file %s %s %d' % (transfer_id, status, bytes_received))
        udp_interface.interface_unregister_file_receiving(
            transfer_id, status, bytes_received, error_message)
           
    def on_received_raw_data(self, infile, newdata):
        infile.process(newdata)
        if infile.is_done():
            self.inbox_file_done(infile, 'finished')
            return True
        return False

    def on_sent_raw_data(self, outfile, bytes_delivered):
        outfile.count_size(bytes_delivered)
        if outfile.is_done():
            self.outbox_file_done(outfile, 'finished')
            return True
        return False

    def on_received_data_packet(self, payload):
        inp = cStringIO.StringIO(payload)
        try:
            stream_id = struct.unpack('i', inp.read(4))[0]
            data_size = struct.unpack('i', inp.read(4))[0]
        except:
            inp.close()
            lg.exc()
            return
        if len(self.streams) >= 2 * MAX_SIMULTANEOUS_STREAMS:
            # too many incoming streams, seems remote side is cheating - drop that session!
            # TODO : need to add some protection - keep a list of bad guys?  
            inp.close()
            lg.out(6, 'udp_stream.data_received WARNING too many incoming files, close session %s' % str(self.session))
            self.session.automat('shutdown') 
            return
        if stream_id not in self.streams.keys():
            self.start_inbox_file(stream_id, data_size)
        try:
            self.streams[stream_id].block_received(inp)
        except:
            lg.exc()
        inp.close()
        
    def on_received_ack_packet(self, payload):
        inp = cStringIO.StringIO(payload)
        try:
            stream_id = struct.unpack('i', inp.read(4))[0]
        except:
            inp.close()
            lg.exc()
            # self.session.automat('shutdown') 
            return
        if stream_id not in self.streams.keys():
            inp.close()
            # if not self.receivedFiles.has_key(stream_id):
            lg.out(8, 'udp_file_queue.ack_received WARNING unknown stream_id=%d in ACK packet from %s' % (
                stream_id, self.session.peer_address))
            # self.session.automat('shutdown') 
            return
        try:
            self.streams[stream_id].ack_received(inp)
        except:
            lg.exc()
            self.session.automat('shutdown') 
        inp.close()

    def on_inbox_file_registered(self, response, stream_id):
        try:
            transfer_id = int(response)
        except:
            transfer_id = None
        infile = self.inboxFiles[stream_id]
        infile.transfer_id = transfer_id
        infile.registration = None
        if infile.is_done():
            self.report_inbox_file(infile.transfer_id, 'finished', infile.bytes_received)
            self.close_inbox_file(stream_id)
            # self.receivedFiles[stream_id] = time.time()
            # self.erase_old_stream_ids()
            del infile
            
    def on_inbox_file_register_failed(self, err, stream_id):
        lg.out(2, 'udp_stream.on_inbox_file_register_failed ERROR failed to register, stream_id=%s' % (str(stream_id)))
        lg.out(6, 'udp_stream.on_inbox_file_register_failed close session %s' % self.session)
        self.session.automat('shutdown')

    def on_outbox_file_registered(self, response, stream_id):
        try:
            transfer_id = int(response)
        except:
            transfer_id = None
        self.outboxFiles[stream_id].transfer_id = transfer_id
        self.outboxFiles[stream_id].registration = None
        if self.outboxFiles[stream_id].is_done():
            outfile = self.outboxFiles[stream_id]
            self.report_outbox_file(outfile.transfer_id, 'finished', outfile.size)
            self.close_outbox_file(stream_id)

    def on_outbox_file_register_failed(self, err, stream_id):
        lg.out(2, 'udp_stream.on_outbox_file_register_failed ERROR failed to register, stream_id=%s :\n%s' % (str(stream_id), str(err)))
        lg.out(6, 'udp_stream.on_outbox_file_register_failed close session %s' % self.session)
        self.session.automat('shutdown')
            
     
#------------------------------------------------------------------------------ 

class InboxFile():
    def __init__(self, queue, stream_id, size):
        self.transfer_id = None
        self.registration = None
        self.queue = queue
        self.stream_id = stream_id
        self.fd, self.filename = tmpfile.make("udp-in")
        self.size = size
        self.bytes_received = 0
        self.started = time.time()
        lg.out(6, 'udp_file_queue.InboxFile.__init__ {%s} [%d] from %s' % (
            os.path.basename(self.filename), self.stream_id, str(self.queue.session.peer_address)))
        
    def __del__(self):
        lg.out(6, 'udp_file_queue.InboxFile.__del__ {%s} [%d]' % (os.path.basename(self.filename), self.stream_id,))

    def process(self, newdata):
        os.write(self.fd, newdata)
        self.bytes_received += len(newdata)
        
    def is_done(self):
        return self.bytes_received == self.size

#------------------------------------------------------------------------------ 


class OutboxFile():
    def __init__(self, queue, stream_id, filename, size, description='', 
                 result_defer=None, single=False):
        self.transfer_id = None
        self.registration = None
        self.queue = queue
        self.stream = None
        self.stream_id = stream_id
        self.filename = filename
        self.size = size
        self.description = description
        self.result_defer = result_defer
        self.single = single
        self.bytes_sent = 0
        self.bytes_delivered = 0
        self.buffer = ''
        self.eof = False
        self.started = time.time()
        self.timeout = max( int(self.size/settings.SendingSpeedLimit()), 5)
        self.fileobj = open(self.filename, 'rb')
        lg.out(6, 'udp_file_queue.OutboxFile {%s} [%d] to %s' % (
            os.path.basename(self.filename), self.stream_id, str(self.queue.session.peer_address)))

    def __del__(self):
        lg.out(6, 'udp_file_queue.OutboxFile.__del__ {%s} [%d]' % (os.path.basename(self.filename), self.stream_id,))

    def is_done(self):
        return self.size == self.bytes_delivered and self.eof
    
    def count_size(self, more_bytes_delivered):
        self.bytes_delivered += more_bytes_delivered
    
    def process(self):
        if self.eof:
            return False
        has_sends = False
        while True:
            if not self.buffer:
                self.buffer = self.fileobj.read(udp_stream.BUFFER_SIZE)
                if not self.buffer:
                    print 'EOF!!!', self.filename
                    self.eof = True
                    break
            try:
                self.stream.write(self.buffer)
            except udp_stream.BufferOverflow:
                break
            self.bytes_sent += len(self.buffer)
            self.buffer = ''
            has_sends = True
        return has_sends
          





#    def erase_old_stream_ids(self):
#        if len(self.receivedFiles) > 10:
#            stream_ids = self.receivedFiles.keys()
#            cur_tm = time.time()
#            for stream_id in stream_ids:
#                if cur_tm - self.receivedFiles[stream_id] > 60 * 20:
#                    del self.receivedFiles[stream_id]
#            del stream_ids 

#    def timeout_incoming_files(self):
#        for stream_id in self.inboxFiles.keys():
#            if self.inboxFiles[stream_id].is_timed_out():
#                lg.out(6, 'udp_stream.data_received WARNING inbox file is timed out, close session %s' % str(self.session))
#                self.session.automat('shutdown')
#                return True
#        return False



#------------------------------------------------------------------------------ 




#    def close(self):
#        try:
#            if self.bytes_received > 0 and self.bytes_extra > self.bytes_received * 0.1:
#                lg.out(10, 'udp_stream.InboxFile.close WARNING %s%% garbage traffic from %s' % (
#                    str(self.bytes_extra/float(self.bytes_received)), self.stream.session.peer_address))
#        except:
#            lg.exc()
#        try:
#            os.close(self.fd)
#        except:
#            lg.exc()
#
#    def get_bytes_received(self):
#        return self.bytes_received
#
#    def input_block(self, block_id, block_data):
#        if block_id not in self.blocks:
#            self.blocks[block_id] = block_data
#            self.bytes_received += len(block_data)
#        else:
#            self.bytes_extra += len(block_data)
#        self.last_block_time = time.time()
#        self.block_timeout = max( int(len(block_data)/settings.SendingSpeedLimit()), 3) 
#    
#    def build(self):
#        for block_id in xrange(len(self.blocks)):
#            os.write(self.fd, self.blocks[block_id])
#        # os.close(self.fd)
#        # lg.out(10, 'transport_udp_server.InboxFile.build [%s] stream_id=%d, blocks=%d' % (
#        #     os.path.basename(self.filename), self.stream_id, self.num_blocks))
#
#    def is_done(self):
#        return len(self.blocks) == self.num_blocks
#
#    def is_timed_out(self):
#        if self.block_timeout == 0:
#            return False
#        return time.time() - self.last_block_time > self.block_timeout

  

#    def close(self):
#        pass
#
#    def cancel(self):
#        lg.out(6, 'udp_stream.OutboxFile.cancel timeout=%d' % self.timeout)
#        self.timeout = 0
#
#    def get_bytes_sent(self):
#        return self.bytes_sent 
#
#    def report_block(self, block_id):
#        if not self.blocks.has_key(block_id):
#            lg.out(10, 'udp_stream.report_block WARNING unknown block_id from %s: [%d]' % (str(self.stream.session.peer_address), block_id))
#            return
#        self.bytes_sent += len(self.blocks[block_id])
#        del self.blocks[block_id]
#        # sys.stdout.write('%d <<<\n' % block_id)
#
#    def check_blocks_timeouts(self):
#        if self.blocks_counter < 10:
#            return 0
#        ratio = float(self.blocks_timeouts) / float(self.blocks_counter)
#        self.blocks_counter = 0
#        self.blocks_timeouts = 0
#        return ratio
#        
#    def send_block(self, block_id):
#        # global _SendControlFunc
#        if not self.blocks.has_key(block_id):
#            lg.out(8, 'udp_stream.send_block WARNING block_id=%d not found, stream_id=%s, transfer_id=%s, blocks: %d' % (
#                block_id, self.stream_id, str(self.transfer_id), len(self.blocks) ))
#            return False
#        data = self.blocks[block_id]
#        # if _SendControlFunc is not None:
#        #     more_bytes = _SendControlFunc(self.stream.last_bytes_sent, len(data))
#        #     if more_bytes < len(data):
#        #         return False
#        self.stream.last_bytes_sent = len(data)
#        datagram = ''
#        datagram += struct.pack('i', self.stream_id)
#        datagram += struct.pack('i', block_id)
#        datagram += struct.pack('i', self.num_blocks)
#        datagram += struct.pack('i', len(data))
#        datagram += data
#        self.bytes_out += len(data)
#        return self.stream.send_data(udp.CMD_DATA, datagram)
#
#    def read_blocks(self):
#        fin = open(self.filename, 'rb')
#        block_id = 0
#        while True:
#            block_data = fin.read(BLOCK_SIZE)
#            if block_data == '':
#                break
#            self.blocks[block_id] = block_data
#            block_id += 1  
#        fin.close()
#        self.num_blocks = block_id
#        self.block_id = 0     
#    
#    def is_done(self):  
#        return len(self.blocks) == 0
#      
#    def is_timed_out(self):
#        return time.time() - self.started > self.timeout

