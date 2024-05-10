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
    * :red:`connect`
    * :red:`disconnect`
    * :red:`init`
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

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.crypt import my_keys

from bitdust.dht import dht_relations

from bitdust.contacts import identitycache

from bitdust.p2p import p2p_service
from bitdust.p2p import propagate
from bitdust.p2p import p2p_service_seeker

from bitdust.access import groups

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

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
        for group_key_id, group_info in groups.active_groups().items():
            if not group_key_id:
                continue
            if not my_keys.is_key_registered(group_key_id):
                lg.err('can not start GroupParticipant because key %r is not registered' % group_key_id)
                continue
            if group_key_id.startswith('person'):
                # TODO: temporarily disabled
                continue
            if not group_info['active']:
                continue
            if not id_url.is_cached(global_id.glob2idurl(group_key_id, as_field=False)):
                continue
            existing_group_participant = get_active_group_participant(group_key_id)
            if not existing_group_participant:
                existing_group_participant = GroupParticipant(group_key_id)
                existing_group_participant.automat('init')
            existing_group_participant.automat('connect')
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
        self.suppliers_in_progress = []
        self.suppliers_succeed = []
        self.participant_sender_id = global_id.MakeGlobalID(idurl=self.participant_idurl, key_alias=self.group_queue_alias)
        self.last_sequence_id = groups.get_last_sequence_id(self.group_key_id)
        self.outgoing_messages = {}
        self.outgoing_counter = 0
        self.buffered_messages = {}
        self.recorded_messages = []
        super(GroupParticipant, self).__init__(
            name='group_participant_%s$%s' % (
                self.group_queue_alias,
                self.group_creator_id,
            ), state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs
        )

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
                'alias': self.group_glob_id['key_alias'],
                'label': my_keys.get_label(self.group_key_id) or '',
                'creator': self.group_creator_id,
                'last_sequence_id': self.last_sequence_id,
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
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'DISCONNECTED'
                self.NeedDisconnect = False
                self.doInit(*args, **kwargs)
        #---SUPPLIERS?---
        elif self.state == 'SUPPLIERS?':
            if event == 'shutdown':
                self.state = 'CLOSED'
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
                self.doDestroyMe(*args, **kwargs)
            elif event == 'suppliers-disconnected':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
            elif event == 'suppliers-connected' and self.NeedDisconnect:
                self.state = 'DISCONNECTED'
                self.NeedDisconnect = False
                self.doSuppliersUnsubscribe(*args, **kwargs)
                self.doReportDisconnected(*args, **kwargs)
            elif event == 'suppliers-connected' and not self.NeedDisconnect:
                self.state = 'CONNECTED'
                self.doReportConnected(*args, **kwargs)
            elif event == 'disconnect':
                self.NeedDisconnect = True
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'reconnect':
                self.state = 'SUPPLIERS?'
                self.doReadSuppliersList(*args, **kwargs)
            elif event == 'disconnect':
                self.state = 'DISCONNECTED'
                self.doSuppliersUnsubscribe(*args, **kwargs)
                self.doReportDisconnected(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect' or event == 'reconnect':
                self.state = 'SUPPLIERS?'
                self.doReadSuppliersList(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doReadSuppliersList(self, *args, **kwargs):
        """
        Action method.
        """
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

    def doReportDisconnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportConnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
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
        self.suppliers_in_progress = None
        self.suppliers_succeed = None

    def _do_connect_with_supplier(self, supplier_idurl):
        if _Debug:
            lg.args(_DebugLevel, supplier_idurl=supplier_idurl, group_creator_idurl=self.group_creator_idurl)
        queue_id = global_id.MakeGlobalQueueID(
            queue_alias=self.group_queue_alias,
            owner_id=self.group_creator_id,
            supplier_id=supplier_idurl.to_id(),
        )
        service_params = {
            'items': [
                {
                    'scope': 'consumer',
                    'action': 'start',
                    'consumer_id': self.participant_id,
                },
                {
                    'scope': 'consumer',
                    'action': 'add_callback',
                    'consumer_id': self.participant_id,
                    'method': self.participant_idurl,
                    'queues': [
                        self.group_queue_alias,
                    ],
                },
                {
                    'scope': 'consumer',
                    'action': 'subscribe',
                    'consumer_id': self.participant_id,
                    'queue_id': queue_id,
                },
            ],
        }
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=supplier_idurl,
            service_name='service_p2p_notifications',
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
        for supplier_idurl in self.known_suppliers_list:
            queue_id = global_id.MakeGlobalQueueID(
                queue_alias=self.group_queue_alias,
                owner_id=self.group_creator_id,
                supplier_id=supplier_idurl.to_id(),
            )
            service_info = {
                'items': [
                    {
                        'scope': 'consumer',
                        'action': 'unsubscribe',
                        'consumer_id': self.participant_id,
                        'queue_id': queue_id,
                    },
                    {
                        'scope': 'consumer',
                        'action': 'remove_callback',
                        'consumer_id': self.participant_id,
                        'method': self.participant_idurl,
                    },
                    {
                        'scope': 'consumer',
                        'action': 'stop',
                        'consumer_id': self.participant_id,
                    },
                ],
            }
            p2p_service.SendCancelService(
                remote_idurl=self.supplier_idurl,
                service_name='service_p2p_notifications',
                json_payload=service_info,
                # callbacks={
                #     commands.Ack(): self._supplier_queue_cancelled,
                #     commands.Fail(): self._supplier_queue_failed,
                # },
            )

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
