

"""
.. module:: udp_session

BitPie.NET udp_session() Automat


EVENTS:
    * :red:`datagram-received`
    * :red:`init`
    * :red:`shutdown`
    * :red:`timer-10sec`
    * :red:`timer-1min`
    * :red:`timer-1sec`
    * :red:`timer-30sec`
        
"""

import os
import sys
import time

from twisted.internet import reactor

from logs import lg

from lib import misc
from lib import automat
from lib import udp

import udp_file_queue
import udp_interface

#------------------------------------------------------------------------------ 

_Debug = False
_DebugLevel = 18

#------------------------------------------------------------------------------ 

MIN_PROCESS_SESSIONS_DELAY = 0.001
MAX_PROCESS_SESSIONS_DELAY = 1.0
  
#------------------------------------------------------------------------------ 

_SessionsDict = {}
_SessionsDictByPeerAddress = {}
_SessionsDictByPeerID = {}
_KnownPeersDict = {}
_KnownUserIDsDict = {}
_PendingOutboxFiles = []
_ProcessSessionsTask = None
_ProcessSessionsDelay = MIN_PROCESS_SESSIONS_DELAY

#------------------------------------------------------------------------------ 

def sessions():
    """
    """
    global _SessionsDict
    return _SessionsDict


def sessions_by_peer_address():
    global _SessionsDictByPeerAddress
    return _SessionsDictByPeerAddress


def sessions_by_peer_id():
    global _SessionsDictByPeerID
    return _SessionsDictByPeerID


def pending_outbox_files():
    global _PendingOutboxFiles
    return _PendingOutboxFiles

#------------------------------------------------------------------------------ 

def create(node, peer_address, peer_id=None):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'udp_session.create peer_address=%s' % str(peer_address))
    s = UDPSession(node, peer_address, peer_id)
    sessions()[s.id] = s
    try:
        sessions_by_peer_address()[peer_address].append(s)
    except:
        sessions_by_peer_address()[peer_address] = [s,]
    if peer_id:
        try:
            sessions_by_peer_id()[peer_id].append(s)
        except:
            sessions_by_peer_id()[peer_id] = [s,]
    return s


def get(peer_address):
    """
    """
    for s in sessions_by_peer_address().get(peer_address, []):
        return s
    # for id, s in sessions().items():
    #     if s.peer_address == peer_address:
    #         return s 
    return None


def get_by_peer_id(peer_id):
    """
    """
    for s in sessions_by_peer_id().get(peer_id, []):
        return s
    # for id, s in sessions().items():
    #     if s.peer_id == peer_id:
    #         return s 
    return None


def close(peer_address):
    """
    """
    s = get(peer_address)
    if s is None:
        return False
    s.automat('shutdown')
    return True


def add_pending_outbox_file(filename, host, description='', result_defer=None, single=False):
    """
    """
    pending_outbox_files().append((filename, host, description, result_defer, single, time.time()))
    if _Debug:
        lg.out(_DebugLevel, 'udp_session.add_pending_outbox_file %s for %s : %s' % (
            os.path.basename(filename), host, description) )


def remove_pending_outbox_file(host, filename):
    """
    """
    ok = False
    i = 0
    while i < len(pending_outbox_files()):
        fn, hst, description, result_defer, single, tm = pending_outbox_files()[i] 
        if fn == filename and host == hst:
            if _Debug:
                lg.out(_DebugLevel, 'udp_interface.cancel_outbox_file removed pending %s for %s' % (os.path.basename(fn), hst))
            pending_outbox_files().pop(i)
            ok = True
        else:
            i += 1
    return ok


def report_and_remove_pending_outbox_files_to_host(remote_host, error_message):
    """
    """
    global _PendingOutboxFiles
    i = 0
    while i < len(_PendingOutboxFiles):
        filename, host, description, result_defer, single, tm = _PendingOutboxFiles[i]
        if host == remote_host:
            udp_interface.interface_cancelled_file_sending(
                remote_host, filename, 0, description, error_message)
            if result_defer:
                result_defer.callback(((filename, description), 'failed', error_message))
            _PendingOutboxFiles.pop(i)
        else:
            i += 1


