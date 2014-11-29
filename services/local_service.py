#!/usr/bin/python
#local_service.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: local_service
.. role:: red

BitPie.NET local_service() Automat

.. raw:: html

    <a href="local_service.png" target="_blank">
    <img src="local_service.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`depend-service-stopped`
    * :red:`service-depend-off`
    * :red:`service-failed`
    * :red:`service-not-installed`
    * :red:`service-started`
    * :red:`service-stopped`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
"""

from twisted.internet.defer import Deferred, DeferredList

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat

from main import settings

from driver import services
from driver import on_service_callback
from driver import RequireSubclass
from driver import ServiceAlreadyExist

#------------------------------------------------------------------------------ 

class LocalService(automat.Automat):
    """
    This class implements all the functionality of the ``local_service()`` state machine.
    """
    
    service_name = ''
    config_path = ''

    def __init__(self):
        if self.service_name == '':
            raise RequireSubclass()
        if self.service_name in services().keys():
            raise ServiceAlreadyExist(self.service_name)
        self.result_deferred = None
        automat.Automat.__init__(self, self.service_name, 'OFF', 10, True)

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when automat's state were changed.
        """
        if not settings.NewWebGUI():
            from web import webcontrol
            webcontrol.OnServiceStateChanged(self.service_name)

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired but automat's state was not changed.
        """

    def A(self, event, arg):
        #---ON---
        if self.state == 'ON':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doStopService(arg)
                self.doDestroyMe(arg)
            elif event == 'stop' :
                self.state = 'INFLUENCE'
                self.doSetCallback(arg)
                self.doStopDependentServices(arg)
        #---OFF---
        elif self.state == 'OFF':
            if event == 'stop' :
                self.doSetCallback(arg)
                self.doNotifyStopped(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
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
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---INFLUENCE---
        elif self.state == 'INFLUENCE':
            if event == 'start' :
                self.doSetCallback(arg)
                self.NeedStart=True
            elif event == 'stop' :
                self.doSetCallback(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doStopService(arg)
                self.doDestroyMe(arg)
            elif event == 'depend-service-stopped' and self.isAllDependsStopped(arg) and self.NeedStart :
                self.state = 'STARTING'
                self.NeedStart=False
                self.doStopService(arg)
                self.doNotifyStopped(arg)
                self.doStartService(arg)
            elif event == 'depend-service-stopped' and self.isAllDependsStopped(arg) and not self.NeedStart :
                self.state = 'STOPPING'
                self.doStopService(arg)
        #---STARTING---
        elif self.state == 'STARTING':
            if event == 'stop' :
                self.doSetCallback(arg)
                self.NeedStop=True
            elif event == 'start' :
                self.doSetCallback(arg)
            elif event == 'service-started' and self.NeedStop :
                self.state = 'INFLUENCE'
                self.NeedStop=False
                self.doStopDependentServices(arg)
            elif event == 'service-failed' :
                self.state = 'OFF'
                self.doNotifyFailed(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doStopService(arg)
                self.doDestroyMe(arg)
            elif event == 'service-not-installed' :
                self.state = 'NOT_INSTALLED'
                self.doNotifyNotInstalled(arg)
            elif event == 'service-depend-off' :
                self.state = 'DEPENDS_OFF'
                self.doNotifyDependsOff(arg)
            elif event == 'service-started' and not self.NeedStop :
                self.state = 'ON'
                self.doNotifyStarted(arg)
        #---DEPENDS_OFF---
        elif self.state == 'DEPENDS_OFF':
            if event == 'stop' :
                self.doSetCallback(arg)
                self.doNotifyDependsOff(arg)
            elif event == 'start' :
                self.state = 'STARTING'
                self.doSetCallback(arg)
                self.doStartService(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---STOPPING---
        elif self.state == 'STOPPING':
            if event == 'start' :
                self.doSetCallback(arg)
                self.NeedStart=True
            elif event == 'service-stopped' :
                self.state = 'OFF'
                self.doNotifyStopped(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isAllDependsStopped(self, arg):
        """
        Condition method.
        """
        for svc in services().values():
            if self.service_name in svc.dependent_on():
                if  svc.state != 'OFF' and \
                    svc.state != 'DEPENDS_OFF' and \
                    svc.state != 'NOT_INSTALLED':
                    return False
        return True
#        for depend_name in self.dependent_on():
#            depend_svc = services().get(depend_name, None)
#            if depend_svc is None:
#                lg.warn('%s not exist' % depend_name)
#                continue
#            if  depend_svc.state != 'OFF' and \
#                depend_svc.state != 'DEPENDS_OFF' and \
#                depend_svc.state != 'NOT_INSTALLED':
#                return False
#        return True

    def doStartService(self, arg):
        """
        Action method.
        """
        if not self.installed():
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
        lg.out(2, '[%s] STARTING' % self.service_name)
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
        lg.out(2, '[%s] STOPPING' % self.service_name)
        try:
            result = self.stop()
        except:
            lg.exc()
            self.automat('service-stopped', 'exception during stopping [%s]' % self.service_name)
            return
        if isinstance(result, Deferred):
            result.addBoth(lambda x: self.automat('service-stopped', x))
        else:
            self.automat('service-stopped', result)

    def doSetCallback(self, arg):
        """
        Action method.
        """
        if arg:
            if self.result_deferred:
                self.result_deferred.addCallback(arg.callback)
            else:
                self.result_deferred = arg

    def doStopDependentServices(self, arg):
        """
        Action method.
        """
        # dl = []
        count = 0
        for svc in services().values():
            if self.service_name in svc.dependent_on():
                lg.out(6, '%r sends "stop" to %r' % (self, svc))
                # d = Deferred()
                svc.automat('stop') # , d)
                count += 1
                # dl.append(d)
        # DeferredList(dl).addBoth(lambda x: self.automat('services-stopped'))
        # self.automat('services-stopped')
        if count == 0:
            self.automat('depend-service-stopped')
        
    def doNotifyStarted(self, arg):
        """
        Action method.
        """
        if self.result_deferred:
            self.result_deferred.callback('started')
            self.result_deferred = None
        on_service_callback('started', self.service_name)

    def doNotifyStopped(self, arg):
        """
        Action method.
        """
        if self.result_deferred:
            self.result_deferred.callback('stopped')
            self.result_deferred = None
        on_service_callback('stopped', self.service_name)

    def doNotifyNotInstalled(self, arg):
        """
        Action method.
        """
        if self.result_deferred:
            self.result_deferred.callback('not_installed')
            self.result_deferred = None
        on_service_callback('not_installed', self.service_name)

    def doNotifyFailed(self, arg):
        """
        Action method.
        """
        if self.result_deferred:
            self.result_deferred.callback('failed')
            self.result_deferred = None
        on_service_callback('failed', self.service_name)

    def doNotifyDependsOff(self, arg):
        """
        Action method.
        """
        if self.result_deferred:
            self.result_deferred.callback('depends_off')
            self.result_deferred = None
        on_service_callback('depends_off', self.service_name)

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        self.result_deferred = None  
        self.destroy()
            
    #------------------------------------------------------------------------------ 

    def dependent_on(self):
        return []
    
    def installed(self):
        return True
    
    def enabled(self):
        from main import config
        return config.conf().getBool(self.config_path)

    def start(self):
        raise RequireSubclass()
    
    def stop(self):
        raise RequireSubclass()

    
        
