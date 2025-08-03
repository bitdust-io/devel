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
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import strng

#------------------------------------------------------------------------------

_ReadsTracking = {}
_WritesTracking = {}

#------------------------------------------------------------------------------


def data_read(file_path, offset, max_size, to_text=True):
    global _ReadsTracking
    if not os.path.isfile(file_path):
        raise Exception('file does not exist')
    if file_path not in _ReadsTracking:
        _ReadsTracking[file_path] = {'bytes': 0, 'count': 0, 'path': file_path}
    f = open(file_path, 'rb')
    f.seek(offset)
    bin_data = f.read(max_size)
    f.close()
    _ReadsTracking[file_path]['bytes'] += len(bin_data)
    _ReadsTracking[file_path]['count'] += 1
    _ReadsTracking[file_path]['offset_last'] = offset
    if _Debug:
        lg.args(_DebugLevel, sz=len(bin_data), file_path=file_path, offset=offset, max_size=max_size)
    if not to_text:
        return bin_data
    return strng.to_text(bin_data, encoding='latin1')


#------------------------------------------------------------------------------


def data_write(file_path, data, from_text=True):
    global _WritesTracking
    if file_path not in _WritesTracking:
        _WritesTracking[file_path] = {'bytes': 0, 'count': 0, 'path': file_path}
    if from_text:
        data = strng.to_bin(data, encoding='latin1')
    f = open(file_path, 'ab')
    f.write(data)
    f.flush()
    f.close()
    _WritesTracking[file_path]['bytes'] += len(data)
    _WritesTracking[file_path]['count'] += 1
    if _Debug:
        lg.args(_DebugLevel, sz=len(data), file_path=file_path)
    return True


#------------------------------------------------------------------------------


def get_current_reads_stats(file_path):
    global _ReadsTracking
    stats = _ReadsTracking.get(file_path)
    if _Debug:
        lg.args(_DebugLevel, path=file_path, stats=stats)
    return stats


def get_current_writes_stats(file_path):
    global _WritesTracking
    stats = _WritesTracking.get(file_path)
    if _Debug:
        lg.args(_DebugLevel, path=file_path, stats=stats)
    return stats
