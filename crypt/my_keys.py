#!/usr/bin/python
# my_keys.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (my_keys.py) is part of BitDust Software.
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
.. module:: my_keys.

"""


#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys

from twisted.conch.ssh import keys

from Crypto.PublicKey import RSA

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

from crypt import key

from userid import my_id
from userid import global_id

#------------------------------------------------------------------------------

_KnownKeys = {}

#------------------------------------------------------------------------------

def init():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.init')
    load_local_keys()


def shutdown():
    """
    """
    lg.out(4, 'my_keys.shutdown')
    known_keys().clear()

#------------------------------------------------------------------------------

def known_keys():
    """
    """
    global _KnownKeys
    return _KnownKeys

#------------------------------------------------------------------------------

def make_key_id(alias, creator_idurl=None, output_format=None):
    """
    Every key has a creator, and we include his IDURL in the final key_id string.
    Here is a global unique address to a remote copy of `cat.png` file:

        group_abc$alice@first-machine.com:animals/cat.png#F20160313043757PM

    key_id here is:

        group_abc$alice@first-machine.com

    key alias is `group_abc` and creator IDURL is:

        http://first-machine.com/alice.xml

    By knowing full key_id we can find and connect to the correct node(s)
    who is supporting that resource.
    """
    if creator_idurl is None:
        creator_idurl = my_id.getLocalID()
    return global_id.MakeGlobalID(
        idurl=creator_idurl,
        key_alias=alias,
        output_format=output_format,
    )

def split_key_id(key_id):
    """
    Return "alias" and "creator" IDURL of that key as a tuple object.
    For example from input string:

        "secret_key_xyz$bob@remote-server.net"

    output will be like that:

        "secret_key_xyz", "http://remote-server.net/bob.xml"
    """
    parts = global_id.ParseGlobalID(key_id)
    if not parts['key_id'] or not parts['idurl']:
        return None, None
    return parts['key_id'], parts['idurl']

def is_valid_key_id(key_id):
    """
    """
    parts = global_id.ParseGlobalID(key_id)
    if not parts['key_id']:
        lg.warn('no key_id found')
        return False
    if not parts['idurl']:
        lg.warn('no idurl found')
        return False
    if len(parts['key_id']) > settings.MaximumUsernameLength():
        lg.warn("key_id: %s" % parts['key_id'])
        return False
    if len(parts['key_id']) < settings.MinimumUsernameLength():
        lg.warn("key_id: %s" % parts['key_id'])
        return False
    for c in parts['key_id']:
        if c not in settings.LegalUsernameChars():
            lg.warn("key_id: %s" % parts['key_id'])
            return False
    return True

#------------------------------------------------------------------------------

def load_local_keys(keys_folder=None):
    """
    """
    if not keys_folder:
        keys_folder = settings.PrivateKeysDir()
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.load_local_keys will read files from %s' % keys_folder)
    known_keys().clear()
    count = 0
    for key_id in os.listdir(keys_folder):
        key_filepath = os.path.join(keys_folder, key_id)
        try:
            key_object = keys.Key.fromFile(key_filepath)
        except:
            lg.exc()
            continue
        if not validate_key(key_object):
            lg.warn('validation failed for %s key' % key_id)
            continue
        known_keys()[key_id] = key_object
        count += 1
    if _Debug:
        lg.out(_DebugLevel, '    %d keys loaded' % count)


def save_keys_local(keys_folder=None, output_type='openssh'):
    """
    """
    if not keys_folder:
        keys_folder = settings.PrivateKeysDir()
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.save_keys_local will store all known keys in %s' % keys_folder)
    count = 0
    for key_id, key_object in known_keys().items():
        key_string = key_object.toString(output_type)
        key_filepath = os.path.join(keys_folder, key_id)
        bpio.WriteFile(key_filepath, key_string)
        count += 1
    if _Debug:
        lg.out(_DebugLevel, '    %d keys saved' % count)

#------------------------------------------------------------------------------

def generate_key(key_id, key_size=4096, keys_folder=None, output_type='openssh'):
    """
    """
    if key_id in known_keys():
        lg.warn('key %s already exists' % key_id)
        return None
    lg.out(4, 'my_keys.generate_key %s of %d bits' % (key_id, key_size))
    rsa_key = RSA.generate(key_size, os.urandom)
    key_object = keys.Key(rsa_key)
    known_keys()[key_id] = key_object
    if not keys_folder:
        keys_folder = settings.PrivateKeysDir()
    key_string = key_object.toString(output_type)
    key_filepath = os.path.join(keys_folder, key_id)
    bpio.WriteFile(key_filepath, key_string)
    if _Debug:
        lg.out(_DebugLevel, '    key %s saved to %s' % (key_id, key_filepath))
    return key_object


def register_key(key_id, openssh_input_string, keys_folder=None, output_type='openssh'):
    """
    """
    if key_id in known_keys():
        lg.warn('key %s already exists' % key_id)
        return None
    key_object = unserialize_key_to_object(openssh_input_string)
    if not key_object:
        lg.warn('invalid openssh string, unserialize_key_to_object() failed')
        return None
    lg.out(4, 'my_keys.register_key %s from %d bytes openssh_input_string' % (key_id, len(openssh_input_string)))
    known_keys()[key_id] = key_object
    if not keys_folder:
        keys_folder = settings.PrivateKeysDir()
    key_string = key_object.toString(output_type)
    key_filepath = os.path.join(keys_folder, key_id)
    bpio.WriteFile(key_filepath, key_string)
    if _Debug:
        lg.out(_DebugLevel, '    key %s saved to %s' % (key_id, key_filepath))
    return key_object


def erase_key(key_id, keys_folder=None):
    """
    """
    if key_id not in known_keys():
        lg.warn('key %s is not found' % key_id)
        return False
    if not keys_folder:
        keys_folder = settings.PrivateKeysDir()
    key_filepath = os.path.join(keys_folder, key_id)
    try:
        os.remove(key_filepath)
    except:
        lg.exc()
        return False
    known_keys().pop(key_id)
    return True


def validate_key(key_object):
    """
    """
    data256 = os.urandom(256)
    signature256 = key_object.keyObject.sign(data256, '')
    return key_object.keyObject.verify(data256, signature256)

#------------------------------------------------------------------------------

def sign(key_id, inp):
    """
    Sign some ``inp`` string with given key.
    This will call PyCrypto method ``Crypto.PublicKey.RSA.sign``.
    """
    key_object = known_keys().get(key_id)
    if not key_object:
        lg.warn('key %s is unknown' % key_id)
        return None
    signature = key_object.keyObject.sign(inp, '')
    result = str(signature[0])
    return result


def verify(key_id, hashcode, signature):
    """
    Verify signature, this calls function ``Crypto.PublicKey.RSA.verify`` to verify.

    :param key_id: private key id to be used
    :param hashcode: input data to verify, we use method ``Hash`` to prepare that.
    :param signature: string with signature to verify.

    Return True if signature is correct, otherwise False.
    """
    key_object = known_keys().get(key_id)
    if not key_object:
        lg.warn('key %s is unknown' % key_id)
        return False
    sig_long = long(signature),
    result = key_object.keyObject.verify(hashcode, sig_long)
    return bool(result)

#------------------------------------------------------------------------------

def encrypt(key_id, inp):
    """
    Encrypt ``inp`` string using given private key ID.

    :param key_id: private key id to be used
    :param inp: raw input string to be encrypted

    Return encrypted string.
    """
    if key_id == 'master':
        return key.EncryptLocalPublicKey(inp)
    key_object = known_keys().get(key_id)
    if not key_object:
        lg.warn('key %s is unknown' % key_id)
        return None
    # There is a bug in rsa.encrypt if there is a leading '\0' in the string.
    # See bug report in http://permalink.gmane.org/gmane.comp.python.cryptography.cvs/217
    # So we add a "1" in front now and in decrypt() we will remove it
    atuple = key_object.keyObject.encrypt('1' + inp, "")
    return atuple[0]


def decrypt(key_id, inp):
    """
    Decrypt ``inp`` string with given private key.

    :param key_id: private key id to be used
    :param inp: input string with encrypted data

    Return decrypted string or raise exception.
    """
    if key_id == 'master':
        return key.DecryptLocalPrivateKey(inp)
    key_object = known_keys().get(key_id)
    if not key_object:
        lg.warn('key %s is unknown' % key_id)
        return None
    atuple = (inp,)
    padresult = key_object.keyObject.decrypt(atuple)
    # remove the "1" added in encrypt() method
    return padresult[1:]

#------------------------------------------------------------------------------

def serialize_key(key_id, output_type='openssh'):
    """
    """
    key_object = known_keys().get(key_id)
    if not key_object:
        lg.warn('key %s is unknown' % key_id)
        return None
    return key_object.toString(output_type)


def unserialize_key_to_object(openssh_string):
    """
    """
    try:
        key_object = keys.Key.fromString(openssh_string)
    except:
        lg.exc()
        return None
    return key_object
