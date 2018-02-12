#!/usr/bin/python
# my_keys.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

def key_obj(key_id=None):
    """
    Alias.
    """
    if not key_id:
        return known_keys()
    if key_id not in known_keys():
        raise Exception('key not found')
    return known_keys().get(key_id)


def known_keys():
    """
    """
    global _KnownKeys
    return _KnownKeys

#------------------------------------------------------------------------------

def is_key_registered(key_id, include_master=True):
    """
    Returns True if this key is known.
    """
    if include_master and key_id == global_id.MakeGlobalID(idurl=my_id.getLocalID(), key_alias='master'):
        return True
    return key_id in known_keys()


def is_key_private(key_id):
    if not is_key_registered(key_id):
        return False
    return not key_obj(key_id).isPublic()


def make_key_id(alias, creator_idurl=None, creator_glob_id=None, output_format=None):
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
    if not alias:
        alias = 'master'
    if creator_glob_id is not None:
        return global_id.MakeGlobalID(
            customer=creator_glob_id,
            key_alias=alias,
        )
    if creator_idurl is None:
        creator_idurl = my_id.getLocalID()
    return global_id.MakeGlobalID(
        idurl=creator_idurl,
        key_alias=alias,
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
    if not parts['key_alias'] or not parts['idurl']:
        return None, None
    return parts['key_alias'], parts['idurl']

def is_valid_key_id(global_key_id):
    """
    """
    parts = global_id.ParseGlobalID(global_key_id)
    if not parts['key_alias']:
        lg.warn('no key_alias found in the input')
        return False
    if not parts['idurl']:
        lg.warn('no idurl found in the input')
        return False
    key_alias = parts['key_alias']
    if len(key_alias) > settings.MaximumUsernameLength():
        lg.warn("key_alias too long: %d" % len(key_alias))
        return False
    if len(key_alias) < settings.MinimumUsernameLength():
        lg.warn("key_alias too short: %d" % len(key_alias))
        return False
    pos = 0
    for c in key_alias:
        if c not in settings.LegalUsernameChars():
            lg.warn("key_alias has illegal character at position: %d" % pos)
            return False
        pos += 1
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
    for key_filename in os.listdir(keys_folder):
        key_filepath = os.path.join(keys_folder, key_filename)
        try:
            key_object = keys.Key.fromFile(key_filepath)
        except:
            lg.exc()
            continue
        if not validate_key(key_object):
            lg.warn('validation failed for %s' % key_filepath)
            continue
        key_id = key_filename.replace('.private', '').replace('.public', '')
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
        if key_object.isPublic():
            key_filepath = os.path.join(keys_folder, key_id + '.public')
        else:
            key_filepath = os.path.join(keys_folder, key_id + '.private')
        key_string = key_object.toString(output_type)
        bpio.WriteFile(key_filepath, key_string)
        count += 1
    if _Debug:
        lg.out(_DebugLevel, '    %d keys saved' % count)

#------------------------------------------------------------------------------

def generate_key(key_id, key_size=4096, keys_folder=None, output_type='openssh'):
    """
    """
    if key_id in known_keys():
        lg.warn('key "%s" already exists' % key_id)
        return None
    lg.out(4, 'my_keys.generate_key "%s" of %d bits' % (key_id, key_size))
    rsa_key = RSA.generate(key_size, os.urandom)
    key_object = keys.Key(rsa_key)
    known_keys()[key_id] = key_object
    if not keys_folder:
        keys_folder = settings.PrivateKeysDir()
    key_string = key_object.toString(output_type)
    if key_object.isPublic():
        key_filepath = os.path.join(keys_folder, key_id + '.public')
    else:
        key_filepath = os.path.join(keys_folder, key_id + '.private')
    bpio.WriteFile(key_filepath, key_string)
    if _Debug:
        lg.out(_DebugLevel, '    key %s generated, saved to %s' % (key_id, key_filepath))
    return key_object


def register_key(key_id, key_object_or_openssh, keys_folder=None, output_type='openssh'):
    """
    """
    if key_id in known_keys():
        lg.warn('key %s already exists' % key_id)
        return None
    if isinstance(key_object_or_openssh, str):
        lg.out(4, 'my_keys.register_key %s from %d bytes openssh_input_string' % (key_id, len(key_object_or_openssh)))
        key_object = unserialize_key_to_object(key_object_or_openssh)
        if not key_object:
            lg.warn('invalid openssh string, unserialize_key_to_object() failed')
            return None
    else:
        lg.out(4, 'my_keys.register_key %s from object' % key_id)
        key_object = key_object_or_openssh
    known_keys()[key_id] = key_object
    if not keys_folder:
        keys_folder = settings.PrivateKeysDir()
    key_string = key_object.toString(output_type)
    if key_object.isPublic():
        key_filepath = os.path.join(keys_folder, key_id + '.public')
    else:
        key_filepath = os.path.join(keys_folder, key_id + '.private')
    bpio.WriteFile(key_filepath, key_string)
    if _Debug:
        lg.out(_DebugLevel, '    key %s added, saved to %s' % (key_id, key_filepath))
    return key_filepath


def erase_key(key_id, keys_folder=None):
    """
    """
    if key_id not in known_keys():
        lg.warn('key %s is not found' % key_id)
        return False
    if not keys_folder:
        keys_folder = settings.PrivateKeysDir()
    if key_obj(key_id).isPublic():
        key_filepath = os.path.join(keys_folder, key_id + '.public')
    else:
        key_filepath = os.path.join(keys_folder, key_id + '.private')
    try:
        os.remove(key_filepath)
    except:
        lg.exc()
        return False
    known_keys().pop(key_id)
    if _Debug:
        lg.out(_DebugLevel, '    key %s removed, file %s deleted' % (key_id, key_filepath))
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
    if key_id == 'master$%s' % my_id.getGlobalID():
        return key.EncryptLocalPublicKey(inp)
    if key_id == my_id.getGlobalID():
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
    if key_id == 'master$%s' % my_id.getGlobalID():
        return key.DecryptLocalPrivateKey(inp)
    if key_id == my_id.getGlobalID():
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

#------------------------------------------------------------------------------

def get_public_key_raw(key_id, type_format='openssh'):
    return key(key_id).public().toString(type_format)


def get_private_key_raw(key_id, type_format='openssh'):
    return key(key_id).toString(type_format)

#------------------------------------------------------------------------------

def make_master_key_info(include_private=False):
    r = {
        'key_id': my_id.getGlobalID(key_alias='master'),
        'alias': 'master',
        'creator': my_id.getLocalID(),
        'is_public': key.MyPrivateKeyObject().isPublic(),
        'fingerprint': str(key.MyPrivateKeyObject().fingerprint()),
        'type': str(key.MyPrivateKeyObject().type()),
        'ssh_type': str(key.MyPrivateKeyObject().sshType()),
        'size': str(key.MyPrivateKeyObject().size()),
        'public': str(key.MyPrivateKeyObject().public().toString('openssh')),
        'include_private': include_private,
    }
    r['private'] = None
    if include_private:
        r['private'] = str(key.MyPrivateKeyObject().toString('openssh'))
    return r


def make_key_info(key_object, key_id=None, key_alias=None, creator_idurl=None, include_private=False):
    if key_id:
        key_alias, creator_idurl = split_key_id(key_id)
    else:
        key_id = make_key_id(alias=key_alias, creator_idurl=creator_idurl)
    r = {
        'key_id': key_id,
        'alias': key_alias,
        'creator': creator_idurl,
        'is_public': key_object.isPublic(),
        'fingerprint': str(key_object.fingerprint()),
        'type': str(key_object.type()),
        'ssh_type': str(key_object.sshType()),
        'size': str(key_object.size()),
        'include_private': include_private,
    }
    r['private'] = None
    if key_object.isPublic():
        r['public'] = str(key_object.toString('openssh'))
    else:
        r['public'] = str(key_object.public().toString('openssh'))
        if include_private:
            r['private'] = str(key_object.toString('openssh'))
    return r


def get_key_info(key_id, include_private=False):
    """
    Returns dictionary with full key info or raise an Exception.
    """
    key_id = str(key_id)
    if key_id == 'master':
        return make_master_key_info(include_private=include_private)
    key_alias, creator_idurl = split_key_id(key_id)
    if not key_alias or not creator_idurl:
        raise Exception('icorrect key_id format')
    key_object = known_keys().get(key_id)
    if not key_object:
        key_id_form_1 = make_key_id(
            alias=key_alias,
            creator_idurl=creator_idurl,
            output_format=global_id._FORMAT_GLOBAL_ID_KEY_USER,
        )
        key_id_form_2 = make_key_id(
            alias=key_alias,
            creator_idurl=creator_idurl,
            output_format=global_id._FORMAT_GLOBAL_ID_USER_KEY,
        )
        key_object = known_keys().get(key_id_form_1)
        if key_object:
            key_id = key_id_form_1
        else:
            key_object = known_keys().get(key_id_form_2)
            if key_object:
                key_id = key_id_form_2
    if not key_object:
        raise Exception('key not found')
    return make_key_info(key_object, key_id=key_id, include_private=include_private, )


def read_key_info(key_json):
    try:
        key_id = str(key_json['key_id'])
        include_private = bool(key_json['include_private'])
        if include_private:
            raw_openssh_string = str(key_json['private'])
        else:
            raw_openssh_string = str(key_json['public'])
        key_object = unserialize_key_to_object(raw_openssh_string)
        if not key_object:
            raise Exception('unserialize failed')
    except:
        lg.exc()
        raise Exception('failed reading key info')
    return key_id, key_object

#------------------------------------------------------------------------------
