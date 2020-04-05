#!/usr/bin/env python
# group_member.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
#
# This file (group_member.py) is part of BitDust Software.
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


"""
.. module:: group_member
.. role:: red

BitDust group_member() Automat

EVENTS:
    * :red:`brokers-connected`
    * :red:`brokers-failed`
    * :red:`brokers-found`
    * :red:`brokers-hired`
    * :red:`brokers-not-found`
    * :red:`dht-read-failed`
    * :red:`init`
    * :red:`instant`
    * :red:`join`
    * :red:`leave`
    * :red:`message-in`
    * :red:`push-message`
    * :red:`queue-in-sync`
    * :red:`queue-read-failed`
    * :red:`shutdown`
"""



#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import utime
from lib import jsn
from lib import packetid

from main import settings
from main import events

from system import local_fs
from system import bpio

from crypt import my_keys

from dht import dht_relations

from stream import message

from p2p import lookup
from p2p import p2p_service_seeker

from userid import global_id
from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

REQUIRED_BROKERS_COUNT = 3

#------------------------------------------------------------------------------

_ActiveGroupMembers = {}
_ActiveGroupMembersByIDURL = {}
_ActiveGroups = {}
_KnownBrokers = {}

#------------------------------------------------------------------------------

def init():
    if _Debug:
        lg.out(_DebugLevel, 'group_member.init')
    load_groups()


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'group_member.shutdown')

#------------------------------------------------------------------------------

def groups():
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

def load_groups():
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    if not os.path.isdir(groups_dir):
        bpio._dirs_make(groups_dir)
    brokers_dir = os.path.join(service_dir, 'brokers')
    if not os.path.isdir(brokers_dir):
        bpio._dirs_make(brokers_dir)
    for group_key_id in os.listdir(groups_dir):
        if group_key_id not in groups():
            groups()[group_key_id] = {
                'last_sequence_id': -1,
                'active': False,
            }
        group_path = os.path.join(groups_dir, group_key_id)
        group_info = jsn.loads_text(local_fs.ReadTextFile(group_path))
        if group_info:
            groups()[group_key_id] = group_info
    for customer_id in os.listdir(brokers_dir):
        customer_path = os.path.join(brokers_dir, customer_id)
        for broker_id in os.listdir(customer_path):
            if customer_id not in known_brokers():
                known_brokers()[customer_id] = [None, ] * REQUIRED_BROKERS_COUNT
            if broker_id in known_brokers(customer_id).values():
                lg.warn('broker %r already exist' % broker_id)
                continue
            broker_path = os.path.join(customer_path, broker_id)
            broker_info = jsn.loads_text(local_fs.ReadTextFile(broker_path))
            known_brokers()[customer_id][int(broker_info['position'])] = broker_id


def save_group(group_key_id):
    if group_key_id not in groups():
        return False
    group_info = groups()[group_key_id]
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    group_info_path = os.path.join(groups_dir, group_key_id)
    if not os.path.isdir(groups_dir):
        bpio._dirs_make(groups_dir)
    ret = local_fs.WriteTextFile(group_info_path, jsn.dumps(group_info))
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id, group_info_path=group_info_path, ret=ret)
    return ret


def erase_group(group_key_id):
    if group_key_id not in groups():
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

#------------------------------------------------------------------------------

def is_group_exist(group_key_id):
    return group_key_id in groups()


def create_group(group_key_id):
    if is_group_exist(group_key_id):
        return False
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    if not os.path.isdir(groups_dir):
        bpio._dirs_make(groups_dir)
    groups()[group_key_id] = {
        'last_sequence_id': -1,
        'active': False,
    }
    return True


def get_last_sequence_id(group_key_id):
    if not is_group_exist(group_key_id):
        return -1
    return groups()[group_key_id]['last_sequence_id']


def set_last_sequence_id(group_key_id, last_sequence_id):
    if not is_group_exist(group_key_id):
        return False
    groups()[group_key_id]['last_sequence_id'] = last_sequence_id
    return True

#------------------------------------------------------------------------------

