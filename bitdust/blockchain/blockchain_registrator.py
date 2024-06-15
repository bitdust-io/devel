#!/usr/bin/env python
# blockchain_registrator.py
#
"""
.. module:: blockchain_registrator
.. role:: red

BitDust blockchain_registrator() Automat

EVENTS:
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`record-already-exist`
    * :red:`shutdown`
    * :red:`start`
    * :red:`timer-5min`
    * :red:`tx-not-found`
    * :red:`valid-tx-found`
"""

#------------------------------------------------------------------------------

import random

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import strng

from bitdust.blockchain import bismuth_wallet

from bitdust.dht import dht_records

from bitdust.userid import my_id
from bitdust.userid import id_url

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

_BlockchainRegistrator = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with `blockchain_registrator()` machine.
    """
    global _BlockchainRegistrator
    if event is None:
        return _BlockchainRegistrator
    if _BlockchainRegistrator is None:
        if event == 'shutdown':
            return _BlockchainRegistrator
        # TODO: set automat name and starting state here
        _BlockchainRegistrator = BlockchainRegistrator(
            name='blockchain_registrator',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
            publish_events=False,
        )
    if event is not None:
        _BlockchainRegistrator.automat(event, *args, **kwargs)
    return _BlockchainRegistrator


class BlockchainRegistrator(automat.Automat):

    """
    This class implements all the functionality of ``blockchain_registrator()`` state machine.
    """

    timers = {
        'timer-5min': (300, ['BLOCKCHAIN_READ']),
    }

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `blockchain_registrator()` state machine.
        """
        self.dht_position = 1
        super(BlockchainRegistrator, self).__init__(
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs,
        )

    def __repr__(self):
        return '%s[%d](%s)' % (self.id, self.dht_position, self.state)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `blockchain_registrator()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `blockchain_registrator()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `blockchain_registrator()`
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
                self.doSearchTransaction(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'dht-read-failed':
                self.state = 'DHT_WRITE'
                self.doDHTWrite(*args, **kwargs)
            elif event == 'dht-read-success':
                self.state = 'BLOCKCHAIN_READ'
            elif event == 'record-already-exist':
                self.doNextPosition(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
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
                self.doDHTRead(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---BLOCKCHAIN_READ---
        elif self.state == 'BLOCKCHAIN_READ':
            if event == 'tx-not-found':
                self.state = 'DHT_READ'
                self.Attempts = 0
                self.doDHTRead(*args, **kwargs)
            elif event == 'valid-tx-found':
                self.state = 'READY'
                self.doDHTErase(*args, **kwargs)
                self.doReportReady(*args, **kwargs)
            elif event == 'timer-5min':
                self.doSearchTransaction(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---READY---
        elif self.state == 'READY':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.result_defer = kwargs.get('result_defer')
        self.dht_position = 1
        self.dht_read_defer = None

    def doNextPosition(self, *args, **kwargs):
        """
        Action method.
        """
        current_position = self.dht_position
        max_position = self.dht_position*2 + 1
        self.dht_position += random.randint(current_position + 1, max_position)
        if self.dht_position > 500:
            self.dht_position = 1

    def doSearchTransaction(self, *args, **kwargs):
        """
        Action method.
        """
        clean_public_key = strng.to_text(my_id.getLocalIdentity().getPublicKey())[:10000].replace('ssh-rsa ', '')
        results = bismuth_wallet.find_transaction(
            recipient=bismuth_wallet.my_wallet_address(),
            operation='identity',
            openfield='{}:{}'.format(my_id.getIDName(), clean_public_key),
        )
        if results:
            self.automat('valid-tx-found')
        else:
            self.automat('tx-not-found')

    def doDHTRead(self, *args, **kwargs):
        """
        Action method.
        """
        if self.dht_read_defer is not None:
            self.dht_read_defer.pause()
            self.dht_read_defer.cancel()
            self.dht_read_defer = None
        self.dht_read_defer = dht_records.get_bismuth_identity_request(position=self.dht_position, use_cache=False)
        self.dht_read_defer.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='blockchain_registrator.doDHTReadKey')
        self.dht_read_defer.addCallback(self._dht_read_result, self.dht_position)
        self.dht_read_defer.addErrback(self._dht_read_failed)

    def doDHTWrite(self, *args, **kwargs):
        """
        Action method.
        """
        clean_public_key = strng.to_text(my_id.getLocalIdentity().getPublicKey())[:10000].replace('ssh-rsa ', '')
        d = dht_records.set_bismuth_identity_request(
            position=self.dht_position,
            idurl=my_id.getIDURL(),
            public_key=clean_public_key,
            wallet_address=bismuth_wallet.my_wallet_address(),
        )
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='blockchain_registrator.doDHTWriteKey')
        d.addCallback(self._dht_write_result)
        d.addErrback(lambda err: self.automat('dht-write-failed', err))

    def doDHTErase(self, *args, **kwargs):
        """
        Action method.
        """
        dht_records.erase_bismuth_identity_request(position=self.dht_position)

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
        global _BlockchainRegistrator
        del _BlockchainRegistrator
        _BlockchainRegistrator = None

    def _dht_read_result(self, value, position):
        if _Debug:
            lg.args(_DebugLevel, position=position, value=value)
        self.dht_read_defer = None
        if not value:
            self.automat('dht-read-failed')
            return
        try:
            idurl_at_position = id_url.field(value['idurl'])
        except:
            lg.exc()
            self.automat('dht-read-failed')
            return
        if id_url.is_the_same(idurl_at_position, my_id.getIDURL()):
            if value['wallet_address'] != bismuth_wallet.my_wallet_address():
                self.automat('dht-read-failed')
            else:
                self.automat('dht-read-success', value)
        else:
            self.automat('record-already-exist', value)

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
