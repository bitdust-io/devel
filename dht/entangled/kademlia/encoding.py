#!/usr/bin/env python
# encoding.py
#
# Copyright (C) 2007-2008 Francois Aucamp, Meraka Institute, CSIR
# See AUTHORS for all authors and contact information. 
# 
# License: GNU Lesser General Public License, version 3 or later; see COPYING
#          included in this archive for details.
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net


from __future__ import absolute_import
from __future__ import unicode_literals
import six
import codecs
import sys


if sys.version_info[0] == 3:
    text_type = str
    binary_type = bytes
else:
    text_type = unicode  # @UndefinedVariable
    binary_type = str


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


def is_string(s):
    """
    Return `True` if `s` is text or binary type (not integer, class, list, etc...)
    """
    return is_text(s) or is_bin(s)


def to_text(s, encoding='utf-8', errors='strict'):
    """
    If ``s`` is binary type - decode it to unicode - "text" type in Python3 terms.
    If ``s`` is not binary and not text calls `str(s)` to build text representation.
    """
    if s is None:
        return s
    if not is_string(s):
        s = text_type(s)
    if is_text(s):
        return s
    return s.decode(encoding=encoding, errors=errors)


def to_bin(s, encoding='utf-8', errors='strict'):
    """
    If ``s`` is unicode ("text" type in Python3 terms) - encode it to utf-8, otherwise return ``s``.
    If ``s`` is not binary and not text calls `str(s)` to build text representation,
    then encode to binary and return.
    """
    if s is None:
        return s
    if not is_string(s):
        s = text_type(s)
    if is_bin(s):
        return s
    return s.encode(encoding=encoding, errors=errors)


def encode_hex(value, as_string=True, encoding='utf-8'):
    hex_value = codecs.encode(value, 'hex')
    if as_string:
        return hex_value.decode('utf-8')
    return hex_value


def decode_hex(value, as_string=True, encoding='utf-8'):
    orig_value = codecs.decode(value, 'hex')
    if as_string:
        return orig_value.decode('utf-8')
    return orig_value


class Encoding(object):
    """
    Interface for RPC message encoders/decoders.

    All encoding implementations used with this library should inherit
    and implement this.
    """

    def encode(self, data):
        """
        Encode the specified data.

        @param data: The data to encode
                     This method has to support encoding of the following
                     types: C{str}, C{int} and C{long}
                     Any additional data types may be supported as long as the
                     implementing class's C{decode()} method can successfully
                     decode them.

        @return: The encoded data
        @rtype: str
        """

    def decode(self, data):
        """
        Decode the specified data string.

        @param data: The data (byte string) to decode.
        @type data: str

        @return: The decoded data (in its correct type)
        """


class Bencode(Encoding):
    """
    Implementation of a Bencode-based algorithm (Bencode is the encoding
    algorithm used by Bittorrent).

    @note: This algorithm differs from the "official" Bencode algorithm in
           that it can encode/decode floating point values in addition to
           integers.
    """

    def encode(self, data, encoding='utf-8'):
        """
        Encoder implementation of the Bencode algorithm.

        @param data: The data to encode
        @type data: int, long, tuple, list, dict or str

        @return: The encoded data
        @rtype: str
        """
        if type(data) in six.integer_types:
            return b'i%de' % data
        elif isinstance(data, six.text_type):
            return b'%d:%s' % (len(data.encode(encoding=encoding)), data.encode(encoding=encoding))
        elif isinstance(data, six.binary_type):
            return b'%d:%s' % (len(data), data)
        elif type(data) in (list, tuple):
            encodedListItems = b''
            for item in data:
                encodedListItems += self.encode(item)
            return b'l%se' % encodedListItems
        elif isinstance(data, dict):
            encodedDictItems = b''
            _d = {(k.encode() if k and isinstance(k, six.text_type) else k) : v for k, v in data.items()}
            keys = sorted(_d.keys())
            for key in keys:
                e_key = self.encode(key)
                e_data = self.encode(_d[key])
                encodedDictItems += e_key
                encodedDictItems += e_data
            return b'd%se' % encodedDictItems
        elif isinstance(data, float):
            # This (float data type) is a non-standard extension to the original Bencode algorithm
            return b'f%fe' % data
        elif data is None:
            return b'i0e'  # return 0
        else:
            raise TypeError("Cannot bencode '%s' object" % type(data))

    def decode(self, data, encoding=None):
        """
        Decoder implementation of the Bencode algorithm.

        @param data: The encoded data
        @type data: str

        @note: This is a convenience wrapper for the recursive decoding
               algorithm, C{_decodeRecursive}

        @return: The decoded data, as a native Python type
        @rtype:  int, list, dict or str
        """
        return self._decodeRecursive(data, encoding=encoding)[0]

    @staticmethod
    def _decodeRecursive(data, startIndex=0, encoding=None):
        """
        Actual implementation of the recursive Bencode algorithm.

        Do not call this; use C{decode()} instead
        """
        if data[startIndex:startIndex+1] == b'i':
            endPos = data[startIndex:].find(b'e') + startIndex
            return (int(data[startIndex + 1:endPos]), endPos + 1)
        elif data[startIndex:startIndex+1] == b'l':
            startIndex += 1
            decodedList = []
            while data[startIndex:startIndex+1] != b'e':
                listData, startIndex = Bencode._decodeRecursive(data, startIndex, encoding=encoding)
                decodedList.append(listData)
            return (decodedList, startIndex + 1)
        elif data[startIndex:startIndex+1] == b'd':
            startIndex += 1
            decodedDict = {}
            while data[startIndex:startIndex+1] != b'e':
                key, startIndex = Bencode._decodeRecursive(data, startIndex, encoding=encoding)
                value, startIndex = Bencode._decodeRecursive(data, startIndex, encoding=encoding)
                decodedDict[key] = value
            return (decodedDict, startIndex)
        elif data[startIndex:startIndex+1] == b'f':
            # This (float data type) is a non-standard extension to the original Bencode algorithm
            endPos = data[startIndex:].find(b'e') + startIndex
            return (float(data[startIndex + 1:endPos]), endPos + 1)
        else:
            splitPos = data[startIndex:].find(b':') + startIndex
            length = int(data[startIndex:splitPos])
            startIndex = splitPos + 1
            endPos = startIndex + length
            byts = data[startIndex:endPos]
            if encoding:
                byts = byts.decode(encoding=encoding)
            return (byts, endPos)
