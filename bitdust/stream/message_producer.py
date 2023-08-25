#!/usr/bin/env python
# message_producer.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
#
# This file (message_producer.py) is part of BitDust Software.
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
.. module:: message_producer
.. role:: red

BitDust message_producer() Automat

EVENTS:
    * :red:`broker-connected`
    * :red:`broker-failed`
    * :red:`brokers-found`
    * :red:`brokers-not-found`
    * :red:`connect`
    * :red:`disconnect`
    * :red:`init`
    * :red:`push-message`
    * :red:`shutdown`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import packetid
from bitdust.lib import serialization
from bitdust.lib import utime

from bitdust.main import config

from bitdust.contacts import identitycache

from bitdust.dht import dht_relations

from bitdust.access import groups

from bitdust.p2p import p2p_service_seeker

from bitdust.stream import message

from bitdust.crypt import my_keys

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_ActiveMessageProducers = {}
_ActiveMessageProducersByIDURL = {}

#------------------------------------------------------------------------------


def register_message_producer(A):
    global _ActiveMessageProducers
    global _ActiveMessageProducersByIDURL
    if _Debug:
        lg.args(_DebugLevel, instance=repr(A))
    if A.group_key_id in _ActiveMessageProducers:
        raise Exception('message_producer already exist')
    _ActiveMessageProducers[A.group_key_id] = A
    if id_url.is_not_in(A.group_creator_idurl, _ActiveMessageProducersByIDURL):
        _ActiveMessageProducersByIDURL[A.group_creator_idurl] = []
    _ActiveMessageProducersByIDURL[A.group_creator_idurl].append(A)


def unregister_message_producer(A):
    global _ActiveMessageProducers
    global _ActiveMessageProducersByIDURL
    if _Debug:
        lg.args(_DebugLevel, instance=repr(A))
    if id_url.is_not_in(A.group_creator_idurl, _ActiveMessageProducersByIDURL):
        lg.warn('for given customer idurl %r did not found active message producer' % A.group_creator_idurl)
    else:
        if A in _ActiveMessageProducersByIDURL[A.group_creator_idurl]:
            _ActiveMessageProducersByIDURL[A.group_creator_idurl].remove(A)
        else:
            lg.warn('message_producer() instance not found for customer %r' % A.group_creator_idurl)
    _ActiveMessageProducers.pop(A.group_key_id, None)


#------------------------------------------------------------------------------


def list_active_message_producers():
    global _ActiveMessageProducers
    return list(_ActiveMessageProducers.keys())


def get_active_message_producer(group_key_id):
    global _ActiveMessageProducers
    if group_key_id not in _ActiveMessageProducers:
        return None
    return _ActiveMessageProducers[group_key_id]


def find_active_message_producers(group_creator_idurl):
    global _ActiveMessageProducersByIDURL
    result = []
    for automat_index in _ActiveMessageProducersByIDURL.values():
        A = automat.by_index(automat_index)
        if not A:
            continue
        if A.group_creator_idurl == group_creator_idurl:
            result.append(A)
    return result


#------------------------------------------------------------------------------


def start_message_producers():
    started = 0
    for key_id in my_keys.known_keys().keys():
        # if not key_id.startswith('person$'):
        #     continue
        group_key_id = key_id
        existing_message_producer = get_active_message_producer(group_key_id)
        if not existing_message_producer:
            existing_message_producer = MessageProducer(group_key_id)
            existing_message_producer.automat('init')
        if existing_message_producer.state in [
            'DHT_READ?',
            'BROKER?',
            'CONNECTED',
        ]:
            continue
        existing_message_producer.automat('connect')
        started += 1
    return started


def shutdown_message_producers():
    global _ActiveMessageProducers
    stopped = 0
    for group_key_id in list(_ActiveMessageProducers.keys()):
        existing_message_producer = get_active_message_producer(group_key_id)
        if not existing_message_producer:
            continue
        existing_message_producer.automat('shutdown')
        stopped += 1
    return stopped


#------------------------------------------------------------------------------


def do_send_message(active_message_producer, data, result_defer):
    if _Debug:
        lg.args(_DebugLevel, active_message_producer=active_message_producer)
    active_message_producer.automat('push-message', json_payload=data)
    result_defer.callback(True)
    return None


