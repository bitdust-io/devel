#!/usr/bin/env python
# jsn.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (jsn.py) is part of BitDust Software.
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
"""
.. module:: jsn.

"""

#------------------------------------------------------------------------------

import sys
import json

#------------------------------------------------------------------------------

_Debug = False

#------------------------------------------------------------------------------

from lib import strng

#------------------------------------------------------------------------------


def dict_keys_to_text(dct, encoding='utf-8', errors='strict'):
    """
    Returns dict where all keys are converted to text strings.
    Only works for keys in a "root" level of the dict.
    """
    return {(k.decode(encoding, errors=errors) if strng.is_bin(k) else k): v for k, v in dct.items()}


def dict_keys_to_bin(dct, encoding='utf-8', errors='strict'):
    """
    Returns dict where all keys are converted to binary strings.
    Only works for keys in a "root" level of the dict.
    """
    return {(k.encode(encoding, errors=errors) if strng.is_text(k) else k): v for k, v in dct.items()}


def dict_values_to_text(dct, encoding='utf-8', errors='strict'):
    """
    Returns dict where all values are converted to text strings.
    Can go recursively, but not super smart.
    If value is a list of dicts - will not be converted.
    """
    # TODO: make it fully recursive... for example if list of lists is passed
    _d = {}
    for k, v in dct.items():
        _v = v
        if strng.is_bin(_v):
            _v = _v.decode(encoding, errors=errors)
        elif isinstance(_v, dict):
            _v = dict_values_to_text(_v, encoding=encoding, errors=errors)
        elif isinstance(_v, list):
            _v = [i.decode(encoding, errors=errors) if strng.is_bin(i) else i for i in _v]
        elif isinstance(_v, tuple):
            _v = tuple([i.decode(encoding, errors=errors) if strng.is_bin(i) else i for i in _v])
        _d[k] = _v
    return _d


def dict_items_to_text(dct, encoding='utf-8', errors='strict'):
    """
    Returns dict where all keys and values are converted to text strings.
    Only works for simple dicts - one level structure.
    """
    # TODO: make it fully recursive... for example if list of lists is passed
    if strng.is_text(dct):
        return dct
    elif strng.is_bin(dct):
        return dct.decode(encoding, errors=errors)
    elif isinstance(dct, list):
        return [dict_items_to_text(i) for i in dct]
    elif isinstance(dct, tuple):
        return tuple([dict_items_to_text(i) for i in dct])
    elif isinstance(dct, dict):
        return {strng.to_text(x): dict_items_to_text(y) for x, y in dct.items()}
    if not isinstance(dct, dict):
        return dct
    _d = {}
    for k in dct.keys():
        _v = dct[k]
        if strng.is_text(_v):
            pass
        elif strng.is_bin(_v):
            _v = _v.decode(encoding, errors=errors)
        elif isinstance(_v, list):
            _v = [dict_items_to_text(i) for i in _v]
        elif isinstance(_v, tuple):
            _v = tuple([dict_items_to_text(i) for i in _v])
        elif isinstance(_v, dict):
            _v = {strng.to_text(x): dict_items_to_text(y) for x, y in _v.items()}
        _k = k
        if strng.is_bin(_k):
            _k = _k.decode(encoding, errors=errors)
        _d[_k] = _v
    return _d


#------------------------------------------------------------------------------


def pack_dict(dct, encoding='utf-8', errors='strict'):
    """
    Creates another dict from input dict where types of keys and values are also present.
    Keys can only be bin/text strings, integers, floats or None.
    Values can only be bin/text strings, integers, floats, None, lists or tuples.
    Result dict will always contain only text (unicode) keys and values or simple types like integer, float or None.
    """
    if not dct:
        return {}
    _d = {}
    for k, v in dct.items():
        _k = k
        _ktyp = 's'
        if strng.is_bin(_k):
            _k = _k.decode(encoding, errors=errors)
            _ktyp = 'b'
        elif isinstance(_k, int):
            _ktyp = 'i'
        elif isinstance(_k, float):
            _ktyp = 'f'
        elif _k is None:
            _ktyp = 'n'
        _v = v
        _vtyp = 's'
        if strng.is_bin(_v):
            _v = _v.decode(encoding, errors=errors)
            _vtyp = 'b'
        elif isinstance(_v, int):
            _vtyp = 'i'
        elif isinstance(_v, float):
            _vtyp = 'f'
        elif isinstance(_v, dict):
            _v = pack_dict(_v, encoding=encoding, errors=errors)
            _vtyp = 'd'
        elif isinstance(_v, list):
            _v = [pack_dict({'i': i}, encoding=encoding, errors=errors) for i in _v]
            _vtyp = 'l'
        elif isinstance(_v, tuple):
            _v = [pack_dict({'i': i}, encoding=encoding, errors=errors) for i in _v]
            _vtyp = 't'
        elif _v is None:
            _vtyp = 'n'
        _d[_k] = (
            _ktyp,
            _vtyp,
            _v,
        )
    return _d


