#!/usr/bin/env python
# strng.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (strng.py) is part of BitDust Software.
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
.. module:: strng.

"""

#------------------------------------------------------------------------------

import sys

#------------------------------------------------------------------------------

if sys.version_info[0] == 3:
    string_types = str,
    text_type = str
    binary_type = bytes
else:
    string_types = basestring,
    text_type = unicode
    binary_type = str

#------------------------------------------------------------------------------

def is_string(s):
    """
    Return `True` if `s` is text or binary type (not integer, class, list, etc...)
    """
    return isinstance(s, string_types)


def is_text(s):
    """
    Return `True` if `s` is a text value:
    + `unicode()` in Python2
    + `str()` in Python3
    """
    return isinstance(s, text_type)


def is_bin(s):
    """
    Return `True` if `s` is a binary value:
    + `str()` in Python2
    + `bytes()` in Python3
    """
    return isinstance(s, binary_type)

#------------------------------------------------------------------------------

def to_text(s, encoding='utf-8', errors='strict'):
    """
    if ``s`` is binary type - decode it to unicode - "text" type in Python3 terms, otherwise return ``s``.
    """
    if is_text(s):
        return s
    return s.decode(encoding=encoding, errors=errors)


def to_bin(s, encoding='utf-8', errors='strict'):
    """
    If ``s`` is unicode ("text" type in Python3 terms) - encode it to utf-8, otherwise return ``s``.
    """
    if is_bin(s):
        return s
    return s.encode(encoding=encoding, errors=errors)


def to_string(v, encoding='utf-8', errors='strict'):
    """
    Something like `str(obj)`, but to "text" type.
    """
    if not is_string(v):
        return text_type(v)
    if is_text(v):
        return v
    return to_text(v, encoding=encoding, errors=errors)
