#!/usr/bin/env python
# accountant_node.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (accountant_node.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com


"""
.. module:: accountant_node.

.. role:: red

BitDust accountant_node() Automat

EVENTS:
    * :red:`accountant-connected`
    * :red:`coin-broadcasted`
    * :red:`coin-not-valid`
    * :red:`coin-verified`
    * :red:`connection-lost`
    * :red:`init`
    * :red:`lookup-failed`
    * :red:`new-coin-mined`
    * :red:`pending-coin`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-1min`
    * :red:`timer-2min`
    * :red:`valid-coins-received`
"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import datetime

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from lib import utime

from automats import automat

from transport import callback

from p2p import p2p_service
from p2p import commands

from coins import coins_db
from coins import coins_io

from broadcast import broadcast_service

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
    This class implements all the functionality of the ``accountant_node()``
    state machine.
    """
    timers = {
        'timer-2min': (120, ['ACCOUNTANTS?']),
        'timer-1min': (60, ['READ_COINS']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of accountant_node() machine.
        """
        self.connected_accountants = []
        self.min_accountants_connected = 1  # TODO: read from settings
        self.max_accountants_connected = 1  # TODO: read from settings
        self.download_offset = datetime.datetime(2016, 1, 1)
        self.download_limit = 100
        self.pending_coins = []
        self.current_coin = None

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when accountant_node() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in
        the accountant_node() but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python
        <http://bitdust.io/visio2python/>`_ tool.
        """
        #---READY---
        if self.state == 'READY':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'connection-lost' or event == 'stop':
                self.state = 'OFFLINE'
            elif event == 'new-coin-mined':
                self.doPushCoin(arg)
            elif event == 'valid-coins-received':
                self.doWriteCoins(arg)
            elif event == 'pending-coin':
                self.state = 'VALID_COIN?'
                self.doPullCoin(arg)
                self.doVerifyCoin(arg)
        #---READ_COINS---
        elif self.state == 'READ_COINS':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'accountant-connected':
                self.doAddAccountant(arg)
                self.doRetreiveCoins(arg)
            elif event == 'stop' or ( event == 'timer-1min' and not self.isAnyCoinsReceived(arg) ):
                self.state = 'OFFLINE'
            elif event == 'new-coin-mined':
                self.doPushCoin(arg)
            elif event == 'valid-coins-received' and self.isMoreCoins(arg):
                self.doWriteCoins(arg)
                self.doRetreiveCoins(arg)
            elif event == 'valid-coins-received' and not self.isMoreCoins(arg):
                self.state = 'READY'
                self.doWriteCoins(arg)
                self.doCheckPendingCoins(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(arg)
        #---VALID_COIN?---
        elif self.state == 'VALID_COIN?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'OFFLINE'
            elif event == 'coin-not-valid':
                self.state = 'READY'
                self.doCheckPendingCoins(arg)
            elif event == 'accountant-connected':
                self.doAddAccountant(arg)
            elif event == 'coin-verified':
                self.state = 'WRITE_COIN!'
                self.doWriteCoin(arg)
                self.doBroadcastCoin(arg)
            elif event == 'valid-coins-received':
                self.doWriteCoins(arg)
            elif event == 'new-coin-mined':
                self.doPushCoin(arg)
        #---WRITE_COIN!---
        elif self.state == 'WRITE_COIN!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'OFFLINE'
            elif event == 'coin-broadcasted':
                self.state = 'READY'
                self.doCheckPendingCoins(arg)
            elif event == 'accountant-connected':
                self.doAddAccountant(arg)
            elif event == 'valid-coins-received':
                self.doWriteCoins(arg)
            elif event == 'new-coin-mined':
                self.doPushCoin(arg)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start':
                self.state = 'ACCOUNTANTS?'
                self.doLookupAccountants(arg)
            elif event == 'accountant-connected':
                self.state = 'ACCOUNTANTS?'
                self.doAddAccountant(arg)
                self.doLookupAccountants(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---ACCOUNTANTS?---
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
                self.doRetreiveCoins(arg)
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

    def isMoreCoins(self, arg):
        """
        Condition method.
        """
        return len(arg) > 0

    def isAnyCoinsReceived(self, arg):
        """
        Condition method.
        """

    def doInit(self, arg):
        """
        Action method.
        """
        callback.append_inbox_callback(self._on_inbox_packet)

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
            if _Debug:
                lg.out(_DebugLevel, 'accountant_node.doAddAccountant SKIP, %s already connected, skip' % arg)
            return
        self.connected_accountants.append(arg)
        if _Debug:
            lg.out(_DebugLevel, 'accountant_node.doAddAccountant NEW %s connected, %d total accountants' % (
                arg, len(self.connected_accountants)))

    def doRetreiveCoins(self, arg):
        """
        Action method.
        """
        query = {'method': 'get_all',
                 'index': 'time',
                 'limit': self.download_limit,
                 'start': utime.datetime_to_sec1970(self.download_offset),
                 'end': utime.utcnow_to_sec1970(), }
        for idurl in self.connected_accountants:
            p2p_service.SendRetreiveCoin(idurl, query)

    def doWriteCoins(self, arg):
        """
        Action method.
        """
        for coin in arg:
            if not coins_db.exist(coin):
                coins_db.insert(coin)
            if coin['tm'] > utime.datetime_to_sec1970(self.download_offset):
                self.download_offset = utime.sec1970_to_datetime_utc(coin['tm'])

    def doPushCoin(self, arg):
        """
        Action method.
        """
        self.pending_coins.append(arg)

    def doPullCoin(self, arg):
        """
        Action method.
        """
        self.current_coin = self.pending_coins.pop(0)

    def doCheckPendingCoins(self, arg):
        """
        Action method.
        """
        if len(self.pending_coins) > 0:
            self.automat('pending-coin')

    def doVerifyCoin(self, arg):
        """
        Action method.
        """
        if not coins_io.validate_coin(self.current_coin):
            self.current_coin = None
            self.automat('coin-not-valid')
            return
        d = self._verify_coin(self.current_coin)
        d.addCallback(lambda coin: self.automat('coin-verified'))
        d.addErrback(lambda err: self.automat('coin-not-valid'))

    def doBroadcastCoin(self, arg):
        """
        Action method.
        """
        broadcast_service.send_broadcast_message({'type': 'coin', 'data': arg})

    def doWriteCoin(self, arg):
        """
        Action method.
        """
        coins_db.insert(arg)

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.pending_coins = None
        self.connected_accountants = None
        callback.remove_inbox_callback(self._on_inbox_packet)
        automat.objects().pop(self.index)
        global _AccountantNode
        del _AccountantNode
        _AccountantNode = None

    #------------------------------------------------------------------------------

    def _verify_coin(self, acoin):
        # TODO:
        # run coin verification process
        # may require to communicate with other accountants
        d = Deferred()
        d.callback(acoin)
        return d

    def _on_inbox_packet(self, newpacket, info, status, error_message):
        if status != 'finished':
            return False
        if newpacket.Command == commands.RetreiveCoin():
            query_j = coins_io.read_query_from_packet(newpacket)
            if not query_j:
                p2p_service.SendFail(newpacket, 'incorrect query received')
                return False
            coins = coins_db.query_json(query_j)
            p2p_service.SendCoin(newpacket.CreatorID, coins, packet_id=newpacket.PacketID)
            return True
        if newpacket.Command == commands.Coin():
            coins_list = coins_io.read_coins_from_packet(newpacket)
            if not coins_list:
                p2p_service.SendFail(newpacket, 'failed to read coins from packet')
                return True
            if len(coins_list) == 1:
                acoin = coins_list[0]
                if not coins_io.validate_coin(acoin):
                    p2p_service.SendFail(newpacket, 'coin validation failed')
                    return True
                if not coins_io.verify_coin(acoin):
                    p2p_service.SendFail(newpacket, 'coin verification failed')
                    return True
                if coins_db.exist(acoin):
                    self.automat('valid-coins-received', [acoin, ])
                else:
                    self.automat('new-coin-mined', acoin)
                return True
            valid_coins = []
            for acoin in coins_list:
                if not coins_io.validate_coin(acoin):
                    continue
                if not coins_io.verify_coin(acoin):
                    continue
                valid_coins.append(acoin)
            if len(valid_coins) == len(coins_list):
                self.automat('valid-coins-received', valid_coins)
            else:
                p2p_service.SendFail(newpacket, 'some non-valid coins received')
            return True
        return False
