#!/usr/bin/env python
# global_state.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (global_state.py) is part of BitDust Software.
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
#

"""
.. module:: global_state.

This module is to keep track of changing states of State Machines.
It also remember the current ``global`` state of the program - this a stats of a several most important automats.
"""

from __future__ import absolute_import

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

#------------------------------------------------------------------------------

_StatesDict = {
    'init at startup': 'beginning',
    'init local': 'local settings initialization',
    'init contacts': 'contacts initialization',
    'init connection': 'initializing connections',
    'init modules': 'starting modules',
    'init install': 'preparing install section',
    'network at startup': 'starting connection',
    'network stun': 'detecting external IP address',
    'network upnp': 'configuring UPnP',
    'network connected': 'internet connection is fine',
    'network disconnected': 'internet connection is not working',
    'network network?': 'checking network interfaces',
    'network google?': 'is www.google.com available?',
    'p2p at startup': 'initial peer-to-peer state',
    'p2p transports': 'starting network transports',
    'p2p propagate': 'propagate my identity',
    'p2p incomming?': 'waiting response from others',
    'p2p connected': 'ready',
    'p2p disconnected': 'starting disconnected',
}

_GlobalState = 'AT_STARTUP'
_GlobalStateNotifyFunc = None

#------------------------------------------------------------------------------


def set_global_state(st):
    """
    This method is called from State Machines when ``state`` is changed:
    global_state.set_global_state('P2P ' + newstate) So ``st`` is a string
    like: 'P2P CONNECTED'.

    ``_GlobalStateNotifyFunc`` can be used to keep track of changing
    program states.
    """
    global _GlobalState
    global _GlobalStateNotifyFunc
    oldstate = _GlobalState
    _GlobalState = st
    # lg.out(6, (' ' * 40) + '{%s}->{%s}' % (oldstate, _GlobalState))
    if _GlobalStateNotifyFunc is not None and oldstate != _GlobalState:
        try:
            _GlobalStateNotifyFunc(_GlobalState)
        except:
            lg.exc()


def get_global_state():
    """
    Return the current ``global state``, for example: P2P CONNECTED.
    """
    global _GlobalState
    # lg.out(6, 'global_state.get_global_state return [%s]' % _GlobalState)
    return _GlobalState


def get_global_state_label():
    """
    Return a label describing current global state, for example: 'checking
    network interfaces'.
    """
    global _GlobalState
    global _StatesDict
    return _StatesDict.get(_GlobalState.replace('_', ' ').lower(), '')


def SetGlobalStateNotifyFunc(f):
    """
    Set callback to catch a global state changed event.
    """
    global _GlobalStateNotifyFunc
    _GlobalStateNotifyFunc = f


def SetSingleStateNotifyFunc(f):
    """
    Set callback to catch state change of any automat.
    """
    automat.SetStateChangedCallback(f)

#------------------------------------------------------------------------------
