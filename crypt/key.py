#!/usr/bin/python
# key.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (key.py) is part of BitDust Software.
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
.. module:: key.

Here is a bunch of cryptography methods used in all parts of the software.
BitDust uses PyCryptodome library: https://www.pycryptodome.org/
Our local key is always on hand.
Main thing here is to be able to use public keys in contacts to verify packets.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
from six.moves import range

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys
import gc

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg
from lib import strng

from system import bpio

from main import settings

from crypt import rsa_key
from crypt import hashes
from crypt import aes_cbc

#------------------------------------------------------------------------------

_MyKeyObject = None

#------------------------------------------------------------------------------


def InitMyKey(keyfilename=None):
    """
    This is core method. At first it check the Private Key in the memory, if it
    is already initialized it does nothing. The local key are placed in the
    "[BitDust data dir]/metadata/mykeyfile". If file "[BitDust data
    dir]/metadata/mykeyfile_location" exists - it should contain the location
    of the mykeyfile. Useful to store Private Key on the USB flash. BitDust
    data dir is platform dependent:

        - Linux and Mac: ~/.bitdust
        - Windows XP: C:/Documents and Settings/[user]/.bitdust
        - Windows Vista, 7, 8: C:/Users/[user]/.bitdust
    Finally if target file exist - the Private Key will be loaded into memory.
    If file does not exist - the new key will be generated.
    The size for new key will be taken from settings.
    """
    global _MyKeyObject
    if _MyKeyObject is not None and _MyKeyObject.isReady():
        return False
    if not LoadMyKey(keyfilename):
        return False
        # GenerateNewKey(keyfilename)
    return True


def isMyKeyExists(keyfilename=None):
    if keyfilename is None:
        keyfilename = settings.KeyFileName()
    if os.path.exists(keyfilename + '_location'):
        newkeyfilename = bpio.ReadTextFile(keyfilename + '_location').strip()
        if os.path.exists(newkeyfilename):
            keyfilename = newkeyfilename
    return os.path.exists(keyfilename)


def LoadMyKey(keyfilename=None):
    global _MyKeyObject
    if keyfilename is None:
        keyfilename = settings.KeyFileName()
    if os.path.exists(keyfilename + '_location'):
        newkeyfilename = bpio.ReadTextFile(keyfilename + '_location').strip()
        if os.path.exists(newkeyfilename):
            keyfilename = newkeyfilename
    if not os.path.exists(keyfilename):
        return False
    _MyKeyObject = rsa_key.RSAKey()
    _MyKeyObject.fromFile(keyfilename)
    if _Debug:
        lg.out(_DebugLevel, 'key.InitMyKey loaded private key from %s' % (keyfilename))
    if not ValidateKey():
        if _Debug:
            lg.out(_DebugLevel, 'key.InitMyKey  private key is not valid: %s' % (keyfilename))
        return False
    return True


def GenerateNewKey(keyfilename=None):
    global _MyKeyObject
    if keyfilename is None:
        keyfilename = settings.KeyFileName()
    if os.path.exists(keyfilename + '_location'):
        newkeyfilename = bpio.ReadTextFile(keyfilename + '_location').strip()
        if os.path.exists(newkeyfilename):
            keyfilename = newkeyfilename
    if _Debug:
        lg.out(_DebugLevel, 'key.InitMyKey generate new private key')
    _MyKeyObject = rsa_key.RSAKey()
    _MyKeyObject.generate(settings.getPrivateKeySize())
    keystring = _MyKeyObject.toPrivateString()
    bpio.WriteTextFile(keyfilename, keystring)
    if _Debug:
        lg.out(_DebugLevel, '    wrote %d bytes to %s' % (len(keystring), keyfilename))
    del keystring
    gc.collect()


def ValidateKey():
    curkey = MyPrivateKeyObject()
    data256 = os.urandom(256)
    signature256 = curkey.sign(data256)
    return curkey.verify(signature256, data256)


def ForgetMyKey():
    """
    Remove Private Key from memory.
    """
    global _MyKeyObject
    if _MyKeyObject:
        _MyKeyObject.forget()
    _MyKeyObject = None


def isMyKeyReady():
    """
    Check if the Key is already loaded into memory.
    """
    global _MyKeyObject
    return _MyKeyObject is not None and _MyKeyObject.isReady()


def MyPublicKey():
    """
    Return Public part of the Key as PEM string.
    """
    global _MyKeyObject
    InitMyKey()
    Result = _MyKeyObject.toPublicString()
    return Result


def MyPrivateKey():
    """
    Return Private part of the Key as PEM string.
    """
    global _MyKeyObject
    if not _MyKeyObject:
        InitMyKey()
    return _MyKeyObject.toPrivateString()


def MyPrivateKeyObject():
    """
    Return Private part of the Key as object.
    """
    global _MyKeyObject
    if not _MyKeyObject:
        InitMyKey()
    return _MyKeyObject

#------------------------------------------------------------------------------


def Sign(inp):
    """
    Sign some ``inp`` string with our Private Key, this calls PyCrypto method
    ``Crypto.PublicKey.RSA.sign``.
    """
    global _MyKeyObject
    if not _MyKeyObject:
        InitMyKey()
    result = _MyKeyObject.sign(inp)
    return result


