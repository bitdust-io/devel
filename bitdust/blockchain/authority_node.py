#!/usr/bin/env python
# authority_node.py
#
"""
.. module:: authority_node
.. role:: red

BitDust authority_node() Automat

EVENTS:
    * :red:`init`
    * :red:`no-record`
    * :red:`read-failed`
    * :red:`run-cycle`
    * :red:`shutdown`
    * :red:`timer-1min`
    * :red:`tx-failed`
    * :red:`tx-not-found`
    * :red:`tx-sent`
    * :red:`valid-record`
    * :red:`valid-tx-found`
"""

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import strng

from bitdust.automats import automat

from bitdust.main import config

from bitdust.blockchain import bismuth_wallet

from bitdust.dht import dht_records

from bitdust.contacts import identitycache

from bitdust.userid import id_url

#------------------------------------------------------------------------------

_AuthorityNode = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with `authority_node()` machine.
    """
    global _AuthorityNode
    if event is None:
        return _AuthorityNode
    if _AuthorityNode is None:
        if event == 'shutdown':
            return _AuthorityNode
        # TODO: set automat name and starting state here
        _AuthorityNode = AuthorityNode(
            name='authority_node',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
            publish_events=False,
        )
    if event is not None:
        _AuthorityNode.automat(event, *args, **kwargs)
    return _AuthorityNode


#------------------------------------------------------------------------------


class AuthorityNode(automat.Automat):

    """
    This class implements all the functionality of ``authority_node()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['IDLE']),
    }

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `authority_node()` state machine.
        """
        self.dht_position = 0
        self.dht_last_value = None
        self.empty_streak = 0
        super(AuthorityNode, self).__init__(
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs,
        )

    def __repr__(self):
        return '%s[%d|%d](%s)' % (self.id, self.dht_position, self.empty_streak, self.state)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `authority_node()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `authority_node()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `authority_node()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://github.com/vesellov/visio2python>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'IDLE'
                self.doInit(*args, **kwargs)
                self.doNextRecord(*args, **kwargs)
                self.doRunCycleSoon(*args, **kwargs)
        #---IDLE---
        elif self.state == 'IDLE':
            if event == 'run-cycle':
                self.state = 'DHT_READ'
                self.doDHTRead(*args, **kwargs)
            elif event == 'timer-1min':
                self.doRunCycleSoon(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'valid-record':
                self.state = 'FIND_TX'
                self.doFindTransaction(*args, **kwargs)
            elif event == 'no-record' or event == 'read-failed':
                self.state = 'IDLE'
                self.doNextRecord(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---FIND_TX---
        elif self.state == 'FIND_TX':
            if event == 'tx-not-found':
                self.state = 'SEND_TX'
                self.doSendTransaction(*args, **kwargs)
            elif event == 'valid-tx-found':
                self.state = 'IDLE'
                self.doDHTErase(*args, **kwargs)
                self.doNextRecord(*args, **kwargs)
                self.doRunCycleSoon(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---SEND_TX---
        elif self.state == 'SEND_TX':
            if event == 'tx-sent' or event == 'tx-failed':
                self.state = 'IDLE'
                self.doNextRecord(*args, **kwargs)
                self.doRunCycleSoon(*args, **kwargs)
            elif event == 'shutdown':
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
        self.dht_position = config.conf().getInt('services/blockchain-authority/requests-reading-offset', 0)
        self.dht_last_value = None
        self.empty_streak = 0

    def doNextRecord(self, *args, **kwargs):
        """
        Action method.
        """
        reading_limit = config.conf().getInt('services/blockchain-authority/requests-reading-limit', 10)
        empty_streak_limit = min(5, int(reading_limit/5.0) + 1)
        if (self.empty_streak >= empty_streak_limit) or (self.dht_position > reading_limit):
            self.dht_position = config.conf().getInt('services/blockchain-authority/requests-reading-offset', 0)
            self.empty_streak = 0
        self.dht_last_value = None
        self.dht_position += 1

    def doRunCycleSoon(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, dht_position=self.dht_position, empty_streak=self.empty_streak)
        self.automat('run-cycle')

    def doDHTRead(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_records.get_bismuth_identity_request(position=self.dht_position, use_cache=False)
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='authority_node.doDHTRead')
        d.addCallback(self._on_dht_read_result, self.dht_position)
        d.addErrback(self._on_dht_read_failed)

    def doDHTErase(self, *args, **kwargs):
        """
        Action method.
        """
        dht_records.erase_bismuth_identity_request(position=self.dht_position)

    def doFindTransaction(self, *args, **kwargs):
        """
        Action method.
        """
        clean_public_key = strng.to_text(self.dht_last_value['public_key'])[:10000].replace('ssh-rsa ', '')
        idurl = id_url.field(self.dht_last_value['idurl'])
        results = bismuth_wallet.find_transaction(
            recipient=self.dht_last_value['wallet_address'],
            operation='identity',
            openfield='{}:{}'.format(idurl.username, clean_public_key),
        )
        if results:
            self.automat('valid-tx-found')
        else:
            self.automat('tx-not-found')

    def doSendTransaction(self, *args, **kwargs):
        """
        Action method.
        """
        registration_bonus_coins = config.conf().getInt('services/blockchain-authority/registration-bonus-coins', 0)
        clean_public_key = strng.to_text(self.dht_last_value['public_key'])[:10000].replace('ssh-rsa ', '')
        idurl = id_url.field(self.dht_last_value['idurl'])
        try:
            tx_id = bismuth_wallet.send_transaction(
                recipient=self.dht_last_value['wallet_address'],
                amount=registration_bonus_coins,
                operation='identity',
                data='{}:{}'.format(idurl.username, clean_public_key),
            )
        except:
            lg.exc()
            self.automat('tx-failed')
            return
        self.automat('tx-sent', tx_id)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()
        global _AuthorityNode
        del _AuthorityNode
        _AuthorityNode = None

    def _on_identity_cached(self, src, idurl, value):
        ident = identitycache.FromCache(idurl)
        if not ident:
            lg.err('identity %r was not cached' % idurl)
            self.empty_streak += 1
            self.dht_last_value = None
            self.automat('read-failed', value)
            return
        if not id_url.is_the_same(ident.getIDURL(), value['idurl']):
            lg.warn('ivalid Bismuth identity register request, idurl is not matching')
            self.empty_streak += 1
            self.dht_last_value = None
            self.automat('read-failed', value)
            return
        if strng.to_text(ident.getPublicKey()).replace('ssh-rsa ', '') != value['public_key']:
            lg.warn('ivalid Bismuth identity register request, public key is not matching')
            self.empty_streak += 1
            self.dht_last_value = None
            self.automat('read-failed', value)
            return
        self.dht_last_value = value
        self.empty_streak = 0
        self.automat('valid-record', value)

    def _on_identity_cache_failed(self, err, idurl):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        self.empty_streak += 1
        self.dht_last_value = None
        self.automat('read-failed', err)

    def _on_dht_read_result(self, value, position):
        if _Debug:
            lg.args(_DebugLevel, position=position, value=value)
        if not value:
            self.empty_streak += 1
            self.dht_last_value = value
            self.automat('no-record', value)
            return
        try:
            idurl = value['idurl']
            value['public_key']
            value['wallet_address']
        except Exception as exc:
            lg.exc()
            self.empty_streak += 1
            self.dht_last_value = value
            self.automat('read-failed', exc)
            return
        d = identitycache.immediatelyCaching(idurl)
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='authority_node._on_dht_read_result')
        d.addErrback(self._on_identity_cache_failed, idurl)
        d.addCallback(self._on_identity_cached, idurl, value)

    def _on_dht_read_failed(self, result):
        if _Debug:
            lg.args(_DebugLevel, result=result)
        self.empty_streak += 1
        self.dht_last_value = result
        self.automat('no-record', result)
