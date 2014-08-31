#!/usr/bin/python
#key.py
#
# <<<COPYRIGHT>>>
#
#
#

"""
.. module:: key

Here is a bunch of cryptography methods used in all parts of the software.
BitPie.NET uses PyCrypto library:
    https://www.dlitz.net/software/pycrypto/
For most of BitPie.NET code (outside ssh I think) we will only use ascii encoded string versions of keys.
Expect to make keys, signatures, and hashes all base64 strings soon.
Our local key is always on hand.
Main thing is to be able to use public keys in contacts to verify packets.
We never want to bother storing bad data, and need localtester to do local scrub.
"""

import os
import random
import hashlib

from Crypto.PublicKey import RSA
from Crypto.Cipher import DES3

import warnings
warnings.filterwarnings('ignore',category=DeprecationWarning)
from twisted.conch.ssh import keys

from logs import lg

from lib import bpio
from lib import settings

#------------------------------------------------------------------------------ 

# Global for this file
MyRsaKey = None 
# This will be an object
MyPublicKey = None

#------------------------------------------------------------------------------ 

def InitMyKey(keyfilename=None):
    """
    This is core method. 
    At first it check the Private Key in the memory, if it is already initialized it does nothing. 
    The local key are placed in the "[BitPie.NET data dir]/metadata/mykeyfile".
    If file "[BitPie.NET data dir]/metadata/mykeyfile_location" exists - 
    it should contain the location of the mykeyfile. Useful to store Private Key on the USB flash.
    BitPie.NET data dir is platform dependent:
        - Linux: ~/.bitpie
        - Windows XP: C:/Documents and Settings/[user]/.bitpie
        - Windows Vista, 7, 8: C:/Users/[user]/.bitpie
    Finally if target file exist - the Private Key will be loaded into memory.
    If file does not exist - the new key will be generated. 
    The size for new key will be taken from settings.  
    """
    global MyRsaKey
    global MyPublicKey
    if MyPublicKey is not None:
        return
    if MyRsaKey is not None:
        return
    if keyfilename is None:
        keyfilename = settings.KeyFileName()
    if os.path.exists(keyfilename+'_location'):
        newkeyfilename = bpio.ReadTextFile(keyfilename+'_location').strip()
        if os.path.exists(newkeyfilename):
            keyfilename = newkeyfilename
    if os.path.exists(keyfilename):
        lg.out(4, 'key.InitMyKey load private key from\n        %s' % keyfilename)
        MyPublicKey = keys.Key.fromFile(keyfilename)
        MyRsaKey = MyPublicKey.keyObject
    else:
        lg.out(4, 'key.InitMyKey generate new private key')
        MyRsaKey = RSA.generate(settings.getPrivateKeySize(), os.urandom)       
        MyPublicKey = keys.Key(MyRsaKey)
        keystring = MyPublicKey.toString('openssh')
        bpio.WriteFile(keyfilename, keystring)

def ForgetMyKey():
    """
    Remove Private Key from memory.
    """
    global MyPublicKey
    global MyRsaKey
    MyPublicKey = None
    MyRsaKey = None

def isMyMyPublicKeyReady():
    """
    Check if the Key is already loaded into memory.
    """
    global MyPublicKey
    return MyPublicKey is not None

def MyPublicKey():
    """
    Return Public part of the Key as openssh string.
    """
    global MyPublicKey
    InitMyKey()
    Result = MyPublicKey.public().toString('openssh')
    return Result

def MyPrivateKey():
    """
    Return Private part of the Key as openssh string.
    """
    global MyPublicKey
    InitMyKey()
    return MyPublicKey.toString('openssh')

def MyPublicKeyObject():
    """
    Return Public part of the Key as object, useful to convert to different formats.
    """
    global MyPublicKey
    InitMyKey()
    return MyPublicKey.public()

def MyPrivateKeyObject():
    """
    Return Private part of the Key as object.
    """
    global MyPublicKey
    InitMyKey()
    return MyPublicKey

def Sign(inp):
    """
    Sign some ``inp`` string with our Private Key, this calls PyCrypto method ``Crypto.PublicKey.RSA.sign``.
    """
    global MyPublicKey
    InitMyKey()
    # Makes a list but we just want a string
    Signature = MyPublicKey.keyObject.sign(inp, '')
    # so we take first element in list - need str cause was long    
    result = str(Signature[0]) 
    return result

