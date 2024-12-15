#!/usr/bin/env python
# shutdowner.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 6

#------------------------------------------------------------------------------

import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in shutdowner.py')

from twisted.internet.defer import DeferredList

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.main import initializer
from bitdust.main import settings
from bitdust.main import config

#------------------------------------------------------------------------------

_Shutdowner = None

#------------------------------------------------------------------------------


def shutdown_settings():
    if config.conf():
        config.conf().removeConfigNotifier('logs/debug-level')
    settings.shutdown()


def shutdown_engine():
    from bitdust.contacts import identitydb
    from bitdust.userid import id_url
    from bitdust.main import listeners
    from bitdust.main import events
    identitydb.shutdown()
    id_url.shutdown()
    listeners.shutdown()
    events.shutdown()


def shutdown_automats():
    survived_automats = list(automat.objects().values())
    if survived_automats:
        lg.warn('found %d survived state machines, sending "shutdown" event to them all' % len(survived_automats))
        for a in survived_automats:
            if a.name != 'shutdowner':
                a.event('shutdown')
    survived_automats = list(automat.objects().values())
    if survived_automats:
        lg.warn('still found %d survived state machines, executing "destroy()" method to them all' % len(survived_automats))
        for a in survived_automats:
            if a.name != 'shutdowner':
                a.destroy()
    automat.shutdown()


def shutdown_local():
    from bitdust.logs import weblog
    from bitdust.logs import webtraffic
    from bitdust.system import tmpfile
    from bitdust.system import run_upnpc
    from bitdust.raid import eccmap
    from bitdust.lib import net_misc
    from bitdust.updates import git_proc
    from bitdust.crypt import my_keys
    from bitdust.userid import my_id
    my_keys.shutdown()
    my_id.shutdown()
    eccmap.shutdown()
    run_upnpc.shutdown()
    net_misc.shutdown()
    git_proc.shutdown()
    tmpfile.shutdown()
    try:
        weblog.shutdown()
    except:
        lg.exc()
    try:
        webtraffic.shutdown()
    except:
        lg.exc()


def shutdown_interfaces():
    from bitdust.interface import api_rest_http_server
    from bitdust.interface import api_web_socket
    from bitdust.interface import api_device
    # from bitdust.interface import ftp_server
    # ftp_server.shutdown()
    api_rest_http_server.shutdown()
    api_device.shutdown()
    api_web_socket.shutdown()


def shutdown_services():
    from bitdust.services import driver
    driver.shutdown()


def shutdown(x=None):
    """
    This is a top level method which control the process of finishing the
    program.

    Calls method ``shutdown()`` in other modules.
    """
    if _Debug:
        lg.out(_DebugLevel, 'shutdowner.shutdown ' + str(x))
    dl = []
    try:
        shutdown_services()
        shutdown_interfaces()
        shutdown_local()
        shutdown_automats()
        shutdown_engine()
        shutdown_settings()
    except:
        lg.exc()
    # TODO: rework all shutdown() methods to return deferred objects
    return DeferredList(dl)


#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    global _Shutdowner
    if event is None:
        return _Shutdowner
    if _Shutdowner is None:
        _Shutdowner = Shutdowner(
            name='shutdowner',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _Shutdowner.event(event, *args, **kwargs)
    return _Shutdowner


#------------------------------------------------------------------------------


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
        if _Debug:
            lg.out(_DebugLevel, 'shutdowner.doSaveParam %s' % str(self.shutdown_param))

    def doShutdown(self, *args, **kwargs):
        if _Debug:
            lg.out(_DebugLevel, 'shutdowner.doShutdown %d machines currently' % len(automat.objects()))

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
        if _Debug:
            lg.out(_DebugLevel, 'shutdowner.doDestroyMe %d machines left in memory:\n        %s' % (len(automat.objects()), '\n        '.join(['%d: %r' % (k, automat.by_index(k)) for k in automat.objects().keys()])))

        if self.enableMemoryProfile:
            try:
                from guppy import hpy  # @UnresolvedImport
                hp = hpy()
                hp.setrelheap()
                if _Debug:
                    lg.out(_DebugLevel, 'hp.heap():\n' + str(hp.heap()))
                    lg.out(_DebugLevel, 'hp.heap().byrcs:\n' + str(hp.heap().byrcs))
                    lg.out(_DebugLevel, 'hp.heap().byvia:\n' + str(hp.heap().byvia))
            except:
                if _Debug:
                    lg.out(_DebugLevel, 'guppy package is not installed')

    def _shutdown_restart(self, param=''):
        """
        Calls ``shutdown()`` method and stop the main reactor, then restart the
        program.
        """
        if _Debug:
            lg.out(_DebugLevel, 'shutdowner.shutdown_restart param=%s' % param)

        def do_restart(param):
            from bitdust.lib import misc
            from bitdust.system import bpio
            detach = False
            if bpio.Windows():
                detach = True
            misc.DoRestart(param, detach=detach)

        def shutdown_finished(x, param):
            if _Debug:
                lg.out(_DebugLevel, 'shutdowner.shutdown_finished want to stop the reactor')
            reactor.addSystemEventTrigger('after', 'shutdown', do_restart, param)  # @UndefinedVariable
            reactor.stop()  # @UndefinedVariable

        d = shutdown('restart')
        d.addBoth(shutdown_finished, param)

    def _shutdown_exit(self, x=None):
        """
        Calls ``shutdown()`` method and stop the main reactor, this will finish
        the program.
        """
        if _Debug:
            lg.out(_DebugLevel, 'shutdowner.shutdown_exit')

        def shutdown_reactor_stop(x=None):
            if _Debug:
                lg.out(_DebugLevel, 'shutdowner.shutdown_reactor_stop want to stop the reactor')
            reactor.stop()  # @UndefinedVariable

        d = shutdown(x)
        d.addBoth(shutdown_reactor_stop)
