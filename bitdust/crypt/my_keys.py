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

_Debug = False
_DebugLevel = 10

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

from bitdust.logs import lg

from bitdust.lib import misc
from bitdust.lib import strng
from bitdust.lib import jsn
from bitdust.lib import utime

from bitdust.system import local_fs

from bitdust.main import settings
from bitdust.main import events
from bitdust.main import listeners

from bitdust.crypt import key
from bitdust.crypt import rsa_key
from bitdust.crypt import hashes

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_KnownKeys = {}
_LatestLocalKeyID = -1
_LocalKeysRegistry = {}
_LocalKeysIndex = {}

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.init')
    scan_local_keys()


def shutdown():
    global _LatestLocalKeyID
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.shutdown')
    known_keys().clear()
    local_keys().clear()
    local_keys_index().clear()
    _LatestLocalKeyID = 0


#------------------------------------------------------------------------------


def key_obj(key_id=None):
    """
    Alias.
    """
    if not key_id:
        return known_keys()
    if key_id not in known_keys():
        new_key_id = latest_key_id(key_id)
        if new_key_id == key_id:
            raise Exception('key %r is not registered' % key_id)
        if new_key_id not in known_keys():
            raise Exception('key %r is not registered' % new_key_id)
        rename_key(key_id, new_key_id)
        key_id = new_key_id
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    return known_keys()[key_id]


def known_keys():
    """
    Returns dictionary with all registered keys by global identifiers.
    Item value can be None which means the key needs to be loaded first from local file.
    """
    global _KnownKeys
    return _KnownKeys


def local_keys():
    """
    Stores local identifiers of the registered keys.
    """
    global _LocalKeysRegistry
    return _LocalKeysRegistry


def local_keys_index():
    """
    Keeps an index of public key part and local key identifier.
    """
    global _LocalKeysIndex
    return _LocalKeysIndex


#------------------------------------------------------------------------------


def is_key_registered(key_id, include_master=True):
    """
    Returns True if this key is known.
    """
    if include_master:
        if key_id == 'master':
            return True
        if key_id == my_id.getGlobalID():
            return True
        if key_id == my_id.getGlobalID(key_alias='master'):
            return True
    if key_id in known_keys():
        return True
    new_key_id = latest_key_id(key_id)
    if new_key_id in known_keys():
        rename_key(key_id, new_key_id)
        return True
    check_rename_my_keys(prefix=new_key_id.split('@')[0])
    return key_id in known_keys()


def is_key_private(key_id, include_master=True):
    if not is_key_registered(key_id):
        return False
    if include_master:
        if key_id == 'master':
            return True
        if key_id == my_id.getGlobalID():
            return True
        if key_id == my_id.getGlobalID(key_alias='master'):
            return True
    return not key_obj(key_id).isPublic()


#------------------------------------------------------------------------------


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
        return '{}${}'.format(alias, creator_glob_id)
    if creator_idurl is None:
        creator_idurl = my_id.getIDURL()
    return global_id.MakeGlobalID(
        idurl=creator_idurl,
        key_alias=alias,
    )


def split_key_id(key_id, as_field=True):
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
    if as_field:
        return parts['key_alias'], id_url.field(parts['idurl'])
    return parts['key_alias'], strng.to_bin(parts['idurl'])


def is_valid_key_id(global_key_id):
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
    key_id = strng.to_text(key_id)
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


def get_creator_idurl(key_id, as_field=True):
    """
    Returns creator IDURL from the key_id.
    """
    _, _, creator_glob_id = key_id.partition('$')
    return global_id.glob2idurl(creator_glob_id, as_field=as_field)


#------------------------------------------------------------------------------


