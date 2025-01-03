#!/usr/bin/python
# chunk.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (chunk.py) is part of BitDust Software.
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

_Debug = False
_DebugLevel = 8

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from bitdust.lib import strng

#------------------------------------------------------------------------------


def data_read(file_path, offset, max_size, to_text=True):
    if not os.path.isfile(file_path):
        raise Exception('file does not exist')
    f = open(file_path, 'rb')
    f.seek(offset=offset)
    bin_data = f.read(size=max_size)
    f.close()
    if not to_text:
        return bin_data
    return strng.to_text(bin_data)


def data_write(file_path):
    return
