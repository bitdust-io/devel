#!/usr/bin/python
# nameurl.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (nameurl.py) is part of BitDust Software.
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
.. module:: nameurl.

"""

#------------------------------------------------------------------------------

import re

#------------------------------------------------------------------------------

from lib import nameurl

#------------------------------------------------------------------------------

_FORMAT_GLOBAL_ID_USER_KEY = '{user}!{key}'
_FORMAT_GLOBAL_ID_KEY_USER = '{key}${user}'
_REGEX_GLOBAL_ID_USER_KEY = '^(?P<user>[a-z0-9-_]+)\!(?P<key>[a-z0-9-_]+)$'
_REGEX_GLOBAL_ID_KEY_USER = '^(?P<key>[a-z0-9-_]+)\$(?P<user>[a-z0-9-_]+)$'

#------------------------------------------------------------------------------

def MakeGlobalID(
    idurl=None,
    user=None,
    idhost=None,
    key=None,
    path=None,
    version=None,
):
    """
    Based on input parameters returns string like this:

        group_abc$alice@first-machine.com:animals/cat.png#F20160313043757PM

    """
    output_format = _FORMAT_GLOBAL_ID_KEY_USER
    out = ''
    if idurl:
        _, idhost, port, filename = nameurl.UrlParse(idurl)
        if port:
            idhost += ':' + str(port)
        user = filename.strip()[0:-4]
    if key:
        out = output_format.format(user=user, key=key)
    else:
        out = user
    out += '@{}'.format(idhost)
    if path:
        out += ':{}'.format(path)
        if version:
            out += '#{}'.format(version)
    return out

#------------------------------------------------------------------------------

def ParseGlobalID(inp):
    """
    Split input string by parts according to different global ID formats:

        "group_abc$alice@first-machine.com:myfiles/animals/cat.png#F20160313043757PM"

    returns such dictionary object:

        {
            "user": "alice",
            "key": "group_abc",
            "idhost": "first-machine.com",
            "customer": "alice@first-machine.com",
            "idurl": "http://first-machine.com/alice.xml",
            "path": "myfiles/animals/cat.png",
            "version": "F20160313043757PM",
        }
    """
    result = {
        "user": "",
        "key": "",
        "idhost": "",
        "customer": "",
        "idurl": "",
        "path": "",
        "version": "",
    }
    if not inp or not str(inp):
        return result
    user, _, path = inp.strip().rpartition(':')
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
                result['key'] = user_key.group('key')
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
        result['idurl'] = 'http://{}/{}.xml'.format(result['idhost'], result['user'])
        result['customer'] = '{}@{}'.format(result['user'], result['idhost'].replace(':', '_'))
    if path:
        if path.count('#'):
            path, _, version = path.rpartition('#')
            result['version'] = version
        result['path'] = path
    return result

#------------------------------------------------------------------------------

def NormalizeGlobalID(inp):
    """
    """
    from userid import my_id
    if isinstance(inp, dict):
        g = inp
    else:
        g = ParseGlobalID(inp)
    if not g['idurl']:
        g['idurl'] = my_id.getLocalID()
    if not g['customer']:
        g['customer'] = UrlToGlobalID(g['idurl'])
    if not g['user']:
        g['user'] = UrlToGlobalID(g['idurl'])
    if not g['key']:
        g['key'] = 'master'
    if not g['idhost']:
        g['idhost'] = my_id.getLocalIdentity().getContactHost()
    return g

#------------------------------------------------------------------------------

def UrlToGlobalID(url):
    """
    """
    _, host, port, filename = nameurl.UrlParse(url)
    if filename.count('.'):
        username = filename.split('.')[0]
    if port:
        host = '%s_%s' % (host, port)
    return '%s@%s' % (username, host)


def GlobalUserToIDURL(inp):
    """
    """
    user, _, idhost = inp.strip().rpartition('@')
    if not user:
        return None
    if not idhost:
        return None
    if idhost.count('_'):
        _pos = idhost.rfind('_')
        port = idhost[_pos + 1:]
        try:
            port = int(port)
        except:
            port = -1
        if port >= 0:
            idhost = "%s:%d" % (idhost[:_pos], port)
    return 'http://{}/{}.xml'.format(idhost, user)

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
    return True
