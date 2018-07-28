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
import json
import base64

from Cryptodome.Cipher import AES
from Cryptodome.Util import Padding
from Cryptodome.Random import get_random_bytes

#------------------------------------------------------------------------------

from lib import serialization

#------------------------------------------------------------------------------

def encrypt_to_json(raw_data, secret_16bytes_key):
    # not in use at the moment
    cipher = AES.new(secret_16bytes_key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(Padding.pad(raw_data, AES.block_size))
    iv = base64.b64encode(cipher.iv).decode('utf-8')
    ct = base64.b64encode(ct_bytes).decode('utf-8')
    result = json.dumps({'iv':iv, 'ct':ct, }, separators=(',', ':'), )
    return result


def decrypt_from_json(encrypted_data, secret_16bytes_key):
    # not in use at the moment
    b64 = json.loads(encrypted_data)  
    iv = base64.b64decode(b64['iv'])
    ct = base64.b64decode(b64['ct'])
    cipher = AES.new(secret_16bytes_key, AES.MODE_CBC, iv)
    result = Padding.unpad(cipher.decrypt(ct), AES.block_size)
    return result


def encrypt(raw_data, secret_16bytes_key):
    cipher = AES.new(
        key=secret_16bytes_key,
        mode=AES.MODE_CBC,
    )
    ct_bytes = cipher.encrypt(Padding.pad(raw_data, AES.block_size))
    output_data = dict(iv=cipher.iv, ct=ct_bytes)
    result = serialization.ObjectToString(output_data)
    return result


def decrypt(encrypted_data, secret_16bytes_key):
    input_data = serialization.StringToObject(encrypted_data)
    cipher = AES.new(
        key=secret_16bytes_key,
        mode=AES.MODE_CBC,
        iv=input_data['iv'],
    )
    padded_data = cipher.decrypt(input_data['ct'])
    result = Padding.unpad(padded_data, AES.block_size)
    return result


def make_key():
    return get_random_bytes(16)

