
# Code for NATs and the like. Also includes code for determining local IP
# address (suprisingly tricky, in the presence of STUPID STUPID STUPID
# networking stacks)

from twisted.internet import defer
from twisted.internet.protocol import DatagramProtocol
import random, socket
from twisted.python import log
from defcache import DeferredCache

# from shtoom.interfaces import StunPolicy as IStunPolicy

_Debug = False

class LocalNetworkMulticast(DatagramProtocol, object):

    def __init__(self, *args, **kwargs):
        self.compDef = defer.Deferred()
        self.completed = False
        super(LocalNetworkMulticast,self).__init__(*args, **kwargs)

    def listenMulticast(self):
        from twisted.internet import reactor
        from twisted.internet.error import CannotListenError
        attempt = 0
        port = 11000 + random.randint(0,5000)
        while True:
            try:
                mcast = reactor.listenMulticast(port, self)
                break
            except CannotListenError:
                port = 11000 + random.randint(0,5000)
                attempt += 1
                if _Debug:
                    print "listenmulticast failed, trying", port
        if attempt > 5:
            log.msg("warning: couldn't listen ony mcast port", system='network')
            d, self.compDef = self.compDef, None
            d.callback(None)
        dd = mcast.joinGroup('239.255.255.250', socket.INADDR_ANY)
        def _cb(x):
            if _Debug:
                print 'multicast group joined'
        def _eb(x):
            if _Debug:
                print 'multicast group join failed', x
            self.completed = True
            self.compDef.errback(x)
        dd.addCallback(_cb)
        dd.addErrback(_eb)
        self.mcastPort = port

    def blatMCast(self):
        try:
            # XXX might need to set an option to make sure we see our own packets
            self.transport.write('ping', ('239.255.255.250', self.mcastPort))
            self.transport.write('ping', ('239.255.255.250', self.mcastPort))
            self.transport.write('ping', ('239.255.255.250', self.mcastPort))
        except:
            pass

    def datagramReceived(self, dgram, addr):
        if self.completed:
            return
        elif dgram != 'ping':
            return
        else:
            self.completed = True
            d, self.compDef = self.compDef, None
            d.callback(addr[0])

_cachedLocalIP = None
def _cacheLocalIP(res):
    global _cachedLocalIP
    if _Debug: print "caching value", res
    _cachedLocalIP = res
    return res

# If there's a need to clear the cache, call this method (e.g. DHCP client)
def _clearCachedLocalIP():
    _cacheLocalIP(None)

def _getLocalIPAddress():
    # So much pain. Don't even bother with
    # socket.gethostbyname(socket.gethostname()) - the number of ways this
    # is broken is beyond belief.
    from twisted.internet import reactor
    global _cachedLocalIP
    if _Debug:
        print '_getLocalIPAddress', _cachedLocalIP
    if _cachedLocalIP is not None:
        return defer.succeed(_cachedLocalIP)
    # first we try a connected udp socket
    if _Debug: 
        print "resolving A.ROOT-SERVERS.NET"
    ret = defer.Deferred()
    d = reactor.resolve('A.ROOT-SERVERS.NET')
    d.addCallback(_getLocalIPAddressViaConnectedUDP, ret)
    d.addErrback(_noDNSerrback, ret)
    return ret

getLocalIPAddress = DeferredCache(_getLocalIPAddress)

# def clearCache():
#     "Clear cached NAT settings (e.g. when moving to a different network)"
#     from shtoom.upnp import clearCache as uClearCache
#     from shtoom.stun import clearCache as sClearCache
#     print "clearing all NAT caches"
#     getLocalIPAddress.clearCache()
#     getMapper.clearCache()
#     uClearCache()
#     sClearCache()

def _noDNSerrback(failure, ret):
    # No global DNS? What the heck, it's possible, I guess.
    if _Debug: 
        print "no DNS, trying multicast"
    d = _getLocalIPAddressViaMulticast(ret)
    

