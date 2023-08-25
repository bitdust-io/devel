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
    * :red:`broker-connect-ack`
    * :red:`broker-connect-failed`
    * :red:`broker-lookup-ack`
    * :red:`broker-lookup-failed`
    * :red:`brokers-all-connected`
    * :red:`brokers-changed`
    * :red:`brokers-found`
    * :red:`brokers-mismatch`
    * :red:`brokers-not-found`
    * :red:`brokers-ping-failed`
    * :red:`brokers-read`
    * :red:`dht-read-failed`
    * :red:`init`
    * :red:`instant`
    * :red:`join`
    * :red:`leave`
    * :red:`message-in`
    * :red:`message-pushed`
    * :red:`push-message`
    * :red:`push-message-failed`
    * :red:`queue-in-sync`
    * :red:`queue-is-ahead`
    * :red:`queue-read-failed`
    * :red:`reconnect`
    * :red:`replace-active-broker`
    * :red:`shutdown`
    * :red:`top-broker-ping-failed`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import re

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import utime
from bitdust.lib import packetid
from bitdust.lib import jsn
from bitdust.lib import strng
from bitdust.lib import serialization

from bitdust.main import events
from bitdust.main import config

from bitdust.crypt import my_keys
from bitdust.crypt import signed

from bitdust.dht import dht_relations

from bitdust.contacts import identitycache

from bitdust.p2p import commands
from bitdust.p2p import p2p_service
from bitdust.p2p import lookup
from bitdust.p2p import propagate
from bitdust.p2p import p2p_service_seeker

from bitdust.transport import packet_out

from bitdust.stream import message

from bitdust.storage import archive_reader

from bitdust.access import groups

from bitdust.userid import identity
from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

CRITICAL_PUSH_MESSAGE_FAILS = None
MAX_BUFFERED_MESSAGES = 10
MAX_CONNECT_LOOKUP_ATTEMPTS = 5

_ActiveGroupMembers = {}
_ActiveGroupMembersByIDURL = {}

#------------------------------------------------------------------------------


def register_group_member(A):
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
    if _Debug:
        lg.args(_DebugLevel, group_creator_idurl=A.group_creator_idurl, group_key_id=A.group_key_id)


def unregister_group_member(A):
    global _ActiveGroupMembers
    global _ActiveGroupMembersByIDURL
    if _Debug:
        lg.args(_DebugLevel, instance=repr(A))
    if id_url.is_not_in(A.group_creator_idurl, _ActiveGroupMembersByIDURL):
        lg.warn('for given customer idurl %r did not found active group members list' % A.group_creator_idurl)
    else:
        if A in _ActiveGroupMembersByIDURL[A.group_creator_idurl]:
            _ActiveGroupMembersByIDURL[A.group_creator_idurl].remove(A)
            if _Debug:
                lg.args(_DebugLevel, group_creator_idurl=A.group_creator_idurl, group_key_id=A.group_key_id)
        else:
            lg.warn('group_member() instance not found for customer %r' % A.group_creator_idurl)
    return _ActiveGroupMembers.pop(A.group_key_id, None)


#------------------------------------------------------------------------------


def list_active_group_members():
    global _ActiveGroupMembers
    return list(_ActiveGroupMembers.keys())


def get_active_group_member(group_key_id):
    global _ActiveGroupMembers
    if group_key_id not in _ActiveGroupMembers:
        return None
    return _ActiveGroupMembers[group_key_id]


def find_active_group_members(group_creator_idurl):
    global _ActiveGroupMembersByIDURL
    result = []
    for automat_index in _ActiveGroupMembersByIDURL.values():
        A = automat.by_index(automat_index, None)
        if not A:
            continue
        if A.group_creator_idurl == group_creator_idurl:
            result.append(A)
    return result


#------------------------------------------------------------------------------


def restart_active_group_member(group_key_id, use_dht_cache=False):
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id, use_dht_cache=use_dht_cache)
    existing_group_member = get_active_group_member(group_key_id)
    if not existing_group_member:
        lg.err('did not found active group member %r' % group_key_id)
        return None
    result = Deferred()
    existing_index = existing_group_member.index
    existing_publish_events = existing_group_member.publish_events
    existing_group_member.automat('shutdown')
    existing_group_member = None
    del existing_group_member
    new_group_member = []

    def _on_group_member_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, oldstate=oldstate, newstate=newstate, event_string=event_string)
        if newstate == 'IN_SYNC!' and oldstate != newstate:
            new_group_member[0].removeStateChangedCallback(_on_group_member_state_changed)
            result.callback(new_group_member[0].to_json())
        if newstate == 'DISCONNECTED' and oldstate != newstate:
            new_group_member[0].removeStateChangedCallback(_on_group_member_state_changed)
            result.callback(new_group_member[0].to_json())
        return None

    def _do_start_new_group_member():
        new_group_member.append(GroupMember(
            group_key_id=group_key_id,
            use_dht_cache=use_dht_cache,
            publish_events=existing_publish_events,
        ))
        new_index = new_group_member[0].index
        new_group_member[0].automat('init')
        new_group_member[0].automat('join')
        new_group_member[0].addStateChangedCallback(_on_group_member_state_changed)
        if _Debug:
            lg.args(_DebugLevel, group_key_id=group_key_id, existing=existing_index, new=new_index)

    reactor.callLater(0, _do_start_new_group_member)  # @UndefinedVariable
    return result


#------------------------------------------------------------------------------


def rotate_active_group_memeber(old_group_key_id, new_group_key_id):
    global _ActiveGroupMembers
    A_old = get_active_group_member(old_group_key_id)
    if not A_old:
        return False
    A_new = get_active_group_member(new_group_key_id)
    if A_new and A_new in _ActiveGroupMembers:
        lg.err('it seems group %r already rotated, but older copy also exists at the moment: %r' % (A_new, A_old))
        return False
    del A_new  # just my paranoia
    unregister_group_member(A_old)
    A_old.update_group_key_id(new_group_key_id)
    register_group_member(A_old)
    restart_active_group_member(new_group_key_id)
    return True


#------------------------------------------------------------------------------


def start_group_members():
    def _start():
        started = 0
        for group_key_id, group_info in groups.active_groups().items():
            if not group_key_id:
                continue
            if not my_keys.is_key_registered(group_key_id):
                lg.err('can not start GroupMember because key %r is not registered' % group_key_id)
                continue
            if group_key_id.startswith('person'):
                # TODO: temporarily disabled
                continue
            if not group_info['active']:
                continue
            if not id_url.is_cached(global_id.glob2idurl(group_key_id, as_field=False)):
                continue
            existing_group_member = get_active_group_member(group_key_id)
            if not existing_group_member:
                existing_group_member = GroupMember(group_key_id)
                existing_group_member.automat('init')
            if existing_group_member.state in [
                'DHT_READ?',
                'BROKERS?',
                'QUEUE?',
                'IN_SYNC!',
            ]:
                continue
            existing_group_member.automat('join')
            started += 1

    def _on_cached(result):
        if _Debug:
            lg.args(_DebugLevel, result=type(result))
        # a small delay to make sure received idurls were refreshed and rotated locally
        reactor.callLater(.5, _start)  # @UndefinedVariable
        return None

    idurls_to_be_updated = []
    for group_key_id, _ in groups.active_groups().items():
        if not group_key_id:
            continue
        if not my_keys.is_key_registered(group_key_id):
            continue
        if group_key_id.startswith('person'):
            # TODO: temporarily disabled
            continue
        creator_idurl = global_id.glob2idurl(group_key_id)
        if id_url.is_the_same(creator_idurl, my_id.getIDURL()):
            continue
        idurls_to_be_updated.append(creator_idurl)

    if _Debug:
        lg.args(_DebugLevel, active_groups=len(groups.active_groups()), idurls_to_be_updated=len(idurls_to_be_updated))
    d = propagate.fetch(idurls_to_be_updated, refresh_cache=True)
    d.addBoth(_on_cached)
    return True


