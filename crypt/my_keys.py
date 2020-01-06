#!/usr/bin/python
# my_keys.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys
import gc
import base64

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from lib import misc
from lib import strng
from lib import jsn
from lib import utime

from system import local_fs

from main import settings
from main import events

from crypt import key
from crypt import rsa_key
from crypt import hashes

from userid import my_id
from userid import global_id
from userid import id_url

#------------------------------------------------------------------------------

_KnownKeys = {}

#------------------------------------------------------------------------------

def init():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.init')
    scan_local_keys()


def shutdown():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.shutdown')
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
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    return known_keys()[key_id]


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
    if include_master and (key_id == my_id.getGlobalID(key_alias='master') or key_id == 'master'):
        return True
    return key_id in known_keys()


def is_key_private(key_id, include_master=True):
    """
    """
    if not is_key_registered(key_id):
        return False
    if include_master and (key_id == my_id.getGlobalID(key_alias='master') or key_id == 'master'):
        return True
    return not key_obj(key_id).isPublic()


def make_key_id(alias, creator_idurl=None, creator_glob_id=None):
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
    return parts['key_alias'], id_url.field(parts['idurl'])

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
    if not misc.ValidKeyAlias(parts['key_alias']):
        lg.warn('invalid key alias in the input')
        return False
    return True


def latest_key_id(key_id):
    """
    Create IDURL object from input key_id and return new key_id (with same key_alias) from that IDURL object.
    This way you can be sure that given key_id is pointing to the correct owner IDURL.
    """
    if not key_id:
        return key_id
    if key_id == 'master':
        return my_id.getGlobalID(key_alias='master')
    glob_id = global_id.ParseGlobalID(key_id, as_field=True)
    if not glob_id['idurl']:
        lg.err('invalid key_id: %r' % key_id)
        return key_id
    return global_id.MakeGlobalID(
        idurl=glob_id['idurl'].to_bin(),
        key_alias=glob_id['key_alias'],
    )

#------------------------------------------------------------------------------

def scan_local_keys(keys_folder=None):
    """
    """
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.scan_local_keys will read files from %s' % keys_folder)
    known_keys().clear()
    count = 0
    for key_filename in os.listdir(keys_folder):
        key_id = key_filename.replace('.private', '').replace('.public', '')
        if not is_valid_key_id(key_id):
            lg.warn('key_id is not valid: %s' % key_id)
            continue
        known_keys()[key_id] = None
        count += 1
    if _Debug:
        lg.out(_DebugLevel, '    %d keys found' % count)


def load_key(key_id, keys_folder=None):
    """
    """
    if not is_valid_key_id(key_id):
        lg.warn('key_id is not valid: %s' % key_id)
        return False
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    key_filepath = os.path.join(keys_folder, '%s.private' % key_id)
    is_private = True
    if not os.path.exists(key_filepath):
        key_filepath = os.path.join(keys_folder, '%s.public' % key_id)
        is_private = False
    key_raw = local_fs.ReadTextFile(key_filepath)
    if not key_raw:
        lg.warn('failed reading key from %r' % key_filepath)
        return False
    key_raw_strip = key_raw.strip()
    need_to_convert = False
    try:
        if key_raw_strip.startswith('{') and key_raw_strip.endswith('}'):
            key_dict = jsn.loads_text(key_raw_strip)
        else:
            key_dict = {
                'label': key_id,
                'body': key_raw_strip,
            }
            need_to_convert = True
    except:
        lg.exc()
        return False
    try:
        key_object = rsa_key.RSAKey()
        key_object.fromDict(key_dict)
    except:
        lg.exc()
        return False
    if not key_object.isPublic():
        if not validate_key(key_object):
            lg.warn('validation failed for %s' % key_filepath)
            return False
    known_keys()[key_id] = key_object
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.load_key %r  label=%r  is_private=%r  from %s' % (
            key_id, key_object.label, is_private, keys_folder, ))
    if need_to_convert:
        save_key(key_id, keys_folder=keys_folder)
        lg.info('key %r format converted to JSON' % key_id)
    return True


