#!/usr/bin/python
# id_url.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import sys
import tempfile

#------------------------------------------------------------------------------

from logs import lg

from system import bpio
from system import local_fs

from lib import strng

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
        one_user_identity_files = sorted(map(int, os.listdir(one_user_dir_path)))
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
            for known_idurl in known_id_obj.getSources():
                known_idurl = to_bin(known_idurl)
                if known_idurl not in _KnownIDURLs:
                    _KnownIDURLs[known_idurl] = known_id_obj.getPublicKey()
                    if _Debug:
                        lg.out(_DebugLevel, '    known IDURL added: %r' % known_idurl)
                else:
                    if _KnownIDURLs[known_idurl] != known_id_obj.getPublicKey():
                        _KnownIDURLs[known_idurl] = known_id_obj.getPublicKey()
                        lg.warn('another user had same identity source: %r' % known_idurl)
                if one_pub_key not in _MergedIDURLs:
                    _MergedIDURLs[one_pub_key] = {}
                if one_revision in _MergedIDURLs[one_pub_key] and _MergedIDURLs[one_pub_key][one_revision] != known_idurl:
                    lg.warn('rewriting existing identity revision %d %r -> %r' % (
                        one_revision, _MergedIDURLs[one_pub_key][one_revision], known_idurl))
                if one_revision not in _MergedIDURLs[one_pub_key]:
                    _MergedIDURLs[one_pub_key][one_revision] = to_bin(known_idurl)
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

def identity_cached(id_obj):
    """
    """
    global _IdentityHistoryDir
    global _KnownUsers
    global _KnownIDURLs
    global _MergedIDURLs
    from userid import identity
    pub_key = id_obj.getPublicKey()
    user_name = id_obj.getIDName()
    if _Debug:
        lg.args(_DebugLevel, user_name=user_name)
    is_identity_rotated = False
    if pub_key not in _KnownUsers:
        user_path = tempfile.mkdtemp(prefix=user_name+'@', dir=_IdentityHistoryDir)
        _KnownUsers[pub_key] = user_path
        first_identity_file_path = os.path.join(user_path, '0')
        local_fs.WriteBinaryFile(first_identity_file_path, id_obj.serialize())
        if _Debug:
            lg.out(_DebugLevel, '        wrote first item for user %r in identity history: %r' % (
                user_name, first_identity_file_path))
    else:
        user_path = _KnownUsers[pub_key]
        user_identity_files = sorted(map(int, os.listdir(user_path)))
        latest_identity_file_path = os.path.join(user_path, strng.to_text(user_identity_files[-1]))
        xmlsrc = local_fs.ReadBinaryFile(latest_identity_file_path)
        latest_id_obj = identity.identity(xmlsrc=xmlsrc)
        if latest_id_obj.getPublicKey() != id_obj.getPublicKey():
            raise Exception('identity history for user %r is broken, public key not matching' % user_name)
        if latest_id_obj.getIDName() != id_obj.getIDName():
            lg.warn('found another user name in identity history for user %r : %r' % (user_name, latest_id_obj.getIDName(), ))
        latest_sources = list(map(lambda i: i.to_bin(), latest_id_obj.getSources()))
        new_sources = list(map(lambda i: i.to_bin(), id_obj.getSources()))
        if latest_sources == new_sources:
            local_fs.WriteBinaryFile(latest_identity_file_path, id_obj.serialize())
            if _Debug:
                lg.out(_DebugLevel, '        latest identity sources for user %r did not changed, updated file %r' % (
                    user_name, latest_identity_file_path))
        else:
            next_identity_file = user_identity_files[-1] + 1
            next_identity_file_path = os.path.join(user_path, strng.to_text(next_identity_file))
            local_fs.WriteBinaryFile(next_identity_file_path, id_obj.serialize())
            is_identity_rotated = True
            if _Debug:
                lg.out(_DebugLevel, '        identity sources for user %r changed, wrote new item in the history: %r' % (
                    user_name, next_identity_file_path))
    new_revision = id_obj.getRevisionValue()
    for new_idurl in id_obj.getSources():
        new_idurl = to_bin(new_idurl)
        if new_idurl not in _KnownIDURLs:
            _KnownIDURLs[new_idurl] = id_obj.getPublicKey()
            if _Debug:
                lg.out(_DebugLevel, '    known IDURL added: %r' % new_idurl)
        else:
            if _KnownIDURLs[new_idurl] != id_obj.getPublicKey():
                lg.warn('another user had same identity source: %r' % new_idurl)
                _KnownIDURLs[new_idurl] = id_obj.getPublicKey()
        if pub_key not in _MergedIDURLs:
            _MergedIDURLs[pub_key] = {}
        if new_revision in _MergedIDURLs[pub_key] and _MergedIDURLs[pub_key][new_revision] != new_idurl:
            lg.warn('rewriting existing identity revision %d %r -> %r' % (
                new_revision, _MergedIDURLs[pub_key][new_revision], new_idurl))
        if new_revision not in _MergedIDURLs[pub_key]:
            _MergedIDURLs[pub_key][new_revision] = to_bin(new_idurl)
            if _Debug:
                lg.out(_DebugLevel, '        added new revision %d for user %r, total revisions %d' % (
                    new_revision, user_name, len(_MergedIDURLs[pub_key])))
    if is_identity_rotated:
        from main import events
        events.send('identity-rotated', data=dict(
            old_idurls=latest_id_obj.getSources(as_fields=False),
            new_idurls=id_obj.getSources(as_fields=False),
        ))
        if latest_id_obj.getIDURL(as_field=False) != id_obj.getIDURL(as_field=False):
            events.send('identity-url-changed', data=dict(
                old_idurl=latest_id_obj.getIDURL(as_field=False),
                new_idurl=id_obj.getIDURL(as_field=False),
            ))
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
        lg.warn('will try to find %r in local identity cache' % idurl)
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


