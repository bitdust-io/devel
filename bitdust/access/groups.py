#!/usr/bin/python
# groups.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (groups.py) is part of BitDust Software.
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
.. module:: groups


BitDust Groups are intended to organize isolated private data flows between multiple users.

Owner of the group (customer) first creates a new "group key" that will be used to
protect data flows between participants of the group.

To add a new member to the group he just need to share the private part of that key
with the trusted person - that is implemented in `group_access_donor()` state machine.
Remote user once received the key will recognize that the key is actually a "group key"
(alias of the key must begins with `group_`) and will start a new instance
of `group_access_coordinator()` state machine which suppose to connect him to
other participants of the group.

In order to run data flows between multiple users a new role was introduced which is
called `postman`. All group communications are done via postmans - those are holding
the queues and group participants are connected to the queues as "consumers" and "producers".
Postmans are running on same devices where suppliers of the group creator are hoster.
That way all group participants always know where to connect to because list of suppliers
is already available in the DHT.

The postman is not able to read message content, but only validate the signature
and verify that participants are authorized.

Each group participant selects only one postman to publish messages to the group, but it always
subscribes to all of the known postmans to listen for incoming messages. In case selected postman goes offline
the group participant will switch to the next known postman in the list.

It is possible that two group participants simultaneously sent two different messages to the group with same
sequence ID. That creates a conflict in the sequence of messages delivered to the group memebers.
It is solved directly on each group participant node.

In short group is:
    1. group key created by "group owner" and shared to participants
    2. messages queues are served by postmans
    3. consumers and producers subscribed to the queues and able to send/receive messages

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.internet.defer import DeferredList

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import strng
from bitdust.lib import utime
from bitdust.lib import jsn

from bitdust.system import local_fs
from bitdust.system import bpio

from bitdust.contacts import contactsdb
from bitdust.contacts import identitycache

from bitdust.main import settings

from bitdust.crypt import key
from bitdust.crypt import my_keys

from bitdust.access import key_ring

from bitdust.userid import id_url
from bitdust.userid import global_id

#------------------------------------------------------------------------------

REQUIRED_BROKERS_COUNT = 3

_ActiveGroups = {}

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'groups.init')
    open_known_groups()


def shutdown():
    unload_groups()
    if _Debug:
        lg.out(_DebugLevel, 'groups.shutdown')


#------------------------------------------------------------------------------


def active_groups():
    global _ActiveGroups
    return _ActiveGroups


#------------------------------------------------------------------------------


def is_group_exist(group_key_id):
    group_key_id = my_keys.latest_key_id(group_key_id)
    return group_key_id in active_groups()


def is_group_stored(group_key_id):
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    group_info_path = os.path.join(groups_dir, group_key_id)
    return os.path.isfile(group_info_path)


def generate_group_key(creator_id=None, label=None, key_size=4096, group_alias=None):
    group_key_id = None
    if group_alias:
        group_key_id = my_keys.make_key_id(alias=group_alias, creator_glob_id=creator_id)
        if my_keys.is_key_registered(group_key_id):
            return my_keys.latest_key_id(group_key_id)
    else:
        while True:
            random_sample = os.urandom(24)
            group_alias = 'group_%s' % strng.to_text(key.HashMD5(random_sample, hexdigest=True))
            group_key_id = my_keys.make_key_id(alias=group_alias, creator_glob_id=creator_id)
            if my_keys.is_key_registered(group_key_id):
                continue
            break
    if not label:
        label = 'group%s' % utime.make_timestamp()
    my_keys.generate_key(key_id=group_key_id, label=label, key_size=key_size)
    my_keys.sign_key(key_id=group_key_id, save=True)
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id, group_alias=group_alias, creator_id=creator_id, label=label)
    return group_key_id


def set_group_info(group_key_id, group_info=None):
    group_key_id = my_keys.latest_key_id(group_key_id)
    if not group_info:
        group_info = {
            'last_sequence_id': -1,
            'active': False,
        }
    active_groups()[group_key_id] = group_info
    return True