def unpack_dict(dct, encoding='utf-8', errors='strict'):
    """
    Reverse operation of `pack_dict()` method - returns original dict with all keys and values of correct types.
    """
    if not dct:
        return {}
    _d = {}
    for k, v in dct.items():
        _k = k
        if len(v) != 3:
            raise ValueError('unpack failed, invalid value: %r' % v)
        if v[0] == 'b':
            _k = _k.encode(encoding, errors=errors)
        _v = v[2]
        if v[1] == 'b':
            _v = _v.encode(encoding, errors=errors)
        elif v[1] == 'd':
            _v = unpack_dict(_v, encoding=encoding, errors=errors)
        elif v[1] == 'l':
            _v = [unpack_dict(i, encoding=encoding, errors=errors)['i'] for i in _v]
        elif v[1] == 't':
            _v = tuple([unpack_dict(i, encoding=encoding, errors=errors)['i'] for i in _v])
        _d[_k] = _v
    return _d


#------------------------------------------------------------------------------


def dumps(obj, indent=None, separators=None, sort_keys=None, ensure_ascii=False, encoding='utf-8', keys_to_text=False, values_to_text=False, empty_result='{}', **kw):
    """
    Calls `json.dumps()` with parameters.
    Always translates every byte string json value into text using encoding.
    """
    if obj is None or obj == '' or obj == b'':
        return empty_result

    enc_errors = kw.pop('errors', 'strict')

    def _to_text(v):
        if strng.is_bin(v):
            v = v.decode(encoding, errors=enc_errors)
        if not strng.is_text(v):
            v = strng.to_text(v)
        return v

    if keys_to_text:
        obj = dict_keys_to_text(obj, encoding=encoding, errors=enc_errors)

    if values_to_text:
        obj = dict_values_to_text(obj, encoding=encoding, errors=enc_errors)

    try:
        if sys.version_info[0] < 3:
            return json.dumps(obj=obj, indent=indent, separators=separators, sort_keys=sort_keys, ensure_ascii=ensure_ascii, default=_to_text, encoding=encoding, **kw)
        else:
            return json.dumps(obj=obj, indent=indent, separators=separators, sort_keys=sort_keys, ensure_ascii=ensure_ascii, default=_to_text, **kw)
    except Exception as exc:
        if _Debug:
            import os
            import tempfile
            fd, _ = tempfile.mkstemp(suffix='err', prefix='jsn_dumps_', text=True)
            try:
                os.write(fd, repr(obj))
            except:
                try:
                    os.write(fd, strng.to_bin(repr(type(obj))))
                except:
                    os.write(fd, b'failed to serialize object')
            os.close(fd)
        raise exc


#------------------------------------------------------------------------------


def loads_bin(s, encoding='utf-8', keys_to_bin=False, **kw):
    """
    Calls `json.loads()` with parameters.
    Always translates all json values into binary strings using encoding.
    Also do the same for keys when `keys_to_bin=True`.
    """
    if not s:
        return None

    def _to_bin(dct):
        for k in dct.keys():
            if strng.is_text(dct[k]):
                dct[k] = dct[k].encode(encoding)
        if keys_to_bin:
            return {(k.encode(encoding) if strng.is_text(k) else k): v for k, v in dct.items()}
        return dct

    try:
        return json.loads(s=s, object_hook=_to_bin, **kw)
    except Exception as exc:
        if _Debug:
            try:
                import os
                import tempfile
                fd, _ = tempfile.mkstemp(suffix='err', prefix='jsn_loads_', text=True)
                os.write(fd, s)
                os.close(fd)
            except:
                pass
        raise exc


#------------------------------------------------------------------------------


def loads(s, encoding='utf-8', **kw):
    """
    Calls `json.loads()` with parameters.
    Always translates all json keys and values into unicode strings.
    """
    if not s:
        return None

    enc_errors = kw.pop('errors', 'strict')

    try:
        return json.loads(s=s, object_hook=lambda itm: dict_items_to_text(itm, encoding=encoding, errors=enc_errors), **kw)
    except Exception as exc:
        if _Debug:
            import os
            import tempfile
            fd, _ = tempfile.mkstemp(suffix='err', prefix='jsn_loads_', text=True)
            os.write(fd, s)
            os.close(fd)
        raise exc


#------------------------------------------------------------------------------


def loads_text(s, encoding='utf-8', **kw):
    """
    Calls `json.loads()` with parameters.
    Always translates all json keys and values into unicode strings.
    """
    if not s:
        return None

    enc_errors = kw.pop('errors', 'strict')

    try:
        return json.loads(s=s, object_hook=lambda itm: dict_items_to_text(itm, encoding=encoding, errors=enc_errors), **kw)
    except Exception as exc:
        if _Debug:
            import os
            import tempfile
            fd, _ = tempfile.mkstemp(suffix='err', prefix='jsn_loads_', text=True)
            os.write(fd, s)
            os.close(fd)
        raise exc
