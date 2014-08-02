

"""
..module:: tcp_stream
"""


import os
import time
import cStringIO
import struct

from twisted.internet import reactor
from twisted.protocols import basic

from logs import lg

from lib import tmpfile
from lib import settings
from lib import misc

import tcp_node
import tcp_connection
import tcp_interface

#------------------------------------------------------------------------------ 

MIN_PROCESS_STREAMS_DELAY = 0.1
MAX_PROCESS_STREAMS_DELAY = 1
MAX_SIMULTANEOUS_OUTGOING_FILES = 1

#------------------------------------------------------------------------------ 

_ProcessStreamsDelay = 0.01
_ProcessStreamsTask = None

#------------------------------------------------------------------------------ 

def start_process_streams():
    reactor.callLater(0, process_streams)
    return True
    
def stop_process_streams():
    global _ProcessStreamsTask
    if _ProcessStreamsTask:
        if _ProcessStreamsTask.active():
            _ProcessStreamsTask.cancel()
            _ProcessStreamsTask = None
            return True
    return False
    
def process_streams():
    global _ProcessStreamsDelay
    global _ProcessStreamsTask
    
    has_activity = False
    
    for connections in tcp_node.opened_connections().values():
        for connection in connections:
            has_timeouts = False # connection.stream.timeout_incoming_files()
            has_sends = False # connection.stream.process_sending_data()    
            has_outbox = connection.process_outbox_queue()
            if has_timeouts or has_sends or has_outbox:
                has_activity = True
    
    _ProcessStreamsDelay = misc.LoopAttenuation(
        _ProcessStreamsDelay, has_activity, 
        MIN_PROCESS_STREAMS_DELAY, 
        MAX_PROCESS_STREAMS_DELAY,)
    
    # attenuation
    _ProcessStreamsTask = reactor.callLater(_ProcessStreamsDelay, process_streams)

#------------------------------------------------------------------------------ 

class TCPFileStream():
    def __init__(self, connection):
        self.connection = connection
        self.outboxFiles = {}
        self.inboxFiles = {}
        
    def close(self):
        """
        """ 
        self.connection = None   

    def abort_files(self, reason='connection closed'):      
        file_ids_to_remove = self.inboxFiles.keys()
        for file_id in file_ids_to_remove:
            # self.send_data(tcp_connection.CMD_ABORT, struct.pack('i', file_id)+' '+reason)
            self.inbox_file_done(file_id, 'failed', reason)
        file_ids_to_remove = self.outboxFiles.keys()
        for file_id in file_ids_to_remove:
            self.send_data(tcp_connection.CMD_ABORT, struct.pack('i', file_id)+' '+reason)
            self.outbox_file_done(file_id, 'failed', reason)
        
    def data_received(self, payload):
        """
        """
        inp = cStringIO.StringIO(payload)
        try:
            file_id = struct.unpack('i', inp.read(4))[0]
            file_size = struct.unpack('i', inp.read(4))[0]
        except:
            inp.close()
            lg.exc()
            return
        # lg.out(6, 'data_received %s' % str(( file_id, file_size)))
        inp_data = inp.read()
        inp.close()
        if not self.inboxFiles.has_key(file_id):
            if len(self.inboxFiles) >= 2 * MAX_SIMULTANEOUS_OUTGOING_FILES:
                # too many incoming files, seems remote guy is cheating - drop that session!
                lg.out(6, 'tcp_stream.data_received WARNING too many incoming files, close connection %s' % str(self.connection))
                self.connection.automat('disconnect') 
                return
            self.create_inbox_file(file_id, file_size)
        self.inboxFiles[file_id].input_data(inp_data) 
        if self.inboxFiles[file_id].is_done():
            self.send_data(tcp_connection.CMD_OK, struct.pack('i', file_id))
            self.inbox_file_done(file_id, 'finished')
            
    def ok_received(self, payload):
        inp = cStringIO.StringIO(payload)
        try:
            file_id = struct.unpack('i', inp.read(4))[0]
        except:
            inp.close()
            lg.exc()
            return
        inp.close()
        self.outboxFiles[file_id].ok_received = True
        if not self.outboxFiles[file_id].registration:
            self.outbox_file_done(file_id, 'finished')
        
    def abort_received(self, payload):
        inp = cStringIO.StringIO(payload)
        try:
            file_id = struct.unpack('i', inp.read(4))[0]
        except:
            inp.close()
            lg.exc()
            return
        reason = inp.read()
        inp.close()
        self.inbox_file_done(file_id, 'failed', reason)
        
    def send_data(self, command, payload):
        return self.connection.sendData(command, payload)
        
    def create_inbox_file(self, file_id, file_size):
        infile = InboxFile(self, file_id, file_size)
        d = tcp_interface.interface_register_file_receiving(
            self.connection.getAddress(), self.connection.peer_idurl, infile.filename)
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
            self.close_inbox_file(file_id)
            # self.receivedFiles[file_id] = time.time()
            # self.erase_old_file_ids()
            self.report_inbox_file(infile.transfer_id, 'finished', infile.get_bytes_received())
