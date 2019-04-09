#!/usr/bin/python
# diskspace.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (diskspace.py) is part of BitDust Software.
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
#

"""
.. module:: diskspace.

This is set of methods to operate with amount of space units.
Examples::
    123 bytes
    45 KB
    67 mb
    8.9 Gigabytes

You can translate values from Kb to Mb or create a good looking string from bytes number.
"""

#------------------------------------------------------------------------------

_Suffixes = {
    '': 1.0,
    'bytes': 1.0,
    'b': 1.0,
    'B': 1.0,
    'K': 1024.0,
    'k': 1024.0,
    'KB': 1024.0,
    'Kb': 1024.0,
    'kb': 1024.0,
    'Kilobytes': 1024.0,
    'kilobytes': 1024.0,
    'm': 1024.0 * 1024.0,
    'M': 1024.0 * 1024.0,
    'MB': 1024.0 * 1024.0,
    'Mb': 1024.0 * 1024.0,
    'mb': 1024.0 * 1024.0,
    'Megabytes': 1024.0 * 1024.0,
    'megabytes': 1024.0 * 1024.0,
    'G': 1024.0 * 1024.0 * 1024.0,
    'GB': 1024.0 * 1024.0 * 1024.0,
    'Gb': 1024.0 * 1024.0 * 1024.0,
    'g': 1024.0 * 1024.0 * 1024.0,
    'gb': 1024.0 * 1024.0 * 1024.0,
    'Gigabytes': 1024.0 * 1024.0 * 1024.0,
    'gigabytes': 1024.0 * 1024.0 * 1024.0,
}

_SuffixLabels = ['bytes', 'Kb', 'Mb', 'Gb']

_MultiDict = {
    'Kb': 1024.0,
    'Mb': 1024.0 * 1024.0,
    'Gb': 1024.0 * 1024.0 * 1024.0,
}

#------------------------------------------------------------------------------


class DiskSpace:
    """
    You can create an object of this class and use it as variable to store
    amount of space.

    But in most cases this class is not used, see below global methods
    in this module.
    """

    def __init__(self, v=None, s='0Mb'):
        if v is None:
            self.v = s
            if self.getSZ() not in ['Kb', 'Mb', 'Gb']:
                self.addSZ('Mb')
        else:
            self.v = str(self.getValueBest(v))
        self.b = self.getValue() * _MultiDict[self.getSZ()]

    def __repr__(self):
        return self.v

    def addSZ(self, sz):
        self.v += sz

    def setSZ(self, sz):
        self.v[-2] = sz[0]
        self.v[-1] = sz[1]

    def getSZ(self):
        return self.v[-2:]

    def getValue(self):
        try:
            return float(self.v[:-2])
        except:
            return 0.0

    def getValueBytes(self):
        return self.b

    def getValueKb(self):
        sz = self.getSZ()
        if sz == 'Gb':
            return round(self.getValue() * 1024.0 * 1024.0, 2)
        elif sz == 'Mb':
            return round(self.getValue() * 1024.0, 2)
        return self.getValue()

    def getValueMb(self):
        sz = self.getSZ().lower()
        if sz == 'Kb':
            return round(self.getValue() / 1024.0, 2)
        elif sz == 'Gb':
            return round(self.getValue() * 1024.0, 2)
        return self.getValue()

    def getValueGb(self):
        sz = self.getSZ()
        if sz == 'Kb':
            return round(self.getValue() / (1024.0 * 1024.0), 2)
        elif sz == 'Mb':
            return round(self.getValue() / 1024.0, 2)
        return self.getValue()

    def getValueBest(self, value=None):
        if value is not None:
            v = value
        else:
            v = self.getValueBytes()
        if v > _MultiDict['Gb']:
            res = round(v / _MultiDict['Gb'], 2)
            sz = 'Gb'
        elif v > _MultiDict['Mb']:
            res = round(v / _MultiDict['Mb'], 2)
            sz = 'Mb'
        else:
            res = round(v / _MultiDict['Kb'], 2)
            sz = 'Kb'
        return str(res) + sz


def SuffixIsCorrect(suffix):
    """
    Check input string to be a valid unit label.

    See global variable ``_Suffixes``.
    """
    global _Suffixes
    return suffix in list(_Suffixes.keys())


def SuffixLabels():
    """
    Return the correct suffix labels.
    """
    global _SuffixLabels
    return _SuffixLabels


def SameSuffix(suf1, suf2):
    """
    Compare 2 unit labels.

    Return True if both are same unit: from diskspace import *
    SameSuffix('b','bytes') True
    """
    global _Suffixes
    if not SuffixIsCorrect(suf1):
        return False
    if not SuffixIsCorrect(suf2):
        return False
    return _Suffixes[suf1] == _Suffixes[suf2]


def MakeString(value, suf):
    """
    Method to join value and unit measure.
    """
    if not SuffixIsCorrect(suf):
        return str(value)
    if round(float(value)) == float(value):
        return str(int(float(value))) + ' ' + suf
    return str(value) + ' ' + suf


def SplitString(s):
    """
    Return tuple (<number>, <suffix>) or (None, None).

    from diskspace import * SplitString("342.67Mb") (342.67, 'Mb')
    """
    num = s.rstrip('bytesBYTESgmkGMK ')
    suf = s.lstrip('0123456789., ').strip()
    try:
        num = float(num)
    except:
        return (None, None)

    if round(num) == num:
        num = int(num)

    if not SuffixIsCorrect(suf):
        return (None, None)

    return (num, suf)


def MakeStringFromBytes(value):
    """
    Make a correct string value with best units measure from given number of
    bytes.

    from diskspace import *     MakeStringFromBytes(123456)     '120.56
    KB'     MakeStringFromBytes(123.456789)     '123 bytes' I think this
    is most used method here.
    """
    try:
        v = float(value)
    except:
        return value
    if v > _Suffixes['GB']:
        res = round(v / _Suffixes['GB'], 2)
        sz = 'GB'
    elif v > _Suffixes['MB']:
        res = round(v / _Suffixes['MB'], 2)
        sz = 'MB'
    elif v > _Suffixes['KB']:
        res = round(v / _Suffixes['KB'], 2)
        sz = 'KB'
    else:
        res = int(v)
        sz = 'bytes'
    return MakeString(res, sz)


def GetBytesFromString(s, default=None):
    """
    Convert a string to a value in bytes, this is reverse method for
    MakeStringFromBytes.

    from diskspace import * GetBytesFromString("123.456 Mb") 129452998
    """
    num, suf = SplitString(s)
    if num is None:
        return default
    return int(num * _Suffixes[suf])


def MakeStringWithSuffix(s, suffix):
    """
    You can move strings from one unit measure to another.

    Convert input string to a string with given suffix.     from
    diskspace import *     MakeStringWithSuffix("12.345 Mb", "Kb")
    '12641.28 Kb'
    """
    b = GetBytesFromString(s)
    if b is None:
        return s
    if not SuffixIsCorrect(suffix):
        return s
    res = round(b / _Suffixes[suffix], 2)
    if _Suffixes[suffix] == 1.0:
        res = int(res)
    return MakeString(res, suffix)


def GetMegaBytesFromString(s):
    """
    This is just a wrapper for ``GetBytesFromString``, but return value in
    Megabytes.
    """
    b = GetBytesFromString(s)
    if b is None:
        return None
    return round(b / (1024 * 1024), 2)


def MakeStringFromString(s):
    """
    This method can be used during loading or checking user input.

    Call ``SplitString`` and than ``MakeString`` to "recreate" input
    string.
    """
    value, suf = SplitString(s)
    if value is None:
        return s
    return MakeString(value, suf)
