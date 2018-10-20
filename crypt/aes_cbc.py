#!/usr/bin/python
# aes_cbc.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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
    cipher = AES.new(
        key=secret_16bytes_key,
        mode=AES.MODE_CBC,
    )
    ct_bytes = cipher.encrypt(Padding.pad(raw_data, AES.block_size))
    iv = base64.b64encode(cipher.iv).decode('utf-8')
    ct = base64.b64encode(ct_bytes).decode('utf-8')
    dct = {'iv':iv, 'ct':ct, }
    raw = serialization.DictToBytes(dct)
    return raw


def decrypt_json(encrypted_data, secret_16bytes_key):
    dct = serialization.BytesToDict(encrypted_data)
    iv = base64.b64decode(dct['iv'])
    ct = base64.b64decode(dct['ct'])
    cipher = AES.new(
        key=secret_16bytes_key,
        mode=AES.MODE_CBC,
        iv=iv,
    )
    result = Padding.unpad(cipher.decrypt(ct), AES.block_size)
    # TODO: remove salt from raw_data
    return result

#------------------------------------------------------------------------------

def make_key():
    return get_random_bytes(16)

