#!/usr/bin/env python
#shtoom/stun.py

# This code comes from Shtoom: http://divmod.org/projects/shtoom
# Licensed under the GNU LGPL.
# Copyright (C) 2004 Anthony Baxter
# $Id: stun.py,v 1.15 2004/03/02 14:22:31 anthony Exp $

import sys
import struct, socket, time
try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in shtoom/stun.py')

from twisted.internet import defer
from twisted.internet.protocol import DatagramProtocol
from twisted.python import log
import warnings

import sets


# from shtoom.interfaces import NATMapper as INATMapper

from defcache import DeferredCache
# from shtoom.nat import BaseMapper

STUNVERBOSE = False
# If we're going to follow RFC recommendation, make this 7
MAX_RETRANSMIT = 7

INITIAL_TIMEOUT = 0.100
BACKOFF_TIME = 0.050
MAX_BACKOFF = 4

# Work to be done:
#  - Reverse engineer the C code stun client - why is it giving up so fast?
#  - Do the shared secret stuff? looks like it needs TLS and crap like that.
#  - Move the StunPolicy code to become nat.NATPolicy - we still don't want to
#    use a NAT if both addresses are RFC1918 addresses.
#  - Make the STUN discovery code use a deferred for it's result!
#  - Cache the first responding STUN server after discovery (in the NatType
#    object, maybe?) and only use it? Then need to handle it failing later.
#
#  What happens to any delayed STUN packets that arrive after the Hook gives
#  the transport back? The code that uses the transport should be forgiving,
#  I guess.

# This should be replaced with lookups of
# _stun._udp.divmod.com and _stun._udp.wirlab.net

DefaultServers = [
('stun.ekiga.net', 3478),
# ('stun.fwdnet.net', 3478),
('stun.ideasip.com', 3478),
# ('stun01.sipphone.com', 3478),
('stun.softjoys.com', 3478),
('stun.voipbuster.com', 3478),
# ('stun.voxgratia.org', 3478),
('stun.xten.com', 3478),
('stunserver.org', 3478),
('stun.sipgate.net', 10000),
('provserver.televolution.net', 3478),
('sip1.lakedestiny.cordiaip.com', 3478),
('stun1.voiceeclipse.net', 3478),
('stun.callwithus.com', 3478),
('stun.counterpath.net', 3478),
# ('stun.endigovoip.com', 3478),
('stun.internetcalls.com', 3478),
('stun.ipns.com', 3478),
('stun.noc.ams-ix.net', 3478),
('stun.phonepower.com', 3478),
('stun.phoneserve.com', 3478),
('stun.rnktel.com', 3478),
('stun.sipgate.net', 3478),
('stun.stunprotocol.org', 3478),
('stun.voip.aebc.com', 3478),
('stun.voxalot.com', 3478),

#    ('stun.ekiga.net', 3478),    # added from http://www.voip-info.org/wiki-STUN
#    ('stun.fwdnet.net', 3478),
#    ('stun.ideasip.com', 3478),
#    ('stun.xten.net', 3478),     # old and broken ones
#    ('sip.iptel.org', 3478),
#    ('stun2.wirlab.net', 3478),
#    ('stun.fwdnet.net', 3478),
#    ('stun2.fwdnet.net', 3478),
#    ('stun.wirlab.net', 3478), #
#    ('stun1.vovida.org', 3478), #
#    ('tesla.divmod.net', 3478), #
#    ('erlang.divmod.net', 3478), #
#    ('69.90.168.13', 3478), # stun.fednet.net
#    ('69.90.168.14', 3478), # stun2.fednet.net
#    ('64.69.76.23', 3478), # stun.xten.net
#    ('195.37.77.99', 3478), # sip.iptel.org
#    ('192.98.81.87', 3478), # stun2.wirlab.net
#    ('192.98.81.66', 3478), # stun.wirlab.net
#    ('128.107.250.38', 3478), # stun1.vovida.org
#    ('204.91.10.94', 3478), # tesla.divmod.net
#    ('204.91.10.93', 3478), # erlang.divmod.net
]


