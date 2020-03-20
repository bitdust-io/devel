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
    * :red:`init`
    * :red:`msg-in`
    * :red:`read-failed`
    * :red:`record-exist`
    * :red:`record-not-exist`
    * :red:`shutdown`
    * :red:`write-failed`
    * :red:`write-success`
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

from userid import id_url
from userid import global_id

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


def check_create(customer_idurl):
    """
    Creates new instance of queue_keeper() state machine and send "init" event to it.
    """
    customer_idurl = strng.to_bin(customer_idurl)
    if id_url.is_empty(customer_idurl):
        return False
    if not id_url.is_cached(customer_idurl):
        return False
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in list(queue_keepers().keys()):
        A(customer_idurl, 'init')
        if _Debug:
            lg.out(_DebugLevel, 'queue_keeper.check_create instance for customer %r was not found, made a new instance' % customer_idurl)
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
            name='queue_%s' % global_id.UrlToGlobalID(customer_idurl),
            state='AT_STARTUP',
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

    def __init__(self, customer_idurl, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `queue_keeper()` state machine.
        """
        self.customer_idurl = customer_idurl
        super(QueueKeeper, self).__init__(
            name="queue_keeper",
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
        self.Position = 0

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
                self.doDestroyMe(*args, **kwargs)
            elif event == 'record-exist' and not self.isOwnRecord(*args, **kwargs):
                self.Position+=1
                self.doDHTRead(*args, **kwargs)
            elif event == 'read-failed':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
            elif event == 'record-not-exist':
                self.state = 'DHT_WRITE'
                self.doDHTWrite(*args, **kwargs)
            elif event == 'record-exist' and self.isOwnRecord(*args, **kwargs):
                self.state = 'CONNECTED'
                self.doDHTRefresh(*args, **kwargs)
                self.doReportConnected(*args, **kwargs)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'write-success':
                self.state = 'DHT_READ'
                self.doDHTRead(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
            elif event == 'write-failed':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.state = 'DHT_READ'
                self.Position=0
                self.doDHTRead(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.state = 'DHT_READ'
                self.Position=0
                self.doDHTRead(*args, **kwargs)
            elif event == 'msg-in':
                self.doProc(*args, **kwargs)
                self.doReconnect(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isOwnRecord(self, *args, **kwargs):
        """
        Condition method.
        """

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doProc(self, *args, **kwargs):
        """
        Action method.
        """

    def doDHTRead(self, *args, **kwargs):
        """
        Action method.
        """

    def doDHTWrite(self, *args, **kwargs):
        """
        Action method.
        """

    def doDHTRefresh(self, *args, **kwargs):
        """
        Action method.
        """

    def doReconnect(self, *args, **kwargs):
        """
        Action method.
        """
        reactor.callLater(0, self.automat, 'connect')  # @UndefinedVariable

    def doReportConnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportDisconnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _QueueKeepers
        _QueueKeepers.pop(self.customer_idurl)
        self.customer_idurl = None
        self.destroy()

