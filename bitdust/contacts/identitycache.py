#!/usr/bin/python
# identitycache.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (identitycache.py) is part of BitDust Software.
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
"""
.. module:: identitycache.

Here we store a local copies of identities. This fetches identities off
the web and stores an XML copy in file and an identity object in a
dictionary. Other parts of BitDust call this to get an identity using an
IDURL. So this is a local cache of user ID's.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 24

#------------------------------------------------------------------------------

import sys
import time

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred, DeferredList, CancelledError

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import net_misc
from bitdust.lib import nameurl
from bitdust.lib import strng

from bitdust.userid import identity
from bitdust.userid import id_url

from bitdust.contacts import identitydb

from bitdust.p2p import p2p_stats

#------------------------------------------------------------------------------

_CachingTasks = {}
_LastTimeCached = {}
_OverriddenIdentities = {}

#-------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'identitycache.init')
    identitydb.clear()


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'identitycache.shutdown')


#------------------------------------------------------------------------------


def caching():
    global _CachingTasks
    return _CachingTasks


def add_callback(idurl, ignore_errors=False):
    idurl = id_url.to_original(idurl)
    defer_obj = Deferred()
    defer_obj.addErrback(on_caching_task_failed, idurl, ignore_errors)
    if idurl not in caching():
        caching()[idurl] = []
    caching()[idurl].append(defer_obj)
    return defer_obj


#------------------------------------------------------------------------------


def get_one(idurl):
    """
    An alias for `FromCache()` method.
    """
    return FromCache(id_url.to_original(idurl))


def start_one(idurl, timeout=15, try_other_sources=True):
    """
    An alias for `immediatelyCaching()` method.
    """
    return immediatelyCaching(id_url.to_original(idurl), timeout=timeout, try_other_sources=try_other_sources)


def start_multiple(idurl_list, timeout=15, try_other_sources=True):
    """
    Executes in parallel multiple `immediatelyCaching()` calls on the list of IDURL items.
    Returns `DeferredList` object.
    """
    idurl_list = list(set(id_url.to_original_list(idurl_list)))
    dl = []
    for idurl in idurl_list:
        if idurl:
            dl.append(immediatelyCaching(idurl, timeout=timeout, try_other_sources=try_other_sources))
    return DeferredList(dl, consumeErrors=True)


#------------------------------------------------------------------------------


def Clear(excludeList=None):
    """
    Clear all cached identities.
    """
    identitydb.clear(excludeList)


def CacheLen():
    """
    Return a number of items in the cache.
    """
    return identitydb.size()


def PrintID(idurl):
    """
    For debug, print an item from cache.
    """
    identitydb.print_id(idurl)


def PrintCacheKeys():
    """
    For debug, print all items keys in the cache.
    """
    identitydb.print_keys()


def PrintAllInCache():
    """
    For debug, print completely all cache.
    """
    identitydb.print_cache()


def Items():
    return identitydb.cache()


def HasKey(idurl):
    """
    Check for some user IDURL in the cache.
    """
    return identitydb.has_idurl(idurl) or IsOverridden(idurl)


def GetLastModifiedTime(idurl):
    return identitydb.get_last_modified_time(idurl)


def HasFile(idurl):
    return identitydb.has_file(idurl)


def FromCache(idurl):
    """
    Get identity object from cache.
    """
    if IsOverridden(idurl):
        overridden_xmlsrc = ReadOverriddenIdentityXMLSource(idurl)
        if overridden_xmlsrc:
            if _Debug:
                lg.out(_DebugLevel, '        returning overridden identity (%d bytes) for %s' % (len(overridden_xmlsrc), idurl))
            return identity.identity(xmlsrc=overridden_xmlsrc)
    return identitydb.get_ident(idurl)


def GetLatest(idurl):
    """
    Returns latest copy from cache or fire `immediatelyCaching`,
    result is a `Deferred` object.
    """
    idurl = id_url.to_original(idurl)
    known = FromCache(idurl)
    result = Deferred()
    if known:
        result.callback(known)
    else:
        d = immediatelyCaching(idurl)
        d.addCallback(lambda _: result.callback(FromCache(idurl)))
        d.addErrback(lambda err: result.errback(err) and None)
    return result


def GetPublicKey(idurl):
    """
    If given `idurl` is known will return public key from the corresponding identity file otherwise `None`.
    """
    ident = FromCache(idurl)
    if not ident:
        return None
    return ident.getPublicKey()


def GetIDURLsByContact(contact):
    """
    In the ``identitydb`` code we keep track of all identity objects and
    prepare an index of all known contacts.

    So we can try to detect who is sending us a packet when got a packet
    from known contact address. This is to get a list of known ID's in
    the cache for that contact.
    """
    return identitydb.get_idurls_by_contact(contact)


def GetIDURLByIPPort(ip, port):
    """
    Same as previous method but the index is created from IP:PORT parts of
    identities contacts.
    """
    return identitydb.get_idurl_by_ip_port(ip, port)


def GetContacts(idurl):
    """
    This is another one index - return a set of contacts for given IDURL.
    Instead of read identity object and parse it every time - this method can be used.
    This is a "cached" info.
    """
    return identitydb.idcontacts(idurl)


def Remove(idurl):
    """
    Remove an item from cache.
    """
    return identitydb.remove(idurl)


def UpdateAfterChecking(idurl, xml_src):
    """
    Need to call that method to update the cache when some identity sources is
    changed.
    """
    return identitydb.update(idurl, xml_src)


def RemapContactAddress(address):
    """
    For local peers in same sub network we need to use local IP, not external
    IP. We pass local IP to transports to send packets inside sub network.

    TODO: Would be great to get rid of that - transport must keep track of local and external situations.
    So this is another index - IDURL to local IP, see identitydb.
    """
    idurl = GetIDURLByIPPort(address[0], address[1])
    if idurl is not None and HasLocalIP(idurl):
        newaddress = (GetLocalIP(idurl), address[1])
        if _Debug:
            lg.out(_DebugLevel, 'identitycache.RemapContactAddress for %s [%s] -> [%s]' % (nameurl.GetName(idurl), str(address), str(newaddress)))
        return newaddress
    return address


def OverrideIdentity(idurl, xml_src):
    """
    Used by proxy router to remember the original identity of the routing node.
    """
    global _OverriddenIdentities
    idurl = id_url.field(idurl)
    if not idurl.is_latest():
        if idurl.original() in _OverriddenIdentities:
            if idurl.to_bin() not in _OverriddenIdentities:
                _OverriddenIdentities[idurl.to_bin()] = _OverriddenIdentities.pop(idurl.original())
                lg.info('detected and processed idurl rotate for overridden identity : %r -> %r' % (idurl.original(), idurl.to_bin()))
    idurl = id_url.to_bin(idurl)
    xml_src = strng.to_text(xml_src.strip())
    if idurl in _OverriddenIdentities:
        if _OverriddenIdentities[idurl] == xml_src:
            if _Debug:
                lg.out(_DebugLevel, 'identitycache.OverrideIdentity SKIPPED "%s", no changes' % idurl)
            return False
        if _Debug:
            lg.out(_DebugLevel, 'identitycache.OverrideIdentity replacing overriden identity %r with new one' % idurl)
            lg.out(_DebugLevel, '\nOVERRIDDEN OLD:\n' + _OverriddenIdentities[idurl])
            lg.out(_DebugLevel, '\nOVERRIDDEN NEW:\n' + xml_src)
    else:
        orig = ''
        if identitydb.has_idurl(idurl):
            orig = identitydb.get_ident(idurl).serialize(as_text=True)
        if orig and orig == xml_src:
            if _Debug:
                lg.out(_DebugLevel, 'identitycache.OverrideIdentity SKIPPED %r , overridden copy is the same as original' % idurl)
            return False
        if _Debug:
            lg.out(_DebugLevel, 'identitycache.OverrideIdentity replacing original identity for %r' % idurl)
            lg.out(_DebugLevel, '\nORIGINAL:\n' + orig)
            lg.out(_DebugLevel, '\nNEW:\n' + xml_src)
    _OverriddenIdentities[idurl] = xml_src
    if _Debug:
        lg.out(_DebugLevel, '    total number of overrides: %d' % len(_OverriddenIdentities))
    return True


def StopOverridingIdentity(idurl):
    global _OverriddenIdentities
    idurl = id_url.field(idurl)
    if not idurl.is_latest():
        if idurl.original() in _OverriddenIdentities:
            if idurl.to_bin() not in _OverriddenIdentities:
                _OverriddenIdentities[idurl.to_bin()] = _OverriddenIdentities.pop(idurl.original())
                lg.info('detected and processed idurl rotate for overridden identity : %r -> %r' % (idurl.original(), idurl.to_bin()))
    idurl = id_url.to_bin(idurl)
    result = _OverriddenIdentities.pop(idurl, None)
    if _Debug:
        lg.out(_DebugLevel, 'identitycache.StopOverridingIdentity   removed overridden source for %s' % idurl)
        if result:
            lg.out(_DebugLevel, '    previous overridden identity was %d bytes' % len(result))
        lg.out(_DebugLevel, '            total number of overrides is %d' % len(_OverriddenIdentities))
    return result


def IsOverridden(idurl):
    global _OverriddenIdentities
    idurl = id_url.field(idurl)
    if not idurl.is_latest():
        if idurl.original() in _OverriddenIdentities:
            if idurl.to_bin() not in _OverriddenIdentities:
                _OverriddenIdentities[idurl.to_bin()] = _OverriddenIdentities.pop(idurl.original())
                lg.info('detected and processed idurl rotate for overridden identity : %r -> %r' % (idurl.original(), idurl.to_bin()))
    idurl = id_url.to_bin(idurl)
    return idurl in _OverriddenIdentities


def ReadOverriddenIdentityXMLSource(idurl):
    global _OverriddenIdentities
    idurl = id_url.field(idurl)
    if not idurl.is_latest():
        if idurl.original() in _OverriddenIdentities:
            if idurl.to_bin() not in _OverriddenIdentities:
                _OverriddenIdentities[idurl.to_bin()] = _OverriddenIdentities.pop(idurl.original())
                lg.info('detected and processed idurl rotate for overridden identity : %r -> %r' % (idurl.original(), idurl.to_bin()))
    idurl = id_url.to_bin(idurl)
    return _OverriddenIdentities.get(idurl, None)


#------------------------------------------------------------------------------


def getPageSuccess(src, idurl):
    """
    This is called when requested identity source gets received.
    """
    UpdateAfterChecking(idurl, src)
    p2p_stats.count_identity_cache(idurl, len(src))
    return src


def getPageFail(x, idurl):
    """
    This is called when identity request is failed.
    """
    if _Debug:
        lg.out(_DebugLevel, 'identitycache.getPageFail NETERROR in request to ' + idurl)
    p2p_stats.count_identity_cache(idurl, 0)
    return x


def pageRequestTwisted(idurl, timeout=15):
    """
    Request an HTML page - this can be an user identity.
    """
    d = net_misc.getPageTwisted(idurl, timeout)
    d.addCallback(getPageSuccess, idurl)
    d.addErrback(getPageFail, idurl)
    return d


def scheduleForCaching(idurl, timeout=15):
    """
    Even if we have a copy in cache we are to try and read another one.
    """
    if _Debug:
        lg.out(_DebugLevel, 'identitycache.scheduleForCaching %r' % idurl)
    return pageRequestTwisted(idurl, timeout)


#------------------------------------------------------------------------------


def last_time_cached(idurl):
    global _LastTimeCached
    idurl = id_url.to_original(idurl)
    if not idurl:
        return None
    return _LastTimeCached.get(idurl, None)


def on_caching_task_failed(err, idurl, ignore_errors):
    if _Debug:
        lg.args(_DebugLevel, idurl=idurl, err=err)
    if ignore_errors:
        return None
    if err.type == CancelledError:
        return None
    return err


def immediatelyCaching(idurl, timeout=15, try_other_sources=True, ignore_errors=False):
    """
    A smart method to cache some identity and get results in callbacks.
    """
    idurl = id_url.to_original(idurl)
    if not idurl:
        raise Exception('can not cache, idurl is empty')

    def _success(src, idurl):
        global _LastTimeCached
        idurl = id_url.to_original(idurl)
        defer_results = caching().pop(idurl, [])
        if _Debug:
            lg.args(_DebugLevel, src=type(src), idurl=idurl, defer_results=len(defer_results))
        if UpdateAfterChecking(idurl, src):
            for result in defer_results:
                if result and not result.called:
                    reactor.callLater(0, result.callback, src)  # @UndefinedVariable
            if _Debug:
                lg.out(_DebugLevel, '[cached] %s' % idurl)
            p2p_stats.count_identity_cache(idurl, len(src))
            _LastTimeCached[idurl] = time.time()
        else:
            for result in defer_results:
                if result and not result.called:
                    reactor.callLater(0, result.errback, Exception(src))  # @UndefinedVariable
            lg.warn('[cache error] %s is not valid' % idurl)
            p2p_stats.count_identity_cache(idurl, 0)
            _LastTimeCached.pop(idurl, None)
        defer_results = []
        del defer_results
        return src

    def _next_source(resp, idurl, sources, pos):
        global _LastTimeCached
        if _Debug:
            lg.args(_DebugLevel, resp=resp, idurl=idurl, pos=pos, sources=len(sources))

        if pos >= len(sources):
            lg.warn('[cache failed] %r and also %d other sources' % (idurl, len(sources)))
            defer_results = caching().pop(idurl, [])
            for result in defer_results:
                if result and not result.called:
                    reactor.callLater(0, result.errback, Exception('cache failed from multiple sources'))  # @UndefinedVariable
            p2p_stats.count_identity_cache(idurl, 0)
            _LastTimeCached.pop(idurl, None)
            defer_results = []
            del defer_results
            return None

        next_idurl = sources[pos]
        next_idurl = id_url.to_original(next_idurl)
        if _Debug:
            lg.args(_DebugLevel, next_idurl=next_idurl)

        d = net_misc.getPageTwisted(url=next_idurl, timeout=timeout)
        d.addCallback(_success, idurl)
        d.addErrback(_next_source, idurl, sources, pos + 1)
        return None

    def _fail(err, idurl):
        global _LastTimeCached
        idurl = id_url.to_original(idurl)
        if _Debug:
            lg.args(_DebugLevel, err=err, idurl=idurl)

        if not try_other_sources:
            p2p_stats.count_identity_cache(idurl, 0)
            _LastTimeCached.pop(idurl, None)
            lg.warn('[cache failed] %s : %s' % (idurl, err.getErrorMessage()))
            defer_results = caching().pop(idurl, [])
            for result in defer_results:
                if result and not result.called:
                    reactor.callLater(0, result.errback, err)  # @UndefinedVariable
            defer_results = []
            del defer_results
            return None

        sources = []
        latest_ident = None
        latest_idurl, _ = id_url.get_latest_revision(idurl)
        if not latest_idurl:
            latest_idurl = idurl
        if latest_idurl:
            latest_ident = identitydb.get_ident(latest_idurl)
        if latest_ident:
            sources.extend(list(latest_ident.getSources(as_originals=True)))
        if not sources:
            pub_key = id_url.known().get(latest_idurl)
            if pub_key:
                known_sources = id_url.sources(pub_key)
                for another_idurl in reversed(known_sources):
                    if another_idurl != latest_idurl and another_idurl != idurl:
                        if another_idurl not in sources:
                            sources.append(another_idurl)
        if idurl in sources:
            sources.remove(idurl)

        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, latest_idurl=latest_idurl, latest_ident=latest_ident, sources=sources)

        if sources:
            lg.warn('[cache failed] %s : %s  but will try %d more sources' % (idurl, err.getErrorMessage(), len(sources)))
            _next_source(None, idurl, sources, 0)
            return None

        p2p_stats.count_identity_cache(idurl, 0)
        _LastTimeCached.pop(idurl, None)
        lg.warn('[cache failed] and also no other sources found %s : %s' % (idurl, err.getErrorMessage()))
        defer_results = caching().pop(idurl, [])
        if _Debug:
            lg.args(_DebugLevel, known=len(id_url.known().keys()), defer_results=len(defer_results))
        for result in defer_results:
            if result and not result.called:
                reactor.callLater(0, result.errback, err)  # @UndefinedVariable
        defer_results = []
        del defer_results
        return None

    def _start_one(idurl, ignore_errors):
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl)
        defer_obj = add_callback(idurl, ignore_errors=ignore_errors)
        d = net_misc.getPageTwisted(idurl, timeout)
        d.addCallback(_success, idurl)
        d.addErrback(_fail, idurl)
        return defer_obj

    if idurl in caching():
        if _Debug:
            lg.out(_DebugLevel, 'identitycache.immediatelyCaching already has tasks for %r' % idurl)
        defer_obj = add_callback(idurl, ignore_errors=ignore_errors)
        return defer_obj

    if _Debug:
        lg.out(_DebugLevel, 'identitycache.immediatelyCaching started new task for %r' % idurl)
    return _start_one(idurl, ignore_errors=ignore_errors)


#------------------------------------------------------------------------------


def SetLocalIPs(local_ips):
    """
    This method is to build an index for local IP's.
    """
    return identitydb.update_local_ips_dict(local_ips)


def GetLocalIP(idurl):
    """
    If known, return a local IP for given user IDURL.
    """
    return identitydb.get_local_ip(idurl)


def HasLocalIP(idurl):
    """
    Return True if at least one local IP is known for that IDURL.
    """
    return identitydb.has_local_ip(idurl)


def SearchLocalIP(ip):
    """
    For given IP search all users in the cache with same local IP.
    """
    return identitydb.search_local_ip(ip)


#------------------------------------------------------------------------------


def _test():
    import logging
    logging.basicConfig(level=logging.DEBUG)
    from twisted.internet import reactor  # @UnresolvedImport
    from twisted.internet.defer import setDebugging
    setDebugging(True)
    # from twisted.python import log as twisted_log
    # twisted_log.startLogging(sys.stdout)
    lg.set_debug_level(20)

    from bitdust.main import settings
    settings.init()
    settings.update_proxy_settings()

    init()

    def _resp(src):
        print(src)
        reactor.stop()  # @UndefinedVariable

    immediatelyCaching(sys.argv[1]).addBoth(_resp)
    reactor.run()  # @UndefinedVariable
    shutdown()
    settings.shutdown()


#------------------------------------------------------------------------------

if __name__ == '__main__':
    _test()
