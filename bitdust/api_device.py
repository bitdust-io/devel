#!/usr/bin/env python
# api_device.py
#
"""
.. module:: api_device
.. role:: red

BitDust api_device() Automat

EVENTS:
    * :red:`api-message`
    * :red:`auth-error`
    * :red:`client-code-input-received`
    * :red:`client-pub-key-received`
    * :red:`start`
    * :red:`stop`
    * :red:`valid-server-code-received`
"""

from automats import automat

_ApiDevice = None


def A(event=None, *args, **kwargs):
    """
    Access method to interact with `api_device()` machine.
    """
    global _ApiDevice
    if event is None:
        return _ApiDevice
    if _ApiDevice is None:
        # TODO: set automat name and starting state here
        _ApiDevice = ApiDevice(name='api_device', state='AT_STARTUP')
    if event is not None:
        _ApiDevice.automat(event, *args, **kwargs)
    return _ApiDevice


def Destroy():
    """
    Destroy `api_device()` automat and remove its instance from memory.
    """
    global _ApiDevice
    if _ApiDevice is None:
        return
    _ApiDevice.destroy()
    del _ApiDevice
    _ApiDevice = None


class ApiDevice(automat.Automat):

    """
    This class implements all the functionality of ``api_device()`` state machine.
    """

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `api_device()` state machine.
        """
        super(ApiDevice, self).__init__(name='api_device', state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `api_device()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `api_device()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `api_device()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://github.com/vesellov/visio2python>`_ tool.
        """
        #---CLIENT_CODE?---
        if self.state == 'CLIENT_CODE?':
            if event == 'client-code-input-received':
                self.state = 'READY'
                self.doSendClientCode(*args, **kwargs)
                self.doSaveAuthToken(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'CLIENT_PUB?'
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'start' and not self.isAuthenticated(*args, **kwargs):
                self.state = 'CLIENT_PUB?'
                self.doInit(*args, **kwargs)
            elif event == 'start' and self.isAuthenticated(*args, **kwargs):
                self.state = 'READY'
                self.doInit(*args, **kwargs)
        #---CLIENT_PUB?---
        elif self.state == 'CLIENT_PUB?':
            if event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---SERVER_CODE?---
        elif self.state == 'SERVER_CODE?':
            if event == 'client-pub-key-received':
                self.state = 'CLIENT_PUB?'
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'valid-server-code-received':
                self.state = 'CLIENT_CODE?'
                self.doWaitClientCodeInput(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---READY---
        elif self.state == 'READY':
            if event == 'client-pub-key-received':
                self.state = 'CLIENT_PUB?'
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'api-message':
                self.doProcess(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'auth-error':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(*args, **kwargs)
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass

    def isAuthenticated(self, *args, **kwargs):
        """
        Condition method.
        """

    def doGenerateServerCode(self, *args, **kwargs):
        """
        Action method.
        """

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

    def doProcess(self, *args, **kwargs):
        """
        Action method.
        """

    def doGenerateAuthToken(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendServerPubKey(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendClientCode(self, *args, **kwargs):
        """
        Action method.
        """

    def doWaitClientCodeInput(self, *args, **kwargs):
        """
        Action method.
        """

    def doSaveAuthToken(self, *args, **kwargs):
        """
        Action method.
        """

    def doRemoveAuthToken(self, *args, **kwargs):
        """
        Action method.
        """

    def doStopListener(self, *args, **kwargs):
        """
        Action method.
        """