def scan_local_keys(keys_folder=None):
    global _LatestLocalKeyID
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.scan_local_keys will read files from %r' % keys_folder)
    latest_local_key_id_filepath = os.path.join(keys_folder, 'latest_local_key_id')
    latest_local_key_id_src = local_fs.ReadTextFile(latest_local_key_id_filepath)
    if latest_local_key_id_src:
        _LatestLocalKeyID = int(latest_local_key_id_src)
    else:
        _LatestLocalKeyID = 0
    known_keys().clear()
    local_keys().clear()
    local_keys_index().clear()
    count = 0
    unregistered_keys = []
    for key_filename in os.listdir(keys_folder):
        if key_filename == 'latest_local_key_id':
            continue
        key_id = key_filename.replace('.private', '').replace('.public', '')
        if not is_valid_key_id(key_id):
            lg.err('key_id is not valid: %r' % key_id)
            continue
        key_dict = read_key_file(key_id, keys_folder=keys_folder)
        local_key_id = key_dict.get('local_key_id')
        if local_key_id is None:
            key_dict['key_id'] = key_id
            unregistered_keys.append(key_dict)
            continue
        if _LatestLocalKeyID < local_key_id:
            _LatestLocalKeyID = local_key_id
        local_keys()[local_key_id] = key_id
        known_keys()[key_id] = None
        count += 1
    registered_count = 0
    for key_dict in unregistered_keys:
        key_id = key_dict['key_id']
        if not load_key(key_id, keys_folder=keys_folder):
            continue
        _LatestLocalKeyID += 1
        new_local_key_id = _LatestLocalKeyID
        lg.info('about to register key %r with local_key_id=%r' % (key_id, new_local_key_id))
        known_keys()[key_id].local_key_id = new_local_key_id
        save_key(key_id, keys_folder=keys_folder)
        registered_count += 1
    unregistered_keys = []
    save_latest_local_key_id(keys_folder=keys_folder)
    if _Debug:
        lg.out(_DebugLevel, '    %d keys found and %d registered' % (count, registered_count))


def read_key_file(key_id, keys_folder=None):
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    key_filepath = os.path.join(keys_folder, '%s.private' % key_id)
    is_private = True
    if not os.path.exists(key_filepath):
        key_filepath = os.path.join(keys_folder, '%s.public' % key_id)
        is_private = False
    key_raw = local_fs.ReadTextFile(key_filepath)
    if not key_raw:
        lg.err('failed reading key from %r' % key_filepath)
        return None
    key_raw_strip = key_raw.strip()
    try:
        if key_raw_strip.startswith('{') and key_raw_strip.endswith('}'):
            key_dict = jsn.loads_text(key_raw_strip)
        else:
            key_dict = {
                'label': key_id,
                'is_private': is_private,
                'body': key_raw_strip,
                'local_key_id': None,
                'need_to_convert': True,
                'active': True,
            }
    except:
        lg.exc()
        return None
    return key_dict


def load_key(key_id, keys_folder=None):
    global _LatestLocalKeyID
    if not is_valid_key_id(key_id):
        lg.err('key is not valid: %r' % key_id)
        return False
    key_dict = read_key_file(key_id, keys_folder=keys_folder)
    try:
        key_object = rsa_key.RSAKey()
        key_object.fromDict(key_dict)
    except:
        lg.exc()
        return False
    if not key_object.isPublic():
        if not validate_key(key_object):
            lg.err('validation failed for: %r' % key_id)
            return False
    known_keys()[key_id] = key_object
    if key_dict.get('need_to_convert'):
        save_key(key_id, keys_folder=keys_folder)
        lg.info('key %r format converted to JSON' % key_id)
    else:
        if key_object.local_key_id is not None:
            if _LatestLocalKeyID < key_object.local_key_id:
                _LatestLocalKeyID = key_object.local_key_id
                save_latest_local_key_id(keys_folder=keys_folder)
            local_keys()[key_object.local_key_id] = key_id
            local_keys_index()[key_object.toPublicString()] = key_object.local_key_id
            if _Debug:
                lg.out(_DebugLevel, 'my_keys.load_key %r  label=%r  active=%r  is_private=%r  local_key_id=%r  from %s' % (key_id, key_object.label, key_object.active, not key_object.isPublic(), key_object.local_key_id, keys_folder))
        else:
            lg.warn('for key %r local_key_id was not set' % key_id)
    events.send('key-loaded', data=dict(
        key_id=key_id,
        label=key_object.label,
        key_size=key_object.size(),
    ))
    snapshot = make_key_info(
        key_object=key_object,
        key_id=key_id,
        event='key-loaded',
        include_private=False,
        include_local_id=True,
        include_signature=True,
        include_label=True,
        include_state=True,
    )
    listeners.push_snapshot('key', snap_id=key_id, data=snapshot)
    return True