StunTypes = {
   0x0001: 'MAPPED-ADDRESS',
   0x0002: 'RESPONSE-ADDRESS ', 
   0x0003: 'CHANGE-REQUEST',
   0x0004: 'SOURCE-ADDRESS',
   0x0005: 'CHANGED-ADDRESS',
   0x0006: 'USERNAME',
   0x0007: 'PASSWORD',
   0x0008: 'MESSAGE-INTEGRITY',
   0x0009: 'ERROR-CODE',
   0x000a: 'UNKNOWN-ATTRIBUTES',
   0x000b: 'REFLECTED-FROM',
}

CHANGE_NONE = struct.pack('!i',0)
CHANGE_PORT = struct.pack('!i',2)
CHANGE_IP = struct.pack('!i',4)
CHANGE_BOTH = struct.pack('!i',6)

for k,v in StunTypes.items():
    StunTypes[v] = k
del k, v

class _NatType:
    def __init__(self, name, useful=True, blocked=False):
        self.name = name
        self.useful = useful
        self.blocked = blocked
    def __repr__(self):
        return '<NatType %s>'%(self.name)

NatTypeUDPBlocked = _NatType('UDPBlocked', useful=False, blocked=True)
NatTypeNone = _NatType('None')
NatTypeSymUDP = _NatType('SymUDP')
NatTypeFullCone = _NatType('FullCone')
NatTypeSymmetric = _NatType('Symmetric', useful=False)
NatTypeRestrictedCone = _NatType('RestrictedCone')
NatTypePortRestricted = _NatType('PortRestricted')


# For testing - always return this STUN type
_ForceStunType = None

def hexify(s):
    if s is None:
        return
    ret = ''.join([ '%x'%(ord(c)) for c in s ])
    return ret


import os
if hasattr(os, 'urandom'):
    def getRandomTID():
        return os.urandom(16)
elif os.path.exists('/dev/urandom'):
    def getRandomTID():
        return open('/dev/urandom').read(16)
else:
    def getRandomTID():
        # It's not absolutely necessary to have a particularly strong TID here
        import random
        tid = [ chr(random.randint(0,255)) for x in range(16) ]
        tid = ''.join(tid)
        return tid

def _parseStunResponse(dgram, address, expectedTID=None, oldtids=[]):
    mt, pktlen, tid = struct.unpack('!hh16s', dgram[:20])
    if expectedTID is not None and expectedTID != tid:
        # a response from an earlier request
        if tid in oldtids:
            # discard
            if STUNVERBOSE:
                log.msg("ignoring belated STUN response to %r from %s"%(
                            hexify(tid), repr(address)), system='stun')
            return
        log.msg("got unexpected STUN response %r != %r from %s"%
                        (hexify(expectedTID), hexify(tid),
                        repr(address),), system='stun')
        return
    resdict = {}
    if mt == 0x0101:
        log.msg("got STUN response to %r from %s"%(hexify(expectedTID),
                                                   repr(address)),
                                                        system='stun')
        # response
        remainder = dgram[20:]
        while remainder:
            avtype, avlen = struct.unpack('!hh', remainder[:4])
            val = remainder[4:4+avlen]
            avtype = StunTypes.get(avtype, '(Unknown type %04x)'%avtype)
            remainder = remainder[4+avlen:]
            if avtype in ('MAPPED-ADDRESS',
                          'CHANGED-ADDRESS',
                          'SOURCE-ADDRESS'):
                dummy,family,port,addr = struct.unpack('!ccH4s', val)
                addr = socket.inet_ntoa(addr)
                # if STUNVERBOSE:
                #     print avtype, addr, port
                if avtype == 'MAPPED-ADDRESS':
                    resdict['externalAddress'] = (addr, port)
                elif avtype == 'CHANGED-ADDRESS':
                    resdict['_altStunAddress'] = (addr, address[1])
