

"""
.. module:: nickname_holder
.. role:: red

BitPie.NET nickname_holder() Automat

.. raw:: html

    <a href="nickname_holder.png" target="_blank">
    <img src="nickname_holder.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`init`
    * :red:`key-exist`
    * :red:`key-not-exist`
    * :red:`timer-5min`
    * :red:`write-failed`
    * :red:`write-success`
"""

import automat

_NicknameHolder = None

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _NicknameHolder
    if _NicknameHolder is None:
        # set automat name and starting state here
        _NicknameHolder = NicknameHolder('nickname_holder', 'AT_STARTUP')
    if event is not None:
        _NicknameHolder.automat(event, arg)
    return _NicknameHolder


class NicknameHolder(automat.Automat):
    """
    This class implements all the functionality of the ``nickname_holder()`` state machine.
    """

    timers = {
        'timer-5min': (300, ['READY']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """

    def state_changed(self, oldstate, newstate):
        """
        Method to to catch the moment when automat's state were changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://code.google.com/p/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'DHT_READ'
                self.doInit(arg)
                self.doMakeKey(arg)
                self.doDHTReadKey(arg)
        #---READY---
        elif self.state == 'READY':
            if event == 'timer-5min' :
                self.state = 'DHT_READ'
                self.doDHTReadKey(arg)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'key-exist' and self.isMyOwnKey(arg) :
                self.state = 'READY'
                self.doReportNicknameOwn(arg)
            elif event == 'key-not-exist' :
                self.state = 'DHT_WRITE'
                self.Attempts=0
                self.doDHTWriteKey(arg)
            elif event == 'key-exist' and not self.isMyOwnKey(arg) :
                self.doReportNicknameExist(arg)
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'write-failed' and self.Attempts>5 :
                self.state = 'READY'
                self.Attempts=0
                self.doReportNicknameFailed(arg)
            elif event == 'write-failed' and self.Attempts<=5 :
                self.state = 'DHT_READ'
                self.Attempts+=1
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'write-success' :
                self.state = 'READY'
                self.Attempts=0
                self.doReportNicknameRegistered(arg)


    def isMyOwnKey(self, arg):
        """
        Condition method.
        """

    def doMakeKey(self, arg):
        """
        Action method.
        """

    def doReportNicknameFailed(self, arg):
        """
        Action method.
        """

    def doReportNicknameOwn(self, arg):
        """
        Action method.
        """

    def doReportNicknameRegistered(self, arg):
        """
        Action method.
        """

    def doDHTWriteKey(self, arg):
        """
        Action method.
        """

    def doReportNicknameExist(self, arg):
        """
        Action method.
        """

    def doNextKey(self, arg):
        """
        Action method.
        """

    def doDHTReadKey(self, arg):
        """
        Action method.
        """

    def doInit(self, arg):
        """
        Action method.
        """



def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

if __name__ == "__main__":
    main()

