#!/usr/bin/python

__doc__ = """
This code comes from Shtoom: http://divmod.org/projects/shtoom
Copyright (C) 2004 Anthony Baxter
Licensed under the GNU LGPL.
"""

"""
.. module:: stun_client_RFC3489

This is a code to run STUN client to detect external IP of that machine.
It uses UDP protocol to communicate with public STUN servers.

After all process of "stunning" IP address is finished you can leave the opened UDP port opened.
This way external UDP port is not changed and
so other users can send us packets to <external IP>:<external PORT>.

TODO:
All this stuff must be simplified.
We really do not need to use a real STUN servers.
No need to detect a network metric or other info, just detect our external IP:PORT.
BitDust already have some sort of own stun server, need to use that stuff instead of shtoom code.
"""

import sys
import sets
import struct
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in stun.py')

from twisted.internet.defer import Deferred, succeed, fail

from logs import lg

from system import bpio

import shtoom.stun
import shtoom.nat

#------------------------------------------------------------------------------

_WorkingDefers = []
_IsWorking = False
_UDPListener = None
_StunClient = None
_LastStunTime = 0
_LastStunResult = None
_TimeoutTask = None

#------------------------------------------------------------------------------


class IPStunProtocol(shtoom.stun.StunDiscoveryProtocol):
    """
    Class to detect external IP address via STUN protocol.
    """
    datagram_received_callback = None

    def stateChanged(self, old, new):
        """
        Called when internal state of the process were changed.
        """
        lg.out(4, 'stun.stateChanged [%s]->[%s]' % (old, new))

    def finishedStun(self):
        """
        Called when the process is finished.
        """
        local = '0.0.0.0'
        ip = '0.0.0.0'
        port = '0'
        typ = 'unknown'
        alt = 'unknown'
        try:
            if self.externalAddress and self.localAddress and self.natType:
                local = str(self.localAddress)
                ip = str(self.externalAddress[0])
                port = str(self.externalAddress[1])
                typ = str(self.natType.name)
                alt = str(self._altStunAddress)
        except:
            lg.exc()
        lg.out(2, 'stun.IPStunProtocol.finishedStun local=%s external=%s altStun=%s NAT_type=%s' % (
            local, ip + ':' + port, alt, typ))
        if self.result is not None:
            if not self.result.called:
                if ip == '0.0.0.0':
                    self.result.callback(ip)
                else:
                    self.result.callback(ip)
            self.result = None

    def datagramReceived(self, dgram, address):
        """
        Called when UDP datagram is received.

        I place a hook here to process datagrams in another place.
        """
        if self._finished:
            if self.datagram_received_callback is not None:
                return self.datagram_received_callback(dgram, address)
        else:
            stun_dgram = dgram[:20]
            if len(stun_dgram) < 20:
                if self.datagram_received_callback is None:
                    return
                return self.datagram_received_callback(dgram, address)
            else:
                try:
                    mt, pktlen, tid = struct.unpack('!hh16s', stun_dgram)
                except:
                    if self.datagram_received_callback is None:
                        return
                    return self.datagram_received_callback(dgram, address)
        return shtoom.stun.StunDiscoveryProtocol.datagramReceived(self, dgram, address)

    def refresh(self):
        """
        Clear fields to be able to restart the process.
        """
        self._potentialStuns = {}
        self._stunState = '1'
        self._finished = False
        self._altStunAddress = None
        self.externalAddress = None
        self.localAddress = None
        self.expectedTID = None
        self.oldTIDs = sets.Set()
        self.natType = None
        self.result = Deferred()
        self.count = 0
        self.servers = [(host, port) for host, port in shtoom.stun.DefaultServers]

    def setCallback(self, cb, arg=None):
        """
        Set a callback to get the stun results.
        """
        self.result.addBoth(cb, arg)


