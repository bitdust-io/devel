#!/usr/bin/env python
# queue_connector.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (fire_hire.py) is part of BitDust Software.
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
.. module:: queue_connector
.. role:: red

BitDust queue_connector() Automat

EVENTS:
    * :red:`broker-connected`
    * :red:`broker-exist`
    * :red:`broker-lookup-failed`
    * :red:`broker-refused`
    * :red:`connect`
    * :red:`dht-read-failed`
    * :red:`init`
    * :red:`message-in`
    * :red:`no-brokers-found`
    * :red:`no-more-messages`
    * :red:`shutdown`
    * :red:`timer-1min`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import sys
import time

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in fire_hire.py')

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

#------------------------------------------------------------------------------

_QueueConnector = None

#------------------------------------------------------------------------------

def A(event=None, *args, **kwargs):
    """
    Access method to interact with `queue_connector()` machine.
    """
    global _QueueConnector
    if event is None:
        return _QueueConnector
    if _QueueConnector is None:
        # TODO: set automat name and starting state here
        _QueueConnector = QueueConnector(
            name='queue_connector',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _QueueConnector.automat(event, *args, **kwargs)
    return _QueueConnector


def Destroy():
    """
    Destroy `queue_connector()` automat and remove its instance from memory.
    """
    global _QueueConnector
    if _QueueConnector is None:
        return
    _QueueConnector.destroy()
    del _QueueConnector
    _QueueConnector = None

#------------------------------------------------------------------------------

class QueueConnector(automat.Automat):
    """
    This class implements all the functionality of ``queue_connector()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['IN_SYNC']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `queue_connector()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `queue_connector()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `queue_connector()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(*args, **kwargs)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.state = 'DHT_READ'
                self.doDHTReadBrokers(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'no-brokers-found':
                self.state = 'FIND_BROKER?'
                self.doLookupBroker(*args, **kwargs)
            elif event == 'dht-read-failed':
                self.state = 'OFFLINE'
                self.doReportOffline(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'broker-exist':
                self.state = 'CATCH_UP?'
                self.doCatchUp(*args, **kwargs)
        #---FIND_BROKER?---
        elif self.state == 'FIND_BROKER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'broker-lookup-failed':
                self.state = 'OFFLINE'
                self.doReportOffline(*args, **kwargs)
            elif event == 'broker-connected':
                self.state = 'DHT_READ'
                self.doDHTReadBrokers(*args, **kwargs)
        #---CATCH_UP?---
        elif self.state == 'CATCH_UP?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'no-more-messages':
                self.state = 'IN_SYNC'
                self.doReportInSync(*args, **kwargs)
            elif event == 'broker-refused':
                self.state = 'FIND_BROKER?'
                self.doLookupBroker(*args, **kwargs)
            elif event == 'message-in':
                self.doProcessMsg(*args, **kwargs)
        #---IN_SYNC---
        elif self.state == 'IN_SYNC':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-1min':
                self.state = 'CATCH_UP?'
                self.doCatchUp(*args, **kwargs)
            elif event == 'message-in':
                self.doProcessMsg(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doDHTReadBrokers(self, *args, **kwargs):
        """
        Action method.
        """

    def doLookupBroker(self, *args, **kwargs):
        """
        Action method.
        """

    def doCatchUp(self, *args, **kwargs):
        """
        Action method.
        """

    def doProcessMsg(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportInSync(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportOffline(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()
