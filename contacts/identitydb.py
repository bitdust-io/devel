#!/usr/bin/python
# identitydb.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (identitydb.py) is part of BitDust Software.
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
.. module:: identitydb.

Here is a simple1 database for identities cache. Also keep track of
changing identities sources and maintain a several "index" dictionaries
to speed up processes.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import os
import time

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

from lib import nameurl
from lib import strng

from userid import identity

#------------------------------------------------------------------------------

# Dictionary cache of identities - lookup by primary url
# global dictionary of identities in this file
# indexed with urls and contains identity objects
_IdentityCache = {}
_IdentityCacheIDs = {}
_IdentityCacheCounter = 0
_IdentityCacheModifiedTime = {}
_Contact2IDURL = {}
_IDURL2Contacts = {}
_IPPort2IDURL = {}
_LocalIPs = {}
_IdentityCacheUpdatedCallbacks = []

#------------------------------------------------------------------------------


def cache():
    global _IdentityCache
    return _IdentityCache


def cache_ids():
    global _IdentityCacheIDs
    return _IdentityCacheIDs

#------------------------------------------------------------------------------


def init():
    """
    Need to call before all other methods.

    Check to exist and create a folder to keep all cached identities.
    """
    lg.out(4, "identitydb.init")
    iddir = settings.IdentityCacheDir()
    if not os.path.exists(iddir):
        lg.out(8, 'identitydb.init create folder %r' % iddir)
        bpio._dir_make(iddir)


def shutdown():
    """
    
    """
    lg.out(4, "identitydb.shutdown")

#------------------------------------------------------------------------------


def clear(exclude_list=None):
    """
    Clear the database, indexes and cached files from disk.
    """
    global _Contact2IDURL
    global _IPPort2IDURL
    global _IDURL2Contacts
    global _IdentityCache
    global _IdentityCacheIDs
    global _IdentityCacheModifiedTime
    lg.out(4, "identitydb.clear")
    _IdentityCache.clear()
    _IdentityCacheIDs.clear()
    _IdentityCacheModifiedTime.clear()
    _Contact2IDURL.clear()
    _IPPort2IDURL.clear()
    _IDURL2Contacts.clear()
    iddir = settings.IdentityCacheDir()
    if not os.path.exists(iddir):
        return
    for file_name in os.listdir(iddir):
        path = os.path.join(iddir, file_name)
        if not os.access(path, os.W_OK):
            continue
        if exclude_list:
            idurl = nameurl.FilenameUrl(file_name)
            if idurl in exclude_list:
                continue
        os.remove(path)
        lg.out(6, 'identitydb.clear remove ' + path)
    fire_cache_updated_callbacks()


def size():
    """
    Return a number of items in the database.
    """
    global _IdentityCache
    return len(_IdentityCache)


def has_idurl(idurl):
    """
    Return True if that IDURL already cached.
    """
    global _IdentityCache
    return strng.to_bin(idurl) in _IdentityCache


def has_file(idurl):
    """
    """
    idurl = strng.to_bin(idurl)
    try:
        partfilename = nameurl.UrlFilename(idurl)
    except:
        lg.out(1, "identitydb.has_file ERROR %r is not correct" % idurl)
        return None
    filename = os.path.join(settings.IdentityCacheDir(), partfilename)
    return os.path.exists(filename)


