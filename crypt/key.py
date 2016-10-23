#!/usr/bin/python
#key.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
.. module:: key

Here is a bunch of cryptography methods used in all parts of the software.
BitDust uses PyCrypto library:
    https://www.dlitz.net/software/pycrypto/
For most of BitDust code (outside ssh I think) we will only use ascii encoded string versions of keys.
Expect to make keys, signatures, and hashes all base64 strings soon.
Our local key is always on hand.
Main thing is to be able to use public keys in contacts to verify packets.
We never want to bother storing bad data, and need localtester to do local scrub.

TODO:
http://code.activestate.com/recipes/576980-authenticated-encryption-with-pycrypto/
    * need to add salt in IV
    * use something more advanced than os.urandom
"""

import os
import sys
import random
import hashlib

from Crypto.PublicKey import RSA
from Crypto.Cipher import DES3
from Crypto.Cipher import AES  
from Crypto.Cipher import Blowfish

import warnings
warnings.filterwarnings('ignore',category=DeprecationWarning)

from twisted.conch.ssh import keys

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio

from main import settings

#------------------------------------------------------------------------------ 

_MyRsaKey = None 
_MyPubKey = None

#------------------------------------------------------------------------------ 

def InitMyKey(keyfilename=None):
    """
    This is core method. 
    At first it check the Private Key in the memory, if it is already initialized it does nothing. 
    The local key are placed in the "[BitDust data dir]/metadata/mykeyfile".
    If file "[BitDust data dir]/metadata/mykeyfile_location" exists - 
    it should contain the location of the mykeyfile. Useful to store Private Key on the USB flash.
    BitDust data dir is platform dependent:
        - Linux and Mac: ~/.bitdust
        - Windows XP: C:/Documents and Settings/[user]/.bitdust
        - Windows Vista, 7, 8: C:/Users/[user]/.bitdust
    Finally if target file exist - the Private Key will be loaded into memory.
    If file does not exist - the new key will be generated. 
    The size for new key will be taken from settings.  
    """
    global _MyRsaKey
    global _MyPubKey
    if _MyPubKey is not None:
        return
    if _MyRsaKey is not None:
        return
    if not LoadMyKey(keyfilename):
        GenerateNewKey(keyfilename)

def LoadMyKey(keyfilename=None):
    global _MyRsaKey
    global _MyPubKey
    if keyfilename is None:
        keyfilename = settings.KeyFileName()
    if os.path.exists(keyfilename+'_location'):
        newkeyfilename = bpio.ReadTextFile(keyfilename+'_location').strip()
        if os.path.exists(newkeyfilename):
            keyfilename = newkeyfilename
    if os.path.exists(keyfilename):
        _MyPubKey = keys.Key.fromFile(keyfilename)
        _MyRsaKey = _MyPubKey.keyObject
        lg.out(4, 'key.InitMyKey loaded private key from %s' % (keyfilename))
        return ValidateKey()
    return False

def GenerateNewKey(keyfilename=None):
    global _MyPubKey
    global _MyRsaKey
    if keyfilename is None:
        keyfilename = settings.KeyFileName()
    if os.path.exists(keyfilename+'_location'):
        newkeyfilename = bpio.ReadTextFile(keyfilename+'_location').strip()
        if os.path.exists(newkeyfilename):
            keyfilename = newkeyfilename
    lg.out(4, 'key.InitMyKey generate new private key')
    _MyRsaKey = RSA.generate(settings.getPrivateKeySize(), os.urandom)
    _MyPubKey = keys.Key(_MyRsaKey)
    keystring = _MyPubKey.toString('openssh')
    bpio.WriteFile(keyfilename, keystring)
    lg.out(4, '    wrote %d bytes to %s' % (len(keystring), keyfilename))

def ValidateKey():
    curkey = MyPrivateKeyObject()
    data256 = os.urandom(256)
    signature256 = curkey.sign(data256)
    return curkey.verify(signature256, data256)

def ForgetMyKey():
    """
    Remove Private Key from memory.
    """
    global _MyPubKey
    global _MyRsaKey
    _MyPubKey = None
    _MyRsaKey = None

def isMyKeyReady():
    """
    Check if the Key is already loaded into memory.
    """
    global _MyRsaKey
    return _MyRsaKey is not None

def MyPublicKey():
    """
    Return Public part of the Key as openssh string.
    """
    global _MyPubKey
    InitMyKey()
    Result = _MyPubKey.public().toString('openssh')
    return Result

def MyPrivateKey():
    """
    Return Private part of the Key as openssh string.
    """
    global _MyPubKey
    InitMyKey()
    return _MyPubKey.toString('openssh')

def MyPublicKeyObject():
    """
    Return Public part of the Key as object, useful to convert to different formats.
    """
    global _MyPubKey
    InitMyKey()
    return _MyPubKey.public()

def MyPrivateKeyObject():
    """
    Return Private part of the Key as object.
    """
    global _MyPubKey
    InitMyKey()
    return _MyPubKey

#------------------------------------------------------------------------------ 

def Sign(inp):
    """
    Sign some ``inp`` string with our Private Key, this calls PyCrypto method ``Crypto.PublicKey.RSA.sign``.
    """
    global _MyPubKey
    InitMyKey()
    # Makes a list but we just want a string
    Signature = _MyPubKey.keyObject.sign(inp, '')
    # so we take first element in list - need str cause was long    
    result = str(Signature[0]) 
    return result

def VerifySignature(pubkeystring, hashcode, signature):
    """
    Verify signature, this calls function ``Crypto.PublicKey.RSA.verify`` to verify.
    
    :param keystring: PublicKey in openssh format.
    :param hashcode: input data to verify, we use method ``Hash`` to prepare that. 
    :param signature: string with signature to verify.
    
    Return True if signature is correct, otherwise False. 
    """
    # key is public key in string format 
    keyobj = keys.Key.fromString(pubkeystring).keyObject
    # needs to be a long in a list
    sig_long = long(signature),
    Result = bool(keyobj.verify(hashcode, sig_long))
    return Result

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
    http://natmchugh.blogspot.co.uk/2014/10/how-i-created-two-images-with-same-md5.html
    """
    if hexdigest:
        return hashlib.md5(inp).hexdigest()
    return hashlib.md5(inp).digest()

