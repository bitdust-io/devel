#!/usr/bin/env python
# group_participant.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
#
# This file (group_participant.py) is part of BitDust Software.
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
.. module:: group_participant
.. role:: red

BitDust group_participant() Automat

EVENTS:
    * :red:`command-in`
    * :red:`connect`
    * :red:`disconnect`
    * :red:`init`
    * :red:`message-in`
    * :red:`push-message`
    * :red:`push-message-failed`
    * :red:`reconnect`
    * :red:`shutdown`
    * :red:`suppliers-connected`
    * :red:`suppliers-disconnected`
    * :red:`suppliers-read-failed`
    * :red:`suppliers-read-success`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import utime
from bitdust.lib import packetid
from bitdust.lib import serialization

from bitdust.main import config

from bitdust.services import driver

from bitdust.crypt import my_keys

from bitdust.dht import dht_relations

from bitdust.contacts import identitycache

from bitdust.p2p import commands
from bitdust.p2p import p2p_service
from bitdust.p2p import propagate
from bitdust.p2p import p2p_service_seeker

from bitdust.stream import message

from bitdust.access import groups

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

CRITICAL_PUSH_MESSAGE_FAILS = None
MAX_BUFFERED_MESSAGES = 50

#------------------------------------------------------------------------------

_ActiveGroupParticipants = {}
_ActiveGroupParticipantsByIDURL = {}

#------------------------------------------------------------------------------


def register_group_participant(A):
    global _ActiveGroupParticipants
    global _ActiveGroupParticipantsByIDURL
    if _Debug:
        lg.args(_DebugLevel, instance=repr(A))
    if A.group_key_id in _ActiveGroupParticipants:
        raise Exception('group_participant already exist')
    _ActiveGroupParticipants[A.group_key_id] = A
    if id_url.is_not_in(A.group_creator_idurl, _ActiveGroupParticipantsByIDURL):
        _ActiveGroupParticipantsByIDURL[A.group_creator_idurl] = []
    _ActiveGroupParticipantsByIDURL[A.group_creator_idurl].append(A)
    if _Debug:
        lg.args(_DebugLevel, group_creator_idurl=A.group_creator_idurl, group_key_id=A.group_key_id)


def unregister_group_participant(A):
    global _ActiveGroupParticipants
    global _ActiveGroupParticipantsByIDURL
    if _Debug:
        lg.args(_DebugLevel, instance=repr(A))
    if id_url.is_not_in(A.group_creator_idurl, _ActiveGroupParticipantsByIDURL):
        lg.warn('for given customer idurl %r did not found active group participants list' % A.group_creator_idurl)
    else:
        if A in _ActiveGroupParticipantsByIDURL[A.group_creator_idurl]:
            _ActiveGroupParticipantsByIDURL[A.group_creator_idurl].remove(A)
            if _Debug:
                lg.args(_DebugLevel, group_creator_idurl=A.group_creator_idurl, group_key_id=A.group_key_id)
        else:
            lg.warn('group_participant() instance not found for customer %r' % A.group_creator_idurl)
    return _ActiveGroupParticipants.pop(A.group_key_id, None)


#------------------------------------------------------------------------------


def list_active_group_participants():
    global _ActiveGroupParticipants
    return list(_ActiveGroupParticipants.keys())


def get_active_group_participant(group_key_id):
    global _ActiveGroupParticipants
    if group_key_id not in _ActiveGroupParticipants:
        return None
    return _ActiveGroupParticipants[group_key_id]


def find_active_group_participants(group_creator_idurl):
    global _ActiveGroupParticipantsByIDURL
    result = []
    for automat_index in _ActiveGroupParticipantsByIDURL.values():
        A = automat.by_index(automat_index, None)
        if not A:
            continue
        if A.group_creator_idurl == group_creator_idurl:
            result.append(A)
    return result


#------------------------------------------------------------------------------


def restart_active_group_participant(group_key_id):
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id)
    existing_group_participant = get_active_group_participant(group_key_id)
    if not existing_group_participant:
        lg.err('did not found active group participant %r' % group_key_id)
        return None
    result = Deferred()
    existing_index = existing_group_participant.index
    existing_publish_events = existing_group_participant.publish_events
    existing_group_participant.automat('shutdown')
    existing_group_participant = None
    del existing_group_participant
    new_group_participant = []

    def _on_group_participant_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, oldstate=oldstate, newstate=newstate, event_string=event_string)
        if newstate == 'CONNECTED' and oldstate != newstate:
            new_group_participant[0].removeStateChangedCallback(_on_group_participant_state_changed)
            result.callback(new_group_participant[0].to_json())
        if newstate == 'DISCONNECTED' and oldstate != newstate:
            new_group_participant[0].removeStateChangedCallback(_on_group_participant_state_changed)
            result.callback(new_group_participant[0].to_json())
        return None

    def _do_start_new_group_participant():
        new_group_participant.append(GroupParticipant(
            group_key_id=group_key_id,
            publish_events=existing_publish_events,
        ))
        new_index = new_group_participant[0].index
        new_group_participant[0].automat('init')
        new_group_participant[0].automat('connect')
        new_group_participant[0].addStateChangedCallback(_on_group_participant_state_changed)
        if _Debug:
            lg.args(_DebugLevel, group_key_id=group_key_id, existing=existing_index, new=new_index)

    reactor.callLater(0, _do_start_new_group_participant)  # @UndefinedVariable
    return result


