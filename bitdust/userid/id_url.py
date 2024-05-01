#!/usr/bin/python
# id_url.py
#
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (id_url.py) is part of BitDust Software.
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
#
"""
.. module:: id_url.

.. role:: red

This is a core module.

IDURL of your node can changed over time, see id_rotator() state machine which does that.
So you must remember your "old" identity sources and store locally old IDURL's you had.
This way when you receive a packet from another node which do not know your new IDURL yet,
you can understand that he is actually trying to contact you and act properly.

Also if you stored some packet for user A and then his IDURL changed you must still be able to
correctly reply to him and send stored data back when he requests.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

import os
import sys
import tempfile

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.system import bpio
from bitdust.system import local_fs

from bitdust.crypt import hashes

from bitdust.lib import strng
from bitdust.lib import nameurl

from bitdust.main import settings

#------------------------------------------------------------------------------

_IdentityHistoryDir = None
# TODO: if this dictionary grow too much use CodernityDB instead of in-memory storage
_KnownUsers = {}
_KnownIDURLs = {}
_MergedIDURLs = {}
_KnownSources = {}
_Ready = False

#------------------------------------------------------------------------------


def init():
    global _IdentityHistoryDir
    global _KnownUsers
    global _KnownIDURLs
    global _MergedIDURLs
    global _KnownSources
    global _Ready
    from bitdust.userid import identity
    if _Debug:
        lg.out(_DebugLevel, 'id_url.init')
    if not _IdentityHistoryDir:
        _IdentityHistoryDir = settings.IdentityHistoryDir()
    if not os.path.exists(_IdentityHistoryDir):
        bpio._dir_make(_IdentityHistoryDir)
        lg.info('created new folder %r' % _IdentityHistoryDir)
    else:
        lg.info('using existing folder %r' % _IdentityHistoryDir)
    for_cleanup = []
    for one_user_dir in os.listdir(_IdentityHistoryDir):
        one_user_dir_path = os.path.join(_IdentityHistoryDir, one_user_dir)
        if not os.path.isdir(one_user_dir_path):
            continue
        one_user_identity_files = []
        for one_filename in os.listdir(one_user_dir_path):
            try:
                one_ident_number = int(one_filename)
            except:
                lg.exc()
                continue
            one_user_identity_files.append(one_ident_number)
        if _Debug:
            lg.out(_DebugLevel, 'id_url.init   found %d historical records in %r' % (len(one_user_identity_files), one_user_dir_path))
        one_user_identity_files.sort()
        for one_ident_file in one_user_identity_files:
            one_ident_path = os.path.join(one_user_dir_path, strng.to_text(one_ident_file))
            try:
                xmlsrc = local_fs.ReadTextFile(one_ident_path)
                known_id_obj = identity.identity(xmlsrc=xmlsrc)
                if not known_id_obj.isCorrect():
                    raise Exception('identity history in %r is broken, identity is not correct: %r' % (one_user_dir, one_ident_path))
                if not known_id_obj.Valid():
                    raise Exception('identity history in %r is broken, identity is not valid: %r' % (one_user_dir, one_ident_path))
            except Exception as exc:
                lg.warn(str(exc))
                for_cleanup.append(one_ident_path)
                continue
            one_pub_key = known_id_obj.getPublicKey()
            one_revision = known_id_obj.getRevisionValue()
            if one_pub_key not in _KnownUsers:
                _KnownUsers[one_pub_key] = one_user_dir_path
            known_sources = known_id_obj.getSources(as_originals=True)
            for known_idurl in reversed(known_sources):
                if known_idurl not in _KnownIDURLs:
                    _KnownIDURLs[known_idurl] = known_id_obj.getPublicKey()
                    if _Debug:
                        lg.out(_DebugLevel, '    new IDURL added: %r' % known_idurl)
                else:
                    if _KnownIDURLs[known_idurl] != known_id_obj.getPublicKey():
                        _KnownIDURLs[known_idurl] = known_id_obj.getPublicKey()
                        lg.warn('another user had same identity source: %r' % known_idurl)
                if one_pub_key not in _MergedIDURLs:
                    _MergedIDURLs[one_pub_key] = {}
                    if _Debug:
                        lg.out(_DebugLevel, '    new Public Key added: %s...' % one_pub_key[-10:])
                if one_revision in _MergedIDURLs[one_pub_key]:
                    if _MergedIDURLs[one_pub_key][one_revision] != known_idurl:
                        if _MergedIDURLs[one_pub_key][one_revision] not in known_sources:
                            lg.warn('rewriting existing identity revision %d : %r -> %r' % (one_revision, _MergedIDURLs[one_pub_key][one_revision], known_idurl))
                    _MergedIDURLs[one_pub_key][one_revision] = known_idurl
                else:
                    _MergedIDURLs[one_pub_key][one_revision] = known_idurl
                    if _Debug:
                        lg.out(_DebugLevel, '        revision %d merged with other %d known items' % (one_revision, len(_MergedIDURLs[one_pub_key])))
                if one_pub_key not in _KnownSources:
                    _KnownSources[one_pub_key] = []
                for one_source in known_id_obj.getSources(as_originals=True):
                    if one_source not in _KnownSources[one_pub_key]:
                        _KnownSources[one_pub_key].append(one_source)
                        if _Debug:
                            lg.out(_DebugLevel, '    new source %r added for %r' % (one_source, one_pub_key[-10:]))
    for one_ident_path in for_cleanup:
        if os.path.isfile(one_ident_path):
            lg.warn('about to erase broken historical identity file: %r' % one_ident_path)
            try:
                os.remove(one_ident_path)
            except:
                lg.exc()
    _Ready = True


def shutdown():
    global _IdentityHistoryDir
    global _KnownIDURLs
    global _KnownUsers
    global _Ready
    global _MergedIDURLs
    global _KnownSources
    _IdentityHistoryDir = None
    _KnownUsers.clear()
    _KnownIDURLs.clear()
    _MergedIDURLs.clear()
    _KnownSources.clear()
    _Ready = False


#------------------------------------------------------------------------------


def known():
    global _KnownIDURLs
    return _KnownIDURLs


def merged(pub_key=None):
    global _MergedIDURLs
    if pub_key is None:
        return _MergedIDURLs
    return _MergedIDURLs.get(pub_key, {})


def users(pub_key=None):
    global _KnownUsers
    if pub_key is None:
        return _KnownUsers
    return _KnownUsers.get(pub_key, None)


def sources(pub_key=None):
    global _KnownSources
    if pub_key is None:
        return _KnownSources
    return _KnownSources.get(pub_key, [])


#------------------------------------------------------------------------------


def identity_cached(new_id_obj):
    """
    After receiving identity file of another user we need to check his identity sources.
    I can be file from identity server or Identity() packet received directly from remote peer.
    Also it can be my own identity that was changed locally.
    In any case we need to take certain actions if those identity sources changed.
    First identity source forms IDURL of that identity and act as unique global ID of that BitDust node.
    When first identity source changed (because identity server went down) identity is "rotated":
    second identity source will be placed on the first position and IDURL will change.
    In that case we need to remember new IDURL and keep track of old IDURL of that user - this way we can
    match and merge different IDURL's for one owner.
    """
    global _IdentityHistoryDir
    global _KnownUsers
    global _KnownIDURLs
    global _MergedIDURLs
    global _KnownSources
    from bitdust.userid import identity
    pub_key = new_id_obj.getPublicKey()
    user_name = new_id_obj.getIDName()
    if _Debug:
        lg.args(_DebugLevel, user_name=user_name)
    is_identity_rotated = False
    latest_id_obj = None
    latest_sources = []
    for_cleanup = []
    if pub_key not in _KnownUsers:
        user_path = tempfile.mkdtemp(prefix=user_name + '@', dir=_IdentityHistoryDir)
        _KnownUsers[pub_key] = user_path
        first_identity_file_path = os.path.join(user_path, '0')
        local_fs.WriteBinaryFile(first_identity_file_path, new_id_obj.serialize())
        if _Debug:
            lg.out(_DebugLevel, 'id_url.identity_cached wrote first item for user %r in identity history: %r' % (user_name, first_identity_file_path))
    else:
        user_path = _KnownUsers[pub_key]
        user_identity_files = sorted(map(int, os.listdir(user_path)))
        if len(user_identity_files) == 0:
            lg.warn('identity history for user %r is broken, public key is known, but no identity files found' % user_name)
        latest_identity_file_path = ''
        latest_pub_key = None
        latest_revision = -1
        known_revisions = set()
        for id_file in user_identity_files:
            identity_file_path = os.path.join(user_path, strng.to_text(id_file))
            xmlsrc = local_fs.ReadBinaryFile(identity_file_path)
            one_id_obj = identity.identity(xmlsrc=xmlsrc)
            if not one_id_obj.isCorrect():
                lg.warn('identity history for user %r is broken, identity in the file %r is not correct' % (user_name, identity_file_path))
                for_cleanup.append(identity_file_path)
                continue
            if not one_id_obj.Valid():
                lg.warn('identity history for user %r is broken, identity in the file %r is not valid' % (user_name, identity_file_path))
                for_cleanup.append(identity_file_path)
                continue
            if not latest_pub_key:
                latest_pub_key = one_id_obj.getPublicKey()
            if latest_pub_key != one_id_obj.getPublicKey():
                lg.err('identity history for user %r is broken, public key not matching in the file %r' % (user_name, identity_file_path))
                for_cleanup.append(identity_file_path)
                continue
            known_revisions.add(one_id_obj.getRevisionValue())
            if one_id_obj.getRevisionValue() > latest_revision:
                latest_revision = one_id_obj.getRevisionValue()
                latest_identity_file_path = identity_file_path
        xmlsrc = local_fs.ReadBinaryFile(latest_identity_file_path)
        if xmlsrc:
            latest_id_obj = identity.identity(xmlsrc=xmlsrc)
            if latest_id_obj.getPublicKey() != new_id_obj.getPublicKey():
                raise Exception('identity history for user %r is broken, public key not matching' % user_name)
            if latest_id_obj.getIDName() != new_id_obj.getIDName():
                lg.warn('found another user name in identity history for user %r : %r' % (user_name, latest_id_obj.getIDName()))
            if new_id_obj.getRevisionValue() in known_revisions:
                if _Debug:
                    lg.out(_DebugLevel, 'id_url.identity_cached revision %d already known for user %r' % (new_id_obj.getRevisionValue(), user_name))
            else:
                latest_sources = latest_id_obj.getSources(as_originals=True)
                new_sources = new_id_obj.getSources(as_originals=True)
                if latest_sources == new_sources:
                    local_fs.WriteBinaryFile(latest_identity_file_path, new_id_obj.serialize())
                    if _Debug:
                        lg.out(_DebugLevel, 'id_url.identity_cached latest identity sources for user %r did not changed, updated file %r' % (user_name, latest_identity_file_path))
                else:
                    next_identity_file = user_identity_files[-1] + 1
                    next_identity_file_path = os.path.join(user_path, strng.to_text(next_identity_file))
                    local_fs.WriteBinaryFile(next_identity_file_path, new_id_obj.serialize())
                    is_identity_rotated = True
                    if _Debug:
                        lg.out(_DebugLevel, 'id_url.identity_cached identity sources for user %r changed, wrote new item in the history: %r' % (user_name, next_identity_file_path))
    new_revision = new_id_obj.getRevisionValue()
    new_sources = new_id_obj.getSources(as_originals=True)
    for new_idurl in reversed(new_sources):
        if new_idurl not in _KnownIDURLs:
            _KnownIDURLs[new_idurl] = new_id_obj.getPublicKey()
            if _Debug:
                lg.out(_DebugLevel, 'id_url.identity_cached new IDURL added: %r' % new_idurl)
        else:
            if _KnownIDURLs[new_idurl] != new_id_obj.getPublicKey():
                lg.warn('another user had same identity source: %r' % new_idurl)
                _KnownIDURLs[new_idurl] = new_id_obj.getPublicKey()
        if pub_key not in _MergedIDURLs:
            _MergedIDURLs[pub_key] = {}
            if _Debug:
                lg.out(_DebugLevel, 'id_url.identity_cached new Public Key added: %s...' % pub_key[-10:])
        prev_idurl = _MergedIDURLs[pub_key].get(new_revision, None)
        if new_revision in _MergedIDURLs[pub_key]:
            if _MergedIDURLs[pub_key][new_revision] != new_idurl:
                if nameurl.GetName(_MergedIDURLs[pub_key][new_revision]) == nameurl.GetName(new_idurl):
                    if _MergedIDURLs[pub_key][new_revision] not in new_sources:
                        lg.warn('rewriting existing identity revision %d : %r -> %r' % (new_revision, _MergedIDURLs[pub_key][new_revision], new_idurl))
            _MergedIDURLs[pub_key][new_revision] = new_idurl
        else:
            _MergedIDURLs[pub_key][new_revision] = new_idurl
            if _Debug:
                lg.out(_DebugLevel, 'id_url.identity_cached added new revision %d for user %r, total revisions %d: %r -> %r' % (new_revision, user_name, len(_MergedIDURLs[pub_key]), prev_idurl, new_idurl))
    if pub_key not in _KnownSources:
        _KnownSources[pub_key] = []
    for one_source in new_sources:
        if one_source not in _KnownSources[pub_key]:
            _KnownSources[pub_key].append(one_source)
            if _Debug:
                lg.out(_DebugLevel, 'id_url.identity_cached added new source %r for user %r' % (one_source, user_name))
    if _Debug:
        lg.args(_DebugLevel, is_identity_rotated=is_identity_rotated, latest_id_obj=bool(latest_id_obj))
    if is_identity_rotated and latest_id_obj is not None:
        latest_revision = latest_id_obj.getRevisionValue()
        if _Debug:
            lg.args(_DebugLevel, new_revision=new_revision, latest_revision=latest_revision)
        if new_revision > latest_revision:
            lg.info('found rotated identity after caching %r -> %r' % (latest_id_obj.getSources(as_originals=True)[0], new_sources[0]))
            from bitdust.main import events
            events.send('identity-rotated', data=dict(
                old_idurls=latest_id_obj.getSources(as_originals=True),
                new_idurls=new_id_obj.getSources(as_originals=True),
                old_revision=latest_id_obj.getRevisionValue(),
                new_revision=new_revision,
            ))
            if latest_id_obj.getIDURL(as_original=True) != new_id_obj.getIDURL(as_original=True):
                events.send('identity-url-changed', data=dict(
                    old_idurl=latest_id_obj.getIDURL(as_original=True),
                    new_idurl=new_id_obj.getIDURL(as_original=True),
                    old_revision=latest_id_obj.getRevisionValue(),
                    new_revision=new_revision,
                ))
            from bitdust.userid import my_id
            if my_id.isLocalIdentityReady():
                if my_id.getIDURL() == new_id_obj.getIDURL():
                    # yapf: disable
                    events.send('my-identity-rotated', data=dict(
                        old_idurls=latest_id_obj.getSources(as_originals=True),
                        new_idurls=new_id_obj.getSources(as_originals=True),
                        old_revision=latest_id_obj.getRevisionValue(),
                        new_revision=new_revision,
                    ))
                    # yapf: enable
                    if latest_id_obj.getIDURL(as_original=True) != new_id_obj.getIDURL(as_original=True):
                        # yapf: disable
                        events.send('my-identity-url-changed', data=dict(
                            old_idurl=latest_id_obj.getIDURL(as_original=True),
                            new_idurl=new_id_obj.getIDURL(as_original=True),
                            old_revision=latest_id_obj.getRevisionValue(),
                            new_revision=new_revision,
                        ))
                        # yapf: enable
        else:
            lg.warn('cached out-dated revision %d for %r, most recent revision is %d' % (new_revision, new_sources[0], latest_revision))
    else:
        if _Debug:
            lg.out(_DebugLevel, 'id_url.identity_cached revision %d for %r' % (new_revision, new_sources[0]))
    for identity_file_path in for_cleanup:
        if os.path.isfile(identity_file_path):
            try:
                os.remove(identity_file_path)
            except:
                lg.exc()
    return True


#------------------------------------------------------------------------------


def field(idurl):
    """
    Translates string into `ID_URL_FIELD` object.
    Also we try to read from local identity cache folder if do not know given "idurl".
    """
    global _KnownIDURLs
    if isinstance(idurl, ID_URL_FIELD):
        return idurl
    if idurl in [None, 'None', '', b'None', b'', False]:
        return ID_URL_FIELD(idurl)
    idurl = strng.to_bin(idurl.strip())
    if idurl not in _KnownIDURLs:
        if _Debug:
            lg.out(_DebugLevel, 'id_url.field   will try to find %r in local identity cache' % idurl)
        from bitdust.contacts import identitydb
        cached_ident = identitydb.get_ident(idurl)
        if cached_ident:
            identity_cached(cached_ident)
        else:
            if _Debug:
                cod = sys._getframe(1).f_back.f_code
                modul = os.path.basename(cod.co_filename).replace('.py', '')
                caller = cod.co_name
                lg.warn('unknown yet idurl %s, call from %s.%s' % (idurl, modul, caller))
    return ID_URL_FIELD(idurl)


def fields_list(idurl_list):
    """
    Same as `field()` but for lists.
    """
    return list(map(field, idurl_list))


def fields_dict(idurl_dict):
    """
    Translates dictionary keys into `ID_URL_FIELD` objects.
    """
    return {field(k): v for k, v in idurl_dict.items()}


def is_idurl(value):
    """
    Return True if input is `ID_URL_FIELD` field or string in valid format.
    """
    if value in [None, 'None', '', b'None', b'', False]:
        return False
    if isinstance(value, ID_URL_FIELD):
        return True
    if not strng.is_string(value):
        return False
    v = strng.to_text(value)
    if not v.startswith('http') or not v.endswith('.xml') or v.count('://') != 1:
        return False
    return True


def to_bin(idurl):
    """
    Translates `ID_URL_FIELD` to binary string.
    """
    if isinstance(idurl, ID_URL_FIELD):
        return idurl.to_bin()
    if idurl in [None, 'None', '', b'None', b'', False]:
        return b''
    return strng.to_bin(idurl)


def to_original(idurl):
    """
    Translates `ID_URL_FIELD` to binary string, but returns its original value.
    """
    if isinstance(idurl, ID_URL_FIELD):
        return idurl.original()
    if idurl in [None, 'None', '', b'None', b'', False]:
        return b''
    return strng.to_bin(idurl)


def to_list(iterable_object, as_field=True, as_bin=False, as_original=False):
    """
    Creates list of desired objects from given `iterable_object`.
    """
    if not iterable_object:
        return iterable_object
    if as_original:
        return list(map(to_original, iterable_object))
    if as_field:
        return list(map(field, iterable_object))
    if as_bin:
        return list(map(to_bin, iterable_object))
    return list(map(strng.to_text, iterable_object))


def to_bin_list(iterable_object):
    """
    Just an alias for to_list().
    """
    if not iterable_object:
        return iterable_object
    return to_list(iterable_object, as_field=False, as_bin=True)


def to_original_list(iterable_object):
    """
    Just an alias for to_list() to extract original values from idurl's.
    """
    if not iterable_object:
        return iterable_object
    return to_list(iterable_object, as_original=True)


def to_bin_dict(idurl_dict):
    """
    Translates dictionary keys into binary strings if they were `ID_URL_FIELD` objects.
    """
    return {to_bin(k): v for k, v in idurl_dict.items()}


def is_in(idurl, iterable_object, as_field=True, as_bin=False):
    """
    Equivalent of `idurl in iterable_object`.
    Because it can be that you need to compare not `ID_URL_FIELD` objects in memory but normal strings.
    So then you will prefer to avoid translating into field object.
    """
    if not iterable_object:
        return False
    if as_field:
        return field(idurl) in fields_list(iterable_object)
    if as_bin:
        return to_bin(idurl) in to_bin_list(iterable_object)
    return strng.to_text(idurl) in to_list(iterable_object, as_field=False, as_bin=False)


def is_not_in(idurl, iterable_object, as_field=True, as_bin=False):
    """
    Vise-versa of `is_in()` method.
    """
    return not is_in(idurl=idurl, iterable_object=iterable_object, as_field=as_field, as_bin=as_bin)


def get_from_dict(idurl, dict_object, default=None, as_field=True, as_bin=False):
    """
    Equivalent of `{<some dict>}.get(idurl, default)`.
    Because it can be that you need to keep not `ID_URL_FIELD` objects in your dictionary but a normal strings.
    So then you will prefer to avoid translating into field object.
    """
    if as_field:
        return dict_object.get(field(idurl), default)
    if as_bin:
        return dict_object.get(to_bin(idurl), default)
    return dict_object.get(strng.to_text(idurl), default)


def is_cached(idurl):
    """
    Return True if given identity was already cached - that means I know his public key.
    """
    global _KnownIDURLs
    if isinstance(idurl, ID_URL_FIELD):
        idurl = idurl.to_bin()
    else:
        idurl = strng.to_bin(idurl)
    cached = idurl in _KnownIDURLs
    if not cached:
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, cached=cached)
    return cached


def is_empty(idurl):
    """
    Return True if given input is None, empty string or empty ID_URL_FIELD object.
    """
    if isinstance(idurl, ID_URL_FIELD):
        return not bool(idurl)
    if idurl in [None, 'None', '', b'None', b'', False]:
        return True
    return not bool(idurl)


def is_some_empty(iterable_object):
    """
    Returns True if given iterable_object contains some empty idurl field.
    """
    return is_in(ID_URL_FIELD(b''), iterable_object=iterable_object, as_field=True, as_bin=False)


def is_the_same(idurl1, idurl2):
    """
    Compares two ID_URL_FIELD objects or binary strings taking in account if those IDURLs are already cached.
    """
    idurl1 = field(idurl1)
    idurl2 = field(idurl2)
    if not idurl1 or not idurl2:
        return False
    if is_cached(idurl1) and is_cached(idurl2):
        return idurl1 == idurl2
    return idurl1.to_bin() == idurl2.to_bin()


def empty_count(iterable_object):
    """
    Returns number of empty idurl fields or empty strings found in given `iterable_object`.
    """
    count = 0
    for idurl in iterable_object:
        if is_empty(idurl):
            count += 1
    return count


def get_latest_revision(idurl):
    """
    Return latest known IDURL (as binary string) and revision number for given idurl field or string.
    This info is extracted from in-memory "index" of all known identity objects.
    """
    global _MergedIDURLs
    global _KnownIDURLs
    latest_rev = -1
    latest_idurl = b''
    idurl_bin = to_bin(idurl)
    if not idurl_bin:
        return latest_idurl, latest_rev
    if idurl_bin not in _KnownIDURLs:
        return latest_idurl, latest_rev
    pub_key = _KnownIDURLs[idurl_bin]
    if pub_key not in _MergedIDURLs:
        lg.warn('idurl %r is known but has no known revisions yet' % idurl_bin)
        return latest_idurl, latest_rev
    for rev, another_idurl in _MergedIDURLs[pub_key].items():
        if rev >= latest_rev:
            latest_idurl = another_idurl
            latest_rev = rev
    return latest_idurl, latest_rev


def get_latest_ident(pub_key):
    global _KnownUsers
    from bitdust.userid import identity
    user_path = _KnownUsers.get(pub_key)
    if not user_path:
        return None
    user_identity_files = sorted(map(int, os.listdir(user_path)))
    if len(user_identity_files) == 0:
        lg.warn('identity history is broken, public key is known, but no identity files found')
    latest_revision = -1
    latest_ident = None
    known_revisions = set()
    for_cleanup = []
    for id_file in user_identity_files:
        identity_file_path = os.path.join(user_path, strng.to_text(id_file))
        xmlsrc = local_fs.ReadBinaryFile(identity_file_path)
        one_id_obj = identity.identity(xmlsrc=xmlsrc)
        if not one_id_obj.isCorrect():
            lg.warn('identity history is broken, identity in the file %r is not correct' % identity_file_path)
            for_cleanup.append(identity_file_path)
            continue
        if not one_id_obj.Valid():
            lg.warn('identity history is broken, identity in the file %r is not valid' % identity_file_path)
            for_cleanup.append(identity_file_path)
            continue
        if pub_key != one_id_obj.getPublicKey():
            lg.err('identity history is broken, public key not matching in the file %r' % identity_file_path)
            for_cleanup.append(identity_file_path)
            continue
        known_revisions.add(one_id_obj.getRevisionValue())
        if one_id_obj.getRevisionValue() > latest_revision:
            latest_revision = one_id_obj.getRevisionValue()
            latest_ident = one_id_obj
    return latest_ident


def list_known_idurls(idurl, num_revisions=5, include_revisions=False):
    """
    Return latest known revisions of given `idurl` (as binary strings) and revision numbers as a list of tuples.
    This info is extracted from in-memory "index" of all known identity objects.
    """
    global _MergedIDURLs
    global _KnownIDURLs
    idurl_bin = to_bin(idurl)
    if not idurl_bin:
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, ret=idurl_bin)
        if include_revisions:
            return [(idurl_bin, -1)]
        return [idurl_bin]
    if idurl_bin not in _KnownIDURLs:
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, ret=idurl_bin)
        if include_revisions:
            return [(idurl_bin, -1)]
        return [idurl_bin]
    pub_key = _KnownIDURLs[idurl_bin]
    if pub_key not in _MergedIDURLs:
        lg.warn('idurl %r does not have any known revisions' % idurl_bin)
        if include_revisions:
            return [(idurl_bin, -1)]
        return [idurl_bin]
    known_revisions = sorted(_MergedIDURLs[pub_key].keys(), reverse=True)
    results = []
    for rev in known_revisions:
        another_idurl = _MergedIDURLs[pub_key][rev]
        if include_revisions:
            if another_idurl not in [i[0] for i in results]:
                results.append((another_idurl, rev))
        else:
            if another_idurl not in results:
                results.append(another_idurl)
        if len(results) >= num_revisions:
            break
    if _Debug:
        lg.args(_DebugLevel, idurl=idurl, ret=results)
    return results


def idurl_to_id(idurl_text, by_parts=False):
    """
    Translates raw IDURL string (not ID_URL_FIELD) into global id short form:
        "http://somehost.com/alice.xml" -> "alice@somehost.com"
    """
    if not idurl_text:
        if by_parts:
            return '', ''
        return idurl_text
    _, host, port, _, filename = nameurl.UrlParseFast(idurl_text)
    if filename.count('.'):
        username = filename.split('.')[0]
    else:
        username = filename
    if port:
        host = '%s_%s' % (host, port)
    if by_parts:
        return username, host
    return '%s@%s' % (username, host)


#------------------------------------------------------------------------------


class ID_URL_FIELD(object):

    """
    A class represents a valid, verified and synced IDURL identifier of a device.
    The IDURL is always corresponding to the identity file.

    When your identity file is updated due to rotation to another identity server,
    the "host" component of your IDURL is changed:
        `http://old-server/alice.xml` will become `http://new-server.org/alice.xml`

    The IDURL can also be presented in a shorter form, which is also called global user ID, so:
        `alice@old-server.com` will become `alice@new-server.org`

    All that is handled automatically and your instance of `ID_URL_FIELD` will receive updated info automatically.
    When incoming identity files are first received, processed and cached your `ID_URL_FIELD` variable is
    automatically synchornized using `ID_URL_FIELD.refresh()` method.

    This is why you can always trust and be able to compare two user IDs and verify recipient/sender identity.
    """

    def __init__(self, idurl):
        self.current = b''
        self.current_as_string = ''
        self.current_id = ''
        self.latest = b''
        self.latest_as_string = ''
        self.latest_id = ''
        self.latest_revision = -1
        self._unique_name = ''
        if isinstance(idurl, ID_URL_FIELD):
            self.current = idurl.current
        else:
            if idurl in [None, 'None', '', b'None', b'', False]:
                self.current = b''
            else:
                self.current = strng.to_bin(idurl.strip())
        self.current_as_string = strng.to_text(self.current)
        username, current_host = idurl_to_id(self.current, by_parts=True)
        self.username = username
        self.current_host = current_host
        self.current_id = '%s@%s' % (self.username, self.current_host)
        self.latest, self.latest_revision = get_latest_revision(self.current)
        if not self.latest:
            self.latest = self.current
            self.latest_revision = -1
        self.latest_as_string = strng.to_text(self.latest)
        latest_username, latest_host = idurl_to_id(self.latest, by_parts=True)
        if latest_username != self.username:
            caller_code = sys._getframe().f_back.f_code
            caller_method = caller_code.co_name
            caller_modul = os.path.basename(caller_code.co_filename).replace('.py', '')
            if caller_method.count('lambda') or caller_method == 'field':
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = ValueError('tried to modify username of the identity %r -> %r' % (self.current, self.latest))
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc
        self.latest_host = latest_host
        self.latest_id = '%s@%s' % (self.username, self.latest_host)
        if _Debug:
            lg.out(_DebugLevel*2, 'NEW ID_URL_FIELD(%r) with id=%r latest=%r' % (self.current, id(self), self.latest))

    def __del__(self):
        try:
            if _Debug:
                lg.out(_DebugLevel*2, 'DELETED ID_URL_FIELD(%r) with id=%r latest=%r' % (self.current, id(self), self.latest))
        except:
            lg.exc()

    def __eq__(self, idurl):
        # always check type : must be `ID_URL_FIELD`
        if not isinstance(idurl, ID_URL_FIELD):
            # to be able to compare with empty value lets make an exception
            if idurl in [None, 'None', '', b'None', b'', False]:
                return not bool(self.latest)
            # in other cases must raise an exception
            caller_code = sys._getframe().f_back.f_code
            caller_method = caller_code.co_name
            caller_modul = os.path.basename(caller_code.co_filename).replace('.py', '')
            if caller_method.count('lambda'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = TypeError('tried to compare ID_URL_FIELD(%r) with %r of type %r' % (self.latest_as_string, idurl, type(idurl)))
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc

        # could be empty field also
        if not idurl:
            return not bool(self.latest)

        # check if we know both sources
        my_pub_key = self.to_public_key(raise_error=False)
        other_pub_key = idurl.to_public_key(raise_error=False)
        if my_pub_key is None or other_pub_key is None:
            # if we do not know some of the sources - so can't be sure
            caller_code = sys._getframe().f_back.f_code
            caller_method = caller_code.co_name
            caller_modul = os.path.basename(caller_code.co_filename).replace('.py', '')
            if caller_method.count('lambda') or caller_method.startswith('_'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            if my_pub_key is None:
                exc = KeyError('unknown idurl %r in %s.%s' % (self.current, caller_modul, caller_method))
            else:
                exc = KeyError('unknown idurl %r in %s.%s' % (idurl.current, caller_modul, caller_method))
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc

        # now compare based on public key
        result = (other_pub_key == my_pub_key)
        if _Debug:
            lg.args(_DebugLevel*2, idurl=idurl, current=self.current, latest=self.latest, result=result)
        return result

    def __ne__(self, idurl):
        # always check type : must be `ID_URL_FIELD`
        if not isinstance(idurl, ID_URL_FIELD):
            # to be able to compare with empty value lets make an exception
            if idurl in [None, 'None', '', b'None', b'', False]:
                return bool(self.latest)
            # in other cases must raise an exception
            caller_code = sys._getframe().f_back.f_code
            caller_method = caller_code.co_name
            caller_modul = os.path.basename(caller_code.co_filename).replace('.py', '')
            if caller_method.count('lambda') or caller_method.startswith('_'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = TypeError('tried to compare ID_URL_FIELD(%r) with %r of type %r' % (self.latest_as_string, idurl, type(idurl)))
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc

        # could be empty field also
        if not idurl:
            return bool(self.latest)

        # check if we know both sources
        my_pub_key = self.to_public_key(raise_error=True)
        other_pub_key = idurl.to_public_key(raise_error=True)
        if my_pub_key is None or other_pub_key is None:
            # if we do not know some of the sources - so can't be sure
            caller_code = sys._getframe().f_back.f_code
            caller_method = caller_code.co_name
            caller_modul = os.path.basename(caller_code.co_filename).replace('.py', '')
            if caller_method.count('lambda') or caller_method.startswith('_'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            if my_pub_key is None:
                exc = KeyError('unknown idurl %r in %s.%s' % (self.current, caller_modul, caller_method))
            else:
                exc = KeyError('unknown idurl %r in %s.%s' % (idurl.current, caller_modul, caller_method))
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc

        # now compare based on public key
        result = (other_pub_key != my_pub_key)
        if _Debug:
            lg.args(_DebugLevel*2, idurl=idurl, current=self.current, latest=self.latest, result=result)
        return result

    def __hash__(self):
        # this trick should make `idurl in some_dictionary` work correctly
        # if idurl1 and idurl2 are different sources of same identity they both must be matching
        # so it must never happen like that: (idurl1 in some_dictionary) and (idurl2 in some_dictionary)
        # same check you can do in a different way: `id_url.is_in(idurl, some_dictionary)`
        pub_key = self.to_public_key()
        hsh = pub_key.__hash__()
        if _Debug:
            lg.args(_DebugLevel*2, current=self.current, latest=self.latest, hash=hsh)
        return hsh

    def __repr__(self):
        if _Debug:
            lg.args(_DebugLevel*2, latest_as_string=self.latest_as_string)
        return '{%s%s}' % ('' if self.is_latest() else '*', self.latest_as_string)

    def __str__(self):
        if _Debug:
            lg.args(_DebugLevel*2, latest_as_string=self.latest_as_string)
        return self.latest_as_string

    def __bytes__(self):
        if _Debug:
            lg.args(_DebugLevel*2, latest=self.latest)
        return self.latest

    def __bool__(self):
        if _Debug:
            lg.args(_DebugLevel*2, latest=self.latest)
        return bool(self.latest)

    def __len__(self):
        if _Debug:
            lg.args(_DebugLevel*2, latest=self.latest)
        return len(self.latest)

    def refresh(self, replace_original=True):
        _latest, _latest_revision = get_latest_revision(self.current)
        if self.latest and self.latest == _latest:
            if _Debug:
                lg.args(_DebugLevel, latest=self.latest_as_string, refreshed=False)
            return False
        self.latest = _latest
        self.latest_revision = _latest_revision
        if not self.latest:
            self.latest = self.current
            self.latest_revision = -1
        self.latest_as_string = strng.to_text(self.latest)
        latest_username, latest_host = idurl_to_id(self.latest, by_parts=True)
        if latest_username != self.username:
            caller_code = sys._getframe().f_back.f_code
            caller_method = caller_code.co_name
            caller_modul = os.path.basename(caller_code.co_filename).replace('.py', '')
            if caller_method.count('lambda') or caller_method == 'field':
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = ValueError('while refreshing tried to modify username of the identity %r -> %r' % (self.current, self.latest))
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc
        self.latest_host = latest_host
        self.latest_id = '%s@%s' % (self.username, self.latest_host)
        if replace_original:
            self.current = self.latest
            self.current_as_string = self.latest_as_string
            self.current_id = self.latest_id
        if _Debug:
            lg.args(_DebugLevel, latest=self.latest_as_string, current=self.current_as_string, refreshed=True)
        return True

    def strip(self):
        if _Debug:
            lg.args(_DebugLevel*2, latest=self.latest_as_string)
        return self.latest

    def original(self):
        if _Debug:
            lg.args(_DebugLevel*2, current=self.current, latest=self.latest)
        return self.current

    def original_id(self):
        if _Debug:
            lg.args(_DebugLevel*2, current=self.current_id, latest=self.latest_id)
        return self.current_id

    def is_latest(self):
        if _Debug:
            lg.args(_DebugLevel*2, current=self.current, latest=self.latest)
        return self.latest and self.current == self.latest

    def to_id(self):
        if _Debug:
            lg.args(_DebugLevel*2, latest_id=self.latest_id)
        return self.latest_id

    def to_text(self):
        if _Debug:
            lg.args(_DebugLevel*2, latest=self.latest_as_string)
        return self.latest_as_string

    def to_bin(self):
        if _Debug:
            lg.args(_DebugLevel*2, latest=self.latest)
        return self.latest

    def to_original(self):
        if _Debug:
            lg.args(_DebugLevel*2, current=self.current, latest=self.latest)
        return self.current

    def to_public_key(self, raise_error=True):
        global _KnownIDURLs
        if _Debug:
            lg.args(_DebugLevel*2, latest=self.latest, current=self.current)
        if not self.current:
            return b''
        if self.current not in _KnownIDURLs:
            if not raise_error:
                return None
            caller_code = sys._getframe().f_back.f_code
            caller_method = caller_code.co_name
            caller_modul = os.path.basename(caller_code.co_filename).replace('.py', '')
            if caller_method.count('lambda') or caller_method.startswith('_'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = KeyError('unknown idurl %r in %s.%s' % (self.current, caller_modul, caller_method))
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc
        pub_key = _KnownIDURLs[self.current]
        return pub_key

    def unique_name(self, raise_error=True):
        if not self._unique_name:
            self._unique_name = '{}_{}'.format(
                self.username,
                strng.to_text(hashes.sha1(self.to_public_key(raise_error=raise_error), hexdigest=True)),
            )
        return self._unique_name
