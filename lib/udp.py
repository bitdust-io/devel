#!/usr/bin/python
#udp.py
#
# <<<COPYRIGHT>>>
#
#
#
#

import sys
import time
import cStringIO

from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import task
from twisted.internet.defer import DeferredList

from logs import lg

import bpio

#------------------------------------------------------------------------------ 

_Listeners = {}
# _DatagramReceivedCallbacksList = []
_LastDatagramReceivedTime = 0

#------------------------------------------------------------------------------

CMD_PING = 'p'
CMD_GREETING = 'g'
CMD_DATA = 'd'
CMD_ACK = 'k'
CMD_ALIVE = 'a'
CMD_STUN = 's'
CMD_MYIPPORT = 'm'

#------------------------------------------------------------------------------ 

#def add_datagram_receiver_callback(callback):
#    global _DatagramReceivedCallbacksList
#    if callback not in _DatagramReceivedCallbacksList:
#        _DatagramReceivedCallbacksList.append(callback)
#
#
#def remove_datagram_receiver_callback(callback):
#    global _DatagramReceivedCallbacksList
#    if callback in _DatagramReceivedCallbacksList:
#        _DatagramReceivedCallbacksList.remove(callback)

#------------------------------------------------------------------------------ 

def listen(port, proto=None):
    if port in listeners().keys():
        lg.warn('already started on port %d' % port)
        lg.out(6, '            %s' % str(listeners().keys()))
        return listeners()[port]
    if proto is None:
        listeners()[port] = reactor.listenUDP(port, CommandsProtocol())
    else:
        listeners()[port] = reactor.listenUDP(port, proto)
    listeners()[port].port = port
    lg.out(6, 'udp.listen on port %d started' % port)
    return listeners()[port]


def port_closed(x):
    lg.out(6, 'udp.port_closed   listeners: %d' % (len(listeners())))
    return x
    
    
def close(port):
    lg.out(6, 'udp.close  %r' % port)
    l = listeners().pop(port)
    l.protocol.disconnect()
    d = l.stopListening()
    del l
    l = None
    if d:
        d.addCallback(port_closed)
    lg.out(6, 'udp.close  STOP listener on UDP port %d' % port)
    return d


def close_all():
    shutlist = []
    l = list(listeners().keys())
    for port in l:
        d = close(port)
        if d:
            # d.addCallback(port_closed)
            shutlist.append(d)
            # lg.out(6, 'udp.close_all  STOP listener on UDP port %d' % port)
    # _Listeners.clear()
    lg.out(6, 'udp.close_all  %d UDP listeners were closed' % len(shutlist))
    return DeferredList(shutlist)

#------------------------------------------------------------------------------ 

def listeners():
    global _Listeners
    # print 'listeners', id(_Listeners)
    return _Listeners


def proto(port):
    if port not in listeners():
        return None
    return listeners()[port].protocol


def listener(port):
    if port not in listeners():
        return None
    return listeners()[port]

#------------------------------------------------------------------------------ 

def send_command(from_port, command, data, address):
    p = proto(from_port)
    if not p:
        lg.warn('port %d is not opened to listen' % from_port)
        return False
    result = p.sendCommand(command, data, address)
    p = None
    return result
    
def get_last_datagram_time():
    global _LastDatagramReceivedTime
    return _LastDatagramReceivedTime
    
#------------------------------------------------------------------------------ 

class BasicProtocol(protocol.DatagramProtocol):
    
    def __init__(self):
        """
        """
        # lg.out(6, 'udp.BasicProtocol.__init__ %r' % id(self))
        self.port = None
        self.callbacks = []
        self.stopping = False
        self.bytes_in = 0
        self.bytes_out = 0
    
    def __del__(self):
        """
        """
        # lg.out(6, 'udp.BasicProtocol.__del__ %r' % id(self))
        # protocol.DatagramProtocol.__del__(self)

    def insert_callback(self, index, cb):
        self.callbacks.insert(index, cb)

    def add_callback(self, cb):
        self.callbacks.append(cb)
        
    def remove_callback(self, cb):
        self.callbacks.remove(cb)

    def run_callbacks(self, data, address):
        for cb in self.callbacks:
            if cb(data, address):
                break

    def datagramReceived(self, datagram, address):
        self.bytes_in += len(datagram)
        self.run_callbacks(datagram, address)
        
    def sendDatagram(self, datagram, address):
        """
        """
        if self.stopping:
            return False
        try:
            self.transport.write(datagram, address)
        except:
            # lg.exc()
            return False
        self.bytes_out += len(datagram)
        return True
        
    def startProtocol(self):
        """
        """
        lg.out(6, 'udp.startProtocol %r' % self)

    def stopProtocol(self):
        """
        """
        lg.out(6, 'udp.stopProtocol %r' % self)
        self.port = None
        self.callbacks = []
        
    def disconnect(self):
        """
        """
        self.stopping = True
        self.callbacks = []
        # self.transport.abortConnection()
        
