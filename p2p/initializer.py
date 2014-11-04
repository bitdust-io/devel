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

import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in initializer.py')

from twisted.internet import defer

from logs import lg

from lib import bpio
from lib import automat
from lib import automats

from services import driver

import installer
import shutdowner
# import webcontrol

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
    A class to execute start up operations to launch BitPie.NET software. 
    """
    
    fast = True
    
    def init(self):
        self.flagCmdLine = False
        self.flagGUI = False
        self.is_installed = None
    
    def state_changed(self, oldstate, newstate, event, arg):
        automats.set_global_state('INIT ' + newstate)

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
        from p2p import webcontrol
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
        from p2p import webcontrol
        d = webcontrol.init()
        if self.flagGUI or not self.is_installed: 
            d.addCallback(webcontrol.show)
        try:
            from tray_icon import USE_TRAY_ICON
        except:
            USE_TRAY_ICON = False
            lg.exc()
        if USE_TRAY_ICON:
            from p2p import tray_icon
            tray_icon.SetControlFunc(webcontrol.OnTrayIconCommand)
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
        self.destroy()
        
    def _init_local(self):
        from lib import settings
        from lib import misc
        from lib import commands 
        from lib import tmpfile
        from lib import net_misc
        from p2p import run_upnpc
        from raid import eccmap
        misc.init()
        commands.init()
        if settings.enableWebStream():
            from logs import weblog
            weblog.init(settings.getWebStreamPort())
        if settings.enableWebTraffic():
            from logs import webtraffic
            webtraffic.init(port=settings.getWebTrafficPort())
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
        from p2p import local_tester
        from p2p import software_update
        from p2p import webcontrol
        reactor.callLater(0, local_tester.init)
        software_update.SetNewVersionNotifyFunc(webcontrol.OnGlobalVersionReceived)
        reactor.callLater(0, software_update.init)
        reactor.callLater(0, webcontrol.OnInitFinalDone)
    
#------------------------------------------------------------------------------ 

class MyTwistedOutputLog:
    softspace = 0
    def read(self): pass
    def write(self, s):
        lg.out(0, s.strip())
    def flush(self): pass
    def close(self): pass
