#!/usr/bin/python
# listeners.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (listeners.py) is part of BitDust Software.
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
.. module:: listeners.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 20

#------------------------------------------------------------------------------

import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in listeners.py')

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import utime

#------------------------------------------------------------------------------

_Listeners = {}
_ModelsToBePopulated = []

#------------------------------------------------------------------------------


def listeners():
    global _Listeners
    return _Listeners


#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'listeners.init')


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'listeners.shutdown')
    clear_listeners()


#------------------------------------------------------------------------------


class Snapshot(object):

    def __init__(self, model_name, snap_id=None, data=None, created=None, deleted=False):
        self.model_name = model_name
        self.snap_id = snap_id
        self.data = data
        self.created = created or utime.utcnow_to_sec1970()
        self.deleted = deleted

    def __repr__(self):
        return '[{}:{}{}>'.format(self.model_name, self.snap_id, ' DELETED' if self.deleted else '')

    def to_json(self):
        j = {
            'name': self.model_name,
            'id': self.snap_id,
            'data': self.data,
            'created': self.created,
        }
        if self.deleted:
            j['deleted'] = utime.utcnow_to_sec1970()
        return j


#------------------------------------------------------------------------------


def add_listener(listener_callback, model_name='*'):
    """
    listener_callback(snapshot_object)
    """
    if listener_callback in listeners().get(model_name, []):
        return False
    if model_name not in listeners():
        listeners()[model_name] = []
    listeners()[model_name].append(listener_callback)
    if _Debug:
        lg.args(_DebugLevel, m=model_name, cb=listener_callback)
    return True


def remove_listener(listener_callback, model_name='*'):
    removed = False
    if model_name == '*':
        for model_name, listeners_callbacks in listeners().items():
            if listener_callback in listeners_callbacks:
                listeners()[model_name].remove(listener_callback)
                removed = True
        if removed:
            for model_name in list(listeners().keys()):
                if not listeners()[model_name]:
                    listeners().pop(model_name)

    else:
        if model_name in listeners():
            if listener_callback in listeners()[model_name]:
                listeners()[model_name].remove(listener_callback)
                removed = True
                if not listeners()[model_name]:
                    listeners().pop(model_name)
    if _Debug:
        lg.args(_DebugLevel, m=model_name, cb=listener_callback, removed=removed)
    return removed


def clear_listeners(model_name='*'):
    removed = False
    total = 0
    for _model_name, listener_callbacks in listeners().items():
        if _model_name == model_name or model_name == '*':
            for _cb in list(listener_callbacks):
                listeners()[_model_name].remove(_cb)
                removed = True
                total += 1
    listeners().clear()
    if _Debug:
        lg.args(_DebugLevel, total=total)
    return removed


#------------------------------------------------------------------------------


def dispatch_snapshot(snap):
    handled = 0
    if snap.model_name in listeners():
        for listener_callback in listeners()[snap.model_name]:
            try:
                listener_callback(snap)
            except:
                lg.exc()
                continue
            handled += 1
    if '*' in listeners():
        for listener_callback in listeners()['*']:
            try:
                listener_callback(snap)
            except:
                lg.exc()
                continue
            handled += 1
    if _Debug:
        lg.args(_DebugLevel, handled=handled, snap=snap)
    return handled


#------------------------------------------------------------------------------


def push_snapshot(model_name, snap_id=None, data=None, created=None, deleted=False, fast=False):
    snap = Snapshot(model_name, snap_id=snap_id, data=data, created=created, deleted=deleted)
    # if _Debug:
    #     lg.args(_DebugLevel, s=snap, d=data)
    if fast:
        dispatch_snapshot(snap)
    else:
        reactor.callLater(0, dispatch_snapshot, snap)  # @UndefinedVariable
    return snap


#------------------------------------------------------------------------------


def populate_later(model_name=None, stop=False):
    global _ModelsToBePopulated
    if model_name is not None:
        if model_name not in _ModelsToBePopulated:
            _ModelsToBePopulated.append(model_name)
            if _Debug:
                lg.args(_DebugLevel, model_name=model_name)
        else:
            if stop:
                _ModelsToBePopulated.remove(model_name)
                if _Debug:
                    lg.args(_DebugLevel, model_name=model_name, stop=True)
    return _ModelsToBePopulated


def is_populate_required(model_name):
    return model_name in _ModelsToBePopulated