def idset(idurl, id_obj):
    """
    Important method - need to call that to update indexes.
    """
    global _Contact2IDURL
    global _IDURL2Contacts
    global _IPPort2IDURL
    global _IdentityCache
    global _IdentityCacheIDs
    global _IdentityCacheCounter
    global _IdentityCacheModifiedTime
    idurl = strng.to_bin(idurl)
    if not has_idurl(idurl):
        lg.out(6, 'identitydb.idset new identity: %r' % idurl)
    _IdentityCache[idurl] = id_obj
    _IdentityCacheModifiedTime[idurl] = time.time()
    identid = _IdentityCacheIDs.get(idurl, None)
    if identid is None:
        identid = _IdentityCacheCounter
        _IdentityCacheCounter += 1
        _IdentityCacheIDs[idurl] = identid
    for contact in id_obj.getContacts():
        if contact not in _Contact2IDURL:
            _Contact2IDURL[contact] = set()
        # else:
        #     if len(_Contact2IDURL[contact]) >= 1 and idurl not in _Contact2IDURL[contact]:
        #         lg.warn('another user have same contact: ' + str(list(_Contact2IDURL[contact])))
        _Contact2IDURL[contact].add(idurl)
        if idurl not in _IDURL2Contacts:
            _IDURL2Contacts[idurl] = set()
        _IDURL2Contacts[idurl].add(contact)
        try:
            proto, host, port, fname = nameurl.UrlParse(contact)
            ipport = (host, int(port))
            _IPPort2IDURL[ipport] = idurl
        except:
            pass
    # TODO: when identity contacts changed - need to remove old items from _Contact2IDURL
    fire_cache_updated_callbacks(single_item=(identid, idurl, id_obj))


def idget(idurl):
    """
    Get identity from cache.
    """
    global _IdentityCache
    idurl = strng.to_bin(idurl)
    return _IdentityCache.get(idurl, None)


def idremove(idurl):
    """
    Remove identity from cache, also update indexes.

    Not remove local file.
    """
    global _IdentityCache
    global _IdentityCacheIDs
    global _IdentityCacheModifiedTime
    global _Contact2IDURL
    global _IDURL2Contacts
    global _IPPort2IDURL
    idurl = strng.to_bin(idurl)
    idobj = _IdentityCache.pop(idurl, None)
    identid = _IdentityCacheIDs.pop(idurl, None)
    _IdentityCacheModifiedTime.pop(idurl, None)
    _IDURL2Contacts.pop(idurl, None)
    if idobj is not None:
        for contact in idobj.getContacts():
            _Contact2IDURL.pop(contact, None)
            try:
                proto, host, port, fname = nameurl.UrlParse(contact)
                ipport = (host, int(port))
                _IPPort2IDURL.pop(ipport, None)
            except:
                pass
    fire_cache_updated_callbacks(single_item=(identid, None, None))
    return idobj


def idcontacts(idurl):
    """
    A fast way to get identity contacts.
    """
    global _IDURL2Contacts
    idurl = strng.to_bin(idurl)
    return list(_IDURL2Contacts.get(idurl, set()))


def get(idurl):
    """
    A smart way to get identity from cache.

    If not cached in memory but found on disk - will cache from disk.
    """
    idurl = strng.to_bin(idurl)
    if has_idurl(idurl):
        return idget(idurl)
    else:
        try:
            partfilename = nameurl.UrlFilename(idurl)
        except:
            lg.out(1, "identitydb.get ERROR %r is incorrect" % idurl)
            return None
        filename = os.path.join(settings.IdentityCacheDir(), partfilename)
        if not os.path.exists(filename):
            lg.out(6, "identitydb.get file %r not exist" % os.path.basename(filename))
            return None
        idxml = bpio.ReadTextFile(filename)
        if idxml:
            idobj = identity.identity(xmlsrc=idxml)
            idurl_orig = idobj.getIDURL()
            if idurl == idurl_orig:
                idset(idurl, idobj)
                return idobj
            else:
                lg.out(1, "identitydb.get ERROR idurl=%r idurl_orig=%r" % (idurl, idurl_orig))
                return None
        lg.out(6, "identitydb.get %s not found" % nameurl.GetName(idurl))
        return None


def get_filename(idurl):
    idurl = strng.to_bin(idurl)
    try:
        partfilename = nameurl.UrlFilename(idurl)
    except:
        lg.out(1, "identitydb.get_filename ERROR %r is incorrect" % idurl)
        return None
    return os.path.join(settings.IdentityCacheDir(), partfilename)


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