#                tcp_interface.interface_unregister_file_receiving(
#                    infile.transfer_id, 'finished', infile.get_bytes_received())
            
    def on_inbox_file_register_failed(self, err, file_id):
        lg.out(2, 'tcp_stream.on_inbox_file_register_failed ERROR failed to register, file_id=%s err:\n%s' % (str(file_id), str(err)))
        lg.out(6, 'tcp_stream.on_inbox_file_register_failed close session %s' % self.session)
        self.connection.automat('disconnect')
              
    def create_outbox_file(self, filename, filesize, description, result_defer, single):
        file_id = int(str(int(time.time() * 100.0))[4:])
        outfile = OutboxFile(self, filename, file_id, filesize, description, result_defer, single)
        # outfile.read_blocks()
        if not single:
            d = tcp_interface.interface_register_file_sending(
                self.connection.getAddress(), self.connection.peer_idurl, filename, description)
            d.addCallback(self.on_outbox_file_registered, file_id)
            d.addErrback(self.on_outbox_file_register_failed, file_id)
            outfile.registration = d
        self.outboxFiles[file_id] = outfile
        outfile.start()
      
    def on_outbox_file_registered(self, response, file_id):
        try:
            transfer_id = int(response)
        except:
            transfer_id = None
        self.outboxFiles[file_id].transfer_id = transfer_id
        self.outboxFiles[file_id].registration = None
        if self.outboxFiles[file_id].is_done():
            self.outbox_file_done(file_id, 'finished')

    def on_outbox_file_register_failed(self, err, file_id):
        lg.out(2, 'tcp_stream.on_outbox_file_register_failed ERROR failed to register, file_id=%s :\n%s' % (str(file_id), str(err)))
        lg.out(6, 'tcp_stream.on_outbox_file_register_failed close session %s' % self.connection)
        self.connection.automat('disconnect')
        
    def close_outbox_file(self, file_id):
        self.outboxFiles[file_id].close()
        del self.outboxFiles[file_id]

    def close_inbox_file(self, file_id):
        self.inboxFiles[file_id].close()   
        del self.inboxFiles[file_id]   
        
    def report_outbox_file(self, transfer_id, status, bytes_sent, error_message=None):    
        lg.out(18, 'tcp_stream.report_outbox_file %s %s %d' % (transfer_id, status, bytes_sent))
        tcp_interface.interface_unregister_file_sending(
            transfer_id, status, bytes_sent, error_message)

    def report_inbox_file(self, transfer_id, status, bytes_received, error_message=None):
        # lg.out(18, 'tcp_stream.report_inbox_file %s %s %d' % (transfer_id, status, bytes_received))
        tcp_interface.interface_unregister_file_receiving(
            transfer_id, status, bytes_received, error_message)
        
    def inbox_file_done(self, file_id, status, error_message=None):
        try:
            infile = self.inboxFiles[file_id]
        except:
            lg.exc()
            return
        if infile.registration:
            return
        self.close_inbox_file(file_id)
        if infile.transfer_id:
            self.report_inbox_file(infile.transfer_id, status, infile.get_bytes_received(), error_message)
        else:
            lg.out(6, 'tcp_stream.inbox_file_done WARNING transfer_id is None, file_id=%s' % (str(file_id)))
        del infile
        # self.receivedFiles[file_id] = time.time()
        
    def outbox_file_done(self, file_id, status, error_message=None):
        """
        """ 
        # lg.out(18, 'tcp_stream.outbox_file_done %s %s %s' % (file_id, status, error_message))
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
        self.close_outbox_file(file_id)
        if outfile.transfer_id:
            self.report_outbox_file(outfile.transfer_id, status, outfile.get_bytes_sent(), error_message)
        # else:
        #     lg.out(6, 'tcp_stream.outbox_file_done WARNING transfer_id is None, file_id=%s' % (str(file_id)))
        if outfile.single:
            lg.out(18, 'tcp_stream.outbox_file_done close single connection %s' % str(self.connection))
            self.connection.automat('disconnect') 
        del outfile

#------------------------------------------------------------------------------ 

