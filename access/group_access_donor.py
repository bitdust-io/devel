#!/usr/bin/env python
# group_access_donor.py
#


"""
.. module:: group_access_donor
.. role:: red

BitDust group_access_donor() Automat

EVENTS:
    * :red:`audit-ok`
    * :red:`fail`
    * :red:`handshake-ok`
    * :red:`init`
    * :red:`private-key-shared`
    * :red:`timer-15sec`
"""


from automats import automat


_GroupAccessDonor = None


def A(event=None, *args, **kwargs):
    """
    Access method to interact with `group_access_donor()` machine.
    """
    global _GroupAccessDonor
    if event is None:
        return _GroupAccessDonor
    if _GroupAccessDonor is None:
        # TODO: set automat name and starting state here
        _GroupAccessDonor = GroupAccessDonor(name='group_access_donor', state='AT_STARTUP')
    if event is not None:
        _GroupAccessDonor.automat(event, *args, **kwargs)
    return _GroupAccessDonor


def Destroy():
    """
    Destroy `group_access_donor()` automat and remove its instance from memory.
    """
    global _GroupAccessDonor
    if _GroupAccessDonor is None:
        return
    _GroupAccessDonor.destroy()
    del _GroupAccessDonor
    _GroupAccessDonor = None


class GroupAccessDonor(automat.Automat):
    """
    This class implements all the functionality of ``group_access_donor()`` state machine.
    """

    timers = {
        'timer-15sec': (15.0, ['PRIV_KEY', 'AUDIT']),
        }

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `group_access_donor()` state machine.
        """
        super(GroupAccessDonor, self).__init__(
            name="group_access_donor",
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
        at creation phase of `group_access_donor()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `group_access_donor()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `group_access_donor()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'HANDSHAKE!'
                self.doInit(*args, **kwargs)
                self.doHandshake(*args, **kwargs)
        #---HANDSHAKE!---
        elif self.state == 'HANDSHAKE!':
            if event == 'handshake-ok':
                self.state = 'AUDIT'
                self.doAuditUserMasterKey(*args, **kwargs)
            elif event == 'fail':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---PRIV_KEY---
        elif self.state == 'PRIV_KEY':
            if event == 'fail' or event == 'timer-15sec':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'private-key-shared':
                self.state = 'SUCCESS'
                self.doReportDone(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---AUDIT---
        elif self.state == 'AUDIT':
            if event == 'fail' or event == 'timer-15sec':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'audit-ok':
                self.state = 'PRIV_KEY'
                self.doSendPrivKeyToUser(*args, **kwargs)
        #---SUCCESS---
        elif self.state == 'SUCCESS':
            pass


    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendPrivKeyToUser(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """

    def doHandshake(self, *args, **kwargs):
        """
        Action method.
        """

    def doAuditUserMasterKey(self, *args, **kwargs):
        """
        Action method.
        """

