#!/usr/bin/python
# identitycache.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

_Debug = False

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from lib import net_misc

from userid import identity
import identitydb

#------------------------------------------------------------------------------

_CachingTasks = {}
_OverriddenIdentities = {}

#-------------------------------------------------------------------------------


def init():
    """
    This should be called before all other things.

    Call to initialize identitydb and cache several important IDs.
    """
    if _Debug:
        lg.out(4, 'identitycache.init')
    # identitydb.clear()
    identitydb.init()


def shutdown():
    if _Debug:
        lg.out(4, 'identitycache.shutdown')

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
    """
    
    """
    return identitydb.cache()


def HasKey(idurl):
    """
    Check for some user IDURL in the cache.
    """
    return identitydb.has_idurl(idurl) or IsOverridden(idurl)


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
                lg.out(14, '        returning overridden identity (%d bytes) for %s' % (len(overridden_xmlsrc), idurl))
            return identity.identity(xmlsrc=overridden_xmlsrc)
    return identitydb.get(idurl)


def GetLatest(idurl):
    """
    Returns latest copy from cache or fire `immediatelyCaching`,
    result is a `Deferred` object.
    """
    known = FromCache(idurl)
    result = Deferred()
    if known:
        result.callback(known)
    else:
        d = immediatelyCaching(idurl)
        d.addCallback(lambda _: result.callback(FromCache(idurl)))
        d.addErrback(lambda _: result.errback(None))
    return result


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
    #out(12, 'identitycache.UpdateAfterChecking ' + url)
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
#        if _Debug: lg.out(8, 'identitycache.RemapContactAddress for %s [%s] -> [%s]' % (
#            nameurl.GetName(idurl), str(address), str(newaddress)))
        return newaddress
    return address


def OverrideIdentity(idurl, xml_src):
    """
    
    """
    global _OverriddenIdentities
    _OverriddenIdentities[idurl] = xml_src
    if _Debug:
        lg.out(4, 'identitycache.OverrideIdentity a new identity source saved for %s' % idurl)
        lg.out(4, '            total number of overrides is %d' % len(_OverriddenIdentities))


def StopOverridingIdentity(idurl):
    """
    
    """
    global _OverriddenIdentities
    return _OverriddenIdentities.pop(idurl, None)
    if _Debug:
        lg.out(4, 'identitycache.OverrideIdentity   removed overridden source for %s' % idurl)
        lg.out(4, '            total number of overrides is %d' % len(_OverriddenIdentities))


def IsOverridden(idurl):
    """
    
    """
    global _OverriddenIdentities
    return idurl in _OverriddenIdentities


def ReadOverriddenIdentityXMLSource(idurl):
    """
    
    """
    global _OverriddenIdentities
    return _OverriddenIdentities.get(idurl, None)

#------------------------------------------------------------------------------


def getPageSuccess(src, idurl):
    """
    This is called when requested identity source gets received.
    """
    UpdateAfterChecking(idurl, src)
    return src


def getPageFail(x, idurl):
    """
    This is called when identity request is failed.
    """
    if _Debug:
        lg.out(6, "identitycache.getPageFail NETERROR in request to " + idurl)
    return x


def pageRequestTwisted(idurl, timeout=0):
    """
    Request an HTML page - this can be an user identity.
    """
    d = net_misc.getPageTwisted(idurl, timeout)
    d.addCallback(getPageSuccess, idurl)
    d.addErrback(getPageFail, idurl)
    return d


def scheduleForCaching(idurl, timeout=0):
    """
    Even if we have a copy in cache we are to try and read another one.
    """
    return pageRequestTwisted(idurl, timeout)

#------------------------------------------------------------------------------


def immediatelyCaching(idurl, timeout=0):
    """
    A smart method to start caching some identity and get results in callbacks.
    """
    global _CachingTasks
    if idurl in _CachingTasks:
        return _CachingTasks[idurl]

    def _getPageSuccess(src, idurl, res):
        global _CachingTasks
        _CachingTasks.pop(idurl)
        if UpdateAfterChecking(idurl, src):
            res.callback(src)
            if _Debug:
                lg.out(14, '    [cached] %s' % idurl)
        else:
            res.errback(Exception(src))
            if _Debug:
                lg.out(14, '    [cache error] %s' % idurl)
        return src

    def _getPageFail(x, idurl, res):
        global _CachingTasks
        _CachingTasks.pop(idurl)
        res.errback(x)
        if _Debug:
            lg.out(14, '    [cache failed] %s' % idurl)
        return None
    result = Deferred()
    d = net_misc.getPageTwisted(idurl, timeout)
    d.addCallback(_getPageSuccess, idurl, result)
    d.addErrback(_getPageFail, idurl, result)
    _CachingTasks[idurl] = result
    if _Debug:
        lg.out(14, 'identitycache.immediatelyCaching %s' % idurl)
    return result

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