class InboxFile():
    def __init__(self, stream, file_id, file_size):
        self.transfer_id = None
        self.registration = None
        self.stream = stream
        self.file_id = file_id
        self.file_size = file_size
        self.fd, self.filename = tmpfile.make("tcp-in")
        self.bytes_received = 0
        self.started = time.time()
        self.last_block_time = time.time()
        self.timeout = max(int(self.file_size/settings.SendingSpeedLimit()), 3)
        # lg.out(6, 'tcp_stream.InboxFile {%s} [%d] from %s' % (self.transfer_id, self.file_id, str(self.stream.remote_address)))

    def close(self):
        try:
            os.close(self.fd)
        except:
            lg.exc()

    def get_bytes_received(self):
        return self.bytes_received

    def input_data(self, data):
        os.write(self.fd, data)
        self.bytes_received += len(data)
        self.last_block_time = time.time()
    
    def is_done(self):
        return self.bytes_received == self.file_size

    def is_timed_out(self):
        return time.time() - self.started > self.timeout 

#------------------------------------------------------------------------------ 

class OutboxFile():
    def __init__(self, stream, filename, file_id, filesize, description='', result_defer=None, single=False):
        self.transfer_id = None
        self.registration = None
        self.stream = stream
        self.file_id = file_id
        self.filename = filename
        self.size = filesize
        self.description = description
        self.single = single
        self.result_defer = result_defer
        self.ok_received = False
        self.bytes_sent = 0
        self.bytes_out = 0
        self.started = time.time()
        self.timeout = max(int(self.size/settings.SendingSpeedLimit()), 6)
        self.fin = open(self.filename, 'rb')
        self.sender = None

    def close(self):
        self.stop()
        try:
            self.fin.close()
        except:
            lg.exc()
        
    def start(self):
        self.sender = FileSender(self)
        d = self.sender.beginFileTransfer(self.fin, self.stream.connection.transport, self.sender.transform_data)
        d.addCallback(self.transfer_finished)
        d.addErrback(self.transfer_failed)
        
    def stop(self):
        if not self.sender:
            return
        if not self.sender.deferred:
            return
        if self.sender.deferred.called:
            return
        # self.sender.close()
        self.sender.stopProducing()
        # del self.sender
        # self.sender = None

    def cancel(self):
        lg.out(6, 'tcp_stream.OutboxFile.cancel timeout=%d' % self.timeout)
        self.stop()

    def get_bytes_sent(self):
        return self.bytes_sent 

    def is_done(self):  
        return self.get_bytes_sent() == self.size and self.ok_received
      
    def is_timed_out(self):
        return time.time() - self.started > self.timeout

    def transfer_finished(self, last_byte):
        if not self.sender:
            return
        self.sender.close()
        del self.sender
        self.sender = None
        if self.ok_received:
            self.stream.outbox_file_done(self.file_id, 'finished')
    
    def transfer_failed(self, err):
        lg.out(18, 'tcp_stream.transfer_failed:   %r' % (err))
        if not self.sender:
            return None
        self.sender.close()
        del self.sender
        self.sender = None
        try:
            e = err.getErrorMessage()
        except:
            e = str(err) 
        self.stream.outbox_file_done(self.file_id, 'failed', e)
        return None
        
#------------------------------------------------------------------------------ 

class FileSender(basic.FileSender):
    def __init__(self, parent):
        # global _RegisterTransferFunc
        # global _ByTransferID
        self.parent = parent
        
        
        # self.peer = self.protocol.remoteaddress # self.protocol.transport.getPeer()
        # self.transfer_id = _RegisterTransferFunc(
        #     'send', self.peer, self.getSentBytes, filename, sz, description)
        # _ByTransferID[self.transfer_id] = self.protocol
        # lg.out(14, 'transport_tcp.TCPFileSender.init length=%d transfer_id=%s' % (self.sz, self.transfer_id))

    # def __del__(self):
    #     lg.out(14, 'transport_tcp.TCPFileSender.del length=%d transfer_id=%s' % (self.sz, self.transfer_id))

    def close(self):
        self.parent = None

    def transform_data(self, data):
        # lg.out(24, 'transform_data')
        datalength = len(data)
        datagram = ''
        datagram += struct.pack('i', self.parent.file_id)
        datagram += struct.pack('i', self.parent.size)
        datagram += data
        self.parent.bytes_sent += datalength
        self.parent.stream.connection.total_bytes_sent += datalength
        return datagram

    def resumeProducing(self):
        chunk = ''
        if self.file:
            try:
                chunk = self.file.read(self.CHUNK_SIZE)
            except:
                self.file = None
                self.consumer.unregisterProducer()
                if self.deferred:
                    self.deferred.errback(self.lastSent)
                    self.deferred = None
                lg.exc()
        if not chunk:
            self.file = None
            self.consumer.unregisterProducer()
            if self.deferred:
                self.deferred.callback(self.lastSent)
                self.deferred = None
            return
        if self.transform:
            chunk = self.transform(chunk)
        # self.consumer.write(chunk)
        self.parent.stream.connection.sendData(tcp_connection.CMD_DATA, chunk)
        self.lastSent = chunk[-1:]
        
