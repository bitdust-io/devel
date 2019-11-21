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
    from CodernityDB.hash_index import HashIndex, UniqueHashIndex
    from CodernityDB.tree_index import TreeBasedIndex, MultiTreeBasedIndex
else:
    from CodernityDB3.hash_index import HashIndex, UniqueHashIndex
    from CodernityDB3.tree_index import TreeBasedIndex, MultiTreeBasedIndex

#------------------------------------------------------------------------------

def definitions():
    if six.PY2 or True:
        return [
            # ('id', MessageID, ),
            ('sender_glob_id', SenderGlobID, ),
            ('recipient_glob_id', RecipientGlobID, ),
            ('sender_recipient_glob_id', SenderRecipientGlobID, ),
            ('payload_type', PayloadType, ),
            ('payload_time', PayloadTime, ),
            ('payload_message_id', PayloadMessageID, ),
            ('payload_body_hash', PayloadBodyHash, ),
        ]
    return [
        ('id', '00id.py', ),
        ('sender_glob_id', '01sender_glob_id.py', ),
        ('recipient_glob_id', '02recipient_glob_id.py', ),
        ('sender_recipient_glob_id', '03sender_recipient_glob_id.py', ),
        ('payload_type', '04payload_type.py', ),
        ('payload_time', '05payload_time.py', ),
        ('payload_message_id', '06payload_message_id.py', ),
        ('payload_body_hash', '07payload_body_hash.py', ),
    ]

#------------------------------------------------------------------------------

def make_custom_header():
    src = '\n'
    src += 'from chat.message_index import BaseTimeIndex\n'
    src += 'from chat.message_index import BaseMD5Index\n'
    src += 'from chat.message_index import BaseMD5DoubleKeyIndex\n'
    return src

#------------------------------------------------------------------------------

class BaseMD5Index(HashIndex):
    role = None
    field = None
    key_format = '32s'

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = self.key_format
        super(BaseMD5Index, self).__init__(*args, **kwargs)

    def make_key_value(self, data):
        try:
            key = data[self.role][self.field]
            if isinstance(key, six.text_type):
                key = key.encode()
            k = md5(key).hexdigest()
            return k, {}
        except (AttributeError, ValueError, KeyError, IndexError, ):
            return None
        except Exception as exc:
            lg.exc()
            raise exc

    def make_key(self, key):
        if isinstance(key, six.text_type):
            key = key.encode()
        k = md5(key).hexdigest()
        return k

#------------------------------------------------------------------------------

class BaseTimeIndex(TreeBasedIndex):
    role = None

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = 'I'
        kwargs['node_capacity'] = 128
        super(BaseTimeIndex, self).__init__(*args, **kwargs)

    def make_key_value(self, data):
        try:
            key = data[self.role]['time']
            return key, None
        except (ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

    def make_key(self, key):
        return key

#------------------------------------------------------------------------------

class BaseMD5DoubleKeyIndex(MultiTreeBasedIndex):
    role_a = None
    field_a = None
    role_b = None
    field_b = None
    key_format = '32s'

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = self.key_format
        super(BaseMD5DoubleKeyIndex, self).__init__(*args, **kwargs)

    def transform_key(self, key):
        if isinstance(key, six.text_type):
            key = key.encode()
        return md5(key).hexdigest().encode()

    def make_key_value(self, data):
        try:
            key_a = data[self.role_a][self.field_a]
            key_b = data[self.role_b][self.field_b]
            version_1 = '{}:{}'.format(key_a, key_b)
            version_2 = '{}:{}'.format(key_b, key_a)
            out = set()
            out.add(self.transform_key(version_1))
            out.add(self.transform_key(version_2))
            return out, None
        except (AttributeError, ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

    def make_key(self, key):
        return self.transform_key(key)

#------------------------------------------------------------------------------

class MessageID(UniqueHashIndex):
    pass


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