def load_local_keys(keys_folder=None):
    """
    """
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.load_local_keys will read files from %s' % keys_folder)
    known_keys().clear()
    count = 0
    for key_filename in os.listdir(keys_folder):
        key_filepath = os.path.join(keys_folder, key_filename)
        key_id = key_filename.replace('.private', '').replace('.public', '')
        if not is_valid_key_id(key_id):
            lg.warn('key_id is not valid: %s' % key_id)
            continue
        key_raw = local_fs.ReadTextFile(key_filepath)
        if not key_raw:
            lg.warn('failed reading key from %r' % key_filepath)
            continue
        key_raw_strip = key_raw.strip()
        try:
            if key_raw_strip.startswith('{') and key_raw_strip.endswith('}'):
                key_dict = jsn.loads_text(key_raw_strip)
            else:
                key_dict = {
                    'label': key_id,
                    'body': key_raw_strip,
                }
        except:
            lg.exc()
            continue
        try:
            key_object = rsa_key.RSAKey()
            key_object.fromDict(key_dict)
        except:
            lg.exc()
            continue
        if not key_object.isPublic():
            if not validate_key(key_object):
                lg.warn('validation failed for %s' % key_filepath)
                continue
        known_keys()[key_id] = key_object
        count += 1
    if _Debug:
        lg.out(_DebugLevel, '    %d keys loaded' % count)
    return count


def save_key(key_id, keys_folder=None):
    """
    """
    key_object = known_keys()[key_id]
    if key_object is None:
        lg.warn('can not save key %s because it is not loaded yet' % key_id)
        return False
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if key_object.isPublic():
        key_filepath = os.path.join(keys_folder, key_id + '.public')
        key_dict = key_object.toDict(include_private=False)
        key_string = jsn.dumps(key_dict, indent=1, separators=(',', ':'))
    else:
        key_filepath = os.path.join(keys_folder, key_id + '.private')
        key_dict = key_object.toDict(include_private=True)
        key_string = jsn.dumps(key_dict, indent=1, separators=(',', ':'))
    if not bpio.WriteTextFile(key_filepath, key_string):
        lg.warn('failed saving key %r to %r' % (key_id, key_filepath, ))
        return False
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.save_key stored key %r locally in %r' % (key_id, key_filepath, ))
    return True


def save_keys_local(keys_folder=None):
    """
    """
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.save_keys_local will store all known keys in %s' % keys_folder)
    count = 0
    for key_id in known_keys().keys():
        if save_key(key_id, keys_folder=keys_folder):
            count += 1
    if _Debug:
        lg.out(_DebugLevel, '    %d keys saved' % count)
    return count

#------------------------------------------------------------------------------

def generate_key(key_id, label='', key_size=4096, keys_folder=None):
    """
    """
    if key_id in known_keys():
        lg.warn('key "%s" already exists' % key_id)
        return None
    if not label:
        label = 'key%s' % utime.make_timestamp() 
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.generate_key "%s" of %d bits, label=%r' % (key_id, key_size, label))
    key_object = rsa_key.RSAKey()
    key_object.generate(key_size)
    key_object.label = label
    known_keys()[key_id] = key_object
    if _Debug:
        lg.out(_DebugLevel, '    key %s generated' % key_id)
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    save_key(key_id, keys_folder=keys_folder)
    events.send('key-generated', data=dict(key_id=key_id, label=label, key_size=key_size, ))
    return key_object


def register_key(key_id, key_object_or_string, label='', keys_folder=None):
    """
    """
    if key_id in known_keys():
        lg.warn('key %s already exists' % key_id)
        return None
    if not label:
        label = 'key%s' % utime.make_timestamp() 
    if strng.is_string(key_object_or_string):
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.register_key %s from %d bytes openssh_input_string' % (
                key_id, len(key_object_or_string)))
        key_object = unserialize_key_to_object(key_object_or_string)
        if not key_object:
            lg.warn('invalid openssh string, unserialize_key_to_object() failed')
            return None
    else:
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.register_key %s from object' % key_id)
        key_object = key_object_or_string
    known_keys()[key_id] = key_object
    if _Debug:
        lg.out(_DebugLevel, '    key %s added' % key_id)
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    save_key(key_id, keys_folder=keys_folder)
    events.send('key-registered', data=dict(key_id=key_id, label=label, key_size=key_object.size(), ))
    return key_object


def erase_key(key_id, keys_folder=None):
    """
    """
    if key_id not in known_keys():
        lg.warn('key %s is not found' % key_id)
        return False
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if key_obj(key_id).isPublic():
        key_filepath = os.path.join(keys_folder, key_id + '.public')
        is_private = False
    else:
        key_filepath = os.path.join(keys_folder, key_id + '.private')
        is_private = True
    try:
        os.remove(key_filepath)
    except:
        lg.exc()
        return False
    known_keys().pop(key_id)
    gc.collect()
    if _Debug:
        lg.out(_DebugLevel, '    key %s removed, file %s deleted' % (key_id, key_filepath))
    events.send('key-erased', data=dict(key_id=key_id, is_private=is_private))
    return True


