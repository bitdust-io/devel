#!/usr/bin/env python
# queue_keeper.py
#
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (queue_keeper.py) is part of BitDust Software.
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
#


"""
.. module:: queue_keeper
.. role:: red

BitDust queue_keeper() Automat

EVENTS:
    * :red:`accepted`
    * :red:`connect`
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`failed`
    * :red:`init`
    * :red:`msg-in`
    * :red:`my-record-invalid`
    * :red:`my-record-missing`
    * :red:`rejected`
    * :red:`request-invalid`
    * :red:`shutdown`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys
import re

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in queue_keeper.py')

from twisted.python.failure import Failure
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import strng

from dht import dht_relations

from access import groups

from stream import broker_negotiator

from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

_QueueKeepers = {}

#------------------------------------------------------------------------------

DHT_RECORD_REFRESH_INTERVAL = 3 * 60

#------------------------------------------------------------------------------

def init():
    """
    Called from top level code when the software is starting.
    Needs to be called before other methods here.
    """
    if _Debug:
        lg.out(_DebugLevel, 'queue_keeper.init')


def shutdown():
    """
    Called from top level code when the software is stopping.
    """
    if _Debug:
        lg.out(_DebugLevel, 'queue_keeper.shutdown')

#------------------------------------------------------------------------------

def queue_keepers():
    global _QueueKeepers
    return _QueueKeepers


def existing(customer_idurl):
    """
    Returns instance of existing `queue_keeper()` or None.
    """
    customer_idurl = id_url.to_bin(customer_idurl)
    if id_url.is_empty(customer_idurl):
        return None
    if not id_url.is_cached(customer_idurl):
        lg.warn('customer idurl is not cached yet, can not start QueueKeeper()')
        return None
    customer_idurl = id_url.field(customer_idurl)
    return A(customer_idurl)


def check_create(customer_idurl, auto_create=True):
    """
    Creates new instance of `queue_keeper()` state machine and send "init" event to it.
    """
    customer_idurl = id_url.to_bin(customer_idurl)
    if id_url.is_empty(customer_idurl):
        return None
    if not id_url.is_cached(customer_idurl):
        lg.warn('customer idurl is not cached yet, can not start QueueKeeper()')
        return None
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in list(queue_keepers().keys()):
        if not auto_create:
            return None
        A(customer_idurl, 'init')
        if _Debug:
            lg.out(_DebugLevel, 'queue_keeper.check_create instance for customer %r was not found, made a new instance' % customer_idurl)
    return A(customer_idurl)


def close(customer_idurl):
    """
    Closes instance of queue_keeper() state machine related to given customer.
    """
    customer_idurl = strng.to_bin(customer_idurl)
    if id_url.is_empty(customer_idurl):
        return False
    if not id_url.is_cached(customer_idurl):
        lg.warn('customer idurl is not cached yet, can not stop QueueKeeper()')
        return False
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in queue_keepers().keys():
        lg.warn('instance of queue_keeper() not found for given customer')
        return False
    A(customer_idurl, 'shutdown')
    return True

#------------------------------------------------------------------------------

def A(customer_idurl, event=None, *args, **kwargs):
    """
    Access method to interact with a state machine created for given contact.
    """
    global _QueueKeepers
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _QueueKeepers:
        if not event:
            return None
        _QueueKeepers[customer_idurl] = QueueKeeper(
            customer_idurl=customer_idurl,
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _QueueKeepers[customer_idurl].automat(event, *args, **kwargs)
    return _QueueKeepers[customer_idurl]

#------------------------------------------------------------------------------

class QueueKeeper(automat.Automat):
    """
    This class implements all the functionality of ``queue_keeper()`` state machine.
    """

    def __init__(self, customer_idurl, broker_idurl=None, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `queue_keeper()` state machine.
        """
        self.customer_idurl = customer_idurl
        self.customer_id = self.customer_idurl.to_id()
        self.broker_idurl = broker_idurl or my_id.getIDURL()
        self.broker_id = self.broker_idurl.to_id()
        self.connected_queues = set()
        self.cooperated_brokers = {}
        self.known_position = -1
        self.known_archive_folder_path = None
        self.current_connect_request = None
        self.pending_connect_requests = []
        # self.refresh_task = None
        self.latest_dht_records = {}
        # self.dht_read_use_cache = True
        # self.registered_callbacks = []
        # self.new_possible_position = None
        # self.requested_archive_folder_path = None
        # self.has_rotated = False
        self.negotiator = None
        super(QueueKeeper, self).__init__(
            name="queue_keeper_%s" % self.customer_id,
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

    def __repr__(self):
        return '%s[%d](%s)' % (self.id, self.known_position, self.state)

    def to_json(self):
        j = super().to_json()
        j.update({
            'customer_id': self.customer_id,
            'broker_id': self.broker_id,
            'position': self.known_position,
            'brokers': self.cooperated_brokers,
            'archive_folder_path': self.known_archive_folder_path,
            'connected_queues': list(self.connected_queues),
        })
        return j

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'DISCONNECTED'
                self.InSync=False
                self.doInit(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.state = 'DHT_READ'
                self.doBuildRequest(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doCancelRequests(*args, **kwargs)
                self.doNotify(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
            elif event == 'connect':
                self.doPushRequest(*args, **kwargs)
            elif event == 'dht-read-failed' or event == 'request-invalid':
                self.state = 'DISCONNECTED'
            elif event == 'dht-read-success':
                self.state = 'COOPERATE?'
                self.doRunBrokerNegotiator(*args, **kwargs)
        #---COOPERATE?---
        elif self.state == 'COOPERATE?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doCancelRequests(*args, **kwargs)
                self.doNotify(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.doPushRequest(*args, **kwargs)
            elif ( event == 'rejected' and not self.InSync ) or event == 'failed' or event == 'my-record-missing' or event == 'my-record-invalid':
                self.state = 'DISCONNECTED'
            elif event == 'request-invalid' or ( event == 'rejected' and self.InSync ) or event == 'accepted':
                self.state = 'DHT_WRITE'
                self.doRememberCooperation(event, *args, **kwargs)
                self.doDHTWrite(event, *args, **kwargs)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doCancelRequests(*args, **kwargs)
                self.doNotify(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
            elif event == 'dht-write-failed':
                self.state = 'DISCONNECTED'
                self.InSync=False
                self.doCancelCooperation(event, *args, **kwargs)
                self.doNotify(event, *args, **kwargs)
                self.doPullRequests(*args, **kwargs)
            elif event == 'connect':
                self.doPushRequest(*args, **kwargs)
            elif event == 'dht-write-success':
                self.state = 'CONNECTED'
                self.doDHTRefresh(*args, **kwargs)
                self.doRememberOwnPosition(*args, **kwargs)
                self.InSync=True
                self.doNotify(event, *args, **kwargs)
                self.doPullRequests(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
            elif event == 'connect':
                self.state = 'DHT_READ'
                self.doBuildRequest(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        # self.refresh_task = LoopingCall(self._on_queue_keeper_refresh_task)

    def doBuildRequest(self, *args, **kwargs):
        """
        Action method.
        """
        self.current_connect_request = {
            # 'queue_id': kwargs['queue_id'],
            'consumer_id': kwargs['consumer_id'],
            'producer_id': kwargs['producer_id'],
            'group_key_info': kwargs['group_key_info'],
            'desired_position': kwargs['desired_position'],
            'archive_folder_path': kwargs['archive_folder_path'],
            'last_sequence_id': kwargs['last_sequence_id'],
            'known_brokers': kwargs['known_brokers'],
            'use_dht_cache': kwargs['use_dht_cache'],
            'result': kwargs['result_callback'],
        }

    def doPushRequest(self, *args, **kwargs):
        """
        Action method.
        """
        self.pending_connect_requests.append(dict(**kwargs))

    def doPullRequests(self, *args, **kwargs):
        """
        Action method.
        """
        if self.pending_connect_requests:
            req = self.pending_connect_requests.pop(0)
            if _Debug:
                lg.args(_DebugLevel, **req)
            reactor.callLater(0, self.automat, 'connect', **req)  # @UndefinedVariable

    def doDHTRead(self, *args, **kwargs):
        """
        Action method.
        """
        use_cache = self.current_connect_request['use_dht_cache']
        result = dht_relations.read_customer_message_brokers(
            customer_idurl=self.customer_idurl,
            positions=list(range(groups.REQUIRED_BROKERS_COUNT)),
            use_cache=use_cache,
        )
        # TODO: add more validations of dht_result
        result.addCallback(self._on_read_customer_message_brokers)
        if _Debug:
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTRead')
        result.addErrback(lambda err: self.automat('dht-read-failed', err))

    def doDHTWrite(self, event, *args, **kwargs):
        """
        Action method.
        """
        # desired_position = self.known_position
        desired_position = None
        for pos, idurl in self.cooperated_brokers.items():
            if idurl and id_url.to_bin(idurl) == self.broker_idurl.to_bin():
                desired_position = pos
        if desired_position is None:
            raise Exception('not able to write record into DHT, new position is unknown')
        archive_folder_path = self.current_connect_request['archive_folder_path']
        if archive_folder_path is None:
            archive_folder_path = self.known_archive_folder_path
        prev_revision = self.latest_dht_records.get(desired_position, {}).get('revision', None)
        if prev_revision is None:
            prev_revision = 0
        if _Debug:
            lg.args(_DebugLevel, c=self.customer_id, p=desired_position, b=self.broker_id,
                    a=archive_folder_path, r=prev_revision+1, latest_dht_records=self.latest_dht_records)
        self._do_dht_write(
            desired_position=desired_position,
            archive_folder_path=archive_folder_path,
            revision=prev_revision+1,
            retry=True,
        )

    def doDHTRefresh(self, *args, **kwargs):
        """
        Action method.
        """
        # if self.refresh_task.running:
        #     self.refresh_task.stop()
        # self.refresh_task.start(DHT_RECORD_REFRESH_INTERVAL, now=False)

    def doRememberCooperation(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.cooperated_brokers = self.cooperated_brokers or {}
        old = dict(self.cooperated_brokers)
        if event in ['accepted', ]:
            self.cooperated_brokers.update(kwargs.get('cooperated_brokers', {}) or {})
        if _Debug:
            lg.args(_DebugLevel, event=event, old=old, new=kwargs.get('cooperated_brokers'))

    def doCancelCooperation(self, event, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, current=self.cooperated_brokers)
        self.cooperated_brokers.clear()

    def doRememberOwnPosition(self, *args, **kwargs):
        """
        Action method.
        """
        my_new_position = -1
        for pos, idurl in self.cooperated_brokers.items():
            if idurl and id_url.to_bin(idurl) == self.broker_idurl.to_bin():
                my_new_position = pos
        if _Debug:
            lg.args(_DebugLevel, known=self.known_position, new=my_new_position)
        if my_new_position >= 0:
            self.known_position = my_new_position

    def doRunBrokerNegotiator(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, my_position=self.known_position, dht_brokers=kwargs['dht_brokers'])
        d = Deferred()
        d.addCallback(self._on_broker_negotiator_callback)
        d.addErrback(self._on_broker_negotiator_errback)
        self.negotiator = broker_negotiator.BrokerNegotiator()
        self.negotiator.automat(
            event='connect',
            my_position=self.known_position,
            cooperated_brokers=self.cooperated_brokers,
            dht_brokers=kwargs['dht_brokers'],
            customer_idurl=self.customer_idurl,
            broker_idurl=self.broker_idurl,
            connect_request=self.current_connect_request,
            result=d,
        )

    def doNotify(self, event, *args, **kwargs):
        """
        Action method.
        """
        result = self.current_connect_request['result']
        self.current_connect_request = None
        if result:
            if not result.called:
                if event == 'dht-write-success':
                    result.callback(self.cooperated_brokers)
                else:
                    result.errback(Exception(event, args, kwargs))

    def doCancelRequests(self, *args, **kwargs):
        """
        Action method.
        """
        if self.pending_connect_requests:
            for req in self.pending_connect_requests:
                result = req['result_callback']
                if result:
                    if not result.called:
                        result.errback(Exception('canceled'))

    def doProc(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _QueueKeepers
        # if self.refresh_task.running:
        #     self.refresh_task.stop()
        # self.refresh_task = None
        _QueueKeepers.pop(self.customer_idurl)
        self.customer_idurl = None
        self.customer_id = None
        self.broker_idurl = None
        self.broker_id = None
        self.known_position = -1
        # self.new_possible_position = None
        # self.registered_callbacks = None
        self.connected_queues = None
        self.known_archive_folder_path = None
        # self.requested_archive_folder_path = None
        self.cooperated_brokers.clear()
        self.latest_dht_records.clear()
        self.negotiator = None
        self.destroy()

#     def isPositionDesired(self, *args, **kwargs):
#         """
#         Condition method.
#         """
#         if self.known_position is None or self.known_position == -1:
#             return False
#         desired_position = kwargs.get('desired_position', -1)
#         if desired_position is None or desired_position == -1:
#             return True
#         return self.known_position == desired_position

#     def isRotated(self, *args, **kwargs):
#         """
#         Condition method.
#         """
#         return self.has_rotated

#     def doAddCallback(self, *args, **kwargs):
#         """
#         Action method.
#         """
#         cb = kwargs.get('result_callback')
#         if cb:
#             self.registered_callbacks.append((cb, kwargs.get('queue_id'), ))

#     def doCheckRotated(self, *args, **kwargs):
#         """
#         Action method.
#         """
#         desired_position = kwargs.get('desired_position', -1)
#         if desired_position >= 0 and self.known_position is not None and self.known_position >= 0:
#             self.has_rotated = desired_position < self.known_position
#             if self.has_rotated:
#                 lg.info('found that group brokers were rotated, my position: %d -> %d' % (self.known_position, desired_position, ))

#     def doSetDesiredPosition(self, *args, **kwargs):
#         """
#         Action method.
#         """
#         self.new_possible_position = kwargs.get('desired_position', -1)
#         self.requested_archive_folder_path = kwargs.get('archive_folder_path', None)

    def _do_dht_write(self, desired_position, archive_folder_path, revision, retry):
        result = dht_relations.write_customer_message_broker(
            customer_idurl=self.customer_idurl,
            broker_idurl=self.broker_idurl,
            position=desired_position,
            archive_folder_path=archive_folder_path,
            revision=revision,
        )
        result.addCallback(self._on_write_customer_message_broker, desired_position, archive_folder_path, revision)
        if _Debug:
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTWrite')
        result.addErrback(self._on_write_customer_message_broker_failed, desired_position, archive_folder_path, revision, retry)

#     def doVerifyOtherBroker(self, *args, **kwargs):
#         """
#         Action method.
#         """
#         other_broker_info = kwargs['broker_info']
#         service_request_params = {
#             'action': 'broker-verify',
#             'customer_idurl': self.customer_idurl,
#             'desired_position': self.new_possible_position,
#         }
#         # TODO: add an extra verification for other broker using group_key_info from the "connect" event
#         # to make sure he really possess the public key for the group - need to do "audit" of the pub. key first
#         result = p2p_service_seeker.connect_known_node(
#             remote_idurl=other_broker_info['broker_idurl'],
#             service_name='service_message_broker',
#             service_params=service_request_params,
#             request_service_timeout=15,
#             ping_retries=0,
#             ack_timeout=15,
#             force_handshake=True,
#         )
#         result.addCallback(self._on_other_broker_response, desired_position=self.new_possible_position)
#         if _Debug:
#             result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doVerifyOtherBroker')
#         result.addErrback(self._on_other_broker_failed, desired_position=self.new_possible_position)

#     def doRunCallbacks(self, event, *args, **kwargs):
#         """
#         Action method.
#         """
#         success = True if event in ['connect', 'my-record-correct', ] else False
#         for cb, queue_id in self.registered_callbacks:
#             if queue_id and success:
#                 self.connected_queues.add(queue_id)
#             if not cb.called:
#                 cb.callback(success)
#         self.registered_callbacks = []

    def _on_read_customer_message_brokers(self, dht_brokers_info_list):
        # self.cooperated_brokers.clear()
        self.latest_dht_records.clear()
        dht_brokers = {}
        if not dht_brokers_info_list:
            lg.warn('no brokers found in DHT records for customer %r' % self.customer_id)
            # self.dht_read_use_cache = False
            self.automat('dht-read-success', dht_brokers=dht_brokers)
            return
        for dht_broker_info in dht_brokers_info_list:
            if not dht_broker_info:
                continue
            dht_broker_idurl = dht_broker_info.get('broker_idurl')
            dht_broker_position = int(dht_broker_info.get('position'))
            dht_brokers[dht_broker_position] = dht_broker_idurl
            self.latest_dht_records[dht_broker_position] = dht_broker_info
        if _Debug:
            lg.args(_DebugLevel, dht_brokers=dht_brokers)
        self.automat('dht-read-success', dht_brokers=dht_brokers)
#         my_broker_info = None
#         my_position_info = None
#         for dht_broker_info in dht_brokers_info_list:
#             if not dht_broker_info:
#                 continue
#             dht_broker_idurl = dht_broker_info.get('broker_idurl')
#             dht_broker_position = int(dht_broker_info.get('position'))
#             # dht_revision = dht_broker_info.get('revision')
#             # dht_timestamp = dht_broker_info.get('timestamp')
#             dht_brokers[dht_broker_position] = dht_broker_idurl
#             self.latest_dht_records[dht_broker_position] = dht_broker_info
#             if dht_broker_position == my_position:
#                 my_position_info = dht_broker_info
#             if id_url.to_bin(dht_broker_idurl) == id_url.to_bin(self.broker_idurl) or (
#                 id_url.is_cached(dht_broker_idurl) and id_url.is_cached(self.broker_idurl) and
#                 id_url.field(self.broker_idurl) == id_url.field(dht_broker_idurl)
#             ):
#                 if not my_broker_info:
#                     my_broker_info = dht_broker_info
#                 else:
#                     if my_broker_info['position'] == my_position:
#                         lg.warn('my broker info already found on correct position, ignoring record: %r' % dht_broker_info)
#                     else:
#                         lg.warn('my broker info already found, but on different position: %d' % my_broker_info['position'])
#                         if int(my_broker_info['position']) == int(dht_broker_position):
#                             pass
#                         else:
#                             lg.warn('overwriting already populated broker record found on another position: %d' % dht_broker_position)
#                             my_broker_info = dht_broker_info
#         if _Debug:
#             lg.args(_DebugLevel, my_broker_info=my_broker_info, my_position_info=my_position_info)
#         if not my_broker_info:
#             # self.dht_read_use_cache = False
#             if my_position_info:
#                 lg.warn('found another broker %r on my position %d in DHT' % (my_position_info.get('broker_idurl'), my_position, ))
#                 self.automat('other-broker-exist', broker_info=my_position_info)
#             else:
#                 lg.info('broker info on position %d in DHT does not exist, going to put my info there' % my_position)
#                 self.automat('my-record-not-exist', desired_position=my_position)
#             return
#         my_position_ok = int(my_broker_info['position']) == int(my_position)
#         if not my_position_ok:
#             lg.info('broker info on position %d in DHT does not exist or is not valid, going to put my info there' % my_position)
#             # self.dht_read_use_cache = False
#             self.automat('my-record-not-correct', desired_position=my_position)
#             return
#         my_idurl_ok = False
#         if my_position_info:
#             my_idurl_ok = (id_url.to_bin(my_position_info['broker_idurl']) == id_url.to_bin(my_broker_info['broker_idurl']) or (
#                 id_url.is_cached(my_position_info['broker_idurl']) and id_url.is_cached(my_broker_info['broker_idurl']) and
#                 id_url.field(my_broker_info['broker_idurl']) == id_url.field(my_position_info['broker_idurl'])
#             ))
#         if not my_idurl_ok:
#             lg.warn('there is another broker %r on my position %d in DHT' % (my_position_info.get('broker_idurl'), my_position, ))
#             # self.dht_read_use_cache = False
#             self.automat('other-broker-exist', broker_info=my_position_info)
#             return
#         # self.dht_read_use_cache = True
#         self.known_archive_folder_path = my_broker_info['archive_folder_path']
#         self.automat('my-record-correct', broker_idurl=my_broker_info['broker_idurl'], position=my_broker_info['position'])

    def _on_write_customer_message_broker(self, nodes, desired_broker_position, archive_folder_path, revision):
        if _Debug:
            lg.args(_DebugLevel, nodes=type(nodes), pos=desired_broker_position, rev=revision)
        if nodes:
            # self.requested_archive_folder_path = None
            self.automat('dht-write-success', desired_position=desired_broker_position)
        else:
            # self.dht_read_use_cache = False
            self.automat('dht-write-failed', desired_position=desired_broker_position)

    def _on_write_customer_message_broker_failed(self, err, desired_broker_position, archive_folder_path, revision, retry):
        if _Debug:
            lg.args(_DebugLevel, err=err, desired_broker_position=desired_broker_position)
        # self.dht_read_use_cache = False
        try:
            errmsg = err.value.subFailure.getErrorMessage()
        except:
            try:
                errmsg = err.getErrorMessage()
            except:
                try:
                    errmsg = err.value
                except:
                    errmsg = str(err)
        err_msg = strng.to_text(errmsg)
        lg.err('failed to write new broker info for %s : %s' % (self.customer_id, err_msg))
        if err_msg.count('current revision is'):
            try:
                current_revision = re.search("current revision is (\d+)", err_msg).group(1)
                current_revision = int(current_revision)
            except:
                lg.exc()
                current_revision = self.transaction['revision']
            current_revision += 1
            if _Debug:
                lg.warn('recognized "DHT write operation failed" because of late revision, increase revision to %d and retry' % current_revision)
            if retry:
                self._do_dht_write(
                    desired_position=desired_broker_position,
                    archive_folder_path=archive_folder_path,
                    revision=current_revision,
                    retry=False,
                )
                return
        self.automat('dht-write-failed', desired_position=desired_broker_position)

#     def _on_queue_keeper_refresh_task(self):
#         if _Debug:
#             lg.args(_DebugLevel, state=self.state, known_position=self.known_position, connected_queues=self.connected_queues)
#         if self.state == 'CONNECTED':
#             # self.dht_read_use_cache = False
#             reactor.callLater(0, self.automat, 'connect')  # @UndefinedVariable

#     def _on_other_broker_response(self, idurl, desired_position):
#         if _Debug:
#             lg.args(_DebugLevel, idurl=idurl, desired_position=desired_position)
#         if idurl:
#             self.automat('other-broker-connected', desired_position=desired_position)
#         else:
#             self.automat('other-broker-disconnected', desired_position=desired_position)

#     def _on_other_broker_failed(self, err, desired_position):
#         if _Debug:
#             lg.args(_DebugLevel, err=err, desired_position=desired_position)
#         self.automat('other-broker-disconnected', desired_position=desired_position)

    def _on_broker_negotiator_callback(self, cooperated_brokers):
        if _Debug:
            lg.args(_DebugLevel, cooperated_brokers=cooperated_brokers)
        self.negotiator = None
        self.automat('accepted', cooperated_brokers=cooperated_brokers)

    def _on_broker_negotiator_errback(self, err):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        self.negotiator = None
        if isinstance(err, Failure):
            try:
                evt, _, _ = err.value.args
            except:
                lg.exc()
                return
            if evt in ['request-invalid', 'my-record-missing', 'my-record-invalid', ]:
                self.automat(evt)
                return
            if evt.count('-failed'):
                self.automat('failed')
                return
        self.automat('rejected')