def create_new_group(label, creator_id=None, key_size=2048, group_alias=None, with_group_info=True):
    if _Debug:
        lg.args(_DebugLevel, label=label, creator_id=creator_id, key_size=key_size, group_alias=group_alias)
    group_key_id = generate_group_key(creator_id=creator_id, label=label, key_size=key_size, group_alias=group_alias)
    if with_group_info:
        set_group_info(group_key_id, group_info={'last_sequence_id': -1, 'active': False})
        save_group_info(group_key_id)
    return group_key_id


#------------------------------------------------------------------------------


def send_group_pub_key_to_suppliers(group_key_id):
    l = []
    for supplier_idurl in contactsdb.suppliers():
        if supplier_idurl:
            d = key_ring.transfer_key(group_key_id, supplier_idurl, include_private=False, include_signature=False)
            d.addCallback(lg.cb, debug=_Debug, debug_level=_DebugLevel, method='groups.write_group_key_to_suppliers')
            d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='groups.write_group_key_to_suppliers')
            # TODO: build some kind of retry mechanism - in case of a particular supplier did not received the key
            # it must be some process with each supplier that first verifies a list of my public keys supplier currently possess
            # and then transfer the missing keys or send a note to erase "unused" keys to be able to cleanup old keys
            l.append(d)
    return DeferredList(l, consumeErrors=True)


#------------------------------------------------------------------------------


def open_known_groups():
    to_be_opened = []
    to_be_cached = []
    for key_id in my_keys.known_keys():
        if not key_id.startswith('group_'):
            continue
        if not my_keys.is_key_private(key_id):
            continue
        if not my_keys.is_active(key_id):
            continue
        to_be_opened.append(key_id)
        _, customer_idurl = my_keys.split_key_id(key_id)
        if not id_url.is_cached(customer_idurl):
            to_be_cached.append(customer_idurl)
    if _Debug:
        lg.args(_DebugLevel, to_be_opened=to_be_opened, to_be_cached=to_be_cached)
    if to_be_cached:
        d = identitycache.start_multiple(to_be_cached)
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='groups.open_known_groups')
        d.addBoth(lambda _: prepare_known_groups(to_be_opened))
        return
    prepare_known_groups(to_be_opened)


def prepare_known_groups(to_be_opened):
    for group_key_id in to_be_opened:
        _, customer_idurl = my_keys.split_key_id(group_key_id)
        if not id_url.is_cached(customer_idurl):
            lg.err('not able to open group %r, customer IDURL %r still was not cached' % (group_key_id, customer_idurl))
            continue
        if not is_group_stored(group_key_id):
            set_group_info(group_key_id)
            set_group_active(group_key_id, bool(my_keys.is_active(group_key_id)))
            save_group_info(group_key_id)
    load_groups()


def load_groups():
    loaded_groups = 0
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    if not os.path.isdir(groups_dir):
        bpio._dirs_make(groups_dir)
    for group_key_id in os.listdir(groups_dir):
        latest_group_key_id = my_keys.latest_key_id(group_key_id)
        latest_group_path = os.path.join(groups_dir, latest_group_key_id)
        if latest_group_key_id != group_key_id:
            lg.info('going to rename rotated group key: %r -> %r' % (group_key_id, latest_group_key_id))
            old_group_path = os.path.join(groups_dir, group_key_id)
            try:
                os.rename(old_group_path, latest_group_path)
            except:
                lg.exc()
                continue
        latest_group_info = jsn.loads_text(local_fs.ReadTextFile(latest_group_path))
        if not latest_group_info:
            lg.err('was not able to load group info from %r' % latest_group_path)
            continue
        active_groups()[latest_group_key_id] = latest_group_info
        loaded_groups += 1
    if _Debug:
        lg.args(_DebugLevel, loaded_groups=loaded_groups)


def unload_groups():
    active_groups().clear()
    if _Debug:
        lg.dbg(_DebugLevel, 'known groups and brokers are erased')


#------------------------------------------------------------------------------