def process_sessions():
    global _ProcessSessionsTask
    global _ProcessSessionsDelay
    has_activity = False
    for s in sessions().values():
        if not s.peer_id:
            continue
        if not s.file_queue:
            continue
        if s.state != 'CONNECTED':
            continue
        has_outbox = s.file_queue.process_outbox_queue()
        has_sends = s.file_queue.process_outbox_files()    
        if has_sends or has_outbox:
            has_activity = True
    if _ProcessSessionsTask is None or _ProcessSessionsTask.called:
        if has_activity:
            _ProcessSessionsTask = reactor.callLater(0, process_sessions)        
        else:
            _ProcessSessionsDelay = misc.LoopAttenuation(
                _ProcessSessionsDelay, has_activity, 
                MIN_PROCESS_SESSIONS_DELAY, MAX_PROCESS_SESSIONS_DELAY,)
            # attenuation
            _ProcessSessionsTask = reactor.callLater(_ProcessSessionsDelay, 
                                                     process_sessions)        


def stop_process_sessions():
    global _ProcessSessionsTask
    if _ProcessSessionsTask:
        if _ProcessSessionsTask.active():
            _ProcessSessionsTask.cancel()
        _ProcessSessionsTask = None

#------------------------------------------------------------------------------ 

class UDPSession(automat.Automat):
    """
    This class implements all the functionality of the ``udp_session()`` state machine.
    """
    
    fast = True

    timers = {
        'timer-1min': (60, ['CONNECTED']),
        'timer-1sec': (1.0, ['PING','GREETING']),
        'timer-30sec': (30.0, ['GREETING']),
        'timer-10sec': (10.0, ['PING','CONNECTED']),
        }

    MESSAGES = {
        'MSG_1': 'remote peer is not active',
        'MSG_2': 'greeting is timed out',
        'MSG_3': 'ping remote machine has failed',
        'MSG_4': 'session has been closed at startup',
        }
   
    def __init__(self, node, peer_address, peer_id=None):
        self.node = node
        self.peer_address = peer_address
        self.peer_id = peer_id
        self.peer_idurl = None
        self.file_queue = udp_file_queue.FileQueue(self) 
        name = 'udp_session[%s:%d]' % (self.peer_address[0], self.peer_address[1])
        automat.Automat.__init__(self, name, 'AT_STARTUP', 14)

    def msg(self, msgid, arg=None):
        return self.MESSAGES.get(msgid, '')

    def init(self):
        """
        """
        self.last_datagram_received_time = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.my_rtt_id = '0' # out
        self.peer_rtt_id = '0' # in
        self.rtts = {}
        self.min_rtt = None

    def send_packet(self, command, payload):
        self.bytes_sent += len(payload)
        return udp.send_command(self.node.listen_port, command, 
                                payload, self.peer_address)

    def A(self, event, arg):
        #---CONNECTED---
        if self.state == 'CONNECTED':
            if event == 'timer-10sec' :
                self.doAlive(arg)
            elif event == 'shutdown' or ( event == 'timer-1min' and not self.isSessionActive(arg) ) :
                self.state = 'CLOSED'
                self.doErrMsg(event,self.msg('MSG_1', arg))
                self.doClosePendingFiles(arg)
                self.doNotifyDisconnected(arg)
                self.doDestroyMe(arg)
            elif event == 'datagram-received' and self.isGreeting(arg) :
                self.doAcceptGreeting(arg)
                self.doFinishRTT(arg)
                self.doAlive(arg)
            elif event == 'datagram-received' and self.isPayloadData(arg) :
                self.doReceiveData(arg)
            elif event == 'datagram-received' and self.isPing(arg) :
                self.doAcceptPing(arg)
                self.doGreeting(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'PING'
                self.doInit(arg)
                self.doStartRTT(arg)
                self.doPing(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doErrMsg(event,self.msg('MSG_4', arg))
                self.doClosePendingFiles(arg)
                self.doNotifyDisconnected(arg)
                self.doDestroyMe(arg)
        #---PING---
        elif self.state == 'PING':
            if event == 'timer-1sec' :
                self.doStartRTT(arg)
                self.doPing(arg)
            elif event == 'datagram-received' and self.isGreeting(arg) :
                self.state = 'GREETING'
                self.doAcceptGreeting(arg)
                self.doFinishRTT(arg)
                self.doStartRTT(arg)
                self.doGreeting(arg)
            elif event == 'datagram-received' and self.isPing(arg) :
                self.state = 'GREETING'
                self.doAcceptPing(arg)
                self.doStartRTT(arg)
                self.doGreeting(arg)
            elif event == 'shutdown' or event == 'timer-10sec' :
                self.state = 'CLOSED'
                self.doErrMsg(event,self.msg('MSG_3', arg))
                self.doClosePendingFiles(arg)
                self.doNotifyDisconnected(arg)
                self.doDestroyMe(arg)
        #---GREETING---
        elif self.state == 'GREETING':
            if event == 'timer-1sec' :
                self.doStartRTT(arg)
                self.doGreeting(arg)
            elif event == 'shutdown' or event == 'timer-30sec' :
                self.state = 'CLOSED'
                self.doErrMsg(event,self.msg('MSG_2', arg))
                self.doClosePendingFiles(arg)
                self.doNotifyDisconnected(arg)
                self.doDestroyMe(arg)
            elif event == 'datagram-received' and self.isAlive(arg) :
                self.state = 'CONNECTED'
                self.doAcceptAlive(arg)
                self.doFinishAllRTTs(arg)
                self.doNotifyConnected(arg)
                self.doCheckPendingFiles(arg)
                self.doAlive(arg)
            elif event == 'datagram-received' and self.isPing(arg) :
                self.doAcceptPing(arg)
                self.doStartRTT(arg)
                self.doGreeting(arg)
            elif event == 'datagram-received' and self.isGreeting(arg) :
                self.doAcceptGreeting(arg)
                self.doFinishRTT(arg)
                self.doAlive(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isPayloadData(self, arg):
        """
        Condition method.
        """
        command = arg[0][0]
        return ( command == udp.CMD_DATA or command == udp.CMD_ACK )

    def isPing(self, arg):
        """
        Condition method.
        """
        command = arg[0][0]
        return ( command == udp.CMD_PING )

    def isGreeting(self, arg):
        """
        Condition method.
        """
        command = arg[0][0]
        return ( command == udp.CMD_GREETING )

    def isAlive(self, arg):
        """
        Condition method.
        """
        command = arg[0][0]
        return ( command == udp.CMD_ALIVE )
        
#    def isGreetingOrAlive(self, arg):
#        """
#        Condition method.
#        """
#        command = arg[0][0]
#        return ( command == udp.CMD_ALIVE or command == udp.CMD_GREETING)

    def isSessionActive(self, arg):
        """
        Condition method.
        """
        return time.time() - self.last_datagram_received_time < 60

    def doInit(self, arg):
        """
        Action method.
        """
        # self.listen_port, self.my_id, self.my_address = arg

    def doPing(self, arg):
        """
        Action method.
        """
#        if udp_stream._Debug:
#            if not (self.peer_address.count('37.18.255.42') or self.peer_address.count('37.18.255.38')):
#                return
        # rtt_id_out = self._rtt_start('PING')
        udp.send_command(self.node.listen_port, udp.CMD_PING, 
                         self.my_rtt_id, self.peer_address)
        # # print 'doPing', self.my_rtt_id
        self.my_rtt_id = '0'

    def doGreeting(self, arg):
        """
        Action method.
        """
        # rtt_id_out = self._rtt_start('GREETING')
        payload = "%s %s %s %s" % (
            str(self.node.my_id), str(self.node.my_idurl), 
            str(self.peer_rtt_id), str(self.my_rtt_id),)
        udp.send_command(self.node.listen_port, udp.CMD_GREETING, payload, self.peer_address)
        # print 'doGreeting', self.peer_rtt_id, self.my_rtt_id
        self.peer_rtt_id = '0'
        self.my_rtt_id = '0'
                
    def doAlive(self, arg):
        """
        Action method.
        """
        udp.send_command(self.node.listen_port, udp.CMD_ALIVE, self.peer_rtt_id, self.peer_address)
        # print 'doAlive', self.peer_rtt_id
        self.peer_rtt_id = '0'

    def doAcceptPing(self, arg):
        """
        Action method.
        """
        address, command, payload = self._dispatch_datagram(arg)
        self.peer_rtt_id = payload.strip()
        # print 'doAcceptPing', self.peer_rtt_id

    def doAcceptGreeting(self, arg):
        """
        Action method.
        """
        address, command, payload = self._dispatch_datagram(arg)
        parts = payload.split(' ')
        try:
            new_peer_id  = parts[0]
            new_peer_idurl  = parts[1]
            if len(parts) >= 4:
                self.peer_rtt_id = parts[3]
            else:
                self.peer_rtt_id = '0'
            if len(parts) >= 3:
                self.my_rtt_id = parts[2]
            else:
                self.my_rtt_id = '0'
        except:
            lg.exc()
            return
        # print 'doAcceptGreeting', self.peer_rtt_id, self.my_rtt_id
        # self._rtt_finish(rtt_id_in)
        # rtt_id_out = self._rtt_start('ALIVE')
        # udp.send_command(self.node.listen_port, udp.CMD_ALIVE, '', self.peer_address)
        first_greeting = False
        if self.peer_id:
            if new_peer_id != self.peer_id:
                lg.warn('session: %s,  peer_id from GREETING is different: %s' % (self, new_peer_id))
        else:
            if _Debug:
                lg.out(_DebugLevel, 'udp_session.doAcceptGreeting detected peer id : %s for session %s' % (new_peer_id, self.peer_address))
            self.peer_id = new_peer_id
            first_greeting = True
            try:
                sessions_by_peer_id()[self.peer_id].append(self)
            except:
                sessions_by_peer_id()[self.peer_id] = [self,]
        if self.peer_idurl:
            if new_peer_idurl != self.peer_idurl:
                lg.warn('session: %s,  peer_idurl from GREETING is different: %s' % (self, new_peer_idurl))
        else:
            if _Debug:
                lg.out(_DebugLevel, 'udp_session.doAcceptGreeting detected peer idurl : %s for session %s' % (new_peer_idurl, self.peer_address))
            self.peer_idurl = new_peer_idurl
            first_greeting = True
        if first_greeting:
            for s in sessions().values():
                if self.id == s.id:
                    continue
                if self.peer_id == s.peer_id:
                    lg.warn('got GREETING from another address, close session %s' % s)
                    s.automat('shutdown')
                    continue
                if self.peer_idurl == s.peer_idurl:
                    lg.warn('got GREETING from another idurl, close session %s' % s)
                    s.automat('shutdown')
                    continue

    def doAcceptAlive(self, arg):
        """
        Action method.
        """        
        address, command, payload = self._dispatch_datagram(arg)
        self.my_rtt_id = payload.strip()
        # print 'doAcceptAlive', self.my_rtt_id        

    def doReceiveData(self, arg):
        """
        Action method.
        """
        self.last_datagram_received_time = time.time()
        try:
            datagram, address = arg
            command, payload = datagram
        except:
            return
        assert address == self.peer_address
        self.bytes_received += len(payload)
        if command == udp.CMD_DATA:
            self.file_queue.on_received_data_packet(payload)
        elif command == udp.CMD_ACK:
            self.file_queue.on_received_ack_packet(payload)
#        elif command == udp.CMD_PING:
#            pass
#        elif command == udp.CMD_ALIVE:
#            pass
#        elif command == udp.CMD_GREETING:
#            pass

    def doNotifyConnected(self, arg):
        """
        Action method.
        """
        # # print 'CONNECTED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'

    def doNotifyDisconnected(self, arg):
        """
        Action method.
        """
        # # print 'DISCONNECTED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'

    def doCheckPendingFiles(self, arg):
        """
        Action method.
        """
        global _PendingOutboxFiles
        i = 0
        outgoings = 0
        # print 'doCheckPendingFiles', self.peer_id, len(_PendingOutboxFiles)
        while i < len(_PendingOutboxFiles):
            filename, host, description, result_defer, single, tm = _PendingOutboxFiles[i]
            # print filename, host, description, 
            if host == self.peer_id:
                outgoings += 1
                # small trick to speed up service packets - they have a high priority
                if description.startswith('Identity') or description.startswith('Ack'):
                    self.file_queue.insert_outbox_file(filename, description, result_defer, single)
                else:
                    self.file_queue.append_outbox_file(filename, description, result_defer, single)
                _PendingOutboxFiles.pop(i)
                # print 'pop'
            else:
                # _PendingOutboxFiles.insert(i, (filename, host, description, result_defer, single, tm))
                i += 1
                # print 'skip'
        # print len(_PendingOutboxFiles)
        if outgoings > 0:
            reactor.callLater(0, process_sessions)

    def doClosePendingFiles(self, arg):
        """
        Action method.
        """
        report_and_remove_pending_outbox_files_to_host(self.peer_id, self.error_message)
        self.file_queue.report_failed_inbox_files(self.error_message)
        self.file_queue.report_failed_outbox_files(self.error_message)
        self.file_queue.report_failed_outbox_queue(self.error_message)
        
    def doStartRTT(self, arg):
        """
        Action method.
        """
        self.my_rtt_id = self._rtt_start(self.state)

    def doFinishRTT(self, arg):
        """
        Action method.
        """
        self._rtt_finish(self.my_rtt_id)
        self.my_rtt_id = '0'

    def doFinishAllRTTs(self, arg):
        """
        Action method.
        """
        self._rtt_finish(self.my_rtt_id)
        self.my_rtt_id = '0'
        to_remove = []
        good_rtts = {}
        min_rtt = sys.float_info.max
        for rtt_id in self.rtts.keys():
            if self.rtts[rtt_id][1] == -1:
                to_remove.append(rtt_id)
            else:
                rtt = self.rtts[rtt_id][1] - self.rtts[rtt_id][0]
                if rtt < min_rtt:
                    min_rtt = rtt
                good_rtts[rtt_id] = rtt 
        self.min_rtt = min_rtt
        for rtt_id in to_remove:
            # print 'doFinishAllRTTs closed', rtt_id
            del self.rtts[rtt_id]
        if _Debug:
            lg.out(_DebugLevel, 'udp_session.doFinishAllRTTs: %r' % good_rtts)# print self.rtts.keys()
        
    def doErrMsg(self, event, arg):
        """
        Action method.
        """
        if event.count('shutdown'):
            self.error_message = 'session has been closed'
        else:
            self.error_message = arg

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'udp_session.doDestroyMe %s' % self)
        self.file_queue.close()
        self.file_queue = None
        self.node = None
        sessions().pop(self.id)
        sessions_by_peer_address()[self.peer_address].remove(self)
        if len(sessions_by_peer_address()[self.peer_address]) == 0:
            sessions_by_peer_address().pop(self.peer_address)
        if self.peer_id in sessions_by_peer_id().keys():
            sessions_by_peer_id()[self.peer_id].remove(self)
            if len(sessions_by_peer_id()[self.peer_id]) == 0:
                sessions_by_peer_id().pop(self.peer_id)            
        automat.objects().pop(self.index)


    def _dispatch_datagram(self, arg):
        self.last_datagram_received_time = time.time()
        try:
            datagram, address = arg
            command, payload = datagram
        except:
            lg.exc()
            return None, None, None
        assert address == self.peer_address
        return address, command, payload         

    def _rtt_start(self, name):
        i = 0
        while name+str(i) in self.rtts.keys():
            i += 1
        new_rtt_id = name+str(i)
        self.rtts[new_rtt_id] = [time.time(), -1]
        if _Debug:
            lg.out(_DebugLevel, 'udp_session._rtt_start added new RTT %s' % new_rtt_id)
        if len(self.rtts) > 10:
            oldest_rtt_moment = time.time()
            oldest_rtt_id = None
            for rtt_id in self.rtts.keys():
                rtt_data = self.rtts[rtt_id]
                if rtt_data[0] < oldest_rtt_moment:
                    oldest_rtt_moment = rtt_data[1]
                    oldest_rtt_id = rtt_id
            if oldest_rtt_id:
                rtt = self.rtts[oldest_rtt_id][1] - self.rtts[oldest_rtt_id][0]
                del self.rtts[oldest_rtt_id]
                if _Debug:
                    lg.out(_DebugLevel, 'udp_session._rtt_start removed oldest RTT %s  %r' % (
                        oldest_rtt_id, rtt))
        while len(self.rtts) > 10:
            i = self.rtts.popitem()
            if _Debug:
                lg.out(_DebugLevel, 'udp_session._rtt_finish removed one extra item : %r' % str(i))
        return new_rtt_id
        
    def _rtt_finish(self, rtt_id_in):
        if rtt_id_in == '0' or rtt_id_in not in self.rtts:
            return
        self.rtts[rtt_id_in][1] = time.time()
        rtt = self.rtts[rtt_id_in][1] - self.rtts[rtt_id_in][0]
        if _Debug:
            lg.out(_DebugLevel, 'udp_session._rtt_finish registered RTT %s  %r' % (
                rtt_id_in, rtt))
        
        
        
