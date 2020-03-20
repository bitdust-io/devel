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
    * :red:`brokers-fialed`
    * :red:`brokers-found`
    * :red:`brokers-hired`
    * :red:`brokers-not-found`
    * :red:`connect`
    * :red:`dht-read-failed`
    * :red:`init`
    * :red:`instant`
    * :red:`message-in`
    * :red:`queue-in-sync`
    * :red:`queue-pull`
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

from lib import strng
from lib import utime
from lib import jsn
from lib import packetid

from main import events
from main import settings

from system import local_fs
from system import bpio

from crypt import my_keys

from dht import dht_relations

from chat import message

from p2p import lookup
from p2p import p2p_service_seeker
from p2p import commands
from p2p import p2p_service

from userid import global_id
from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

_ActiveGroupMembers = {}
_ActiveGroupMembersByIDURL = {}
_ActiveGroups = {}

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

#------------------------------------------------------------------------------

def load_groups():
    service_dir = settings.ServiceDir('service_private_groups')
    groups_dir = os.path.join(service_dir, 'groups')
    for group_key_id in os.listdir(groups_dir):
        if group_key_id not in groups():
            groups()[group_key_id] = {
                'brokers': {},
                'last_sequence_id': -1,
            }
        brokers_dir = os.path.join(groups_dir, group_key_id, 'brokers')
        for broker_id in os.listdir(brokers_dir):
            if broker_id in groups()[group_key_id]['brokers']:
                lg.warn('broker %r already exist in groups %r' % (broker_id, group_key_id, ))
                continue
            broker_path = os.path.join(brokers_dir, broker_id)
            broker_info = jsn.loads_text(local_fs.ReadTextFile(broker_path))
            groups()[group_key_id]['brokers'][broker_id] = broker_info

#------------------------------------------------------------------------------

def is_group_exist(group_key_id):
    return group_key_id in groups()


def create_group(group_key_id):
    if is_group_exist(group_key_id):
        return False
    service_dir = settings.ServiceDir('service_private_groups')
    group_dir = os.path.join(service_dir, 'groups', group_key_id)
    brokers_dir = os.path.join(group_dir, 'brokers')
    bpio._dirs_make(brokers_dir)
    groups()[group_key_id] = {
        'brokers': {},
        'last_sequence_id': -1,
    }
    return True


def is_broker_exist(group_key_id, broker_id):
    if group_key_id not in groups():
        return False
    return broker_id in groups()[group_key_id]['brokers']


def set_broker(group_key_id, broker_id, position=0):
    if not is_group_exist(group_key_id):
        return False
    if is_broker_exist(group_key_id, broker_id):
        return False
    service_dir = settings.ServiceDir('service_private_groups')
    brokers_dir = os.path.join(service_dir, 'groups', group_key_id, 'brokers')
    broker_path = os.path.join(brokers_dir, broker_id)
    if os.path.isfile(broker_path):
        return False
    broker_info = {
        'position': position,
    }
    if not local_fs.WriteTextFile(broker_path, jsn.dumps(broker_info)):
        lg.err('failed to set broker %r at position %d to group %r' % (broker_id, position, group_key_id, ))
        return False
    groups()[group_key_id]['brokers'][broker_id] = broker_info
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id, broker_id=broker_id, broker_info=broker_info)
    return True


def clear_brokers(group_key_id):
    if not is_group_exist(group_key_id):
        return False
    service_dir = settings.ServiceDir('service_private_groups')
    brokers_dir = os.path.join(service_dir, 'groups', group_key_id, 'brokers')
    groups()[group_key_id]['brokers'].clear()
    list_brokers = os.listdir(brokers_dir)
    for broker_id in list_brokers:
        broker_path = os.path.join(brokers_dir, broker_id)
        os.remove(broker_path)


def get_brokers(group_key_id):
    if not is_group_exist(group_key_id):
        return []
    return groups()[group_key_id]['brokers']