def _getLocalIPAddressViaConnectedUDP(ip, ret):
    from twisted.internet import reactor
    from twisted.internet.protocol import DatagramProtocol
    if _Debug: 
        print "connecting UDP socket to", ip
    prot = DatagramProtocol()
    p = reactor.listenUDP(0, prot)
    try:
        res = prot.transport.connect(ip, 7)
    except:
        if _Debug: 
            print "can not connect to %s:%d" % ( ip, 7 )
        return _getLocalIPAddressViaMulticast(ret)
    locip = prot.transport.getHost().host
    p.stopListening()
    del prot, p
    if _Debug: 
        print "connected UDP socket says", locip
    if isBogusAddress(locip):
        # #$#*(&??!@#$!!!
        if _Debug: 
            print "connected UDP socket gives crack, trying mcast instead"
        return _getLocalIPAddressViaMulticast(ret)
    else:
        return ret.callback(locip) 


def _getLocalIPAddressViaMulticast(ret):
    # We listen on a new multicast address (using UPnP group, and
    # a random port) and send out a packet to that address - we get
    # our own packet back and get the address from it.
    from twisted.internet import reactor
    from twisted.internet.interfaces import IReactorMulticast
    try:
        IReactorMulticast(reactor)
    except:
        if _Debug: 
            print "no multicast support in reactor"
        log.msg("warning: no multicast in reactor", system='network')
        return ret.callback('0.0.0.0')
    locprot = LocalNetworkMulticast()
    def _cb(x, ret):
        _cacheLocalIP(x)
        ret.callback(x)
    def _eb(x, ret):
        if _Debug:
            print 'multicast failed'
        ret.callback('0.0.0.0')
    try:
        locprot.compDef.addCallback(_cb, ret)
        locprot.compDef.addErrback(_eb, ret)
        if _Debug: 
            print "listening to multicast"
        locprot.listenMulticast()
        if _Debug: 
            print "sending multicast packets"
        locprot.blatMCast()
    except:
        ret.callback('0.0.0.0')
    # return locprot.compDef

# def cb_detectNAT(res):
#     (ufired,upnp), (sfired,stun) = res
#     if not ufired and not sfired:
#         log.msg("no STUN or UPnP results", system="nat")
#         return None
#     if ufired:
#         return upnp
#     return stun
#
# def detectNAT():
#     # We prefer UPnP when available, as it's less pissing about (ha!)
#     from shtoom.upnp import getUPnP
#     from shtoom.stun import getSTUN
#     ud = getUPnP()
#     sd = getSTUN()
#     dl = defer.DeferredList([ud, sd])
#     dl.addCallback(cb_detectNAT).addErrback(log.err)
#     return dl
#
# def cb_getMapper(res):
#     from shtoom.upnp import getMapper as getUMapper
#     from shtoom.stun import getMapper as getSTUNMapper
#     (ufired,upnp), (sfired,stun) = res
#     log.msg("detectNAT got %r"%res, system="nat")
#     if not upnp and not stun:
#         log.msg("no STUN or UPnP results", system="nat")
#         return getNullMapper()
#     if upnp:
#         log.msg("using UPnP mapper", system="nat")
#         return getUMapper()
#     if stun.useful:
#         log.msg("using STUN mapper", system="nat")
#         return getSTUNMapper()
#     log.msg("No UPnP, and STUN is useless", system="nat")
#     return getNullMapper()
#
# _forcedMapper = None
#
# _installedShutdownHook = False
# def getMapper():
#     # We prefer UPnP when available, as it's more robust
#     global _installedShutdownHook
#     if not _installedShutdownHook:
#         from twisted.internet import reactor
#         t = reactor.addSystemEventTrigger('after',
#                                           'shutdown',
#                                           clearCache)
#         _installedShutdownHook = True
#     try:
#         from __main__ import app
#     except:
#         app = None
#     natPref = 'both'
#     if app is not None:
#         print "app is", app
#         natPref = app.getPref('nat')
#         log.msg('NAT preference says to use %s'%(natPref))
#     if _forcedMapper is not None:
#         return defer.succeed(_forcedMapper)
#     from shtoom.upnp import getUPnP
#     from shtoom.stun import getSTUN
#     if natPref == 'both':
#         ud = getUPnP()
#         sd = getSTUN()
#         d = defer.DeferredList([ud, sd])
#     elif natPref == 'upnp':
#         ud = getUPnP()
#         d = defer.DeferredList([ud, defer.succeed(None) ])
#     elif natPref == 'stun':
#         ud = getSTUN()
#         d = defer.DeferredList([defer.succeed(None), sd])
#     else:
#         nm = NullMapper()
#         d = defer.DeferredList([defer.succeed(None),
#                                 defer.succeed(None)])
#     d.addCallback(cb_getMapper).addErrback(log.err)
#     return d
# getMapper = DeferredCache(getMapper, inProgressOnly=False)
#
# def _forceMapper(mapper):
#     global _forcedMapper
#     _forcedMapper = mapper

