#!/usr/bin/python
# events.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (events.py) is part of BitDust Software.
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
.. module:: events.

A very simple "event" system, just to show and remember what is goin on.
Also you can subscribe to given event and receive notifications.

TODO: need to store events on the local HDD
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 18

_EventLogFileEnabled = True

#------------------------------------------------------------------------------

import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in events.py')

from twisted.internet.defer import Deferred  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from lib import utime

#------------------------------------------------------------------------------

MAX_PENDING_EVENTS_PER_CONSUMER = 100

#------------------------------------------------------------------------------

_Subscribers = {}
_ConsumersCallbacks = {}
_EventQueuePerConsumer = {}

#------------------------------------------------------------------------------

def subscribers():
    global _Subscribers
    return _Subscribers

#------------------------------------------------------------------------------

def init():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'events.init')
    add_subscriber(push_event)


def shutdown():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'events.shutdown')
    subscribers().clear()

#------------------------------------------------------------------------------

class Event(object):
    """
    """

    def __init__(self, event_id, data=None, created=None):
        self.event_id = event_id
        self.data = data
        self.created = created or utime.get_sec1970()

    def __repr__(self):
        return '<{}>'.format(self.event_id)

#------------------------------------------------------------------------------

def add_subscriber(subscriber_callback, event_id='*'):
    """
    subscriber_callback(evt)
    """
    if event_id not in subscribers():
        subscribers()[event_id] = []
    subscribers()[event_id].append(subscriber_callback)
    return True


def remove_subscriber(subscriber_callback, event_id='*'):
    """
    """
    removed = False
    if event_id == '*':
        for event_id, subscriber_callbacks in subscribers().items():
            if subscriber_callback in subscriber_callbacks:
                subscribers()[event_id].remove(subscriber_callback)
                removed = True
    else:
        if event_id in subscribers():
            if subscriber_callback in subscribers()[event_id]:
                subscribers()[event_id].remove(subscriber_callback)
                removed = True
    return removed


def clear_subscribers(event_id='*'):
    """
    """
    removed = False
    for _event_id, subscriber_callbacks in subscribers().items():
        if _event_id == event_id or event_id == '*':
            for _cb in list(subscriber_callbacks):
                subscribers()[_event_id].remove(_cb)
                removed = True
    return removed

#------------------------------------------------------------------------------

def dispatch(evt):
    """
    """
    handled = 0
    if evt.event_id in subscribers():
        for subscriber_callback in subscribers()[evt.event_id]:
            try:
                subscriber_callback(evt)
            except:
                lg.exc()
                continue
            handled += 1
    if '*' in subscribers():
        for subscriber_callback in subscribers()['*']:
            try:
                subscriber_callback(evt)
            except:
                lg.exc()
                continue
            handled += 1
    if _Debug:
        if not handled:
            lg.warn('event {} was not handled'.format(evt.event_id))
        else:
            lg.out(_DebugLevel, 'events.dispatch {} was handled by {} subscribers'.format(
                evt.event_id, handled))
    if _EventLogFileEnabled:
        lg.out(2, '\033[0;49;91m%s\033[0m  %r' % (evt.event_id, str(evt.data)), log_name='event', showtime=True)
    return handled


def send(event_id, data=None, created=None):
    """
    """
    evt = Event(event_id, data=data, created=created)
    reactor.callWhenRunning(dispatch, evt)  # @UndefinedVariable
    return evt

#------------------------------------------------------------------------------


def event_queue():
    global _EventQueuePerConsumer
    return _EventQueuePerConsumer


def consumers_callbacks():
    global _ConsumersCallbacks
    return _ConsumersCallbacks


def consume_events(consumer_id):
    """
    """
    if consumer_id not in consumers_callbacks():
        consumers_callbacks()[consumer_id] = []
    d = Deferred()
    consumers_callbacks()[consumer_id].append(d)
    if _Debug:
        lg.out(_DebugLevel, 'events.consume_events added callback for consumer "%s", %d total callbacks' % (
            consumer_id, len(consumers_callbacks()[consumer_id])))
    reactor.callLater(0, pop_event)  # @UndefinedVariable
    return d


def push_event(event_object):
    """
    """
    for consumer_id in consumers_callbacks().keys():
        if consumer_id not in event_queue():
            event_queue()[consumer_id] = []
        event_queue()[consumer_id].append({
            'type': 'event',
            'id': event_object.event_id,
            'data': event_object.data,
            'time': event_object.created,
        })
        if _Debug:
            lg.out(_DebugLevel, 'events.push_event "%s" for consumer "%s", %d pending events' % (
                event_object.event_id, consumer_id, len(event_queue()[consumer_id])))
    reactor.callLater(0, pop_event)  # @UndefinedVariable


def pop_event():
    """
    """
    for consumer_id in list(consumers_callbacks().keys()):
        if consumer_id not in event_queue() or len(event_queue()[consumer_id]) == 0:
            continue
        registered_callbacks = consumers_callbacks()[consumer_id]
        pending_messages = event_queue()[consumer_id]
        if len(registered_callbacks) == 0 and len(pending_messages) > MAX_PENDING_EVENTS_PER_CONSUMER:
            consumers_callbacks().pop(consumer_id)
            event_queue().pop(consumer_id)
            if _Debug:
                lg.out(_DebugLevel, 'events.pop_event STOPPED consumer "%s", too many pending messages but no callbacks' % consumer_id)
            continue
        for consumer_callback in registered_callbacks:
            if not consumer_callback:
                if _Debug:
                    lg.out(_DebugLevel, 'events.pop_event %d events waiting consuming by "%s", no callback yet' % (
                        len(event_queue()[consumer_id]), consumer_id))
                continue
            if consumer_callback.called:
                if _Debug:
                    lg.out(_DebugLevel, 'events.pop_event %d events waiting consuming by "%s", callback state is "called"' % (
                        len(event_queue()[consumer_id]), consumer_id))
                continue
            consumer_callback.callback(pending_messages)
            event_queue()[consumer_id] = []
            if _Debug:
                lg.out(_DebugLevel, 'events.pop_event %d events consumed by "%s"' % (len(pending_messages), consumer_id))
        consumers_callbacks()[consumer_id] = []

#------------------------------------------------------------------------------