def set_broker(customer_id, broker_id, position=0):
    service_dir = settings.ServiceDir('service_private_groups')
    brokers_dir = os.path.join(service_dir, 'brokers')
    customer_dir = os.path.join(brokers_dir, customer_id)
    broker_path = os.path.join(customer_dir, broker_id)
    if os.path.isfile(broker_path):
        lg.warn('broker %r already exist for customer %r' % (broker_id, customer_id, ))
        return False
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


def clear_brokers(customer_id):
    service_dir = settings.ServiceDir('service_private_groups')
    brokers_dir = os.path.join(service_dir, 'brokers')
    customer_dir = os.path.join(brokers_dir, customer_id)
    known_brokers(customer_id, erase_brokers=True)
    if os.path.isdir(customer_dir):
        bpio.rmdir_recursive(customer_dir, ignore_errors=True)

#------------------------------------------------------------------------------

def register_group_member(A):
    """
    """
    global _ActiveGroupMembers
    global _ActiveGroupMembersByIDURL
    if _Debug:
        lg.args(_DebugLevel, instance=repr(A))
    if A.group_key_id in _ActiveGroupMembers:
        raise Exception('group_member already exist')
    _ActiveGroupMembers[A.group_key_id] = A
    if id_url.is_not_in(A.group_creator_idurl, _ActiveGroupMembersByIDURL):
        _ActiveGroupMembersByIDURL[A.group_creator_idurl] = []
    _ActiveGroupMembersByIDURL[A.group_creator_idurl].append(A)
    if not is_group_exist(A.group_key_id):
        create_group(A.group_key_id)


def unregister_group_member(A):
    """
    """
    global _ActiveGroupMembers
    global _ActiveGroupMembersByIDURL
    if _Debug:
        lg.args(_DebugLevel, instance=repr(A))
    if id_url.is_not_in(A.group_creator_idurl, _ActiveGroupMembersByIDURL):
        lg.warn('for given customer idurl %r did not found active group members list' % A.group_creator_idurl)
    else:
        if A in _ActiveGroupMembersByIDURL[A.group_creator_idurl]:
            _ActiveGroupMembersByIDURL[A.group_creator_idurl].remove(A)
        else:
            lg.warn('group_member() instance not found for customer %r' % A.group_creator_idurl)
    _ActiveGroupMembers.pop(A.group_key_id, None)

#------------------------------------------------------------------------------

def list_active_group_members():
    """
    """
    global _ActiveGroupMembers
    return list(_ActiveGroupMembers.keys())


def get_active_group_member(group_key_id):
    """
    """
    global _ActiveGroupMembers
    if group_key_id not in _ActiveGroupMembers:
        return None
    return _ActiveGroupMembers[group_key_id]


def find_active_group_members(group_creator_idurl):
    """
    """
    global _ActiveGroupMembersByIDURL
    result = []
    for automat_index in _ActiveGroupMembersByIDURL.values():
        A = automat.objects().get(automat_index, None)
        if not A:
            continue
        if A.group_creator_idurl == group_creator_idurl:
            result.append(A)
    return result

#------------------------------------------------------------------------------

def set_active(group_key_id, value):
    if not is_group_exist(group_key_id):
        return False
    old_value = groups()[group_key_id]['active']
    groups()[group_key_id]['active'] = value
    if old_value != value:
        lg.info('group %r "active" status changed: %r -> %r' % (group_key_id, old_value, value, ))
    return True

#------------------------------------------------------------------------------

