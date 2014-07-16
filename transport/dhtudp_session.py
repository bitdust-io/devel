

"""
.. module:: dhtudp_session

BitPie.NET dhtudp_session() Automat


EVENTS:
    * :red:`datagram-received`
    * :red:`init`
    * :red:`shutdown`
    * :red:`timer-10sec`
    * :red:`timer-1min`
    * :red:`timer-1sec`
    * :red:`timer-30sec`
        
"""

import time

from twisted.internet import reactor

import lib.bpio as bpio
import lib.automat as automat
import lib.udp as udp

import dhtudp_stream

#------------------------------------------------------------------------------ 

_SessionsDict = {}
_KnownPeersDict = {}
_KnownUserIDsDict = {}
_PendingOutboxFiles = []

#------------------------------------------------------------------------------ 

def sessions():
    """
    """
    global _SessionsDict
    return _SessionsDict


def create(node, peer_address, peer_id=None):
    """
    """
    bpio.log(10, 'dhtudp_session.create  peer_address=%s' % str(peer_address))
    s = DHTUDPSession(node, peer_address, peer_id)
    sessions()[s.id] = s
    return s


def get(peer_address):
    """
    """
    # bpio.log(18, 'dhtudp_session.get %s %s' % (str(peer_address), 
    #     str(map(lambda s:s.peer_address, sessions().values()))))
    for id, s in sessions().items():
        if s.peer_address == peer_address:
            return s 
    return None


def get_by_peer_id(peer_id):
    """
    """
    for id, s in sessions().items():
        if s.peer_id == peer_id:
            return s 
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
    global _PendingOutboxFiles
    _PendingOutboxFiles.append((filename, host, description, result_defer, single, time.time()))



#------------------------------------------------------------------------------ 

