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

    <a href="http://bitdust.io/automats/initializer/initializer.png" target="_blank">
    <img src="http://bitdust.io/automats/initializer/initializer.png" style="max-width:100%;">
    </a>

This Automat is the "entry point" to run all other state machines.
It manages the process of initialization of the whole program.

It also checks whether the program is installed and switch to run another "installation" code if needed. 

The ``initializer()`` machine is doing several operations:

    * start low-level modules and init local data, see ``initializer._init_local()``
    * starts the network communications by running core method ``initializer.doInitServices()``
    * other modules is started after all other more important things 
    * machine can switch to "install" wizard if Private Key or local identity file is not fine
    * it will finally switch to "READY" state to indicate the whole status of the application
    * during shutting down it will wait for ``shutdowner()`` automat to do its work completely
    * once ``shutdowner()`` become "FINISHED" - the state machine changes its state to "EXIT" and is destroyed
    
    
EVENTS:
    * :red:`init-interfaces-done`
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

from twisted.internet import defer

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio

from automats import automat
from automats import global_state

from services import driver

import installer
import shutdowner

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


def Destroy():
    """
    Destroy initializer() automat and remove its instance from memory.
    """
    global _Initializer
    if _Initializer is None:
        return
    _Initializer.destroy()
    del _Initializer
    _Initializer = None
    
    