#                elif avtype == 'SOURCE-ADDRESS':
#                    resdict['sourceAddress'] = (addr, port)
                elif address[0] != addr:
                    # Some son of a bitch is rewriting packets on the way
                    # back. AAARGH.
                    log.msg('WARNING: packets are being rewritten %r != %r'%
                            (address, (addr,port)), system='stun')
                    return
            else:
                log.msg("STUN: unhandled AV %s, val %r"%(avtype,
                                                         repr(val)),
                                                         system='stun')
    elif mt == 0x0111:
        log.err("STUN got an error response")
    return resdict

class  _StunBase(object):

    def sendRequest(self, server, tid=None, avpairs=()):
        # <AP>
        if not self.transport:
##            print "No transport defined, cannot send STUN request"
            return
        # </AP>
        if tid is None:
            tid = getRandomTID()
        mt = 0x1 # binding request
        avstr = ''
        # add any attributes
        if not avpairs:
            avpairs = ('CHANGE-REQUEST', CHANGE_NONE),
        for a,v in avpairs:
            avstr = avstr + struct.pack('!hh', StunTypes[a], len(v)) + v
        pktlen = len(avstr)
        if pktlen > 65535:
            raise ValueError, "stun request too big (%d bytes)"%pktlen
        pkt = struct.pack('!hh16s', mt, pktlen, tid) + avstr
        if STUNVERBOSE:
            print "sending request %r with %d avpairs to %r (in state %s)"%(
                            hexify(tid), len(avpairs), server, self._stunState)
        try:
            self.transport.write(pkt, server)
        except:
            if STUNVERBOSE:
                print "exception during sending request"

class StunDiscoveryProtocol(DatagramProtocol, _StunBase):

    stunDiscoveryRetries = 0

    def __init__(self, servers=DefaultServers, *args, **kwargs):
        # Potential STUN servers
        self._potentialStuns = {}
        # See flowchart ascii art at bottom of file.
        self._stunState = '1'
        self._finished = False
        self._altStunAddress = None
        self.externalAddress = None
        self.localAddress = None
        self.expectedTID = None
        self.oldTIDs = sets.Set()
        self.natType = None
        self.timerTask = None
        self.timeout = 20
        self.servers = [(host, port) for host, port in servers]
        # super(StunDiscoveryProtocol, self).__init__(*args, **kwargs)

    def stateChanged(self, old, new):
        if STUNVERBOSE:
            print "stun state changed: [%s] -> [%s]" % (old, new)

    def initialStunRequest(self, address):
