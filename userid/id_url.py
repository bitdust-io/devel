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
import six

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
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
    _IdentityHistoryDir = settings.IdentityHistoryDir()
    if not os.path.exists(_IdentityHistoryDir):
        bpio._dir_make(_IdentityHistoryDir)
        lg.info('created new folder %r' % _IdentityHistoryDir)
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
            if one_pub_key not in _KnownUsers:
                _KnownUsers[one_pub_key] = one_user_dir_path
            for known_idurl in known_id_obj.getSources():
                known_idurl = strng.to_bin(known_idurl)
                if known_idurl not in _KnownIDURLs:
                    _KnownIDURLs[known_idurl] = known_id_obj.getPublicKey()
                else:
                    if _KnownIDURLs[known_idurl] != known_id_obj.getPublicKey():
                        _KnownIDURLs[known_idurl] = known_id_obj.getPublicKey()
                        lg.warn('another user had same identity source: %r' % known_idurl)
                if one_pub_key not in _MergedIDURLs:
                    _MergedIDURLs[one_pub_key] = []
                if known_idurl not in _MergedIDURLs[one_pub_key]:
                    _MergedIDURLs[one_pub_key].append(strng.to_bin(known_idurl))
    _Ready = True


def shutdown():
    """
    """
    global _IdentityHistoryDir
    global _KnownIDURLs
    global _KnownUsers
    global _Ready
    _IdentityHistoryDir = None
    _KnownUsers = {}
    _KnownIDURLs = {}
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
            lg.out(_DebugLevel, '    wrote first item to identity history: %r' % first_identity_file_path)
    else:
        user_path = _KnownUsers[pub_key]
        user_identity_files = sorted(map(int, os.listdir(user_path)))
        latest_identity_file_path = os.path.join(user_path, strng.to_text(user_identity_files[-1]))
        xmlsrc = local_fs.ReadBinaryFile(latest_identity_file_path)
        latest_id_obj = identity.identity(xmlsrc=xmlsrc)
        if latest_id_obj.getPublicKey() != id_obj.getPublicKey():
            raise Exception('identity history for user %r is broken, public key not matching')
        if latest_id_obj.getIDName() != id_obj.getIDName():
            raise Exception('identity history for user %r is broken, user name not matching')
        if latest_id_obj.getSources() == id_obj.getSources():
            local_fs.WriteBinaryFile(latest_identity_file_path, id_obj.serialize())
            if _Debug:
                lg.out(_DebugLevel, '    latest identity sources for user %r did not changed, updated file %r' % (
                    user_name, latest_identity_file_path))
        else:
            next_identity_file = user_identity_files[-1] + 1
            next_identity_file_path = os.path.join(user_path, strng.to_text(next_identity_file))
            local_fs.WriteBinaryFile(next_identity_file_path, id_obj.serialize())
            is_identity_rotated = True
            lg.info('identity sources for user %r changed, wrote new item in the history: %r' % (
                user_name, next_identity_file_path))
    for new_idurl in id_obj.getSources():
        new_idurl = strng.to_bin(new_idurl)
        if new_idurl not in _KnownIDURLs:
            _KnownIDURLs[new_idurl] = id_obj.getPublicKey()
        else:
            if _KnownIDURLs[new_idurl] != id_obj.getPublicKey():
                lg.warn('another user had same identity source: %r' % new_idurl)
                _KnownIDURLs[new_idurl] = id_obj.getPublicKey()
        if pub_key not in _MergedIDURLs:
            _MergedIDURLs[pub_key] = []
        if new_idurl not in _MergedIDURLs[pub_key]:
            _MergedIDURLs[pub_key].append(strng.to_bin(new_idurl))
            lg.info('added new identity source %r for user %r' % (new_idurl, user_name))
    if is_identity_rotated:
        from main import events
        events.send('identity-rotated', data=dict(
            old_idurls=latest_id_obj.getSources(),
            new_idurls=id_obj.getSources(),
        ))
    return True

#------------------------------------------------------------------------------

class ID_URL(object):
    
    def __init__(self, idurl):
        self.current = b''
        if isinstance(idurl, ID_URL):
            self.current = idurl.current
        else:
            if idurl in [None, 'None', '', b'None', b'', ]:
                self.current = b''
            else:
                self.current = strng.to_bin(idurl.strip())
        self.current_as_string = strng.to_text(self.current)
        self.current_id = global_id.idurl2glob(self.current)
        if _Debug:
            lg.out(_DebugLevel, 'NEW ID_URL: %r with id=%r' % (self.current, id(self)))

    def __del__(self):
        try:
            if _Debug:
                lg.out(_DebugLevel, 'DELETED ID_URL: %r with id=%r' % (self.current, id(self)))
        except:
            lg.exc()

    def __eq__(self, idurl):
        # first compare as strings
        if isinstance(idurl, ID_URL) and idurl.current == self.current:
            if _Debug:
                lg.args(_DebugLevel, idurl=idurl, current=self.current, result=True)
            return True
        if isinstance(idurl, six.binary_type) and idurl == self.current:
            if _Debug:
                lg.args(_DebugLevel, idurl=idurl, current=self.current, result=True)
            return True
        if isinstance(idurl, six.text_type) and strng.to_bin(idurl) == self.current:
            if _Debug:
                lg.args(_DebugLevel, idurl=idurl, current=self.current, result=True)
            return True
        # now compare based on public key
        if not isinstance(idurl, ID_URL):
            idurl = ID_URL(idurl)
        result = idurl.to_public_key() == self.to_public_key()
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, current=self.current, result=result)
        return result 

    def __hash__(self):
        # this trick should make `idurl in some_dictionary` check work correctly
        # if idurl1 and idurl2 are different sources of same identity they both must be matching
        pub_key = self.to_public_key()
        hsh = pub_key.__hash__()
        if _Debug:
            lg.args(_DebugLevel, current=self.current, hash=hsh)
        return hsh

    def __repr__(self):
        if _Debug:
            lg.args(_DebugLevel, current_as_string=self.current_as_string)
        return self.current_as_string

    def __str__(self):
        if _Debug:
            lg.args(_DebugLevel, current_as_string=self.current_as_string)
        return self.current_as_string

    def __bytes__(self):
        if _Debug:
            lg.args(_DebugLevel, current=self.current)
        return self.current

    def strip(self):
        if _Debug:
            lg.args(_DebugLevel, current=self.current_as_string)
        return self.current

    def to_id(self):
        if _Debug:
            lg.args(_DebugLevel, current_id=self.current_id)
        return self.current_id

    def to_text(self):
        if _Debug:
            lg.args(_DebugLevel, current=self.current_as_string)
        return self.current_as_string

    def to_bin(self):
        if _Debug:
            lg.args(_DebugLevel, current=self.current)
        return self.current

    def to_public_key(self):
        global _KnownIDURLs
        if _Debug:
            lg.args(_DebugLevel, current=self.current)
        if not self.current:
            return b''
        if self.current not in _KnownIDURLs:
            raise Exception('unknown idurl: %r' % self.current)
        pub_key = _KnownIDURLs[self.current]
        return pub_key
