#!/usr/bin/env python
# serialization.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

def DictToBytes(dct, encoding='latin1', errors='strict', keys_to_text=False, values_to_text=False, pack_types=False):
    """
    Calls `json.dupms()` method for input dict to build bytes output.
    Uses encoding to decode every byte string to text and ensure ascii output.
    If `keys_to_text` is True it will also convert dict keys from binary strings to text strings.
    If `values_to_text` is True it will also convert dict values from binary strings to text strings.
    Another smart feature is `pack_types` - it will remember types of keys and values in the input dict.
    Respective feature `unpack_types` of `BytesToDict()` method can be used to "extract" exactly same dict from bytes. 
    Can be used to serialize dictionaries of mixed types - with binary and text values.   
    """
    return strng.to_bin(
        jsn.dumps(
            jsn.pack_dict(dct, encoding=encoding, errors=errors) if pack_types else dct,
            separators=(',', ':'),
            indent=None,
            sort_keys=True,
            ensure_ascii=True,
            encoding=encoding,
            keys_to_text=keys_to_text,
            values_to_text=values_to_text,
        ),
        encoding=encoding,
        errors=errors,
    )


def BytesToDict(inp, encoding='latin1', errors='strict', keys_to_text=False, values_to_text=False, unpack_types=False):
    """
    A smart way to extract input bytes into python dictionary object.
    All input bytes will be decoded into text and then loaded via `json.loads()` method.
    Finally every text key and value in result dict will be encoded back to bytes if `values_to_text` is False.
    Smart feature `unpack_types` can be used to "extract" real types of keys and values from input bytes.
    Can be used to extract dictionaries of mixed types - binary and text values.   
    """
    _t = strng.to_text(inp, encoding=encoding)
    if values_to_text:
        return jsn.loads_text(_t, encoding=encoding)
    if unpack_types:
        return jsn.unpack_dict(jsn.loads(_t, encoding=encoding), encoding=encoding, errors=errors)
    if keys_to_text:
        return jsn.dict_keys_to_text(jsn.loads(_t, encoding=encoding))
    return jsn.loads(_t, encoding=encoding)
