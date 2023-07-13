#!/usr/bin/env python
# bismuth_identity.py
#
"""
.. module:: bismuth_identity
.. role:: red

BitDust bismuth_identity() Automat

EVENTS:
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`shutdown`
    * :red:`start`
    * :red:`timer-5min`
    * :red:`tx-not-found`
    * :red:`valid-tx-found`
"""

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import strng

from bitdust.blockchain import bismuth_wallet

from bitdust.dht import dht_records

from bitdust.userid import my_id
from bitdust.userid import id_url

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

_BismuthIdentity = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with `bismuth_identity()` machine.
    """
    global _BismuthIdentity
    if event is None:
        return _BismuthIdentity
    if _BismuthIdentity is None:
        if event == 'shutdown':
            return _BismuthIdentity
        # TODO: set automat name and starting state here
        _BismuthIdentity = BismuthIdentity(
            name='bismuth_identity',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
            publish_events=False,
        )
    if event is not None:
        _BismuthIdentity.automat(event, *args, **kwargs)
    return _BismuthIdentity


class BismuthIdentity(automat.Automat):
    """
    This class implements all the functionality of ``bismuth_identity()`` state machine.
    """

    timers = {
        'timer-5min': (300, ['BLOCKCHAIN_READ']),
    }

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `bismuth_identity()` state machine.
        """
        super(BismuthIdentity, self).__init__(debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `bismuth_identity()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `bismuth_identity()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `bismuth_identity()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://github.com/vesellov/visio2python>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'BLOCKCHAIN_READ'
                self.doInit(*args, **kwargs)
                self.doBlockchainTxSearch(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'dht-read-failed':
                self.state = 'DHT_WRITE'
                self.doDHTWriteKey(*args, **kwargs)
            elif event == 'dht-read-success' and self.isMyOwnKey(*args, **kwargs):
                self.state = 'BLOCKCHAIN_READ'
            elif event == 'dht-read-success' and not self.isMyOwnKey(*args, **kwargs):
                self.doNextPosition(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'shutdown':
                self.doDestroyMe(*args, **kwargs)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'dht-write-success' or (event == 'dht-write-failed' and self.Attempts > 5):
                self.state = 'BLOCKCHAIN_READ'
                self.Attempts = 0
            elif event == 'dht-write-failed' and self.Attempts <= 5:
                self.state = 'DHT_READ'
                self.Attempts += 1
                self.doNextPosition(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'shutdown':
                self.doDestroyMe(*args, **kwargs)
        #---BLOCKCHAIN_READ---
        elif self.state == 'BLOCKCHAIN_READ':
            if event == 'tx-not-found':
                self.state = 'DHT_READ'
                self.Attempts = 0
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'valid-tx-found':
                self.state = 'READY'
                self.doReportReady(*args, **kwargs)
            elif event == 'timer-5min':
                self.doBlockchainTxSearch(*args, **kwargs)
            elif event == 'shutdown':
                self.doDestroyMe(*args, **kwargs)
        #---READY---
        elif self.state == 'READY':
            if event == 'shutdown':
                self.doDestroyMe(*args, **kwargs)
        return None

    def isMyOwnKey(self, *args, **kwargs):
        """
        Condition method.
        """
        return id_url.to_bin(args[0]) == my_id.getIDURL().to_bin()

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.result_defer = kwargs.get('result_defer')
        self.dht_position = 0
        self.dht_read_defer = None
        self.my_pub_key = my_id.getIDName() + ':' + strng.to_text(my_id.getLocalIdentity().getPublicKey()).replace('ssh-rsa ', '')

    def doNextPosition(self, *args, **kwargs):
        """
        Action method.
        """
        self.dht_position += 1

    def doBlockchainTxSearch(self, *args, **kwargs):
        """
        Action method.
        """
        results = bismuth_wallet.client().search_transactions(
            recipient=bismuth_wallet.my_wallet_address(),
            operation='identity',
            openfield=self.my_pub_key,
        )
        if _Debug:
            lg.args(_DebugLevel, my_wallet_address=bismuth_wallet.my_wallet_address(), results=results)
        if results:
            self.automat('valid-tx-found')
        else:
            self.automat('tx-not-found')

    def doDHTReadKey(self, *args, **kwargs):
        """
        Action method.
        """
        if self.dht_read_defer is not None:
            self.dht_read_defer.pause()
            self.dht_read_defer.cancel()
            self.dht_read_defer = None
        d = dht_records.get_bismuth_identity_request(position=self.dht_position, use_cache=False)
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='bismuth_identity.doDHTReadKey')
        d.addCallback(self._dht_read_result, self.dht_position)
        d.addErrback(self._dht_read_failed)
        self.dht_read_defer = d

    def doDHTWriteKey(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_records.set_bismuth_identity_request(
            position=self.dht_position,
            idurl=my_id.getIDURL(),
            public_key=self.my_pub_key,
        )
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='bismuth_identity.doDHTWriteKey')
        d.addCallback(self._dht_write_result)
        d.addErrback(lambda err: self.automat('dht-write-failed', err))

    def doReportReady(self, *args, **kwargs):
        """
        Action method.
        """
        if self.result_defer:
            self.result_defer.callback(True)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

    def _dht_read_result(self, value, position):
        if _Debug:
            lg.args(_DebugLevel, position=position, value=value)
        self.dht_read_defer = None
        if not value:
            self.automat('dht-read-failed')
            return
        try:
            v = id_url.field(value['idurl'])
        except:
            if _Debug:
                lg.out(_DebugLevel, '%r' % value)
            lg.exc()
            self.automat('dht-read-failed')
            return
        self.automat('dht-read-success', v)

    def _dht_read_failed(self, result):
        if _Debug:
            lg.args(_DebugLevel, result=result)
        self.dht_read_defer = None
        self.automat('dht-read-failed', result)

    def _dht_write_result(self, nodes):
        if _Debug:
            lg.args(_DebugLevel, nodes=nodes)
        if len(nodes) > 0:
            self.automat('dht-write-success')
        else:
            self.automat('dht-write-failed', nodes)
