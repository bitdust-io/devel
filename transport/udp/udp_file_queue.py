
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

    def cb_send_data(self, stream_id, outfile, output):
        newoutput = ''.join((
            struct.pack('i', stream_id),
            struct.pack('i', outfile.size),
            output))
        return self.session.send_packet(udp.CMD_DATA, newoutput)
    
    def cb_send_ack(self, ack_data):
        return self.session.send_packet(udp.CMD_ACK, ack_data)
    
    def cb_received_raw_data(self, infile, newdata):
        return infile.process(newdata)

    def cb_received_ack_packet(self, outfile, bytes_delivered):
        if outfile.size == bytes_delivered and outfile.eof:
            pass

    def data_packet_received(self, payload):
        inp = cStringIO.StringIO(payload)
        try:
            stream_id = struct.unpack('i', inp.read(4))[0]
            data_size = struct.unpack('i', inp.read(4))[0]
        except:
            inp.close()
            lg.exc()
            return
        if len(self.streams) >= 2 * MAX_SIMULTANEOUS_STREAMS:
            # too many incoming streams, seems remote guy is cheating - drop that session!
            inp.close()
            lg.out(6, 'udp_stream.data_received WARNING too many incoming files, close session %s' % str(self.session))
            self.session.automat('shutdown') 
            return
        if stream_id not in self.streams.keys():
            infile = InboxFile(self, stream_id, data_size)
            self.inboxFiles[stream_id] = infile
            self.streams[stream_id] = udp_stream.UDPStream(
                stream_id, infile,  
                self.cb_send_data, self.cb_send_ack, 
                self.cb_received_raw_data, self.cb_received_ack_packet)
        try:
            self.streams[stream_id].block_received(inp)
        except:
            lg.exc()
        inp.close()
        
    def ack_packet_received(self, payload):
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
            # if not self.receivedFiles.has_key(file_id):
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
            stream_id = self.make_unique_stream_id()
            outfile = OutboxFile(self, stream_id, filename, filesize, description, result_defer, single)
            self.outboxFiles[stream_id] = outfile
            self.streams[stream_id] = udp_stream.UDPStream(
                stream_id, outfile, 
                self.cb_send_data, self.cb_send_ack, 
                self.cb_received_raw_data, self.cb_received_ack_packet)
#            if not single:
#                d = udp_interface.interface_register_file_sending(
#                    self.session.peer_id, self.session.peer_idurl, filename, description)
#                d.addCallback(self.on_outbox_file_registered, stream_id)
#                d.addErrback(self.on_outbox_file_register_failed, stream_id)
#                self.streams[stream_id].registration = d
        return has_reads
    
    def process_outbox_files(self):
        has_sends = False
        for outfile in self.outboxFiles.values():
            has_sends = has_sends or outfile.process()
        return has_sends
            
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
        print 'infile.process', self.bytes_received, self.size
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
        self.buffer = ''
        self.eof = False
        self.started = time.time()
        self.timeout = max( int(self.size/settings.SendingSpeedLimit()), 5)
        self.fileobj = open(self.filename, 'rb')
        lg.out(6, 'udp_file_queue.OutboxFile {%s} [%d] to %s' % (
            os.path.basename(self.filename), self.stream_id, str(self.queue.session.peer_address)))

    def __del__(self):
        lg.out(6, 'udp_file_queue.OutboxFile.__del__ {%s} [%d]' % (os.path.basename(self.filename), self.stream_id,))

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
          




#    def process_streams(self):
#        for stream_id, stream in self.streams.items():
#            
#            stream.process()
            

#    def process_sending_data(self):
#        has_sends = False
#        # has_timedout = False
#        failed_ids = []
#        for file_id in self.outboxFiles.keys():
#            outfile = self.outboxFiles[file_id]
#            if outfile.send():
#                has_sends = True
#            if outfile.is_timed_out():
#                if outfile.timeout == 0:
#                    failed_ids.append((file_id, 'canceled'))
#                else:
#                    failed_ids.append((file_id, 'timeout'))
#                    # has_timedout = True
#        for file_id, why in failed_ids:
#            self.outbox_file_done(file_id, 'failed', why)
#        del failed_ids
#        # if has_timedout:
#            # if some packets we currently sending is timed out
#            # all other in the outbox will fail too - so erase all.
#            # self.clearOutboxQueue()
#        has_sends = has_sends or self.check_sliding_window()
#        return has_sends


#    def erase_old_file_ids(self):
#        if len(self.receivedFiles) > 10:
#            file_ids = self.receivedFiles.keys()
#            cur_tm = time.time()
#            for file_id in file_ids:
#                if cur_tm - self.receivedFiles[file_id] > 60 * 20:
#                    del self.receivedFiles[file_id]
#            del file_ids 

#    def timeout_incoming_files(self):
#        for file_id in self.inboxFiles.keys():
#            if self.inboxFiles[file_id].is_timed_out():
#                lg.out(6, 'udp_stream.data_received WARNING inbox file is timed out, close session %s' % str(self.session))
#                self.session.automat('shutdown')
#                return True
#        return False

#    def on_inbox_file_registered(self, response, file_id):
#        try:
#            transfer_id = int(response)
#        except:
#            transfer_id = None
#        self.inboxFiles[file_id].transfer_id = transfer_id
#        self.inboxFiles[file_id].registration = None
#        if self.inboxFiles[file_id].is_done():
#            infile = self.inboxFiles[file_id]
#            self.inboxFiles[file_id].build()
##                udp_interface.interface_unregister_file_receiving(
##                    infile.transfer_id, 'finished', infile.get_bytes_received())
#            self.report_inbox_file(infile.transfer_id, 'finished', infile.get_bytes_received())
#            self.close_inbox_file(file_id)
#            self.receivedFiles[file_id] = time.time()
#            self.erase_old_file_ids()
            
