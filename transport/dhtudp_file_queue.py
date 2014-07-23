
"""
..module:: dhtudp_stream
"""

import os
import time
import cStringIO
import struct

from twisted.internet import reactor

from logs import lg

from lib import bpio
from lib import udp
from lib import tmpfile
from lib import settings
from lib import misc

import dhtudp_interface
import dhtudp_session
import dhtudp_stream

#------------------------------------------------------------------------------ 

MAX_SIMULTANEOUS_OUTGOING_FILES = 1
MIN_PROCESS_SESSIONS_DELAY = 0.1
MAX_PROCESS_SESSIONS_DELAY = 1

#------------------------------------------------------------------------------ 

_ProcessSessionsDelay = 0.01
_ProcessSessionsTask = None

#------------------------------------------------------------------------------ 

def start_process_sessions():
    global _ProcessSessionsTask
    if not _ProcessSessionsTask:
        reactor.callLater(0, process_sessions)
    
def stop_process_sessions():
    global _ProcessSessionsTask
    if _ProcessSessionsTask:
        if not _ProcessSessionsTask.cancelled:
            _ProcessSessionsTask.cancel()
            _ProcessSessionsTask = None
    
def process_sessions():
    global _ProcessSessionsDelay
    global _ProcessSessionsTask
    
    has_activity = False
    
    for s in dhtudp_session.sessions().values():
        has_timeouts = s.stream.timeout_incoming_files()
        has_sends = s.stream.process_sending_data()    
        has_outbox = s.stream.process_outbox_queue()
        if has_timeouts or has_sends or has_outbox:
            has_activity = True
    
    _ProcessSessionsDelay = misc.LoopAttenuation(
        _ProcessSessionsDelay, has_activity, 
        MIN_PROCESS_SESSIONS_DELAY, 
        MAX_PROCESS_SESSIONS_DELAY,)
    
    # attenuation
    _ProcessSessionsTask = reactor.callLater(_ProcessSessionsDelay, process_sessions)

#------------------------------------------------------------------------------ 

class FileQueue:
    def __init__(self, session):
        self.session = session
        self.inboxFiles = {}
        self.outboxFiles = {}
        self.receivedFiles = {}
        self.outboxQueue = []
        self.stream = dhtudp_stream.UDPStream()
        
    def close(self):
        file_ids_to_remove = self.inboxFiles.keys()
        for file_id in file_ids_to_remove:
            self.inbox_file_done(file_id, 'failed', 'session has been closed')
        file_ids_to_remove = self.outboxFiles.keys()
        for file_id in file_ids_to_remove:
            self.outbox_file_done(file_id, 'failed', 'session has been closed')
        self.receivedFiles.clear()
        self.sliding_window.clear()

    def process_outbox_queue(self):
        has_reads = False
        while len(self.outboxQueue) > 0 and len(self.outboxFiles) < MAX_SIMULTANEOUS_OUTGOING_FILES:        
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
            self.create_outbox_file(filename, filesize, description, result_defer, single)
        return has_reads

    def process_sending_data(self):
        has_sends = False
        # has_timedout = False
        failed_ids = []
        for file_id in self.outboxFiles.keys():
            outfile = self.outboxFiles[file_id]
            if outfile.send():
                has_sends = True
            if outfile.is_timed_out():
                if outfile.timeout == 0:
                    failed_ids.append((file_id, 'canceled'))
                else:
                    failed_ids.append((file_id, 'timeout'))
                    # has_timedout = True
        for file_id, why in failed_ids:
            self.outbox_file_done(file_id, 'failed', why)
        del failed_ids
        # if has_timedout:
            # if some packets we currently sending is timed out
            # all other in the outbox will fail too - so erase all.
            # self.clearOutboxQueue()
        has_sends = has_sends or self.check_sliding_window()
        return has_sends


    def erase_old_file_ids(self):
        if len(self.receivedFiles) > 10:
            file_ids = self.receivedFiles.keys()
            cur_tm = time.time()
            for file_id in file_ids:
                if cur_tm - self.receivedFiles[file_id] > 60 * 20:
                    del self.receivedFiles[file_id]
            del file_ids 

    def timeout_incoming_files(self):
        for file_id in self.inboxFiles.keys():
            if self.inboxFiles[file_id].is_timed_out():
                lg.out(6, 'dhtudp_stream.data_received WARNING inbox file is timed out, close session %s' % str(self.session))
                self.session.automat('shutdown')
                return True
        return False

    def append_outbox_file(self, filename, description='', result_defer=None, single=False):
        self.outboxQueue.append((filename, description, result_defer, single))
        
    def insert_outbox_file(self, filename, description='', result_defer=None, single=False):
        self.outboxQueue.insert(0, (filename, description, result_defer, single))    
        
    def send_data(self, command, payload):
        return udp.send_command(self.session.node.listen_port, command, 
                                payload, self.session.peer_address)

    def create_inbox_file(self, file_id, num_blocks):
        infile = InboxFile(self, file_id, num_blocks)
        # TODO: need to transfer files size also
        d = dhtudp_interface.interface_register_file_receiving(
            self.session.peer_id, self.session.peer_idurl, infile.filename, 0)
        d.addCallback(self.on_inbox_file_registered, file_id)
        d.addErrback(self.on_inbox_file_register_failed, file_id)
        infile.registration = d
        self.inboxFiles[file_id] = infile

    def on_inbox_file_registered(self, response, file_id):
        try:
            transfer_id = int(response)
        except:
            transfer_id = None
        self.inboxFiles[file_id].transfer_id = transfer_id
        self.inboxFiles[file_id].registration = None
        if self.inboxFiles[file_id].is_done():
            infile = self.inboxFiles[file_id]
            self.inboxFiles[file_id].build()
