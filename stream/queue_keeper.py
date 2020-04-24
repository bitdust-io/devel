#!/usr/bin/env python
# queue_keeper.py
#
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (online_status.py) is part of BitDust Software.
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
    sys.exit('Error initializing twisted.internet.reactor in online_status.py')

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import strng

from dht import dht_relations

from access import groups

from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

_QueueKeepers = {}

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


def check_create(customer_idurl, auto_create=True):
    """
    Creates new instance of queue_keeper() state machine and send "init" event to it.
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

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `queue_keeper()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `queue_keeper()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `queue_keeper()`
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
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
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
        if _Debug:
            lg.args(_DebugLevel, expected_broker_position=expected_broker_position, dht_read_use_cache=self.dht_read_use_cache,
                    has_rotated=self.has_rotated)
        use_cache = self.dht_read_use_cache
        if self.has_rotated:
            use_cache = False
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
        if _Debug:
            lg.args(_DebugLevel, desired_position=desired_position, broker_idurl=self.broker_idurl)
        result = dht_relations.write_customer_message_broker(
            customer_idurl=self.customer_idurl,
            broker_idurl=self.broker_idurl,
            position=desired_position,
        )
        result.addCallback(self._on_write_customer_message_broker, desired_position)
        if _Debug:
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTWrite')
        result.addErrback(self._on_write_customer_message_broker_failed, desired_position)

    def doDHTRefresh(self, *args, **kwargs):
        """
        Action method.
        """

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
        _QueueKeepers.pop(self.customer_idurl)
        self.customer_idurl = None
        self.broker_idurl = None
        self.known_position = -1
        self.new_possible_position = None
        self.registered_callbacks = None
        self.connected_queues = None
        self.known_brokers.clear()
        self.destroy()

    def _on_read_customer_message_brokers(self, brokers_info_list, my_position):
        self.known_brokers.clear()
        if not brokers_info_list:
            lg.warn('no brokers found in DHT records for customer %r' % self.customer_idurl)
            self.dht_read_use_cache = False
            self.automat('my-record-not-exist', desired_position=my_position)
            return
        my_broker_info = None
        my_position_info = None
        for broker_info in brokers_info_list:
            if broker_info:
                if broker_info['position'] == my_position:
                    my_position_info = broker_info
                if broker_info['broker_idurl'] == self.broker_idurl:
                    my_broker_info = broker_info
                self.known_brokers[broker_info['position']] = broker_info['broker_idurl']
        if _Debug:
            lg.args(_DebugLevel, my_position=my_position, my_broker_info=my_broker_info, my_position_info=my_position_info,
                    known_brokers=self.known_brokers)
        if not my_broker_info:
            self.dht_read_use_cache = False
            self.automat('my-record-not-exist', desired_position=my_position)
            return
        my_position_ok = int(my_broker_info['position']) == int(my_position)
        my_idurl_ok = my_position_info and my_position_info['broker_idurl'] == my_broker_info['broker_idurl']
        if _Debug:
            lg.args(_DebugLevel, my_position_ok=my_position_ok, my_idurl_ok=my_idurl_ok)
        if not my_position_ok or not my_idurl_ok:
            self.dht_read_use_cache = False
            self.automat('my-record-not-correct', desired_position=my_position)
            return
        self.dht_read_use_cache = True
        self.automat('my-record-correct', broker_idurl=my_broker_info['broker_idurl'], position=my_broker_info['position'])

    def _on_write_customer_message_broker(self, nodes, desired_broker_position):
        if _Debug:
            lg.args(_DebugLevel, nodes=nodes, desired_broker_position=desired_broker_position)
        if nodes:
            self.has_rotated = False
            self.automat('dht-write-success', desired_position=desired_broker_position)
        else:
            self.dht_read_use_cache = False
            self.automat('dht-write-failed', desired_position=desired_broker_position)

    def _on_write_customer_message_broker_failed(self, err, desired_broker_position):
        if _Debug:
            lg.args(_DebugLevel, err=err, desired_broker_position=desired_broker_position)
        self.dht_read_use_cache = False
        self.automat('dht-write-failed', desired_position=desired_broker_position)