def isBogusAddress(addr):
    """ Returns true if the given address is bogus, i.e. 0.0.0.0 or
        127.0.0.1. Additional forms of bogus might be added later.
    """
    if addr.startswith('0.') or addr.startswith('127.'):
        return True
    return False

# class BaseMapper:
#     "Base class with useful functionality for Mappers"
#     _ptypes = []
#
#     def _checkValidPort(self, port):
#         from twisted.internet.base import BasePort
#         # Ugh. Why is there no IPort ?
#         if not isinstance(port, BasePort):
#             raise ValueError("expected a Port, got %r"%(port))
#         # XXX Check it's listening! How???
#         if not hasattr(port, 'socket'):
#             raise ValueError("Port %r appears to be closed"%(port))
#
#         locAddr = port.getHost()
#         if locAddr.type not in self._ptypes:
#             raise ValueError("can only map %s, not %s"%
#                         (', '.join(self._ptypes),locAddr.type))
#         if locAddr.port == 0:
#             raise ValueError("Port %r has port number of 0"%(port))
#
#         if not port.connected:
#             raise ValueError("Port %r is not listening"%(port))
#
# class NullMapper(BaseMapper):
#     "Mapper that does nothing"
#
#     _ptypes = ( 'TCP', 'UDP' )
#
#     def __init__(self):
#         self._mapped = {}
#
#     def map(self, port):
#         "See shtoom.interfaces.NATMapper.map"
#         self._checkValidPort(port)
#         if port in self._mapped:
#             return defer.succeed(self._mapped[port])
#         cd = defer.Deferred()
#         self._mapped[port] = cd
#         locAddr = port.getHost().host
#         if isBogusAddress(locAddr):
#             # lookup local IP.
#             d = getLocalIPAddress()
#             d.addCallback(lambda x: self._cb_map_gotLocalIP(x, port))
#         else:
#             reactor.callLater(0, lambda: self._cb_map_gotLocalIP(locAddr, port))
#         return cd
#     map = DeferredCache(map, inProgressOnly=True)
#
#     def _cb_map_gotLocalIP(self, locIP, port):
#         cd = self._mapped[port]
#         self._mapped[port] = (locIP, port.getHost().port)
#         cd.callback(self._mapped[port])
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
#         # A no-op for NullMapper
#         if port not in self._mapped:
#             raise ValueError('Port %r is not currently mapped'%(port))
#         del self._mapped[port]
#         return defer.succeed(None)
#
# _cached_nullmapper = None
# def getNullMapper():
#     global _cached_nullmapper
#     if _cached_nullmapper is None:
#         _cached_nullmapper = NullMapper()
#     return _cached_nullmapper
#
# class NetAddress:
#     """ A class that represents a net address of the form
#         foo/nbits, e.g. 10/8, or 192.168/16, or whatever
#     """
#     def __init__(self, netaddress):
#         parts = netaddress.split('/')
#         if len(parts) > 2:
#             raise ValueError, "should be of form address/mask"
#         if len(parts) == 1:
#             ip, mask = parts[0], 32
#         else:
#             ip, mask = parts[0], int(parts[1])
#         if mask < 0 or mask > 32:
#             raise ValueError, "mask should be between 0 and 32"
#
#         self.net = self.inet_aton(ip)
#         self.mask = ( 2L**32 -1 ) ^ ( 2L**(32-mask) - 1 )
#         self.start = self.net
#         self.end = self.start | (2L**(32-mask) - 1)
#
#     def inet_aton(self, ipstr):
#         "A sane inet_aton"
#         if ':' in ipstr:
#             return
#         net = [ int(x) for x in ipstr.split('.') ] + [ 0,0,0 ]
#         net = net[:4]
#         return  ((((((0L+net[0])<<8) + net[1])<<8) + net[2])<<8) +net[3]
#
#     def inet_ntoa(self, ip):
#         import socket, struct
#         return socket.inet_ntoa(struct.pack('!I',ip))
#
#     def __repr__(self):
#         return '<NetAddress %s/%s (%s-%s) at %#x>'%(self.inet_ntoa(self.net),
#                                            self.inet_ntoa(self.mask),
#                                            self.inet_ntoa(self.start),
#                                            self.inet_ntoa(self.end),
#                                            id(self))
#
#     def check(self, ip):
#         "Check if an IP or network is contained in this network address"
#         if isinstance(ip, NetAddress):
#             return self.check(ip.start) and self.check(ip.end)
#         if isinstance(ip, basestring):
#             ip = self.inet_aton(ip)
#         if ip is None:
#             return False
#         if ip & self.mask == self.net:
#             return True
#         else:
#             return False
#
#     __contains__ = check
#
#
# class AlwaysStun:
#     __implements__ = IStunPolicy
#
#     def checkStun(self, localip, remoteip):
#         return True
#
# class NeverStun:
#     __implements__ = IStunPolicy
#
#     def checkStun(self, localip, remoteip):
#         return False
#
# class RFC1918Stun:
#     "A sane default policy"
#     __implements__ = IStunPolicy
#
#     addresses = ( NetAddress('10/8'),
#                   NetAddress('172.16/12'),
#                   NetAddress('192.168/16'),
#                   NetAddress('127/8') )
#     localhost = NetAddress('127/8')
#
#     def checkStun(self, localip, remoteip):
#         localIsRFC1918 = False
#         remoteIsRFC1918 = False
#         remoteIsLocalhost = False
#         # Yay. getPeer() returns a name, not an IP
#         #  XXX tofix: grab radix's goodns.py until it
#         # lands in twisted proper.
#         # Until then, use this getaddrinfo() hack.
#         if not remoteip:
#             return None
#         if remoteip[0] not in '0123456789':
#             import socket
#             try:
#                 ai = socket.getaddrinfo(remoteip, None)
#             except (socket.error, socket.gaierror):
#                 return None
#             remoteips = [x[4][0] for x in ai]
#         else:
#             remoteips = [remoteip,]
#         for net in self.addresses:
#             if localip in net:
#                 localIsRFC1918 = True
#             # See comments above. Worse, if the host has an address that's
#             # RFC1918, and externally advertised (which is wrong, and broken),
#             # the STUN check will be incorrect. Bah.
#             for remoteip in remoteips:
#                 if remoteip in net:
#                     remoteIsRFC1918 = True
#                 if remoteip in self.localhost:
#                     remoteIsLocalhost = True
#         if localIsRFC1918 and not (remoteIsRFC1918 or remoteIsLocalhost):
#             return True
#         else:
#             return False
#
# _defaultPolicy = RFC1918Stun()
# def installPolicy(policy):
#     global _defaultPolicy
#     _defaultPolicy = policy
#
# def getPolicy():
#     return _defaultPolicy



if __name__ == "__main__":
#     from twisted.internet import gtk2reactor
#     gtk2reactor.install()
    from twisted.internet import reactor
    import sys

    log.FileLogObserver.timeFormat = "%H:%M:%S"
    log.startLogging(sys.stdout)

    def cb_gotip(addr):
        print "got local IP address of", addr
#     def cb_gotnat(res):
#         print "got NAT of", res
    d1 = getLocalIPAddress().addCallback(cb_gotip)
#     d2 = detectNAT().addCallback(cb_gotnat)
#     dl = defer.DeferredList([d1,d2])
#     dl.addCallback(lambda x:reactor.stop())
    d1.addCallback(lambda x:reactor.stop())
    reactor.run()