def get_last_sequence_id(group_key_id):
    if not is_group_exist(group_key_id):
        return -1
    return groups()[group_key_id]['last_sequence_id']

#------------------------------------------------------------------------------

def register_group_memeber(A):
    """
    """
    global _ActiveGroupMembers
    global _ActiveGroupMembersByIDURL
    if A.key_id in _ActiveGroupMembers:
        raise Exception('group_memeber already exist')
    if id_url.is_not_in(A.group_creator_idurl, _ActiveGroupMembersByIDURL):
        _ActiveGroupMembersByIDURL[A.group_creator_idurl] = []
    _ActiveGroupMembersByIDURL[A.group_creator_idurl].append(A)
    _ActiveGroupMembers[A.key_id] = A


def unregister_group_memeber(A):
    """
    """
    global _ActiveGroupMembers
    global _ActiveGroupMembersByIDURL
    _ActiveGroupMembers.pop(A.key_id, None)
    if id_url.is_not_in(A.group_creator_idurl, _ActiveGroupMembersByIDURL):
        lg.warn('for given customer idurl did not found in active group memebers lists')
    else:
        _ActiveGroupMembersByIDURL[A.group_creator_idurl] = []

#------------------------------------------------------------------------------

def list_active_group_memebers():
    """
    """
    global _ActiveGroupMembers
    return list(_ActiveGroupMembers.keys())

def get_active_group_memeber(group_key_id):
    """
    """
    global _ActiveGroupMembers
    if group_key_id not in _ActiveGroupMembers:
        return None
    return _ActiveGroupMembers[group_key_id]


def find_active_group_memebers(group_creator_idurl):
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

