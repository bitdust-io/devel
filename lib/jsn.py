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

def _to_text(v):
    if not isinstance(v, six.text_type):
        v = v.decode()
    return v

#------------------------------------------------------------------------------

def dumps(o, indent=None, separators=None, sort_keys=None, **kw):
    return json.dumps(
        o,
        indent=indent,
        separators=separators,
        sort_keys=sort_keys,
        ensure_ascii=False,
        default=_to_text,
        **kw
    )

#------------------------------------------------------------------------------

def loads(s, encoding=None, **kw):
    return json.loads(
        s,
        encoding=encoding,
        **kw
    )