##        print 'initialStunRequest', address
        # <AP>
        if self._finished:
            return
        # </AP>
        tid = getRandomTID()
        delayed = reactor.callLater(INITIAL_TIMEOUT,
                                    self.retransmitInitial, address, tid)
        self._potentialStuns[tid] = delayed
        self.oldTIDs.add(tid)
        self.sendRequest(address, tid=tid)

    def retransmitInitial(self, address, tid, count=1):
        # <AP>
        if self._finished:
            return
        # </AP>
        if count <= MAX_RETRANSMIT:
            t = BACKOFF_TIME * 2**min(count, MAX_BACKOFF)
            delayed = reactor.callLater(t, self.retransmitInitial,
                                                address, tid, count+1)
            self._potentialStuns[tid] = delayed
            self.sendRequest(address, tid=tid)
        else:
            del self._potentialStuns[tid]
            if STUNVERBOSE:
                print "giving up on %r, _potentialStuns: %s" % (str(address), str(self._potentialStuns))
            if not self._potentialStuns:
                if STUNVERBOSE:
                    print "stun state 1 timeout - no internet UDP possible"
                self.natType = NatTypeUDPBlocked
                self._finishedStun()

    def datagramReceived(self, dgram, address):
        if self._finished:
            return
        mt, pktlen, tid = struct.unpack('!hh16s', dgram[:20])
        # Check tid is one we sent and haven't had a reply to yet
        if tid in self._potentialStuns:
            delayed = self._potentialStuns.get(tid)
            if delayed is not None:
                delayed.cancel()
            del self._potentialStuns[tid]
            if self._stunState == '1':
                # We got a (potentially) working STUN server!
                # Cancel the retransmit timers for the other ones
                for k in self._potentialStuns.keys():
                    if self._potentialStuns.has_key(k) and self._potentialStuns[k] is not None:
                        self._potentialStuns[k].cancel()
                        self._potentialStuns[k] = None
                resdict = _parseStunResponse(dgram, address, self.expectedTID,
                                                self.oldTIDs)
                if not resdict:
                    return
                self.handleStunState1(resdict, address)
            else:
                # We already have a working STUN server to play with.
                pass
            return
        resdict = _parseStunResponse(dgram, address, self.expectedTID,
                                                self.oldTIDs)
        if not resdict:
            return
        if STUNVERBOSE:
            print 'calling handleStunState%s'%(self._stunState)
        getattr(self, 'handleStunState%s'%(self._stunState))(resdict, address)

    def handleStunState1(self, resdict, address):
        self.__dict__.update(resdict)

        if self.externalAddress and self._altStunAddress:
            if self.localAddress == self.externalAddress[0]:
                self.stateChanged(self._stunState, '2a')
                self._stunState = '2a'
            else:
                self.stateChanged(self._stunState, '2b')
                self._stunState = '2b'
            self.expectedTID = tid = getRandomTID()
            self.oldTIDs.add(tid)
            self.state2DelayedCall = reactor.callLater(INITIAL_TIMEOUT,
                                                self.retransmitStunState2,
                                                address, tid)
            self.sendRequest(address, tid, avpairs=(
                                    ('CHANGE-REQUEST', CHANGE_BOTH),))

    def handleStunState2a(self, resdict, address):
        self.state2DelayedCall.cancel()
        del self.state2DelayedCall
        if STUNVERBOSE:
            print "2a", resdict
        self.natType = NatTypeNone
        self._finishedStun()

    def handleStunState2b(self, resdict, address):
        self.state2DelayedCall.cancel()
        del self.state2DelayedCall
        if STUNVERBOSE:
            print "2b", resdict
        self.natType = NatTypeFullCone
        self._finishedStun()

    def retransmitStunState2(self, address, tid, count=1):
        # <AP>
        if self._finished:
            return
        # </AP>
        if count <= MAX_RETRANSMIT:
            t = BACKOFF_TIME * 2**min(count, MAX_BACKOFF)
            self.state2DelayedCall = reactor.callLater(t,
                                                    self.retransmitStunState2,
                                                    address, tid, count+1)
            self.sendRequest(address, tid, avpairs=(
                                    ('CHANGE-REQUEST', CHANGE_BOTH),))
        elif self._stunState == '2a':
            self.natType = NatTypeSymUDP
            self._finishedStun()
        else: # 2b
            # Off to state 3 we go!
            self.stateChanged(self._stunState, '3')
            self._stunState = '3'
            self.state3DelayedCall = reactor.callLater(INITIAL_TIMEOUT,
                                                    self.retransmitStunState3,
                                                    address, tid)
            self.expectedTID = tid = getRandomTID()
            self.oldTIDs.add(tid)
            self.sendRequest(self._altStunAddress, tid)

    def handleStunState3(self, resdict, address):
        self.state3DelayedCall.cancel()
        del self.state3DelayedCall
        if STUNVERBOSE:
            print "3", resdict
        if self.externalAddress == resdict['externalAddress']:
            # State 4! wheee!
            self.stateChanged(self._stunState, '4')
            self._stunState = '4'
            self.expectedTID = tid = getRandomTID()
            self.oldTIDs.add(tid)
            self.state4DelayedCall = reactor.callLater(INITIAL_TIMEOUT,
                                                self.retransmitStunState4,
                                                address, tid)
            self.expectedTID = tid = getRandomTID()
            self.oldTIDs.add(tid)
            self.sendRequest(address, tid, avpairs=(
                                    ('CHANGE-REQUEST', CHANGE_PORT),))
        else:
            self.natType = NatTypeSymmetric
            self._finishedStun()

    def retransmitStunState3(self, address, tid, count=1):
        # <AP>
        if self._finished:
            return
        # </AP>
        if count <= (2 * MAX_RETRANSMIT):
            t = BACKOFF_TIME * 2**min(count, MAX_BACKOFF)
            self.state3DelayedCall = reactor.callLater(t,
                                                    self.retransmitStunState3,
                                                    address, tid, count+1)
            self.sendRequest(self._altStunAddress, tid)
        else:
            log.err("STUN Failed in state 3, retrying")
            # We should do _something_ here. a new type BrokenNAT?
            self.stunDiscoveryRetries = self.stunDiscoveryRetries + 1
            if self.stunDiscoveryRetries < 5:
                reactor.callLater(0.2, self.startDiscovery)

    def handleStunState4(self, resdict, address):
        self.state4DelayedCall.cancel()
        del self.state4DelayedCall
        self.natType = NatTypeRestrictedCone
        self._finishedStun()

    def retransmitStunState4(self, address, tid, count = 1):
        # <AP>
        if self._finished:
            return
        # </AP>
        if count < MAX_RETRANSMIT:
            t = BACKOFF_TIME * 2**min(count, MAX_BACKOFF)
            self.state4DelayedCall = reactor.callLater(t,
                                                    self.retransmitStunState4,
                                                    address, tid, count+1)
            self.sendRequest(address, tid, avpairs=(
                                    ('CHANGE-REQUEST', CHANGE_PORT),))
        else:
            self.natType = NatTypePortRestricted
            self._finishedStun()


    def _finishedStun(self):
        if self.timerTask and not self.timerTask.called and not self.timerTask.cancelled:
            self.timerTask.cancel()
            self.timerTask = None 
        self._finished = True
        self.finishedStun()

    def finishedStun(self):
        # Override in a subclass
        if STUNVERBOSE:
            print "firewall type is", self.natType

    def startDiscovery(self):
        from nat import isBogusAddress, getLocalIPAddress
        if _ForceStunType is not None:
            self.natType = _ForceStunType
            reactor.callLater(0, self._finishedStun)
            return
        if not self.transport:
            self.natType = _ForceStunType
            reactor.callLater(0, self._finishedStun)
            return
        localAddress = self.transport.getHost().host
        if STUNVERBOSE:
            print 'startDiscovery, localAddres =', localAddress
        if isBogusAddress(localAddress):
            d = getLocalIPAddress()
            d.addCallback(self._resolveStunServers)
            # d.addErrback(self._hostNotResolved, localAddress)
            d.addErrback(lambda x: self._finishedStun())
        else:
            self._resolveStunServers(localAddress)
            self.timerTask = reactor.callLater(self.timeout, self._timeout, localAddress)

    def _hostNotResolved(self, x, localAddress):
