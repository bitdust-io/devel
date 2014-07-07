#!/usr/bin/env python
#shutdowner.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: shutdowner

.. raw:: html

    <a href="http://bitpie.net/automats/shutdowner/shutdowner.png" target="_blank">
    <img src="http://bitpie.net/automats/shutdowner/shutdowner.png" style="max-width:100%;">
    </a>
    
The state machine ``shutdowner()`` manages the completion of the program.

Synchronized between the completion of the blocking code and stop of the main Twisted reactor.

State "FINISHED" is a sign for the ``initializer()`` automat to stop of the whole program.


EVENTS:
    * :red:`block`
    * :red:`init`
    * :red:`reactor-stopped`
    * :red:`ready`
    * :red:`stop`
    * :red:`unblock`
"""

import os
import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in shutdowner.py')
from twisted.internet.defer import Deferred, maybeDeferred
from twisted.internet.task import LoopingCall

import lib.dhnio as dhnio
from lib.automat import Automat
import lib.automats as automats

import initializer
import dhninit

_Shutdowner = None

#------------------------------------------------------------------------------

def A(event=None, arg=None):
    global _Shutdowner
    if _Shutdowner is None:
        _Shutdowner = Shutdowner('shutdowner', 'AT_STARTUP', 2)
    if event is not None:
        _Shutdowner.event(event, arg)
    return _Shutdowner


class Shutdowner(Automat):
    
    def init(self):
        self.flagApp = False
        self.flagReactor = False
        self.shutdown_param = None
    
    def state_changed(self, oldstate, newstate):
        automats.set_global_state('SHUTDOWN ' + newstate)
        initializer.A('shutdowner.state', newstate)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'INIT'
                self.flagApp=False
                self.flagReactor=False
        #---INIT---
        elif self.state == 'INIT':
            if event == 'stop' :
                self.doSaveParam(arg)
                self.flagApp=True
            elif event == 'reactor-stopped' :
                self.flagReactor=True
            elif event == 'ready' and self.flagReactor :
                self.state = 'FINISHED'
            elif event == 'ready' and not self.flagReactor and self.flagApp :
                self.state = 'STOPPING'
                self.doShutdown(arg)
            elif event == 'ready' and not self.flagReactor and not self.flagApp :
                self.state = 'READY'
        #---READY---
        elif self.state == 'READY':
            if event == 'stop' :
                self.state = 'STOPPING'
                self.doShutdown(arg)
            elif event == 'reactor-stopped' :
                self.state = 'FINISHED'
            elif event == 'block' :
                self.state = 'BLOCKED'
        #---BLOCKED---
        elif self.state == 'BLOCKED':
            if event == 'stop' :
                self.doSaveParam(arg)
                self.flagApp=True
            elif event == 'reactor-stopped' :
                self.flagReactor=True
            elif event == 'unblock' and not self.flagReactor and not self.flagApp :
                self.state = 'READY'
            elif event == 'unblock' and not self.flagReactor and self.flagApp :
                self.state = 'STOPPING'
                self.doShutdown(arg)
            elif event == 'unblock' and self.flagReactor :
                self.state = 'FINISHED'
        #---FINISHED---
        elif self.state == 'FINISHED':
            pass
        #---STOPPING---
        elif self.state == 'STOPPING':
            if event == 'reactor-stopped' :
                self.state = 'FINISHED'

    def doSaveParam(self, arg):
        self.shutdown_param = arg
        dhnio.Dprint(2, 'shutdowner.doSaveParam %s' % str(self.shutdown_param))

    def doShutdown(self, arg):
        param = arg
        if self.shutdown_param is not None:
            param = self.shutdown_param
        if arg is None:
            param = 'exit' 
        elif isinstance(arg, str):
            param = arg
        if param not in ['exit', 'restart', 'restartnshow']:
            param = 'exit'
        if param == 'exit':
            dhninit.shutdown_exit()
        elif param == 'restart':
            dhninit.shutdown_restart()
        elif param == 'restartnshow':
            dhninit.shutdown_restart('show')






