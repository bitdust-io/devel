#!/usr/bin/python
#identitydb.py
#
# <<<COPYRIGHT>>>
#
#
#

"""
.. module:: identitydb

Here is a simple1 database for identities cache.
Also keep track of changing identities sources and maintain a several "index" dictionaries to speed up processes.  
"""

import os

import lib.bpio as bpio
import lib.settings as settings
import lib.nameurl as nameurl

import identity

#------------------------------------------------------------------------------ 

# Dictionary cache of identities - lookup by primary url
# global dictionary of identities in this file
# indexed with urls and contains identity objects
_IdentityCache = {}
_Contact2IDURL = {}
_IDURL2Contacts = {}
_IPPort2IDURL = {}
_LocalIPs = {}

#------------------------------------------------------------------------------ 

def init():
    """
    Need to call before all other methods.
    Check to exist and create a folder to keep all cached identities.
    """
    bpio.log(4,"identitydb.init")
    iddir = settings.IdentityCacheDir()
    if not os.path.exists(iddir):
        bpio.log(8, 'identitydb.init create folder ' + iddir)
        bpio._dir_make(iddir)

def clear(exclude_list=None):
    """
    Clear the database, indexes and cached files from disk.
    """
    global _IdentityCache
    global _Contact2IDURL
    global _IPPort2IDURL
    global _IDURL2Contacts
    bpio.log(4,"identitydb.clear")
    _IdentityCache.clear()
    _Contact2IDURL.clear()
    _IPPort2IDURL.clear()
    _IDURL2Contacts.clear()

    iddir = settings.IdentityCacheDir()
    if not os.path.exists(iddir):
        return

    for name in os.listdir(iddir):
        path = os.path.join(iddir, name)
        if not os.access(path, os.W_OK):
            continue
        if exclude_list:
            idurl = nameurl.FilenameUrl(name)
            if idurl in exclude_list:
                continue 
        os.remove(path)
        bpio.log(6, 'identitydb.clear remove ' + path)

def size():
    """
    Return a number of items in the database.
    """
    global _IdentityCache
    return len(_IdentityCache)

def has_key(idurl):
    """
    Return True if that IDURL already cached.
    """
    global _IdentityCache
    return _IdentityCache.has_key(idurl)

def idset(idurl, id_obj):
    """
    Important method - need to call that to update indexes.
    """
    global _IdentityCache
    global _Contact2IDURL
    global _IDURL2Contacts
    global _IPPort2IDURL
    if not has_key(idurl):
        bpio.log(6, 'identitydb.idset new identity: ' + idurl)
    _IdentityCache[idurl] = id_obj
    for contact in id_obj.getContacts():
        if not _Contact2IDURL.has_key(contact):
            _Contact2IDURL[contact] = set()
        else:
            if len(_Contact2IDURL[contact]) >= 1 and idurl not in _Contact2IDURL[contact]:
                bpio.log(6, 'identitydb.idset WARNING another user have same contact: ' + str(list(_Contact2IDURL[contact])))
        _Contact2IDURL[contact].add(idurl)
        if not _IDURL2Contacts.has_key(idurl):
            _IDURL2Contacts[idurl] = set()
        _IDURL2Contacts[idurl].add(contact)
        try: 
            proto, host, port, fname = nameurl.UrlParse(contact)
            ipport = (host, int(port))
            _IPPort2IDURL[ipport] = idurl 
        except:
            pass
    # TODO when identity contacts changed - need to remove old items from _Contact2IDURL

def idget(url):
    """
    Get identity from cache.
    """
    global _IdentityCache
    return _IdentityCache.get(url, None)

def idremove(url):
    """
    Remove identity from cache, also update indexes. Not remove local file.
    """
    global _IdentityCache
    global _Contact2IDURL
    global _IDURL2Contacts
    global _IPPort2IDURL
    idobj = _IdentityCache.pop(url, None)
    _IDURL2Contacts.pop(url, None)
    if idobj is not None:
        for contact in idobj.getContacts():
            _Contact2IDURL.pop(contact, None)
            try: 
                proto, host, port, fname = nameurl.UrlParse(contact)
                ipport = (host, int(port))
                _IPPort2IDURL.pop(ipport, None) 
            except:
                pass
    return idobj

def idcontacts(idurl):
    """
    A fast way to get identity contacts.
    """
    global _IDURL2Contacts
    return list(_IDURL2Contacts.get(idurl, set()))

