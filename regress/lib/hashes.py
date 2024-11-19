#!/usr/bin/python
# hashes.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (hashes.py) is part of BitDust Software.
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
.. module:: hashes.


"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10
_CryptoLog = None

#------------------------------------------------------------------------------

try:
    from Cryptodome.Hash import MD5
    from Cryptodome.Hash import SHA1
    from Cryptodome.Hash import SHA256
except:
    from Crypto.Hash import MD5  # @UnresolvedImport @Reimport
    from Crypto.Hash import SHA1  # @UnresolvedImport @Reimport
    from Crypto.Hash import SHA256  # @UnresolvedImport @Reimport

#------------------------------------------------------------------------------

from lib import strng

#------------------------------------------------------------------------------


def md5(inp, hexdigest=False, return_object=False):
    global _CryptoLog
    # if _CryptoLog is None:
    #     _CryptoLog = os.environ.get('CRYPTO_LOG') == '1'
    if not strng.is_bin(inp):
        raise ValueError('input must by byte string')
    h = MD5.new(inp)
    if _Debug:
        if _CryptoLog:
            print('md5 hexdigest:', h.hexdigest())
    if return_object:
        return h
    if hexdigest:
        return strng.to_bin(h.hexdigest())
    return h.digest()


def sha1(inp, hexdigest=False, return_object=False):
    global _CryptoLog
    # if _CryptoLog is None:
    #     _CryptoLog = os.environ.get('CRYPTO_LOG') == '1'
    if not strng.is_bin(inp):
        raise ValueError('input must by byte string')
    h = SHA1.new(inp)
    if _Debug:
        if _CryptoLog:
            print('sha1 hexdigest:', h.hexdigest())
    if return_object:
        return h
    if hexdigest:
        return strng.to_bin(h.hexdigest())
    return h.digest()


def sha256(inp, hexdigest=False, return_object=False):
    global _CryptoLog
    # if _CryptoLog is None:
    #     _CryptoLog = os.environ.get('CRYPTO_LOG') == '1'
    if not strng.is_bin(inp):
        raise ValueError('input must by byte string')
    h = SHA256.new(inp)
    if _Debug:
        if _CryptoLog:
            print('sha256 hexdigest:', h.hexdigest())
    if return_object:
        return h
    if hexdigest:
        return strng.to_bin(h.hexdigest())
    return h.digest()
