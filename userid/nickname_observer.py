

"""
.. module:: nickname_observer
.. role:: red

BitPie.NET nickname_observer() Automat

.. raw:: html

    <a href="nickname_observer.png" target="_blank">
    <img src="nickname_observer.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`key-exist`
    * :red:`key-not-exist`
    * :red:`observe-many`
    * :red:`observe-one`
    * :red:`stop`
"""

import automat

_NicknameObserver = None

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _NicknameObserver
    if _NicknameObserver is None:
        # set automat name and starting state here
        _NicknameObserver = NicknameObserver('nickname_observer', 'AT_STARTUP')
    if event is not None:
        _NicknameObserver.automat(event, arg)
    return _NicknameObserver


class NicknameObserver(automat.Automat):
    """
    This class implements all the functionality of the ``nickname_observer()`` state machine.
    """

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
            if event == 'observe-many' :
                self.state = 'DHT_LOOP'
                self.doInitLoop(arg)
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'observe-one' :
                self.state = 'DHT_FIND'
                self.doInitSearch(arg)
                self.doMakeKey(arg)
                self.doDHTReadKey(arg)
        #---DHT_LOOP---
        elif self.state == 'DHT_LOOP':
            if event == 'stop' :
                self.state = 'STOPPED'
                self.doDestroyMe(arg)
            elif event == 'key-not-exist' and self.isMoreNeeded(arg) :
                self.doReportNicknameNotExist(arg)
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'key-exist' :
                self.doReportNicknameExist(arg)
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'key-not-exist' and not self.isMoreNeeded(arg) :
                self.state = 'FINISHED'
                self.doReportFinished(arg)
                self.doDestroyMe(arg)
        #---FINISHED---
        elif self.state == 'FINISHED':
            pass
        #---DHT_FIND---
        elif self.state == 'DHT_FIND':
            if event == 'key-exist' :
                self.state = 'FOUND'
                self.doReportNicknameExist(arg)
                self.doDestroyMe(arg)
            elif event == 'key-not-exist' and not self.isMoreNeeded(arg) :
                self.state = 'FINISHED'
                self.doReportFinished(arg)
                self.doDestroyMe(arg)
            elif event == 'key-not-exist' and self.isMoreNeeded(arg) :
                self.doReportNicknameNotExist(arg)
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
        #---FOUND---
        elif self.state == 'FOUND':
            pass
        #---STOPPED---
        elif self.state == 'STOPPED':
            pass


    def isMoreNeeded(self, arg):
        """
        Condition method.
        """

    def doMakeKey(self, arg):
        """
        Action method.
        """

    def doInitSearch(self, arg):
        """
        Action method.
        """

    def doReportFinished(self, arg):
        """
        Action method.
        """

    def doReportNicknameExist(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        automat.objects().pop(self.index)
        global _NicknameObserver
        del _NicknameObserver
        _NicknameObserver = None

    def doInitLoop(self, arg):
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

    def doReportNicknameNotExist(self, arg):
        """
        Action method.
        """



def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

if __name__ == "__main__":
    main()

