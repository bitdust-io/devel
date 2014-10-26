#!/usr/bin/env python
#initializer.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: initializer

.. raw:: html

    <a href="http://bitpie.net/automats/initializer/initializer.png" target="_blank">
    <img src="http://bitpie.net/automats/initializer/initializer.png" style="max-width:100%;">
    </a>

This Automat is the "entry point" to run all other state machines.
It manages the process of initialization of the whole program.

It also checks whether the program is installed and switch to run another "installation" code if needed. 

The ``initializer()`` machine is doing several operations:

    * start low-level modules and init local data, see ``p2p.init_shutdown.init_local()``
    * prepare lists of my contacts, see ``p2p.init_shutdown.init_contacts()``
    * starts the network communications by running core method ``p2p.init_shutdown.init_connection()``
    * other modules is started after all other more important things 
    * machine can switch to "install" wizard if Private Key or local identity file is not fine
    * it will finally switch to "READY" state to indicate the whole status of the application
    * during shutting down it will wait for ``shutdowner()`` automat to do its work completely
    * once ``shutdowner()`` become "FINISHED" - the state machine changes its state to "EXIT" and is destroyed
    
    
EVENTS:
    * :red:`connected`
    * :red:`disconnected`
    * :red:`init-contacts-done`
    * :red:`init-local-done`
    * :red:`init-modules-done`
    * :red:`init-services-done`
    * :red:`installer.state`
    * :red:`run`
    * :red:`run-cmd-line-recover`
    * :red:`run-cmd-line-register`
    * :red:`shutdowner.state`