def to_list(iterable_object, as_field=True, as_bin=False):
    """
    Creates list of desired objects from given `iterable_object`.
    """
    if not iterable_object:
        return iterable_object
    if as_field:
        return list(map(field, iterable_object))
    if as_bin:
        return list(map(to_bin, iterable_object))
    return list(iterable_object)


def to_bin_list(iterable_object):
    """
    Just an alias for to_list().
    """
    if not iterable_object:
        return iterable_object
    return to_list(iterable_object, as_field=False, as_bin=True)


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
    return idurl in to_list(iterable_object, as_field=False, as_bin=False)


def is_not_in(idurl, iterable_object, as_field=True, as_bin=False):
    """
    Vise versa of `is_in()` method.
    """
    return (not is_in(idurl=idurl, iterable_object=iterable_object, as_field=as_field, as_bin=as_bin))


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
    return dict_object.get(idurl, default)


def is_cached(idurl):
    """
    Return True if given identity was already cached.
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
    return bool(idurl)


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
            rev = latest_rev
    return latest_idurl, latest_rev

#------------------------------------------------------------------------------

class ID_URL_FIELD(object):
    
    def __init__(self, idurl):
        self.current = b''
        self.latest = b''
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
            lg.out(_DebugLevel, 'NEW ID_URL_FIELD(%r) with id=%r latest=%r' % (self.current, id(self), self.latest))

    def __del__(self):
        try:
            if _Debug:
                lg.out(_DebugLevel, 'DELETED ID_URL_FIELD(%r) with id=%r latest=%r' % (self.current, id(self), self.latest))
        except:
            lg.exc()

    def __eq__(self, idurl):
        # always check type : must be `ID_URL_FIELD`
        if not isinstance(idurl, ID_URL_FIELD):
            # to be able to compare with empty value lets make an exception
            if idurl in [None, 'None', '', b'None', b'', False, ]:
                return not bool(self.latest)
            # in other cases must raise an exception
            caller_method = sys._getframe().f_back.f_code.co_name
            if caller_method.count('lambda'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = TypeError('tried to compare ID_URL_FIELD(%r) with %r of type %r' % (
                self.latest_as_string, idurl, type(idurl)))
            lg.exc(msg='called from %s()' % caller_method, exc_value=exc)
            raise exc

        # could be empty field also
        if not idurl:
            return not bool(self.latest)

        # check if we know both sources
        my_pub_key = self.to_public_key(raise_error=False) 
        other_pub_key = idurl.to_public_key(raise_error=False)
        if my_pub_key is None or other_pub_key is None:
            # if we do not know some of the sources - so can't be sure
            caller_method = sys._getframe().f_back.f_code.co_name
            if caller_method.count('lambda') or caller_method.startswith('_'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            if my_pub_key is None:
                exc = KeyError('unknown idurl: %r' % self.current)
            else:
                exc = KeyError('unknown idurl: %r' % idurl.current)
            lg.exc(msg='called from %s()' % caller_method, exc_value=exc)
            raise exc

        # now compare based on public key
        result = (other_pub_key == my_pub_key)
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, current=self.current, latest=self.latest, result=result)
        return result

    def __ne__(self, idurl):
        # always check type : must be `ID_URL_FIELD`
        if not isinstance(idurl, ID_URL_FIELD):
            # to be able to compare with empty value lets make an exception
            if idurl in [None, 'None', '', b'None', b'', False, ]:
                return bool(self.latest)
            # in other cases must raise an exception
            caller_method = sys._getframe().f_back.f_code.co_name
            if caller_method.count('lambda') or caller_method.startswith('_'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = TypeError('tried to compare ID_URL_FIELD(%r) with %r of type %r' % (
                self.latest_as_string, idurl, type(idurl)))
            lg.exc(msg='called from %s()' % caller_method, exc_value=exc)
            raise exc

        # could be empty field also
        if not idurl:
            return bool(self.latest)

        # check if we know both sources
        my_pub_key = self.to_public_key(raise_error=True) 
        other_pub_key = idurl.to_public_key(raise_error=True)
        if my_pub_key is None or other_pub_key is None:
            # if we do not know some of the sources - so can't be sure
            caller_method = sys._getframe().f_back.f_code.co_name
            if caller_method.count('lambda') or caller_method.startswith('_'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            if my_pub_key is None:
                exc = KeyError('unknown idurl: %r' % self.current)
            else:
                exc = KeyError('unknown idurl: %r' % idurl.current)
            lg.exc(msg='called from %s()' % caller_method, exc_value=exc)
            raise exc

        # now compare based on public key
        result = (other_pub_key != my_pub_key)
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, current=self.current, latest=self.latest, result=result)
        return result

    def __hash__(self):
        # this trick should make `idurl in some_dictionary` work correctly
        # if idurl1 and idurl2 are different sources of same identity they both must be matching
        # so it must never happen like that: (idurl1 in some_dictionary) and (idurl2 in some_dictionary)
        # same check you can do in a different way: `id_url.is_in(idurl, some_dictionary)`
        pub_key = self.to_public_key()
        hsh = pub_key.__hash__()
        if _Debug:
            lg.args(_DebugLevel, current=self.current, latest=self.latest, hash=hsh)
        return hsh

    def __repr__(self):
        if _Debug:
            lg.args(_DebugLevel, latest_as_string=self.latest_as_string)
        return self.latest_as_string

    def __str__(self):
        if _Debug:
            lg.args(_DebugLevel, latest_as_string=self.latest_as_string)
        return self.latest_as_string

    def __bytes__(self):
        if _Debug:
            lg.args(_DebugLevel, latest=self.latest)
        return self.latest

    def __bool__(self):
        if _Debug:
            lg.args(_DebugLevel, latest=self.latest)
        return bool(self.latest)

    def __len__(self):
        if _Debug:
            lg.args(_DebugLevel, latest=self.latest)
        return len(self.latest)

    def strip(self):
        if _Debug:
            lg.args(_DebugLevel, latest=self.latest_as_string)
        return self.latest

    def original(self):
        if _Debug:
            lg.args(_DebugLevel, current=self.current, latest=self.latest)
        return self.current

    def is_latest(self):
        if _Debug:
            lg.args(_DebugLevel, current=self.current, latest=self.latest)
        return self.latest and self.current == self.latest

    def to_id(self):
        if _Debug:
            lg.args(_DebugLevel, latest_id=self.latest_id)
        return self.latest_id

    def to_text(self):
        if _Debug:
            lg.args(_DebugLevel, latest=self.latest_as_string)
        return self.latest_as_string

    def to_bin(self):
        if _Debug:
            lg.args(_DebugLevel, latest=self.latest)
        return self.latest

    def to_public_key(self, raise_error=True):
        global _KnownIDURLs
        if _Debug:
            lg.args(_DebugLevel, latest=self.latest, current=self.current)
        if not self.current:
            return b''
        if self.current not in _KnownIDURLs:
            if not raise_error:
                return None
            caller_method = sys._getframe().f_back.f_code.co_name
            if caller_method.count('lambda') or caller_method.startswith('_'):
                caller_method = sys._getframe(1).f_back.f_code.co_name
            exc = KeyError('unknown idurl: %r' % self.current)
            lg.exc(msg='called from %s()' % caller_method, exc_value=exc)
            raise exc
        pub_key = _KnownIDURLs[self.current]
        return pub_key