class GroupMember(automat.Automat):
    """
    This class implements all the functionality of ``group_member()`` state machine.
    """

    def __init__(self, group_key_id, member_idurl=None, debug_level=0, log_events=_Debug, log_transitions=_Debug, **kwargs):
        """
        Builds `group_member()` state machine.
        """
        self.member_idurl = member_idurl or my_id.getIDURL()
        self.member_id = self.member_idurl.to_id()
        self.group_key_id = group_key_id
        self.group_glob_id = global_id.ParseGlobalID(self.group_key_id)
        self.group_queue_alias = self.group_glob_id['key_alias']
        self.group_creator_id = self.group_glob_id['customer']
        self.group_creator_idurl = self.group_glob_id['idurl']
        self.active_broker_id = None
        self.active_queue_id = None
        self.dead_broker = None
        self.hired_brokers = {}
        self.connected_brokers = {}
        self.missing_brokers = set()
        self.latest_dht_brokers = None
        self.last_sequence_id = get_last_sequence_id(self.group_key_id)
        super(GroupMember, self).__init__(
            name="group_member_%s$%s" % (self.group_queue_alias[:10], self.group_creator_id),
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=False,
            **kwargs
        )

    def to_json(self):
        return {
            'member_id': self.member_id,
            'group_key_id': self.group_key_id,
            'alias': self.group_glob_id['key_alias'],
            'label': my_keys.get_label(self.group_key_id),
            'creator': self.group_creator_idurl,
            'active_broker_id': self.active_broker_id,
            'active_queue_id': self.active_queue_id,
            'latest_known_brokers': self.latest_dht_brokers,
            'connected_brokers': self.connected_brokers,
            'last_sequence_id': self.last_sequence_id,
            'state': self.state,
        }

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `group_member()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `group_member()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `group_member()`
        but automat state was not changed.
        """

    def register(self):
        """
        """
        automat_index = automat.Automat.register(self)
        register_group_member(self)
        return automat_index

    def unregister(self):
        """
        """
        unregister_group_member(self)
        return automat.Automat.unregister(self)

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'DISCONNECTED'
                self.doInit(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'leave' or event == 'shutdown':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'join' or ( event == 'instant' and self.isDeadBroker(*args, **kwargs) ):
                self.state = 'DHT_READ?'
                self.doActivate(*args, **kwargs)
                self.doDHTReadBrokers(*args, **kwargs)
        #---DHT_READ?---
        elif self.state == 'DHT_READ?':
            if event == 'dht-read-failed':
                self.state = 'DISCONNECTED'
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'brokers-found' and not self.isDeadBroker(*args, **kwargs):
                self.state = 'BROKERS?'
                self.doConnectBrokers(*args, **kwargs)
            elif ( event == 'brokers-found' and self.isDeadBroker(*args, **kwargs) ) or event == 'brokers-not-found':
                self.state = 'BROKERS?'
                self.doLookupRotateBrokers(*args, **kwargs)
            elif event == 'shutdown' or event == 'leave':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doCancelService(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---QUEUE?---
        elif self.state == 'QUEUE?':
            if event == 'queue-in-sync':
                self.state = 'IN_SYNC!'
                self.doConnected(*args, **kwargs)
            elif event == 'queue-read-failed':
                self.state = 'DISCONNECTED'
                self.doMarkDeadBroker(*args, **kwargs)
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'message-in':
                self.doProcess(*args, **kwargs)
            elif event == 'push-message':
                self.doPublishLater(*args, **kwargs)
            elif event == 'shutdown' or event == 'leave':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doCancelService(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---IN_SYNC!---
        elif self.state == 'IN_SYNC!':
            if event == 'message-in' and self.isInSync(*args, **kwargs):
                self.doProcess(*args, **kwargs)
            elif event == 'push-message':
                self.doPublish(*args, **kwargs)
            elif event == 'shutdown' or event == 'leave':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doCancelService(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'join' or ( event == 'message-in' and not self.isInSync(*args, **kwargs) ):
                self.state = 'QUEUE?'
                self.doReadQueue(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---BROKERS?---
        elif self.state == 'BROKERS?':
            if event == 'brokers-hired' or event == 'brokers-connected':
                self.state = 'QUEUE?'
                self.doRememberBrokers(event, *args, **kwargs)
                self.doReadQueue(*args, **kwargs)
            elif event == 'brokers-failed':
                self.state = 'DISCONNECTED'
                self.doForgetBrokers(*args, **kwargs)
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'shutdown' or event == 'leave':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doCancelService(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        return None

    def isDeadBroker(self, *args, **kwargs):
        """
        Condition method.
        """
        return None in args[0]

    def isInSync(self, *args, **kwargs):
        """
        Condition method.
        """
        # TODO: ...
        return True

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        message.consume_messages(
            consumer_id=self.name,
            callback=self._on_read_queue_messages,
            direction='incoming',
            message_types=['queue_message', ],
        )

    def doActivate(self, *args, **kwargs):
        """
        Action method.
        """
        set_active(self.group_key_id, True)
        save_group(self.group_key_id)

    def doDHTReadBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        self.latest_dht_brokers = None
        result = dht_relations.read_customer_message_brokers(self.group_creator_idurl)
        # TODO: add more validations of dht_result
        result.addCallback(self._on_read_customer_message_brokers)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member.doDHTReadBrokers')
        result.addErrback(lambda err: self.automat('dht-read-failed', err))

    def doLookupRotateBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_lookup_replace_brokers(args[0])

    def doConnectBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_connect_known_brokers(args[0])

    def doRememberBrokers(self, event, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, event, *args, **kwargs)
        self.active_broker_id = None
        self.active_queue_id = None
        if event == 'brokers-hired':
            for position, broker_idurl in self.hired_brokers.items():
                if not broker_idurl:
                    continue
                broker_id = global_id.idurl2glob(broker_idurl)
                set_broker(self.group_creator_id, broker_id, position)
                if position == 0:
                    self.active_broker_id = broker_id
                    self.active_queue_id = global_id.MakeGlobalQueueID(
                        queue_alias=self.group_queue_alias,
                        owner_id=self.group_creator_id,
                        supplier_id=self.active_broker_id,
                    )
        elif event == 'brokers-found':
            for broker_info in args[0]:
                if not broker_info['broker_idurl']:
                    continue
                broker_id = global_id.idurl2glob(broker_info['broker_idurl'])
                set_broker(self.group_creator_id, broker_id, broker_info['position'])
                if broker_info['position'] == 0:
                    self.active_broker_id = broker_id
                    self.active_queue_id = global_id.MakeGlobalQueueID(
                        queue_alias=self.group_queue_alias,
                        owner_id=self.group_creator_id,
                        supplier_id=self.active_broker_id,
                    )
        elif event == 'brokers-connected':
            for position, broker_idurl in self.connected_brokers.items():
                if not broker_idurl:
                    continue
                broker_id = global_id.idurl2glob(broker_idurl)
                set_broker(self.group_creator_id, broker_id, position)
                if position == 0:
                    self.active_broker_id = broker_id
                    self.active_queue_id = global_id.MakeGlobalQueueID(
                        queue_alias=self.group_queue_alias,
                        owner_id=self.group_creator_id,
                        supplier_id=self.active_broker_id,
                    )
        else:
            raise Exception('unexpected event')
        if self.active_broker_id is None:
            raise Exception('no brokers found or hired') 
        self.hired_brokers.clear()
        self.missing_brokers.clear()

    def doForgetBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        clear_brokers(self.group_creator_id)

    def doReadQueue(self, *args, **kwargs):
        """
        Action method.
        """
        result = message.send_message(
            json_data={
                'created': utime.get_sec1970(),
                'payload': 'queue-read',
                'last_sequence_id': self.last_sequence_id,
                'queue_id': self.active_queue_id,
                'consumer_id': self.member_id,
            },
            recipient_global_id=self.active_broker_id,
            packet_id='queue_%s_%s' % (self.active_queue_id, packetid.UniqueID()),
            skip_handshake=True,
            fire_callbacks=False,
        )
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member.doReadQueue')
        result.addErrback(lambda err: self.automat('queue-read-failed', err))

    def doProcess(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, **kwargs)
        message.push_group_message(**kwargs)

    def doPublish(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_send_message_to_broker(json_payload=kwargs['json_payload'])

    def doPublishLater(self, *args, **kwargs):
        """
        Action method.
        """

    def doMarkDeadBroker(self, *args, **kwargs):
        """
        Action method.
        """

    def doConnected(self, *args, **kwargs):
        """
        Action method.
        """
        events.send('group-connected', data=dict(
            group_key_id=self.group_key_id,
            member_id=self.member_id,
            queue_id=self.active_queue_id,
        ))

    def doDisconnected(self, *args, **kwargs):
        """
        Action method.
        """
        events.send('group-disconnected', data=dict(
            group_key_id=self.group_key_id,
            member_id=self.member_id,
            queue_id=self.active_queue_id,
        ))

    def doDeactivate(self, event, *args, **kwargs):
        """
        Action method.
        """
        if event == 'leave':
            set_active(self.group_key_id, False)
            save_group(self.group_key_id)
            if kwargs.get('erase_key', False):
                if my_keys.is_key_registered(self.group_key_id):
                    my_keys.erase_key(self.group_key_id)
                else:
                    lg.warn('key %r not registered, can not be erased' % self.group_key_id)
        else:
            save_group(self.group_key_id)

    def doCancelService(self, event, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        message.clear_consumer_callbacks(self.name)
        self.destroy()
        self.member_idurl = None
        self.member_id = None
        self.group_key_id = None
        self.group_glob_id = None
        self.group_queue_alias = None
        self.group_creator_id = None
        self.group_creator_idurl = None
        self.active_broker_id = None
        self.active_queue_id = None
        self.dead_broker = None
        self.hired_brokers = None
        self.connected_brokers = None
        self.missing_brokers = None
        self.latest_dht_brokers = None

    def _do_prepare_service_request_params(self, possible_broker_idurl, desired_broker_position):
        queue_id = global_id.MakeGlobalQueueID(
            queue_alias=self.group_queue_alias,
            owner_id=self.group_creator_id,
            supplier_id=global_id.idurl2glob(possible_broker_idurl),
        )
        group_key_info = my_keys.get_key_info(self.group_key_id, include_private=False, include_signature=True)
        service_request_params = {
            'action': 'queue-connect',
            'position': desired_broker_position,
            'queue_id': queue_id,
            'consumer_id': self.member_id,
            'producer_id': self.member_id,
            'group_key': group_key_info,
        }
        if _Debug:
            lg.args(_DebugLevel, service_request_params=service_request_params)
        return service_request_params

    def _do_send_message_to_broker(self, json_payload):
        result = message.send_message(
            json_data={
                'created': utime.get_sec1970(),
                'payload': json_payload,
                'queue_id': self.active_queue_id,
                'producer_id': self.member_id,
            },
            recipient_global_id=self.active_broker_id,
            packet_id='queue_%s_%s' % (self.active_queue_id, packetid.UniqueID(), ),
            skip_handshake=True,
            fire_callbacks=False,
        )
        return result

    def _do_lookup_replace_brokers(self, existing_brokers):
        self.hired_brokers = {}
        self.connected_brokers = {}
        self.missing_brokers = set()
        top_broker_pos = None
        for broker_pos in range(REQUIRED_BROKERS_COUNT):
            broker_at_position = None
            for existing_broker in existing_brokers:
                if existing_broker['position'] == broker_pos:
                    broker_at_position = existing_broker
                    break
            if not broker_at_position:
                lg.warn('not found broker for %r at position %d' % (self.group_key_id, broker_pos, ))
                self.missing_brokers.add(broker_pos)
                continue
            try:
                broker_idurl = broker_at_position['broker_idurl']
            except IndexError:
                broker_idurl = None
            if not broker_idurl:
                self.missing_brokers.add(broker_pos)
                lg.warn('broker is empty for %r at position %d' % (self.group_key_id, broker_pos, ))
                continue
            if _Debug:
                lg.dbg(_DebugLevel, 'found broker %r at position %r for %r' % (broker_idurl, broker_pos, self.group_key_id, ))
            if top_broker_pos is None:
                top_broker_pos = broker_pos
            if broker_pos < top_broker_pos:
                top_broker_pos = broker_pos
        if top_broker_pos is None:
            lg.warn('not brokers found, start new lookup at position 0')
            self._do_lookup_one_broker(0)
            return
        if top_broker_pos > 0:
            lg.warn('first broker not exist, start new lookup at position 0')
            self._do_lookup_one_broker(0)
            return
        lg.err('did not found any missing brokers, but expect at least one dead')
        self.automat('brokers-hired')

    def _do_lookup_one_broker(self, broker_pos):
        connected_brokers_idurls = list(map(global_id.glob2idurl, filter(None, known_brokers(self.group_creator_id))))
        result = p2p_service_seeker.connect_random_node(
            lookup_method=lookup.random_message_broker,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params(idurl, broker_pos),
            exclude_nodes=connected_brokers_idurls,
        )
        result.addCallback(self._on_broker_hired, broker_pos)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member._do_lookup_one_broker')
        result.addErrback(self._on_message_broker_lookup_failed, broker_pos)

    def _do_connect_known_brokers(self, existing_brokers):
        if _Debug:
            lg.args(_DebugLevel, existing_brokers=existing_brokers)
        self.connected_brokers = {}
        self.missing_brokers = set()
        top_broker_pos = None
        top_broker_idurl = None
        for broker_pos in range(REQUIRED_BROKERS_COUNT):
            broker_at_position = None
            for existing_broker in existing_brokers:
                if existing_broker['position'] == broker_pos:
                    broker_at_position = existing_broker
                    break
            if not broker_at_position:
                lg.warn('not found broker for %r at position %d' % (self.group_key_id, broker_pos, ))
                self.missing_brokers.add(broker_pos)
                continue
            try:
                broker_idurl = broker_at_position['broker_idurl']
            except IndexError:
                broker_idurl = None
            if not broker_idurl:
                self.missing_brokers.add(broker_pos)
                lg.warn('broker is empty for %r at position %d' % (self.group_key_id, broker_pos, ))
                continue
            if _Debug:
                lg.dbg(_DebugLevel, 'found broker %r at position %r for %r' % (broker_idurl, broker_pos, self.group_key_id, ))
            if top_broker_pos is None:
                top_broker_pos = broker_pos
                top_broker_idurl = broker_idurl
            if broker_pos < top_broker_pos:
                top_broker_pos = broker_pos
                top_broker_idurl = broker_idurl
        if top_broker_idurl is None:
            raise Exception('not found any brokers')
        self._do_request_service_one_broker(top_broker_idurl, top_broker_pos)

    def _do_request_service_one_broker(self, broker_idurl, broker_pos):
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=broker_idurl,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params(idurl, broker_pos),
        )
        result.addCallback(self._on_broker_connected, broker_pos)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member._do_request_service_one_broker')
        result.addErrback(self._on_message_broker_lookup_failed, broker_pos)

    def _on_read_customer_message_brokers(self, brokers_info_list):
        if _Debug:
            lg.args(_DebugLevel, brokers=brokers_info_list)
        if not brokers_info_list:
            self.automat('brokers-not-found', [])
            return
        self.latest_dht_brokers = brokers_info_list
        self.automat('brokers-found', brokers_info_list)

    def _on_broker_hired(self, idurl, broker_pos):
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, broker_pos=broker_pos)
        self.hired_brokers[broker_pos] = idurl or None
        if idurl:
            self.connected_brokers[broker_pos] = idurl 
        self.missing_brokers.discard(broker_pos)
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, broker_pos=broker_pos, missing_brokers=self.missing_brokers,
                    hired_brokers=self.hired_brokers, connected_brokers=self.connected_brokers)
        if 0 not in self.missing_brokers and 0 in self.hired_brokers and self.hired_brokers[0]:
            self.automat('brokers-hired')
            return
        if not self.missing_brokers:
            if list(filter(None, self.hired_brokers.values())):
                lg.warn('some brokers hired, but broker at position 0 is still empty')
            else:
                lg.err('failed to hire any brokers')
            self.automat('brokers-failed')

    def _on_broker_connected(self, idurl, broker_pos):
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, broker_pos=broker_pos)
        if idurl:
            self.connected_brokers[broker_pos] = idurl
        self.missing_brokers.discard(broker_pos)
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl, broker_pos=broker_pos, missing_brokers=self.missing_brokers,
                    connected_brokers=self.connected_brokers)
        if 0 not in self.missing_brokers and 0 in self.connected_brokers:
            self.automat('brokers-connected')
            return
        if not self.missing_brokers:
            if self.connected_brokers:
                lg.warn('some brokers connected, but broker at position 0 is still empty')
            else:
                lg.err('failed to connect with any brokers')
            self.automat('brokers-failed')
            return
        if _Debug:
            lg.dbg(_DebugLevel, 'broker %d connected but some more missing brokers still: %r' % (broker_pos, self.missing_brokers, ))

    def _on_message_broker_lookup_failed(self, err, broker_pos):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        self.hired_brokers[broker_pos] = None
        self.missing_brokers.remove(broker_pos)
        if _Debug:
            lg.args(_DebugLevel, err=err, broker_pos=broker_pos, missing_brokers=self.missing_brokers, hired_brokers=self.hired_brokers)
        if not self.missing_brokers or (0 not in self.missing_brokers):
            if list(filter(None, self.hired_brokers.values())):
                self.automat('brokers-hired')
            else:
                self.automat('brokers-failed')

    def _on_read_queue_messages(self, json_messages):
        if not json_messages:
            return True
        if _Debug:
            lg.args(_DebugLevel, json_messages=json_messages)
        latest_known_sequence_id = -1
        received_group_messages = []
        for json_message in json_messages:
            try:
                msg_type = json_message.get('type', '')
                msg_direction = json_message['dir']
                # packet_id = json_message['id']
                # from_user = json_message['from']
                # to_user = json_message['to']
                msg_data = json_message['data']
            except:
                lg.exc()
                continue
            if msg_direction != 'incoming':
                continue
            if msg_type != 'queue_message':
                continue
            try:
                chunk_last_sequence_id = int(msg_data['last_sequence_id'])
                list_messages = msg_data['items']
            except:
                lg.exc()
                continue
            if chunk_last_sequence_id > latest_known_sequence_id:
                latest_known_sequence_id = chunk_last_sequence_id
            for one_message in list_messages:
                if one_message['sequence_id'] > latest_known_sequence_id:
                    lg.warn('invalid item sequence_id %d   vs.  last_sequence_id %d known' % (
                        one_message['sequence_id'], latest_known_sequence_id))
                    continue
                received_group_messages.append(dict(
                    json_message=one_message['payload'],
                    direction='incoming',
                    group_key_id=self.group_key_id,
                    producer_id=one_message['producer_id'],
                    sequence_id=one_message['sequence_id'],
                ))
        if not received_group_messages:
            if latest_known_sequence_id > self.last_sequence_id:
                # TODO: read messages from archive
                lg.warn('found queue latest sequence %d is ahead of my current position %d, need to read messages from archive' % (
                    latest_known_sequence_id, self.last_sequence_id, ))
                self.last_sequence_id = latest_known_sequence_id
                set_last_sequence_id(self.group_key_id, latest_known_sequence_id)
                save_group(self.group_key_id)
            if _Debug:
                lg.dbg(_DebugLevel, 'no new messages, queue in sync')
            self.automat('queue-in-sync')
            return True
        received_group_messages.sort(key=lambda m: m['sequence_id'])
        newly_processed = 0
        if _Debug:
            lg.args(_DebugLevel, my_last_sequence_id=self.last_sequence_id, received_group_messages=received_group_messages)
        for new_message in received_group_messages:
            if self.last_sequence_id + 1 == new_message['sequence_id']:
                self.last_sequence_id = new_message['sequence_id']
                newly_processed += 1
                if _Debug:
                    lg.dbg(_DebugLevel, 'new message consumed, last_sequence_id incremented to %d' % self.last_sequence_id)
                self.automat('message-in', **new_message)
        if newly_processed != len(received_group_messages):
            raise Exception('message sequence is broken by message broker %s, some messages were not consumed' % self.active_broker_id)
        if newly_processed and latest_known_sequence_id == self.last_sequence_id:
            set_last_sequence_id(self.group_key_id, self.last_sequence_id)
            save_group(self.group_key_id)
            if _Debug:
                lg.dbg(_DebugLevel, 'processed all messages, queue in sync, last_sequence_id=%d' % self.last_sequence_id)
            self.automat('queue-in-sync')
        return True
