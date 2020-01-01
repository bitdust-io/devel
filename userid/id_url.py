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

from logs import lg

from system import bpio
from system import local_fs

from lib import strng
from lib import nameurl

from main import settings

from userid import global_id

#------------------------------------------------------------------------------

_IdentityHistoryDir = None
# TODO: if this dictionary grow too much use CodernityDB instead of in-memory storage
_KnownUsers = {}
_KnownIDURLs = {}
_MergedIDURLs = {}
_Ready = False

#------------------------------------------------------------------------------

def init():
    """
    """
    global _IdentityHistoryDir
    global _KnownUsers
    global _KnownIDURLs
    global _MergedIDURLs
    global _Ready
    from userid import identity
    if _Debug:
        lg.out(_DebugLevel, "id_url.init")
    if not _IdentityHistoryDir:
        _IdentityHistoryDir = settings.IdentityHistoryDir()
    if not os.path.exists(_IdentityHistoryDir):
        bpio._dir_make(_IdentityHistoryDir)
        lg.info('created new folder %r' % _IdentityHistoryDir)
    else:
        lg.info('using existing folder %r' % _IdentityHistoryDir)
    for one_user_dir in os.listdir(_IdentityHistoryDir):
        one_user_dir_path = os.path.join(_IdentityHistoryDir, one_user_dir)
        one_user_identity_files = []
        for one_filename in os.listdir(one_user_dir_path):
            try:
                one_ident_number = int(one_filename)
            except:
                lg.exc()
                continue
            one_user_identity_files.append(one_ident_number)
        if _Debug:
            lg.out(_DebugLevel, 'id_url.init   found %d historical records in %r' % (len(one_user_identity_files), one_user_dir_path, ))
        for one_ident_file in one_user_identity_files:
            one_ident_path = os.path.join(one_user_dir_path, strng.to_text(one_ident_file))
            try:
                xmlsrc = local_fs.ReadTextFile(one_ident_path)
                known_id_obj = identity.identity(xmlsrc=xmlsrc)
                if not known_id_obj.isCorrect():
                    raise Exception('identity history in %r is broken, identity is not correct: %r' % (
                        one_user_dir, one_ident_path))
                if not known_id_obj.Valid():
                    raise Exception('identity history in %r is broken, identity is not valid: %r' % (
                        one_user_dir, one_ident_path))
            except:
                lg.exc()
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
                            lg.warn('rewriting existing identity revision %d : %r -> %r' % (
                                one_revision, _MergedIDURLs[one_pub_key][one_revision], known_idurl))
                    _MergedIDURLs[one_pub_key][one_revision] = known_idurl
                else:
                    _MergedIDURLs[one_pub_key][one_revision] = known_idurl
                    if _Debug:
                        lg.out(_DebugLevel, '        revision %d merged with other %d known items' % (
                            one_revision, len(_MergedIDURLs[one_pub_key])))
    _Ready = True


