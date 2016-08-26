

"""
.. module:: broadcast_listener
.. role:: red

BitDust broadcast_listener() Automat

EVENTS:
    * :red:`ack-received`
    * :red:`broadcast-message`
    * :red:`connect`
    * :red:`disconnect`
    * :red:`found-broadcaster`
    * :red:`init`
    * :red:`listening-options-changed`
    * :red:`new-message`
    * :red:`shutdown`
"""


import automat


class BroadcastListener(automat.Automat):
    """
    This class implements all the functionality of the ``broadcast_listener()`` state machine.
    """

    def __init__(self, state):
        """
        Create broadcast_listener() state machine.
        """
        super(BroadcastListener, self).__init__("broadcast_listener", state)

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when broadcast_listener() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the broadcast_listener()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(arg)
        elif self.state == 'BROADCASTER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopBroadcasterLookup(arg)
                self.doClose(arg)
            elif event == 'disconnect':
                self.state = 'OFFLINE'
                self.doStopBroadcasterLookup(arg)
            elif event == 'found-broadcaster':
                self.state = 'SERVICE?'
                self.doRequestService(arg)
        elif self.state == 'SERVICE?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doClose(arg)
            elif event == 'disconnect':
                self.state = 'OFFLINE'
                self.doCancelService(arg)
                self.doRemoveBroadcaster(arg)
            elif event == 'listening-options-changed':
                self.doSendListeningOptions(arg)
            elif event == 'ack-received' and self.isServiceAccepted(arg):
                self.state = 'LISTENING'
                self.doSetBroadcaster(arg)
                self.doNotifyListeningStarted(arg)
            elif event == 'ack-received' and not self.isServiceAccepted(arg):
                self.state = 'BROADCASTER?'
                self.doSearchBroadcaster(arg)
        elif self.state == 'LISTENING':
            if event == 'disconnect':
                self.state = 'OFFLINE'
                self.doCancelService(arg)
                self.doNotifyListeningStopped(arg)
                self.doRemoveBroadcaster(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doNotifyListeningStopped(arg)
                self.doRemoveBroadcaster(arg)
                self.doClose(arg)
            elif event == 'listening-options-changed':
                self.doSendListeningOptions(arg)
            elif event == 'new-message':
                self.doBroadcastMessage(arg)
            elif event == 'broadcast-message':
                self.doNotifyInputMessage(arg)
        elif self.state == 'OFFLINE':
            if event == 'connect':
                self.state = 'BROADCASTER?'
                self.doSearchBroadcaster(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doClose(arg)
        elif self.state == 'CLOSED':
            pass


    def isServiceAccepted(self, arg):
        """
        Condition method.
        """

    def doSearchBroadcaster(self, arg):
        """
        Action method.
        """

    def doStopBroadcasterLookup(self, arg):
        """
        Action method.
        """

    def doBroadcastMessage(self, arg):
        """
        Action method.
        """

    def doClose(self, arg):
        """
        Action method.
        """

    def doCancelService(self, arg):
        """
        Action method.
        """

    def doRemoveBroadcaster(self, arg):
        """
        Action method.
        """

    def doRequestService(self, arg):
        """
        Action method.
        """

    def doNotifyListeningStarted(self, arg):
        """
        Action method.
        """

    def doSetBroadcaster(self, arg):
        """
        Action method.
        """

    def doNotifyInputMessage(self, arg):
        """
        Action method.
        """

    def doInit(self, arg):
        """
        Action method.
        """

    def doSendListeningOptions(self, arg):
        """
        Action method.
        """

    def doNotifyListeningStopped(self, arg):
        """
        Action method.
        """