#                dhtudp_interface.interface_unregister_file_receiving(
#                    infile.transfer_id, 'finished', infile.get_bytes_received())
            self.report_inbox_file(infile.transfer_id, 'finished', infile.get_bytes_received())
            self.close_inbox_file(file_id)
            self.receivedFiles[file_id] = time.time()
            self.erase_old_file_ids()
            
    def on_inbox_file_register_failed(self, err, file_id):
        lg.out(2, 'dhtudp_stream.on_inbox_file_register_failed ERROR failed to register, file_id=%s' % (str(file_id)))
        lg.out(6, 'dhtudp_stream.on_inbox_file_register_failed close session %s' % self.session)
        self.session.automat('shutdown')

    def create_outbox_file(self, filename, filesize, description, result_defer, single):
        file_id = int(str(int(time.time() * 100.0))[4:])
        outfile = OutboxFile(self, filename, file_id, filesize, description, result_defer, single)
        outfile.read_blocks()
        if not single:
            d = dhtudp_interface.interface_register_file_sending(
                self.session.peer_id, self.session.peer_idurl, filename, description)
            d.addCallback(self.on_outbox_file_registered, file_id)
            d.addErrback(self.on_outbox_file_register_failed, file_id)
            outfile.registration = d
        self.outboxFiles[file_id] = outfile
        # self.registeringOutboxFiles[file_id] = d

    def on_outbox_file_registered(self, response, file_id):
        try:
            transfer_id = int(response)
        except:
            transfer_id = None
        self.outboxFiles[file_id].transfer_id = transfer_id
        self.outboxFiles[file_id].registration = None
        if self.outboxFiles[file_id].is_done():
            outfile = self.outboxFiles[file_id]
            # dhtudp_interface.interface_unregister_file_sending(outfile.transfer_id, 'finished', outfile.size)
            self.report_outbox_file(outfile.transfer_id, 'finished', outfile.size)
            self.close_outbox_file(file_id)

    def on_outbox_file_register_failed(self, err, file_id):
        lg.out(2, 'dhtudp_stream.on_outbox_file_register_failed ERROR failed to register, file_id=%s :\n%s' % (str(file_id), str(err)))
        lg.out(6, 'dhtudp_stream.on_outbox_file_register_failed close session %s' % self.session)
        self.session.automat('shutdown')

    def inbox_file_done(self, file_id, status, error_message=None):
        try:
            infile = self.inboxFiles[file_id]
        except:
            lg.exc()
            return
        if infile.registration:
            return
        if infile.transfer_id:
