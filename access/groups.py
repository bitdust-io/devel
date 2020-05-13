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
called `message_broker`. All group communications are done via message broker - he holds
the queue and participants are connected to the queue as "consumers" and "producers".

If owner / participant is not on-line at the moment the broker will keep the message for
some time. Basically broker removes a message from the queue only after all consumers
received it with acknowledgment. If single consumer not reading any messages from the queue
for a quite some time broker will release him automatically to prevent queue to be overloaded.

The owner of the group or one of the participants will have to first make sure that
at least one message broker "was hired" for the group. Basically first "consumer"
or "producer" who is interested in the particular queue will have to check and hire
a new message broker for given customer.

Customer can create multiple groups&queues but will have only one primary message broker
and possibly secondary and third brokers in stand by mode. This way there is no concurrency
exist in that flow and all group messages just passing by via single host from producers to
consumers: `producer -> message broker -> consumer`.

To hire a message broker owner, consumer or producer needs to find a new host in the network
via DHT and share public part of the group key with him. So message broker is not able to
read messages content but only validate the signatures and verify that participants are authorized.

Message broker publishes his info on DHT and so all of the group members
are able to find and connect to it. Secondary and third message broker also will be
hired but will be in "stand by" mode and not receive the messages from producers.

In case primary broker went offline but one of the producers wanted to publish a new message
to the queue - he will fail and switch to the secondary message broker quickly.
So producer will just re-try the message but to the secondary message broker.
Because other consumers are already connected to the secondary broker they will not recognize
any difference and will receive the message right away. This way mechanism of automatic failover
of message broker from primary to secondary suppose to prevent message lost.

In short group is:
    1. group key created by "group owner" and shared to participants
    2. message queue served by message broker
    3. DHT record holding ID of primary, secondary and third message brokers

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.internet.defer import DeferredList

#------------------------------------------------------------------------------

from logs import lg

from lib import strng
from lib import utime
from lib import jsn

from system import local_fs
from system import bpio

from contacts import contactsdb

from main import settings

from crypt import key
from crypt import my_keys

from access import key_ring

from userid import global_id

from interface import api

#------------------------------------------------------------------------------

REQUIRED_BROKERS_COUNT = 3

_ActiveGroups = {}
_KnownBrokers = {}

#------------------------------------------------------------------------------

def init():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'groups.init')
    load_groups()


def shutdown():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'groups.shutdown')

#------------------------------------------------------------------------------

def known_groups():
    global _ActiveGroups
    return _ActiveGroups


def known_brokers(customer_id=None, erase_brokers=False):
    global _KnownBrokers
    if not customer_id:
        return _KnownBrokers
    if erase_brokers:
        return _KnownBrokers.pop(customer_id, None)
    if customer_id not in _KnownBrokers:
        _KnownBrokers[customer_id] = [None, ] * REQUIRED_BROKERS_COUNT
    return _KnownBrokers[customer_id]

#------------------------------------------------------------------------------

def is_group_exist(group_key_id):
    return group_key_id in known_groups()


def is_group_stored(group_key_id):
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    group_info_path = os.path.join(groups_dir, group_key_id)
    return os.path.isfile(group_info_path)


def generate_group_key(creator_id=None, label=None, key_size=4096):
    group_key_id = None
    group_alias = None
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
    my_keys.sign_key(key_id=group_key_id)
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id, group_alias=group_alias, creator_id=creator_id, label=label)
    return group_key_id


def create_archive_folder(group_key_id, force_path_id=None):
    group_key_alias, group_creator_idurl = my_keys.split_key_id(group_key_id)
    catalog_path = os.path.join('.archive', group_key_alias)
    archive_folder_catalog_path = global_id.MakeGlobalID(
        key_alias=group_key_alias, customer=group_creator_idurl.to_id(), path=catalog_path)
    res = api.file_create(archive_folder_catalog_path, as_folder=True, exist_ok=True, force_path_id=force_path_id)
    if res['status'] != 'OK':
        lg.err('failed to create archive folder in the catalog: %r' % res)
        return None
    if res['result']['created']:
        lg.info('created new archive folder in the catalog: %r' % res)
    else:
        lg.info('archive folder already exist in the catalog: %r' % res)
    ret = res['result']['path_id']
    if force_path_id is not None:
        if force_path_id != ret:
            lg.err('archive folder exists, but have different path ID in the catalog: %r' % ret)
            return None
    return ret


def set_group_info(group_key_id, group_info=None):
    if not group_info:
        group_info = {
            'last_sequence_id': -1,
            'active': False,
            'archive_folder_path': None,
        }
    known_groups()[group_key_id] = group_info
    return True


def create_new_group(label, creator_id=None, key_size=4096):
    if _Debug:
        lg.args(_DebugLevel, label=label, creator_id=creator_id, key_size=key_size)
    group_key_id = generate_group_key(creator_id, label, key_size)
    remote_path = create_archive_folder(group_key_id)
    if remote_path is None:
        return None
    set_group_info(group_key_id, {
        'last_sequence_id': -1,
        'active': False,
        'archive_folder_path': remote_path,
    })
    save_group_info(group_key_id)
    return group_key_id

#------------------------------------------------------------------------------

def send_group_pub_key_to_suppliers(group_key_id):
    l = []
    for supplier_idurl in contactsdb.suppliers():
        if supplier_idurl:
            d = key_ring.transfer_key(group_key_id, supplier_idurl, include_private=False)
            if _Debug:
                d.addCallback(lg.cb, debug=_Debug, debug_level=_DebugLevel, method='groups.write_group_key_to_suppliers')
                d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='groups.write_group_key_to_suppliers')
            # TODO: build some kind of retry mechanism - if some supplier did not received the key
            l.append(d)
    return DeferredList(l, consumeErrors=True)