def save_key(key_id, keys_folder=None):
    key_object = known_keys()[key_id]
    if key_object is None:
        lg.warn('can not save key %s because it is not loaded yet' % key_id)
        return False
    if key_object.local_key_id is None:
        raise Exception('local key id was not set for %r' % key_id)
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
    if not local_fs.WriteTextFile(key_filepath, key_string):
        lg.err('failed saving key %r to %r' % (key_id, key_filepath))
        return False
    local_keys()[key_object.local_key_id] = key_id
    local_keys_index()[key_object.toPublicString()] = key_object.local_key_id
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.save_key stored key %r with local_key_id=%r in %r' % (key_id, key_object.local_key_id, key_filepath))
    return True


def save_keys_local(keys_folder=None):
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


def save_latest_local_key_id(keys_folder=None):
    global _LatestLocalKeyID
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    latest_local_key_id_filepath = os.path.join(keys_folder, 'latest_local_key_id')
    if not local_fs.WriteTextFile(latest_local_key_id_filepath, '{}'.format(_LatestLocalKeyID)):
        lg.err('failed saving latest_local_key_id to %r' % latest_local_key_id_filepath)
        return False
    return True


#------------------------------------------------------------------------------


def generate_key(key_id, label='', active=True, key_size=4096, keys_folder=None):
    global _LatestLocalKeyID
    key_id = latest_key_id(key_id)
    if is_key_registered(key_id):
        lg.warn('key %r already registered' % key_id)
        return None
    if not label:
        label = 'key%s' % utime.make_timestamp()
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.generate_key %r of %d bits, label=%r' % (key_id, key_size, label))
    _LatestLocalKeyID += 1
    save_latest_local_key_id(keys_folder=keys_folder)
    key_object = rsa_key.RSAKey()
    key_object.generate(key_size)
    key_object.label = label
    key_object.active = active
    key_object.local_key_id = _LatestLocalKeyID
    known_keys()[key_id] = key_object
    if _Debug:
        lg.out(_DebugLevel, '    key %r generated' % key_id)
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    save_key(key_id, keys_folder=keys_folder)
    events.send('key-generated', data=dict(
        key_id=key_id,
        label=label,
        key_size=key_size,
    ))
    snapshot = make_key_info(
        key_object=key_object,
        key_id=key_id,
        event='key-generated',
        include_private=False,
        include_local_id=True,
        include_signature=True,
        include_label=True,
        include_state=True,
    )
    listeners.push_snapshot('key', snap_id=key_id, data=snapshot)
    return key_object


def register_key(key_id, key_object_or_string, label='', active=True, keys_folder=None):
    global _LatestLocalKeyID
    key_id = latest_key_id(key_id)
    if is_key_registered(key_id):
        lg.warn('key %s already registered' % key_id)
        return None
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if not label:
        label = 'key%s' % utime.make_timestamp()
    if strng.is_string(key_object_or_string):
        key_object_or_string = strng.to_bin(key_object_or_string)
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.register_key %r from %d bytes openssh_input_string' % (key_id, len(key_object_or_string)))
        key_object = unserialize_key_to_object(key_object_or_string)
        if not key_object:
            lg.err('invalid openssh string, unserialize_key_to_object() failed')
            return None
    else:
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.register_key %r from object' % key_id)
        key_object = key_object_or_string
        label = key_object.label or label
    known_local_key_id = local_keys_index().get(key_object.toPublicString())
    if known_local_key_id is not None:
        known_key_id = local_keys().get(known_local_key_id)
        if known_key_id is not None:
            known_key_id = latest_key_id(known_key_id)
            if known_key_id != key_id:
                raise Exception('must not register same key with local_key_id=%r twice with different key_id: %r ~ %r' % (
                    known_local_key_id,
                    known_key_id,
                    key_id,
                ))
    new_local_key_id = known_local_key_id
    if new_local_key_id is None:
        _LatestLocalKeyID += 1
        save_latest_local_key_id(keys_folder=keys_folder)
        new_local_key_id = _LatestLocalKeyID
    key_object.local_key_id = new_local_key_id
    key_object.label = label
    key_object.active = active
    known_keys()[key_id] = key_object
    if _Debug:
        lg.out(_DebugLevel, '    key %r registered' % key_id)
    save_key(key_id, keys_folder=keys_folder)
    events.send('key-registered', data=dict(
        key_id=key_id,
        local_key_id=new_local_key_id,
        label=label,
        key_size=key_object.size(),
    ))
    snapshot = make_key_info(
        key_object=key_object,
        key_id=key_id,
        event='key-registered',
        include_private=False,
        include_local_id=True,
        include_signature=True,
        include_label=True,
        include_state=True,
    )
    listeners.push_snapshot('key', snap_id=key_id, data=snapshot)
    return key_object


