#!/usr/bin/env python
# shutdowner.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (shutdowner.py) is part of BitDust Software.
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
.. module:: shutdowner.

.. raw:: html

    <a href="https://bitdust.io/automats/shutdowner/shutdowner.png" target="_blank">
    <img src="https://bitdust.io/automats/shutdowner/shutdowner.png" style="max-width:100%;">
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

from __future__ import absolute_import
import six

import os
import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in shutdowner.py')

from twisted.internet.defer import DeferredList

#------------------------------------------------------------------------------

from logs import lg

from automats import automat
from automats import global_state

from main import initializer
from main import settings

#------------------------------------------------------------------------------

_Shutdowner = None

#------------------------------------------------------------------------------


def shutdown(x=None):
    """
    This is a top level method which control the process of finishing the
    program.

    Calls method ``shutdown()`` in other modules.
    """
    lg.out(2, "shutdowner.shutdown " + str(x))
    from services import driver
    from main import control
    from main import events
    from logs import weblog
    from logs import webtraffic
    from system import tmpfile
    from system import run_upnpc
    from raid import eccmap
    from lib import net_misc
    from updates import git_proc
    from interface import api_jsonrpc_server
    from interface import api_rest_http_server
    from interface import ftp_server
    from userid import my_id
    from crypt import my_keys
    dl = []
    my_keys.shutdown()
    my_id.shutdown()
    ftp_server.shutdown()
    api_jsonrpc_server.shutdown()
    api_rest_http_server.shutdown()
    driver.shutdown()
    eccmap.shutdown()
    run_upnpc.shutdown()
    net_misc.shutdown()
    git_proc.shutdown()
    events.clear_subscribers()
    tmpfile.shutdown()
    control.shutdown()
    weblog.shutdown()
    webtraffic.shutdown()
    survived_automats = list(automat.objects().values())
    for a in survived_automats:
        if a.name != 'shutdowner':
            a.event('shutdown')
    return DeferredList(dl)

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    global _Shutdowner
    if _Shutdowner is None:
        _Shutdowner = Shutdowner('shutdowner', 'AT_STARTUP', 2, True)
    if event is not None:
        _Shutdowner.event(event, *args, **kwargs)
    return _Shutdowner


class Shutdowner(automat.Automat):
    """
    This is a state machine to manage a process of correctly finishing the
    BitDust software.
    """

    fast = True

    def init(self):
        self.flagApp = False
        self.flagReactor = False
        self.shutdown_param = None
        self.enableMemoryProfile = settings.enableMemoryProfile()


    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        global_state.set_global_state('SHUTDOWN ' + newstate)
        initializer.A('shutdowner.state', newstate)

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'INIT'
                self.flagApp = False
                self.flagReactor = False
        #---INIT---
        elif self.state == 'INIT':
            if event == 'stop':
                self.doSaveParam(*args, **kwargs)
                self.flagApp = True
            elif event == 'reactor-stopped':
                self.flagReactor = True
            elif event == 'ready' and self.flagReactor:
                self.state = 'FINISHED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ready' and not self.flagReactor and self.flagApp:
                self.state = 'STOPPING'
                self.doShutdown(*args, **kwargs)
            elif event == 'ready' and not self.flagReactor and not self.flagApp:
                self.state = 'READY'
        #---READY---
        elif self.state == 'READY':
            if event == 'stop':
                self.state = 'STOPPING'
                self.doShutdown(*args, **kwargs)
            elif event == 'reactor-stopped':
                self.state = 'FINISHED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'block':
                self.state = 'BLOCKED'
        #---BLOCKED---
        elif self.state == 'BLOCKED':
            if event == 'stop':
                self.doSaveParam(*args, **kwargs)
                self.flagApp = True
            elif event == 'reactor-stopped':
                self.flagReactor = True
            elif event == 'unblock' and not self.flagReactor and not self.flagApp:
                self.state = 'READY'
            elif event == 'unblock' and not self.flagReactor and self.flagApp:
                self.state = 'STOPPING'
                self.doShutdown(*args, **kwargs)
            elif event == 'unblock' and self.flagReactor:
                self.state = 'FINISHED'
                self.doDestroyMe(*args, **kwargs)
        #---FINISHED---
        elif self.state == 'FINISHED':
            pass
        #---STOPPING---
        elif self.state == 'STOPPING':
            if event == 'reactor-stopped':
                self.state = 'FINISHED'
                self.doDestroyMe(*args, **kwargs)
        return None

    def doSaveParam(self, *args, **kwargs):
        self.shutdown_param = args[0]
        lg.out(2, 'shutdowner.doSaveParam %s' % str(self.shutdown_param))

    def doShutdown(self, *args, **kwargs):
        lg.out(2, 'shutdowner.doShutdown %d machines currently' % len(automat.objects()))

        param = args[0]
        if self.shutdown_param is not None:
            param = self.shutdown_param
        if not args or args[0] is None:
            param = 'exit'
        elif isinstance(args[0], six.string_types):
            param = args[0]
        if param not in ['exit', 'restart', 'restartnshow']:
            param = 'exit'
        if param == 'exit':
            self._shutdown_exit()
        elif param == 'restart':
            self._shutdown_restart()
        elif param == 'restartnshow':
            self._shutdown_restart('show')

    def doDestroyMe(self, *args, **kwargs):
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

        if self.enableMemoryProfile:
            try:
                from guppy import hpy  # @UnresolvedImport
                hp = hpy()
                hp.setrelheap()
                lg.out(2, 'hp.heap():\n'+str(hp.heap()))
                lg.out(2, 'hp.heap().byrcs:\n'+str(hp.heap().byrcs))
                lg.out(2, 'hp.heap().byvia:\n'+str(hp.heap().byvia))
            except:
                lg.out(2, "guppy package is not installed")

    #------------------------------------------------------------------------------

    def _shutdown_restart(self, param=''):
        """
        Calls ``shutdown()`` method and stop the main reactor, then restart the
        program.
        """
        lg.out(2, "shutdowner.shutdown_restart param=%s" % param)

        def do_restart(param):
            from lib import misc
            from system import bpio
            from main import settings
            settings.init()
            appdata = settings.BaseDir()
            detach = False
            if bpio.Windows():
                detach = True
            misc.DoRestart(
                param,
                detach=detach,
                std_out=os.path.join(appdata, 'logs', 'stdout.log'),
                std_err=os.path.join(appdata, 'logs', 'stderr.log'),
            )

        def shutdown_finished(x, param):
            lg.out(2, "shutdowner.shutdown_finished want to stop the reactor")
            reactor.addSystemEventTrigger('after', 'shutdown', do_restart, param)  # @UndefinedVariable
            reactor.stop()  # @UndefinedVariable
        d = shutdown('restart')
        d.addBoth(shutdown_finished, param)

    def _shutdown_exit(self, x=None):
        """
        Calls ``shutdown()`` method and stop the main reactor, this will finish
        the program.
        """
        lg.out(2, "shutdowner.shutdown_exit")

        def shutdown_reactor_stop(x=None):
            lg.out(2, "shutdowner.shutdown_reactor_stop want to stop the reactor")
            reactor.stop()  # @UndefinedVariable
        d = shutdown(x)
        d.addBoth(shutdown_reactor_stop)