def shutdown():
    """
    """
    global _IdentityHistoryDir
    global _KnownIDURLs
    global _KnownUsers
    global _Ready
    global _MergedIDURLs
    _IdentityHistoryDir = None
    _KnownUsers = {}
    _KnownIDURLs = {}
    _MergedIDURLs = {}
    _Ready = False

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
    from userid import identity
    pub_key = new_id_obj.getPublicKey()
    user_name = new_id_obj.getIDName()
    if _Debug:
        lg.args(_DebugLevel, user_name=user_name)
    is_identity_rotated = False
    latest_id_obj = None
    latest_sources = []
    if pub_key not in _KnownUsers:
        user_path = tempfile.mkdtemp(prefix=user_name+'@', dir=_IdentityHistoryDir)
        _KnownUsers[pub_key] = user_path
        first_identity_file_path = os.path.join(user_path, '0')
        local_fs.WriteBinaryFile(first_identity_file_path, new_id_obj.serialize())
        if _Debug:
            lg.out(_DebugLevel, 'id_url.identity_cached wrote first item for user %r in identity history: %r' % (
                user_name, first_identity_file_path))
    else:
        user_path = _KnownUsers[pub_key]
        user_identity_files = sorted(map(int, os.listdir(user_path)))
        if len(user_identity_files) == 0:
            raise Exception('identity history for user %r is broken, public key is known, but no identity files found' % user_name)
        latest_identity_file_path = ''
        latest_pub_key = None
        latest_revision = -1
        known_revisions = set()
        for id_file in user_identity_files:
            identity_file_path = os.path.join(user_path, strng.to_text(id_file))
            xmlsrc = local_fs.ReadBinaryFile(identity_file_path)
            one_id_obj = identity.identity(xmlsrc=xmlsrc)
            if not one_id_obj.isCorrect():
                lg.err('identity history for user %r is broken, identity in the file %r is not correct' % (user_name, identity_file_path))
                continue
            if not one_id_obj.Valid():
                lg.err('identity history for user %r is broken, identity in the file %r is not valid' % (user_name, identity_file_path))
                continue
            if not latest_pub_key:
                latest_pub_key = one_id_obj.getPublicKey()
            if latest_pub_key != one_id_obj.getPublicKey():
                lg.err('identity history for user %r is broken, public key not matching in the file %r' % (user_name, identity_file_path))
                continue
            known_revisions.add(one_id_obj.getRevisionValue())
            if one_id_obj.getRevisionValue() > latest_revision:
                latest_revision = one_id_obj.getRevisionValue()
                latest_identity_file_path = identity_file_path
        xmlsrc = local_fs.ReadBinaryFile(latest_identity_file_path)
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
                    lg.out(_DebugLevel, 'id_url.identity_cached latest identity sources for user %r did not changed, updated file %r' % (
                        user_name, latest_identity_file_path))
            else:
                next_identity_file = user_identity_files[-1] + 1
                next_identity_file_path = os.path.join(user_path, strng.to_text(next_identity_file))
                local_fs.WriteBinaryFile(next_identity_file_path, new_id_obj.serialize())
                is_identity_rotated = True
                if _Debug:
                    lg.out(_DebugLevel, 'id_url.identity_cached identity sources for user %r changed, wrote new item in the history: %r' % (
                        user_name, next_identity_file_path))
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
                        lg.warn('rewriting existing identity revision %d : %r -> %r' % (
                        new_revision, _MergedIDURLs[pub_key][new_revision], new_idurl))
            _MergedIDURLs[pub_key][new_revision] = new_idurl
        else:
            _MergedIDURLs[pub_key][new_revision] = new_idurl
            if _Debug:
                lg.out(_DebugLevel, 'id_url.identity_cached added new revision %d for user %r, total revisions %d: %r -> %r' % (
                    new_revision, user_name, len(_MergedIDURLs[pub_key]), prev_idurl, new_idurl))
    if _Debug:
        lg.args(_DebugLevel, is_identity_rotated=is_identity_rotated, latest_id_obj=bool(latest_id_obj))
    if is_identity_rotated and latest_id_obj is not None:
        latest_revision = latest_id_obj.getRevisionValue()
        if _Debug:
            lg.args(_DebugLevel, new_revision=new_revision, latest_revision=latest_revision)
        if new_revision > latest_revision:
            lg.info('found rotated identity after caching %r -> %r' % (
                latest_id_obj.getSources(as_originals=True)[0], new_sources[0]))
            from main import events
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
            from userid import my_id
            if my_id.isLocalIdentityReady():
                if my_id.getLocalID() == new_id_obj.getIDURL():
                    events.send('my-identity-rotated', data=dict(
                        old_idurls=latest_id_obj.getSources(as_originals=True),
                        new_idurls=new_id_obj.getSources(as_originals=True),
                        old_revision=latest_id_obj.getRevisionValue(),
                        new_revision=new_revision,
                    ))
                    if latest_id_obj.getIDURL(as_original=True) != new_id_obj.getIDURL(as_original=True):
                        events.send('my-identity-url-changed', data=dict(
                            old_idurl=latest_id_obj.getIDURL(as_original=True),
                            new_idurl=new_id_obj.getIDURL(as_original=True),
                            old_revision=latest_id_obj.getRevisionValue(),
                            new_revision=new_revision,
                        ))
        else:
            lg.warn('cached out-dated revision %d for %r' % (new_revision, new_sources[0]))
    else:
        if _Debug:
            lg.out(_DebugLevel, 'id_url.identity_cached revision %d for %r' % (new_revision, new_sources[0]))
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
    if idurl in [None, 'None', '', b'None', b'', False, ]:
        return ID_URL_FIELD(idurl)
    idurl = strng.to_bin(idurl.strip())
    if idurl not in _KnownIDURLs:
        if _Debug:
            lg.out(_DebugLevel, 'id_url.field   will try to find %r in local identity cache' % idurl)
        from contacts import identitydb
        cached_ident = identitydb.get(idurl)
        if cached_ident:
            identity_cached(cached_ident)
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


