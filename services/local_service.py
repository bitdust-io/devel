

"""
.. module:: local_service
.. role:: red

BitPie.NET local_service() Automat

.. raw:: html

    <a href="local_service.png" target="_blank">
    <img src="local_service.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`service-depends-broken`
    * :red:`service-depends-ok`
    * :red:`service-installed`
    * :red:`service-not-installed`
    * :red:`services-stopped`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------ 

from lib import automat

from driver import services, RequireSubclass, ServiceAlreadyExist

#------------------------------------------------------------------------------ 

class LocalService(automat.Automat):
    """
    This class implements all the functionality of the ``local_service()`` state machine.
    """
    
    name = ''

    def __init__(self):
        if self.name == '':
            raise RequireSubclass()
        if self.name in services().keys():
            raise ServiceAlreadyExist(self.name)
        automat.Automat.__init__(self, self.name, 'OFF', 10)

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.result_callback = None

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to to catch the moment when automat's state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        Method to to catch the moment when some event was fired but automat's state was not changed.
        """

    def A(self, event, arg):
        #---ON---
        if self.state == 'ON':
            if event == 'stop' :
                self.state = 'INFLUENCE'
                self.doSetCallback(arg)
                self.doStopDependentServices(arg)
        #---OFF---
        elif self.state == 'OFF':
            if event == 'start' :
                self.state = 'INSTALLED?'
                self.NeedStart=False
                self.NeedStop=False
                self.doSetCallback(arg)
                self.doCheckInstall(arg)
            elif event == 'stop' :
                self.doSetCallback(arg)
                self.doNotifyStopped(arg)
        #---NOT_INSTALLED---
        elif self.state == 'NOT_INSTALLED':
            if event == 'start' :
                self.state = 'INSTALLED?'
                self.doSetCallback(arg)
                self.doCheckInstall(arg)
            elif event == 'stop' :
                self.doSetCallback(arg)
                self.doNotifyNotInstalled(arg)
        #---DEPENDS_BROKEN---
        elif self.state == 'DEPENDS_BROKEN':
            if event == 'start' :
                self.state = 'DEPENDS?'
                self.doSetCallback(arg)
                self.doCheckDependencies(arg)
            elif event == 'stop' :
                self.doSetCallback(arg)
                self.doNotifyDependsBroken(arg)
        #---INFLUENCE---
        elif self.state == 'INFLUENCE':
            if event == 'services-stopped' and self.NeedStart :
                self.state = 'INSTALLED?'
                self.NeedStart=False
                self.doStopService(arg)
                self.doNotifyStopped(arg)
                self.doCheckInstall(arg)
            elif event == 'services-stopped' and not self.NeedStart :
                self.state = 'OFF'
                self.doStopService(arg)
                self.doNotifyStopped(arg)
            elif event == 'start' :
                self.doSetCallback(arg)
                self.NeedStart=True
            elif event == 'stop' :
                self.doSetCallback(arg)
        #---DEPENDS?---
        elif self.state == 'DEPENDS?':
            if event == 'service-depends-broken' :
                self.state = 'DEPENDS_BROKEN'
                self.doNotifyDependsBroken(arg)
            elif event == 'service-depends-ok' and self.NeedStop :
                self.state = 'INFLUENCE'
                self.NeedStop=False
                self.doStopDependentServices(arg)
            elif event == 'service-depends-ok' and not self.NeedStop :
                self.state = 'ON'
                self.doStartService(arg)
                self.doNotifyStarted(arg)
            elif event == 'stop' :
                self.doSetCallback(arg)
                self.NeedStop=True
            elif event == 'start' :
                self.doSetCallback(arg)
        #---INSTALLED?---
        elif self.state == 'INSTALLED?':
            if event == 'service-not-installed' :
                self.state = 'NOT_INSTALLED'
                self.doNotifyNotInstalled(arg)
            elif event == 'service-installed' and not self.NeedStop :
                self.state = 'DEPENDS?'
                self.doCheckDependencies(arg)
            elif event == 'service-installed' and self.NeedStop :
                self.state = 'INFLUENCE'
                self.NeedStop=False
                self.doStopDependentServices(arg)
            elif event == 'stop' :
                self.doSetCallback(arg)
                self.NeedStop=True
            elif event == 'start' :
                self.doSetCallback(arg)
        return None

    def doCheckInstall(self, arg):
        """
        Action method.
        """
        if self.is_installed():
            self.automat('service-installed')
        else:
            self.automat('service-not-installed')

    def doCheckDependencies(self, arg):
        """
        Action method.
        """
        result = []
        for depend_name in self.dependent_on():
            depend_service = services().get(depend_name, None)
            if depend_service is None:
                result.append((depend_name, 'not found'))
                return
            if depend_service.state != ['ON',]:
                result.append((depend_name, 'not started'))
                return
        if len(result) > 0: 
            self.automat('service-depends-broken', result)
        else:
            self.automat('service-depends-ok')

    def doStopDependentServices(self, arg):
        """
        Action method.
        """
        for svc in services().values():
            if self.name in svc.dependent_on():
                # lg.out(6, '%r sends "stop" to %r' % (self, svc))
                svc.automat('stop')

    def doStartService(self, arg):
        """
        Action method.
        """
        self.start()

    def doStopService(self, arg):
        """
        Action method.
        """
        self.stop()

    def doSetCallback(self, arg):
        """
        Action method.
        """
        if arg:
            self.result_callback = arg

    def doNotifyStarted(self, arg):
        """
        Action method.
        """
        if self.result_callback:
            self.result_callback((self.name, 'started'))
            self.result_callback = None

    def doNotifyStopped(self, arg):
        """
        Action method.
        """
        if self.result_callback:
            self.result_callback((self.name, 'stopped'))
            self.result_callback = None

    def doNotifyDependsBroken(self, arg):
        """
        Action method.
        """
        if self.result_callback:
            self.result_callback((self.name, 'broken'))
            self.result_callback = None

    def doNotifyNotInstalled(self, arg):
        """
        Action method.
        """
        if self.result_callback:
            self.result_callback((self.name, 'not installed'))
            self.result_callback = None
        
    #------------------------------------------------------------------------------ 

    def dependent_on(self):
        return []
    
    def start(self):
        raise RequireSubclass()
    
    def stop(self):
        raise RequireSubclass()

    
    