def do_start_message_producer(group_key_id, data, result_defer):
    active_message_producer = get_active_message_producer(group_key_id)
    if _Debug:
        lg.args(_DebugLevel, active_message_producer=active_message_producer)
    if not active_message_producer:
        active_message_producer = MessageProducer(group_key_id)
        active_message_producer.automat('init')
    if active_message_producer.state == 'CONNECTED':
        do_send_message(active_message_producer, data, result_defer)
        return active_message_producer

    def _on_message_producer_state_changed(oldstate, newstate, event_string, args):
        if _Debug:
            lg.args(_DebugLevel, oldstate=oldstate, newstate=newstate, event_string=event_string)
        if newstate == 'CONNECTED' and oldstate != newstate:
            active_message_producer.removeStateChangedCallback(_on_message_producer_state_changed)
            do_send_message(active_message_producer, data, result_defer)
        if newstate == 'DISCONNECTED' and oldstate != newstate:
            active_message_producer.removeStateChangedCallback(_on_message_producer_state_changed)
            if not result_defer.called:
                result_defer.errback(Exception('disconnected'))
        return None

    active_message_producer.addStateChangedCallback(_on_message_producer_state_changed)
    active_message_producer.automat('connect')
    return active_message_producer


def push_message(group_key_id, data):
    creator_idurl = my_keys.get_creator_idurl(group_key_id, as_field=False)
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id, creator_idurl=creator_idurl)
    ret = Deferred()
    if not id_url.is_cached(creator_idurl):
        d = identitycache.immediatelyCaching(creator_idurl)
        d.addErrback(ret.errback)
        d.addCallback(lambda *args: do_start_message_producer(group_key_id, data, ret))
        return ret
    do_start_message_producer(group_key_id, data, ret)
    return ret


#------------------------------------------------------------------------------