#------------------------------------------------------------------------------

def load_groups():
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    if not os.path.isdir(groups_dir):
        bpio._dirs_make(groups_dir)
    brokers_dir = os.path.join(service_dir, 'brokers')
    if not os.path.isdir(brokers_dir):
        bpio._dirs_make(brokers_dir)
    for group_key_id in os.listdir(groups_dir):
        if group_key_id not in known_groups():
            known_groups()[group_key_id] = {
                'last_sequence_id': -1,
                'active': False,
                'archive_folder_path': None,
            }
        group_path = os.path.join(groups_dir, group_key_id)
        group_info = jsn.loads_text(local_fs.ReadTextFile(group_path))
        if group_info:
            known_groups()[group_key_id] = group_info
    for customer_id in os.listdir(brokers_dir):
        customer_path = os.path.join(brokers_dir, customer_id)
        for broker_id in os.listdir(customer_path):
            if customer_id not in known_brokers():
                known_brokers()[customer_id] = [None, ] * REQUIRED_BROKERS_COUNT
            if broker_id in known_brokers(customer_id):
                lg.warn('broker %r already exist' % broker_id)
                continue
            broker_path = os.path.join(customer_path, broker_id)
            broker_info = jsn.loads_text(local_fs.ReadTextFile(broker_path))
            known_brokers()[customer_id][int(broker_info['position'])] = broker_id


def save_group_info(group_key_id):
    if not is_group_exist(group_key_id):
        lg.warn('group %r is not known' % group_key_id)
        return False
    group_info = known_groups()[group_key_id]
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
    if not is_group_exist(group_key_id):
        return -1
    return known_groups()[group_key_id]['last_sequence_id']


def set_last_sequence_id(group_key_id, last_sequence_id):
    if not is_group_exist(group_key_id):
        lg.warn('group %r is not known' % group_key_id)
        return False
    known_groups()[group_key_id]['last_sequence_id'] = last_sequence_id
    return True


def get_archive_folder_path(group_key_id):
    if not is_group_exist(group_key_id):
        return None
    return known_groups()[group_key_id].get('archive_folder_path', None)


def set_archive_folder_path(group_key_id, archive_folder_path):
    if not is_group_exist(group_key_id):
        lg.warn('group %r is not known' % group_key_id)
        return False
    known_groups()[group_key_id]['archive_folder_path'] = archive_folder_path
    return True

#------------------------------------------------------------------------------

def set_broker(customer_id, broker_id, position=0):
    service_dir = settings.ServiceDir('service_private_groups')
    brokers_dir = os.path.join(service_dir, 'brokers')
    customer_dir = os.path.join(brokers_dir, customer_id)
    broker_path = os.path.join(customer_dir, broker_id)
    if os.path.isfile(broker_path):
        lg.warn('broker %r already exist for customer %r, overwriting' % (broker_id, customer_id, ))
    if not os.path.isdir(customer_dir):
        bpio._dirs_make(customer_dir)
    broker_info = {
        'position': position,
    }
    if not local_fs.WriteTextFile(broker_path, jsn.dumps(broker_info)):
        lg.err('failed to set broker %r at position %d for customer %r' % (broker_id, position, customer_id, ))
        return False
    known_brokers(customer_id)[position] = broker_id
    if _Debug:
        lg.args(_DebugLevel, customer_id=customer_id, broker_id=broker_id, broker_info=broker_info)
    return True


def clear_broker(customer_id, position):
    service_dir = settings.ServiceDir('service_private_groups')
    brokers_dir = os.path.join(service_dir, 'brokers')
    customer_dir = os.path.join(brokers_dir, customer_id)
    if not os.path.isdir(customer_dir):
        if _Debug:
            lg.args(_DebugLevel, customer_id=customer_id, position=position)
        return False
    to_be_erased = []
    for broker_id in os.listdir(customer_dir):
        broker_path = os.path.join(customer_dir, broker_id)
        broker_info = jsn.loads_text(local_fs.ReadTextFile(broker_path))
        if not broker_info:
            to_be_erased.append(broker_id)
            lg.warn('found empty broker info for customer %r : %r' % (customer_id, broker_id, ))
            continue
        if broker_info.get('position') != position:
            continue
        to_be_erased.append(broker_id)
    if not to_be_erased:
        if _Debug:
            lg.args(_DebugLevel, customer_id=customer_id, position=position, to_be_erased=to_be_erased)
        return False
    removed = []
    for broker_id in to_be_erased:
        broker_path = os.path.join(customer_dir, broker_id)
        os.remove(broker_path)
        removed.append(broker_path)
    if _Debug:
        lg.args(_DebugLevel, customer_id=customer_id, position=position, removed=removed)
    return True


def clear_brokers(customer_id):
    service_dir = settings.ServiceDir('service_private_groups')
    brokers_dir = os.path.join(service_dir, 'brokers')
    customer_dir = os.path.join(brokers_dir, customer_id)
    known_brokers(customer_id, erase_brokers=True)
    if os.path.isdir(customer_dir):
        bpio.rmdir_recursive(customer_dir, ignore_errors=True)

#------------------------------------------------------------------------------

def set_group_active(group_key_id, value):
    if not is_group_exist(group_key_id):
        lg.warn('group %r is not known' % group_key_id)
        return False
    old_value = known_groups()[group_key_id]['active']
    known_groups()[group_key_id]['active'] = value
    if old_value != value:
        lg.info('group %r "active" status changed: %r -> %r' % (group_key_id, old_value, value, ))
    return True
