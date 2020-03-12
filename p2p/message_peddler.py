#!/usr/bin/env python
# message_peddler.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (message_peddler.py) is part of BitDust Software.
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
.. module:: message_peddler
.. role:: red

BitDust message_peddler() Automat

EVENTS:
    * :red:`consumer-subscribed`
    * :red:`consumer-unsubscribed`
    * :red:`producer-connected`
    * :red:`producer-disconnected`
    * :red:`queue-close`
    * :red:`queue-open`
    * :red:`queues-loaded`
    * :red:`start`
    * :red:`stop`
"""


#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import sys

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in keys_synchronizer.py')

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred, DeferredList
from twisted.python import failure

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from crypt import my_keys

from storage import backup_fs

from main import events

from raid import eccmap

from access import key_ring

from lib import jsn

from system import bpio
from system import local_fs

from main import settings

from p2p import p2p_queue

#------------------------------------------------------------------------------ 

_ActiveStreams = {}

_MessagePeddler = None

#------------------------------------------------------------------------------

def streams():
    global _ActiveStreams
    return _ActiveStreams

#------------------------------------------------------------------------------

def A(event=None, *args, **kwargs):
    """
    Access method to interact with `message_peddler()` machine.
    """
    global _MessagePeddler
    if event is None:
        return _MessagePeddler
    if _MessagePeddler is None:
        _MessagePeddler = MessagePeddler(
            name='message_peddler',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _MessagePeddler.automat(event, *args, **kwargs)
    return _MessagePeddler

#------------------------------------------------------------------------------

class MessagePeddler(automat.Automat):
    """
    This class implements all the functionality of ``message_peddler()`` state machine.
    """

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `message_peddler()` state machine.
        """
        super(MessagePeddler, self).__init__(
            name="message_peddler",
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
        at creation phase of `message_peddler()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `message_peddler()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `message_peddler()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'LOAD'
                self.doInit(*args, **kwargs)
                self.doLoadKnownQueues(*args, **kwargs)
        #---LOAD---
        elif self.state == 'LOAD':
            if event == 'queues-loaded':
                self.state = 'READY'
                self.doRunQueues(*args, **kwargs)
        #---READY---
        elif self.state == 'READY':
            if event == 'stop':
                self.state = 'CLOSED'
                self.doStopQueues(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'queue-open' or event == 'queue-close':
                self.doStartStopQueue(event, *args, **kwargs)
            elif event == 'consumer-subscribed' or event == 'consumer-unsubscribed' or event == 'producer-connected' or event == 'producer-disconnected':
                self.doAddRemoveQueueMember(event, *args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass


    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doLoadKnownQueues(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_open_known_streams()

    def doRunQueues(self, *args, **kwargs):
        """
        Action method.
        """

    def doStopQueues(self, *args, **kwargs):
        """
        Action method.
        """

    def doStartStopQueue(self, event, *args, **kwargs):
        """
        Action method.
        """

    def doAddRemoveQueueMember(self, event, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

    def _do_open_known_streams(self):
        service_dir = settings.ServiceDir('service_message_broker')
        queues_dir = os.path.join(service_dir, 'queues')
        consumers_dir = os.path.join(service_dir, 'consumers')
        producers_dir = os.path.join(service_dir, 'producers')
    
        for queue_id in os.listdir(queues_dir):
            stream_dirpath = os.path.join(queues_dir, queue_id)
            if queue_id not in streams():
                streams()[queue_id] = {
                    'messages': [],
                }
            if not p2p_queue.is_queue_exist(queue_id):
                p2p_queue.open_queue(queue_id)
            for message_id in os.listdir(stream_dirpath):
                streams()[queue_id]['messages'].append({
                    'message_id': message_id,
                    # TODO: ...
                })
    
        for consumer_id in os.listdir(consumers_dir):
            consumer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(consumers_dir, consumer_id)))
            queue_id = consumer_info['queue_id']
            if queue_id not in streams():
                lg.warn('unknown stream %r for consumer %r' % (queue_id, consumer_id))
                continue 
            if not p2p_queue.is_consumer_exists(consumer_id):
                p2p_queue.add_consumer(consumer_id)
            p2p_queue.subscribe_consumer(consumer_id, queue_id)
    
        for producer_id in os.listdir(producers_dir):
            producer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(producers_dir, producer_id)))
            queue_id = producer_info['queue_id']
            if queue_id not in streams():
                lg.warn('unknown stream %r for producer %r' % (queue_id, producer_id))
                continue 
            if not p2p_queue.is_producer_exist(producer_id):
                p2p_queue.add_producer(producer_id)
            p2p_queue.connect_producer(producer_id, queue_id)
    