class DHTUDPSession(automat.Automat):
    """
    This class implements all the functionality of the ``dhtudp_session()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['CONNECTED']),
        'timer-1sec': (1.0, ['PING','GREETING']),
        'timer-30sec': (30.0, ['GREETING']),
        'timer-10sec': (10.0, ['PING','CONNECTED']),
        }
    
    def __init__(self, node, peer_address, peer_id=None):
        self.node = node
        self.peer_address = peer_address
        self.peer_id = peer_id
        self.peer_idurl = None
        self.last_datagram_received_time = 0
        self.stream = dhtudp_stream.FileStream(self) 
        name = 'dhtudp_session[%s:%d]' % (self.peer_address[0], self.peer_address[1])
        automat.Automat.__init__(self, name, 'AT_STARTUP')

    def A(self, event, arg):
        #---CONNECTED---
        if self.state == 'CONNECTED':
            if event == 'datagram-received' :
                self.doReceiveData(arg)
            elif event == 'timer-10sec' :
                self.doAlive(arg)
            elif event == 'shutdown' or ( event == 'timer-1min' and not self.isSessionActive(arg) ) :
                self.state = 'CLOSED'
                self.doNotifyDisconnected(arg)
                self.doDestroyMe(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'PING'
                self.doInit(arg)
                self.doPing(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---PING---
        elif self.state == 'PING':
            if event == 'timer-1sec' :
                self.doPing(arg)
            elif event == 'datagram-received' and self.isPing(arg) :
                self.state = 'GREETING'
                self.doReceiveData(arg)
            elif event == 'datagram-received' and self.isGreeting(arg) :
                self.state = 'GREETING'
                self.doReceiveData(arg)
            elif event == 'datagram-received' and not self.isPingOrGreeting(arg) :
                self.doReceiveData(arg)
            elif event == 'shutdown' or event == 'timer-10sec' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---GREETING---
        elif self.state == 'GREETING':
            if event == 'timer-1sec' :
                self.doGreeting(arg)
            elif event == 'shutdown' or event == 'timer-30sec' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'datagram-received' and not self.isGreetingOrAlive(arg) :
                self.doReceiveData(arg)
            elif event == 'datagram-received' and self.isGreetingOrAlive(arg) :
                self.state = 'CONNECTED'
                self.doReceiveData(arg)
                self.doNotifyConnected(arg)
                self.doCheckPendingFiles(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass

    def isPing(self, arg):
        """
        Condition method.
        """
        command = arg[0][0]
        return command == udp.CMD_PING

    def isGreeting(self, arg):
        """
        Condition method.
        """
        command = arg[0][0]
        return command == udp.CMD_GREETING

    def isPingOrGreeting(self, arg):
        """
        Condition method.
        """
        command = arg[0][0]
        return ( command == udp.CMD_PING or command == udp.CMD_GREETING)

    def isGreetingOrAlive(self, arg):
        """
        Condition method.
        """
        command = arg[0][0]
        return ( command == udp.CMD_ALIVE or command == udp.CMD_GREETING)

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

    def doAlive(self, arg):
        """
        Action method.
        """
        udp.send_command(self.node.listen_port, udp.CMD_ALIVE, '', self.peer_address)

    def doGreeting(self, arg):
        """
        Action method.
        """
        payload = str(self.node.my_id)+' '+str(self.node.my_idurl)
        udp.send_command(self.node.listen_port, udp.CMD_GREETING, payload, self.peer_address)

    def doPing(self, arg):
        """
        Action method.
        """
        udp.send_command(self.node.listen_port, udp.CMD_PING, '', self.peer_address)

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
        if command == udp.CMD_DATA:
            self.stream.data_received(payload)
        elif command == udp.CMD_ACK:
            self.stream.ack_received(payload)
        elif command == udp.CMD_GREETING:
            try:
                new_peer_id, new_peer_idurl = payload.split(' ')
            except:
                return 
            udp.send_command(self.node.listen_port, udp.CMD_ALIVE, '', self.peer_address)
            if self.peer_id:
                if new_peer_id != self.peer_id:
                    bpio.log(4, 'dhtudp_session.doReceiveData WARNING session: %s,  peer_id from GREETING is different: %s' % (self, new_peer_id))
            else:
                # bpio.log(4, 'dhtudp_session.doReceiveData got peer id (%s) for session %s from GREETING packet' % (new_peer_id, self))
                self.peer_id = new_peer_id
            if self.peer_idurl:
                if new_peer_idurl != self.peer_idurl:
                    bpio.log(4, 'dhtudp_session.doReceiveData WARNING session: %s,  peer_idurl from GREETING is different: %s' % (self, new_peer_idurl))
            else:
                # bpio.log(4, 'dhtudp_session.doReceiveData got peer idurl (%s) for session %s from GREETING packet' % (new_peer_id, self))
                self.peer_idurl = new_peer_idurl
            for s in sessions().values():
                if self.id == s.id:
                    continue
                if self.peer_id == s.peer_id:
                    bpio.log(6, 'dhtudp_session.doReceiveData WARNING  got GREETING from another address, close session %s' % s)
                    s.automat('shutdown')
                    continue
                if self.peer_idurl == s.peer_idurl:
                    bpio.log(6, 'dhtudp_session.doReceiveData WARNING  got GREETING from another idurl, close session %s' % s)
                    s.automat('shutdown')
                    continue
        elif command == udp.CMD_PING:
            payload = str(self.node.my_id)+' '+str(self.node.my_idurl)
            udp.send_command(self.node.listen_port, udp.CMD_GREETING, payload, self.peer_address)

    def doNotifyConnected(self, arg):
        """
        Action method.
        """
        # print 'CONNECTED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'

    def doNotifyDisconnected(self, arg):
        """
        Action method.
        """
        # print 'DISCONNECTED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'

    def doCheckPendingFiles(self, arg):
        """
        Action method.
        """
        global _PendingOutboxFiles
        i = 0
        while i < len(_PendingOutboxFiles):
            filename, host, description, result_defer, single, tm = _PendingOutboxFiles.pop(i)
            if host == self.peer_id:
                self.stream.append_outbox_file(filename, description, result_defer, single)
            else:
                _PendingOutboxFiles.insert(i, (filename, host, description, result_defer, single, tm))
                i += 1

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        self.stream.close()
        self.stream = None
        self.node = None
        sessions().pop(self.id)
        automat.objects().pop(self.index)