def validate_key(key_object):
    """
    """
    sample_data = strng.to_bin(base64.b64encode(os.urandom(256)))
    sample_hash_base = hashes.sha1(sample_data, hexdigest=True)
    sample_signature = key_object.sign(sample_hash_base)
    is_valid = key_object.verify(sample_signature, sample_hash_base)
    if not is_valid:
        if _Debug:
            lg.err('validate_key FAILED')
            lg.out(_DebugLevel, 'pubkey=%r' % key_object.toPublicString())
            lg.out(_DebugLevel, 'signature=%r' % sample_signature)
            lg.out(_DebugLevel, 'hash_base=%r' % sample_hash_base)
            lg.out(_DebugLevel, 'data=%r' % sample_data)
    return is_valid


def rename_key(current_key_id, new_key_id, keys_folder=None):
    """
    """
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if current_key_id not in known_keys():
        lg.warn('key %s is not found' % current_key_id)
        return False
    if key_obj(current_key_id).isPublic():
        current_key_filepath = os.path.join(keys_folder, current_key_id + '.public')
        new_key_filepath = os.path.join(keys_folder, new_key_id + '.public')
        is_private = False
    else:
        current_key_filepath = os.path.join(keys_folder, current_key_id + '.private')
        new_key_filepath = os.path.join(keys_folder, new_key_id + '.private')
        is_private = True
    try:
        os.rename(current_key_filepath, new_key_filepath)
    except:
        lg.exc()
        return False
    key_object = known_keys().pop(current_key_id)
    known_keys()[new_key_id] = key_object
    gc.collect()
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.rename_key   key %s renamed to %s' % (current_key_id, new_key_id, ))
        lg.out(_DebugLevel, '    file %s renamed to %s' % (current_key_filepath, new_key_filepath, ))
    events.send('key-renamed', data=dict(old_key_id=current_key_id, new_key_id=new_key_id, is_private=is_private))
    return True

#------------------------------------------------------------------------------

