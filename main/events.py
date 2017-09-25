#!/usr/bin/python
# events.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

_Debug = True
_DebugLevel = 12

#------------------------------------------------------------------------------

import time
import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in events.py')


#------------------------------------------------------------------------------

from logs import lg

#------------------------------------------------------------------------------

_Subscribers = {}

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

    def __init__(self, event_id, data=None):
        self.event_id = event_id
        self.data = data
        self.created = time.time()

    def __repr__(self):
        return '<{}>'.format(self.event_id)

#------------------------------------------------------------------------------

def add_subscriber(subscriber_callback, event_id='*'):
    """
    """
    if event_id not in subscribers():
        subscribers()[event_id] = []
    subscribers()[event_id].append(subscriber_callback)

def remove_subscriber(subscriber_callback):
    """
    """
    removed = False
    for event_id, subscriber_callbacks in subscribers().items():
        if subscriber_callback in subscriber_callbacks:
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
    handled = False
    if evt.event_id in subscribers():
        for subscriber_callback in subscribers()[evt.event_id]:
            try:
                subscriber_callback(evt)
            except:
                lg.exc()
                continue
            handled = True
    if '*' in subscribers():
        for subscriber_callback in subscribers()['*']:
            try:
                subscriber_callback(evt)
            except:
                lg.exc()
                continue
            handled = True
    if _Debug:
        if not handled:
            lg.warn('event {} was not handled'.format(evt.event_id))
    return handled


def send(event_id, data=None):
    """
    """
    evt = Event(event_id, data=data)
    reactor.callWhenRunning(dispatch, evt)
    return True
