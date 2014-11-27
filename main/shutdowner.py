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

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat
from automats import global_state

from system import bpio

import initializer
import init_shutdown

#------------------------------------------------------------------------------ 

_Shutdowner = None

#------------------------------------------------------------------------------

def A(event=None, arg=None):
    global _Shutdowner
    if _Shutdowner is None:
        _Shutdowner = Shutdowner('shutdowner', 'AT_STARTUP', 2)
    if event is not None:
        _Shutdowner.event(event, arg)
    return _Shutdowner


class Shutdowner(automat.Automat):
    """
    This is a state machine to manage a process of correctly finishing the BitPie.NET software. 
    """
    
    fast = True
    
    def init(self):
        self.flagApp = False
        self.flagReactor = False
        self.shutdown_param = None
    
    def state_changed(self, oldstate, newstate, event, arg):
        global_state.set_global_state('SHUTDOWN ' + newstate)
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
                self.doDestroyMe(arg)
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
                self.doDestroyMe(arg)
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
                self.doDestroyMe(arg)
        #---FINISHED---
        elif self.state == 'FINISHED':
            pass
        #---STOPPING---
        elif self.state == 'STOPPING':
            if event == 'reactor-stopped' :
                self.state = 'FINISHED'
                self.doDestroyMe(arg)
        return None

    def doSaveParam(self, arg):
        self.shutdown_param = arg
        lg.out(2, 'shutdowner.doSaveParam %s' % str(self.shutdown_param))

    def doShutdown(self, arg):
        lg.out(2, 'shutdowner.doShutdown %d machines currently' % len(automat.objects()))
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
            init_shutdown.shutdown_exit()
        elif param == 'restart':
            init_shutdown.shutdown_restart()
        elif param == 'restartnshow':
            init_shutdown.shutdown_restart('show')

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        global _Shutdowner
        del _Shutdowner
        _Shutdowner = None
        self.destroy()
        lg.out(2, 'shutdowner.doDestroyMe %d machines left in memory' % len(automat.objects()))