class MessageProducer(automat.Automat):
    """
    This class implements all the functionality of ``message_producer()`` state machine.
    """
    def __init__(self, group_key_id, debug_level=_Debug, log_events=_Debug, log_transitions=_DebugLevel, **kwargs):
        """
        Builds `message_producer()` state machine.
        """
        self.producer_id = my_id.getGlobalID(key_alias='person')
        self.group_key_id = group_key_id
        self.group_glob_id = global_id.ParseGlobalID(self.group_key_id)
        self.group_creator_id = self.group_glob_id['customer']
        self.group_creator_idurl = self.group_glob_id['idurl']
        self.active_broker_id = None
        super(MessageProducer, self).__init__(name='message_producer_%s' % self.group_creator_id, state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=False, **kwargs)

    def to_json(self):
        j = super().to_json()
        j.update({
            'group_key_id': self.group_key_id,
            'label': my_keys.get_label(self.group_key_id) or '',
            'creator': self.group_creator_idurl,
            'active_broker_id': self.active_broker_id,
        })
        return j

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `message_producer()` machine.
        """

    def register(self):
        """
        """
        automat_index = automat.Automat.register(self)
        register_message_producer(self)
        return automat_index

    def unregister(self):
        """
        """
        unregister_message_producer(self)
        return automat.Automat.unregister(self)

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `message_producer()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `message_producer()`
        but automat state was not changed.
        """

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
            if event == 'disconnect' or event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.state = 'DHT_READ?'
                self.doDHTReadBrokers(*args, **kwargs)
        #---DHT_READ?---
        elif self.state == 'DHT_READ?':
            if event == 'disconnect' or event == 'brokers-not-found':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(event, *args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'brokers-found':
                self.state = 'BROKER?'
                self.doConnectFirstBroker(*args, **kwargs)
        #---BROKER?---
        elif self.state == 'BROKER?':
            if event == 'disconnect' or event == 'broker-failed':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(event, *args, **kwargs)
            elif event == 'broker-connected':
                self.state = 'CONNECTED'
                self.doRememberBroker(*args, **kwargs)
                self.doReportConnected(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'disconnect':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(event, *args, **kwargs)
            elif event == 'push-message':
                self.doSendMessageToBroker(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doDHTReadBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        result = dht_relations.read_customer_message_brokers(
            self.group_creator_idurl,
            positions=list(range(groups.REQUIRED_BROKERS_COUNT)),
            use_cache=False,
        )
        # TODO: add more validations of dht_result
        result.addCallback(self._on_read_customer_message_brokers)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='message_producer.doDHTReadBrokers')
        result.addErrback(lambda err: self.automat('dht-read-failed', err))

    def doConnectFirstBroker(self, *args, **kwargs):
        """
        Action method.
        """
        existing_brokers = args[0]
        if _Debug:
            lg.args(_DebugLevel, existing_brokers=existing_brokers)
        known_brokers = [
            None,
        ]*groups.REQUIRED_BROKERS_COUNT
        top_broker_pos = None
        top_broker_idurl = None
        for broker_pos in range(groups.REQUIRED_BROKERS_COUNT):
            broker_at_position = None
            for existing_broker in existing_brokers:
                if existing_broker['position'] == broker_pos and existing_broker['broker_idurl']:
                    broker_at_position = existing_broker
                    break
            if not broker_at_position:
                continue
            try:
                broker_idurl = broker_at_position['broker_idurl']
            except IndexError:
                broker_idurl = None
            if not broker_idurl:
                lg.warn('broker is empty for %r at position %d' % (self.group_key_id, broker_pos))
                continue
            known_brokers[broker_pos] = broker_idurl
            if _Debug:
                lg.dbg(_DebugLevel, 'found broker %r at position %r for %r' % (broker_idurl, broker_pos, self.group_key_id))
            if top_broker_pos is None:
                top_broker_pos = broker_pos
                top_broker_idurl = broker_idurl
            if broker_pos < top_broker_pos:
                top_broker_pos = broker_pos
                top_broker_idurl = broker_idurl
        if _Debug:
            lg.args(_DebugLevel, known_brokers=known_brokers)
        if top_broker_idurl is None:
            lg.info('did not found any existing brokers for %r' % self.group_key_id)
            self.automat('broker-failed')
            return
        if _Debug:
            lg.args(_DebugLevel, top_broker_pos=top_broker_pos, top_broker_idurl=top_broker_idurl)
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=top_broker_idurl,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params(idurl, top_broker_pos),
            attempts=1,
        )
        result.addCallback(self._on_broker_connected, top_broker_pos)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='message_producer.doConnectFirstBroker')
        result.addErrback(self._on_message_broker_connect_failed, top_broker_pos)

    def doRememberBroker(self, *args, **kwargs):
        """
        Action method.
        """
        self.active_broker_id = args[0]
        self.active_queue_id = global_id.MakeGlobalQueueID(
            queue_alias=self.group_glob_id['key_alias'],
            owner_id=self.group_creator_id,
            supplier_id=self.active_broker_id,
        )

    def doReportConnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportDisconnected(self, event, *args, **kwargs):
        """
        Action method.
        """

    def doSendMessageToBroker(self, *args, **kwargs):
        """
        Action method.
        """
        data = kwargs['json_payload']
        data['msg_type'] = 'personal_message'
        data['action'] = 'read'
        self._do_send_message_to_broker(
            json_payload=data,
            outgoing_counter=None,
            packet_id='personal_%s' % packetid.UniqueID(),
        )

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()
        self.producer_id = None
        self.group_key_id = None
        self.group_glob_id = None
        self.group_creator_id = None
        self.group_creator_idurl = None
        self.active_broker_id = None

    def _on_read_customer_message_brokers(self, brokers_info_list):
        if _Debug:
            lg.args(_DebugLevel, brokers=len(brokers_info_list))
        if not brokers_info_list:
            self.automat('brokers-not-found', [])
            return
        self.automat('brokers-found', brokers_info_list)

    def _on_message_broker_connect_failed(self, err, broker_pos):
        if _Debug:
            lg.args(_DebugLevel, err=err, broker_pos=broker_pos)
        self.automat('broker-failed')

    def _on_broker_connected(self, response_info, broker_pos, *a, **kw):
        if _Debug:
            lg.args(_DebugLevel, resp=response_info, broker_pos=broker_pos)
        self.automat('broker-connected', response_info[0].CreatorID)

    def _do_send_message_to_broker(self, json_payload=None, packet_id=None):
        if packet_id is None:
            packet_id = packetid.UniqueID()
        if _Debug:
            lg.args(_DebugLevel, json_payload=json_payload, packet_id=packet_id)
        raw_payload = serialization.DictToBytes(
            json_payload,
            pack_types=True,
            encoding='utf-8',
        )
        try:
            private_message_object = message.GroupMessage(
                recipient=self.group_key_id,
                sender=self.producer_id,
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
                'producer_id': self.producer_id,
            },
            recipient_global_id=self.active_broker_id,
            packet_id=packetid.MakeQueueMessagePacketID(self.active_queue_id, packet_id),
            message_ack_timeout=config.conf().getInt('services/private-groups/message-ack-timeout'),
            skip_handshake=True,
            fire_callbacks=False,
        )
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='message_producer._do_send_message_to_broker')
        # d.addCallback(self._on_message_to_broker_sent, packet_id)
        # d.addErrback(self._on_message_to_broker_failed, packet_id)
