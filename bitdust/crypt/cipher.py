#!/usr/bin/python
# cipher.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (cipher.py) is part of BitDust Software.
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
.. module:: cipher.


"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import base64

try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Cipher import DES3
    from Cryptodome.Util import Padding
    from Cryptodome.Random import get_random_bytes, random
except:
    from Crypto.Cipher import AES  # @UnresolvedImport @Reimport
    from Crypto.Cipher import DES3  # @UnresolvedImport @Reimport
    from Crypto.Util import Padding  # @UnresolvedImport @Reimport
    from Crypto.Random import get_random_bytes, random  # @UnresolvedImport @Reimport

#------------------------------------------------------------------------------

from bitdust.lib import serialization

#------------------------------------------------------------------------------


def encrypt_json(raw_data, secret_bytes_key, cipher_type='AES'):
    # TODO: add salt to raw_data
    padded_data = Padding.pad(
        data_to_pad=raw_data,
        block_size=AES.block_size,
    )
    if cipher_type == 'AES':
        cipher = AES.new(
            key=secret_bytes_key,
            mode=AES.MODE_CBC,
        )
    elif cipher_type == 'DES3':
        cipher = DES3.new(
            key=secret_bytes_key,
            mode=DES3.MODE_CBC,
        )
    else:
        raise Exception('unsupported cipher type')
    ct_bytes = cipher.encrypt(padded_data)
    dct = {
        'iv': base64.b64encode(cipher.iv).decode('utf-8'),
        'ct': base64.b64encode(ct_bytes).decode('utf-8'),
    }
    encrypted_data = serialization.DictToBytes(dct, encoding='utf-8')
    return encrypted_data


def decrypt_json(encrypted_data, secret_bytes_key, cipher_type='AES'):
    dct = serialization.BytesToDict(
        encrypted_data,
        encoding='utf-8',
        keys_to_text=True,
        values_to_text=True,
    )
    if cipher_type == 'AES':
        cipher = AES.new(
            key=secret_bytes_key,
            mode=AES.MODE_CBC,
            iv=base64.b64decode(dct['iv'].encode('utf-8')),
        )
    elif cipher_type == 'DES3':
        cipher = DES3.new(
            key=secret_bytes_key,
            mode=DES3.MODE_CBC,
            iv=base64.b64decode(dct['iv'].encode('utf-8')),
        )
    else:
        raise Exception('unsupported cipher type')
    padded_data = cipher.decrypt(base64.b64decode(dct['ct'].encode('utf-8')))
    if cipher_type == 'AES':
        raw_data = Padding.unpad(
            padded_data=padded_data,
            block_size=AES.block_size,
        )
    elif cipher_type == 'DES3':
        raw_data = Padding.unpad(
            padded_data=padded_data,
            block_size=DES3.block_size,
        )
    # TODO: remove salt from raw_data
    return raw_data


#------------------------------------------------------------------------------

def make_key(cipher_type='AES'):
    if cipher_type == 'AES':
        return get_random_bytes(AES.block_size)
    elif cipher_type == 'DES3':
        return get_random_bytes(DES3.block_size)
    raise Exception('unsupported cipher type')


def generate_secret_text(size):
    return base64.b32encode(get_random_bytes(size)).decode()


def generate_digits(length, as_text=True):
    if as_text:
        return ''.join(map(str, [random.randint(0, 9) for _ in range(length)]))
    return [random.randint(0, 9) for _ in range(length)]