#------------------------------------------------------------------------------


def rotate_active_group_participant(old_group_key_id, new_group_key_id):
    global _ActiveGroupParticipants
    A_old = get_active_group_participant(old_group_key_id)
    if not A_old:
        return False
    A_new = get_active_group_participant(new_group_key_id)
    if A_new and A_new in _ActiveGroupParticipants:
        lg.err('it seems group %r already rotated, but older copy also exists at the moment: %r' % (A_new, A_old))
        return False
    del A_new  # just my paranoia
    unregister_group_participant(A_old)
    A_old.update_group_key_id(new_group_key_id)
    register_group_participant(A_old)
    restart_active_group_participant(new_group_key_id)
    return True


#------------------------------------------------------------------------------


def start_group_participants():

    def _start():
        started = 0
        for group_key_id, _ in groups.active_groups().items():
            if not group_key_id:
                continue
            if group_key_id.startswith('person'):
                # TODO: temporarily disabled
                continue
            if not groups.is_group_active(group_key_id):
                continue
            if not my_keys.is_key_registered(group_key_id):
                lg.err('can not start GroupParticipant because key %r is not registered' % group_key_id)
                continue
            if not id_url.is_cached(global_id.glob2idurl(group_key_id, as_field=False)):
                continue
            existing_group_participant = get_active_group_participant(group_key_id)
            if not existing_group_participant:
                existing_group_participant = GroupParticipant(group_key_id)
                existing_group_participant.automat('init')
            existing_group_participant.automat('connect')
            started += 1
        if _Debug:
            lg.args(_DebugLevel, started=started)

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
        if group_key_id.startswith('person'):
            # TODO: temporarily disabled
            continue
        if not groups.is_group_active(group_key_id):
            continue
        if not my_keys.is_key_registered(group_key_id):
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


def shutdown_group_participants():
    stopped = 0
    for group_key_id in groups.active_groups().keys():
        existing_group_participant = get_active_group_participant(group_key_id)
        if not existing_group_participant:
            continue
        existing_group_participant.automat('shutdown')
        stopped += 1
    return stopped


#------------------------------------------------------------------------------