def erase_key(key_id, keys_folder=None):
    key_id = latest_key_id(key_id)
    if not is_key_registered(key_id):
        lg.warn('key %s is not registered' % key_id)
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
    k_obj = known_keys().pop(key_id)
    erased_local_key_id = k_obj.local_key_id
    local_keys().pop(k_obj.local_key_id, None)
    local_keys_index().pop(k_obj.toPublicString(), None)
    gc.collect()
    if _Debug:
        lg.out(_DebugLevel, '    key %s removed, file %s deleted' % (key_id, key_filepath))
    events.send('key-erased', data=dict(key_id=key_id, local_key_id=erased_local_key_id, is_private=is_private))
    snapshot = make_key_info(
        key_object=None,
        key_id=key_id,
        local_id=erased_local_key_id,
        event='key-erased',
        include_private=False,
        include_local_id=True,
        include_signature=True,
        include_label=True,
        include_state=True,
    )
    listeners.push_snapshot('key', snap_id=key_id, deleted=True, data=snapshot)
    return True


def validate_key(key_object):
    sample_data = strng.to_bin(base64.b64encode(os.urandom(256)))
    sample_hash_base = hashes.sha1(sample_data, hexdigest=True)
    sample_signature = key_object.sign(sample_hash_base)
    is_valid = key_object.verify(sample_signature, sample_hash_base)
    if not is_valid:
        if _Debug:
            lg.err('validate_key FAILED')
            lg.out(_DebugLevel, 'public=%r' % key_object.toPublicString())
            lg.out(_DebugLevel, 'signature=%r' % sample_signature)
            lg.out(_DebugLevel, 'hash_base=%r' % sample_hash_base)
            lg.out(_DebugLevel, 'data=%r' % sample_data)
    return is_valid


def rename_key(current_key_id, new_key_id, keys_folder=None):
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
    is_signed = key_obj(current_key_id).isSigned()
    try:
        os.rename(current_key_filepath, new_key_filepath)
    except:
        lg.exc()
        return False
    key_object = known_keys().pop(current_key_id)
    known_keys()[new_key_id] = key_object
    local_keys()[key_object.local_key_id] = new_key_id
    if is_signed:
        sign_key(
            key_id=new_key_id,
            keys_folder=keys_folder,
            ignore_shared_keys=True,
            save=False,
        )
    save_key(new_key_id, keys_folder=keys_folder)
    gc.collect()
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.rename_key   key %s renamed to %s' % (current_key_id, new_key_id))
    events.send('key-renamed', data=dict(old_key_id=current_key_id, new_key_id=new_key_id, is_private=is_private))
    return True