def VerifySignature(keystring, hashcode, signature):
    """
    Verify signature, this calls function ``Crypto.PublicKey.RSA.verify`` to verify.
    
    :param keystring: PublicKey in openssh format.
    :param hashcode: input data to verify, we use method ``Hash`` to prepare that. 
    :param signature: string with signature to verify.
    
    Return True if signature is correct, otherwise False. 
    """
    # key is public key in string format 
    keyobj = keys.Key.fromString(keystring).keyObject
    # needs to be a long in a list
    sig_long = long(signature),
    Result = bool(keyobj.verify(hashcode, sig_long))
    return Result

def Verify(ConIdentity, hashcode, signature):
    """
    This takes Public Key from user identity and calls ``VerifySignature``.
     
    :param ConIdentity: user's identity object'.
    """
    key = ConIdentity.publickey
    Result = VerifySignature(key, hashcode, signature)
    return Result

def HashSHA(inp):
    """
    Use SHA1 method to calculate the hash of ``inp`` string. 
    """
    return hashlib.sha1(inp).digest()

def HashMD5(inp):
    """
    Use MD5 method to calculate the hash of ``inp`` string. 
    """
    return hashlib.md5(inp).digest()

def Hash(inp):
    """
    Core function to calculate hash of ``inp`` string, right now it uses MD5 method.
    """
    return HashMD5(inp)

def EncryptStringPK(publickeystring, inp):
    """
    Encrypt ``inp`` string with given Public Key.
    This will construct a temporary Public Key object in the memory from ``publickeystring``. 
    Outside of this file we just use the string version of the public keys.
    """
    keyobj = keys.Key.fromString(publickeystring)
    return EncryptBinaryPK(keyobj, inp)

def EncryptLocalPK(inp):
    """
    This is just using local key, encrypt ``inp`` string.
    """
    global MyPublicKey
    InitMyKey()
    return EncryptBinaryPK(MyPublicKey, inp)

def EncryptBinaryPK(publickey, inp):
    """
    Encrypt ``inp`` string using given Public Key in the ``publickey`` object.
    Return encrypted string.
    """
    # There is a bug in rsa.encrypt if there is a leading '\0' in the string.
    # Only think we encrypt is produced by NewSessionKey() which takes care not to have leading zero.
    # See   bug report in http://permalink.gmane.org/gmane.comp.python.cryptography.cvs/217
    # So we add a 1 in front.
    atuple = publickey.keyObject.encrypt("1"+inp,"")
    return atuple[0]                     

def DecryptLocalPK(inp):
    """
    Decrypt ``inp`` string with your Private Key.
    We only decrypt with our local private key so no argument for that.
    """
    global MyRsaKey
    global MyPublicKey
    InitMyKey()
    atuple = (inp,)
    padresult = MyRsaKey.decrypt(atuple)
    # remove the "1" added in EncryptBinaryPK
    result = padresult[1:]                   
    return result

def SessionKeyType():
    """
    Which crypto is used for session key.
    """
    return "DES3"

def NewSessionKey():
    """
    Return really random string for making equivalent DES3 objects when needed.
    """
    # to work around bug in rsa.encrypt - do not want leading 0.          
    return chr(random.randint(1, 255)) + os.urandom(23)   

def RoundupString(data, stepsize):
    """
    """
    size = len(data)
    mod = size % stepsize
    increase = 0
    addon = ''
    if mod > 0:
        increase = stepsize - mod
        addon = ' ' * increase
    return data + addon

def EncryptWithSessionKey(rand24, inp):
    """
    Encrypt input string with Session Key.
    
    :param rand24: randomly generated session key 
    :param inp: input string to encrypt 
    """
    SessionKey = DES3.new(rand24)
    data = RoundupString(inp, 24)
    ret = SessionKey.encrypt(data)
    del data
    return ret

def DecryptWithSessionKey(rand24, inp):
    """
    Decrypt string with given session key.
    """
    SessionKey = DES3.new(rand24)
    return SessionKey.decrypt(inp)

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
    
     