def update(idurl, xml_src):
    """
    This is a correct method to update an identity in the local cache.

    PREPRO need to check that date or version is after old one so not
    vulnerable to replay attacks.
    """
    idurl = strng.to_bin(idurl)
    try:
        newid = identity.identity(xmlsrc=xml_src)
    except:
        lg.exc()
        return False

    if not newid.isCorrect():
        lg.out(1, "identitydb.update ERROR incorrect identity : %r" % idurl)
        return False

    try:
        if not newid.Valid():
            lg.out(1, "identitydb.update ERROR identity not Valid : %r" % idurl)
            return False
    except:
        lg.exc()
        return False

    filename = os.path.join(settings.IdentityCacheDir(), nameurl.UrlFilename(idurl))
    if os.path.exists(filename):
        oldidentityxml = bpio.ReadTextFile(filename)
        oldidentity = identity.identity(xmlsrc=oldidentityxml)

        if oldidentity.publickey != newid.publickey:
            # TODO: SECURITY   add some kind of black list to be able to block certain IP's if the DDoS me
            lg.out(1, "identitydb.update ERROR new publickey does not match old, SECURITY VIOLATION : %r" % idurl)
            return False

        if oldidentity.signature != newid.signature:
            lg.out(6, 'identitydb.update have new data for %r' % nameurl.GetName(idurl))
        else:
            idset(idurl, newid)
            return True

    # publickeys match so we can update it
    bpio.WriteTextFile(filename, xml_src)
    idset(idurl, newid)

    return True


def remove(idurl):
    """
    Top method to remove identity from cache - also remove local file.
    """
    idurl = strng.to_bin(idurl)
    filename = os.path.join(settings.IdentityCacheDir(), nameurl.UrlFilename(idurl))
    if os.path.isfile(filename):
        lg.out(6, "identitydb.remove file %r" % filename)
        try:
            os.remove(filename)
        except:
            lg.exc()
    idremove(idurl)
    return True


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
    idurl = strng.to_bin(idurl)
    return _LocalIPs.get(idurl, None)


def has_local_ip(idurl):
    """
    To check for some known local IP of given user.
    """
    global _LocalIPs
    idurl = strng.to_bin(idurl)
    return idurl in _LocalIPs


def search_local_ip(ip):
    """
    Search all index for given local IP and return a first found idurl.
    """
    global _LocalIPs
    for idurl, localip in _LocalIPs.items():
        if localip == ip:
            return idurl
    return None


def get_last_modified_time(idurl):
    """
    """
    global _IdentityCacheModifiedTime
    idurl = strng.to_bin(idurl)
    return _IdentityCacheModifiedTime.get(idurl, None)

#------------------------------------------------------------------------------


def print_id(idurl):
    """
    For debug purposes.
    """
    idurl = strng.to_bin(idurl)
    if has_idurl(idurl):
        idForKey = get(idurl)
        lg.out(6, str(idForKey.sources))
        lg.out(6, str(idForKey.contacts))
        lg.out(6, str(idForKey.publickey))
        lg.out(6, str(idForKey.signature))


def print_keys():
    """
    For debug purposes.
    """
    global _IdentityCache
    for key in _IdentityCache.keys():
        lg.out(6, "%d: %r" % (_IdentityCacheIDs[key], key))


def print_cache():
    """
    For debug purposes.
    """
    global _IdentityCache
    for key in _IdentityCache.keys():
        lg.out(6, "---------------------")
        print_id(key)

#------------------------------------------------------------------------------


def AddCacheUpdatedCallback(cb):
    global _IdentityCacheUpdatedCallbacks
    _IdentityCacheUpdatedCallbacks.append(cb)


def RemoveCacheUpdatedCallback(cb):
    global _IdentityCacheUpdatedCallbacks
    if cb in _IdentityCacheUpdatedCallbacks:
        _IdentityCacheUpdatedCallbacks.remove(cb)


def fire_cache_updated_callbacks(single_item=None):
    global _IdentityCacheUpdatedCallbacks
    for cb in _IdentityCacheUpdatedCallbacks:
        cb(cache_ids(), cache(), single_item)
