#!/usr/bin/env python
# coins_miner.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (coins_miner.py) is part of BitDust Software.
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
.. module:: coins_miner.

.. role:: red

BitDust coins_miner() Automat

EVENTS:
    * :red:`accountant-connected`
    * :red:`cancel`
    * :red:`coin-confirmed`
    * :red:`coin-mined`
    * :red:`coin-rejected`
    * :red:`init`
    * :red:`lookup-failed`
    * :red:`new-data-received`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-2min`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import random
import string
import hashlib

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet import threads
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from userid import my_id

from lib import utime

from p2p import commands
from p2p import p2p_service

from transport import callback

from coins import coins_io

#------------------------------------------------------------------------------

_CoinsMiner = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _CoinsMiner
    if event is None and not args:
        return _CoinsMiner
    if _CoinsMiner is None:
        # set automat name and starting state here
        _CoinsMiner = CoinsMiner('coins_miner', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _CoinsMiner.automat(event, *args, **kwargs)
    return _CoinsMiner

#------------------------------------------------------------------------------


class CoinsMiner(automat.Automat):
    """
    This class implements all the functionality of the ``coins_miner()`` state
    machine.
    """

    fast = True

    timers = {
        'timer-2min': (120, ['ACCOUNTANTS?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of coins_miner() machine.
        """
        self.offline_mode = False  # only for Debug purposes
        self.new_coin_filter_method = None
        self.connected_accountants = []
        self.min_accountants_connected = 3  # TODO: read from settings
        self.max_accountants_connected = 5  # TODO: read from settings
        self.input_data = []
        self.max_mining_counts = 10**8  # TODO: read from settings
        self.max_mining_seconds = 60 * 3  # TODO: read from settings
        self.simplification = 2
        self.starter_length = 10
        self.starter_limit = 9999
        self.mining_started = -1
        self.mining_counts = 0

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python
        <https://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(*args, **kwargs)
        #---READY---
        elif self.state == 'READY':
            if event == 'stop':
                self.state = 'STOPPED'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'new-data-received' and self.isDecideOK(*args, **kwargs):
                self.state = 'MINING'
                self.doStartMining(*args, **kwargs)
            elif event == 'new-data-received' and not self.isDecideOK(*args, **kwargs):
                self.doSendFail(*args, **kwargs)
        #---MINING---
        elif self.state == 'MINING':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doStopMining(*args, **kwargs)
            elif event == 'coin-mined':
                self.state = 'PUBLISH_COIN'
                self.doSendCoinToAccountants(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopMining(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'new-data-received':
                self.doPushInputData(*args, **kwargs)
            elif event == 'cancel':
                self.state = 'READY'
                self.doStopMining(*args, **kwargs)
                self.doSendFail(*args, **kwargs)
                self.doPullInputData(*args, **kwargs)
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'start':
                self.state = 'ACCOUNTANTS?'
                self.doLookupAccountants(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---PUBLISH_COIN---
        elif self.state == 'PUBLISH_COIN':
            if event == 'stop':
                self.state = 'STOPPED'
            elif event == 'coin-confirmed' and self.isAllConfirmed(*args, **kwargs):
                self.state = 'READY'
                self.doSendAck(*args, **kwargs)
                self.doPullInputData(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'coin-rejected' and self.isDecideOK(*args, **kwargs):
                self.state = 'MINING'
                self.doContinueMining(*args, **kwargs)
            elif event == 'new-data-received':
                self.doPushInputData(*args, **kwargs)
            elif event == 'cancel' or ( event == 'coin-rejected' and not self.isDecideOK(*args, **kwargs) ):
                self.state = 'READY'
                self.doSendFail(*args, **kwargs)
                self.doPullInputData(*args, **kwargs)
        #---ACCOUNTANTS?---
        elif self.state == 'ACCOUNTANTS?':
            if event == 'accountant-connected' and not self.isMoreNeeded(*args, **kwargs):
                self.state = 'READY'
                self.doAddAccountant(*args, **kwargs)
                self.doPullInputData(*args, **kwargs)
            elif event == 'accountant-connected' and self.isMoreNeeded(*args, **kwargs):
                self.doAddAccountant(*args, **kwargs)
                self.doLookupAccountants(*args, **kwargs)
            elif event == 'new-data-received':
                self.doPushInputData(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop' or event == 'cancel' or event == 'timer-2min' or ( event == 'lookup-failed' and not self.isAnyAccountants(*args, **kwargs) ):
                self.state = 'STOPPED'
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isAnyAccountants(self, *args, **kwargs):
        """
        Condition method.
        """
        if self.offline_mode:
            return True
        return len(self.connected_accountants) > 0

    def isMoreNeeded(self, *args, **kwargs):
        """
        Condition method.
        """
        if self.offline_mode:
            return False
        return len(self.connected_accountants) < self.min_accountants_connected

    def isDecideOK(self, *args, **kwargs):
        """
        Condition method.
        """
        # TODO:
        return True

    def isAllConfirmed(self, *args, **kwargs):
        """
        Condition method.
        """
        if self.offline_mode:
            return True
        # TODO:
        return False

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        callback.append_inbox_callback(self._on_inbox_packet)
        if args and args[0]:
            self.new_coin_filter_method, self.offline_mode = args[0]

    def doAddAccountant(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0]:
            if args[0] not in self.connected_accountants:
                self.connected_accountants.append(args[0])
            else:
                lg.warn('%s already connected as accountant' % args[0])

    def doLookupAccountants(self, *args, **kwargs):
        """
        Action method.
        """
        if self.offline_mode or len(self.connected_accountants) >= self.min_accountants_connected:
            self.automat('accountant-connected', '')
            return
        from coins import accountants_finder
        accountants_finder.A('start', (self.automat, 'read'))

    def doPushInputData(self, *args, **kwargs):
        """
        Action method.
        """
        self.input_data.append(args[0])

    def doPullInputData(self, *args, **kwargs):
        """
        Action method.
        """
        if len(self.input_data) > 0:
            self.automat('new-data-received', self.input_data.pop(0))

    def doStartMining(self, *args, **kwargs):
        """
        Action method.
        """
        self.mining_started = utime.get_sec1970()
        d = self._start(args[0])
        d.addCallback(self._on_coin_mined)
        d.addErrback(lambda err: self.automat('stop'))
        d.addErrback(lambda err: lg.exc(exc_value=err))

    def doStopMining(self, *args, **kwargs):
        """
        Action method.
        """
        self.mining_started = -1

    def doSendCoinToAccountants(self, *args, **kwargs):
        """
        Action method.
        """
        if self.offline_mode:
            self.automat('coin-confirmed')
            return
        coins = [args[0], ]
        if _Debug:
            lg.out(_DebugLevel, 'coins_miner.doSendCoinToAccountants: %s' % coins)
        for idurl in self.connected_accountants:
            p2p_service.SendCoin(idurl, coins)

    def doContinueMining(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendAck(self, *args, **kwargs):
        """
        Action method.
        """
        if self.offline_mode:
            return
        # TODO:

    def doSendFail(self, *args, **kwargs):
        """
        Action method.
        """
        if self.offline_mode:
            return
        # TODO:

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        callback.remove_inbox_callback(self._on_inbox_packet)
        self.unregister()
        global _CoinsMiner
        if self == _CoinsMiner:
            del _CoinsMiner
            _CoinsMiner = None

    #------------------------------------------------------------------------------

    def _on_inbox_packet(self, newpacket, info, status, error_message):
        if newpacket.Command == commands.Coin():
            coins_list = coins_io.read_coins_from_packet(newpacket)
            if not coins_list:
                p2p_service.SendFail(newpacket, 'failed to read coins from packet')
                return True
            if len(coins_list) != 1:
                p2p_service.SendFail(newpacket, 'expected only one coin to be mined')
                return True
            coin_json = coins_list[0]
            if not coins_io.validate_coin(coin_json):
                lg.warn('coin not valid: %s' % coin_json)
                p2p_service.SendFail(newpacket, 'coin not valid')
                return True
            if not coins_io.verify_signature(coin_json, 'creator'):
                lg.warn('creator signature is not valid: %s' % coin_json)
                p2p_service.SendFail(newpacket, 'creator signature is not valid')
                return True
            self.automat('new-data-received', coin_json)
            return True
        return False

    def _on_coin_mined(self, coin):
        if self.new_coin_filter_method is not None:
            coin = self.new_coin_filter_method(coin)
            if coin is None:
                self.automat('cancel')
                return
        self.automat('coin-mined', coin)

    def _stop_marker(self):
        if self.mining_started < 0:
            return True
        if self.mining_counts >= self.max_mining_counts:
            return True
        if utime.get_sec1970() - self.mining_started > self.max_mining_seconds:
            return True
        self.mining_counts += 1
        return False

    def _build_starter(self, length):
        return (''.join(
            [random.choice(string.uppercase + string.lowercase + string.digits)  # @UndefinedVariable
                for _ in range(length)])) + '_'

    def _build_hash(self, payload):
        return hashlib.sha1(payload).hexdigest()

    def _get_hash_complexity(self, hexdigest, simplification):
        complexity = 0
        while complexity < len(hexdigest):
            if int(hexdigest[complexity], 16) < simplification:
                complexity += 1
            else:
                break
        return complexity

    def _get_hash_difficulty(self, hexdigest, simplification):
        difficulty = 0
        while True:
            ok = False
            for simpl in range(simplification):
                if hexdigest.startswith(str(simpl) * difficulty):
                    ok = True
                    break
            if ok:
                difficulty += 1
            else:
                break
        return difficulty - 1

    def _mine(self, coin_json, difficulty, simplification, starter_length, starter_limit):
        data_dump = coins_io.coin_to_string(coin_json)
        starter = self._build_starter(starter_length)
        on = 0
        while True:
            if self._stop_marker():
                if _Debug:
                    lg.out(_DebugLevel, 'coins_miner._mine STOPPED, stop marker returned True')
                return None
            check = starter + str(on)
            check += data_dump
            hexdigest = self._build_hash(check)
            if difficulty == self._get_hash_complexity(hexdigest, simplification):
                # SOLVED!
                break
            on += 1
            if on > starter_limit:
                starter = self._build_starter(starter_length)
                on = 0
        coin_json['miner'].update({
            'hash': hexdigest,
            'starter': starter + str(on),
            'mined': utime.utcnow_to_sec1970(),
        })
        return coin_json

    def _start(self, coin_json):
        coin_json['miner']['idurl'] = my_id.getLocalID()
        # "prev" field must already be there
        prev_hash = coin_json['miner']['prev']
        difficulty = self._get_hash_difficulty(prev_hash, self.simplification)
        complexity = self._get_hash_complexity(prev_hash, self.simplification)
        if difficulty == complexity:
            complexity += 1
            if _Debug:
                lg.out(_DebugLevel, 'coins_miner.found golden coin, step up complexity: %s' % complexity)
        return threads.deferToThread(self._mine, coin_json, complexity,
                                     self.simplification, self.starter_length, self.starter_limit)

#------------------------------------------------------------------------------

def start_offline_job(coin):
    result = Deferred()
    one_miner = CoinsMiner('coins_miner', 'AT_STARTUP', _DebugLevel, _Debug)

    def _job_done(new_coin):
        reactor.callLater(0, one_miner.automat, 'shutdown')  # @UndefinedVariable
        result.callback(new_coin)
        return None

    one_miner.automat('init', (_job_done, True))
    one_miner.automat('start')
    one_miner.automat('new-data-received', coin)

    return result

#------------------------------------------------------------------------------

def _test():
    lg.set_debug_level(20)
    acoin = coins_io.storage_contract_open('http://abc.com/id.xml', 3600, 100)
    start_offline_job(acoin).addBoth(lambda *a, **kw: reactor.stop())  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable


if __name__ == "__main__":
    _test()
