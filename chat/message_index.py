#!/usr/bin/python
# message_index.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (message_index.py) is part of BitDust Software.
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
..

module:: message_index
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import six

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

from hashlib import md5

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from lib import strng

#------------------------------------------------------------------------------

if six.PY2:
    from CodernityDB.hash_index import HashIndex
    from CodernityDB.tree_index import TreeBasedIndex, MultiTreeBasedIndex
else:
    from CodernityDB3.hash_index import HashIndex
    from CodernityDB3.tree_index import TreeBasedIndex, MultiTreeBasedIndex

#------------------------------------------------------------------------------

def definitions():
    return [
        ('sender_glob_id', SenderGlobID, ),
        ('recipient_glob_id', RecipientGlobID, ),
        ('sender_recipient_glob_id', SenderRecipientGlobID, ),
        ('payload_type', PayloadType, ),
        ('payload_time', PayloadTime, ),
        ('payload_message_id', PayloadMessageID, ),
        ('payload_body_hash', PayloadBodyHash, ),
    ]

#------------------------------------------------------------------------------

def make_custom_header():
    src = '\n'
    src += 'from chat.message_index import BaseHashIndex\n'
    src += 'from chat.message_index import BaseMD5Index\n'
    src += 'from chat.message_index import BaseTimeIndex\n'
    src += 'from chat.message_index import BaseMD5DoubleKeyIndex\n'
    return src

#------------------------------------------------------------------------------

class BaseHashIndex(HashIndex):
    role = None
    field = None
    key_format = '16s'

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = self.key_format
        super(BaseHashIndex, self).__init__(*args, **kwargs)

    def transform_key(self, key):
        if isinstance(key, six.text_type):
            key = key.encode()            
        return key

    def make_key_value(self, data):
        try:
            return self.transform_key(data[self.role][self.field]), None
        except (AttributeError, ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

    def make_key(self, key):
        if isinstance(key, six.text_type):
            key = key.encode()            
        return self.transform_key(key)

#------------------------------------------------------------------------------

class BaseMD5Index(BaseHashIndex):

    def transform_key(self, key):
        if isinstance(key, six.text_type):
            key = key.encode()            
        return md5(strng.to_bin(key)).digest()

#------------------------------------------------------------------------------

class BaseTimeIndex(TreeBasedIndex):
    role = None

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = 'I'
        kwargs['node_capacity'] = 128
        super(BaseTimeIndex, self).__init__(*args, **kwargs)

    def make_key_value(self, data):
        try:
            return data[self.role]['time'], None
        except (ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

    def make_key(self, key):
        if isinstance(key, six.text_type):
            key = key.encode()            
        return key

#------------------------------------------------------------------------------

class BaseMD5DoubleKeyIndex(MultiTreeBasedIndex):
    role_a = None
    field_a = None
    role_b = None
    field_b = None
    key_format = '16s'

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = self.key_format
        super(BaseMD5DoubleKeyIndex, self).__init__(*args, **kwargs)

    def transform_key(self, key):
        if isinstance(key, six.text_type):
            key = key.encode()            
        return md5(strng.to_bin(key)).digest()

    def make_key_value(self, data):
        try:
            key_a = data[self.role_a][self.field_a]
            key_b = data[self.role_b][self.field_b]
            if isinstance(key_a, six.text_type):
                key_a = key_a.encode()            
            if isinstance(key_b, six.text_type):
                key_b = key_b.encode()            
            version_1 = b'{}:{}'.format(key_a, key_b)
            version_2 = b'{}:{}'.format(key_b, key_a)
            out = set()
            out.add(self.transform_key(version_1))
            out.add(self.transform_key(version_2))
            return out, None
        except (AttributeError, ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

    def make_key(self, key):
        if isinstance(key, six.text_type):
            key = key.encode()            
        return self.transform_key(key)

#------------------------------------------------------------------------------

class SenderGlobID(BaseMD5Index):
    role = 'sender'
    field = 'glob_id'

#------------------------------------------------------------------------------

class RecipientGlobID(BaseMD5Index):
    role = 'recipient'
    field = 'glob_id'

#------------------------------------------------------------------------------

class SenderRecipientGlobID(BaseMD5DoubleKeyIndex):
    role_a = 'sender'
    field_a = 'glob_id'
    role_b = 'recipient'
    field_b = 'glob_id'

#------------------------------------------------------------------------------

class PayloadType(BaseMD5Index):
    role = 'payload'
    field = 'type'

#------------------------------------------------------------------------------

class PayloadMessageID(BaseMD5Index):
    role = 'payload'
    field = 'message_id'

#------------------------------------------------------------------------------

class PayloadBodyHash(BaseMD5Index):
    role = 'payload'
    field = 'body'

#------------------------------------------------------------------------------

class PayloadTime(BaseTimeIndex):
    role = 'payload'

#------------------------------------------------------------------------------
