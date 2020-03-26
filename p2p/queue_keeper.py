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
    * :red:`dht-record-exist`
    * :red:`dht-record-not-exist`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`init`
    * :red:`msg-in`
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

from twisted.internet.task import LoopingCall
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import strng

from dht import dht_relations

from userid import id_url
from userid import global_id
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
    customer_idurl = strng.to_bin(customer_idurl)
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
        super(QueueKeeper, self).__init__(
            name="queue_keeper_%s#%d" % (self.customer_id, self.known_position),
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

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
            elif event == 'dht-record-exist' and self.isOwnRecord(*args, **kwargs):
                self.state = 'CONNECTED'
                self.doDHTRefresh(*args, **kwargs)
                self.doSetOwnPosition(*args, **kwargs)
                self.doRunCallbacks(event, *args, **kwargs)
            elif event == 'dht-read-failed':
                self.state = 'DISCONNECTED'
                self.doRunCallbacks(event, *args, **kwargs)
            elif event == 'dht-record-exist' and not self.isOwnRecord(*args, **kwargs):
                self.doFindNextPosition(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
            elif event == 'dht-record-not-exist':
                self.state = 'DHT_WRITE'
                self.doDHTWrite(*args, **kwargs)
            elif event == 'connect':
                self.doAddCallback(*args, **kwargs)
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
                self.doSetDesiredPosition(*args, **kwargs)
                self.doAddCallback(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
            elif event == 'connect' and self.isPositionDesired(*args, **kwargs):
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

    def isOwnRecord(self, *args, **kwargs):
        """
        Condition method.
        """
        return kwargs.get('broker_idurl') == self.broker_idurl

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

    def doSetDesiredPosition(self, *args, **kwargs):
        """
        Action method.
        """
        self.new_possible_position = kwargs.get('desired_position', -1)

    def doFindNextPosition(self, *args, **kwargs):
        """
        Action method.
        """
        current_broker_position = kwargs.get('position', -1)
        self.new_possible_position = current_broker_position + 1

    def doProc(self, *args, **kwargs):
        """
        Action method.
        """

    def doDHTRead(self, *args, **kwargs):
        """
        Action method.
        """
        possible_broker_position = kwargs.get('desired_position', -1)
        if self.new_possible_position is not None:
            possible_broker_position = self.new_possible_position
        if possible_broker_position < 0:
            possible_broker_position = 0
        result = dht_relations.read_customer_message_brokers(
            customer_idurl=self.customer_idurl,
            positions=[possible_broker_position, ],
        )
        # TODO: add more validations of dht_result
        result.addCallback(self._on_read_customer_message_brokers, possible_broker_position)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTRead')
        result.addErrback(lambda err: self.automat('dht-read-failed', err))

    def doDHTWrite(self, *args, **kwargs):
        """
        Action method.
        """
        desired_position = kwargs.get('desired_position', 0)
        result = dht_relations.write_customer_message_broker(
            customer_idurl=self.customer_idurl,
            broker_idurl=self.broker_idurl,
            position=desired_position,
        )
        result.addCallback(self._on_write_customer_message_broker, desired_position)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='queue_keeper.doDHTWrite')
        result.addErrback(lambda err: self.automat('dht-write-failed', err))

    def doDHTRefresh(self, *args, **kwargs):
        """
        Action method.
        """

    def doReconnect(self, *args, **kwargs):
        """
        Action method.
        """
        reactor.callLater(0, self.automat, 'connect')  # @UndefinedVariable

    def doSetOwnPosition(self, *args, **kwargs):
        """
        Action method.
        """
        self.known_position = kwargs.get('position')

    def doRunCallbacks(self, event, *args, **kwargs):
        """
        Action method.
        """
        success = True if event in ['connect', 'dht-record-exist', ] else False
        for cb, queue_id in self.registered_callbacks:
            if queue_id and success:
                self.connected_queues.add(queue_id)
            if not cb.called:
                cb.callback(success)
        self.registered_callbacks.clear()

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
        self.destroy()

    def _on_read_customer_message_brokers(self, brokers_info_list, possible_broker_position):
        if _Debug:
            lg.args(_DebugLevel, brokers=brokers_info_list)
        self.new_possible_position = None
        if not brokers_info_list:
            self.automat('dht-record-not-exist', desired_position=possible_broker_position)
            return
        if len(brokers_info_list) > 1:
            lg.warn('more than one broker returned from dht request')
        self.automat('dht-record-exist', broker_idurl=brokers_info_list[0]['broker_idurl'], position=brokers_info_list[0]['position'])

    def _on_write_customer_message_broker(self, nodes, desired_broker_position):
        if _Debug:
            lg.args(_DebugLevel, nodes=nodes, desired_broker_position=desired_broker_position)
        if nodes:
            self.automat('dht-write-success', desired_position=desired_broker_position)
        else:
            self.automat('dht-write-failed', desired_position=desired_broker_position)