#        if self.timerTask and not self.timerTask.called and not self.timerTask.cancelled:
#            self.timerTask.cancel() 
#            self.timerTask = None
        if STUNVERBOSE:
            print '_hostNotResolved', str(x).replace('\n', '')
        self.not_resolved_servers += 1
        if len(self.servers) == self.not_resolved_servers:
            self._finishedStun()

    def _resolveStunServers(self, localAddress):
        self.localAddress = localAddress
        # reactor.resolve the hosts!
        self.not_resolved_servers = 0
        for host, port in self.servers:
##            print '_resolveStunServers', host, port
            d = reactor.resolve(host)
            d.addCallback(lambda x,p=port: self.initialStunRequest((x, p)))
            d.addErrback(self._hostNotResolved, (host, port))

    def _timeout(self, localAddress):
#        if STUNVERBOSE:
#            print '_timeout'
        self._hostNotResolved('timeout %d seconds' % self.timeout, localAddress)
        

# class StunHook(_StunBase):
#     """Hook a StunHook into a UDP protocol object, and it will discover
#        STUN settings for it.
#
#        You should probably use the NATMapper approach rather than using
#        StunHook directly.
#     """
#     def __init__(self, prot, servers=DefaultServers, *args, **kwargs):
#         self._protocol = prot
#         self._pending = {}
#         self.servers = servers
#         self.expectedTID = None
#         self.oldTIDs = sets.Set()
#         self._stunState = 'hook'
#         super(StunHook, self).__init__(*args, **kwargs)
#
#     def initialStunRequest(self, address):
#         tid = getRandomTID()
#         self.oldTIDs.add(tid)
#         delayed = reactor.callLater(INITIAL_TIMEOUT,
#                                     self.retransmitInitial, address, tid)
#         self._pending[tid] = delayed
#         self.sendRequest(address, tid=tid)
#
#     def retransmitInitial(self, address, tid, count=1):
#         if count <= MAX_RETRANSMIT:
#             t = BACKOFF_TIME * 2**min(count, MAX_BACKOFF)
#             delayed = reactor.callLater(t, self.retransmitInitial,
#                                             address, tid, count+1)
#             self._pending[tid] = delayed
#             self.sendRequest(address, tid=tid)
#         else:
#             if STUNVERBOSE:
#                 print "giving up on %r"%(address,)
#             del self._potentialStuns[tid]
#             if not self._potentialStuns:
#                 if STUNVERBOSE:
#                     print "stun state 1 timeout - no internet UDP possible"
#                 self.natType = NatTypeUDPBlocked
#                 self.finishedStun()
#
#     def datagramReceived(self, dgram, address):
#         if STUNVERBOSE:
#             print "hook got a datagram from", address
#         if self.deferred is None:
#             # We're already done
#             return
#
#         mt, pktlen, tid = struct.unpack('!hh16s', dgram[:20])
#         if self._pending.has_key(tid):
#             delayed = self._pending[tid]
#             if delayed is not None:
#                 delayed.cancel()
#             del self._pending[tid]
#             resdict = _parseStunResponse(dgram, address,
#                                                 oldtids=self.oldTIDs)
#             if not resdict or not resdict.get('externalAddress'):
#                 # Crap response, ignore it.
#                 return
#
#             # Got a valid response. Clean up around here first.
#             self.uninstallStun()
#             # kill any pending retransmits
#             for delayed in self._pending.values():
#                 if delayed is not None:
#                     delayed.cancel()
#             # send response
#             d, self.deferred = self.deferred, None
#             d.callback(resdict['externalAddress'])
#
#     def installStun(self):
#         self._protocol._mp_datagramReceived = self._protocol.datagramReceived
#         self._protocol.datagramReceived = self.datagramReceived
#         self.transport = self._protocol.transport
#
#     def discoverAddress(self):
#         """ Sniff out external address. Returns a deferred with the external
#             address as a 2-tuple (ip, port)
#         """
#         from twisted.internet import defer
#         self.installStun()
#         self.deferred = defer.Deferred()
#         for host, port in self.servers[:3]:
#             d = reactor.resolve(host)
#             d.addCallback(lambda x, p=port: self.initialStunRequest((x, p)))
#         return self.deferred
#
#     def uninstallStun(self):
#         self._protocol.datagramReceived = self._protocol._mp_datagramReceived
#         del self.transport

