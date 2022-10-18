#!/usr/bin/python
# local_fs.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (local_fs.py) is part of BitDust Software.
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
.. module:: local_fs.


"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import open

#------------------------------------------------------------------------------

import os
import platform

#------------------------------------------------------------------------------

from bitdust.lib import strng

from bitdust.logs import lg

#------------------------------------------------------------------------------

_PlatformInfo = None

#------------------------------------------------------------------------------


def WriteBinaryFile(filename, data):
    """
    A smart way to write data to binary file. Return True if success.
    This should be atomic operation - data is written to another temporary file and than renamed.
    """
    global _PlatformInfo
    if _PlatformInfo is None:
        _PlatformInfo = platform.uname()
    try:
        tmpfilename = filename + '.new'
        f = open(tmpfilename, 'wb')
        bin_data = strng.to_bin(data)
        f.write(bin_data)
        f.flush()
        # from http://docs.python.org/library/os.html on os.fsync
        os.fsync(f.fileno())
        f.close()
        # in Unix the rename will overwrite an existing file,
        # but in Windows it fails, so have to remove existing file first
        if _PlatformInfo[0] == 'Windows' and os.path.exists(filename):
            os.remove(filename)
        os.rename(tmpfilename, filename)
    except:
        lg.exc('file write failed: %r' % filename)
        try:
            # make sure file gets closed
            f.close()
        except:
            pass
        return False
    return True


def AppendBinaryFile(filename, data, mode='a'):
    """
    Same as WriteBinaryFile but do not erase previous data in the file.
    TODO: this is not atomic right now
    """
    try:
        f = open(filename, mode)
        if 'b' in mode:
            bin_data = strng.to_bin(data)
            f.write(bin_data)
        else:
            f.write(data)
        f.flush()
        os.fsync(f.fileno())
        f.close()
    except:
        lg.exc()
        try:
            # make sure file gets closed
            f.close()
        except:
            lg.exc()
        return False
    return True


def ReadBinaryFile(filename, decode_encoding=None):
    """
    A smart way to read binary file. Return empty string in case of:

    - path not exist
    - process got no read access to the file
    - some read error happens
    - file is really empty
    """
    if not filename:
        return b''
    if not os.path.isfile(filename):
        return b''
    if not os.access(filename, os.R_OK):
        return b''
    try:
        infile = open(filename, mode='rb')
        data = infile.read()
        if decode_encoding is not None:
            data = data.decode(decode_encoding)
        infile.close()
        return data
    except:
        lg.exc('file read failed: %r' % filename)
        return b''


#------------------------------------------------------------------------------


def WriteTextFile(filepath, data):
    """
    A smart way to write data into text file. Return True if success.
    This should be atomic operation - data is written to another temporary file and than renamed.
    """
    temp_path = filepath + '.tmp'
    if os.path.exists(temp_path):
        if not os.access(temp_path, os.W_OK):
            return False
    if os.path.exists(filepath):
        if not os.access(filepath, os.W_OK):
            return False
        try:
            os.remove(filepath)
        except:
            lg.exc()
            return False
    fout = open(temp_path, 'wt', encoding='utf-8')
    text_data = strng.to_text(data)
    fout.write(text_data)
    fout.flush()
    os.fsync(fout)
    fout.close()
    try:
        os.rename(temp_path, filepath)
    except:
        lg.exc('file write failed: %r' % filepath)
        return False
    return True


def ReadTextFile(filename):
    """
    Read text file and return its content.
    """
    if not filename:
        return u''
    global _PlatformInfo
    if _PlatformInfo is None:
        _PlatformInfo = platform.uname()
    if not os.path.isfile(filename):
        return u''
    if not os.access(filename, os.R_OK):
        return u''
    try:
        infile = open(filename, 'rt', encoding='utf-8')
        data = infile.read()
        infile.close()
        return strng.to_text(data)
    except:
        lg.exc('file read failed: %r' % filename)
    return u''


#------------------------------------------------------------------------------


def RoundupFile(filename, stepsize):
    """
    For some things we need to have files which are round sizes, for example
    some encryption needs files that are multiples of 8 bytes.

    This function rounds file up to the next multiple of step size.
    """
    try:
        size = os.path.getsize(filename)
    except:
        lg.exc()
        return 0
    mod = size % stepsize
    increase = 0
    if mod > 0:
        increase = stepsize - mod
        fil = open(filename, 'a')
        fil.write(u' '*increase)
        fil.flush()
        os.fsync(fil)
        fil.close()
    return increase