#------------------------------------------------------------------------------ 

class CommandsProtocol(BasicProtocol):
    """
    Datagram format is::
    
        | Software | Command ID | Payload |  
        | version  |            |         |
        | (1 byte) | (1 byte)   |         |
        
    Commands have different payload format, see in the code.
    List of valid commands (by ID):
    
        * 'p' = ``PING``        an empty packet to establish connection   
        * 'g' = ``GREETING``    need to give a response when received a ``PING`` packet,
                                payload should contain a global ID of responding user
                                so remote peer can identify who is this.                 
        * 'd' = ``DATA``        a data packet, payload format will be described bellow.   
        * 'r' = ``REPORT``      a response after receiving a ``DATA`` packet,
                                so sender can send next packets. 
        * 'a' = ``ALIVE``       periodically need to send an empty packet to keep session alive.
        * 's' = ``STUN``        request remote peer for my external IP:PORT.
        * 'm' = ``MYIPPORT``    response to ``STUN`` packet, payload will contain IP:PORT of remote peer
    """
    
    SoftwareVersion = '1'
    
    def __init__(self):
        self.command_filter_callback = None
        BasicProtocol.__init__(self)
    
    def set_command_filter_callback(self, cb):
        self.command_filter_callback = cb
        
    def datagramReceived(self, datagram, address):
        global _LastDatagramReceivedTime
        _LastDatagramReceivedTime = time.time()
        inp = cStringIO.StringIO(datagram)
        try:
            # version = datagram[0]
            # command = datagram[1]
            # payload = datagram[2:]
            # payloadsz = len(payload)
            datagramsz = len(datagram)
            version = inp.read(1)
            command = inp.read(1)
        except:
            inp.close()
            lg.exc()
            return
        if version != self.SoftwareVersion:
            inp.close()
            lg.warn('- different software version: %s' % version)
            return
        # self.bytes_in += datagramsz
        handled = False
        try:
            if self.command_filter_callback:
                handled = self.command_filter_callback(command, datagram, inp, address)
        except:
            lg.exc()
        if not handled:
            payload = inp.read()
            self.run_callbacks((command, payload), address)
        inp.close()
        self.bytes_in += datagramsz
        # lg.out(18, '>>> [%s] (%d bytes) from %s, total %d bytes received' % (
        #     command, datagramsz, str(address), self.bytes_in))
        
    def sendCommand(self, command, data, address):
        payloadsz = len(data)
        outp = cStringIO.StringIO()
        try:
            outp.write(self.SoftwareVersion)
            outp.write(command)
            outp.write(data)
            # datagram = ''.join((
            #     self.SoftwareVersion,
            #     command,
            #     data))
            result = self.sendDatagram(outp.getvalue(), address)
        except:
            outp.close()
            return None
        outp.close()
        self.bytes_out += payloadsz + 2
        # lg.out(18, '<<< [%s] (%d bytes) to %s, total %d bytes sent' % (
        #     command, payloadsz + 2, address, self.bytes_out))
        return result

#------------------------------------------------------------------------------ 

def main():
    bpio.init()
    lg.set_debug_level(18)
    listnport = int(sys.argv[1])
    def received(dgrm, addr):
        send_command(listnport, CMD_ALIVE, 'ok', addr)
    def go(x, port):
        print 'go', x
        l = listen(port)
        l.protocol.add_callback(received)
    def restart(port):
        print 'restart'
        if listener(port):
            close(port).addCallback(go, port)
        else:
            go(None, port)
    def ping(fromport, toaddr):
        print 'ping'
        send_command(fromport, CMD_PING, 'ping', toaddr)
    if len(sys.argv)>2:
        addr = sys.argv[2].split(':')
        addr = (addr[0], int(addr[1]))
        listen(listnport)
        task.LoopingCall(ping, listnport, addr).start(1, False)
    else:
        restart(listnport)
        # task.LoopingCall(restart, listnport).start(5)
    reactor.run()

if __name__ == "__main__":
    main()        
        
        
        
        
        
        

    
        
