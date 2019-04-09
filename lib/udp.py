#!/usr/bin/python
# udp.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (udp.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
from io import BytesIO

#------------------------------------------------------------------------------

import sys
import time

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet import protocol
from twisted.internet import task
from twisted.internet.defer import DeferredList

#------------------------------------------------------------------------------

from lib import strng

from logs import lg

from system import bpio

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 12

#------------------------------------------------------------------------------

_Listeners = {}
# _DatagramReceivedCallbacksList = []
_LastDatagramReceivedTime = 0

#------------------------------------------------------------------------------

CMD_PING = b'p'
CMD_GREETING = b'g'
CMD_DATA = b'd'
CMD_ACK = b'k'
CMD_ALIVE = b'a'
CMD_STUN = b's'
CMD_MYIPPORT = b'm'

#------------------------------------------------------------------------------

# def add_datagram_receiver_callback(callback):
#    global _DatagramReceivedCallbacksList
#    if callback not in _DatagramReceivedCallbacksList:
#        _DatagramReceivedCallbacksList.append(callback)
#
#
# def remove_datagram_receiver_callback(callback):
#    global _DatagramReceivedCallbacksList
#    if callback in _DatagramReceivedCallbacksList:
#        _DatagramReceivedCallbacksList.remove(callback)

#------------------------------------------------------------------------------


def listen(port, proto=None):
    if port in list(listeners().keys()):
        lg.warn('already started on port %d' % port)
        lg.out(6, '            %s' % str(list(listeners().keys())))
        return listeners()[port]
    if proto is None:
        listeners()[port] = reactor.listenUDP(port, CommandsProtocol())  # @UndefinedVariable
    else:
        listeners()[port] = reactor.listenUDP(port, proto)  # @UndefinedVariable
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
        if cb in self.callbacks:
            lg.warn('Callback method %s already registered' % cb)
        else:
            self.callbacks.append(cb)

    def remove_callback(self, cb):
        if cb not in self.callbacks:
            lg.warn('Callback method %s not registered' % cb)
        else:
            self.callbacks.remove(cb)

    def run_callbacks(self, data, address):
        for cb in self.callbacks:
            # print cb
            if cb(data, address):
                break

    def datagramReceived(self, datagram, address):
        self.bytes_in += len(datagram)
        self.run_callbacks(datagram, address)

    def sendDatagram(self, datagram, address):
        """
        Sends UDP datagram to transport.
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

    SoftwareVersion = b'1'

    def __init__(self):
        self.command_filter_callback = None
        BasicProtocol.__init__(self)

    def set_command_filter_callback(self, cb):
        self.command_filter_callback = cb

    def datagramReceived(self, datagram, address):
        global _LastDatagramReceivedTime
        _LastDatagramReceivedTime = time.time()
        inp = BytesIO(datagram)
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
            lg.warn('different software version: %s' % version)
            return
        if _Debug:
            lg.out(_DebugLevel, '<<< [%s] (%d bytes) from %s, total %d bytes received' % (
                command, datagramsz, str(address), self.bytes_in))
        # self.bytes_in += datagramsz
        handled = False
        try:
            if self.command_filter_callback:
                handled = self.command_filter_callback(command, datagram, inp, address)
        except:
            lg.exc()
        payload = inp.read()
        inp.close()
        if not handled:
            self.run_callbacks((command, payload), address)
        self.bytes_in += datagramsz
        # if command in [CMD_DATA, CMD_ACK]:

    def sendCommand(self, command, data, address):
        payloadsz = len(data)
        outp = BytesIO()
        try:
            outp.write(self.SoftwareVersion)
            outp.write(strng.to_bin(command))
            outp.write(strng.to_bin(data))
            # datagram = ''.join((
            #     self.SoftwareVersion,
            #     command,
            #     data))
            if _Debug:
                lg.out(_DebugLevel, '>>> [%s] (%d bytes) to %s, total %d bytes sent' % (
                    command, payloadsz + 2, address, self.bytes_out))
            result = self.sendDatagram(outp.getvalue(), address)
        except:
            outp.close()
            lg.exc()
            return None
        outp.close()
        self.bytes_out += payloadsz + 2
        # if command in [CMD_DATA, CMD_ACK]:
        return result

#------------------------------------------------------------------------------


def main():
    bpio.init()
    lg.set_debug_level(18)
    listnport = int(sys.argv[1])

    def received(dgrm, addr):
        send_command(listnport, CMD_ALIVE, 'ok', addr)

    def go(x, port):
        print('go', x)
        l = listen(port)
        l.protocol.add_callback(received)

    def restart(port):
        print('restart')
        if listener(port):
            close(port).addCallback(go, port)
        else:
            go(None, port)

    def ping(fromport, toaddr):
        print('ping')
        send_command(fromport, CMD_PING, b'ping', toaddr)

    if len(sys.argv) > 2:
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