class _DetectSTUNProt(StunDiscoveryProtocol):
    d = None
    def finishedStun(self):
        self.d.callback(self.natType)

_cached_stuntype = None

def _getSTUN():
    #print "getSTUN triggering startDiscovery!"
    if _cached_stuntype is not None:
        return defer.succeed(_cached_stuntype)
    stunClient = _DetectSTUNProt()
    stunClient.d = defer.Deferred()
    l = reactor.listenUDP(0, stunClient)
    reactor.callLater(0, stunClient.startDiscovery)
    def _stundone(x, l=l):
        global _cached_stuntype
        _cached_stuntype = x
        l.stopListening()
        return x
    stunClient.d.addCallback(_stundone)
    return stunClient.d

getSTUN = DeferredCache(_getSTUN)

# _cached_mapper = None
# def getMapper():
#     global _cached_mapper
#     if _cached_mapper is None:
#         _cached_mapper = STUNMapper()
#     return _cached_mapper
#
# def clearCache():
#     global _cached_mapper, _cached_stuntype
#     _cached_stuntype = None
#     _cached_mapper = None
#     getSTUN.clearCache()
#
# class STUNMapper(BaseMapper):
#     __implements__ = INATMapper
#     _ptypes = [ 'UDP', ]
#     def __init__(self):
#         self._mapped = {}
#
#     def map(self, port):
#         "See shtoom.interfaces.NATMapper.map"
#         self._checkValidPort(port)
#         cd = defer.Deferred()
#         self._mapped[port] = cd
#         d = getSTUN()
#         d.addCallback(lambda x: self._cb_map_gotSTUN(x, port))
#         return cd
#     map = DeferredCache(map, inProgressOnly=True)
#
#     def _cb_map_gotSTUN(self, stun, port):
#         if not stun.useful:
#             cd = self._mapped[port]
#             del self._mapped[port]
#             cd.errback(ValueError('%r means STUN is useless'%(stun,)))
#             return
#         SH = StunHook(port.protocol)
#         d = SH.discoverAddress()
#         d.addCallback(lambda x: self._cb_map_discoveredAddress(x, port))
#     map = DeferredCache(map, inProgressOnly=True)
#
#     def _cb_map_discoveredAddress(self, addr, port):
#         cd = self._mapped[port]
#         self._mapped[port] = addr
#         cd.callback(addr)
#
#     def info(self, port):
#         "See shtoom.interfaces.NATMapper.info"
#         if port in self._mapped:
#             return self._mapped[port]
#         else:
#             raise ValueError('Port %r is not currently mapped'%(port))
#
#     def unmap(self, port):
#         "See shtoom.interfaces.NATMapper.unmap"
#         # A no-op for STUN
#         if port not in self._mapped:
#             raise ValueError('Port %r is not currently mapped'%(port))
#         del self._mapped[port]
#         return defer.succeed(None)


