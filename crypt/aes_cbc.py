#!/usr/bin/python
# aes_cbc.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (aes_cbc.py) is part of BitDust Software.
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

"""
.. module:: aes_cbc.


"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import base64

from Cryptodome.Cipher import AES
from Cryptodome.Util import Padding
from Cryptodome.Random import get_random_bytes

#------------------------------------------------------------------------------

from lib import serialization

#------------------------------------------------------------------------------

def encrypt_json(raw_data, secret_16bytes_key):
    # TODO: add salt to raw_data
    padded_data = Padding.pad(
        data_to_pad=raw_data,
        block_size=AES.block_size,
    )
    cipher = AES.new(
        key=secret_16bytes_key,
        mode=AES.MODE_CBC,
    )
    ct_bytes = cipher.encrypt(padded_data)
    dct = {
        'iv': base64.b64encode(cipher.iv).decode('utf-8'),
        'ct': base64.b64encode(ct_bytes).decode('utf-8'),
    }
    encrypted_data = serialization.DictToBytes(dct, encoding='utf-8')
    return encrypted_data


def decrypt_json(encrypted_data, secret_16bytes_key):
    dct = serialization.BytesToDict(
        encrypted_data,
        encoding='utf-8',
        keys_to_text=True,
        values_to_text=True,
    )
    cipher = AES.new(
        key=secret_16bytes_key,
        mode=AES.MODE_CBC,
        iv=base64.b64decode(dct['iv'].encode('utf-8')),
    )
    padded_data = cipher.decrypt(
        base64.b64decode(dct['ct'].encode('utf-8'))
    )
    raw_data = Padding.unpad(
        padded_data=padded_data,
        block_size=AES.block_size,
    )
    # TODO: remove salt from raw_data
    return raw_data

#------------------------------------------------------------------------------

def make_key():
    return get_random_bytes(16)