class GroupParticipant(automat.Automat):

    """
    This class implements all the functionality of ``group_participant()`` state machine.
    """

    def __init__(self, group_key_id, participant_idurl=None, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `group_participant()` state machine.
        """
        self.participant_idurl = participant_idurl or my_id.getIDURL()
        self.participant_id = self.participant_idurl.to_id()
        self.group_key_id = group_key_id
        self.group_glob_id = global_id.NormalizeGlobalID(self.group_key_id)
        self.group_queue_alias = self.group_glob_id['key_alias']
        self.group_creator_id = self.group_glob_id['customer']
        self.group_creator_idurl = self.group_glob_id['idurl']
        self.known_suppliers_list = []
        self.known_ecc_map = None
        self.active_supplier_pos = None
        self.active_supplier_idurl = None
        self.active_supplier_id = None
        self.active_queue_id = None
        self.suppliers_in_progress = []
        self.suppliers_succeed = []
        self.participant_sender_id = global_id.MakeGlobalID(idurl=self.participant_idurl, key_alias=self.group_queue_alias)
        self.last_sequence_id = groups.get_last_sequence_id(self.group_key_id)
        self.sequence_head = None
        self.sequence_tail = None
        self.sequence_count = None
        self.outgoing_messages = {}
        self.outgoing_counter = 0
        self.buffered_messages = {}
        self.recorded_messages = []
        self.message_ack_timeout = config.conf().getInt('services/private-groups/message-ack-timeout')
        super(GroupParticipant, self).__init__(
            name='group_participant_%s$%s' % (
                self.group_queue_alias,
                self.group_creator_id,
            ), state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs
        )

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        groups.run_group_state_callbacks(oldstate, newstate, self.to_json())

    def update_group_key_id(self, new_group_key_id):
        if _Debug:
            lg.args(_DebugLevel, old=self.group_key_id, new=new_group_key_id)
        self.group_key_id = new_group_key_id
        self.group_glob_id = global_id.NormalizeGlobalID(self.group_key_id)
        self.group_queue_alias = self.group_glob_id['key_alias']
        self.group_creator_id = self.group_glob_id['customer']
        self.group_creator_idurl = self.group_glob_id['idurl']
        self.participant_sender_id = global_id.MakeGlobalID(idurl=self.participant_idurl, key_alias=self.group_queue_alias)

    def to_json(self):
        j = super().to_json()
        j.update(
            {
                'active': groups.is_group_active(self.group_key_id),
                'participant_id': self.participant_id,
                'group_key_id': self.group_key_id,
                'alias': self.group_glob_id['key_alias'] if self.group_glob_id else '',
                'label': my_keys.get_label(self.group_key_id) or '',
                'creator': self.group_creator_id,
                'active_supplier_pos': self.active_supplier_pos,
                'active_supplier_id': self.active_supplier_id,
                'active_queue_id': self.active_queue_id,
                'last_sequence_id': self.last_sequence_id,
                'sequence_head': self.sequence_head,
                'sequence_tail': self.sequence_tail,
                'sequence_count': self.sequence_count,
            }
        )
        return j

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `group_participant()` machine.
        """

    def register(self):
        automat_index = automat.Automat.register(self)
        register_group_participant(self)
        return automat_index

    def unregister(self):
        unregister_group_participant(self)
        return automat.Automat.unregister(self)

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://github.com/vesellov/visio2python>`_ tool.
        """
        #---CONNECTED---
        if self.state == 'CONNECTED':
            if event == 'push-message':
                self.doPublish(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doReportDisconnected(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'reconnect':
                self.state = 'SUPPLIERS?'
                self.doReadSuppliersList(*args, **kwargs)
            elif event == 'disconnect':
                self.state = 'DISCONNECTED'
                self.doSuppliersUnsubscribe(*args, **kwargs)
                self.doDeactivate(event, *args, **kwargs)
                self.doReportDisconnected(*args, **kwargs)
            elif event == 'push-message-failed':
                self.doRotateSupplier(*args, **kwargs)
            elif event == 'message-in':
                self.doRecord(*args, **kwargs)
                self.doProcess(*args, **kwargs)
            elif event == 'command-in':
                self.doHandle(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'DISCONNECTED'
                self.NeedDisconnect = False
                self.doInit(*args, **kwargs)
        #---SUPPLIERS?---
        elif self.state == 'SUPPLIERS?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doReportDisconnected(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'suppliers-read-failed':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
            elif event == 'suppliers-read-success':
                self.state = 'SUBSCRIBE!'
                self.doSuppliersSubscribe(*args, **kwargs)
            elif event == 'disconnect':
                self.NeedDisconnect = True
        #---SUBSCRIBE!---
        elif self.state == 'SUBSCRIBE!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doReportDisconnected(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'suppliers-disconnected':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
            elif event == 'suppliers-connected' and self.NeedDisconnect:
                self.state = 'DISCONNECTED'
                self.NeedDisconnect = False
                self.doSuppliersUnsubscribe(*args, **kwargs)
                self.doDeactivate(event, *args, **kwargs)
                self.doReportDisconnected(*args, **kwargs)
            elif event == 'suppliers-connected' and not self.NeedDisconnect:
                self.state = 'CONNECTED'
                self.doReportConnected(*args, **kwargs)
            elif event == 'disconnect':
                self.NeedDisconnect = True
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDeactivate(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect' or event == 'reconnect':
                self.state = 'SUPPLIERS?'
                self.doActivate(*args, **kwargs)
                self.doReadSuppliersList(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

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

    def doActivate(self, *args, **kwargs):
        """
        Action method.
        """
        groups.set_group_active(self.group_key_id, True)
        groups.save_group_info(self.group_key_id)

    def doDeactivate(self, event, *args, **kwargs):
        """
        Action method.
        """
        if event in ['disconnect', 'suppliers-connected']:
            groups.set_group_active(self.group_key_id, False)
            groups.save_group_info(self.group_key_id)
        else:
            groups.save_group_info(self.group_key_id)
        if kwargs.get('erase_key', False):
            if my_keys.is_key_registered(self.group_key_id):
                my_keys.erase_key(self.group_key_id)
            else:
                lg.warn('key %r not registered, can not be erased' % self.group_key_id)

    def doPublish(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_send_message_to_supplier(
            json_payload=kwargs['json_payload'],
            outgoing_counter=None,
            packet_id=None,
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
            if self.sequence_count is not None:
                self.sequence_count += 1
                self.sequence_tail = recorded_kwargs['sequence_id']
                if self.sequence_head is None:
                    self.sequence_head = recorded_kwargs['sequence_id']

    def doHandle(self, *args, **kwargs):
        """
        Action method.
        """
        if not driver.is_on('service_message_history'):
            return
        self._do_handle_group_command(kwargs['json_message'])

    def doReadSuppliersList(self, *args, **kwargs):
        """
        Action method.
        """
        self.known_suppliers_list.clear()
        self.known_ecc_map = None
        self.active_supplier_pos = None
        self.active_supplier_idurl = None
        self.active_supplier_id = None
        self.active_queue_id = None
        d = dht_relations.read_customer_suppliers(self.group_creator_idurl, use_cache=True)
        d.addCallback(self._on_read_group_creator_suppliers)
        d.addErrback(lambda err: self.automat('suppliers-read-failed', err))

    def doSuppliersSubscribe(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            self.known_suppliers_list = [s for s in args[0]['suppliers'] if s]
        except:
            lg.exc()
            self.automat('suppliers-disconnected')
            return
        self.known_ecc_map = args[0].get('ecc_map')
        self.suppliers_in_progress.clear()
        self.suppliers_succeed.clear()
        for supplier_idurl in self.known_suppliers_list:
            if not supplier_idurl:
                continue
            self.suppliers_in_progress.append(supplier_idurl)
            if id_url.is_cached(supplier_idurl):
                self._do_connect_with_supplier(supplier_idurl)
            else:
                d = identitycache.immediatelyCaching(supplier_idurl)
                d.addCallback(lambda *a: self._do_connect_with_supplier(supplier_idurl))
                d.addErrback(self._on_supplier_connect_failed, supplier_idurl=kwargs['supplier_idurl'], reason='failed caching supplier identity')
        if _Debug:
            lg.args(_DebugLevel, known_ecc_map=self.known_ecc_map, known_suppliers_list=self.known_suppliers_list)

    def doSuppliersUnsubscribe(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_unsubscibe_all_suppliers()

    def doReportConnected(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_refresh_sequence_stats()
        self._do_send_message_to_supplier(
            json_payload={
                'command': 'connected',
                'participant_id': self.participant_id,
                'sequence_head': self.sequence_head,
                'sequence_tail': self.sequence_tail,
                'sequence_count': self.sequence_count,
            },
            outgoing_counter=None,
            packet_id=None,
        )

    def doReportDisconnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doRotateSupplier(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_rotate_active_supplier()

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        message.clear_consumer_callbacks(self.name)
        self.destroy()
        self.participant_idurl = None
        self.participant_id = None
        self.participant_sender_id = None
        self.group_glob_id = None
        self.group_queue_alias = None
        self.group_creator_id = None
        self.group_creator_idurl = None
        self.known_suppliers_list = None
        self.known_ecc_map = None
        self.active_supplier_pos = None
        self.active_supplier_idurl = None
        self.active_supplier_id = None
        self.active_queue_id = None
        self.suppliers_in_progress = []
        self.suppliers_succeed = []
        self.last_sequence_id = None
        self.sequence_head = None
        self.sequence_tail = None
        self.sequence_count = None
        self.recorded_messages = None
        self.buffered_messages = None

    def _do_connect_with_supplier(self, supplier_idurl):
        if _Debug:
            lg.args(_DebugLevel, supplier_idurl=supplier_idurl, group_creator_idurl=self.group_creator_idurl)
        group_key_info = {}
        if not my_keys.is_key_registered(self.group_key_id):
            lg.warn('closing group_participant %r because key %r is not registered' % (self, self.group_key_id))
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
        service_params = {
            'action': 'queue-connect',
            'consumer_id': self.participant_id,
            'producer_id': self.participant_id,
            'group_key': group_key_info,
            'last_sequence_id': self.last_sequence_id,
        }
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=supplier_idurl,
            service_name='service_joint_postman',
            service_params=service_params,
            request_service_timeout=30,
            attempts=1,
        )
        result.addCallback(self._on_supplier_connected, supplier_idurl=supplier_idurl)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_participant._do_connect_with_supplier')
        result.addErrback(self._on_supplier_connect_failed, supplier_idurl=supplier_idurl, reason='supplier request refused')

    def _do_check_all_suppliers_connected(self):
        critical_suppliers_number = 1
        if self.known_ecc_map:
            from bitdust.raid import eccmap
            critical_suppliers_number = eccmap.GetCorrectableErrors(eccmap.GetEccMapSuppliersNumber(self.known_ecc_map))
        if _Debug:
            lg.args(_DebugLevel, progress=len(self.suppliers_in_progress), succeed=self.suppliers_succeed, critical_suppliers_number=critical_suppliers_number)
        if len(self.suppliers_in_progress) == 0:
            if len(self.suppliers_succeed) >= critical_suppliers_number:
                self.automat('suppliers-connected')
            else:
                self.automat('suppliers-disconnected')

    def _do_unsubscibe_all_suppliers(self):
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
            return
        for supplier_idurl in self.known_suppliers_list:
            if not supplier_idurl:
                continue
            queue_id = global_id.MakeGlobalQueueID(
                queue_alias=self.group_queue_alias,
                owner_id=self.group_creator_id,
                supplier_id=supplier_idurl.to_id(),
            )
            service_info = {
                'action': 'queue-disconnect',
                'queue_id': queue_id,
                'consumer_id': self.participant_id,
                'producer_id': self.participant_id,
                'group_key': group_key_info,
                'last_sequence_id': self.last_sequence_id,
            }
            p2p_service.SendCancelService(
                remote_idurl=supplier_idurl,
                service_name='service_joint_postman',
                json_payload=service_info,
                # callbacks={
                #     commands.Ack(): self._supplier_queue_cancelled,
                #     commands.Fail(): self._supplier_queue_failed,
                # },
            )

    def _do_send_message_to_supplier(self, json_payload=None, outgoing_counter=None, packet_id=None):
        global CRITICAL_PUSH_MESSAGE_FAILS
        if CRITICAL_PUSH_MESSAGE_FAILS is None:
            CRITICAL_PUSH_MESSAGE_FAILS = int(os.environ.get('BITDUST_CRITICAL_PUSH_MESSAGE_FAILS', 2))
        if packet_id is None:
            packet_id = packetid.UniqueID()
        require_handshake = False
        if self.active_supplier_pos is None:
            self.active_supplier_pos = 0
        if not self.known_suppliers_list:
            lg.err('no suppliers found, shutting down %r' % self)
            self.automat('shutdown')
            return
        if not self.known_suppliers_list[self.active_supplier_pos]:
            if self.known_suppliers_list.count(None) == len(self.known_suppliers_list):
                lg.err('no known suppliers found, shutting down %r' % self)
                self.automat('shutdown')
                return
            while not self.known_suppliers_list[self.active_supplier_pos]:
                self.active_supplier_pos += 1
                if self.active_supplier_pos >= len(self.known_suppliers_list):
                    self.active_supplier_pos = 0
            self.active_supplier_idurl = self.known_suppliers_list[self.active_supplier_pos]
            self.active_supplier_id = self.active_supplier_idurl.to_id()
            self.active_queue_id = global_id.MakeGlobalQueueID(
                queue_alias=self.group_queue_alias,
                owner_id=self.group_creator_id,
                supplier_id=self.active_supplier_id,
            )
        if self.active_queue_id is None:
            self.active_supplier_idurl = self.known_suppliers_list[self.active_supplier_pos]
            self.active_supplier_id = self.active_supplier_idurl.to_id()
            self.active_queue_id = global_id.MakeGlobalQueueID(
                queue_alias=self.group_queue_alias,
                owner_id=self.group_creator_id,
                supplier_id=self.active_supplier_id,
            )
        if _Debug:
            lg.args(_DebugLevel, p=self.active_supplier_pos, s=self.active_supplier_id, counter=outgoing_counter, packet_id=packet_id)
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
                lg.err('failed sending message to supplier %r after %d attempts in %r' % (self.active_supplier_pos, self.outgoing_messages[outgoing_counter]['attempts'], self))
                # self.outgoing_messages[outgoing_counter]['attempts'] = 0
                # self.outgoing_messages[outgoing_counter]['last_attempt'] = None
                self.automat('shutdown')
                return
            self.outgoing_messages[outgoing_counter]['attempts'] += 1
            self.outgoing_messages[outgoing_counter]['last_attempt'] = utime.utcnow_to_sec1970()
            json_payload = self.outgoing_messages[outgoing_counter]['payload']
            if self.outgoing_messages[outgoing_counter]['attempts'] >= 1:
                require_handshake = True
            lg.warn('re-trying sending message to supplier %r  counter=%d attempts=%d packet_id=%s' % (self.active_supplier_pos, outgoing_counter, self.outgoing_messages[outgoing_counter]['attempts'], packet_id))
        raw_payload = serialization.DictToBytes(
            json_payload,
            pack_types=True,
            encoding='utf-8',
        )
        try:
            private_message_object = message.GroupMessage(
                recipient=self.group_key_id,
                sender=self.participant_sender_id,
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
                'producer_id': self.participant_id,
            },
            recipient_global_id=self.active_supplier_id,
            packet_id=packetid.MakeQueueMessagePacketID(self.active_queue_id, packet_id),
            message_ack_timeout=self.message_ack_timeout,
            skip_handshake=True,
            fire_callbacks=False,
            require_handshake=require_handshake,
        )
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_participant._do_send_message_to_supplier')
        d.addCallback(self._on_message_to_supplier_sent, outgoing_counter, packet_id)
        d.addErrback(self._on_message_to_supplier_failed, outgoing_counter, packet_id)

    def _do_read_queue_messages(self, json_messages):
        if not json_messages:
            return True
        if _Debug:
            lg.args(_DebugLevel, json_messages=len(json_messages))
        latest_known_sequence_id = -1
        received_group_messages = []
        packets_to_ack = {}
        found_group_ids = set()
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
            if msg_action == 'pull':
                try:
                    incoming_group_key_id = my_keys.latest_key_id(msg_data['group_key_id'])
                    incoming_participant_id = global_id.latest_glob_id(msg_data['participant_id'])
                    incoming_sequence_head = msg_data['sequence_head']
                    incoming_sequence_tail = msg_data['sequence_tail']
                    incoming_sequence_count = msg_data['sequence_count']
                except:
                    lg.exc(msg_data)
                    continue
                if incoming_group_key_id != self.group_key_id:
                    if _Debug:
                        lg.dbg(_DebugLevel, 'skip message from %r based on incoming group_key_id for %r : %r' % (incoming_participant_id, self.group_key_id, incoming_group_key_id))
                    continue
                self._do_push_messages_to_another_participant(
                    remote_id=incoming_participant_id,
                    sequence_head=incoming_sequence_head,
                    sequence_tail=incoming_sequence_tail,
                    sequence_count=incoming_sequence_count,
                )
                return True
            incoming_queue_id = packetid.SplitQueueMessagePacketID(packet_id)[0]
            incoming_group_alias, incoming_group_creator_id, incoming_supplier_id = global_id.SplitGlobalQueueID(incoming_queue_id)
            incoming_group_creator_id = global_id.latest_glob_id(incoming_group_creator_id)
            incoming_group_key_id = global_id.MakeGlobalKeyID(incoming_group_alias, incoming_group_creator_id)
            found_group_ids.add(incoming_group_key_id)
            if incoming_group_key_id != self.group_key_id:
                if _Debug:
                    lg.dbg(_DebugLevel, 'skip message from %r based on packet_id for %r : %r' % (incoming_supplier_id, self.group_key_id, incoming_group_key_id))
                continue
            if msg_action == 'push':
                received_group_messages = []
                for msg in msg_data.get('items', []):
                    received_group_messages.append(dict(
                        json_message=msg['data'],
                        direction='incoming',
                        group_key_id=self.group_key_id,
                        producer_id=msg['producer_id'],
                        sequence_id=int(msg['message_id']),
                    ))
                self._do_process_group_messages(received_group_messages)
                return True
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
            if chunk_last_sequence_id is not None and chunk_last_sequence_id > latest_known_sequence_id:
                latest_known_sequence_id = chunk_last_sequence_id
            for one_message in list_messages:
                if one_message['sequence_id'] > latest_known_sequence_id:
                    lg.warn('incoming sequence_id %d is older than known last_sequence_id %d' % (one_message['sequence_id'], latest_known_sequence_id))
                    # continue
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
        if not packets_to_ack:
            if _Debug:
                lg.args(_DebugLevel, json_messages=json_messages)
            return True
        for packet_id, owner_idurl in packets_to_ack.items():
            p2p_service.SendAckNoRequest(owner_idurl, packet_id)
        packets_to_ack.clear()
        if not received_group_messages:
            if self.group_key_id not in found_group_ids:
                if _Debug:
                    lg.dbg(_DebugLevel, 'no messages for %r found in the incoming stream' % self.group_key_id)
                return True
            if latest_known_sequence_id < self.last_sequence_id:
                lg.err('found queue latest sequence %d is behind of my current position %d' % (latest_known_sequence_id, self.last_sequence_id))
            if latest_known_sequence_id > self.last_sequence_id:
                lg.warn('nothing received, but found queue latest sequence %d is ahead of my current position %d, need to read messages from archive' % (latest_known_sequence_id, self.last_sequence_id))
            self.last_sequence_id = latest_known_sequence_id
            groups.set_last_sequence_id(self.group_key_id, latest_known_sequence_id)
            groups.save_group_info(self.group_key_id)
            if _Debug:
                lg.dbg(_DebugLevel, 'no new messages, queue in sync, latest_known_sequence_id=%d' % latest_known_sequence_id)
            return True
        received_group_messages.sort(key=lambda m: m['sequence_id'])
        ret = self._do_process_group_messages(received_group_messages)
        return ret

    def _do_process_group_messages(self, received_group_messages):
        if _Debug:
            lg.args(_DebugLevel, received_group_messages=len(received_group_messages), buffered_messages=len(self.buffered_messages))
        newly_processed = 0
        for new_message in received_group_messages:
            new_sequence_id = new_message['sequence_id']
            if new_sequence_id in self.buffered_messages:
                lg.warn('message %d already buffered' % new_sequence_id)
                continue
            self.buffered_messages[new_sequence_id] = new_message
        buffered_sequence_ids = sorted(self.buffered_messages.keys())
        for new_sequence_id in buffered_sequence_ids:
            newly_processed += 1
            inp_message = self.buffered_messages.pop(new_sequence_id)
            inp_message['fast'] = True
            command = inp_message.get('json_message', {}).get('command', None)
            if command:
                if _Debug:
                    lg.dbg(_DebugLevel, 'new command received in %r, last_sequence_id incremented to %d' % (self, self.last_sequence_id))
                self.automat('command-in', **inp_message)
            else:
                if _Debug:
                    lg.dbg(_DebugLevel, 'new message consumed in %r, last_sequence_id incremented to %d' % (self, self.last_sequence_id))
                self.last_sequence_id = new_sequence_id
                groups.set_last_sequence_id(self.group_key_id, self.last_sequence_id)
                groups.save_group_info(self.group_key_id)
                self.automat('message-in', **inp_message)
        if len(self.buffered_messages) > MAX_BUFFERED_MESSAGES:
            raise Exception('message sequence is broken, currently %d buffered messages' % len(self.buffered_messages))
        if _Debug:
            lg.dbg(_DebugLevel, 'my_last_sequence_id=%d  newly_processed=%d  buffered_messages=%d' % (self.last_sequence_id, newly_processed, len(self.buffered_messages)))
        return True

    def _do_rotate_active_supplier(self):
        if not self.known_suppliers_list:
            lg.err('no suppliers found, shutting down %r' % self)
            self.automat('shutdown')
            return
        if self.known_suppliers_list.count(None) == len(self.known_suppliers_list):
            lg.err('no known suppliers found, shutting down %r' % self)
            self.automat('shutdown')
            return
        current_active_supplier_pos = self.active_supplier_pos
        if self.active_supplier_pos is None:
            self.active_supplier_pos = 0
        self.active_supplier_pos += 1
        if self.active_supplier_pos >= len(self.known_suppliers_list):
            self.active_supplier_pos = 0
        while not self.known_suppliers_list[self.active_supplier_pos]:
            self.active_supplier_pos += 1
            if self.active_supplier_pos >= len(self.known_suppliers_list):
                self.active_supplier_pos = 0
        self.active_supplier_idurl = self.known_suppliers_list[self.active_supplier_pos]
        self.active_supplier_id = self.active_supplier_idurl.to_id()
        self.active_queue_id = global_id.MakeGlobalQueueID(
            queue_alias=self.group_queue_alias,
            owner_id=self.group_creator_id,
            supplier_id=self.active_supplier_id,
        )
        if _Debug:
            lg.args(_DebugLevel, current=current_active_supplier_pos, new=self.active_supplier_pos)

    def _do_refresh_sequence_stats(self):
        if driver.is_on('service_message_history'):
            from bitdust.chat import message_database
            head = None
            tail = None
            count = 0
            for stored_message in message_database.query_messages(
                recipient_id=self.group_key_id,
                bidirectional=False,
                message_types=[
                    'group_message',
                ],
            ):
                try:
                    message_id = int(stored_message['payload']['message_id'])
                except:
                    lg.exc()
                    continue
                if head is None:
                    head = message_id
                if tail is None:
                    tail = message_id
                if count is None:
                    count = 0
                if head > message_id:
                    head = message_id
                if tail < message_id:
                    tail = message_id
                count += 1
            self.sequence_head = head
            self.sequence_tail = tail
            self.sequence_count = count
        else:
            self.sequence_head = None
            self.sequence_tail = None
            self.sequence_count = None
        if _Debug:
            lg.args(_DebugLevel, count=self.sequence_count, head=self.sequence_head, tail=self.sequence_tail, recipient_id=self.group_key_id)

    def _do_handle_group_command(self, json_message):
        command = json_message['command']
        incoming_participant_id = json_message.get('participant_id')
        if _Debug:
            lg.dbg(_DebugLevel, 'received command [%s] from %r in %r' % (command.upper(), incoming_participant_id, self))
        if command == 'connected':
            if incoming_participant_id:
                incoming_participant_id = my_keys.latest_key_id(incoming_participant_id)
                if incoming_participant_id != self.participant_id:
                    if self.sequence_count is None:
                        self._do_refresh_sequence_stats()
                    incoming_sequence_head = json_message.get('sequence_head', None)
                    incoming_sequence_tail = json_message.get('sequence_tail', None)
                    incoming_sequence_count = json_message.get('sequence_count', None)
                    pull_required = False
                    pull_sequence_head = None
                    pull_sequence_tail = None
                    pull_sequence_count = None
                    push_required = False
                    push_sequence_head = None
                    push_sequence_tail = None
                    push_sequence_count = None
                    if incoming_sequence_count is not None:
                        if self.sequence_head is not None:
                            if incoming_sequence_head is None:
                                push_required = True
                                push_sequence_head = self.sequence_head
                            elif incoming_sequence_head < self.sequence_head:
                                pull_required = True
                                pull_sequence_head = incoming_sequence_head
                            elif incoming_sequence_head > self.sequence_head:
                                push_required = True
                                push_sequence_head = self.sequence_head
                        if self.sequence_tail is not None:
                            if incoming_sequence_tail is None:
                                push_required = True
                                push_sequence_tail = self.sequence_tail
                            elif incoming_sequence_tail > self.sequence_tail:
                                pull_required = True
                                pull_sequence_tail = incoming_sequence_tail
                            elif incoming_sequence_tail < self.sequence_tail:
                                push_required = True
                                push_sequence_tail = self.sequence_tail
                        if self.sequence_count is not None:
                            if incoming_sequence_count is None:
                                push_required = True
                                push_sequence_count = self.sequence_count
                            elif incoming_sequence_count < self.sequence_count:
                                push_required = True
                                push_sequence_count = self.sequence_count
                            elif incoming_sequence_count > self.sequence_count:
                                pull_required = True
                                pull_sequence_count = incoming_sequence_count
                    else:
                        if self.sequence_count is not None:
                            push_required = True
                            push_sequence_head = self.sequence_head
                            push_sequence_tail = self.sequence_tail
                            push_sequence_count = self.sequence_count
                    if _Debug:
                        lg.args(_DebugLevel, pull_required=pull_required, push_required=push_required)
                    if pull_required:
                        self._do_pull_messages_from_another_participant(
                            remote_id=incoming_participant_id,
                            sequence_head=pull_sequence_head,
                            sequence_tail=pull_sequence_tail,
                            sequence_count=pull_sequence_count,
                        )
                    if push_required:
                        self._do_push_messages_to_another_participant(
                            remote_id=incoming_participant_id,
                            sequence_head=push_sequence_head,
                            sequence_tail=push_sequence_tail,
                            sequence_count=push_sequence_count,
                        )
        else:
            lg.err('unknown incoming command %r from %r' % (command, incoming_participant_id))

    def _do_push_messages_to_another_participant(self, remote_id, sequence_head, sequence_tail, sequence_count):
        messages = []
        if driver.is_on('service_message_history'):
            from bitdust.chat import message_database
            messages.extend(
                [
                    {
                        'data': m['payload']['data'],
                        'producer_id': m['sender']['glob_id'],
                        'message_id': m['payload']['message_id'],
                    } for m in message_database.query_messages(
                        recipient_id=self.group_key_id,
                        bidirectional=False,
                        message_types=[
                            'group_message',
                        ],
                        sequence_head=sequence_head,
                        sequence_tail=sequence_tail,
                        limit=max(sequence_count, 1000),
                    )
                ]
            )
        queue_id = global_id.MakeGlobalQueueID(
            queue_alias=self.group_queue_alias,
            owner_id=self.group_creator_id,
            supplier_id=self.active_supplier_id,
        )
        packet_id = packetid.MakeQueueMessagePacketID(queue_id, packetid.UniqueID())
        ret = message.send_message(
            json_data={
                'msg_type': 'queue_message',
                'action': 'push',
                'created': utime.utcnow_to_sec1970(),
                'group_key_id': self.group_key_id,
                'participant_id': self.participant_id,
                'items': messages,
            },
            recipient_global_id=remote_id,
            packet_id=packet_id,
            # skip_handshake=True,
            fire_callbacks=False,
        )
        ret.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, ignore=True, method='group_participant._do_push_messages_to_another_participant')
        if _Debug:
            lg.out(_DebugLevel, '>>> PUSH >>>    %d messages from %r to %r with head=%r tail=%r count=%r' % (len(messages), self, remote_id, sequence_head, sequence_tail, sequence_count))

    def _do_pull_messages_from_another_participant(self, remote_id, sequence_head, sequence_tail, sequence_count):
        queue_id = global_id.MakeGlobalQueueID(
            queue_alias=self.group_queue_alias,
            owner_id=self.group_creator_id,
            supplier_id=self.active_supplier_id,
        )
        packet_id = packetid.MakeQueueMessagePacketID(queue_id, packetid.UniqueID())
        ret = message.send_message(
            json_data={
                'msg_type': 'queue_message',
                'action': 'pull',
                'created': utime.utcnow_to_sec1970(),
                'group_key_id': self.group_key_id,
                'participant_id': self.participant_id,
                'sequence_head': sequence_head,
                'sequence_tail': sequence_tail,
                'sequence_count': sequence_count,
            },
            recipient_global_id=remote_id,
            packet_id=packet_id,
            # skip_handshake=True,
            fire_callbacks=False,
        )
        ret.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, ignore=True, method='group_participant._do_pull_messages_from_another_participant')
        if _Debug:
            lg.out(_DebugLevel, '>>> PULL >>>    from %r to %r with head=%r tail=%r count=%r' % (self, remote_id, sequence_head, sequence_tail, sequence_count))

    def _on_message_to_supplier_sent(self, response_packet, outgoing_counter, packet_id):
        if _Debug:
            lg.args(_DebugLevel, response_packet=response_packet, outgoing_counter=outgoing_counter, packet_id=packet_id)
        if outgoing_counter not in self.outgoing_messages:
            raise Exception('outgoing message with counter %d not found' % outgoing_counter)
        if response_packet and response_packet.Command == commands.Ack():
            self.outgoing_messages.pop(outgoing_counter)
            self.automat('message-pushed', outgoing_counter=outgoing_counter)
            return
        self._do_send_message_to_supplier(json_payload=None, outgoing_counter=outgoing_counter, packet_id=None)

    def _on_message_to_supplier_failed(self, err, outgoing_counter, packet_id):
        if _Debug:
            lg.args(_DebugLevel, err=err, outgoing_counter=outgoing_counter, packet_id=packet_id)
        self.outgoing_messages[outgoing_counter]['last_attempt'] = None
        self._do_rotate_active_supplier()
        self._do_send_message_to_supplier(json_payload=None, outgoing_counter=outgoing_counter, packet_id=None)

    def _on_read_group_creator_suppliers(self, dht_value):
        if _Debug:
            lg.args(_DebugLevel, dht_value=dht_value)
        # TODO: use known list of suppliers from shared_access_coordinator() if it is connected already
        if dht_value and isinstance(dht_value, dict) and len(dht_value.get('suppliers', [])) > 0:
            self.automat('suppliers-read-success', dht_value)
        else:
            self.automat('suppliers-read-failed', Exception('customer suppliers not found in DHT'))

    def _on_supplier_connected(self, response_info, supplier_idurl):
        if _Debug:
            lg.args(_DebugLevel, s=supplier_idurl, response_info=response_info)
        if supplier_idurl in self.suppliers_in_progress:
            self.suppliers_in_progress.remove(supplier_idurl)
            if supplier_idurl not in self.suppliers_succeed:
                self.suppliers_succeed.append(supplier_idurl)
        else:
            lg.warn('supplier %s was already processed in %r' % (supplier_idurl, self))
        self._do_check_all_suppliers_connected()

    def _on_supplier_connect_failed(self, err, supplier_idurl, reason):
        lg.err('supplier %s failed with %r : %r' % (supplier_idurl, err, reason))
        if supplier_idurl in self.suppliers_in_progress:
            self.suppliers_in_progress.remove(supplier_idurl)
        else:
            lg.warn('supplier %s was already processed in %r' % (supplier_idurl, self))
        self.automat('supplier-failed', supplier_idurl=supplier_idurl)
        self._do_check_all_suppliers_connected()
        return None
