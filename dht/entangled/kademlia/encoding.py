#!/usr/bin/env python
# encoding.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (encoding.py) is part of BitDust Software.
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
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net


class Encoding(object):
    """ Interface for RPC message encoders/decoders

    All encoding implementations used with this library should inherit and
    implement this.
    """

    def encode(self, data):
        """ Encode the specified data

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
        """ Decode the specified data string

        @param data: The data (byte string) to decode.
        @type data: str

        @return: The decoded data (in its correct type)
        """


class Bencode(Encoding):
    """ Implementation of a Bencode-based algorithm (Bencode is the encoding
    algorithm used by Bittorrent).

    @note: This algorithm differs from the "official" Bencode algorithm in
           that it can encode/decode floating point values in addition to
           integers.
    """

    def encode(self, data):
        """ Encoder implementation of the Bencode algorithm

        @param data: The data to encode
        @type data: int, long, tuple, list, dict or str

        @return: The encoded data
        @rtype: str
        """
        if type(data) in (int, long):
            return 'i%de' % data
        elif isinstance(data, str):
            return '%d:%s' % (len(data), data)
        elif type(data) in (list, tuple):
            encodedListItems = ''
            for item in data:
                encodedListItems += self.encode(item)
            return 'l%se' % encodedListItems
        elif isinstance(data, dict):
            encodedDictItems = ''
            keys = sorted(data.keys())
            for key in keys:
                encodedDictItems += self.encode(key)
                encodedDictItems += self.encode(data[key])
            return 'd%se' % encodedDictItems
        elif type(data == float):
            # This (float data type) is a non-standard extension to the
            # original Bencode algorithm
            return 'f%fe' % data
        else:
            raise TypeError("Cannot bencode '%s' object" % type(data))

    def decode(self, data):
        """ Decoder implementation of the Bencode algorithm

        @param data: The encoded data
        @type data: str

        @note: This is a convenience wrapper for the recursive decoding
               algorithm, C{_decodeRecursive}

        @return: The decoded data, as a native Python type
        @rtype:  int, list, dict or str
        """
        return self._decodeRecursive(data)[0]

    @staticmethod
    def _decodeRecursive(data, startIndex=0):
        """ Actual implementation of the recursive Bencode algorithm

        Do not call this; use C{decode()} instead
        """
        if data[startIndex] == 'i':
            endPos = data[startIndex:].find('e') + startIndex
            return (int(data[startIndex + 1:endPos]), endPos + 1)
        elif data[startIndex] == 'l':
            startIndex += 1
            decodedList = []
            while data[startIndex] != 'e':
                listData, startIndex = Bencode._decodeRecursive(
                    data, startIndex)
                decodedList.append(listData)
            return (decodedList, startIndex + 1)
        elif data[startIndex] == 'd':
            startIndex += 1
            decodedDict = {}
            while data[startIndex] != 'e':
                key, startIndex = Bencode._decodeRecursive(data, startIndex)
                value, startIndex = Bencode._decodeRecursive(data, startIndex)
                decodedDict[key] = value
            return (decodedDict, startIndex)
        elif data[startIndex] == 'f':
            # This (float data type) is a non-standard extension to the
            # original Bencode algorithm
            endPos = data[startIndex:].find('e') + startIndex
            return (float(data[startIndex + 1:endPos]), endPos + 1)
        else:
            splitPos = data[startIndex:].find(':') + startIndex
            length = int(data[startIndex:splitPos])
            startIndex = splitPos + 1
            endPos = startIndex + length
            bytes = data[startIndex:endPos]
            return (bytes, endPos)