def sign_key(key_id, keys_folder=None, ignore_shared_keys=False, save=True):
    key_id = latest_key_id(strng.to_text(key_id))
    if not is_key_registered(key_id):
        lg.warn('key %s is not found' % key_id)
        return False
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    key_object = known_keys()[key_id]
    if key_object.signed:
        if key_object.signed[1] != key.MyPublicKey():
            if ignore_shared_keys:
                if _Debug:
                    lg.dbg(_DebugLevel, 'skip generating signature for shared key: %r' % key_id)
                return True
            raise Exception('must not generate and overwrite existing signature for shared key: %r' % key_id)
    signed_key_info = make_key_info(
        key_object=key_object,
        key_id=key_id,
        include_private=not key_object.isPublic(),
        generate_signature=True,
    )
    key_object.save_signed_info(
        signature_raw=signed_key_info['signature'],
        public_key_raw=signed_key_info['signature_pubkey'],
    )
    known_keys()[key_id] = key_object
    if save:
        save_key(key_id, keys_folder=keys_folder)
    events.send('key-signed', data=dict(
        key_id=key_id,
        label=key_object.label,
        key_size=key_object.size(),
    ))
    snapshot = make_key_info(
        key_object=key_object,
        key_id=key_id,
        event='key-signed',
        include_private=False,
        include_local_id=True,
        include_signature=True,
        include_label=True,
        include_state=True,
    )
    listeners.push_snapshot('key', snap_id=key_id, data=snapshot)
    return key_object


#------------------------------------------------------------------------------


