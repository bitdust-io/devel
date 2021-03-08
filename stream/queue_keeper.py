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
    * :red:`connect`
    * :red:`dht-read-failed`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`init`
    * :red:`msg-in`
    * :red:`my-record-correct`
    * :red:`my-record-not-correct`
    * :red:`my-record-not-exist`
    * :red:`other-broker-connected`
    * :red:`other-broker-disconnected`
    * :red:`other-broker-exist`
    * :red:`other-broker-timeout`
    * :red:`shutdown`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in queue_keeper.py')

from twisted.internet.task import LoopingCall

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import strng

from dht import dht_relations

from access import groups

from p2p import p2p_service_seeker

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
        self.known_position = -1
        self.registered_callbacks = []
        self.connected_queues = set()
        self.new_possible_position = None
        self.has_rotated = False
        self.known_brokers = {}
        self.dht_read_use_cache = True
        self.known_archive_folder_path = None
        self.requested_archive_folder_path = None
        self.refresh_task = None
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
                self.doRunCallbacks(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.state = 'DHT_READ'
                self.doCheckRotated(*args, **kwargs)
                self.doSetDesiredPosition(*args, **kwargs)
                self.doAddCallback(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
                self.doReconnect(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doRunCallbacks(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
            elif event == 'connect':
                self.doCheckRotated(*args, **kwargs)
                self.doAddCallback(*args, **kwargs)
            elif event == 'my-record-correct':
                self.state = 'CONNECTED'
                self.doDHTRefresh(*args, **kwargs)
                self.doSetOwnPosition(*args, **kwargs)
                self.doRunCallbacks(event, *args, **kwargs)
            elif event == 'dht-read-failed' or ( event == 'my-record-not-correct' and not self.isRotated(*args, **kwargs) ):
                self.state = 'DISCONNECTED'
                self.doRunCallbacks(event, *args, **kwargs)
            elif ( event == 'my-record-not-correct' and self.isRotated(*args, **kwargs) ) or event == 'my-record-not-exist':
                self.state = 'DHT_WRITE'
                self.doDHTWrite(*args, **kwargs)
            elif event == 'other-broker-exist':
                self.state = 'OTHER_BROKER?'
                self.doVerifyOtherBroker(*args, **kwargs)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doRunCallbacks(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
            elif event == 'dht-write-success':
                self.state = 'DHT_READ'
                self.doDHTRead(*args, **kwargs)
            elif event == 'dht-write-failed':
                self.state = 'DISCONNECTED'
                self.doRunCallbacks(event, *args, **kwargs)
            elif event == 'connect':
                self.doCheckRotated(*args, **kwargs)
                self.doAddCallback(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doRunCallbacks(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
            elif event == 'connect' and not self.isPositionDesired(*args, **kwargs):
                self.state = 'DHT_READ'
                self.doCheckRotated(*args, **kwargs)
                self.doSetDesiredPosition(*args, **kwargs)
                self.doAddCallback(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
            elif event == 'connect' and self.isPositionDesired(*args, **kwargs):
                self.doCheckRotated(*args, **kwargs)
                self.doAddCallback(*args, **kwargs)
                self.doRunCallbacks(event, *args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---OTHER_BROKER?---
        elif self.state == 'OTHER_BROKER?':
            if event == 'other-broker-connected':
                self.state = 'DISCONNECTED'
                self.doRunCallbacks(event, *args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doRunCallbacks(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'other-broker-disconnected' or event == 'other-broker-timeout':
                self.state = 'DHT_WRITE'
                self.doDHTWrite(*args, **kwargs)
        return None

    def isPositionDesired(self, *args, **kwargs):
        """
        Condition method.
        """
        if self.known_position is None or self.known_position == -1:
            return False
        desired_position = kwargs.get('desired_position', -1)
        if desired_position is None or desired_position == -1:
            return True
        return self.known_position == desired_position

    def isRotated(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.has_rotated

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.refresh_task = LoopingCall(self._on_queue_keeper_refresh_task)

    def doAddCallback(self, *args, **kwargs):
        """
        Action method.
        """
        cb = kwargs.get('result_callback')
        if cb:
            self.registered_callbacks.append((cb, kwargs.get('queue_id'), ))

    def doCheckRotated(self, *args, **kwargs):
        """
        Action method.
        """
        desired_position = kwargs.get('desired_position', -1)
        if desired_position >= 0 and self.known_position >= 0:
            self.has_rotated = desired_position < self.known_position
            if self.has_rotated:
                lg.info('found that group brokers were rotated, my position: %d -> %d' % (self.known_position, desired_position, ))

    def doSetDesiredPosition(self, *args, **kwargs):
        """
        Action method.
        """
        self.new_possible_position = kwargs.get('desired_position', -1)
        self.requested_archive_folder_path = kwargs.get('archive_folder_path', None)

    def doProc(self, *args, **kwargs):
        """
        Action method.
        """

    def doDHTRead(self, *args, **kwargs):
        """
        Action method.
        """
        expected_broker_position = kwargs.get('desired_position', -1)
        if self.new_possible_position is not None:
            expected_broker_position = self.new_possible_position
        if expected_broker_position < 0:
            expected_broker_position = 0
        use_cache = self.dht_read_use_cache
        if 'use_dht_cache' in kwargs:
            use_cache = kwargs['use_dht_cache']
        if self.has_rotated:
            use_cache = False
        if _Debug:
            lg.args(_DebugLevel, expected_position=expected_broker_position, use_cache=use_cache, has_rotated=self.has_rotated)
        result = dht_relations.read_customer_message_brokers(
            customer_idurl=self.customer_idurl,
            positions=list(range(groups.REQUIRED_BROKERS_COUNT)),
            use_cache=use_cache,
        )
        # TODO: add more validations of dht_result
        result.addCallback(self._on_read_customer_message_brokers, expected_broker_position)
        if _Debug:
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTRead')
        result.addErrback(lambda err: self.automat('dht-read-failed', err))

    def doDHTWrite(self, *args, **kwargs):
        """
        Action method.
        """
        desired_position = kwargs.get('desired_position', 0)
        archive_folder_path = self.requested_archive_folder_path
        if archive_folder_path is None:
            archive_folder_path = self.known_archive_folder_path
        if _Debug:
            lg.args(_DebugLevel, desired_position=desired_position, broker_idurl=self.broker_idurl, archive_folder_path=archive_folder_path)
        result = dht_relations.write_customer_message_broker(
            customer_idurl=self.customer_idurl,
            broker_idurl=self.broker_idurl,
            position=desired_position,
            archive_folder_path=archive_folder_path,
        )
        result.addCallback(self._on_write_customer_message_broker, desired_position)
        if _Debug:
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTWrite')
        result.addErrback(self._on_write_customer_message_broker_failed, desired_position)

    def doDHTRefresh(self, *args, **kwargs):
        """
        Action method.
        """
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.refresh_task.start(DHT_RECORD_REFRESH_INTERVAL, now=False)

    def doVerifyOtherBroker(self, *args, **kwargs):
        """
        Action method.
        """
        other_broker_info = kwargs['broker_info']
        service_request_params = {
            'action': 'broker-verify',
            'customer_idurl': self.customer_idurl,
        }
        # TODO: add an extra verification for other broker using group_key_info from the "connect" event
        # to make sure he is really possess the public key for the group - need to do "audit" of the pub. key
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=other_broker_info['broker_idurl'],
            service_name='service_message_broker',
            service_params=service_request_params,
            request_service_timeout=15,
        )
        result.addCallback(self._on_other_broker_response)
        if _Debug:
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doVerifyOtherBroker')
        result.addErrback(self._on_other_broker_failed)

    def doReconnect(self, *args, **kwargs):
        """
        Action method.
        """
        self.dht_read_use_cache = False
        reactor.callLater(0, self.automat, 'connect')  # @UndefinedVariable

    def doSetOwnPosition(self, *args, **kwargs):
        """
        Action method.
        """
        self.has_rotated = False
        self.new_possible_position = None
        self.known_position = kwargs.get('position')

    def doRunCallbacks(self, event, *args, **kwargs):
        """
        Action method.
        """
        success = True if event in ['connect', 'my-record-correct', ] else False
        for cb, queue_id in self.registered_callbacks:
            if queue_id and success:
                self.connected_queues.add(queue_id)
            if not cb.called:
                cb.callback(success)
        self.registered_callbacks = []

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _QueueKeepers
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.refresh_task = None
        _QueueKeepers.pop(self.customer_idurl)
        self.customer_idurl = None
        self.broker_idurl = None
        self.known_position = -1
        self.new_possible_position = None
        self.registered_callbacks = None
        self.connected_queues = None
        self.known_archive_folder_path = None
        self.requested_archive_folder_path = None
        self.known_brokers.clear()
        self.destroy()

    def _on_read_customer_message_brokers(self, dht_brokers_info_list, my_position):
        if _Debug:
            lg.args(_DebugLevel, my_position=my_position, dht_brokers=dht_brokers_info_list)
        self.known_brokers.clear()
        if not dht_brokers_info_list:
            lg.warn('no brokers found in DHT records for customer %r' % self.customer_idurl)
            self.dht_read_use_cache = False
            self.automat('my-record-not-exist', desired_position=my_position)
            return
        my_broker_info = None
        my_position_info = None
        for dht_broker_info in dht_brokers_info_list:
            if not dht_broker_info:
                continue
            dht_broker_idurl = dht_broker_info.get('broker_idurl')
            dht_broker_position = int(dht_broker_info.get('position'))
            self.known_brokers[dht_broker_position] = dht_broker_idurl
            if dht_broker_position == my_position:
                my_position_info = dht_broker_info
            if id_url.to_bin(dht_broker_idurl) == id_url.to_bin(self.broker_idurl):
                if not my_broker_info:
                    my_broker_info = dht_broker_info
                else:
                    if my_broker_info['position'] == my_position:
                        lg.warn('my broker info already found on correct position, ignoring record: %r' % dht_broker_info)
                    else:
                        lg.warn('my broker info already found, but on different position: %d' % my_broker_info['position'])
                        if int(my_broker_info['position']) == int(dht_broker_position):
                            pass
                        else:
                            lg.warn('overwriting already populated broker record found on another position: %d' % dht_broker_position)
                            my_broker_info = dht_broker_info
        if _Debug:
            lg.args(_DebugLevel, my_broker_info=my_broker_info, my_position_info=my_position_info)
        if not my_broker_info:
            self.dht_read_use_cache = False
            if not my_position_info:
                self.automat('my-record-not-exist', desired_position=my_position)
            else:
                self.automat('other-broker-exist', broker_info=my_position_info)
            return
        my_position_ok = int(my_broker_info['position']) == int(my_position)
        my_idurl_ok = False
        if my_position_info:
            my_idurl_ok = id_url.to_bin(my_position_info['broker_idurl']) == id_url.to_bin(my_broker_info['broker_idurl'])
        if not my_position_ok or not my_idurl_ok:
            lg.err('found my broker info in DHT, but it is not correct: pos=%s idurl=%s' % (my_position_ok, my_idurl_ok, ))
            self.dht_read_use_cache = False
            if not my_idurl_ok:
                self.automat('other-broker-exist', broker_info=my_position_info)
            else:
                self.automat('my-record-not-correct', desired_position=my_position)
            return
        self.dht_read_use_cache = True
        self.known_archive_folder_path = my_broker_info['archive_folder_path']
        self.automat('my-record-correct', broker_idurl=my_broker_info['broker_idurl'], position=my_broker_info['position'])

    def _on_write_customer_message_broker(self, nodes, desired_broker_position):
        if _Debug:
            lg.args(_DebugLevel, nodes=nodes, desired_broker_position=desired_broker_position)
        if nodes:
            self.requested_archive_folder_path = None
            self.automat('dht-write-success', desired_position=desired_broker_position)
        else:
            self.dht_read_use_cache = False
            self.automat('dht-write-failed', desired_position=desired_broker_position)

    def _on_write_customer_message_broker_failed(self, err, desired_broker_position):
        if _Debug:
            lg.args(_DebugLevel, err=err, desired_broker_position=desired_broker_position)
        self.dht_read_use_cache = False
        self.automat('dht-write-failed', desired_position=desired_broker_position)

    def _on_queue_keeper_refresh_task(self):
        if _Debug:
            lg.args(_DebugLevel, state=self.state, known_position=self.known_position, connected_queues=self.connected_queues)
        if self.state == 'CONNECTED':
            self.dht_read_use_cache = False
            reactor.callLater(0, self.automat, 'connect')  # @UndefinedVariable

    def _on_other_broker_response(self, idurl):
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl)
        if idurl:
            self.automat('other-broker-connected')
        else:
            self.automat('other-broker-disconnected')

    def _on_other_broker_failed(self, err):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        self.automat('other-broker-disconnected')
