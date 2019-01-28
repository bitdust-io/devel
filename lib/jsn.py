#!/usr/bin/env python
# jsn.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

import json
import six

#------------------------------------------------------------------------------

def dumps(obj, indent=None, separators=None, sort_keys=None, ensure_ascii=False, encoding='utf-8', **kw):
    """
    Calls `json.dumps()` with parameters.
    Always translates every byte string json value into text using encoding.
    """

    enc_errors = kw.pop('errors', 'strict')
    keys_to_text = kw.pop('keys_to_text', False)

    def _to_text(v):
        if isinstance(v, six.binary_type):
            v = v.decode(encoding, errors=enc_errors)
        return v

    def _keys_to_text(o, enc):
        return {(k.decode(enc, errors=enc_errors) if isinstance(k, six.binary_type) else k) : v for k, v in o.items()}

    if keys_to_text:
        obj = _keys_to_text(obj, enc=encoding)

    if six.PY2:
        return json.dumps(
            obj=obj,
            indent=indent,
            separators=separators,
            sort_keys=sort_keys,
            ensure_ascii=ensure_ascii,
            default=_to_text,
            encoding=encoding,
            **kw
        )

    else:
        return json.dumps(
            obj=obj,
            indent=indent,
            separators=separators,
            sort_keys=sort_keys,
            ensure_ascii=ensure_ascii,
            default=_to_text,
            **kw
        )

#------------------------------------------------------------------------------

def loads(s, encoding='utf-8', **kw):
    """
    Calls `json.loads()` with parameters.
    Always translates all json text values into binary strings using encoding.
    """

    def _to_bin(dct):
        for k in dct.keys():
            if isinstance(dct[k], six.text_type):
                dct[k] = dct[k].encode(encoding)
        return dct

    return json.loads(
        s=s,
        object_hook=_to_bin,
        **kw
    )


def loads_text(s, encoding='utf-8', **kw):
    """
    Calls `json.loads()` with parameters.
    Always translates all json values into unicode strings.
    """

    enc_errors = kw.pop('errors', 'strict')

    def _to_text(dct):
        for k in dct.keys():
            if isinstance(dct[k], six.binary_type):
                dct[k] = dct[k].decode(encoding, errors=enc_errors)
        return dct

    return json.loads(
        s=s,
        object_hook=_to_text,
        **kw
    )
