#!/usr/bin/python
# global_id.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (global_id.py) is part of BitDust Software.
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

"""
.. module:: global_id.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import re

#------------------------------------------------------------------------------

from lib import strng

#------------------------------------------------------------------------------

_FORMAT_GLOBAL_ID = '{key_alias}${username}@{host}'
_FORMAT_GLOBAL_ID_USER = '{username}@{host}'
_FORMAT_GLOBAL_ID_USER_KEY = '{user}!{key_alias}'
_FORMAT_GLOBAL_ID_KEY_USER = '{key_alias}${user}'
_FORMAT_GLOBAL_ID_QUEUE_ID = '{queue_alias}&{owner_id}&{supplier_id}'

_REGEX_GLOBAL_ID_USER_KEY = '^(?P<user>[a-z0-9-_]+)\!(?P<key_alias>[a-z0-9-_]+)$'
_REGEX_GLOBAL_ID_KEY_USER = '^(?P<key_alias>[a-z0-9-_]+)\$(?P<user>[a-z0-9-_]+)$'
_REGEX_GLOBAL_ID_QUEUE_ID = '^(?P<queue_alias>[a-z0-9-_]+)\&(?P<owner_id>[a-z0-9-_\@\.]+)\&(?P<supplier_id>[a-z0-9-_\@\.]+)$'

#------------------------------------------------------------------------------

def idurl2glob(idurl):
    """
    Alias.
    """
    return UrlToGlobalID(idurl)


def glob2idurl(glob_id):
    """
    Alias.
    """
    return GlobalUserToIDURL(glob_id)

#------------------------------------------------------------------------------

def MakeGlobalID(
    idurl=None,
    user=None,
    idhost=None,
    customer=None,
    key_alias=None,
    path=None,
    version=None,
    key_id=None,
):
    """
    Based on input parameters returns string like this:

        group_abc$alice@first-machine.com:animals/cat.png#F20160313043757PM

    """
    output_format = _FORMAT_GLOBAL_ID_KEY_USER
    out = ''
    if key_id:
        out = key_id
    else:
        if customer:
            idurl = GlobalUserToIDURL(customer)
            if customer.count('$'):
                key_alias, _, _ = customer.rpartition('$')
            if customer.count('!'):
                user_and_key, _, _ = customer.rpartition('@')
                _, _, key_alias = user_and_key.rpartition('!')
        if idurl:
            from lib import nameurl
            _, idhost, port, filename = nameurl.UrlParse(idurl)
            if port:
                idhost += '_' + str(port)
            user = filename.strip()[0:-4]
        if key_alias:
            out = output_format.format(user=user, key_alias=key_alias)
        else:
            out = user
        out += '@{}'.format(idhost)
    if path:
        out += ':{}'.format(path)
        if version:
            out += '#{}'.format(version)
    return out


def ParseIDURL(idurl):
    """
    """
    return ParseGlobalID(UrlToGlobalID(idurl, include_key=False))


def ParseGlobalID(inp, detect_version=False):
    """
    Split input string by parts according to different global ID formats:

    For such input (global resource path):

        "group_abc$alice@first-machine.com:myfiles/animals/cat.png#F20160313043757PM"

    returns such dictionary object:

        {
            "user": "alice",
            "key_alias": "group_abc",
            "key_id": "group_abc$alice@first-machine.com",
            "idhost": "first-machine.com",
            "customer": "alice@first-machine.com",
            "idurl": b"http://first-machine.com/alice.xml",
            "path": "myfiles/animals/cat.png",
            "version": "F20160313043757PM",
        }

    For such input (global path ID) with `detect_version=True`:

        "group_abc$alice@first-machine.com:1/2/3/F20160313043757PM/4-5-Parity"

    returns such dictionary object:

        {
            "user": "alice",
            "key_alias": "group_abc",
            "key_id": "group_abc$alice@first-machine.com",
            "idhost": "first-machine.com",
            "customer": "alice@first-machine.com",
            "idurl": b"http://first-machine.com/alice.xml",
            "path": "1/2/3/F20160313043757PM/4-5-Parity",
            "version": "F20160313043757PM",
        }
    """
    result = {
        "user": "",
        "key_alias": "",
        "key_id": "",
        "idhost": "",
        "customer": "",
        "idurl": b'',
        "path": "",
        "version": "",
    }
    if not inp:
        return result
    inp = strng.to_text(inp)
    if inp.count(':'):
        user, _, path = inp.strip().rpartition(':')
    else:
        if inp.count('@'):
            user = inp
            path = ''
        else:
            user = ''
            path = inp
    if user:
        user_and_key, _, idhost = user.strip().rpartition('@')
        if not user_and_key or not idhost:
            return result
        try:
            user_key = re.match(_REGEX_GLOBAL_ID_USER_KEY, user_and_key)
            if not user_key:
                user_key = re.match(_REGEX_GLOBAL_ID_KEY_USER, user_and_key)
            if user_key:
                result['user'] = user_key.group('user')
                result['key_alias'] = user_key.group('key_alias')
            else:
                result['user'] = user_and_key
        except:
            return result
        result['idhost'] = idhost
        if result['idhost'].count('_'):
            _pos = result['idhost'].rfind('_')
            port = result['idhost'][_pos + 1:]
            try:
                port = int(port)
            except:
                port = -1
            if port >= 0:
                result['idhost'] = "%s:%d" % (result['idhost'][:_pos], port)
        if result['user'] and result['idhost']:
            result['idurl'] = strng.to_bin('http://{}/{}.xml'.format(result['idhost'], result['user']))
            result['customer'] = '{}@{}'.format(result['user'], result['idhost'].replace(':', '_'))
    if path:
        if path.count('#'):
            path, _, version = path.rpartition('#')
            result['version'] = version
        result['path'] = path
        if detect_version:
            try:
                from lib import packetid
                backupID, _, fileName = path.rpartition('/')
                if packetid.IsPacketNameCorrect(fileName):
                    _, _, versionName = backupID.rpartition('/')
                    result['version'] = versionName
            except:
                pass
    if not result['key_alias']:
        result['key_alias'] = 'master'
    result['key_id'] = _FORMAT_GLOBAL_ID_KEY_USER.format(
        key_alias=result['key_alias'],
        user=result['customer'],
    )
    return result


def NormalizeGlobalID(inp, detect_version=False):
    """
    Input `inp` is a string or glob_path_id dict.
    This will fill out missed/empty fields from existing data.
    Such an order:
        1. if no idurl : use my local identity,
        2. if no customer : use idurl
        3. if no user : use customer
        4. if no key alias : use "master"
        5. if no idhost : use idurl
    """
    from userid import my_id
    if isinstance(inp, dict):
        g = inp
    else:
        g = ParseGlobalID(inp, detect_version=detect_version)
    if not g['idurl']:
        g['idurl'] = my_id.getLocalID()
    if not g['customer']:
        g['customer'] = UrlToGlobalID(g['idurl'])
    if not g['user']:
        g['user'] = g['customer'].split('@')[0]
    if not g['key_alias']:
        g['key_alias'] = 'master'
    if not g['idhost']:
        from lib import nameurl
        g['idhost'] = nameurl.GetHost(g['idurl'])
    return g


def CanonicalID(inp, include_key=True):
    """
    """
    parts = NormalizeGlobalID(ParseGlobalID(inp))
    if include_key:
        parts['key_alias'] = parts.get('key_alias') or 'master'
    else:
        parts['key_alias'] = ''
    return MakeGlobalID(**parts)

#------------------------------------------------------------------------------

def UrlToGlobalID(url, include_key=False):
    """
    """
    if not url:
        return url
    from lib import nameurl
    _, host, port, filename = nameurl.UrlParse(url)
    if filename.count('.'):
        username = filename.split('.')[0]
    else:
        username = filename
    if port:
        host = '%s_%s' % (host, port)
    if include_key:
        username = 'master$%s' % username
    return '%s@%s' % (username, host)


def GlobalUserToIDURL(inp):
    """
    """
    user, _, idhost = inp.strip().rpartition('@')
    if not user:
        return None
    if not idhost:
        return None
    _, _, user = user.strip().rpartition('$')
    if idhost.count('_'):
        _pos = idhost.rfind('_')
        port = idhost[_pos + 1:]
        try:
            port = int(port)
        except:
            port = -1
        if port >= 0:
            idhost = "%s:%d" % (idhost[:_pos], port)
    return strng.to_bin('http://{}/{}.xml'.format(idhost, user))

#------------------------------------------------------------------------------

def IsValidGlobalUser(inp):
    """
    """
    if not inp:
        return False
    if inp.count('@') != 1:
        return False
    user, _, idhost = inp.strip().rpartition('@')
    if not user:
        return False
    if not idhost:
        return False
    # TODO: validate user and idhost
    return True


def IsFullGlobalID(inp):
    """
    """
    if not inp:
        return False
    user, _, remote_path = inp.strip().rpartition(':')
    if not IsValidGlobalUser(user):
        return False
    if not remote_path:
        return False
    return True

#------------------------------------------------------------------------------

def MakeGlobalQueueID(queue_alias, owner_id=None, supplier_id=None):
    """
    """
    global _FORMAT_GLOBAL_ID_QUEUE_ID
    return _FORMAT_GLOBAL_ID_QUEUE_ID.format(
        queue_alias=strng.to_text(queue_alias),
        owner_id=strng.to_text(owner_id),
        supplier_id=strng.to_text(supplier_id),
    )

def ParseGlobalQueueID(inp):
    global _REGEX_GLOBAL_ID_QUEUE_ID
    ret = {
        'queue_alias': '',
        'owner_id': '',
        'supplier_id': '',
    }
    result = re.match(_REGEX_GLOBAL_ID_QUEUE_ID, inp)
    if not result:
        return ret
    ret['queue_alias'] = strng.to_text(result.group('queue_alias'))
    ret['owner_id'] = strng.to_text(result.group('owner_id'))
    ret['supplier_id'] = strng.to_text(result.group('supplier_id'))
    return ret

#------------------------------------------------------------------------------
