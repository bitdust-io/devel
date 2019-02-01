#!/usr/bin/env python
# serialization.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (serialization.py) is part of BitDust Software.
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

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

from lib import jsn
from lib import strng
    
#------------------------------------------------------------------------------

def DictToBytes(dct, encoding='latin1'):
    """
    Calls `json.dupms()` method for input dict to build bytes output.
    Uses encoding to decode every byte string to text and ensure ascii output.
    """
    return strng.to_bin(
        jsn.dumps(
            dct,
            separators=(',', ':'),
            indent=None,
            sort_keys=True,
            ensure_ascii=True,
            encoding=encoding,
        ),
        encoding=encoding,
        errors='strict',
    )


def BytesToDict(inp, encoding='latin1', as_text_values=False):
    """
    A smart way to extract input bytes into python dictionary object.
    All input bytes will be decoded into text and then loaded via `json.loads()` method.
    Finally every text value in result dict will be encoded back to bytes if `as_text_values` is False.
    """
    _t = strng.to_text(inp, encoding=encoding)
    if as_text_values:
        return jsn.loads_text(_t, encoding=encoding)
    return jsn.loads(_t, encoding=encoding)
