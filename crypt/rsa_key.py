#!/usr/bin/python
# rsa_key.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (rsa_key.py) is part of BitDust Software.
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
.. module:: rsa_key.


"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import gc

#------------------------------------------------------------------------------

_Debug = False

#------------------------------------------------------------------------------

from Cryptodome.PublicKey import RSA
from Cryptodome.Hash import SHA1
from Cryptodome.Signature import pkcs1_15
from Cryptodome.Cipher import PKCS1_OAEP
from Cryptodome.Util import number

#------------------------------------------------------------------------------

from lib import strng

from system import local_fs

#------------------------------------------------------------------------------

class RSAKey(object):
    
    def __init__(self):
        self.keyObject = None
    
    def isReady(self):
        return self.keyObject is not None

    def generate(self, bits):
        if self.keyObject:
            raise ValueError('key object already exist')
        self.keyObject = RSA.generate(bits)
        return True

    def isPublic(self):
        if not self.keyObject:
            raise ValueError('key object is not exist')
        if self.keyObject.has_private():
            return False
        return True

    def isPrivate(self):
        if not self.keyObject:
            raise ValueError('key object is not exist')
        if not self.keyObject.has_private():
            return False
        return True

    def public(self):
        if self.isPublic():
            return self
        return self.keyObject.publickey()

    def fromString(self, key_string):
        if self.keyObject:
            raise ValueError('key object already exist')
        self.keyObject = RSA.import_key(strng.to_bin(key_string))
        return True

    def fromFile(self, keyfilename):
        if self.keyObject:
            raise ValueError('key object already exist')
        key_src = local_fs.ReadTextFile(keyfilename)
        self.keyObject = RSA.import_key(strng.to_bin(key_src))
        del key_src
        gc.collect()
        return True

    def toPrivateString(self, output_format='PEM'):
        if not self.keyObject:
            raise ValueError('key object is not exist')
        if not self.keyObject.has_private():
            raise ValueError('this key contains only public component')
        return strng.to_text(self.keyObject.exportKey(format=output_format))

    def toPublicString(self, output_format='OpenSSH'):
        if not self.keyObject:
            raise ValueError('key object is not exist')
        return strng.to_text(self.keyObject.publickey().exportKey(format=output_format))

    def sign(self, message):
        if not self.keyObject:
            raise ValueError('key object is not exist')
        h = SHA1.new(strng.to_bin(message))
        signature_bytes = pkcs1_15.new(self.keyObject).sign(h)
        signature_int = number.bytes_to_long(signature_bytes)
        signature = strng.to_text(str(signature_int))
        return signature

    def verify(self, signature, message):
        h = SHA1.new(strng.to_bin(message))
        try:
            signature_int = int(signature)
            signature_bytes = number.long_to_bytes(signature_int)
            pkcs1_15.new(self.keyObject).verify(h, signature_bytes)
            result = True
        except (ValueError, TypeError, ):
            if _Debug:
                from logs import lg
                lg.exc()
            result = False
        return result

    def encrypt(self, private_message):
        if not self.keyObject:
            raise ValueError('key object is not exist')
        cipher = PKCS1_OAEP.new(self.keyObject)
        ciphertext = cipher.encrypt(private_message)        
        return ciphertext

    def decrypt(self, encrypted_payload):
        if not self.keyObject:
            raise ValueError('key object is not exist')
        cipher = PKCS1_OAEP.new(self.keyObject)
        private_message = cipher.decrypt(encrypted_payload)
        return private_message