def to_bin(idurl):
    """
    Translates `ID_URL_FIELD` to binary string.
    """
    if isinstance(idurl, ID_URL_FIELD):
        return idurl.to_bin()
    if idurl in [None, 'None', '', b'None', b'', False, ]:
        return b''
    return strng.to_bin(idurl)


def to_original(idurl):
    """
    Translates `ID_URL_FIELD` to binary string, but returns its original value.
    """
    if isinstance(idurl, ID_URL_FIELD):
        return idurl.original()
    if idurl in [None, 'None', '', b'None', b'', False, ]:
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
    if _Debug:
        lg.args(_DebugLevel, idurl=idurl, cached=cached)
    return cached


def is_empty(idurl):
    """
    Return True if given input is None, empty string or empty ID_URL_FIELD object.
    """
    if isinstance(idurl, ID_URL_FIELD):
        return not bool(idurl)
    if idurl in [None, 'None', '', b'None', b'', False, ]:
        return True
    return not bool(idurl)


def is_some_empty(iterable_object):
    """
    Returns True if given iterable_object contains some empty idurl field.
    """
    return is_in(ID_URL_FIELD(b''), iterable_object=iterable_object, as_field=True, as_bin=False)


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
        lg.warn('idurl %r does not have any known revisions' % idurl_bin)
        return latest_idurl, latest_rev
    for rev, another_idurl in _MergedIDURLs[pub_key].items():
        if rev >= latest_rev:
            latest_idurl = another_idurl
            latest_rev = rev
    return latest_idurl, latest_rev
    
#------------------------------------------------------------------------------