class Initializer(automat.Automat):
    """
    A class to execute start up operations to launch BitDust software. 
    """
    
    fast = True
    
    def init(self):
        self.flagCmdLine = False
        self.flagGUI = False
        self.is_installed = None
    
    def state_changed(self, oldstate, newstate, event, arg):
        global_state.set_global_state('INIT ' + newstate)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'run' :
                self.state = 'LOCAL'
                shutdowner.A('init')
                self.doInitLocal(arg)
                self.flagCmdLine=False
            elif event == 'run-cmd-line-register' :
                self.state = 'INSTALL'
                shutdowner.A('init')
                self.flagCmdLine=True
                installer.A('register-cmd-line', arg)
                shutdowner.A('ready')
            elif event == 'run-cmd-line-recover' :
                self.state = 'INSTALL'
                shutdowner.A('init')
                self.flagCmdLine=True
                installer.A('recover-cmd-line', arg)
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
            if ( event == 'shutdowner.state' and arg == 'FINISHED' ) :
                self.state = 'EXIT'
                self.doDestroyMe(arg)
            elif event == 'init-services-done' :
                self.state = 'INTERFACES'
                self.doInitInterfaces(arg)
        #---INTERFACES---
        elif self.state == 'INTERFACES':
            if ( event == 'shutdowner.state' and arg == 'FINISHED' ) :
                self.state = 'EXIT'
                self.doDestroyMe(arg)
            elif event == 'init-interfaces-done' :
                self.state = 'MODULES'
                self.doInitModules(arg)
                self.doUpdate(arg)
                shutdowner.A('ready')
        return None

    def isInstalled(self, arg):
        if self.is_installed is None:
            self.is_installed = self._check_install() 
        return self.is_installed
    
    def isGUIPossible(self, arg):
        if bpio.Windows():
            return True
        if bpio.Linux():
            return bpio.X11_is_running()
        return False

    def doUpdate(self, arg):
        from web import webcontrol
        reactor.callLater(0, webcontrol.OnUpdateStartingPage)

    def doInitLocal(self, arg):
        """
        """
        lg.out(2, 'initializer.doInitLocal')
        self.flagGUI = arg
        self._init_local()
        reactor.callLater(0, self.automat, 'init-local-done')

    def doInitServices(self, arg):
        """
        Action method.
        """
        lg.out(2, 'initializer.doInitServices')
        driver.init()
        d = driver.start()
        d.addBoth(lambda x: self.automat('init-services-done'))

    def doInitInterfaces(self, arg):
        lg.out(2, 'initializer.doInitConnection')
        from interface import xmlrpc_server 
        xmlrpc_server.init()
        reactor.callLater(0, self.automat, 'init-interfaces-done')

    def doInitModules(self, arg):
        self._init_modules()
        reactor.callLater(0, self.automat, 'init-modules-done')

    def doShowGUI(self, arg):
        from main import settings
        if settings.NewWebGUI():
            from web import control
            control.init()
        else:
            from web import webcontrol
            d = webcontrol.init()
        try:
            from main.tray_icon import USE_TRAY_ICON
        except:
            USE_TRAY_ICON = False
            lg.exc()
        if USE_TRAY_ICON:
            from main import tray_icon
            if settings.NewWebGUI():
                tray_icon.SetControlFunc(control.on_tray_icon_command)
            else:
                tray_icon.SetControlFunc(webcontrol.OnTrayIconCommand)
        if not settings.NewWebGUI():
            webcontrol.ready()
        if self.flagGUI or not self.is_installed:
            if settings.NewWebGUI(): 
                reactor.callLater(0.1, control.show)
            else:
                d.addCallback(webcontrol.show)

    def doPrintMessage(self, arg):
        """
        Action method.
        """
        lg.out(0, 'You must register first, run command:')
        lg.out(0, '   bitdust register <your name>')

    def doDestroyMe(self, arg):
        global _Initializer
        del _Initializer
        _Initializer = None
        self.destroy()
        
    #------------------------------------------------------------------------------ 

    def _check_install(self):
        """
        Return True if Private Key and local identity files exists and both is valid.
        """
        lg.out(2, 'initializer._check_install')
        from main import settings
        from userid import identity
        from crypt import key
        keyfilename = settings.KeyFileName()
        keyfilenamelocation = settings.KeyFileNameLocation()
        if os.path.exists(keyfilenamelocation):
            keyfilename = bpio.ReadTextFile(keyfilenamelocation)
            if not os.path.exists(keyfilename):
                keyfilename = settings.KeyFileName()
        idfilename = settings.LocalIdentityFilename()
        if not os.path.exists(keyfilename) or not os.path.exists(idfilename):
            lg.out(2, 'initializer._check_install local key or local id not exists')
            return False
        current_key = bpio.ReadBinaryFile(keyfilename)
        current_id = bpio.ReadBinaryFile(idfilename)
        if current_id == '':
            lg.out(2, 'initializer._check_install local identity is empty ')
            return False
        if current_key == '':
            lg.out(2, 'initializer._check_install private key is empty ')
            return False
        try:
            key.InitMyKey()
        except:
            lg.out(2, 'initializer._check_install fail loading private key ')
            return False
        try:
            ident = identity.identity(xmlsrc=current_id)
        except:
            lg.out(2, 'initializer._check_install fail init local identity ')
            return False
        try:
            res = ident.Valid()
        except:
            lg.out(2, 'initializer._check_install wrong data in local identity   ')
            return False
        if not res:
            lg.out(2, 'initializer._check_install local identity is not valid ')
            return False
        lg.out(2, 'initializer._check_install done')
        return True
        
    def _init_local(self):
        from p2p import commands 
        from lib import net_misc
        from lib import misc
        from main import settings
        from system import tmpfile
        from system import run_upnpc
        from raid import eccmap
        from userid import my_id
        if settings.enableWebStream():
            from logs import weblog
            weblog.init(settings.getWebStreamPort())
        if settings.enableWebTraffic():
            from logs import webtraffic
            webtraffic.init(port=settings.getWebTrafficPort())
        misc.init()
        commands.init()
        tmpfile.init(settings.getTempDir())
        net_misc.init()
        settings.update_proxy_settings()
        run_upnpc.init()
        eccmap.init()
        if sys.argv.count('--twisted'):
            from twisted.python import log as twisted_log
            twisted_log.startLogging(MyTwistedOutputLog(), setStdout=0)
            # import twisted.python.failure as twisted_failure
            # twisted_failure.startDebugMode()
            # twisted_log.defaultObserver.stop()
        if settings.getDebugLevel() > 10:
            defer.setDebugging(True)
#        if settings.enableMemoryProfile():
#            try:
#                from guppy import hpy
#                hp = hpy()
#                hp.setrelheap()
#                lg.out(2, 'hp.heap():\n'+str(hp.heap()))
#                lg.out(2, 'hp.heap().byrcs:\n'+str(hp.heap().byrcs))
#                lg.out(2, 'hp.heap().byvia:\n'+str(hp.heap().byvia))
#            except:
#                lg.out(2, "guppy package is not installed")            
    
    def _init_modules(self):
        """
        Finish initialization part, run delayed methods.
        """
        lg.out(2,"initializer._init_modules")
        from updates import os_windows_update
        from web import webcontrol
        os_windows_update.SetNewVersionNotifyFunc(webcontrol.OnGlobalVersionReceived)
        reactor.callLater(0, os_windows_update.init)
        reactor.callLater(0, webcontrol.OnInitFinalDone)
    
#------------------------------------------------------------------------------ 

class MyTwistedOutputLog:
    softspace = 0
    def read(self): pass
    def write(self, s):
        lg.out(0, s.strip())
    def flush(self): pass
    def close(self): pass