def HashSHA(inp, hexdigest=False):
    """
    Use SHA1 method to calculate the hash of ``inp`` string. 
    """
    if hexdigest:
        return hashlib.sha1(inp).hexdigest()
    return hashlib.sha1(inp).digest()

def HashSHA512(inp, hexdigest=False):
    """
    """
    if hexdigest:
        return hashlib.sha512(inp).hexdigest()
    return hashlib.sha512(inp).digest()
    
def Hash(inp, hexdigest=False):
    """
    Core function to calculate hash of ``inp`` string, right now it uses MD5 method.
    """
    # return HashMD5(inp)
    return HashSHA(inp, hexdigest=hexdigest)

#------------------------------------------------------------------------------ 

def SessionKeyType():
    """
    Which crypto is used for session key.
    """
    # return "AES"
    return 'DES3'

def NewSessionKey():
    """
    Return really random string for making equivalent DES3 objects when needed.
    """
    # to work around bug in rsa.encrypt - do not want leading 0.          
    return chr(random.randint(1, 255)) + os.urandom(23)   

#------------------------------------------------------------------------------ 

def DecryptWithSessionKey(rand24, inp, session_key_type=SessionKeyType()):
    """
    Decrypt string with given session key.

    :param rand24: a session key comes with the message in encrypted form  
    :param inp: input string to encrypt 
    """
    if session_key_type == 'DES3':
        SessionKey = DES3.new(rand24)
        ret = SessionKey.decrypt(inp) 
    elif session_key_type == 'AES':
        # TODO: AES is not tested yet
        SessionKey = AES.new(rand24)
        ret = SessionKey.decrypt(inp)
    return ret