def sign(key_id, inp):
    """
    Sign some ``inp`` string with given key.
    This will call PyCrypto method ``Crypto.PublicKey.RSA.sign``.
    Returns byte string.
    """
    key_id = latest_key_id(key_id)
    if key_id not in known_keys():
        raise Exception('key %s is unknown' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    result = key_object.sign(inp)
    return result


def verify(key_id, hashcode, signature):
    """
    Verify signature, this calls function ``Crypto.PublicKey.RSA.verify`` to verify.

    :param key_id: private key id to be used
    :param hashcode: input data to verify, we use method ``Hash`` to prepare that.
    :param signature: string with signature to verify.

    Return True if signature is correct, otherwise False.
    """
    key_id = latest_key_id(key_id)
    if key_id not in known_keys():
        raise Exception('key %s is unknown' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    result = key_object.verify(signature, hashcode)
    return result

#------------------------------------------------------------------------------

def encrypt(key_id, inp):
    """
    Encrypt ``inp`` string using given private key ID.

    :param key_id: private key id to be used
    :param inp: raw binary input string to be encrypted

    Return encrypted string.
    """
    if key_id == 'master':  # master
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.encrypt  payload of %d bytes using my master key' % len(inp))
        return key.EncryptLocalPublicKey(inp)
    key_id = latest_key_id(key_id)
    if key_id == my_id.getGlobalID(key_alias='master'):  # master$user@host.org
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.encrypt  payload of %d bytes using my master key' % len(inp))
        return key.EncryptLocalPublicKey(inp)
    if key_id == my_id.getGlobalID():  # user@host.org
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.encrypt  payload of %d bytes using my master key' % len(inp))
        return key.EncryptLocalPublicKey(inp)
    if key_id not in known_keys():
        raise Exception('key %s is unknown' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.encrypt  payload of %d bytes with key %s' % (len(inp), key_id, ))
    result = key_object.encrypt(inp)
    return result


def decrypt(key_id, inp):
    """
    Decrypt ``inp`` string with given private key.

    :param key_id: private key id to be used
    :param inp: input string with encrypted data

    Return decrypted string or raise exception.
    """
    if key_id == 'master':  # master
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.decrypt  payload of %d bytes using my master key' % len(inp))
        return key.DecryptLocalPrivateKey(inp)
    key_id = latest_key_id(key_id)
    if key_id == my_id.getGlobalID(key_alias='master'):  # master$user@host.org
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.decrypt  payload of %d bytes using my master key' % len(inp))
        return key.DecryptLocalPrivateKey(inp)
    if key_id == my_id.getGlobalID():  # user@host.org
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.decrypt  payload of %d bytes using my master key' % len(inp))
        return key.DecryptLocalPrivateKey(inp)
    if key_id not in known_keys():
        raise Exception('key %s is unknown' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.decrypt  payload of %d bytes with key %s' % (len(inp), key_id, ))
    result = key_object.decrypt(inp)
    return result

#------------------------------------------------------------------------------

def serialize_key(key_id):
    """
    """
    key_id = latest_key_id(key_id)
    if key_id not in known_keys():
        raise Exception('key %s is unknown' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    return key_object.toPrivateString()


def unserialize_key_to_object(raw_string):
    """
    """
    try:
        key_object = rsa_key.RSAKey()
        key_object.fromString(raw_string)
    except:
        lg.exc()
        return None
    return key_object

#------------------------------------------------------------------------------

def get_public_key_raw(key_id):
    kobj = key_obj(key_id)
    return kobj.toPublicString()


def get_private_key_raw(key_id):
    kobj = key_obj(key_id)
    if kobj.isPublic():
        raise ValueError('not a private key')
    return kobj.toPrivateString()

#------------------------------------------------------------------------------

def make_master_key_info(include_private=False):
    r = {
        'key_id': my_id.getGlobalID(key_alias='master'),
        'alias': 'master',
        'label': my_id.getGlobalID(key_alias='master'),
        'creator': my_id.getLocalID(),
        'is_public': key.MyPrivateKeyObject().isPublic(),
        # 'fingerprint': str(key.MyPrivateKeyObject().fingerprint()),
        # 'type': str(key.MyPrivateKeyObject().type()),
        # 'ssh_type': str(key.MyPrivateKeyObject().sshType()),
        'public': str(key.MyPrivateKeyObject().toPublicString()),
        'include_private': include_private,
    }
    r['private'] = None
    if include_private:
        r['private'] = str(key.MyPrivateKeyObject().toPrivateString())
    if hasattr(key.MyPrivateKeyObject(), 'size'):
        r['size'] = str(key.MyPrivateKeyObject().size())
    else:
        r['size'] = '0'
    return r


def make_key_info(key_object, key_id=None, key_alias=None, creator_idurl=None, include_private=False):
    if key_id:
        key_id = latest_key_id(key_id)
        key_alias, creator_idurl = split_key_id(key_id)
    else:
        key_id = make_key_id(alias=key_alias, creator_idurl=id_url.field(creator_idurl))
    r = {
        'key_id': key_id,
        'alias': key_alias,
        'label': key_object.label,
        'creator': creator_idurl,
        'is_public': key_object.isPublic(),
        # 'fingerprint': str(key_object.fingerprint()),
        # 'type': str(key_object.type()),
        # 'ssh_type': str(key_object.sshType()),
        'include_private': include_private,
    }
    r['private'] = None
    if key_object.isPublic():
        r['public'] = str(key_object.toPublicString())
        if include_private:
            raise Exception('this key contains only public component')
    else:
        r['public'] = str(key_object.toPublicString())
        if include_private:
            r['private'] = str(key_object.toPrivateString())
    if hasattr(key_object, 'size'):
        r['size'] = str(key_object.size())
    else:
        r['size'] = '0'
    return r


def get_key_info(key_id, include_private=False):
    """
    Returns dictionary with full key info or raise an Exception.
    """
    key_id = latest_key_id(strng.to_text(key_id))
    if key_id == 'master' or key_id == my_id.getGlobalID(key_alias='master') or key_id == my_id.getGlobalID():
        return make_master_key_info(include_private=include_private)
    key_alias, creator_idurl = split_key_id(key_id)
    if not key_alias or not creator_idurl:
        raise Exception('incorrect key_id format')
    if key_id not in known_keys():
        key_id = make_key_id(
            alias=key_alias,
            creator_idurl=creator_idurl,
        )
    if key_id not in known_keys():
        raise Exception('key %s is unknown' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    key_info = make_key_info(key_object, key_id=key_id, include_private=include_private, )
    return key_info


def read_key_info(key_json):
    try:
        key_id = strng.to_text(key_json['key_id'])
        include_private = bool(key_json['include_private'])
        if include_private:
            raw_openssh_string = strng.to_text(key_json['private'])
        else:
            raw_openssh_string = strng.to_text(key_json['public'])
        key_object = unserialize_key_to_object(raw_openssh_string)
        if not key_object:
            raise Exception('unserialize failed')
        key_object.label = strng.to_text(key_json.get('label', ''))
    except:
        lg.exc()
        raise Exception('failed reading key info')
    return latest_key_id(key_id), key_object

#------------------------------------------------------------------------------

def get_label(key_id):
    """
    Returns known label for given key.
    """
    key_id = latest_key_id(strng.to_text(key_id))
    if key_id not in known_keys():
        return None
    return key_obj(key_id).label

#------------------------------------------------------------------------------
