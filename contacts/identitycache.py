#!/usr/bin/python
#identitycache.py
#
# <<<COPYRIGHT>>>
#
#
#

"""
.. module:: identitycache

Here we store a local copies of identities.
This fetches identities off the web and stores an XML copy in file and an identity object in a dictionary.  
Other parts of BitDust call this to get an identity using an IDURL.
So this is a local cache of user ID's.
"""


from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------ 

from logs import lg

from lib import net_misc

import identitydb

#------------------------------------------------------------------------------ 

_CachingTasks = {}

#-------------------------------------------------------------------------------

def init():
    """
    This should be called before all other things.
    Call to initialize identitydb and cache several important IDs.
    """
    lg.out(4, 'identitycache.init')
    identitydb.clear()
    identitydb.init()
        

def shutdown():
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


def PrintID(url):
    """
    For debug, print an item from cache.
    """
    identitydb.print_id(url)


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


def HasKey(url):
    """
    Check for some user IDURL in the cache.
    """
    return identitydb.has_key(url)


def HasFile(url):
    return identitydb.has_file(url)


def FromCache(url):
    """
    Get identity object from cache.
    """
    return identitydb.get(url)


def GetIDURLsByContact(contact):
    """
    In the ``identitydb`` code we keep track of all identity objects and prepare an index of all known contacts.
    So we can try to detect who is sending us a packet when got a packet from known contact address. 
    This is to get a list of known ID's in the cache for that contact.
    """
    return identitydb.get_idurls_by_contact(contact)


def GetIDURLByIPPort(ip, port):
    """
    Same as previous method but the index is created from IP:PORT parts of identities contacts.
    """
    return identitydb.get_idurl_by_ip_port(ip, port)


def GetContacts(url):
    """
    This is another one index - return a set of contacts for given IDURL.
    Instead of read identity object and parse it every time - this method can be used.
    This is a "cached" info. 
    """
    return identitydb.idcontacts(url)


def Remove(url):
    """
    Remove an item from cache.
    """
    return identitydb.remove(url)


def UpdateAfterChecking(url, xml_src):
    """
    Need to call that method to update the cache when some identity sources is changed.
    """
    #out(12, 'identitycache.UpdateAfterChecking ' + url)
    return identitydb.update(url, xml_src)


def RemapContactAddress(address):
    """
    For local peers in same sub network we need to use local IP, not external IP.
    We pass local IP to transports to send packets inside sub network. 
    TODO Would be great to get rid of that - transport must keep track of local and external situations.  
    So this is another index - IDURL to local IP, see identitydb.  
    """
    idurl = GetIDURLByIPPort(address[0], address[1])
    if idurl is not None and HasLocalIP(idurl):
        newaddress = (GetLocalIP(idurl), address[1])
#        lg.out(8, 'identitycache.RemapContactAddress for %s [%s] -> [%s]' % (
#            nameurl.GetName(idurl), str(address), str(newaddress)))
        return newaddress
    return address

#------------------------------------------------------------------------------ 

def getPageSuccess(src, url):
    """
    This is called when requested identity source gets received.
    """
    UpdateAfterChecking(url, src)
    return src


def getPageFail(x, url):
    """
    This is called when identity request is failed. 
    """
    lg.out(6, "identitycache.getPageFail NETERROR in request to " + url)
    return x


def pageRequestTwisted(url):
    """
    Request an HTML page - this can be an user identity.
    """
    d = net_misc.getPageTwisted(url)
    d.addCallback(getPageSuccess, url)
    d.addErrback(getPageFail, url)
    return d


def scheduleForCaching(url):
    """
    Even if we have a copy in cache we are to try and read another one.
    """
    return pageRequestTwisted(url)

#------------------------------------------------------------------------------ 

def immediatelyCaching(url):
    """
    A smart method to start caching some identity and get results in callbacks.
    """
    global _CachingTasks
    if _CachingTasks.has_key(url):
        return _CachingTasks[url]
    def _getPageSuccess(src, url, res):
        global _CachingTasks
        _CachingTasks.pop(url)
        if UpdateAfterChecking(url, src):
            res.callback(src)
            lg.out(14, '    [cached] %s' % url)
        else:
            res.errback(Exception(src))
            lg.out(14, '    [cache error] %s' % url)
        return src
    def _getPageFail(x, url, res):
        global _CachingTasks
        _CachingTasks.pop(url)
        res.errback(x)
        lg.out(14, '    [cache failed] %s' % url)
        return None
    result = Deferred()
    d = net_misc.getPageTwisted(url)
    d.addCallback(_getPageSuccess, url, result)
    d.addErrback(_getPageFail, url, result)
    _CachingTasks[url] = result
    lg.out(14, 'identitycache.immediatelyCaching %s' % url)
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


