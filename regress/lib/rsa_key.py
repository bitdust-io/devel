#!/usr/bin/python
# rsa_key.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10
_CryptoLog = None

#------------------------------------------------------------------------------

try:
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Signature import pkcs1_15
    from Cryptodome.Cipher import PKCS1_OAEP
except:
    from Crypto.PublicKey import RSA  # @UnresolvedImport @Reimport
    from Crypto.Signature import pkcs1_15  # @UnresolvedImport @Reimport
    from Crypto.Cipher import PKCS1_OAEP  # @UnresolvedImport @Reimport

#------------------------------------------------------------------------------

from lib import strng
from lib import system
from lib import hashes
from lib import number

#------------------------------------------------------------------------------


class RSAKey(object):

    def __init__(self):
        self.keyObject = None
        self.label = ''
        self.signed = None
        self.active = True
        self.meta = {}

    def __str__(self) -> str:
        return 'RSAKey(%s|%s)' % (self.label, 'active' if self.active else 'inactive')

    def isReady(self):
        return self.keyObject is not None

    def forget(self):
        self.keyObject = None
        self.label = ''
        self.signed = None
        self.active = False
        self.meta = {}
        # gc.collect()
        return True

    def size(self):
        return self.keyObject.size_in_bits()

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

    def fromDict(self, key_dict):
        if self.keyObject:
            raise ValueError('key object already exist')
        key_src = key_dict['body']
        result = self.fromString(key_src)
        if result:
            self.label = key_dict.get('label', '')
            self.active = key_dict.get('active', True)
            self.meta = dict(key_dict.get('meta', {}))
            if 'signature' in key_dict and 'signature_pubkey' in key_dict:
                self.signed = (
                    key_dict['signature'],
                    key_dict['signature_pubkey'],
                )
        del key_src
        # gc.collect()
        return result

    def fromString(self, key_src):
        if self.keyObject:
            raise ValueError('key object already exist')
        if strng.is_text(key_src):
            key_src = strng.to_bin(key_src)
        try:
            self.keyObject = RSA.import_key(key_src)  # @UndefinedVariable
        except Exception as exc:
            if _Debug:
                print(exc, 'key_src=%r' % key_src)
            raise ValueError('failed to read key body')
        del key_src
        # gc.collect()
        return True

    def fromFile(self, keyfilename):
        if self.keyObject:
            raise ValueError('key object already exist')
        key_src = system.ReadTextFile(keyfilename)
        key_src = strng.to_bin(key_src)
        try:
            self.keyObject = RSA.import_key(key_src)  # @UndefinedVariable
        except Exception as exc:
            if _Debug:
                print(exc, 'key_src=%r' % key_src)
        del key_src
        # gc.collect()
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

    def toDict(self, include_private=False, output_format_private='PEM', output_format_public='OpenSSH'):
        if not self.keyObject:
            raise ValueError('key object is not exist')
        if include_private and not self.keyObject.has_private():
            raise ValueError('this key contains only public component')
        if include_private:
            key_body = strng.to_text(self.keyObject.exportKey(format=output_format_private))
        else:
            key_body = strng.to_text(self.keyObject.publickey().exportKey(format=output_format_public))
        key_dict = {
            'body': key_body,
            'label': self.label,
            'active': self.active,
        }
        if self.isSigned():
            key_dict.update({
                'signature': self.signed[0],
                'signature_pubkey': self.signed[1],
            })
        if self.meta:
            key_dict['meta'] = self.meta.copy()
        return key_dict

    def sign(self, message, as_digits=True):
        global _CryptoLog
        # if _CryptoLog is None:
        #     _CryptoLog = os.environ.get('CRYPTO_LOG') == '1'
        if not self.keyObject:
            raise ValueError('key object is not exist')
        if not strng.is_bin(message):
            raise ValueError('message must be byte string')
        h = hashes.sha1(message, return_object=True)
        signature_raw = pkcs1_15.new(self.keyObject).sign(h)
        if not as_digits:
            if _Debug:
                if _CryptoLog:
                    print('sign signature_raw:', signature_raw)
            return signature_raw
        signature_long = number.bytes_to_long(signature_raw)
        signature_bytes = strng.to_bin(signature_long)
        if _Debug:
            if _CryptoLog:
                print('sign signature_bytes:', signature_bytes)
        return signature_bytes

    def verify(self, signature, message, signature_as_digits=True):
        global _CryptoLog
        # if _CryptoLog is None:
        #     _CryptoLog = os.environ.get('CRYPTO_LOG') == '1'
        signature_bytes = signature
        if signature_as_digits:
            signature_bytes = number.long_to_bytes(signature, blocksize=4)
        if not strng.is_bin(signature_bytes):
            raise ValueError('signature must be byte string')
        if not strng.is_bin(message):
            raise ValueError('message must be byte string')
        h = hashes.sha1(message, return_object=True)
        result = False
        try:
            pkcs1_15.new(self.keyObject).verify(h, signature_bytes)
            result = True
        except (
            ValueError,
            TypeError
        ) as exc:
            # do not raise any exception... just return False
            if _Debug:
                print(exc, 'signature=%r message=%r signed=%r label=%r meta=%r' % (signature, message, self.isSigned(), self.label, self.meta))
        if _Debug:
            if _CryptoLog:
                print('verify', result, signature)
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

    def isSigned(self):
        return self.signed is not None
