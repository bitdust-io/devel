

"""
.. module:: accountant_node
.. role:: red

BitDust accountant_node() Automat

EVENTS:
    * :red:`accountant-connected`
    * :red:`all-coins-received`
    * :red:`coin-broadcasted`
    * :red:`coin-not-valid`
    * :red:`coin-received`
    * :red:`coin-valid`
    * :red:`connection-lost`
    * :red:`download-failed`
    * :red:`init`
    * :red:`lookup-failed`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-2min`
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------ 

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat

#------------------------------------------------------------------------------ 

_AccountantNode = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _AccountantNode
    if event is None and arg is None:
        return _AccountantNode
    if _AccountantNode is None:
        # set automat name and starting state here
        _AccountantNode = AccountantNode('accountant_node', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _AccountantNode.automat(event, arg)
    return _AccountantNode

#------------------------------------------------------------------------------ 

class AccountantNode(automat.Automat):
    """
    This class implements all the functionality of the ``accountant_node()`` state machine.
    """
    timers = {
        'timer-2min': (120, ['ACCOUNTANTS?']),
        }
    
    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of accountant_node() machine.
        """
        self.connected_accountants = []
        self.max_accountants_connected = 1 # TODO: read from settings
        self.lookup_task = None
        self.download_coins_task = None

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when accountant_node() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the accountant_node()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        if self.state == 'READY':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'coin-received':
                self.state = 'VALID_COIN?'
                self.doVerifyCoin(arg)
            elif event == 'connection-lost' or event == 'stop':
                self.state = 'OFFLINE'
            elif event == 'accountant-connected':
                self.doAddAccountant(arg)
        elif self.state == 'READ_COINS':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopDownloadCoins(arg)
                self.doDestroyMe(arg)
            elif event == 'stop' or event == 'download-failed':
                self.state = 'OFFLINE'
                self.doStopDownloadCoins(arg)
            elif event == 'all-coins-received':
                self.state = 'READY'
                self.doCheckNewCoins(arg)
            elif event == 'accountant-connected':
                self.doAddAccountant(arg)
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(arg)
        elif self.state == 'VALID_COIN?':
            if event == 'coin-valid':
                self.state = 'WRITE_COIN!'
                self.doBroadcastCoin(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'OFFLINE'
            elif event == 'coin-not-valid':
                self.state = 'READY'
                self.doCheckNewCoins(arg)
            elif event == 'accountant-connected':
                self.doAddAccountant(arg)
        elif self.state == 'WRITE_COIN!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'OFFLINE'
            elif event == 'coin-broadcasted':
                self.state = 'READY'
                self.doCheckNewCoins(arg)
            elif event == 'accountant-connected':
                self.doAddAccountant(arg)
        elif self.state == 'OFFLINE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start':
                self.state = 'ACCOUNTANTS?'
                self.doLookupAccountants(arg)
        elif self.state == 'CLOSED':
            pass
        elif self.state == 'ACCOUNTANTS?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'accountant-connected' and self.isMoreNeeded(arg):
                self.doAddAccountant(arg)
                self.doLookupAccountants(arg)
            elif ( event == 'lookup-failed' and not self.isAnyAccountants(arg) ) or event == 'timer-2min':
                self.state = 'OFFLINE'
            elif event == 'accountant-connected' and not self.isMoreNeeded(arg):
                self.state = 'READ_COINS'
                self.doDownloadCoins(arg)
            elif event == 'lookup-failed' and self.isAnyAccountants(arg):
                self.doLookupAccountants(arg)
        return None

    def isAnyAccountants(self, arg):
        """
        Condition method.
        """
        return len(self.connected_accountants) > 0

    def isMoreNeeded(self, arg):
        """
        Condition method.
        """
        return len(self.connected_accountants) < self.max_accountants_connected

    def doInit(self, arg):
        """
        Action method.
        """

    def doLookupAccountants(self, arg):
        """
        Action method.
        """
        from coins import accountants_finder
        accountants_finder.A('start', (self.automat, 'join'))

    def doAddAccountant(self, arg):
        """
        Action method.
        """
        if arg in self.connected_accountants:
            lg.warn('%s already connected, skip' % arg)
            return
        self.connected_accountants.append(arg)

    def doDownloadCoins(self, arg):
        """
        Action method.
        """
        self.download_coins_task = None
        self._download_coins()

    def doStopDownloadCoins(self, arg):
        """
        Action method.
        """

    def doVerifyCoin(self, arg):
        """
        Action method.
        """

    def doBroadcastCoin(self, arg):
        """
        Action method.
        """

    def doCheckNewCoins(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        automat.objects().pop(self.index)
        global _AccountantNode
        del _AccountantNode
        _AccountantNode = None
    
    #------------------------------------------------------------------------------ 

    def _download_coins(self):
        self.download_coins_task = Deferred()
        
