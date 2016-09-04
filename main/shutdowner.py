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

    <a href="http://bitdust.io/automats/shutdowner/shutdowner.png" target="_blank">
    <img src="http://bitdust.io/automats/shutdowner/shutdowner.png" style="max-width:100%;">
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

from twisted.internet.defer import DeferredList

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat
from automats import global_state

import initializer

#------------------------------------------------------------------------------ 

_Shutdowner = None

#------------------------------------------------------------------------------

def shutdown(x=None):
    """
    This is a top level method which control the process of finishing the program.
    Calls method ``shutdown()`` in other modules.
    """
    lg.out(2, "shutdowner.shutdown " + str(x))
    from services import driver
    from main import settings
    from logs import weblog
    from logs import webtraffic
    from system import tmpfile
    from system import run_upnpc
    from raid import eccmap
    from lib import net_misc
    from updates import git_proc
    from automats import automat
    dl = []
    driver.shutdown()
    eccmap.shutdown()
    run_upnpc.shutdown()
    net_misc.shutdown()
    git_proc.shutdown()
    if settings.NewWebGUI():
        from web import control
        dl.append(control.shutdown())
    else:
        from web import webcontrol
        dl.append(webcontrol.shutdown())
    weblog.shutdown()
    webtraffic.shutdown()
    for a in automat.objects().values():
        if a.name != 'shutdowner':
            a.event('shutdown')
    return DeferredList(dl)        
    
#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    global _Shutdowner
    if _Shutdowner is None:
        _Shutdowner = Shutdowner('shutdowner', 'AT_STARTUP', 2, True)
    if event is not None:
        _Shutdowner.event(event, arg)
    return _Shutdowner


class Shutdowner(automat.Automat):
    """
    This is a state machine to manage a process of correctly finishing the BitDust software. 
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
            self._shutdown_exit()
        elif param == 'restart':
            self._shutdown_restart()
        elif param == 'restartnshow':
            self._shutdown_restart('show')

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        global _Shutdowner
        del _Shutdowner
        _Shutdowner = None
        self.destroy()
        lg.out(2, 'shutdowner.doDestroyMe %d machines left in memory:\n        %s' % (
            len(automat.objects()), '\n        '.join(
                ['%d: %r' % (k, automat.objects()[k]) for k in automat.objects().keys()])))

    #------------------------------------------------------------------------------ 
    
    def _shutdown_restart(self, param=''):
        """
        Calls ``shutdown()`` method and stop the main reactor, then restart the program. 
        """
        lg.out(2, "shutdowner.shutdown_restart param=%s" % param)
        def do_restart(param):
            from lib import misc
            from system import bpio
            detach = False
            if bpio.Windows():
                detach = True
            misc.DoRestart(param, detach=detach)
        def shutdown_finished(x, param):
            lg.out(2, "shutdowner.shutdown_finished want to stop the reactor")
            reactor.addSystemEventTrigger('after','shutdown', do_restart, param)
            reactor.stop()
        d = shutdown('restart')
        d.addBoth(shutdown_finished, param)
    
    def _shutdown_exit(self, x=None):
        """
        Calls ``shutdown()`` method and stop the main reactor, this will finish the program. 
        """
        lg.out(2, "shutdowner.shutdown_exit")
        def shutdown_reactor_stop(x=None):
            lg.out(2, "shutdowner.shutdown_reactor_stop want to stop the reactor")
            reactor.stop()
        d = shutdown(x)
        d.addBoth(shutdown_reactor_stop)

        