def get(url):
    """
    A smart way to get identity from cache.
    If not cached in memory but found on disk - will cache from disk.
    """
    if has_key(url):
        return idget(url)
    else:
        try:
            partfilename = nameurl.UrlFilename(url)
        except:
            bpio.log(1, "identitydb.get ERROR %s is incorrect" % str(url))
            return None
        
        filename = os.path.join(settings.IdentityCacheDir(), partfilename)
        if not os.path.exists(filename):
            bpio.log(6, "identitydb.get file %s not exist" % os.path.basename(filename))
            return None
        
        idxml = bpio.ReadTextFile(filename)
        if idxml:
            idobj = identity.identity(xmlsrc=idxml)
            url2 = idobj.getIDURL()
            if url == url2:
                idset(url, idobj)
                return idobj
            
            else:
                bpio.log(1, "identitydb.get ERROR url=%s url2=%s" % (url, url2))
                return None

        bpio.log(6, "identitydb.get %s not found" % nameurl.GetName(url))
        return None

def get_idurls_by_contact(contact):
    """
    Use index dictionary to get IDURL with given contact. 
    """
    global _Contact2IDURL
    return list(_Contact2IDURL.get(contact, set()))

def get_idurl_by_ip_port(ip, port):
    """
    Use index dictionary to get IDURL by IP and PORT. 
    """
    global _IPPort2IDURL
    return _IPPort2IDURL.get((ip, int(port)), None)

def update(url, xml_src):
    """
    This is a correct method to update an identity in the database.
    PREPRO need to check that date or version is after old one so not vulnerable to replay attacks.
    """
    try:
        newid = identity.identity(xmlsrc=xml_src)
    except:
        bpio.exception()
        return False

    if not newid.isCorrect():
        bpio.log(1, "identitydb.update ERROR: incorrect identity " + str(url))
        return False

    try:
        if not newid.Valid():
            bpio.log(1, "identitydb.update ERROR identity not Valid" + str(url))
            return False
    except:
        bpio.exception()
        return False

    filename = os.path.join(settings.IdentityCacheDir(), nameurl.UrlFilename(url))
    if os.path.exists(filename):
        oldidentityxml = bpio.ReadTextFile(filename)
        oldidentity = identity.identity(xmlsrc=oldidentityxml)

        if oldidentity.publickey != newid.publickey:
            bpio.log(1, "identitydb.update ERROR new publickey does not match old : SECURITY VIOLATION " + url)
            return False

        if oldidentity.signature != newid.signature:
            bpio.log(6, 'identitydb.update have new data for ' + nameurl.GetName(url))
        else:
            idset(url, newid)
            return True

    bpio.WriteFile(filename, xml_src)             # publickeys match so we can update it
    idset(url, newid)

    return True

def remove(url):
    """
    Top method to remove identity from cache - also remove local file.
    """
    filename = os.path.join(settings.IdentityCacheDir(), nameurl.UrlFilename(url))
    if os.path.isfile(filename):
        bpio.log(6, "identitydb.remove file %s" % filename)
        try:
            os.remove(filename)
        except:
            bpio.exception()
    idremove(url)

def update_local_ips_dict(local_ips_dict):
    """
    This method intended to maintain a local IP's index.
    """
    global _LocalIPs
    # _LocalIPs.clear()
    # _LocalIPs = local_ips_dict
    _LocalIPs.update(local_ips_dict)
    
def get_local_ip(idurl):
    """
    This is to get a local IP of some user from the index. 
    """
    global _LocalIPs
    return _LocalIPs.get(idurl, None)

def has_local_ip(idurl):
    """
    To check for some known local IP of given user.
    """
    global _LocalIPs
    return _LocalIPs.has_key(idurl)

def search_local_ip(ip):
    """
    Search all index for given local IP and return a first found idurl.
    """
    global _LocalIPs
    for idurl, localip in _LocalIPs.items():
        if localip == ip:
            return idurl
    return None

#------------------------------------------------------------------------------ 

def print_id(url):
    """
    For debug purposes.
    """
    if has_key(url):
        idForKey = get(url)
        bpio.log(6, str(idForKey.sources) )
        bpio.log(6, str(idForKey.contacts ))
        bpio.log(6, str(idForKey.publickey ))
        bpio.log(6, str(idForKey.signature ))

def print_keys():
    """
    For debug purposes.
    """
    global _IdentityCache
    for key in _IdentityCache.keys():
        bpio.log(6, key)

def print_cache():
    """
    For debug purposes.
    """
    global _IdentityCache
    for key in _IdentityCache.keys():
        bpio.log(6, "---------------------" )
        print_id(key)









