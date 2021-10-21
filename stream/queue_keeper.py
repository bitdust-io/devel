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

from logs import lg

from automats import automat

from system import local_fs

from lib import strng
from lib import jsn

from main import events
from main import settings

from dht import dht_relations

from access import groups

from stream import broker_negotiator

from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

_QueueKeepers = {}

#------------------------------------------------------------------------------

DHT_RECORD_REFRESH_INTERVAL = 10 * 60

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


def check_create(customer_idurl, auto_create=True):
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
        A(customer_idurl, 'init')
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
    if not existing(customer_idurl):
        lg.warn('instance of queue_keeper() not found for given customer %r' % customer_idurl)
        return False
    qk = queue_keepers().get(customer_idurl)
    qk.event('shutdown')
    del qk
    return True


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
    return json_value


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
            lg.args(_DebugLevel, customer_id=customer_id, broker_id=broker_id, json_value=json_value)
        return None
    if not os.path.isdir(broker_dir):
        try:
            os.makedirs(broker_dir)
        except:
            lg.exc()
            return None
    if not local_fs.WriteTextFile(keeper_state_file_path, jsn.dumps(json_value)):
        lg.err('failed writing queue_keeper state for customer %r of broker %r to %r' % (
            customer_id, broker_id, keeper_state_file_path, ))
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
        if not event or event in ['shutdown', 'failed', 'rejected', ]:
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
        self.broker_idurl = id_url.field(broker_idurl or my_id.getLocalID())
        self.broker_id = self.broker_idurl.to_id()
        json_state = read_state(customer_id=self.customer_id, broker_id=self.broker_id) or {}
        self.cooperated_brokers = json_state.get('cooperated_brokers') or {}
        self.known_position = json_state.get('position') or -1
        self.known_archive_folder_path = json_state.get('archive_folder_path')
        self.current_connect_request = None
        self.pending_connect_requests = []
        self.latest_dht_records = {}
        # self.negotiator = None
        # TODO: read latest state from local data
        super(QueueKeeper, self).__init__(
            name="queue_keeper_%s" % self.customer_id,
            state=json_state.get('state') or 'AT_STARTUP',
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
        })
        return j

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        if oldstate != newstate:
            if newstate == 'DISCONNECTED':
                write_state(customer_id=self.customer_id, broker_id=self.broker_id, json_value=None)

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
        self.refresh_period = DHT_RECORD_REFRESH_INTERVAL
        self.refresh_task = LoopingCall(self._on_queue_keeper_dht_refresh_task)

    def doBuildRequest(self, *args, **kwargs):
        """
        Action method.
        """
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.current_connect_request = {
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
        self._do_dht_push_state()

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
        if event in ['accepted', ]:
            self.cooperated_brokers.update(kwargs.get('cooperated_brokers', {}) or {})
        if _Debug:
            lg.args(_DebugLevel, e=event, cooperated_brokers=kwargs.get('cooperated_brokers'))

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
        if _Debug:
            lg.args(_DebugLevel, known=self.known_position, new=my_new_position, cooperated_brokers=self.cooperated_brokers)
        if my_new_position >= 0:
            self.known_position = my_new_position
        # store queue keeper info locally here to be able to start up again after application restart
        write_state(customer_id=self.customer_id, broker_id=self.broker_id, json_value={
            'position': self.known_position,
            'cooperated_brokers': self.cooperated_brokers,
            'archive_folder_path': self.known_archive_folder_path,
            'state': self.state,
        })

    def doRunBrokerNegotiator(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, my_position=self.known_position, dht_brokers=kwargs['dht_brokers'])
        d = Deferred()
        d.addCallback(self._on_broker_negotiator_callback)
        d.addErrback(self._on_broker_negotiator_errback)
        negotiator = broker_negotiator.BrokerNegotiator()
        negotiator.automat(
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
        self.known_archive_folder_path = None
        self.cooperated_brokers.clear()
        self.latest_dht_records.clear()
        # self.negotiator = None
        self.destroy()

    def _do_dht_write(self, desired_position, archive_folder_path, revision, retry):
        result = dht_relations.write_customer_message_broker(
            customer_idurl=self.customer_idurl,
            broker_idurl=self.broker_idurl,
            position=desired_position,
            archive_folder_path=archive_folder_path,
            revision=revision,
        )
        result.addCallback(self._on_write_customer_message_broker_success, desired_position, archive_folder_path, revision)
        if _Debug:
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTWrite')
        result.addErrback(self._on_write_customer_message_broker_failed, desired_position, archive_folder_path, revision, retry)

    def _do_dht_push_state(self):
        desired_position = self.known_position
        if desired_position is None or desired_position == -1:
            for pos, idurl in self.cooperated_brokers.items():
                if idurl and id_url.to_bin(idurl) == self.broker_idurl.to_bin():
                    desired_position = pos
        if desired_position is None or desired_position == -1:
            raise Exception('not able to write record into DHT, my position is unknown')
        archive_folder_path = self.known_archive_folder_path
        if self.current_connect_request:
            archive_folder_path = self.current_connect_request['archive_folder_path']
        prev_revision = self.latest_dht_records.get(desired_position, {}).get('revision', None)
        if prev_revision is None:
            prev_revision = 0
        if _Debug:
            lg.args(_DebugLevel, c=self.customer_id, p=desired_position, b=self.broker_id, a=archive_folder_path, r=prev_revision+1)
        self._do_dht_write(
            desired_position=desired_position,
            archive_folder_path=archive_folder_path,
            revision=prev_revision+1,
            retry=True,
        )

    def _on_read_customer_message_brokers(self, dht_brokers_info_list):
        self.latest_dht_records.clear()
        self.known_archive_folder_path = None
        dht_brokers = {}
        archive_folder_path = None
        all_archive_folder_paths = []
        if not dht_brokers_info_list:
            lg.warn('no brokers found in DHT records for customer %r' % self.customer_id)
            self.automat('dht-read-success', dht_brokers=dht_brokers, archive_folder_path=archive_folder_path)
            return
        for dht_broker_info in dht_brokers_info_list:
            if not dht_broker_info:
                continue
            dht_broker_idurl = dht_broker_info.get('broker_idurl')
            dht_broker_position = int(dht_broker_info.get('position'))
            dht_brokers[dht_broker_position] = dht_broker_idurl
            if all_archive_folder_paths.count(dht_broker_info['archive_folder_path']) == 0:
                all_archive_folder_paths.append(dht_broker_info['archive_folder_path'])
            self.latest_dht_records[dht_broker_position] = dht_broker_info
        if all_archive_folder_paths:
            archive_folder_path = all_archive_folder_paths[0]
        self.known_archive_folder_path = archive_folder_path
        if _Debug:
            lg.args(_DebugLevel, dht_brokers=dht_brokers, archive_folder_path=archive_folder_path)
        self.automat('dht-read-success', dht_brokers=dht_brokers, archive_folder_path=archive_folder_path)

    def _on_write_customer_message_broker_success(self, nodes, desired_broker_position, archive_folder_path, revision):
        if _Debug:
            lg.args(_DebugLevel, nodes=type(nodes), pos=desired_broker_position, rev=revision)
        if nodes:
            self.automat('dht-write-success', desired_position=desired_broker_position, archive_folder_path=archive_folder_path)
        else:
            self.automat('dht-write-failed', desired_position=desired_broker_position, archive_folder_path=archive_folder_path)

    def _on_write_customer_message_broker_failed(self, err, desired_broker_position, archive_folder_path, revision, retry):
        if _Debug:
            lg.args(_DebugLevel, err=err, desired_broker_position=desired_broker_position)
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

    def _on_broker_negotiator_callback(self, cooperated_brokers):
        if _Debug:
            lg.args(_DebugLevel, cooperated_brokers=cooperated_brokers)
        # self.negotiator = None
        self.automat('accepted', cooperated_brokers=cooperated_brokers)

    def _on_broker_negotiator_errback(self, err):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        # self.negotiator = None
        if isinstance(err, Failure):
            try:
                evt, _, _ = err.value.args
            except:
                lg.exc()
                return
            if evt in ['request-invalid', 'my-record-missing', 'my-top,record-missing', 'my-record-invalid', ]:
                self.automat(evt)
                return
            if evt.count('-failed'):
                self.automat('failed')
                return
        self.automat('rejected')

    def _on_queue_keeper_dht_refresh_task(self):
        self._do_dht_push_state()