class ID_URL_FIELD(object):
    
    def __init__(self, idurl):
        self.current = b''
        self.current_as_string = ''
        self.current_id = ''
        self.latest = b''
        self.latest_as_string = ''
        self.latest_id = ''
        self.latest_revision = -1
        if isinstance(idurl, ID_URL_FIELD):
            self.current = idurl.current
        else:
            if idurl in [None, 'None', '', b'None', b'', False, ]:
                self.current = b''
            else:
                self.current = strng.to_bin(idurl.strip())
        self.current_as_string = strng.to_text(self.current)
        self.current_id = global_id.idurl2glob(self.current)
        self.latest, self.latest_revision = get_latest_revision(self.current)
        if not self.latest:
            self.latest = self.current
            self.latest_revision = -1
        self.latest_as_string = strng.to_text(self.latest)
        self.latest_id = global_id.idurl2glob(self.latest)
        if _Debug:
            lg.out(_DebugLevel * 2, 'NEW ID_URL_FIELD(%r) with id=%r latest=%r' % (self.current, id(self), self.latest))

    def __del__(self):
        try:
            if _Debug:
                lg.out(_DebugLevel * 2, 'DELETED ID_URL_FIELD(%r) with id=%r latest=%r' % (self.current, id(self), self.latest))
        except:
            lg.exc()

    def __eq__(self, idurl):
        # always check type : must be `ID_URL_FIELD`
        if not isinstance(idurl, ID_URL_FIELD):
            # to be able to compare with empty value lets make an exception
            if idurl in [None, 'None', '', b'None', b'', False, ]:
                return not bool(self.latest)
            # in other cases must raise an exception
            caller_code = sys._getframe().f_back.f_code
            caller_method = caller_code.co_name
            caller_modul = os.path.basename(caller_code.co_filename).replace('.py', '')
            if caller_method.count('lambda'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = TypeError('tried to compare ID_URL_FIELD(%r) with %r of type %r' % (
                self.latest_as_string, idurl, type(idurl)))
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
                exc = KeyError('unknown idurl: %r' % self.current)
            else:
                exc = KeyError('unknown idurl: %r' % idurl.current)
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc

        # now compare based on public key
        result = (other_pub_key == my_pub_key)
        if _Debug:
            lg.args(_DebugLevel * 2, idurl=idurl, current=self.current, latest=self.latest, result=result)
        return result

    def __ne__(self, idurl):
        # always check type : must be `ID_URL_FIELD`
        if not isinstance(idurl, ID_URL_FIELD):
            # to be able to compare with empty value lets make an exception
            if idurl in [None, 'None', '', b'None', b'', False, ]:
                return bool(self.latest)
            # in other cases must raise an exception
            caller_code = sys._getframe().f_back.f_code
            caller_method = caller_code.co_name
            caller_modul = os.path.basename(caller_code.co_filename).replace('.py', '')
            if caller_method.count('lambda') or caller_method.startswith('_'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = TypeError('tried to compare ID_URL_FIELD(%r) with %r of type %r' % (
                self.latest_as_string, idurl, type(idurl)))
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
                exc = KeyError('unknown idurl: %r' % self.current)
            else:
                exc = KeyError('unknown idurl: %r' % idurl.current)
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc

        # now compare based on public key
        result = (other_pub_key != my_pub_key)
        if _Debug:
            lg.args(_DebugLevel * 2, idurl=idurl, current=self.current, latest=self.latest, result=result)
        return result

    def __hash__(self):
        # this trick should make `idurl in some_dictionary` work correctly
        # if idurl1 and idurl2 are different sources of same identity they both must be matching
        # so it must never happen like that: (idurl1 in some_dictionary) and (idurl2 in some_dictionary)
        # same check you can do in a different way: `id_url.is_in(idurl, some_dictionary)`
        pub_key = self.to_public_key()
        hsh = pub_key.__hash__()
        if _Debug:
            lg.args(_DebugLevel * 2, current=self.current, latest=self.latest, hash=hsh)
        return hsh

    def __repr__(self):
        if _Debug:
            lg.args(_DebugLevel * 2, latest_as_string=self.latest_as_string)
        return self.latest_as_string

    def __str__(self):
        if _Debug:
            lg.args(_DebugLevel * 2, latest_as_string=self.latest_as_string)
        return self.latest_as_string

    def __bytes__(self):
        if _Debug:
            lg.args(_DebugLevel * 2, latest=self.latest)
        return self.latest

    def __bool__(self):
        if _Debug:
            lg.args(_DebugLevel * 2, latest=self.latest)
        return bool(self.latest)

    def __len__(self):
        if _Debug:
            lg.args(_DebugLevel * 2, latest=self.latest)
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
        self.latest_id = global_id.idurl2glob(self.latest)
        if replace_original:
            self.current = self.latest
            self.current_as_string = self.latest_as_string
            self.current_id = self.latest_id
        if _Debug:
            lg.args(_DebugLevel, latest=self.latest_as_string, current=self.current_as_string, refreshed=True)
        return True

    def strip(self):
        if _Debug:
            lg.args(_DebugLevel * 2, latest=self.latest_as_string)
        return self.latest

    def original(self):
        if _Debug:
            lg.args(_DebugLevel * 2, current=self.current, latest=self.latest)
        return self.current

    def original_id(self):
        if _Debug:
            lg.args(_DebugLevel * 2, current=self.current_id, latest=self.latest_id)
        return self.current_id

    def is_latest(self):
        if _Debug:
            lg.args(_DebugLevel, current=self.current, latest=self.latest)
        return self.latest and self.current == self.latest

    def to_id(self):
        if _Debug:
            lg.args(_DebugLevel * 2, latest_id=self.latest_id)
        return self.latest_id

    def to_text(self):
        if _Debug:
            lg.args(_DebugLevel * 2, latest=self.latest_as_string)
        return self.latest_as_string

    def to_bin(self):
        if _Debug:
            lg.args(_DebugLevel * 2, latest=self.latest)
        return self.latest

    def to_original(self):
        if _Debug:
            lg.args(_DebugLevel * 2, current=self.current, latest=self.latest)
        return self.current

    def to_public_key(self, raise_error=True):
        global _KnownIDURLs
        if _Debug:
            lg.args(_DebugLevel * 2, latest=self.latest, current=self.current)
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
            exc = KeyError('unknown idurl: %r' % self.current)
            lg.exc(msg='called from %s.%s()' % (caller_modul, caller_method), exc_value=exc)
            raise exc
        pub_key = _KnownIDURLs[self.current]
        return pub_key