def save_group_info(group_key_id):
    group_key_id = my_keys.latest_key_id(group_key_id)
    if not is_group_exist(group_key_id):
        lg.warn('group %r is not known' % group_key_id)
        return False
    group_info = active_groups()[group_key_id]
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    group_info_path = os.path.join(groups_dir, group_key_id)
    if not os.path.isdir(groups_dir):
        bpio._dirs_make(groups_dir)
    ret = local_fs.WriteTextFile(group_info_path, jsn.dumps(group_info))
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id, group_info_path=group_info_path, ret=ret)
    return ret


def erase_group_info(group_key_id):
    if not is_group_exist(group_key_id):
        lg.warn('group %r is not known' % group_key_id)
        return False
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    group_info_path = os.path.join(groups_dir, group_key_id)
    if not os.path.isfile(group_info_path):
        return False
    os.remove(group_info_path)
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id, group_info_path=group_info_path)
    return True


def read_group_info(group_key_id):
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    group_info_path = os.path.join(groups_dir, group_key_id)
    if not os.path.isfile(group_info_path):
        return None
    group_info = jsn.loads_text(local_fs.ReadTextFile(group_info_path))
    return group_info


#------------------------------------------------------------------------------


def get_last_sequence_id(group_key_id):
    group_key_id = my_keys.latest_key_id(group_key_id)
    if not is_group_exist(group_key_id):
        return -1
    return active_groups()[group_key_id]['last_sequence_id']


def set_last_sequence_id(group_key_id, last_sequence_id):
    group_key_id = my_keys.latest_key_id(group_key_id)
    if not is_group_exist(group_key_id):
        lg.warn('group %r is not known' % group_key_id)
        return False
    active_groups()[group_key_id]['last_sequence_id'] = last_sequence_id
    return True


#------------------------------------------------------------------------------


def is_group_active(group_key_id):
    group_key_id = my_keys.latest_key_id(group_key_id)
    if not is_group_exist(group_key_id):
        return False
    return active_groups()[group_key_id]['active']


def set_group_active(group_key_id, value):
    group_key_id = my_keys.latest_key_id(group_key_id)
    if not is_group_exist(group_key_id):
        lg.warn('group %r is not known' % group_key_id)
        return False
    old_value = active_groups()[group_key_id]['active']
    active_groups()[group_key_id]['active'] = value
    if old_value != value:
        lg.info('group %r "active" status changed: %r -> %r' % (group_key_id, old_value, value))
    return True


#------------------------------------------------------------------------------


def on_identity_url_changed(evt):
    from bitdust.access import group_participant
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    old_idurl = id_url.field(evt.data['old_idurl'])
    active_group_keys = list(active_groups())
    to_be_reconnected = []
    for group_key_id in active_group_keys:
        if not group_key_id:
            continue
        group_creator_idurl = global_id.glob2idurl(group_key_id)
        if id_url.is_the_same(group_creator_idurl, old_idurl):
            old_group_path = os.path.join(groups_dir, group_key_id)
            latest_group_key_id = my_keys.latest_key_id(group_key_id)
            latest_group_path = os.path.join(groups_dir, latest_group_key_id)
            lg.info('going to rename rotated group file: %r -> %r' % (old_group_path, latest_group_path))
            if os.path.isfile(old_group_path):
                try:
                    os.rename(old_group_path, latest_group_path)
                except:
                    lg.exc()
                    continue
            else:
                lg.warn('key file %r was not found, key was not renamed' % old_group_path)
            active_groups()[latest_group_key_id] = active_groups().pop(group_key_id)
            group_participant.rotate_active_group_participant(group_key_id, latest_group_key_id)
        gp = group_participant.get_active_group_participant(group_key_id)
        if gp and gp.active_supplier_idurl and id_url.is_the_same(old_idurl, gp.active_supplier_idurl):
            lg.info('active supplier %r IDURL is rotated, going to reconnect %r' % (old_idurl, gp))
            if group_key_id not in to_be_reconnected:
                to_be_reconnected.append(group_key_id)
    if _Debug:
        lg.args(_DebugLevel, to_be_reconnected=to_be_reconnected)
    for group_key_id in to_be_reconnected:
        gp = group_participant.get_active_group_participant(group_key_id)
        if gp:
            gp.automat('reconnect')