#    def on_inbox_file_register_failed(self, err, file_id):
#        lg.out(2, 'udp_stream.on_inbox_file_register_failed ERROR failed to register, file_id=%s' % (str(file_id)))
#        lg.out(6, 'udp_stream.on_inbox_file_register_failed close session %s' % self.session)
#        self.session.automat('shutdown')

#    def create_outbox_file(self, filename, filesize, description, result_defer, single):
#        file_id = int(str(int(time.time() * 100.0))[4:])
#        outfile = OutboxFile(self, filename, file_id, filesize, description, result_defer, single)
#        outfile.read_blocks()
#        if not single:
#            d = udp_interface.interface_register_file_sending(
#                self.session.peer_id, self.session.peer_idurl, filename, description)
#            d.addCallback(self.on_outbox_file_registered, file_id)
#            d.addErrback(self.on_outbox_file_register_failed, file_id)
#            outfile.registration = d
#        self.outboxFiles[file_id] = outfile
#        # self.registeringOutboxFiles[file_id] = d

#    def on_outbox_file_registered(self, response, file_id):
#        try:
#            transfer_id = int(response)
#        except:
#            transfer_id = None
#        self.outboxFiles[file_id].transfer_id = transfer_id
#        self.outboxFiles[file_id].registration = None
#        if self.outboxFiles[file_id].is_done():
#            outfile = self.outboxFiles[file_id]
#            # udp_interface.interface_unregister_file_sending(outfile.transfer_id, 'finished', outfile.size)
#            self.report_outbox_file(outfile.transfer_id, 'finished', outfile.size)
#            self.close_outbox_file(file_id)

#    def on_outbox_file_register_failed(self, err, file_id):
#        lg.out(2, 'udp_stream.on_outbox_file_register_failed ERROR failed to register, file_id=%s :\n%s' % (str(file_id), str(err)))
#        lg.out(6, 'udp_stream.on_outbox_file_register_failed close session %s' % self.session)
#        self.session.automat('shutdown')

#    def inbox_file_done(self, file_id, status, error_message=None):
#        try:
#            infile = self.inboxFiles[file_id]
#        except:
#            lg.exc()
#            return
#        if infile.registration:
#            return
#        if infile.transfer_id:
##            udp_interface.interface_unregister_file_receiving(
##                infile.transfer_id, status, infile.get_bytes_received(), error_message)
#            self.report_inbox_file(infile.transfer_id, status, infile.get_bytes_received(), error_message)
#        else:
#            lg.out(6, 'udp_stream.file_received WARNING transfer_id is None, file_id=%s' % (str(file_id)))
#        self.close_inbox_file(file_id)
#        self.receivedFiles[file_id] = time.time()
#        self.erase_old_file_ids()

#    def outbox_file_done(self, file_id, status, error_message=None):
#        lg.out(18, 'udp_stream.outbox_file_done %s %s because %s' % (file_id, status, error_message))
#        try:
#            outfile = self.outboxFiles[file_id]
#        except:
#            lg.exc()
#            return
#        if outfile.result_defer:
#            outfile.result_defer.callback((outfile, status, error_message))
#            outfile.result_defer = None
#        if outfile.registration:
#            return
#        if outfile.transfer_id:
#            # udp_interface.interface_unregister_file_sending(outfile.transfer_id, 'finished', outfile.size)
#            self.report_outbox_file(outfile.transfer_id, 'finished', outfile.size)
#        self.close_outbox_file(file_id)

#    def failed_outbox_queue_item(self, filename, description='', error_message='', result_defer=None, single=False):
#        lg.out(18, 'udp_stream.failed_outbox_queue_item %s because %s' % (filename, error_message))
#        if not single:
#            udp_interface.interface_cancelled_file_sending(
#                self.session.peer_id, filename, 0, description, error_message)
#        if result_defer:
#            result_defer.callback(((filename, description), 'failed', error_message))
        
#    def close_outbox_file(self, file_id):
#        self.outboxFiles[file_id].close()
#        del self.outboxFiles[file_id]

#    def close_inbox_file(self, file_id):
#        self.inboxFiles[file_id].close()   
#        del self.inboxFiles[file_id]   

#    def report_outbox_file(self, transfer_id, status, bytes_sent, error_message=None):    
#        lg.out(18, 'udp_stream.report_outbox_file %s %s %d' % (transfer_id, status, bytes_sent))
#        udp_interface.interface_unregister_file_sending(
#            transfer_id, status, bytes_sent, error_message)

#    def report_inbox_file(self, transfer_id, status, bytes_received, error_message=None):
#        lg.out(18, 'udp_stream.report_inbox_file %s %s %d' % (transfer_id, status, bytes_received))
#        udp_interface.interface_unregister_file_receiving(
#            transfer_id, status, bytes_received, error_message)

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
#        # lg.out(10, 'transport_udp_server.InboxFile.build [%s] file_id=%d, blocks=%d' % (
#        #     os.path.basename(self.filename), self.file_id, self.num_blocks))
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
#            lg.out(8, 'udp_stream.send_block WARNING block_id=%d not found, file_id=%s, transfer_id=%s, blocks: %d' % (
#                block_id, self.file_id, str(self.transfer_id), len(self.blocks) ))
#            return False
#        data = self.blocks[block_id]
#        # if _SendControlFunc is not None:
#        #     more_bytes = _SendControlFunc(self.stream.last_bytes_sent, len(data))
#        #     if more_bytes < len(data):
#        #         return False
#        self.stream.last_bytes_sent = len(data)
#        datagram = ''
#        datagram += struct.pack('i', self.file_id)
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

