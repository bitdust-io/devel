#!/usr/bin/python
# rsa_key.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

_Debug = True

#------------------------------------------------------------------------------

from Cryptodome.PublicKey import RSA
from Cryptodome.Signature import pkcs1_15
from Cryptodome.Cipher import PKCS1_OAEP
from Cryptodome.Util import number

#------------------------------------------------------------------------------

from logs import lg

from lib import strng

from system import local_fs

from crypt import hashes

#------------------------------------------------------------------------------

class RSAKey(object):
    
    def __init__(self):
        self.keyObject = None
    
    def isReady(self):
        return self.keyObject is not None

    def forget(self):
        self.keyObject = None
        gc.collect()
        return True

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

    def fromString(self, key_src):
        if self.keyObject:
            raise ValueError('key object already exist')
        key_src = strng.to_bin(key_src)
        try:
            self.keyObject = RSA.import_key(key_src)
        except:
            if _Debug:
                lg.exc('key_src=%r' % key_src)
        return True

    def fromFile(self, keyfilename):
        if self.keyObject:
            raise ValueError('key object already exist')
        key_src = local_fs.ReadTextFile(keyfilename)
        key_src = strng.to_bin(key_src)
        try:
            self.keyObject = RSA.import_key(key_src)
        except:
            if _Debug:
                lg.exc('key_src=%r' % key_src)
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

    def sign(self, message, as_digits=True):
        if not self.keyObject:
            raise ValueError('key object is not exist')
        if not strng.is_bin(message):
            raise ValueError('message must be byte string')
        h = hashes.sha1(message, return_object=True)
        signature_bytes = pkcs1_15.new(self.keyObject).sign(h)
        if not as_digits:
            return signature_bytes
        signature_raw = strng.to_bin(number.bytes_to_long(signature_bytes))
        if signature_bytes[0:1] == b'\x00':
            signature_raw = b'0' + signature_raw
        return signature_raw

    def verify(self, signature, message, signature_as_digits=True):
        signature_bytes = signature
        if signature_as_digits:
            signature_text = strng.to_text(signature)
            signature_int = int(signature_text)
            signature_bytes = number.long_to_bytes(signature_int)
            if signature[0:1] == b'0':
                signature_bytes = b'\x00' + signature_bytes
        if not strng.is_bin(signature_bytes):
            raise ValueError('signature must be byte string')
        if not strng.is_bin(message):
            raise ValueError('message must be byte string')
        h = hashes.sha1(message, return_object=True)
        try:
            pkcs1_15.new(self.keyObject).verify(h, signature_bytes)
            result = True
        except (ValueError, TypeError, ):
            if _Debug:
                lg.exc(msg='signature=%r\nmessage=%r\nsignature_as_digits=%r\n' % (
                    signature, message, signature_as_digits))
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
