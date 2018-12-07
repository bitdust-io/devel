#!/usr/bin/env python
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



def encode_hex(value):
    return codecs.decode(codecs.encode(value, 'hex'), 'utf8')


def decode_hex(value):
#     if not isinstance(value, six.text_type):
#         value = value.decode()
    return codecs.decode(value, 'hex')


class DecodeError(Exception):
    """ Should be raised by an C{Encoding} implementation if decode operation
    fails
    """

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
        """
        Encoder implementation of the Bencode algorithm.

        @param data: The data to encode
        @type data: int, long, tuple, list, dict or str

        @return: The encoded data
        @rtype: str
        """
        try:
            if type(data) in six.integer_types:
                return b'i%de' % data
            elif isinstance(data, six.text_type):
                return b'%d:%s' % (len(data.encode('utf-8')), data.encode('utf-8'))
            elif isinstance(data, six.binary_type):
                return b'%d:%s' % (len(data), data)
            elif type(data) in (list, tuple):
                encodedListItems = b''
                for item in data:
                    encodedListItems += self.encode(item)
                return b'l%se' % encodedListItems
            elif isinstance(data, dict):
                encodedDictItems = b''
                keys = sorted(data.keys())
                for key in keys:
                    e_key = self.encode(key)
                    e_data = self.encode(data[key])
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
        except:
            import traceback
            traceback.print_exc()

    def decode(self, data):
        """
        Decoder implementation of the Bencode algorithm.

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
        """
        Actual implementation of the recursive Bencode algorithm.

        Do not call this; use C{decode()} instead
        """
        try:
            if data[startIndex:startIndex+1] == b'i':
                endPos = data[startIndex:].find(b'e') + startIndex
                return (int(data[startIndex + 1:endPos]), endPos + 1)
            elif data[startIndex:startIndex+1] == b'l':
                startIndex += 1
                decodedList = []
                while data[startIndex:startIndex+1] != b'e':
                    listData, startIndex = Bencode._decodeRecursive(data, startIndex)
                    decodedList.append(listData)
                return (decodedList, startIndex + 1)
            elif data[startIndex:startIndex+1] == b'd':
                startIndex += 1
                decodedDict = {}
                while data[startIndex:startIndex+1] != b'e':
                    key, startIndex = Bencode._decodeRecursive(data, startIndex)
                    value, startIndex = Bencode._decodeRecursive(data, startIndex)
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
                return (byts, endPos)
        except:
            import traceback
            traceback.print_exc()