"""

import os
import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in initializer.py')

from twisted.internet.defer import Deferred, maybeDeferred
from twisted.internet.task import LoopingCall

from logs import lg

from lib import bpio
from lib import automat
from lib import automats

from services import driver

import installer
import shutdowner
# import p2p_connector

# import init_shutdown
import webcontrol

#------------------------------------------------------------------------------ 

_Initializer = None

#------------------------------------------------------------------------------

def A(event=None, arg=None, use_reactor=True):
    """
    Access method to interact with the state machine.
    """
    global _Initializer
    if _Initializer is None:
        _Initializer = Initializer('initializer', 'AT_STARTUP', 2)
    if event is not None:
        if use_reactor:
            _Initializer.automat(event, arg)
        else:
            _Initializer.event(event, arg)
    return _Initializer


class Initializer(automat.Automat):
    """
    A class to execute start up operations to launch BitPie.NET software. 
    """
    
    def init(self):
        self.flagCmdLine = False
        self.is_installed = None
    
    def state_changed(self, oldstate, newstate, event, arg):
        automats.set_global_state('INIT ' + newstate)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'run' :
                self.state = 'LOCAL'
                self.doInitLocal(arg)
                self.flagCmdLine=False
                shutdowner.A('init')
            elif event == 'run-cmd-line-register' :
                self.state = 'INSTALL'
                self.flagCmdLine=True
                installer.A('register-cmd-line', arg)
                shutdowner.A('init')
                shutdowner.A('ready')
            elif event == 'run-cmd-line-recover' :
                self.state = 'INSTALL'
                self.flagCmdLine=True
                installer.A('recover-cmd-line', arg)
                shutdowner.A('init')
                shutdowner.A('ready')
        #---LOCAL---
        elif self.state == 'LOCAL':
            if event == 'init-local-done' and not self.isInstalled(arg) and self.isGUIPossible(arg) :
                self.state = 'INSTALL'
                self.doShowGUI(arg)
                installer.A('init')
                self.doUpdate(arg)
                shutdowner.A('ready')
            elif event == 'init-local-done' and not self.isInstalled(arg) and not self.isGUIPossible(arg) :
                self.state = 'STOPPING'
                self.doPrintMessage(arg)
                shutdowner.A('ready')
                shutdowner.A('stop', "exit")
            elif event == 'init-local-done' and self.isInstalled(arg) :
                self.state = 'SERVICES'
                self.doShowGUI(arg)
                self.doInitServices(arg)
        #---CONTACTS---
        elif self.state == 'CONTACTS':
            if event == 'init-contacts-done' :
                self.state = 'CONNECTION'
                self.doInitConnection(arg)
                self.doUpdate(arg)
                shutdowner.A('ready')
            elif ( event == 'shutdowner.state' and arg == 'FINISHED' ) :
                self.state = 'EXIT'
                self.doDestroyMe(arg)
        #---CONNECTION---
        elif self.state == 'CONNECTION':
            if ( event == 'shutdowner.state' and arg == 'FINISHED' ) :
                self.state = 'EXIT'
                self.doDestroyMe(arg)
            elif event == 'connected' or event == 'disconnected' :
                self.state = 'MODULES'
                self.doInitModules(arg)
                self.doUpdate(arg)
        #---MODULES---
        elif self.state == 'MODULES':
            if event == 'init-modules-done' :
                self.state = 'READY'
                self.doUpdate(arg)
            elif ( event == 'shutdowner.state' and arg == 'FINISHED' ) :
                self.state = 'EXIT'
                self.doDestroyMe(arg)
        #---INSTALL---
        elif self.state == 'INSTALL':
            if not self.flagCmdLine and ( event == 'installer.state' and arg == 'DONE' ) :
                self.state = 'STOPPING'
                shutdowner.A('stop', "restartnshow")
            elif self.flagCmdLine and ( event == 'installer.state' and arg == 'DONE' ) :
                self.state = 'STOPPING'
                shutdowner.A('stop', "exit")
            elif ( event == 'shutdowner.state' and arg == 'FINISHED' ) :
                self.state = 'EXIT'
                self.doDestroyMe(arg)
        #---READY---
        elif self.state == 'READY':
            if ( event == 'shutdowner.state' and arg == 'FINISHED' ) :
                self.state = 'EXIT'
                self.doDestroyMe(arg)
        #---STOPPING---
        elif self.state == 'STOPPING':
            if ( event == 'shutdowner.state' and arg == 'FINISHED' ) :
                self.state = 'EXIT'
                self.doUpdate(arg)
                self.doDestroyMe(arg)
        #---EXIT---
        elif self.state == 'EXIT':
            pass
        #---SERVICES---
        elif self.state == 'SERVICES':
            if event == 'init-services-done' :
                self.state = 'CONTACTS'
                self.doInitContacts(arg)
            elif ( event == 'shutdowner.state' and arg == 'FINISHED' ) :
                self.state = 'EXIT'
                self.doDestroyMe(arg)
        return None

    def isInstalled(self, arg):
        import init_shutdown
        if self.is_installed is None:
            self.is_installed = init_shutdown.check_install() 
        return self.is_installed
    
    def isGUIPossible(self, arg):
        if bpio.Windows():
            return True
        if bpio.Linux():
            return bpio.X11_is_running()
        return False

    def doUpdate(self, arg):
        reactor.callLater(0, webcontrol.OnUpdateStartingPage)

    def doInitLocal(self, arg):
        """
        """
        lg.out(2, 'initializer.doInitLocal')
        import init_shutdown
        maybeDeferred(init_shutdown.init_local, arg).addCallback(
            lambda x: self.automat('init-local-done'))

    def doInitServices(self, arg):
        """
        Action method.
        """
        lg.out(2, 'initializer.doInitServices')
        driver.init()
        driver.start()
            # callback=lambda : self.automat('init-services-done'))
        self.automat('init-services-done')

    def doInitContacts(self, arg):
        lg.out(2, 'initializer.doInitContacts')
        import init_shutdown
        init_shutdown.init_contacts(
            # lambda x: self.automat('init-contacts-done'),
            lambda x: reactor.callLater(2, self.automat, 'init-contacts-done'),
            lambda x: self.automat('init-contacts-done'), )

    def doInitConnection(self, arg):
        lg.out(2, 'initializer.doInitConnection')
        # init_shutdown.init_connection()
        # TODO
        self.automat('connected')

    def doInitModules(self, arg):
        self.automat('init-modules-done')
        # maybeDeferred(init_shutdown.init_modules).addCallback(
            # lambda x: self.automat('init-modules-done'))

    def doShowGUI(self, arg):
        import init_shutdown
        d = webcontrol.init()
        if init_shutdown.UImode == 'show' or not self.is_installed: 
            d.addCallback(webcontrol.show)
        webcontrol.ready()
        # sys.path.append(os.path.abspath('dj'))
        # import local_site
        # local_site.init()

    def doPrintMessage(self, arg):
        """
        Action method.
        """
        lg.out(0, 'You must register first, run command:')
        lg.out(0, '   bitpie register <your name>')

    def doDestroyMe(self, arg):
        global _Initializer
        del _Initializer
        _Initializer = None
        automat.objects().pop(self.index)


