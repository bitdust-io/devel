

"""
.. module:: accountant_node
.. role:: red

BitDust accountant_node() Automat

EVENTS:
    * :red:`accountants-connected`
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
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------ 

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat

from p2p import lookup
from p2p import p2p_service
from p2p import commands

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

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of accountant_node() machine.
        """
        self.connected_accountants = []
        self.max_accountants_connected = 3 # TODO: read from settings
        self.accountatnts_lookup_task = None
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
        elif self.state == 'WRITE_COIN!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'OFFLINE'
            elif event == 'coin-broadcasted':
                self.state = 'READY'
                self.doCheckNewCoins(arg)
        elif self.state == 'OFFLINE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start':
                self.state = 'ACCOUNTANTS?'
                self.doLookupAccountatns(arg)
        elif self.state == 'CLOSED':
            pass
        elif self.state == 'ACCOUNTANTS?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopLookupAccountants(arg)
                self.doDestroyMe(arg)
            elif event == 'accountants-connected':
                self.state = 'READ_COINS'
                self.doDownloadCoins(arg)
            elif event == 'lookup-failed':
                self.state = 'OFFLINE'
        return None

    def doInit(self, arg):
        """
        Action method.
        """

    def doLookupAccountatns(self, arg):
        """
        Action method.
        """
        self.connected_accountants = []
        self.accountatnts_lookup_task = None
        self._lookup_accountants()

    def doStopLookupAccountants(self, arg):
        """
        Action method.
        """
        self.accountatnts_lookup_task.cancel()

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
        global _Accountant
        del _Accountant
        _Accountant = None

    #------------------------------------------------------------------------------ 
    
    def join_accountant(self, idurl):
        self.connected_accountants.append(idurl)

    #------------------------------------------------------------------------------ 
    
    def _lookup_accountants(self):
        if self.accountatnts_lookup_task and self.accountatnts_lookup_task.cancelled:
            self.accountatnts_lookup_task = None
            return
        d = lookup.start(count=1)
        d.addCallback(self._node_observed)
        d.addErrback(lambda err: self.automat('lookup-failed'))
        self.accountatnts_lookup_task = d

    def _node_observed(self, idurls):
        for idurl in idurls:
            service_info = 'service_accountant join'
            p2p_service.SendRequestService(
                idurl, service_info, callbacks={
                    commands.Ack():  self._node_acked,
                    commands.Fail(): self._node_failed,
                }
            )
            
    def _node_acked(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'accountant._node_acked %r %r' % (response, info))
        if not response.Payload.startswith('accepted'):
            if _Debug:
                lg.out(_DebugLevel, 'accountant._node_acked %r %r' % (response, info))
            self._lookup_accountants()
            return
        if _Debug:
            lg.out(_DebugLevel, 'accountant._node_acked !!!! accountant %s now connected' % response.CreatorID)
        self.join_accountant(response.CreatorID)
        if len(self.connected_accountants) < self.max_accountants_connected:
            self._lookup_accountants()
        else:
            self.automat('accountants-connected')

    def _node_failed(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'accountant._node_failed %r %r' % (response, info))
        self._lookup_accountants()

    def _download_coins(self):
        if self.download_coins_task and self.download_coins_task.cancelled:
            self.download_coins_task = None
            return
        self.download_coins_task = Deferred()
        # 
        