class GroupQueueMember(automat.Automat):
    """
    This class implements all the functionality of ``group_member()`` state machine.
    """

    def __init__(self, group_key_id, member_idurl=None, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
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
        super(GroupQueueMember, self).__init__(
            name="member_%s$%s" % (self.group_queue_alias[:10], self.group_owner_id),
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
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
        register_group_memeber(self)
        return automat_index

    def unregister(self):
        """
        """
        unregister_group_memeber(self)
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
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect' or ( event == 'instant' and self.isDeadBroker(*args, **kwargs) ):
                self.state = 'DHT_READ?'
                self.doDHTReadBrokers(*args, **kwargs)
        #---DHT_READ?---
        elif self.state == 'DHT_READ?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'brokers-not-found':
                self.state = 'HIRE_BROKERS'
                self.doLookupBrokers(*args, **kwargs)
            elif event == 'dht-read-failed':
                self.state = 'DISCONNECTED'
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'brokers-found' and not self.isDeadBroker(*args, **kwargs):
                self.state = 'QUEUE?'
                self.doRememberBrokers(*args, **kwargs)
                self.doReadQueue(*args, **kwargs)
            elif event == 'brokers-found' and self.isDeadBroker(*args, **kwargs):
                self.state = 'HIRE_BROKERS'
                self.doLookupRotateBrokers(*args, **kwargs)
        #---HIRE_BROKERS---
        elif self.state == 'HIRE_BROKERS':
            if event == 'brokers-hired':
                self.state = 'QUEUE?'
                self.doRememberBrokers(*args, **kwargs)
                self.doReadQueue(*args, **kwargs)
            elif event == 'brokers-fialed':
                self.state = 'DISCONNECTED'
                self.doForgetBrokers(*args, **kwargs)
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---QUEUE?---
        elif self.state == 'QUEUE?':
            if event == 'queue-in-sync':
                self.state = 'IN_SYNC!'
                self.doConnected(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'queue-read-failed':
                self.state = 'DISCONNECTED'
                self.doMarkDeadBroker(*args, **kwargs)
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'message-in':
                self.doProcess(*args, **kwargs)
        #---IN_SYNC!---
        elif self.state == 'IN_SYNC!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'message-in' and self.isInSync(*args, **kwargs):
                self.doProcess(*args, **kwargs)
            elif event == 'queue-pull' or ( event == 'message-in' and not self.isInSync(*args, **kwargs) ):
                self.state = 'QUEUE?'
                self.doReadQueue(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isDeadBroker(self, *args, **kwargs):
        """
        Condition method.
        """

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

    def doDHTReadBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        result = dht_relations.read_customer_message_brokers(self.group_creator_idurl)
        # TODO: add more validations of dht_result
        result.addCallback(self._on_read_customer_message_brokers)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member.doDHTReadBrokers')
        result.addErrback(lambda err: self.automat('dht-read-failed', err))

    def doLookupBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        p2p_service_seeker.connect_random_node(
            'service_message_broker',
            lookup_method=lookup.random_message_broker,
            service_params=self._do_prepare_service_request_params,
            exclude_nodes=self.connected_message_brokers,
        ).addBoth(self._on_message_broker_lookup_finished)

    def doLookupRotateBrokers(self, *args, **kwargs):
        """
        Action method.
        """

    def doRememberBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        brokers_list = args[0]
        for position, broker_idurl in enumerate(brokers_list):
            broker_id = global_id.idurl2glob(broker_idurl)
            set_broker(self.group_key_id, broker_id, position)
            if position == 0:
                self.active_broker_id = broker_id
                self.active_queue_id = global_id.MakeGlobalQueueID(
                    queue_alias=self.group_queue_alias,
                    owner_id=self.group_owner_id,
                    supplier_id=self.active_broker_id,
                )

    def doForgetBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        clear_brokers(self.group_key_id)

    def doReadQueue(self, *args, **kwargs):
        """
        Action method.
        """
        result = message.send_message(
            json_data={
                'created': utime.get_sec1970(),
                'payload': 'queue-read',
                'last_sequence_id': get_last_sequence_id(self.group_key_id),
                'queue_id': self.active_queue_id,
                'consumer_id': self.member_id,
            },
            recipient_global_id=self.active_broker_id,
            packet_id='queue_%s_%s' % (self.active_queue_id, packetid.UniqueID(), ),
        )
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member.doReadQueue')
        result.addErrback(lambda err: self.automat('queue-read-failed', err))

    def doMarkDeadBroker(self, *args, **kwargs):
        """
        Action method.
        """

    def doConnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doDisconnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doProcess(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

    def _do_prepare_service_request_params(self, possible_broker_idurl):
        queue_id = global_id.MakeGlobalQueueID(
            queue_alias=self.group_queue_alias,
            owner_id=self.group_owner_id,
            supplier_id=global_id.idurl2glob(possible_broker_idurl),
        )
        group_key_info = my_keys.get_key_info(self.group_key_id, include_private=False)
        return {
            'action': 'queue-connect',
            'queue_id': queue_id,
            'consumer_id': self.member_id,
            'producer_id': self.member_id,
            'group_key': group_key_info,
        }

    def _do_send_message_to_broker(self, json_payload):
        result = message.send_message(
            json_data={
                'created': utime.get_sec1970(),
                'payload': json_payload,
                'queue_id': self.active_queue_id,
                'producer_id': self.member_id,
            },
            recipient_global_id=self.broker_id,
            packet_id='queue_%s_%s' % (self.active_queue_id, packetid.UniqueID(), ),
        )
        return result

    def _on_read_customer_message_brokers(self, idurls):
        if not idurls:
            self.automat('brokers-not-found')
        else:
            self.automat('brokers-found', idurls)

    def _on_message_broker_lookup_finished(self, idurl):
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl)
        if not idurl:
            self.automat('brokers-failed')
            return None
        if _Debug:
            lg.out(_DebugLevel, 'contract_chain_consumer._on_miner_lookup_finished SUCCESS, miner %s connected' % self.connected_miner)
        brokers_list = [idurl, ]
        self.automat('brokers-hired', brokers_list)