if __name__ == "__main__":
    STUNVERBOSE=True
    log.FileLogObserver.timeFormat = "%H:%M:%S"
    import sys
    class TestStunDiscoveryProtocol(StunDiscoveryProtocol):

        def finishedStun(self):
            print "STUN finished, results:"
            print "You're behind a %r"%(self.natType)
            if self.natType is NatTypeSymmetric:
                print "You're going to have to use an outbound proxy"
            else:
                print "and external address is %r" % (self.externalAddress,)
            reactor.stop()


    stunClient = TestStunDiscoveryProtocol()
    log.startLogging(sys.stdout)
    try:
        reactor.listenUDP(5061, stunClient)
    except:
        reactor.listenUDP(0, stunClient)
    #reactor.callLater(20, stunClient.stunTimedOut)
    reactor.callLater(0, stunClient.startDiscovery)
    reactor.run()



"""

Copied from RFC 3489


                        +--------+
                        |  Test  | S:1
                        |   I    |
                        +--------+
                             |
                             |
                             V             S:1a
                            /\              /\
                         N /  \ Y          /  \ Y             +--------+
          UDP     <-------/Resp\--------->/ IP \------------->|  Test  | S:2a
          Blocked         \ ?  /          \Same/              |   II   |
                           \  /            \? /               +--------+
                            \/              \/                    |
                                             | N                  |
                                             |                    V
                                             V                    /\
                                         +--------+  Sym.      N /  \
                                    S:2b |  Test  |  UDP    <---/Resp\
                                         |   II   |  Firewall   \ ?  /
                                         +--------+              \  /
                                             |                    \/
                                             V                     |Y
                  /\           S:3           /\                    |
   Symmetric  N  /  \       +--------+   N  /  \                   V
      NAT  <--- / IP \<-----|  Test  |<--- /Resp\               Open
                \Same/      |   III  |     \ ?  /               Internet
                 \? /       +--------+      \  /
                  \/                         \/
                  |                           |Y
                  |                           |
                  |                           V
                  |                           Full
                  |                           Cone
                  V              /\
              +--------+        /  \ Y
         S:4  |  Test  |------>/Resp\---->Restricted
              |    IV  |       \ ?  /
              +--------+        \  /
                                 \/
                                  |N
                                  |       Port
                                  +------>Restricted

                 Figure 2: Flow for type discovery process

Test I: A Binding Request with no change port/change ip
Test II: A Binding Request with change port & change ip
Test III: A Binding Request with no change port/change ip, sent to the
          address from CHANGED-ADDRESS in response to Test I.
Test IV: A Binding Request with change port

"""