def shutdown_group_members():
    stopped = 0
    for group_key_id in groups.active_groups().keys():
        existing_group_member = get_active_group_member(group_key_id)
        if not existing_group_member:
            continue
        existing_group_member.automat('shutdown')
        stopped += 1
    return stopped


#------------------------------------------------------------------------------


class GroupMember(automat.Automat):
    """
    This class implements all the functionality of ``group_member()`` state machine.
    """
    def __init__(self, group_key_id, member_idurl=None, use_dht_cache=True, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `group_member()` state machine.
        """
        self.member_idurl = member_idurl or my_id.getIDURL()
        self.member_id = self.member_idurl.to_id()
        self.group_key_id = group_key_id
        self.group_glob_id = global_id.NormalizeGlobalID(self.group_key_id)
        self.group_queue_alias = self.group_glob_id['key_alias']
        self.group_creator_id = self.group_glob_id['customer']
        self.group_creator_idurl = self.group_glob_id['idurl']
        self.member_sender_id = global_id.MakeGlobalID(idurl=self.member_idurl, key_alias=self.group_queue_alias)
        self.active_broker_id = None
        self.active_queue_id = None
        self.dead_broker_id = None
        self.connected_brokers = {}
        self.latest_dht_brokers = None
        self.last_sequence_id = groups.get_last_sequence_id(self.group_key_id)
        self.outgoing_messages = {}
        self.outgoing_counter = 0
        self.dht_read_use_cache = use_dht_cache
        self.buffered_messages = {}
        self.recorded_messages = []
        self.group_brokers_updated = False
        super(GroupMember, self).__init__(
            name='group_member_%s$%s' % (
                self.group_queue_alias,
                self.group_creator_id,
            ), state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs
        )

    def __repr__(self):
        connected_brokers_short = ['+' if (self.connected_brokers or {}).get(p) else ' ' for p in range(groups.REQUIRED_BROKERS_COUNT)]
        return '%s[%s](%s)' % (self.id, ''.join(connected_brokers_short), self.state)

    def update_group_key_id(self, new_group_key_id):
        if _Debug:
            lg.args(_DebugLevel, old=self.group_key_id, new=new_group_key_id)
        self.group_key_id = new_group_key_id
        self.group_glob_id = global_id.NormalizeGlobalID(self.group_key_id)
        self.group_queue_alias = self.group_glob_id['key_alias']
        self.group_creator_id = self.group_glob_id['customer']
        self.group_creator_idurl = self.group_glob_id['idurl']
        self.member_sender_id = global_id.MakeGlobalID(idurl=self.member_idurl, key_alias=self.group_queue_alias)

    def to_json(self):
        j = super().to_json()
        j.update(
            {
                'active': groups.is_group_active(self.group_key_id),
                'member_id': self.member_id,
                'group_key_id': self.group_key_id,
                'alias': self.group_glob_id['key_alias'],
                'label': my_keys.get_label(self.group_key_id) or '',
                'creator': self.group_creator_id,
                'active_broker_id': self.active_broker_id,
                'active_queue_id': self.active_queue_id,
                'connected_brokers': {p: id_url.idurl_to_id(b)
                                      for p, b in self.connected_brokers.items()},
                'last_sequence_id': self.last_sequence_id,
                'archive_folder_path': groups.get_archive_folder_path(self.group_key_id),
            }
        )
        return j

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `group_member()` machine.
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

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when automat's state was changed.
        """
        if newstate == 'QUEUE?':
            self.automat('instant')
        if _Debug:
            lg.out(_DebugLevel - 2, '%s : [%s]->[%s]' % (self.name, oldstate, newstate))
        if newstate == 'IN_SYNC!':
            lg.info('group synchronized : %s' % self.group_key_id)
            events.send('group-synchronized', data=dict(
                group_key_id=self.group_key_id,
                old_state=oldstate,
                new_state=newstate,
            ))
        if newstate not in ['DISCONNECTED', 'IN_SYNC!', 'CLOSED'] and oldstate in ['DISCONNECTED', 'IN_SYNC!']:
            lg.info('group connecting : %s' % self.group_key_id)
            events.send('group-connecting', data=dict(
                group_key_id=self.group_key_id,
                old_state=oldstate,
                new_state=newstate,
            ))
        if newstate == 'DISCONNECTED' and oldstate != 'AT_STARTUP':
            lg.info('group disconnected : %s' % self.group_key_id)
            events.send('group-disconnected', data=dict(
                group_key_id=self.group_key_id,
                old_state=oldstate,
                new_state=newstate,
            ))

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'DISCONNECTED'
                self.SyncedUp = False
                self.doInit(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'leave' or event == 'shutdown':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'join' or (event == 'brokers-changed' and self.isActive(*args, **kwargs)) or (event == 'instant' and self.isActive(*args, **kwargs) and self.isDeadBroker(*args, **kwargs)):
                self.state = 'DHT_READ?'
                self.doActivate(*args, **kwargs)
                self.doDHTReadBrokers(event, *args, **kwargs)
        #---DHT_READ?---
        elif self.state == 'DHT_READ?':
            if event == 'dht-read-failed':
                self.state = 'DISCONNECTED'
                self.SyncedUp = False
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'shutdown' or event == 'leave':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doCancelService(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'message-in':
                self.doRecord(*args, **kwargs)
            elif event == 'queue-in-sync':
                self.SyncedUp = True
            elif event == 'brokers-changed' or event == 'brokers-read' or event == 'brokers-found' or event == 'brokers-not-found':
                self.state = 'BROKERS?'
                self.doConnectSingleBroker(event, *args, **kwargs)
        #---BROKERS?---
        elif self.state == 'BROKERS?':
            if event == 'shutdown' or event == 'leave':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doCancelService(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'message-in':
                self.doRecord(*args, **kwargs)
            elif event == 'queue-in-sync':
                self.SyncedUp = True
            elif event == 'brokers-all-connected':
                self.state = 'QUEUE?'
                self.doRememberBrokers(*args, **kwargs)
                self.doProcess(*args, **kwargs)
                self.doReadQueue(*args, **kwargs)
            elif event == 'broker-lookup-ack' or event == 'broker-connect-ack':
                self.doPingBrokers(*args, **kwargs)
            elif event == 'top-broker-ping-failed' or event == 'brokers-ping-failed' or event == 'broker-lookup-failed' or event == 'broker-connect-failed':
                self.state = 'DISCONNECTED'
            elif event == 'brokers-mismatch':
                self.doConnectSingleBroker(event, *args, **kwargs)
        #---QUEUE?---
        elif self.state == 'QUEUE?':
            if event == 'queue-read-failed':
                self.state = 'DISCONNECTED'
                self.SyncedUp = False
                self.doMarkDeadBroker(event, *args, **kwargs)
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'message-in':
                self.doRecord(*args, **kwargs)
                self.doProcess(*args, **kwargs)
            elif event == 'shutdown' or event == 'leave':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doCancelService(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'queue-is-ahead':
                self.doReadArchive(*args, **kwargs)
            elif event == 'queue-in-sync' or (event == 'instant' and self.SyncedUp):
                self.state = 'IN_SYNC!'
                self.SyncedUp = True
                self.doPushPendingMessages(*args, **kwargs)
                self.doConnected(*args, **kwargs)
            elif event == 'reconnect' or event == 'brokers-changed' or event == 'push-message-failed' or event == 'replace-active-broker':
                self.state = 'DHT_READ?'
                self.SyncedUp = False
                self.doMarkDeadBroker(event, *args, **kwargs)
                self.doDHTReadBrokers(event, *args, **kwargs)
        #---IN_SYNC!---
        elif self.state == 'IN_SYNC!':
            if event == 'push-message':
                self.doPublish(*args, **kwargs)
            elif event == 'shutdown' or event == 'leave':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doCancelService(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'message-pushed':
                self.doNotifyMessageAccepted(*args, **kwargs)
            elif event == 'reconnect' or event == 'brokers-changed' or event == 'push-message-failed' or event == 'replace-active-broker':
                self.state = 'DHT_READ?'
                self.SyncedUp = False
                self.doMarkDeadBroker(event, *args, **kwargs)
                self.doDHTReadBrokers(event, *args, **kwargs)
            elif event == 'message-in':
                self.doRecord(*args, **kwargs)
                self.doProcess(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isDeadBroker(self, *args, **kwargs):
        """
        Condition method.
        """
        if self.dead_broker_id and self.dead_broker_id == self.active_broker_id:
            return True
        return None in args[0]

    def isActive(self, *args, **kwargs):
        """
        Condition method.
        """
        return groups.is_group_active(self.group_key_id)

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        if not groups.is_group_exist(self.group_key_id):
            groups.set_group_info(self.group_key_id)
            groups.save_group_info(self.group_key_id)
        message.consume_messages(
            consumer_callback_id=self.name,
            callback=self._do_read_queue_messages,
            direction='incoming',
            message_types=[
                'queue_message',
            ],
        )
        events.add_subscriber(self._on_group_brokers_updated, 'group-brokers-updated')

    def doActivate(self, *args, **kwargs):
        """
        Action method.
        """
        groups.set_group_active(self.group_key_id, True)
        groups.save_group_info(self.group_key_id)

    def doDHTReadBrokers(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.latest_dht_brokers = None
        if event == 'brokers-changed':
            self.dht_read_use_cache = True
            known_brokers = {}
            for pos, broker_id in enumerate(groups.known_brokers(self.group_creator_id)):
                if broker_id:
                    known_brokers[pos] = global_id.glob2idurl(broker_id)
            if _Debug:
                lg.args(_DebugLevel, e=event, known_brokers=known_brokers)
            self.automat('brokers-read', known_brokers=known_brokers)
            return
        if event == 'reconnect':
            cooperated_brokers = kwargs.get('cooperated_brokers')
            if cooperated_brokers:
                if _Debug:
                    lg.args(_DebugLevel, e=event, cooperated_brokers=cooperated_brokers)
                self.dht_read_use_cache = True
                self.automat('brokers-read', known_brokers=cooperated_brokers)
                return
        if event in ['reconnect', 'push-message-failed', 'replace-active-broker', 'broker-position-mismatch', 'top-broker-connect-failed']:
            self.dht_read_use_cache = False
        if _Debug:
            lg.args(_DebugLevel, e=event, use_cache=self.dht_read_use_cache)
        result = dht_relations.read_customer_message_brokers(
            self.group_creator_idurl,
            positions=list(range(groups.REQUIRED_BROKERS_COUNT)),
            use_cache=self.dht_read_use_cache,
        )
        # TODO: add more validations of dht_result
        result.addCallback(self._on_read_customer_message_brokers)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member.doDHTReadBrokers')
        result.addErrback(lambda err: self.automat('dht-read-failed', err))

    def doConnectSingleBroker(self, event, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, e=event, kw=kwargs)
        target_broker = None
        if event == 'brokers-changed':
            target_broker = self._do_detect_target_broker(available_brokers=kwargs['connected_brokers'])
        elif event == 'brokers-read':
            target_broker = self._do_detect_target_broker(available_brokers=kwargs['known_brokers'])
        elif event == 'brokers-mismatch':
            groups.clear_brokers(self.group_creator_id)
            if 'dht_brokers' in kwargs:
                target_broker = self._do_detect_target_broker(available_brokers=kwargs['dht_brokers'])
            elif 'cooperated_brokers' in kwargs:
                target_broker = self._do_detect_target_broker(available_brokers=kwargs['cooperated_brokers'])
            else:
                target_broker = self._do_detect_target_broker()
        else:
            groups.clear_brokers(self.group_creator_id)
            target_broker = self._do_detect_target_broker(dht_brokers=kwargs['dht_brokers'])
        self._do_connect_target_broker(target_broker['broker_pos'], target_broker['broker_idurl'])

    def doPingBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        cooperated_brokers = kwargs.get('cooperated_brokers') or {}
        archive_folder_path = kwargs.get('archive_folder_path')
        if _Debug:
            lg.args(_DebugLevel, cooperated=cooperated_brokers, archive_folder_path=archive_folder_path)
        idurl_list = [cooperated_brokers.get(i) for i in range(groups.REQUIRED_BROKERS_COUNT)]
        propagate.ping_nodes(
            idurl_list=idurl_list,
            timeout=15,
            channel='ping_broker',
            keep_alive=False,
        ).addBoth(
            self._on_brokers_ping_result,
            cooperated_brokers=cooperated_brokers,
            archive_folder_path=archive_folder_path,
        )

    def doRememberBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_remember_brokers(*args, **kwargs)

    def doReadQueue(self, *args, **kwargs):
        """
        Action method.
        """
        message_ack_timeout = config.conf().getInt('services/private-groups/message-ack-timeout')
        if message_ack_timeout:
            message_ack_timeout *= 2
        result = message.send_message(
            json_data={
                'msg_type': 'queue_message',
                'action': 'consume',
                'created': utime.utcnow_to_sec1970(),
                'last_sequence_id': self.last_sequence_id,
                'queue_id': self.active_queue_id,
                'consumer_id': self.member_id,
            },
            recipient_global_id=self.active_broker_id,
            packet_id=packetid.MakeQueueMessagePacketID(self.active_queue_id, packetid.UniqueID()),
            message_ack_timeout=message_ack_timeout,
            skip_handshake=True,
            fire_callbacks=False,
        )
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member.doReadQueue')
        result.addErrback(self._on_read_queue_failed)

    def doReadArchive(self, *args, **kwargs):
        """
        Action method.
        """
        latest_known_sequence_id = kwargs.get('latest_known_sequence_id')
        received_messages = kwargs.get('received_messages')
        result_defer = Deferred()
        result_defer.addCallback(self._on_read_archive_success, received_messages)
        result_defer.addErrback(self._on_read_archive_failed, received_messages, latest_known_sequence_id)
        ar = archive_reader.ArchiveReader()
        ar.automat(
            'start',
            queue_id=self.active_queue_id,
            start_sequence_id=self.last_sequence_id + 1,
            end_sequence_id=latest_known_sequence_id,
            archive_folder_path=groups.get_archive_folder_path(self.group_key_id),
            result_defer=result_defer,
        )

    def doRecord(self, *args, **kwargs):
        """
        Action method.
        """
        self.recorded_messages.append(kwargs)

    def doProcess(self, *args, **kwargs):
        """
        Action method.
        """
        while self.recorded_messages:
            recorded_kwargs = self.recorded_messages.pop(0)
            message.push_group_message(**recorded_kwargs)
            self.automat('message-consumed', recorded_kwargs)

    def doPublish(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_send_message_to_broker(
            json_payload=kwargs['json_payload'],
            outgoing_counter=None,
            packet_id=None,
        )

    def doPushPendingMessages(self, *args, **kwargs):
        """
        Action method.
        """
        if self.outgoing_messages:
            for outgoing_counter in sorted(list(self.outgoing_messages.keys())):
                self._do_send_message_to_broker(
                    json_payload=None,
                    outgoing_counter=outgoing_counter,
                    packet_id=None,
                )

    def doNotifyMessageAccepted(self, *args, **kwargs):
        """
        Action method.
        """

    def doMarkDeadBroker(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.group_brokers_updated = False
        if event == 'top-broker-failed':
            self.dead_broker_id = None
            if self.latest_dht_brokers is not None:
                for broker_info in self.latest_dht_brokers:
                    if broker_info['position'] == 0 and broker_info.get('idurl'):
                        self.dead_broker_id = global_id.idurl2glob(broker_info['idurl'])
        elif event == 'replace-active-broker':
            self.dead_broker_id = args[0]
        elif event == 'brokers-changed':
            self.dead_broker_id = None
        else:
            if event == 'reconnect':
                self.dead_broker_id = None
            else:
                self.dead_broker_id = self.active_broker_id
        self.dht_read_use_cache = False
        for outgoing_counter in self.outgoing_messages.keys():
            self.outgoing_messages[outgoing_counter]['attempts'] = 0
        if _Debug:
            lg.args(_DebugLevel, dead_broker_id=self.dead_broker_id)

    def doConnected(self, *args, **kwargs):
        """
        Action method.
        """
        self.dht_read_use_cache = True
        if self.group_brokers_updated:
            # yapf: disable
            events.send('group-brokers-updated', data=dict(
                group_creator_id=self.group_creator_id,
                group_key_id=self.group_key_id,
                member_id=self.member_id,
                connected_brokers=self.connected_brokers,
            ))
            # yapf: enable
            self.group_brokers_updated = False

    def doDisconnected(self, *args, **kwargs):
        """
        Action method.
        """
        self.group_brokers_updated = False
        self.dht_read_use_cache = False

    def doDeactivate(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.group_brokers_updated = False
        if event == 'leave':
            groups.set_group_active(self.group_key_id, False)
            groups.save_group_info(self.group_key_id)
        else:
            groups.save_group_info(self.group_key_id)

    def doCancelService(self, event, *args, **kwargs):
        """
        Action method.
        """
        if event == 'leave':
            for broker_idurl in self.connected_brokers.values():
                if not broker_idurl:
                    continue
                p2p_service.SendCancelService(
                    remote_idurl=broker_idurl,
                    service_name='service_message_broker',
                    json_payload=self._do_prepare_service_request_params(broker_idurl, action='queue-disconnect'),
                )
            if kwargs.get('erase_key', False):
                if my_keys.is_key_registered(self.group_key_id):
                    my_keys.erase_key(self.group_key_id)
                else:
                    lg.warn('key %r not registered, can not be erased' % self.group_key_id)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        events.remove_subscriber(self._on_group_brokers_updated, 'group-brokers-updated')
        message.clear_consumer_callbacks(self.name)
        self.destroy()
        self.member_idurl = None
        self.member_id = None
        self.member_sender_id = None
        self.group_glob_id = None
        self.group_queue_alias = None
        self.group_creator_id = None
        self.group_creator_idurl = None
        self.active_broker_id = None
        self.active_queue_id = None
        self.dead_broker_id = None
        self.connected_brokers = None
        self.latest_dht_brokers = None
        self.outgoing_messages = None
        self.outgoing_counter = None
        self.buffered_messages = None
        self.recorded_messages = None
        self.group_brokers_updated = None

    #------------------------------------------------------------------------------

    def _do_detect_target_broker(self, available_brokers=None, dht_brokers=None):
        if _Debug:
            lg.args(_DebugLevel, dead=self.dead_broker_id, available=len(available_brokers or []), dht=len(dht_brokers or []))
        last_pos = groups.REQUIRED_BROKERS_COUNT - 1
        if self.dead_broker_id:
            if not self.active_broker_id or self.active_broker_id == self.dead_broker_id:
                return {'broker_idurl': None, 'broker_pos': last_pos}
        if available_brokers:
            if last_pos in available_brokers:
                return {'broker_idurl': available_brokers[last_pos], 'broker_pos': last_pos}
        if dht_brokers:
            for dht_broker in dht_brokers:
                if dht_broker['position'] == last_pos and dht_broker['broker_idurl']:
                    return {'broker_idurl': dht_broker['broker_idurl'], 'broker_pos': last_pos}
        return {'broker_idurl': None, 'broker_pos': last_pos}

    def _do_connect_target_broker(self, broker_pos, broker_idurl):
        if broker_idurl:
            self._do_request_service_one_broker(broker_pos, broker_idurl)
        else:
            self._do_lookup_one_broker(broker_pos, skip_brokers=[])

    def _do_request_service_one_broker(self, broker_pos, broker_idurl):
        if _Debug:
            lg.args(_DebugLevel, broker_pos=broker_pos, broker_idurl=broker_idurl)
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=broker_idurl,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params(idurl, broker_pos),
            request_service_timeout=config.conf().getInt('services/private-groups/broker-connect-timeout', 120),
            attempts=1,
        )
        result.addCallback(self._on_broker_connected, broker_pos)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member._do_request_service_one_broker')
        result.addErrback(self._on_broker_connect_failed, broker_pos)

    def _do_lookup_one_broker(self, broker_pos, skip_brokers):
        if _Debug:
            lg.args(_DebugLevel, broker_pos=broker_pos, skip_brokers=skip_brokers)
        exclude_brokers = set()
        for known_broker_id in groups.known_brokers(self.group_creator_id):
            if known_broker_id:
                exclude_brokers.add(id_url.to_bin(global_id.glob2idurl(known_broker_id, as_field=False)))
        for connected_broker_idurl in self.connected_brokers.values():
            exclude_brokers.add(id_url.to_bin(connected_broker_idurl))
        for skip_idurl in skip_brokers:
            if skip_idurl:
                exclude_brokers.add(id_url.to_bin(skip_idurl))
        if self.dead_broker_id:
            exclude_brokers.add(id_url.to_bin(global_id.glob2idurl(self.dead_broker_id, as_field=False)))
        preferred_brokers = []
        preferred_brokers_raw = config.conf().getString('services/private-groups/preferred-brokers').strip()
        if preferred_brokers_raw:
            preferred_brokers_list = re.split('\n|,|;| ', preferred_brokers_raw)
            preferred_brokers.extend(preferred_brokers_list)
            preferred_brokers = id_url.to_bin_list(preferred_brokers)
        if preferred_brokers:
            preferred_brokers = [x for x in preferred_brokers if x not in exclude_brokers]
        if _Debug:
            lg.args(_DebugLevel, exclude_brokers=exclude_brokers, preferred_brokers=preferred_brokers)
        if preferred_brokers:
            preferred_broker_idurl = id_url.field(preferred_brokers[0])
            if preferred_broker_idurl and id_url.is_not_in(preferred_broker_idurl, exclude_brokers, as_field=False):
                result = p2p_service_seeker.connect_known_node(
                    remote_idurl=preferred_broker_idurl,
                    service_name='service_message_broker',
                    service_params=lambda idurl: self._do_prepare_service_request_params(idurl, broker_pos),
                    request_service_timeout=config.conf().getInt('services/private-groups/broker-connect-timeout', 120),
                    exclude_nodes=list(exclude_brokers),
                    attempts=1,
                )
                result.addCallback(self._on_broker_hired, broker_pos)
                result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member._do_lookup_one_broker')
                result.addErrback(self._on_broker_connect_failed, broker_pos)
                return result
        result = p2p_service_seeker.connect_random_node(
            lookup_method=lookup.random_message_broker,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params(idurl, broker_pos),
            request_service_timeout=config.conf().getInt('services/private-groups/broker-connect-timeout', 120),
            exclude_nodes=list(exclude_brokers),
            attempts=2,
        )
        result.addCallback(self._on_broker_hired, broker_pos)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member._do_lookup_one_broker')
        result.addErrback(self._on_broker_lookup_failed, broker_pos)
        return result

    def _do_read_queue_messages(self, json_messages):
        if not json_messages:
            return True
        if _Debug:
            lg.args(_DebugLevel, active_queue_id=self.active_queue_id, active_broker_id=self.active_broker_id, json_messages=len(json_messages))
        latest_known_sequence_id = -1
        received_group_messages = []
        packets_to_ack = {}
        cooperated_brokers = {}
        to_be_reconnected = False
        found_group_ids = set()
        found_broker_ids = set()
        for json_message in json_messages:
            try:
                msg_type = json_message.get('msg_type', '') or json_message.get('type', '')  # TODO: need to cleanup that later
                msg_direction = json_message['dir']
                packet_id = json_message['packet_id']
                owner_idurl = json_message['owner_idurl']
                msg_data = json_message['data']
                msg_action = msg_data.get('action', 'read')
            except:
                lg.exc()
                continue
            if msg_direction != 'incoming':
                continue
            if msg_type != 'queue_message':
                continue
            if msg_action != 'read':
                continue
            if 'last_sequence_id' not in msg_data:
                continue
            try:
                chunk_last_sequence_id = int(msg_data['last_sequence_id'])
                list_messages = msg_data['items']
            except:
                lg.exc(msg_data)
                continue
            incoming_queue_id = packetid.SplitQueueMessagePacketID(packet_id)[0]
            incoming_group_alias, incoming_group_creator_id, incoming_broker_id = global_id.SplitGlobalQueueID(incoming_queue_id)
            incoming_group_creator_id = global_id.glob2idurl(incoming_group_creator_id).to_id()
            incoming_group_key_id = global_id.MakeGlobalKeyID(incoming_group_alias, incoming_group_creator_id)
            found_group_ids.add(incoming_group_key_id)
            found_broker_ids.add(incoming_broker_id)
            if incoming_group_key_id != self.group_key_id:
                if _Debug:
                    lg.dbg(_DebugLevel, 'skip message based on packet_id for %r : %r' % (self.group_key_id, incoming_group_key_id))
                continue
            if chunk_last_sequence_id > latest_known_sequence_id:
                latest_known_sequence_id = chunk_last_sequence_id
            for one_message in list_messages:
                if one_message['sequence_id'] > latest_known_sequence_id:
                    lg.warn('invalid item sequence_id %d   vs.  last_sequence_id %d known' % (one_message['sequence_id'], latest_known_sequence_id))
                    continue
                group_message_object = message.GroupMessage.deserialize(one_message['payload'])
                if group_message_object is None:
                    lg.err('GroupMessage deserialize failed, can not extract message from payload of %d bytes' % len(one_message['payload']))
                    continue
                try:
                    decrypted_message = group_message_object.decrypt()
                    json_message = serialization.BytesToDict(
                        decrypted_message,
                        unpack_types=True,
                        encoding='utf-8',
                    )
                except:
                    lg.exc()
                    continue
                received_group_messages.append(dict(
                    json_message=json_message,
                    direction='incoming',
                    group_key_id=self.group_key_id,
                    producer_id=one_message['producer_id'],
                    sequence_id=one_message['sequence_id'],
                ))
                if owner_idurl:
                    packets_to_ack[packet_id] = owner_idurl
        for packet_id, owner_idurl in packets_to_ack.items():
            p2p_service.SendAckNoRequest(owner_idurl, packet_id)
            received_queue_id, _, _ = packet_id.rpartition('_')
            _, received_broker_id = global_id.SplitGlobalQueueID(received_queue_id, split_queue_alias=False)
            if self.active_broker_id and received_broker_id != self.active_broker_id:
                if not to_be_reconnected:
                    to_be_reconnected = True
                    lg.warn('received message from broker %r which is different from my active broker %r' % (received_broker_id, self.active_broker_id))
        if received_group_messages and len(found_broker_ids) > 0 and self.active_broker_id not in found_broker_ids:
            to_be_reconnected = True
            lg.warn('active broker is %r but incoming message received from another broker %r in %r' % (self.active_broker_id, list(found_broker_ids), self))
        packets_to_ack.clear()
        if to_be_reconnected:
            cooperated_brokers = json_message.get('cooperated_brokers', {}) or {}
            cooperated_brokers = {int(k): id_url.field(v) for k, v in cooperated_brokers.items()}
            if _Debug:
                lg.args(_DebugLevel, cooperated_brokers=cooperated_brokers)
        if not received_group_messages:
            if self.group_key_id not in found_group_ids:
                if _Debug:
                    lg.dbg(_DebugLevel, 'no messages for %r found in the incoming stream' % self.active_queue_id)
                return True
            if latest_known_sequence_id < self.last_sequence_id:
                lg.warn('found queue latest sequence %d is behind of my current position %d' % (latest_known_sequence_id, self.last_sequence_id))
                self.automat('queue-in-sync')
                if to_be_reconnected:
                    if _Debug:
                        lg.dbg(_DebugLevel, 'going to reconnect %r' % self)
                    reactor.callLater(0.01, self.automat, 'reconnect', cooperated_brokers=cooperated_brokers)  # @UndefinedVariable
                return True
            if latest_known_sequence_id > self.last_sequence_id:
                lg.warn('nothing received, but found queue latest sequence %d is ahead of my current position %d, need to read messages from archive' % (latest_known_sequence_id, self.last_sequence_id))
                self.automat('queue-is-ahead', latest_known_sequence_id=latest_known_sequence_id, received_messages=received_group_messages)
                if to_be_reconnected:
                    if _Debug:
                        lg.dbg(_DebugLevel, 'going to reconnect %r' % self)
                    reactor.callLater(0.01, self.automat, 'reconnect', cooperated_brokers=cooperated_brokers)  # @UndefinedVariable
                return True
            self.last_sequence_id = latest_known_sequence_id
            groups.set_last_sequence_id(self.group_key_id, latest_known_sequence_id)
            groups.save_group_info(self.group_key_id)
            if _Debug:
                lg.dbg(_DebugLevel, 'no new messages, queue in sync, latest_known_sequence_id=%d' % latest_known_sequence_id)
            self.automat('queue-in-sync')
            if to_be_reconnected:
                if _Debug:
                    lg.dbg(_DebugLevel, 'going to reconnect %r' % self)
                reactor.callLater(0.01, self.automat, 'reconnect', cooperated_brokers=cooperated_brokers)  # @UndefinedVariable
            return True
        received_group_messages.sort(key=lambda m: m['sequence_id'])
        ret = self._do_process_group_messages(received_group_messages, latest_known_sequence_id)
        if to_be_reconnected:
            if _Debug:
                lg.dbg(_DebugLevel, 'going to reconnect %r' % self)
            self.automat('reconnect', cooperated_brokers=cooperated_brokers)
        return ret

    def _do_process_group_messages(self, received_group_messages, latest_known_sequence_id):
        if _Debug:
            lg.args(_DebugLevel, received_group_messages=len(received_group_messages), buffered_messages=len(self.buffered_messages), latest_known_sequence_id=latest_known_sequence_id)
        newly_processed = 0
        for new_message in received_group_messages:
            new_sequence_id = new_message['sequence_id']
            if new_sequence_id in self.buffered_messages:
                lg.warn('message %d already buffered' % new_sequence_id)
                continue
            self.buffered_messages[new_sequence_id] = new_message
        buffered_sequence_ids = sorted(self.buffered_messages.keys())
        for new_sequence_id in buffered_sequence_ids:
            if self.last_sequence_id + 1 == new_sequence_id:
                inp_message = self.buffered_messages.pop(new_sequence_id)
                self.last_sequence_id = new_sequence_id
                newly_processed += 1
                groups.set_last_sequence_id(self.group_key_id, self.last_sequence_id)
                groups.save_group_info(self.group_key_id)
                lg.info('new message consumed in %r, last_sequence_id incremented to %d' % (self.group_key_id, self.last_sequence_id))
                self.automat('message-in', **inp_message)
        if len(self.buffered_messages) > MAX_BUFFERED_MESSAGES:
            raise Exception('message sequence is broken by message broker %s, currently %d buffered messages' % (self.active_broker_id, len(self.buffered_messages)))
        if _Debug:
            lg.dbg(_DebugLevel, 'my_last_sequence_id=%d  newly_processed=%d  buffered_messages=%d' % (self.last_sequence_id, newly_processed, len(self.buffered_messages)))
        if not newly_processed or newly_processed != len(received_group_messages):
            if latest_known_sequence_id > self.last_sequence_id:
                lg.warn('found queue latest sequence %d is ahead of my current position %d, need to read messages from archive' % (latest_known_sequence_id, self.last_sequence_id))
                self.automat('queue-is-ahead', latest_known_sequence_id=latest_known_sequence_id, received_messages=received_group_messages)
                return True
        if _Debug:
            lg.dbg(_DebugLevel, 'processed all messages, queue in sync, last_sequence_id=%d' % self.last_sequence_id)
        self.automat('queue-in-sync')
        return True

    def _do_send_message_to_broker(self, json_payload=None, outgoing_counter=None, packet_id=None):
        global CRITICAL_PUSH_MESSAGE_FAILS
        if CRITICAL_PUSH_MESSAGE_FAILS is None:
            CRITICAL_PUSH_MESSAGE_FAILS = int(os.environ.get('BITDUST_CRITICAL_PUSH_MESSAGE_FAILS', 2))
        if packet_id is None:
            packet_id = packetid.UniqueID()
        if _Debug:
            lg.args(_DebugLevel, json_payload=json_payload, outgoing_counter=outgoing_counter, packet_id=packet_id)
        require_handshake = False
        if outgoing_counter is None:
            self.outgoing_counter += 1
            outgoing_counter = self.outgoing_counter
            self.outgoing_messages[outgoing_counter] = {
                'attempts': 0,
                'last_attempt': None,
                'payload': json_payload,
            }
        else:
            if self.outgoing_messages[outgoing_counter]['attempts'] > CRITICAL_PUSH_MESSAGE_FAILS:
                lg.err('failed sending message to broker %r after %d attempts' % (self.active_broker_id, self.outgoing_messages[outgoing_counter]['attempts']))
                self.outgoing_messages[outgoing_counter]['attempts'] = 0
                self.outgoing_messages[outgoing_counter]['last_attempt'] = None
                self.automat('push-message-failed')
                return
            if self.outgoing_messages[outgoing_counter]['last_attempt'] is not None:
                if utime.utcnow_to_sec1970() - self.outgoing_messages[outgoing_counter]['last_attempt'] < config.conf().getInt('services/private-groups/message-ack-timeout'):
                    lg.warn('pending message %d already made attempt to send recently' % outgoing_counter)
                    return
            self.outgoing_messages[outgoing_counter]['attempts'] += 1
            self.outgoing_messages[outgoing_counter]['last_attempt'] = utime.utcnow_to_sec1970()
            json_payload = self.outgoing_messages[outgoing_counter]['payload']
            if self.outgoing_messages[outgoing_counter]['attempts'] >= 1:
                require_handshake = True
            lg.warn('re-trying sending message to broker %r   counter=%d attempts=%d packet_id=%s' % (self.active_broker_id, outgoing_counter, self.outgoing_messages[outgoing_counter]['attempts'], packet_id))
        raw_payload = serialization.DictToBytes(
            json_payload,
            pack_types=True,
            encoding='utf-8',
        )
        try:
            private_message_object = message.GroupMessage(
                recipient=self.group_key_id,
                sender=self.member_sender_id,
            )
            private_message_object.encrypt(raw_payload)
        except:
            lg.exc()
            raise Exception('message encryption failed')
        encrypted_payload = private_message_object.serialize()
        d = message.send_message(
            json_data={
                'msg_type': 'queue_message',
                'action': 'produce',
                'created': utime.utcnow_to_sec1970(),
                'payload': encrypted_payload,
                'queue_id': self.active_queue_id,
                'producer_id': self.member_id,
                'brokers': self.connected_brokers,
            },
            recipient_global_id=self.active_broker_id,
            packet_id=packetid.MakeQueueMessagePacketID(self.active_queue_id, packet_id),
            message_ack_timeout=config.conf().getInt('services/private-groups/message-ack-timeout'),
            skip_handshake=True,
            fire_callbacks=False,
            require_handshake=require_handshake,
        )
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_member._do_send_message_to_broker')
        d.addCallback(self._on_message_to_broker_sent, outgoing_counter, packet_id)
        d.addErrback(self._on_message_to_broker_failed, outgoing_counter, packet_id)

    def _do_prepare_service_request_params(self, possible_broker_idurl, desired_broker_position=-1, action='queue-connect'):
        if _Debug:
            lg.args(_DebugLevel, broker=possible_broker_idurl, pos=desired_broker_position, action=action, owner=self.group_creator_id)
        group_key_info = {}
        # if not my_keys.is_key_registered(self.group_key_id):
        #     lg.warn('group key %r was not registered, checking all registered keys' % self.group_key_id)
        #     my_keys.check_rename_my_keys(prefix=self.group_key_id.split('@')[0])
        if not my_keys.is_key_registered(self.group_key_id):
            lg.warn('closing group_member %r because key %r is not registered' % (self, self.group_key_id))
            lg.exc('group key %r is not registered' % self.group_key_id)
            self.automat('shutdown')
            return
        try:
            group_key_info = my_keys.get_key_info(
                key_id=self.group_key_id,
                include_private=False,
                include_signature=True,
                generate_signature=True,
                include_label=False,
            )
        except:
            lg.exc()
            self.automat('shutdown')
            return
        service_request_params = {
            'action': action,
            'queue_id': None,
            'consumer_id': self.member_id,
            'producer_id': self.member_id,
            'group_key': group_key_info,
            'archive_folder_path': groups.get_archive_folder_path(self.group_key_id),
            'last_sequence_id': self.last_sequence_id,
            'known_brokers': self.connected_brokers,
        }
        if action == 'queue-disconnect':
            service_request_params['queue_id'] = self.active_queue_id
        if desired_broker_position >= 0:
            service_request_params['position'] = desired_broker_position
        if _Debug:
            lg.args(_DebugLevel, action=action, last_sequence_id=service_request_params['last_sequence_id'], archive_folder_path=service_request_params['archive_folder_path'])
        return service_request_params

    def _do_remember_brokers(self, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, args=args, kwargs=kwargs)
        cooperated_brokers = kwargs.get('cooperated_brokers') or {}
        current_connected_brokers = dict(self.connected_brokers or {})
        archive_folder_path = kwargs.get('archive_folder_path')
        brokers_changed = False
        self.active_broker_id = None
        self.active_queue_id = None
        self.connected_brokers = {}
        for position in range(groups.REQUIRED_BROKERS_COUNT):
            broker_idurl = cooperated_brokers.get(position)
            if broker_idurl:
                broker_idurl = id_url.field(broker_idurl)
                broker_id = global_id.idurl2glob(broker_idurl)
                groups.set_broker(self.group_creator_id, broker_id, position)
                self.connected_brokers[position] = broker_idurl
                if position == 0:
                    self.dead_broker_id = None
                    self.active_broker_id = broker_id
                    self.active_queue_id = global_id.MakeGlobalQueueID(
                        queue_alias=self.group_queue_alias,
                        owner_id=self.group_creator_id,
                        supplier_id=self.active_broker_id,
                    )
            else:
                groups.clear_broker(self.group_creator_id, position)
            if current_connected_brokers.get(position) != self.connected_brokers.get(position):
                brokers_changed = True
        if self.active_broker_id is None:
            raise Exception('active broker was not connected')
        if archive_folder_path:
            current_path = groups.get_archive_folder_path(self.group_key_id)
            if current_path and current_path != archive_folder_path:
                lg.warn('for %r overwriting existing archive_folder_path %r with new value %r' % (self.group_key_id, current_path, archive_folder_path))
            else:
                if not current_path:
                    lg.info('recognized archive folder path for %r from broker response: %r' % (self.group_key_id, archive_folder_path))
            groups.set_archive_folder_path(self.group_key_id, archive_folder_path)
        groups.save_group_info(self.group_key_id)
        if brokers_changed:
            self.group_brokers_updated = True

    #------------------------------------------------------------------------------

    def _on_read_customer_message_brokers(self, brokers_info_list):
        if _Debug:
            lg.args(_DebugLevel, brokers=len(brokers_info_list))
        if not brokers_info_list:
            self.dht_read_use_cache = False
            self.automat('brokers-not-found', dht_brokers=[])
            return
        self.latest_dht_brokers = brokers_info_list
        self.automat('brokers-found', dht_brokers=brokers_info_list)

    def _on_broker_connected(self, response_info, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, resp=response_info, broker_pos=broker_pos, args=args, kwargs=kwargs)
        try:
            # skip leading "accepted:" marker
            cooperated_brokers = jsn.loads(strng.to_text(response_info[0].Payload)[9:])
            archive_folder_path = strng.to_text(cooperated_brokers.pop('archive_folder_path', None))
            cooperated_brokers = {int(k): id_url.field(v) for k, v in cooperated_brokers.items()}
        except:
            lg.exc()
            self.automat('broker-connect-failed')
            return
        self.automat('broker-connect-ack', cooperated_brokers=cooperated_brokers, archive_folder_path=archive_folder_path)

    def _on_broker_connect_failed(self, err, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, err=err, broker_pos=broker_pos, args=args, kwargs=kwargs)
        if isinstance(err, Failure):
            if _Debug:
                lg.args(_DebugLevel, args=err.value.args)
            mismatch_info = {}
            try:
                evt, a, kw = err.value.args
                if a and a[0]:
                    if isinstance(a[0], packet_out.PacketOut):
                        resp_payload = strng.to_text(a[0].outpacket.Payload)
                    else:
                        resp_payload = strng.to_text(a[0][0].Payload)
                    if resp_payload.startswith('identity:'):
                        xml_src = resp_payload[9:]
                        new_ident = identity.identity(xmlsrc=xml_src)
                        if new_ident.isCorrect() and new_ident.Valid():
                            if identitycache.UpdateAfterChecking(new_ident.getIDURL(), xml_src):
                                reactor.callLater(0.2, self.automat, 'brokers-mismatch')  # @UndefinedVariable
                                return
                    if resp_payload.startswith('mismatch:'):
                        mismatch_info = jsn.loads(resp_payload[9:])
                        if 'dht_brokers' in mismatch_info:
                            mismatch_info['dht_brokers'] = {int(k): id_url.field(v) for k, v in mismatch_info['dht_brokers'].items()}
                        if 'cooperated_brokers' in mismatch_info:
                            mismatch_info['cooperated_brokers'] = {int(k): id_url.field(v) for k, v in mismatch_info['cooperated_brokers'].items()}
            except:
                lg.exc()
                self.automat('broker-connect-failed', err)
                return
            if mismatch_info:
                lg.warn('broker request mismatch at position %d: %r' % (broker_pos, mismatch_info))
                self.automat('brokers-mismatch', **mismatch_info)
                return
        lg.err('failed connecting to broker at position %d : %r' % (broker_pos, err))
        self.automat('broker-connect-failed', err)

    def _on_broker_hired(self, response_info, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, resp=response_info, broker_pos=broker_pos, args=args, kwargs=kwargs)
        try:
            # skip leading "accepted:" marker
            cooperated_brokers = jsn.loads(strng.to_text(response_info[0].Payload)[9:])
            archive_folder_path = strng.to_text(cooperated_brokers.pop('archive_folder_path', None))
            cooperated_brokers = {int(k): id_url.field(v) for k, v in cooperated_brokers.items()}
        except:
            lg.exc()
            self.automat('broker-lookup-failed')
            return
        self.automat('broker-lookup-ack', cooperated_brokers=cooperated_brokers, archive_folder_path=archive_folder_path)

    def _on_broker_lookup_failed(self, err, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, err=err, broker_pos=broker_pos)
        if isinstance(err, Failure):
            if _Debug:
                lg.args(_DebugLevel, args=err.value.args)
            mismatch_info = {}
            try:
                evt, a, kw = err.value.args
                if a and a[0]:
                    if isinstance(a[0], packet_out.PacketOut):
                        resp_payload = strng.to_text(a[0].outpacket.Payload)
                    else:
                        resp_payload = strng.to_text(a[0][0].Payload)
                    if resp_payload.startswith('mismatch:'):
                        mismatch_info = jsn.loads(resp_payload[9:])
                        if 'dht_brokers' in mismatch_info:
                            mismatch_info['dht_brokers'] = {int(k): id_url.field(v) for k, v in mismatch_info['dht_brokers'].items()}
                        if 'cooperated_brokers' in mismatch_info:
                            mismatch_info['cooperated_brokers'] = {int(k): id_url.field(v) for k, v in mismatch_info['cooperated_brokers'].items()}
            except:
                lg.exc()
                self.automat('broker-lookup-failed', err)
                return
            if mismatch_info:
                self.automat('brokers-mismatch', **mismatch_info)
                return
        self.automat('broker-lookup-failed', err)

    def _on_brokers_ping_result(self, ping_results, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, ping_results=ping_results, kwargs=kwargs)
        try:
            all_results = [r[0] for r in ping_results]
            top_broker_result = ping_results[0][0]
        except:
            lg.exc()
            top_broker_result = False
        if not top_broker_result:
            self.automat('top-broker-ping-failed')
            return
        if True not in all_results:
            self.automat('brokers-ping-failed')
            return
        self.automat('brokers-all-connected', **kwargs)

    def _on_read_queue_failed(self, err):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        if isinstance(err, Failure):
            if _Debug:
                lg.args(_DebugLevel, args=err.value.args)
            try:
                if isinstance(err.value.args[0], str):
                    resp_payload = strng.to_text(err.value.args[0])
                elif isinstance(err.value.args[0], packet_out.PacketOut):
                    resp_payload = strng.to_text(err.value.args[0].outpacket.Payload)
                elif isinstance(err.value.args[0], signed.Packet):
                    resp_payload = strng.to_text(err.value.args[0].Payload)
                else:
                    resp_payload = strng.to_text(err.value.args[0][0].Payload)
                if _Debug:
                    lg.dbg(_DebugLevel, resp_payload)
                if resp_payload.startswith('identity:'):
                    xml_src = resp_payload[9:]
                    new_ident = identity.identity(xmlsrc=xml_src)
                    if new_ident.isCorrect() and new_ident.Valid():
                        if identitycache.UpdateAfterChecking(new_ident.getIDURL(), xml_src):
                            reactor.callLater(0.5, self.automat, 'reconnect')  # @UndefinedVariable
                            return
            except:
                lg.exc()
        self.automat('queue-read-failed', err)

    def _on_message_to_broker_sent(self, response_packet, outgoing_counter, packet_id):
        if _Debug:
            lg.args(_DebugLevel, response_packet=response_packet, outgoing_counter=outgoing_counter)
        if outgoing_counter not in self.outgoing_messages:
            raise Exception('outgoing message with counter %d not found' % outgoing_counter)
        if response_packet and response_packet.Command == commands.Ack():
            self.outgoing_messages.pop(outgoing_counter)
            self.automat('message-pushed', outgoing_counter=outgoing_counter)
            return
        self._do_send_message_to_broker(json_payload=None, outgoing_counter=outgoing_counter, packet_id=None)

    def _on_message_to_broker_failed(self, err, outgoing_counter, packet_id):
        if _Debug:
            lg.args(_DebugLevel, err=err, outgoing_counter=outgoing_counter, packet_id=packet_id)
        self.outgoing_messages[outgoing_counter]['last_attempt'] = None
        self._do_send_message_to_broker(json_payload=None, outgoing_counter=outgoing_counter, packet_id=None)

    def _on_read_archive_success(self, archive_messages, received_messages):
        if _Debug:
            lg.args(_DebugLevel, archive_messages=len(archive_messages), received_messages=len(received_messages))
        received_group_messages = []
        latest_known_sequence_id = -1
        for archive_message in archive_messages:
            if archive_message['sequence_id'] > latest_known_sequence_id:
                latest_known_sequence_id = archive_message['sequence_id']
        for archive_message in archive_messages:
            received_group_messages.append(dict(
                json_message=archive_message['payload'],
                direction='incoming',
                group_key_id=self.group_key_id,
                producer_id=archive_message['producer_id'],
                sequence_id=archive_message['sequence_id'],
            ))
        for received_message in received_messages:
            received_group_messages.append(
                dict(
                    json_message=received_message['json_message'],
                    direction='incoming',
                    group_key_id=self.group_key_id,
                    producer_id=received_message['producer_id'],
                    sequence_id=received_message['sequence_id'],
                )
            )
            if received_message['sequence_id'] > latest_known_sequence_id:
                latest_known_sequence_id = received_message['sequence_id']
        self._do_process_group_messages(received_group_messages, latest_known_sequence_id)

    def _on_read_archive_failed(self, err, received_messages, latest_known_sequence_id):
        lg.warn('received %d recent messages but read archived messages failed with: %r' % (len(received_messages), err))
        self.last_sequence_id = latest_known_sequence_id
        groups.set_last_sequence_id(self.group_key_id, latest_known_sequence_id)
        groups.save_group_info(self.group_key_id)
        self.automat('queue-in-sync')
        return None

    def _on_group_brokers_updated(self, evt):
        d = evt.data
        if d.get('group_creator_id') != self.group_creator_id:
            return
        if d.get('group_key_id') == self.group_key_id:
            return
        changed = False
        for pos, broker_idurl in d['connected_brokers'].items():
            if pos not in self.connected_brokers:
                changed = True
                break
            if self.connected_brokers[pos] != broker_idurl:
                changed = True
                break
        if _Debug:
            lg.args(_DebugLevel, changed=changed, this=repr(self), connected_brokers=d['connected_brokers'])
        if changed:
            reactor.callLater(0.01, self.automat, 'brokers-changed', connected_brokers=d['connected_brokers'])  # @UndefinedVariable
