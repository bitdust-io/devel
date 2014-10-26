

"""
.. module:: local_service
.. role:: red

BitPie.NET local_service() Automat

.. raw:: html

    <a href="local_service.png" target="_blank">
    <img src="local_service.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`service-depend-off`
    * :red:`service-failed`
    * :red:`service-not-installed`
    * :red:`service-started`
    * :red:`service-stopped`
    * :red:`services-stopped`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------ 

from twisted.internet.defer import Deferred

from logs import lg

from lib import automat

from driver import services, RequireSubclass, ServiceAlreadyExist

#------------------------------------------------------------------------------ 

class LocalService(automat.Automat):
    """
    This class implements all the functionality of the ``local_service()`` state machine.
    """
    
    # fast = True
    
    service_name = ''

    def __init__(self):
        if self.service_name == '':
            raise RequireSubclass()
        if self.service_name in services().keys():
            raise ServiceAlreadyExist(self.service_name)
        automat.Automat.__init__(self, self.service_name+'_service', 'OFF', 18)

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
            if event == 'stop' :
                self.doSetCallback(arg)
                self.doNotifyStopped(arg)
            elif event == 'start' :
                self.state = 'STARTING'
                self.NeedStart=False
                self.NeedStop=False
                self.doSetCallback(arg)
                self.doStartService(arg)
        #---NOT_INSTALLED---
        elif self.state == 'NOT_INSTALLED':
            if event == 'stop' :
                self.doSetCallback(arg)
                self.doNotifyNotInstalled(arg)
            elif event == 'start' :
                self.state = 'STARTING'
                self.doSetCallback(arg)
                self.doStartService(arg)
        #---INFLUENCE---
        elif self.state == 'INFLUENCE':
            if event == 'start' :
                self.doSetCallback(arg)
                self.NeedStart=True
            elif event == 'stop' :
                self.doSetCallback(arg)
            elif event == 'services-stopped' and self.NeedStart :
                self.state = 'STARTING'
                self.NeedStart=False
                self.doStopService(arg)
                self.doNotifyStopped(arg)
                self.doStartService(arg)
            elif event == 'services-stopped' and not self.NeedStart :
                self.state = 'STOPPING'
                self.doStopService(arg)
        #---STARTING---
        elif self.state == 'STARTING':
            if event == 'service-not-installed' :
                self.state = 'NOT_INSTALLED'
                self.doNotifyNotInstalled(arg)
            elif event == 'service-depend-off' :
                self.state = 'DEPENDS_OFF'
                self.doNotifyDependsOff(arg)
            elif event == 'service-started' and self.NeedStop :
                self.state = 'INFLUENCE'
                self.NeedStop=False
                self.doStopDependentServices(arg)
            elif event == 'stop' :
                self.doSetCallback(arg)
                self.NeedStop=True
            elif event == 'service-failed' :
                self.state = 'OFF'
                self.doNotifyFailed(arg)
            elif event == 'start' :
                self.doSetCallback(arg)
            elif event == 'service-started' and not self.NeedStop :
                self.state = 'ON'
                self.doNotifyStarted(arg)
        #---DEPENDS_OFF---
        elif self.state == 'DEPENDS_OFF':
            if event == 'start' :
                self.state = 'STARTING'
                self.doSetCallback(arg)
                self.doStartService(arg)
            elif event == 'stop' :
                self.doSetCallback(arg)
                self.doNotifyDependsOff(arg)
        #---STOPPING---
        elif self.state == 'STOPPING':
            if event == 'service-stopped' :
                self.state = 'OFF'
                self.doNotifyStopped(arg)
            elif event == 'start' :
                self.doSetCallback(arg)
                self.NeedStart=True
        return None

    def doStopDependentServices(self, arg):
        """
        Action method.
        """
        for svc in services().values():
            if self.service_name in svc.dependent_on():
                # lg.out(6, '%r sends "stop" to %r' % (self, svc))
                svc.automat('stop')

    def doStartService(self, arg):
        """
        Action method.
        """
        if not self.is_installed():
            self.automat('service-not-installed')
            return
        depends_results = []
        for depend_name in self.dependent_on():
            depend_service = services().get(depend_name, None)
            if depend_service is None:
                depends_results.append((depend_name, 'not found'))
                continue
            if depend_service.state != 'ON':
                depends_results.append((depend_name, 'not started'))
                continue
        if len(depends_results) > 0: 
            self.automat('service-depend-off', depends_results)
            return
        lg.out(4, 'starting service [%s]' % self.service_name)
        try:
            result = self.start()
        except:
            lg.exc()
            self.automat('service-failed', 'exception when starting')
            return
        if isinstance(result, Deferred):
            result.addCallback(lambda x: self.automat('service-started'))
            result.addErrback(lambda x: self.automat('service-failed', x))
            return
        if result:
            self.automat('service-started')
        else:
            self.automat('service-failed', 'result is %r' % result)

    def doStopService(self, arg):
        """
        Action method.
        """
        lg.out(4, '    stopping service [%s]' % self.service_name)
        try:
            result = self.stop()
        except:
            lg.exc()
            self.automat('service-stopped', 'exception when stopping')
            return
        if isinstance(result, Deferred):
            result.addCallback(lambda x: self.automat('service-stopped'))
            result.addErrback(lambda x: self.automat('service-stopped', x))
            return
        self.automat('service-stopped', result)

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
            self.result_callback(self.service_name, 'started')
            self.result_callback = None

    def doNotifyStopped(self, arg):
        """
        Action method.
        """
        if self.result_callback:
            self.result_callback(self.service_name, 'stopped')
            self.result_callback = None

    def doNotifyNotInstalled(self, arg):
        """
        Action method.
        """
        if self.result_callback:
            self.result_callback(self.service_name, 'not installed')
            self.result_callback = None

    def doNotifyFailed(self, arg):
        """
        Action method.
        """
        if self.result_callback:
            self.result_callback(self.service_name, 'broken')
            self.result_callback = None

    def doNotifyDependsOff(self, arg):
        """
        Action method.
        """
        
    #------------------------------------------------------------------------------ 

    def dependent_on(self):
        return []
    
    def is_installed(self):
        return True
    
    def is_enabled(self):
        return True

    def start(self):
        raise RequireSubclass()
    
    def stop(self):
        raise RequireSubclass()

    
        