def sign(key_id, inp):
    """
    Sign some ``inp`` string with given key.
    This will call PyCrypto method ``Crypto.PublicKey.RSA.sign``.
    Returns byte string.
    """
    key_id = latest_key_id(key_id)
    if not is_key_registered(key_id):
        raise Exception('key %s is not registered' % key_id)
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
    if not is_key_registered(key_id):
        raise Exception('key %s is not registered' % key_id)
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
            lg.out(_DebugLevel, 'my_keys.encrypt  payload of %d bytes using my "master" key alias' % len(inp))
        return key.EncryptLocalPublicKey(inp)
    if key_id == my_id.getGlobalID():  # user@host.org
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.encrypt  payload of %d bytes using my "master" key, short format' % len(inp))
        return key.EncryptLocalPublicKey(inp)
    if key_id == my_id.getGlobalID(key_alias='master'):  # master$user@host.org
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.encrypt  payload of %d bytes using my "master" key, full format' % len(inp))
        return key.EncryptLocalPublicKey(inp)
    key_id = latest_key_id(key_id)
    if not is_key_registered(key_id):
        raise Exception('key %s is not registered' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.encrypt  payload of %d bytes with key %s' % (len(inp), key_id))
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
            lg.out(_DebugLevel, 'my_keys.decrypt  payload of %d bytes using my "master" key alias' % len(inp))
        return key.DecryptLocalPrivateKey(inp)
    if key_id == my_id.getGlobalID(key_alias='master'):  # master$user@host.org
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.decrypt  payload of %d bytes using my "master" key, full format' % len(inp))
        return key.DecryptLocalPrivateKey(inp)
    if key_id == my_id.getGlobalID():  # user@host.org
        if _Debug:
            lg.out(_DebugLevel, 'my_keys.decrypt  payload of %d bytes using my "master" key, short format' % len(inp))
        return key.DecryptLocalPrivateKey(inp)
    key_id = latest_key_id(key_id)
    if not is_key_registered(key_id):
        raise Exception('key %s is not registered' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    if _Debug:
        lg.out(_DebugLevel, 'my_keys.decrypt  payload of %d bytes with registered key %s' % (len(inp), key_id))
    result = key_object.decrypt(inp)
    return result


#------------------------------------------------------------------------------


def serialize_key(key_id):
    key_id = latest_key_id(key_id)
    if not is_key_registered(key_id):
        raise Exception('key %s is not registered' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    return key_object.toPrivateString()


def unserialize_key_to_object(raw_string):
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


def get_label(key_id):
    """
    Returns known label for given key.
    """
    key_id = strng.to_text(key_id)
    if not is_key_registered(key_id):
        return ''
    return key_obj(key_id).label


def get_local_key_id(key_id):
    key_id = strng.to_text(key_id)
    if key_id == 'master':
        return 0
    if key_id == my_id.getGlobalID():
        return 0
    if key_id == my_id.getGlobalID(key_alias='master'):
        return 0
    if not is_key_registered(key_id, include_master=False):
        return None
    return key_obj(key_id).local_key_id


def get_local_key(local_key_id):
    if local_key_id == 0:
        return my_id.getGlobalID('master')
    return local_keys().get(local_key_id)


#------------------------------------------------------------------------------


def is_active(key_id):
    """
    Returns True if given key has "active" state. If key is not set to "active" state, certain parts of the software should not use it.
    """
    key_id = strng.to_text(key_id)
    if not is_key_registered(key_id):
        return None
    return key_obj(key_id).active


def set_active(key_id, active=True):
    key_id = strng.to_text(key_id)
    if not is_key_registered(key_id):
        return
    key_obj(key_id).active = active


#------------------------------------------------------------------------------


def make_master_key_info(include_private=False):
    r = {
        'key_id': my_id.getGlobalID(key_alias='master'),
        'alias': 'master',
        'label': my_id.getGlobalID(key_alias='master'),
        'active': True,
        'creator': my_id.getIDURL(),
        'is_public': key.MyPrivateKeyObject().isPublic(),  # 'fingerprint': str(key.MyPrivateKeyObject().fingerprint()),
        # 'type': str(key.MyPrivateKeyObject().type()),
        # 'ssh_type': str(key.MyPrivateKeyObject().sshType()),
        'public': strng.to_text(key.MyPrivateKeyObject().toPublicString()),
        'include_private': include_private,
    }
    r['private'] = None
    if include_private:
        r['private'] = strng.to_text(key.MyPrivateKeyObject().toPrivateString())
    if hasattr(key.MyPrivateKeyObject(), 'size'):
        r['size'] = strng.to_text(key.MyPrivateKeyObject().size())
    else:
        r['size'] = '0'
    return r


def make_key_info(
    key_object, key_id=None, key_alias=None, creator_idurl=None, include_private=False, generate_signature=False, include_signature=False, include_local_id=False, include_label=True, include_state=False, event=None, local_id=None
):
    if key_id:
        key_id = latest_key_id(key_id)
        key_alias, creator_idurl = split_key_id(key_id)
    else:
        key_id = make_key_id(alias=key_alias, creator_idurl=id_url.field(creator_idurl))
    r = {
        'key_id': key_id,
        'alias': key_alias,
        'creator': creator_idurl,
        'public': strng.to_text(key_object.toPublicString()) if key_object else None,
        'private': None,
        'include_private': include_private,
    }
    if event:
        r['event'] = event
    if include_label:
        r['label'] = key_object.label if key_object else ''
    if include_state:
        r['active'] = key_object.active if key_object else True
    if key_object and key_object.isPublic():
        r['is_public'] = True
        if include_private:
            raise Exception('this key contains only public component')
    else:
        r['is_public'] = not include_private
        if include_private:
            r['private'] = strng.to_text(key_object.toPrivateString()) if key_object else None
    if key_object and hasattr(key_object, 'size'):
        r['size'] = strng.to_text(key_object.size())
    else:
        r['size'] = '0'
    if include_local_id:
        if local_id:
            r['local_key_id'] = local_id
        else:
            r['local_key_id'] = getattr(key_object, 'local_key_id', None) if key_object else None
    if key_object and generate_signature:
        r = sign_key_info(r)
    else:
        if include_signature and key_object and key_object.isSigned():
            r['signature'] = key_object.signed[0]
            r['signature_pubkey'] = key_object.signed[1]
    return r


def get_key_info(key_id, include_private=False, include_signature=False, generate_signature=False, include_label=True, include_state=False):
    """
    Returns dictionary with full key info or raise an Exception.
    """
    key_id = strng.to_text(key_id)
    if key_id == 'master' or key_id == my_id.getGlobalID(key_alias='master') or key_id == my_id.getGlobalID():
        return make_master_key_info(include_private=include_private)
    key_id = latest_key_id(key_id)
    key_alias, creator_idurl = split_key_id(key_id)
    if not key_alias or not creator_idurl:
        raise Exception('incorrect key_id format: %s' % key_id)
    if not is_key_registered(key_id):
        key_id = make_key_id(
            alias=key_alias,
            creator_idurl=creator_idurl,
        )
    if not is_key_registered(key_id):
        raise Exception('key %s is not registered' % key_id)
    if known_keys()[key_id] is None:
        if not load_key(key_id):
            raise Exception('key load failed: %s' % key_id)
    key_object = known_keys()[key_id]
    key_info = make_key_info(
        key_object=key_object,
        key_id=key_id,
        include_private=include_private,
        include_signature=include_signature,
        generate_signature=generate_signature,
        include_label=include_label,
        include_state=include_state,
    )
    return key_info


def read_key_info(key_json):
    try:
        key_id = strng.to_text(key_json['key_id'])
        include_private = bool(key_json['include_private'])
        if include_private or key_json.get('private'):
            raw_openssh_string = strng.to_text(key_json['private'])
        else:
            raw_openssh_string = strng.to_text(key_json['public'])
        key_object = unserialize_key_to_object(raw_openssh_string)
        if not key_object:
            raise Exception('unserialize failed')
        key_object.label = strng.to_text(key_json.get('label', ''))
        key_object.active = key_json.get('active', True)
        if 'signature' in key_json and 'signature_pubkey' in key_json:
            key_object.save_signed_info(
                signature_raw=key_json['signature'],
                public_key_raw=key_json['signature_pubkey'],
            )
    except:
        lg.exc()
        raise Exception('failed reading key info')
    return latest_key_id(key_id), key_object


#------------------------------------------------------------------------------


def sign_key_info(key_info):
    key_info['signature_pubkey'] = key.MyPublicKey()
    hash_items = []
    for field in [
        'alias',
        'public',
        'signature_pubkey',
    ]:
        hash_items.append(strng.to_text(key_info[field]))
    hash_text = '-'.join(hash_items)
    if _Debug:
        lg.dbg(_DebugLevel, hash_text)
    hash_bin = key.Hash(strng.to_bin(hash_text))
    key_info['signature'] = strng.to_text(key.Sign(hash_bin))
    return key_info


def verify_key_info_signature(key_info):
    if 'signature' not in key_info or 'signature_pubkey' not in key_info:
        lg.warn('signature was not found in the key info')
        return False
    hash_items = []
    for field in [
        'alias',
        'public',
        'signature_pubkey',
    ]:
        hash_items.append(strng.to_text(key_info[field]))
    hash_text = '-'.join(hash_items)
    if _Debug:
        lg.dbg(_DebugLevel, hash_text)
    hash_bin = key.Hash(strng.to_bin(hash_text))
    signature_bin = strng.to_bin(key_info['signature'])
    result = key.VerifySignature(key_info['signature_pubkey'], hash_bin, signature_bin)
    return result


#------------------------------------------------------------------------------


def check_rename_my_keys(prefix=None):
    """
    Make sure all my keys have correct names according to known latest identities I have cached.
    For every key checks corresponding IDURL info and decides to rename it if key owner's identity was rotated.
    """
    keys_to_be_renamed = {}
    for key_id in list(known_keys().keys()):
        if prefix:
            if not key_id.startswith(prefix):
                continue
        key_glob_id = global_id.ParseGlobalID(key_id)
        owner_idurl = key_glob_id['idurl']
        if not owner_idurl.is_latest():
            keys_to_be_renamed[key_id] = global_id.MakeGlobalID(
                idurl=owner_idurl.to_bin(),
                key_alias=key_glob_id['key_alias'],
            )
    if _Debug:
        lg.args(_DebugLevel, keys_to_be_renamed=len(keys_to_be_renamed))
    for current_key_id, new_key_id in keys_to_be_renamed.items():
        rename_key(current_key_id, new_key_id)


#------------------------------------------------------------------------------


def populate_keys():
    for key_id, key_object in known_keys().items():
        listeners.push_snapshot('key', snap_id=key_id, data=make_key_info(
            key_object=key_object,
            key_id=key_id,
            event=None,
            include_private=False,
            include_local_id=True,
            include_signature=True,
            include_label=True,
            include_state=True,
        ))


#------------------------------------------------------------------------------

if __name__ == '__main__':
    lg.set_debug_level(18)
    settings.init()
    init()
    import pprint
    pprint.pprint(local_keys_index())
    pprint.pprint(local_keys())
    print(get_key_info('master$recalx@seed.bitdust.io'))
    pprint.pprint(local_keys_index())