#            dhtudp_interface.interface_unregister_file_receiving(
#                infile.transfer_id, status, infile.get_bytes_received(), error_message)
            self.report_inbox_file(infile.transfer_id, status, infile.get_bytes_received(), error_message)
        else:
            lg.out(6, 'dhtudp_stream.file_received WARNING transfer_id is None, file_id=%s' % (str(file_id)))
        self.close_inbox_file(file_id)
        self.receivedFiles[file_id] = time.time()
        self.erase_old_file_ids()

    def outbox_file_done(self, file_id, status, error_message=None):
        lg.out(18, 'dhtudp_stream.outbox_file_done %s %s because %s' % (file_id, status, error_message))
        try:
            outfile = self.outboxFiles[file_id]
        except:
            lg.exc()
            return
        if outfile.result_defer:
            outfile.result_defer.callback((outfile, status, error_message))
            outfile.result_defer = None
        if outfile.registration:
            return
        if outfile.transfer_id:
            # dhtudp_interface.interface_unregister_file_sending(outfile.transfer_id, 'finished', outfile.size)
            self.report_outbox_file(outfile.transfer_id, 'finished', outfile.size)
        self.close_outbox_file(file_id)

    def failed_outbox_queue_item(self, filename, description='', error_message='', result_defer=None, single=False):
        lg.out(18, 'dhtudp_stream.failed_outbox_queue_item %s because %s' % (filename, error_message))
        if not single:
            dhtudp_interface.interface_cancelled_file_sending(
                self.session.peer_id, filename, 0, description, error_message)
        if result_defer:
            result_defer.callback(((filename, description), 'failed', error_message))
        
    def close_outbox_file(self, file_id):
        self.outboxFiles[file_id].close()
        del self.outboxFiles[file_id]

    def close_inbox_file(self, file_id):
        self.inboxFiles[file_id].close()   
        del self.inboxFiles[file_id]   

    def report_outbox_file(self, transfer_id, status, bytes_sent, error_message=None):    
        lg.out(18, 'dhtudp_stream.report_outbox_file %s %s %d' % (transfer_id, status, bytes_sent))
        dhtudp_interface.interface_unregister_file_sending(
            transfer_id, status, bytes_sent, error_message)

    def report_inbox_file(self, transfer_id, status, bytes_received, error_message=None):
        lg.out(18, 'dhtudp_stream.report_inbox_file %s %s %d' % (transfer_id, status, bytes_received))
        dhtudp_interface.interface_unregister_file_receiving(
            transfer_id, status, bytes_received, error_message)

#------------------------------------------------------------------------------ 

class InboxFile():
    def __init__(self, stream, file_id, num_blocks):
        self.transfer_id = None
        self.registration = None
        self.stream = stream
        self.file_id = file_id
        self.fd, self.filename = tmpfile.make("dhtudp-in")
        self.num_blocks = num_blocks
        self.blocks = {}
        self.bytes_received = 0
        self.bytes_extra = 0
        self.started = time.time()
        self.last_block_time = time.time()
        self.block_timeout = 0
        # lg.out(6, 'dhtudp_stream.InboxFile {%s} [%d] from %s' % (self.transfer_id, self.file_id, str(self.stream.remote_address)))

    def close(self):
        try:
            if self.bytes_received > 0 and self.bytes_extra > self.bytes_received * 0.1:
                lg.out(10, 'dhtudp_stream.InboxFile.close WARNING %s%% garbage traffic from %s' % (
                    str(self.bytes_extra/float(self.bytes_received)), self.stream.session.peer_address))
        except:
            lg.exc()
        try:
            os.close(self.fd)
        except:
            lg.exc()

    def get_bytes_received(self):
        return self.bytes_received

    def input_block(self, block_id, block_data):
        if block_id not in self.blocks:
            self.blocks[block_id] = block_data
            self.bytes_received += len(block_data)
        else:
            self.bytes_extra += len(block_data)
        self.last_block_time = time.time()
        self.block_timeout = max( int(len(block_data)/settings.SendingSpeedLimit()), 3) 
    
    def build(self):
        for block_id in xrange(len(self.blocks)):
            os.write(self.fd, self.blocks[block_id])
        # os.close(self.fd)
        # lg.out(10, 'transport_udp_server.InboxFile.build [%s] file_id=%d, blocks=%d' % (
        #     os.path.basename(self.filename), self.file_id, self.num_blocks))

    def is_done(self):
        return len(self.blocks) == self.num_blocks

    def is_timed_out(self):
        if self.block_timeout == 0:
            return False
        return time.time() - self.last_block_time > self.block_timeout


