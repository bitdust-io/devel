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
    * :red:`cooperation-mismatch`
    * :red:`dht-mismatch`
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`failed`
    * :red:`init`
    * :red:`msg-in`
    * :red:`rejected`
    * :red:`request-invalid`
    * :red:`request-rejected`
    * :red:`restore`
    * :red:`shutdown`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import sys
import re

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in queue_keeper.py')

from twisted.python.failure import Failure
from twisted.internet.defer import Deferred
from twisted.internet.task import LoopingCall

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.system import local_fs

from bitdust.lib import utime
from bitdust.lib import strng
from bitdust.lib import jsn

from bitdust.main import settings
from bitdust.main import config

from bitdust.dht import dht_relations

from bitdust.p2p import p2p_service_seeker

from bitdust.access import groups

from bitdust.stream import broker_negotiator

from bitdust.userid import id_url
from bitdust.userid import global_id
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_QueueKeepers = {}

#------------------------------------------------------------------------------

DHT_RECORD_REFRESH_INTERVAL = 10*60

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
    global _QueueKeepers
    customer_idurl = id_url.to_bin(customer_idurl)
    if id_url.is_empty(customer_idurl):
        return None
    if not id_url.is_cached(customer_idurl):
        lg.warn('customer idurl is not cached yet, can not start QueueKeeper()')
        return None
    customer_idurl = id_url.field(customer_idurl)
    return customer_idurl in _QueueKeepers


#------------------------------------------------------------------------------


def check_create(customer_idurl, auto_create=True, event='init'):
    """
    Creates new instance of `queue_keeper()` state machine and send "init" event to it.
    """
    customer_idurl = id_url.to_bin(customer_idurl)
    if _Debug:
        lg.args(_DebugLevel, customer_idurl=customer_idurl)
    if id_url.is_empty(customer_idurl):
        return None
    if not id_url.is_cached(customer_idurl):
        lg.warn('customer idurl is not cached yet, can not start QueueKeeper()')
        return None
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in list(queue_keepers().keys()):
        if not auto_create:
            return None
        if event:
            A(customer_idurl, event)
            if _Debug:
                lg.out(_DebugLevel, 'queue_keeper.check_create instance for customer %r was not found, made a new instance' % customer_idurl)
    return A(customer_idurl)


def close(customer_idurl):
    """
    Closes instance of queue_keeper() state machine related to given customer.
    """
    customer_idurl = strng.to_bin(customer_idurl)
    if _Debug:
        lg.args(_DebugLevel, customer_idurl=customer_idurl)
    if id_url.is_empty(customer_idurl):
        return False
    if not id_url.is_cached(customer_idurl):
        lg.warn('customer idurl is not cached yet, can not stop QueueKeeper()')
        return False
    customer_idurl = id_url.field(customer_idurl)
    qk = queue_keepers().get(customer_idurl)
    if not qk:
        lg.warn('instance of queue_keeper() not found for given customer %r' % customer_idurl)
        return False
    qk.event('shutdown')
    del qk
    return True


#------------------------------------------------------------------------------


def read_state(customer_id, broker_id):
    service_dir = settings.ServiceDir('service_message_broker')
    keepers_dir = os.path.join(service_dir, 'keepers')
    broker_dir = os.path.join(keepers_dir, broker_id)
    keeper_state_file_path = os.path.join(broker_dir, customer_id)
    json_value = None
    if os.path.isfile(keeper_state_file_path):
        try:
            json_value = jsn.loads_text(local_fs.ReadTextFile(keeper_state_file_path))
        except:
            lg.exc()
            return None
        if _Debug:
            lg.args(_DebugLevel, customer_id=customer_id, broker_id=broker_id, json_value=json_value)
        return json_value
    broker_idurl = global_id.glob2idurl(broker_id)
    if id_url.is_cached(broker_idurl):
        for one_broker_id in os.listdir(keepers_dir):
            one_broker_idurl = global_id.glob2idurl(one_broker_id)
            if id_url.is_cached(one_broker_idurl):
                if one_broker_idurl == broker_idurl:
                    broker_dir = os.path.join(keepers_dir, one_broker_id)
                    keeper_state_file_path = os.path.join(broker_dir, customer_id)
                    json_value = None
                    if os.path.isfile(keeper_state_file_path):
                        try:
                            json_value = jsn.loads_text(local_fs.ReadTextFile(keeper_state_file_path))
                        except:
                            lg.exc()
                            return None
                        if _Debug:
                            lg.args(_DebugLevel, customer_id=customer_id, broker_id=one_broker_id, json_value=json_value)
                        return json_value
    return None


