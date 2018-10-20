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
    """
    return strng.to_bin(
        jsn.dumps(
            dct,
            separators=(',', ':'),
            indent=0,
            sort_keys=True,
            encoding=encoding,
        ),
        encoding=encoding,
        errors='strict',
    )


def BytesToDict(inp, encoding='latin1'):
    """
    """
    return jsn.loads(
        strng.to_text(
            inp,
            encoding=encoding,
        ),
        encoding=encoding,
    )