def EncryptWithSessionKey(session_key, inp, session_key_type=SessionKeyType()):
    """
    Encrypt input string with Session Key.
    
    :param session_key: randomly generated session key 
    :param inp: input string to encrypt 
    """
    if session_key_type == 'DES3':
        SessionKey = DES3.new(session_key)
        from lib import misc
        data = misc.RoundupString(inp, 24)
        ret = SessionKey.encrypt(data)
        del data
    elif session_key_type == 'AES':
        # TODO: AES is not tested yet
        SessionKey = AES.new(session_key)
        from lib import misc
        data = misc.RoundupString(inp, 24)
        ret = SessionKey.encrypt(data)
        del data
    elif session_key_type == 'Blowfish':
        # TODO: BlowFish is not done yet!
        SessionKey = Blowfish.new(session_key)
        ret = ''
    return ret

#------------------------------------------------------------------------------ 

def DecryptLocalPK(inp):
    """
    Decrypt ``inp`` string with your Private Key.
    We only decrypt with our local private key so no argument for that.
    """
    global _MyRsaKey
    InitMyKey()
    atuple = (inp,)
    padresult = _MyRsaKey.decrypt(atuple)
    # remove the "1" added in EncryptBinaryPK
    result = padresult[1:]                   
    return result

def EncryptLocalPK(inp):
    """
    This is just using local key, encrypt ``inp`` string.
    """
    global _MyPubKey
    InitMyKey()
    return EncryptBinaryPK(_MyPubKey, inp)

#------------------------------------------------------------------------------ 

def EncryptStringPK(publickeystring, inp):
    """
    Encrypt ``inp`` string with given Public Key.
    """
    keyobj = keys.Key.fromString(publickeystring)
    return EncryptBinaryPK(keyobj, inp)

def EncryptBinaryPK(publickey, inp):
    """
    Encrypt ``inp`` string using given Public Key in the ``publickey`` object.
    Return encrypted string.
    """
    # There is a bug in rsa.encrypt if there is a leading '\0' in the string.
    # Only think we encrypt is produced by NewSessionKey() which takes care not to have leading zero.
    # See   bug report in http://permalink.gmane.org/gmane.comp.python.cryptography.cvs/217
    # So we add a 1 in front.
    atuple = publickey.keyObject.encrypt('1'+inp, "")
    return atuple[0]                     

#------------------------------------------------------------------------------ 

def SpeedTest():
    """
    Some tests to check the performance.
    """
    import time
    import string
    import random
    dataSZ = 1024*640
    loops = 10
    packets = []
    dt = time.time()
    print 'encrypt %d pieces of %d bytes' % (loops, dataSZ)
    for i in range(loops):
        Data = os.urandom(dataSZ)
        SessionKey = NewSessionKey()
        EncryptedSessionKey = EncryptLocalPK(SessionKey)
        EncryptedData = EncryptWithSessionKey(SessionKey, Data)
        Signature = Sign(Hash(EncryptedData))
        packets.append((Data, len(Data), EncryptedSessionKey, EncryptedData, Signature))
        print '.',
    print time.time()-dt, 'seconds'
    
    dt = time.time()    
    print 'decrypt now'
    for Data, Length, EncryptedSessionKey, EncryptedData, Signature in packets:
        SessionKey = DecryptLocalPK(EncryptedSessionKey)
        paddedData = DecryptWithSessionKey(SessionKey, EncryptedData)
        newData = paddedData[:Length]
        if not VerifySignature(MyPublicKey(), Hash(EncryptedData), Signature):
            raise Exception()
        if newData != Data:
            raise Exception 
        print '.',
    print time.time()-dt, 'seconds'

#------------------------------------------------------------------------------ 


if __name__ == '__main__':
    bpio.init()
    lg.set_debug_level(18)
    settings.init()
    # from twisted.internet import reactor
    # settings.uconfig().set('backup.private-key-size', '3072')
    InitMyKey()
    SpeedTest()
    
     