def stunExternalIP(timeout=10, verbose=False, close_listener=True, internal_port=5061, block_marker=None):
    """
    Start the STUN process.

    :param timeout: how long to wait before decide that STUN is failed
    :param verbose: set to True to print more log messages
    :param close_listener: if True the listener will be closed after STUN is finished
    :param internal_port: a port number to listen, the external port will be different
    :param block_marker: you can provide a function if you need to block some other code while STUN is working
    """
    global _WorkingDefers
    global _IsWorking
    global _UDPListener
    global _StunClient
    global _LastStunTime
    global _TimeoutTask

    # d = Deferred()
    # ip = bpio.ReadTextFile(settings.ExternalIPFilename())
    # d.callback(ip or '0.0.0.0')
    # return d

    if _IsWorking:
        res = Deferred()
        _WorkingDefers.append(res)
        lg.out(4, 'stun.stunExternalIP SKIP, already called')
        return res

    res = Deferred()
    _WorkingDefers.append(res)
    _IsWorking = True

    lg.out(2, 'stun.stunExternalIP')

    shtoom.stun.STUNVERBOSE = verbose
    shtoom.nat._Debug = verbose
    shtoom.nat._cachedLocalIP = None
    shtoom.nat.getLocalIPAddress.clearCache()

    if _UDPListener is None:
        lg.out(4, 'stun.stunExternalIP prepare listener')
        if _StunClient is None:
            _StunClient = IPStunProtocol()
        else:
            _StunClient.refresh()

        try:
            UDP_port = int(internal_port)
            _UDPListener = reactor.listenUDP(UDP_port, _StunClient)
            lg.out(4, 'stun.stunExternalIP UDP listening on port %d started' % UDP_port)
        except:
            try:
                _UDPListener = reactor.listenUDP(0, _StunClient)
                lg.out(4, 'stun.stunExternalIP multi-cast UDP listening started')
            except:
                lg.exc()
                for d in _WorkingDefers:
                    d.callback('0.0.0.0')
                _WorkingDefers = []
                _IsWorking = False
                return res

    lg.out(6, 'stun.stunExternalIP refresh stun client')
    _StunClient.refresh()
    _StunClient.timeout = timeout

    def stun_finished(x, block_marker):
        global _UDPListener
        global _StunClient
        global _WorkingDefers
        global _IsWorking
        global _LastStunResult
        global _TimeoutTask

        if block_marker:
            block_marker('unblock')
        lg.out(6, 'stun.stunExternalIP.stun_finished: ' + str(x).replace('\n', ''))
        _LastStunResult = x
        try:
            if _IsWorking:
                _IsWorking = False
                for d in _WorkingDefers:
                    if x == '0.0.0.0':
                        d.callback(x)
                    else:
                        d.callback(x)
            _WorkingDefers = []
            _IsWorking = False
            if _UDPListener is not None and close_listener is True:
                _UDPListener.stopListening()
                _UDPListener = None
            if _StunClient is not None and close_listener is True:
                del _StunClient
                _StunClient = None
        except:
            lg.exc()

    _StunClient.setCallback(stun_finished, block_marker)

    lg.out(6, 'stun.stunExternalIP starting discovery')
    if block_marker:
        block_marker('block')
    reactor.callLater(0, _StunClient.startDiscovery)

    _LastStunTime = time.time()
    return res


def getUDPListener():
    """
    Return a current UDP listener from memory.
    """
    global _UDPListener
    return _UDPListener


def getUDPClient():
    """
    Return a current STUN client from memory.
    """
    global _StunClient
    return _StunClient


def stopUDPListener():
    """
    Close STUN client and UDP listener.
    """
    lg.out(6, 'stun.stopUDPListener')
    global _UDPListener
    global _StunClient
    result = None
    if _UDPListener is not None:
        result = _UDPListener.stopListening()
        _UDPListener = None
    if _StunClient is not None:
        del _StunClient
        _StunClient = None
    if result is None:
        result = succeed(1)
    return result


def last_stun_time():
    """
    Return a last moment when STUN process was started.
    """
    global _LastStunTime
    return _LastStunTime


def last_stun_result():
    """
    Return a results from previous calls.
    """
    global _LastStunResult
    return _LastStunResult

#------------------------------------------------------------------------------


def success(x):
    """
    For tests.
    """
    print x
    if sys.argv.count('continue'):
        reactor.callLater(10, main)
    else:
        reactor.stop()


def fail(x):
    """
    For tests.
    """
    print x
    if sys.argv.count('continue'):
        reactor.callLater(5, main)
    else:
        reactor.stop()


def main(verbose=False):
    """
    For tests.
    """
    if sys.argv.count('port'):
        d = stunExternalIP(verbose=verbose, close_listener=False, internal_port=int(sys.argv[sys.argv.index('port') + 1]))
    else:
        d = stunExternalIP(verbose=verbose, close_listener=False,)
    d.addCallback(success)
    d.addErrback(fail)

#------------------------------------------------------------------------------

if __name__ == "__main__":
    bpio.init()
    if sys.argv.count('quite'):
        lg.set_debug_level(0)
        main(False)
    else:
        # log.startLogging(sys.stdout)
        lg.set_debug_level(20)
        main(True)
    reactor.run()
