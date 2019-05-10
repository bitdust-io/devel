#!/usr/bin/env python
# id_rotator.py
#


"""
.. module:: id_rotator
.. role:: red

BitDust id_rotator() Automat

EVENTS:
    * :red:`found-id-server`
    * :red:`id-server-failed`
    * :red:`my-id-exist`
    * :red:`my-id-sent`
    * :red:`my-id-updated`
    * :red:`no-id-servers-found`
    * :red:`ping-done`
    * :red:`run`
"""


from automats import automat


_IdRotator = None


def A(event=None, *args, **kwargs):
    """
    Access method to interact with `id_rotator()` machine.
    """
    global _IdRotator
    if event is None:
        return _IdRotator
    if _IdRotator is None:
        # TODO: set automat name and starting state here
        _IdRotator = IdRotator(name='id_rotator', state='AT_STARTUP')
    if event is not None:
        _IdRotator.automat(event, *args, **kwargs)
    return _IdRotator


def Destroy():
    """
    Destroy `id_rotator()` automat and remove its instance from memory.
    """
    global _IdRotator
    if _IdRotator is None:
        return
    _IdRotator.destroy()
    del _IdRotator
    _IdRotator = None


class IdRotator(automat.Automat):
    """
    This class implements all the functionality of ``id_rotator()`` state machine.
    """

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `id_rotator()` state machine.
        """
        super(IdRotator, self).__init__(
            name="id_rotator",
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `id_rotator()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `id_rotator()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `id_rotator()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'run':
                self.state = 'ID_SERVERS?'
                self.doPingMyIDServers(*args, **kwargs)
        #---ID_SERVERS?---
        elif self.state == 'ID_SERVERS?':
            if event == 'ping-done' and self.isAllReplied(*args, **kwargs):
                self.state = 'DONE'
                self.doReportDone(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ping-done' and not self.isAllReplied(*args, **kwargs):
                self.state = 'NEW_SOURCE!'
                self.doSelectNewIDServer(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---NEW_SOURCE!---
        elif self.state == 'NEW_SOURCE!':
            if event == 'found-id-server':
                self.state = 'MY_ID_ROTATE'
                self.doRebuildMyIdentity(*args, **kwargs)
            elif event == 'no-id-servers-found':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---MY_ID_ROTATE---
        elif self.state == 'MY_ID_ROTATE':
            if event == 'my-id-updated':
                self.state = 'SEND_ID'
                self.doSendMyIdentity(*args, **kwargs)
        #---SEND_ID---
        elif self.state == 'SEND_ID':
            if event == 'id-server-failed':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'my-id-sent':
                self.state = 'REQUEST_ID'
                self.doRequestMyIdentity(*args, **kwargs)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---REQUEST_ID---
        elif self.state == 'REQUEST_ID':
            if event == 'my-id-exist' and self.isMyIdentityValid(*args, **kwargs):
                self.state = 'DONE'
                self.doSaveMyIdentity(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'id-server-failed' or ( event == 'my-id-exist' and not self.isMyIdentityValid(*args, **kwargs) ):
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)


    def isMyIdentityValid(self, *args, **kwargs):
        """
        Condition method.
        """

    def isAllReplied(self, *args, **kwargs):
        """
        Condition method.
        """

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """

    def doRequestMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

    def doRebuildMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """

    def doSelectNewIDServer(self, *args, **kwargs):
        """
        Action method.
        """

    def doSaveMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """

    def doPingMyIDServers(self, *args, **kwargs):
        """
        Action method.
        """

