

"""
.. module:: switchable_service
.. role:: red

BitPie.NET switchable_service() Automat

.. raw:: html

    <a href="switchable_service.png" target="_blank">
    <img src="switchable_service.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`init`
    * :red:`service-depends-broken`
    * :red:`service-not-installed`
    * :red:`service-started`
    * :red:`service-stopped`
    * :red:`start`
    * :red:`stop`
"""

from logs import lg

from lib import automat

#------------------------------------------------------------------------------ 

_ServicesDict = {}

#------------------------------------------------------------------------------ 

def services():
    """
    """
    global _ServicesDict
    return _ServicesDict

#------------------------------------------------------------------------------ 

class ServiceAlreadyExist(Exception):
    pass

#------------------------------------------------------------------------------ 

def init_all():
    """
    """

#------------------------------------------------------------------------------ 

class SwitchableService(automat.Automat):
    """
    This class implements all the functionality of the ``switchable_service()`` state machine.
    """

    def __init__(self, name):
        if name in services().keys():
            raise ServiceAlreadyExist(name)
        services()[name] = self
        self.name = name
        automat.Automat.__init__(self, self.name, 'AT_STARTUP', 10)
        lg.out(10, 'SwitchableService.__init__ %s' % self.name)

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to to catch the moment when automat's state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        Method to to catch the moment when some event was fired but automat's state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://code.google.com/p/visio2python/>`_ tool.
        """
        #---UP---
        if self.state == 'UP':
            if event == 'service-depends-broken' :
                self.state = 'DEPENDS_BROKEN'
                self.doNotifyDependsBroken(arg)
            elif event == 'service-not-installed' :
                self.state = 'NOT_INSTALLED'
                self.doNotifyNotInstalled(arg)
            elif event == 'stop' :
                self.NeedStop=True
            elif event == 'service-started' and self.NeedStop :
                self.state = 'DOWN'
                self.NeedStop=False
                self.doSetDown(arg)
            elif event == 'service-started' and not self.NeedStop :
                self.state = 'ON'
                self.NeedStop=False
                self.doNotifyStarted(arg)
        #---ON---
        elif self.state == 'ON':
            if event == 'stop' :
                self.state = 'DOWN'
                self.NeedStart=False
                self.doSetDown(arg)
        #---OFF---
        elif self.state == 'OFF':
            if event == 'start' :
                self.state = 'UP'
                self.NeedStop=False
                self.doSetUp(arg)
        #---DOWN---
        elif self.state == 'DOWN':
            if event == 'service-stopped' and self.NeedStart :
                self.state = 'UP'
                self.NeedStart=False
                self.doSetUp(arg)
            elif event == 'service-stopped' and not self.NeedStart :
                self.state = 'OFF'
                self.NeedStart=False
                self.doNotifyStopped(arg)
            elif event == 'start' :
                self.NeedStart=True
        #---NOT_INSTALLED---
        elif self.state == 'NOT_INSTALLED':
            if event == 'start' :
                self.state = 'UP'
                self.doSetUp(arg)
        #---DEPENDS_BROKEN---
        elif self.state == 'DEPENDS_BROKEN':
            if event == 'start' :
                self.state = 'UP'
                self.doSetUp(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'OFF'
                self.doInit(arg)


    def doNotifyStarted(self, arg):
        """
        Action method.
        """

    def doNotifyStopped(self, arg):
        """
        Action method.
        """

    def doNotifyDependsBroken(self, arg):
        """
        Action method.
        """

    def doSetUp(self, arg):
        """
        Action method.
        """

    def doNotifyNotInstalled(self, arg):
        """
        Action method.
        """

    def doInit(self, arg):
        """
        Action method.
        """

    def doSetDown(self, arg):
        """
        Action method.
        """
    
    #------------------------------------------------------------------------------ 
    
    def dependent_on(self):
        return []

    
    