class OutboxFile():
    def __init__(self, stream, filename, file_id, filesize, description='', 
                 result_defer=None, single=False):
        self.transfer_id = None
        self.registration = None
        self.stream = stream
        self.file_id = file_id
        self.filename = filename
        self.size = filesize
        self.description = description
        self.result_defer = result_defer
        self.single = single
        self.blocks = {} 
        self.num_blocks = 0
        self.bytes_sent = 0
        self.bytes_out = 0
        self.block_id = -1
        self.blocks_timeouts = 0
        self.blocks_counter = 0
        self.started = time.time()
        self.timeout = max( int(self.size/settings.SendingSpeedLimit()), 5)

    def close(self):
        pass

    def cancel(self):
        lg.out(6, 'dhtudp_stream.OutboxFile.cancel timeout=%d' % self.timeout)
        self.timeout = 0

    def get_bytes_sent(self):
        return self.bytes_sent 

    def report_block(self, block_id):
        if not self.blocks.has_key(block_id):
            lg.out(10, 'dhtudp_stream.report_block WARNING unknown block_id from %s: [%d]' % (str(self.stream.session.peer_address), block_id))
            return
        self.bytes_sent += len(self.blocks[block_id])
        del self.blocks[block_id]
        # sys.stdout.write('%d <<<\n' % block_id)

    def check_blocks_timeouts(self):
        if self.blocks_counter < 10:
            return 0
        ratio = float(self.blocks_timeouts) / float(self.blocks_counter)
        self.blocks_counter = 0
        self.blocks_timeouts = 0
        return ratio
        
    def send_block(self, block_id):
        # global _SendControlFunc
        if not self.blocks.has_key(block_id):
            lg.out(8, 'dhtudp_stream.send_block WARNING block_id=%d not found, file_id=%s, transfer_id=%s, blocks: %d' % (
                block_id, self.file_id, str(self.transfer_id), len(self.blocks) ))
            return False
        data = self.blocks[block_id]
        # if _SendControlFunc is not None:
        #     more_bytes = _SendControlFunc(self.stream.last_bytes_sent, len(data))
        #     if more_bytes < len(data):
        #         return False
        self.stream.last_bytes_sent = len(data)
        datagram = ''
        datagram += struct.pack('i', self.file_id)
        datagram += struct.pack('i', block_id)
        datagram += struct.pack('i', self.num_blocks)
        datagram += struct.pack('i', len(data))
        datagram += data
        self.bytes_out += len(data)
        return self.stream.send_data(udp.CMD_DATA, datagram)

    def read_blocks(self):
        fin = open(self.filename, 'rb')
        block_id = 0
        while True:
            block_data = fin.read(BLOCK_SIZE)
            if block_data == '':
                break
            self.blocks[block_id] = block_data
            block_id += 1  
        fin.close()
        self.num_blocks = block_id
        self.block_id = 0     
    
    def is_done(self):  
        return len(self.blocks) == 0
      
    def is_timed_out(self):
        return time.time() - self.started > self.timeout