def VerifySignature(pubkeystring, hashcode, signature):
    """
    Verify signature, this calls function ``Crypto.PublicKey.RSA.verify`` to
    verify.

    :param keystring: PublicKey in openssh format.
    :param hashcode: input data to verify, we use method ``Hash`` to prepare that.
    :param signature: string with signature to verify.

    Return True if signature is correct, otherwise False.
    """
    pub_key = rsa_key.RSAKey()
    pub_key.fromString(pubkeystring)
    result = pub_key.verify(signature, hashcode)
    return result


def Verify(ConIdentity, hashcode, signature):
    """
    This takes Public Key from user identity and calls ``VerifySignature``.

    :param ConIdentity: user's identity object'.
    """
    pubkey = ConIdentity.publickey
    Result = VerifySignature(pubkey, hashcode, signature)
    return Result

#------------------------------------------------------------------------------


def HashMD5(inp, hexdigest=False):
    """
    Use MD5 method to calculate the hash of ``inp`` string.

    However it seems it is not so safe anymore:
    http://natmchugh.blogspot.co.uk/2014/10/how-i-created-two-images-
    with-same-md5.html
    """
    return hashes.md5(inp, hexdigest=hexdigest)


def HashSHA(inp, hexdigest=False):
    """
    Use SHA1 method to calculate the hash of ``inp`` string.
    """
    return hashes.sha1(inp, hexdigest=hexdigest)


def HashSHA512(inp, hexdigest=False):
    """
    """
    return hashes.sha256(inp, hexdigest=hexdigest)


def Hash(inp, hexdigest=False):
    """
    Core function to calculate hash of ``inp`` string, right now it uses SHA1
    method.
    """
    return HashSHA(inp, hexdigest=hexdigest)

#------------------------------------------------------------------------------


def SessionKeyType():
    """
    Which crypto is used for session key.
    """
    return 'AES'


def NewSessionKey():
    """
    Return really random string for making AES cipher objects when needed.
    """
    return aes_cbc.make_key()

#------------------------------------------------------------------------------

def EncryptWithSessionKey(session_key, inp):
    """
    Encrypt input string with Session Key.

    :param session_key: randomly generated session key
    :param inp: input string to encrypt
    """
    ret = aes_cbc.encrypt_json(inp, session_key)
    return ret


def DecryptWithSessionKey(session_key, inp):
    """
    Decrypt string with given session key.

    :param session_key: a session key comes with the message in encrypted form,
        here it must be already decrypted
    :param inp: input string to decrypt
    """
    ret = aes_cbc.decrypt_json(inp, session_key)
    return ret

#------------------------------------------------------------------------------

def EncryptOpenSSHPublicKey(pubkeystring, inp):
    """
    Encrypt ``inp`` string with given Public Key.
    """
    pub_key = rsa_key.RSAKey()
    pub_key.fromString(pubkeystring)
    result = pub_key.encrypt(inp)
    return result


def DecryptOpenSSHPrivateKey(privkeystring, inp):
    """
    Decrypt ``inp`` string with a Private Key provided as string in PEM format.
    """
    priv_key = rsa_key.RSAKey()
    priv_key.fromString(privkeystring)
    result = priv_key.decrypt(inp)
    return result

#------------------------------------------------------------------------------

def EncryptLocalPublicKey(inp):
    """
    This is just using local key, encrypt ``inp`` string.
    """
    global _MyKeyObject
    if not _MyKeyObject:
        InitMyKey()
    result = _MyKeyObject.encrypt(inp)
    return result


def DecryptLocalPrivateKey(inp):
    """
    Decrypt ``inp`` string with your Private Key.
    Here we decrypt with our local private key - so no argument for that.
    """
    global _MyKeyObject
    if not _MyKeyObject:
        InitMyKey()
    result = _MyKeyObject.decrypt(inp)
    return result

#------------------------------------------------------------------------------


def SpeedTest():
    """
    Some tests to check the performance.
    """
    import time
    dataSZ = 1024 * 640
    loops = 10
    packets = []
    dt = time.time()
    print('encrypt %d pieces of %d bytes' % (loops, dataSZ))
    for i in range(loops):
        Data = os.urandom(dataSZ)
        SessionKey = NewSessionKey()
        EncryptedSessionKey = EncryptLocalPublicKey(SessionKey)
        EncryptedData = EncryptWithSessionKey(SessionKey, Data)
        Signature = Sign(Hash(EncryptedData))
        packets.append((Data, len(Data), EncryptedSessionKey, EncryptedData, Signature))
        print('.', end=' ')
    print(time.time() - dt, 'seconds')

    dt = time.time()
    print('decrypt now')
    i = 0
    for Data, Length, EncryptedSessionKey, EncryptedData, Signature in packets:
        SessionKey = DecryptLocalPrivateKey(EncryptedSessionKey)
        paddedData = DecryptWithSessionKey(SessionKey, EncryptedData)
        newData = paddedData[:Length]
        if not VerifySignature(MyPublicKey(), Hash(EncryptedData), Signature):
            raise Exception()
        if newData != Data:
            raise Exception
        print('.', end=' ')
        # open(str(i), 'wb').write(EncryptedData)
        i += 1
    print(time.time() - dt, 'seconds')

#------------------------------------------------------------------------------

if __name__ == '__main__':
    bpio.init()
    lg.set_debug_level(18)
    settings.init()
    InitMyKey()
    SpeedTest()
