#!/usr/bin/env python
# group_queue_member.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (group_queue_memver.py) is part of BitDust Software.
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
.. module:: group_queue_member
.. role:: red

BitDust group_queue_member() Automat

EVENTS:
    * :red:`brokers-fialed`
    * :red:`brokers-found`
    * :red:`brokers-hired`
    * :red:`brokers-not-found`
    * :red:`connect`
    * :red:`dht-read-failed`
    * :red:`init`
    * :red:`message-in`
    * :red:`queue-connected`
    * :red:`queue-failed`
    * :red:`queue-in-sync`
    * :red:`queue-pull`
    * :red:`shutdown`
"""



#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import strng
from lib import utime

from main import events

from crypt import my_keys

from dht import dht_relations

from p2p import p2p_service_seeker
from p2p import lookup

from userid import global_id
from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

_ActiveGroupMembers = {}
_ActiveGroupMembersByIDURL = {}

#------------------------------------------------------------------------------

def register_group_memeber(A):
    """
    """
    global _ActiveGroupMembers
    global _ActiveGroupMembersByIDURL
    if A.key_id in _ActiveGroupMembers:
        raise Exception('group_memeber already exist')
    if id_url.is_not_in(A.customer_idurl, _ActiveGroupMembersByIDURL):
        _ActiveGroupMembersByIDURL[A.customer_idurl] = []
    _ActiveGroupMembersByIDURL[A.customer_idurl].append(A)
    _ActiveGroupMembers[A.key_id] = A


def unregister_group_memeber(A):
    """
    """
    global _ActiveGroupMembers
    global _ActiveGroupMembersByIDURL
    _ActiveGroupMembers.pop(A.key_id, None)
    if id_url.is_not_in(A.customer_idurl, _ActiveGroupMembersByIDURL):
        lg.warn('for given customer idurl did not found in active group memebers lists')
    else:
        _ActiveGroupMembersByIDURL[A.customer_idurl] = []

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


def find_active_group_memebers(customer_idurl):
    """
    """
    global _ActiveGroupMembersByIDURL
    result = []
    for automat_index in _ActiveGroupMembersByIDURL.values():
        A = automat.objects().get(automat_index, None)
        if not A:
            continue
        if A.customer_idurl == customer_idurl:
            result.append(A)
    return result

#------------------------------------------------------------------------------

class GroupQueueMember(automat.Automat):
    """
    This class implements all the functionality of ``group_queue_member()`` state machine.
    """

    def __init__(self, group_key_id, member_idurl=None, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `group_queue_member()` state machine.
        """
        self.broker_idurl = None
        self.broker_id = None
        self.queue_id = None
        self.member_idurl = member_idurl or my_id.getIDURL()
        self.member_id = self.member_idurl.to_id()
        self.group_key_id = group_key_id
        self.group_glob_id = global_id.ParseGlobalID(self.group_key_id)
        self.group_queue_alias = self.group_glob_id['key_alias']
        self.group_owner_id = self.group_glob_id['customer']
        self.customer_idurl = self.group_glob_id['idurl']
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
            'creator': self.customer_idurl,
            'state': self.state,
        }

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `group_queue_member()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `group_queue_member()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `group_queue_member()`
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
            elif event == 'connect':
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
            elif event == 'brokers-found':
                self.state = 'QUEUE?'
                self.doConnectQueue(*args, **kwargs)
            elif event == 'dht-read-failed':
                self.state = 'DISCONNECTED'
                self.doDisconnected(event, *args, **kwargs)
        #---HIRE_BROKERS---
        elif self.state == 'HIRE_BROKERS':
            if event == 'brokers-hired':
                self.state = 'QUEUE?'
                self.doConnectQueue(*args, **kwargs)
            elif event == 'brokers-fialed':
                self.state = 'DISCONNECTED'
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---QUEUE?---
        elif self.state == 'QUEUE?':
            if event == 'queue-failed':
                self.state = 'DISCONNECTED'
                self.doDisconnected(event, *args, **kwargs)
            elif event == 'queue-in-sync':
                self.state = 'IN_SYNC!'
                self.doConnected(*args, **kwargs)
            elif event == 'queue-connected':
                self.doReadQueue(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
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
        d = dht_relations.read_customer_message_brokers(self.customer_idurl)
        # TODO: add more validations of dht_result
        d.addCallback(self._on_read_customer_message_brokers)
        d.addErrback(lambda err: self.automat('fail', err))

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

    def doConnectQueue(self, *args, **kwargs):
        """
        Action method.
        """

    def doReadQueue(self, *args, **kwargs):
        """
        Action method.
        """
        self.broker_idurl = kwargs['broker_idurl']
        self.broker_id = global_id.idurl2glob(self.broker_idurl)
        self.queue_id = global_id.MakeGlobalQueueID(
            queue_alias=self.group_queue_alias,
            owner_id=self.group_owner_id,
            supplier_id=self.broker_id,
        )

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
        from chat import message
        result = message.send_message(
            json_data={
                'created': utime.get_sec1970(),
                'payload': json_payload,
                'queue_id': self.queue_id,
                'producer_id': self.member_id,
            },
            recipient_global_id=self.broker_id,
            # ping_timeout=ping_timeout,
            # message_ack_timeout=message_ack_timeout,
        )
        # ret = Deferred()
        # result.addCallback(lambda packet: ret.callback(OK(strng.to_text(packet), api_method='message_send')))
        # result.addErrback(lambda err: ret.callback(ERROR(err, api_method='message_send')))
        return result
