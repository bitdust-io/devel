#!/usr/bin/env python
#automats.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: automats

This module is to keep track of changing states of State Machines.
It also remember the current ``global`` state of the program - this a stats of a several most important automats.
"""

import os
import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in automats.py')
    
from twisted.internet.defer import Deferred, maybeDeferred
from twisted.internet.task import LoopingCall

from logs import lg

import automat

#------------------------------------------------------------------------------

_StatesDict = {
    'init at startup':           'beginning',
    'init local':                'local settings initialization',
    'init contacts':             'contacts initialization',
    'init connection':           'initializing connections',
    'init modules':              'starting modules',
    'init install':              'preparing install section',
    'network at startup':        'starting connection',
    'network stun':              'detecting external IP address',
    'network upnp':              'configuring UPnP',
    'network connected':         'internet connection is fine',
    'network disconnected':      'internet connection is not working',
    'network network?':          'checking network interfaces',
    'network google?':           'is www.google.com available?',
    'p2p at startup':            'initial peer-to-peer state',
    'p2p transports':            'starting network transports',
    'p2p centralservice':        'connecting to central server',
    'p2p propagate':             'propagate my identity',
    'p2p incomming?':            'waiting response from others',
    'p2p connected':             'ready',
    'p2p disconnected':          'starting disconnected',
    'central at startup':        'starting central server connection',
    'central identity':          'sending my identity to central server',
    'central settings':          'sending my settings to central server',
    'central request settings':  'asking my settings from central server',
    'central suppliers':         'requesting suppliers from central server',
    'central connected':         'connected to central server',
    'central disconnected':      'disconnected from central server',
    }

_GlobalState = 'AT_STARTUP'
_GlobalStateNotifyFunc = None

#------------------------------------------------------------------------------

def set_global_state(st):
    """
    This method is called from State Machines when ``state`` is changed:
        automats.set_global_state('CENTRAL ' + newstate)
    So ``st`` is a string like: 'CENTRAL CONNECTED'.
    ``_GlobalStateNotifyFunc`` can be used to keep track of changing program states.
    """
    global _GlobalState
    global _GlobalStateNotifyFunc
    oldstate = _GlobalState
    _GlobalState = st
    lg.out(6, (' ' * 40) + '{%s}->{%s}' % (oldstate, _GlobalState))
    if _GlobalStateNotifyFunc is not None and oldstate != _GlobalState:
        try:
            _GlobalStateNotifyFunc(_GlobalState)
        except:
            lg.exc()


def get_global_state():
    """
    Return the current ``global state``, for example:
        P2P CONNECTED
    """
    global _GlobalState
    lg.out(6, 'automats.get_global_state return [%s]' % _GlobalState)
    return _GlobalState


def get_global_state_label():
    """
    Return a label describing current global state, for example:
        'checking network interfaces'
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
    Set callback to catch state change of any automat 
    """
    automat.SetStateChangedCallback(f)

#------------------------------------------------------------------------------