def write_state(customer_id, broker_id, json_value):
    service_dir = settings.ServiceDir('service_message_broker')
    keepers_dir = os.path.join(service_dir, 'keepers')
    broker_dir = os.path.join(keepers_dir, broker_id)
    keeper_state_file_path = os.path.join(broker_dir, customer_id)
    if json_value is None:
        if os.path.isfile(keeper_state_file_path):
            try:
                os.remove(keeper_state_file_path)
            except:
                lg.exc()
        if _Debug:
            lg.args(_DebugLevel, customer_id=customer_id, broker_id=broker_id)
        return None
    if not os.path.isdir(broker_dir):
        try:
            os.makedirs(broker_dir)
        except:
            lg.exc()
            return None
    if not local_fs.WriteTextFile(keeper_state_file_path, jsn.dumps(json_value)):
        lg.err('failed writing queue_keeper state for customer %r of broker %r to %r' % (customer_id, broker_id, keeper_state_file_path))
        return None
    if _Debug:
        lg.args(_DebugLevel, customer_id=customer_id, broker_id=broker_id, json_value=json_value)
    return json_value


#------------------------------------------------------------------------------


def A(customer_idurl, event=None, *args, **kwargs):
    """
    Access method to interact with a state machine created for given contact.
    """
    global _QueueKeepers
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _QueueKeepers:
        if not event or event in [
            'shutdown',
            'failed',
            'rejected',
        ]:
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
        self.customer_idurl = id_url.field(customer_idurl)
        self.customer_id = self.customer_idurl.to_id()
        self.broker_idurl = id_url.field(broker_idurl or my_id.getIDURL())
        self.broker_id = self.broker_idurl.to_id()
        self.cooperated_brokers = {}
        self.known_position = -1
        self.known_streams = {}
        self.current_connect_request = None
        self.pending_connect_requests = []
        self.latest_dht_records = {}
        self.InSync = False
        super(QueueKeeper, self).__init__(name='queue_keeper_%s' % self.customer_id, state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)

    def __repr__(self):
        return '%s[%d](%s)' % (self.id, self.known_position, self.state)

    def to_json(self):
        j = super().to_json()
        j.update({
            'customer_id': self.customer_id,
            'broker_id': self.broker_id,
            'position': self.known_position,
            'brokers': self.cooperated_brokers,
            'streams': self.known_streams,
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
                self.InSync = False
                self.doEraseState(*args, **kwargs)
                self.doInit(*args, **kwargs)
            elif event == 'restore':
                self.state = 'DHT_READ'
                self.InSync = False
                self.doInit(*args, **kwargs)
                self.doReadState(*args, **kwargs)
                self.doBuildVerifyRequest(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.state = 'DHT_READ'
                self.doBuildConnectRequest(*args, **kwargs)
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
            elif event == 'dht-read-success':
                self.state = 'COOPERATE?'
                self.doRunBrokerNegotiator(*args, **kwargs)
            elif event == 'dht-read-failed':
                self.state = 'DISCONNECTED'
                self.InSync = False
                self.doNotify(event, *args, **kwargs)
                self.doPullRequests(*args, **kwargs)
        #---COOPERATE?---
        elif self.state == 'COOPERATE?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doCancelRequests(*args, **kwargs)
                self.doNotify(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.doPushRequest(*args, **kwargs)
            elif event == 'request-invalid' or (event == 'rejected' and self.InSync) or event == 'accepted':
                self.state = 'DHT_WRITE'
                self.doRememberCooperation(event, *args, **kwargs)
                self.doDHTWrite(event, *args, **kwargs)
            elif (event == 'rejected' and not self.InSync) or event == 'failed' or event == 'dht-mismatch' or event == 'cooperation-mismatch':
                self.state = 'DISCONNECTED'
                self.doCancelCooperation(event, *args, **kwargs)
                self.doEraseState(*args, **kwargs)
                self.InSync = False
                self.doNotify(event, *args, **kwargs)
                self.doPullRequests(*args, **kwargs)
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
                self.InSync = False
                self.doEraseState(*args, **kwargs)
                self.doCancelCooperation(event, *args, **kwargs)
                self.doNotify(event, *args, **kwargs)
                self.doPullRequests(*args, **kwargs)
            elif event == 'connect':
                self.doPushRequest(*args, **kwargs)
            elif event == 'request-rejected' or event == 'dht-write-success':
                self.state = 'CONNECTED'
                self.doDHTRefresh(*args, **kwargs)
                self.doRememberOwnPosition(*args, **kwargs)
                self.InSync = True
                self.doWriteState(*args, **kwargs)
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
                self.doBuildConnectRequest(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.refresh_period = DHT_RECORD_REFRESH_INTERVAL
        self.refresh_task = LoopingCall(self._on_queue_keeper_dht_refresh_task)

    def doReadState(self, *args, **kwargs):
        """
        Action method.
        """
        json_value = read_state(customer_id=self.customer_id, broker_id=self.broker_id) or {}
        self.cooperated_brokers = {int(k): id_url.field(v) for k, v in (json_value.get('cooperated_brokers') or {}).items()}
        try:
            self.known_position = int(json_value.get('position', -1))
        except:
            self.known_position = -1
        self.known_streams = json_value.get('streams', {}) or {}

    def doEraseState(self, *args, **kwargs):
        """
        Action method.
        """
        write_state(customer_id=self.customer_id, broker_id=self.broker_id, json_value=None)
        self.cooperated_brokers = {}
        self.known_position = -1
        self.known_streams = {}

    def doWriteState(self, *args, **kwargs):
        """
        Action method.
        """
        # store queue keeper info locally here to be able to start up again after application restart
        write_state(
            customer_id=self.customer_id,
            broker_id=self.broker_id,
            json_value={
                'state': self.state,
                'position': self.known_position,
                'cooperated_brokers': self.cooperated_brokers,
                'streams': self.known_streams,
                'time': utime.utcnow_to_sec1970(),
            },
        )

    def doBuildConnectRequest(self, *args, **kwargs):
        """
        Action method.
        """
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.current_connect_request = {
            'request': 'connect',
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

    def doBuildVerifyRequest(self, *args, **kwargs):
        """
        Action method.
        """
        self.current_connect_request = {
            'request': 'verify',
            'desired_position': self.known_position,
            'streams': self.known_streams,
            'known_brokers': self.cooperated_brokers,
            'use_dht_cache': False,
            'result': kwargs['result_callback'],
        }

    def doPushRequest(self, *args, **kwargs):
        """
        Action method.
        """
        self.pending_connect_requests.append(dict(**kwargs))
        if _Debug:
            lg.args(_DebugLevel, pending=len(self.pending_connect_requests), **kwargs)

    def doPullRequests(self, *args, **kwargs):
        """
        Action method.
        """
        if self.pending_connect_requests:
            req = self.pending_connect_requests.pop(0)
            if _Debug:
                lg.args(_DebugLevel, more_pending=len(self.pending_connect_requests), **req)
            reactor.callLater(0, self.automat, 'connect', **req)  # @UndefinedVariable

    def doDHTRead(self, *args, **kwargs):
        """
        Action method.
        """
        use_cache = (self.current_connect_request or {}).get('use_dht_cache', False)
        result = dht_relations.read_customer_message_brokers(
            customer_idurl=self.customer_idurl,
            positions=list(range(groups.REQUIRED_BROKERS_COUNT)),
            use_cache=use_cache,
        )
        # TODO: add more validations of dht_result
        result.addCallback(self._on_read_customer_message_brokers)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTRead')
        result.addErrback(lambda err: self.automat('dht-read-failed', err))

    def doDHTWrite(self, event, *args, **kwargs):
        """
        Action method.
        """
        self._do_dht_push_state(event=event, **kwargs)

    def doDHTRefresh(self, *args, **kwargs):
        """
        Action method.
        """
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.refresh_task.start(DHT_RECORD_REFRESH_INTERVAL, now=False)

    def doRememberCooperation(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.cooperated_brokers = self.cooperated_brokers or {}
        archive_folder_path = None
        if event in [
            'accepted',
        ]:
            accepted_brokers = kwargs.get('cooperated_brokers', {}) or {}
            archive_folder_path = accepted_brokers.pop('archive_folder_path', None)
            self.cooperated_brokers.update(accepted_brokers)
        if _Debug:
            lg.args(_DebugLevel, e=event, cooperated=kwargs.get('cooperated_brokers'), af_path=archive_folder_path)

    def doCancelCooperation(self, event, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, e=event, current=self.cooperated_brokers)
        self.cooperated_brokers.clear()

    def doRememberOwnPosition(self, *args, **kwargs):
        """
        Action method.
        """
        my_new_position = -1
        for pos, idurl in self.cooperated_brokers.items():
            if idurl and id_url.is_the_same(idurl, self.broker_idurl):
                my_new_position = pos
        archive_folder_path = kwargs.get('archive_folder_path')
        if _Debug:
            lg.args(_DebugLevel, known=self.known_position, new=my_new_position, cooperated=self.cooperated_brokers, af_path=archive_folder_path)
        if my_new_position >= 0:
            self.known_position = my_new_position
        if self.current_connect_request and self.current_connect_request.get('request') == 'connect' and archive_folder_path:
            try:
                self.known_streams[self.current_connect_request['group_key_info']['alias']] = archive_folder_path
            except:
                lg.exc(str(self.current_connect_request))

    def doRunBrokerNegotiator(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, req=self.current_connect_request['request'], my_pos=self.known_position, dht_brokers=kwargs['dht_brokers'])
        if self.current_connect_request['request'] == 'verify':
            self._do_verify_cooperated_brokers()
            return

        def _run_broker_negotiator(d, **kw):
            negotiator = broker_negotiator.BrokerNegotiator()
            negotiator.automat(
                event='connect',
                my_position=self.known_position,
                cooperated_brokers=self.cooperated_brokers,
                dht_brokers=kw['dht_brokers'],
                customer_idurl=self.customer_idurl,
                broker_idurl=self.broker_idurl,
                connect_request=self.current_connect_request,
                result=d,
            )

        ret = Deferred()
        ret.addCallback(self._on_broker_negotiator_callback)
        ret.addErrback(self._on_broker_negotiator_errback)
        reactor.callLater(0, _run_broker_negotiator, ret, **kwargs)  # @UndefinedVariable

    def doNotify(self, event, *args, **kwargs):
        """
        Action method.
        """
        result = self.current_connect_request['result']
        self.current_connect_request = None
        if _Debug:
            lg.args(_DebugLevel, e=event, cooperated_brokers=self.cooperated_brokers, pos=self.known_position)
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
        _QueueKeepers.pop(self.customer_idurl, None)
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.refresh_task = None
        self.customer_idurl = None
        self.customer_id = None
        self.broker_idurl = None
        self.broker_id = None
        self.known_position = -1
        self.known_streams.clear()
        self.cooperated_brokers.clear()
        self.latest_dht_records.clear()
        self.destroy()

    #------------------------------------------------------------------------------

    def verify_broker(self, broker_idurl, position, known_brokers, known_streams):
        if not self.InSync or self.state != 'CONNECTED':
            lg.warn('not able to verify another broker because %r is not in sync' % self)
            return None
        if self.cooperated_brokers:
            if id_url.is_not_in(broker_idurl, self.cooperated_brokers.values()):
                return 'unknown broker'
            if position not in self.cooperated_brokers.keys():
                return 'unknown position'
            if not id_url.is_the_same(self.cooperated_brokers[position], broker_idurl):
                return 'position mismatch'
            if len(self.cooperated_brokers) != len(known_brokers):
                return 'brokers count mismatch'
            for i, b_idurl in self.cooperated_brokers.items():
                if not id_url.is_the_same(known_brokers[i], b_idurl):
                    return 'broker mismatch'
        if self.known_streams and known_streams:
            for my_queue_alias, my_archive_folder_path in self.known_streams.items():
                for other_queue_alias, other_archive_folder_path in self.known_streams.items():
                    # TODO: verify streams
                    pass
        return None

    #------------------------------------------------------------------------------

    def _do_dht_write(self, desired_position, archive_folder_path, revision, retry, event=None, **kwargs):
        result = dht_relations.write_customer_message_broker(
            customer_idurl=self.customer_idurl,
            broker_idurl=self.broker_idurl,
            position=desired_position,
            revision=revision,
        )
        result.addCallback(self._on_write_customer_message_broker_success, desired_position, archive_folder_path, revision, event, **kwargs)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTWrite')
        result.addErrback(self._on_write_customer_message_broker_failed, desired_position, archive_folder_path, revision, retry, event, **kwargs)

    def _do_dht_push_state(self, event=None, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, known_position=self.known_position, cooperated_brokers=self.cooperated_brokers, e=event, kw=kwargs)
        desired_position = self.known_position
        if desired_position is None or desired_position == -1:
            for pos, idurl in self.cooperated_brokers.items():
                if idurl and id_url.is_the_same(idurl, self.broker_idurl):
                    desired_position = pos
        if desired_position is None or desired_position == -1:
            raise Exception('not able to write record into DHT, my position is unknown')
        archive_folder_path = None
        if self.current_connect_request and self.current_connect_request.get('archive_folder_path'):
            archive_folder_path = self.current_connect_request['archive_folder_path']
        prev_revision = self.latest_dht_records.get(desired_position, {}).get('revision', None)
        if prev_revision is None:
            prev_revision = 0
        if _Debug:
            lg.args(_DebugLevel, c=self.customer_id, p=desired_position, b=self.broker_id, r=prev_revision + 1)
        self._do_dht_write(
            desired_position=desired_position,
            archive_folder_path=archive_folder_path,
            revision=prev_revision + 1,
            retry=True,
            event=event,
            **kwargs,
        )

    def _do_verify_cooperated_brokers(self):
        other_brokers = list(self.cooperated_brokers.values())
        if self.broker_idurl in other_brokers:
            other_brokers.remove(self.broker_idurl)
        if not other_brokers:
            self.automat('failed')
            return
        other_broker_idurl = other_brokers[0]
        service_params = {
            'action': 'broker-verify',
            'customer_id': self.customer_id,
            'broker_id': self.broker_id,
            'position': self.known_position,
            'streams': self.known_streams,
            'known_brokers': self.cooperated_brokers,
        }
        if _Debug:
            lg.args(_DebugLevel, target=other_broker_idurl, service_params=service_params)
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=other_broker_idurl,
            service_name='service_message_broker',
            service_params=service_params,
            request_service_timeout=config.conf().getInt('services/message-broker/broker-negotiate-ack-timeout'),
            force_handshake=False,
            attempts=1,
        )
        result.addCallback(self._on_broker_verify_result)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper._do_verify_cooperated_brokers')
        result.addErrback(self._on_broker_verify_failed)

    def _on_read_customer_message_brokers(self, dht_brokers_info_list):
        self.latest_dht_records.clear()
        dht_brokers = {}
        if not dht_brokers_info_list:
            lg.warn('no brokers found in DHT records for customer %r' % self.customer_id)
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

    def _on_write_customer_message_broker_success(self, nodes, desired_broker_position, archive_folder_path, revision, event, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, nodes=type(nodes), pos=desired_broker_position, af_path=archive_folder_path, rev=revision)
        if nodes:
            if event == 'request-invalid':
                self.automat('request-rejected', desired_position=desired_broker_position, archive_folder_path=archive_folder_path, **kwargs)
            else:
                self.automat('dht-write-success', desired_position=desired_broker_position, archive_folder_path=archive_folder_path)
        else:
            self.automat('dht-write-failed', desired_position=desired_broker_position, archive_folder_path=archive_folder_path)

    def _on_write_customer_message_broker_failed(self, err, desired_broker_position, archive_folder_path, revision, retry, event, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, err=err, desired_broker_position=desired_broker_position, e=event, kw=kwargs)
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
                current_revision = re.search('current revision is (\d+)', err_msg).group(1)
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
                    event=event,
                    **kwargs,
                )
                return
        if event == 'request-invalid':
            self.automat('request-rejected', desired_position=desired_broker_position, archive_folder_path=archive_folder_path, **kwargs)
        else:
            self.automat('dht-write-failed', desired_position=desired_broker_position)

    def _on_broker_negotiator_callback(self, cooperated_brokers):
        if _Debug:
            lg.args(_DebugLevel, cooperated_brokers=cooperated_brokers)
        self.automat('accepted', cooperated_brokers=cooperated_brokers)

    def _on_broker_negotiator_errback(self, err):
        if isinstance(err, Failure):
            try:
                evt, args, kwargs = err.value.args
            except:
                lg.exc()
                return None
            if _Debug:
                lg.args(_DebugLevel, event=evt, args=args, kwargs=kwargs)
            if evt == 'request-invalid':
                self.automat('request-invalid', *args, **kwargs)
                return None
            if evt in [
                'top-record-busy',
                'prev-record-own',
            ]:
                self.automat('dht-mismatch', **kwargs)
                return None
            if evt in [
                'broker-rejected',
                'new-broker-rejected',
                'broker-rotate-denied',
            ]:
                self.automat('cooperation-mismatch', **kwargs)
                return None
            if evt.count('-failed'):
                self.automat('failed')
                return None
        else:
            if _Debug:
                lg.args(_DebugLevel, err=err)
        self.automat('rejected', *args, **kwargs)
        return None

    def _on_queue_keeper_dht_refresh_task(self):
        self._do_dht_push_state()

    def _on_broker_verify_result(self, ret):
        if _Debug:
            lg.args(_DebugLevel, ret=ret)
        self.automat('accepted', cooperated_brokers=self.cooperated_brokers)

    def _on_broker_verify_failed(self, err):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        self.automat('failed')
