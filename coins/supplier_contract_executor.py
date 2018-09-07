#!/usr/bin/env python
# supplier_contract_executor.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (supplier_contract_executor.py) is part of BitDust Software.
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
.. module:: supplier_contract_executor
.. role:: red

BitDust supplier_contract_executor() Automat

EVENTS:
    * :red:`chain-1-state`
    * :red:`chain-2-state`
    * :red:`chain-closed`
    * :red:`chain-empty`
    * :red:`coin-failed`
    * :red:`coin-published`
    * :red:`coin-sent`
    * :red:`contract-signed`
    * :red:`init`
    * :red:`payment-timeout`
    * :red:`query-failed`
    * :red:`recheck`
    * :red:`shutdown`
    * :red:`time-to-charge`
    * :red:`timer-1min`
    * :red:`timer-30sec`
"""

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 6

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import nameurl

from storage import accounting

from userid import my_id

from p2p import commands
from p2p import p2p_service

from coins import coins_io
from coins import contract_chain_node

#------------------------------------------------------------------------------

_ActiveSupplierContracts = dict()  # provides SupplierContractExecutor object by customer idurl

#------------------------------------------------------------------------------

def all_contracts():
    """
    """
    global _ActiveSupplierContracts
    return _ActiveSupplierContracts


def init_contract(customer_idurl):
    """
    """
    global _ActiveSupplierContracts
    if customer_idurl in _ActiveSupplierContracts:
        lg.warn('contract with customer %s already started' % customer_idurl)
        return _ActiveSupplierContracts[customer_idurl]
    cce = SupplierContractExecutor(customer_idurl)
    cce.automat('init')
    _ActiveSupplierContracts[customer_idurl] = cce
    return _ActiveSupplierContracts[customer_idurl]


def shutdown_contract(customer_idurl):
    """
    """
    global _ActiveSupplierContracts
    if customer_idurl not in _ActiveSupplierContracts:
        lg.warn('no contract started for given customer')
        return False
    _ActiveSupplierContracts[customer_idurl].automat('shutdown')
    _ActiveSupplierContracts.pop(customer_idurl)
    return True


def get_contract(customer_idurl):
    """
    """
    global _ActiveSupplierContracts
    if customer_idurl not in _ActiveSupplierContracts:
        return None
    return _ActiveSupplierContracts[customer_idurl]


def recheck_contract(customer_idurl):
    """
    """
    contract_executor = get_contract(customer_idurl)
    if contract_executor is None:
        contract_executor = init_contract(customer_idurl)
    contract_executor.automat('recheck')

#------------------------------------------------------------------------------

class SupplierContractExecutor(automat.Automat):
    """
    This class implements all the functionality of the ``supplier_contract_executor()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['READ_CHAIN?']),
        'timer-30sec': (30.0, ['CUSTOMER_SIGN?']),
    }

    def __init__(self, customer_idurl):
        self.customer_idurl = customer_idurl
        name = 'supplier_executor_%s' % nameurl.GetName(self.customer_idurl)
        automat.Automat.__init__(self, name, 'AT_STARTUP', _DebugLevel, _Debug)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of supplier_contract_executor() machine.
        """
        self.current_duration = 60 * 60  # TODO: read from settings

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <https://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READ_CHAIN?'
                self.doRequestCoins(arg)
        #---MY_COIN!---
        elif self.state == 'MY_COIN!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'coin-failed':
                self.state = 'UNCLEAR'
            elif event == 'coin-sent':
                self.state = 'CUSTOMER_COIN?'
        #---CUSTOMER_COIN?---
        elif self.state == 'CUSTOMER_COIN?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'coin-published':
                self.state = 'ACTIVE'
                self.doSchedulePayment(arg)
            elif event == 'payment-timeout':
                self.state = 'FINISHED'
                self.doRemoveCustomer(arg)
        #---ACTIVE---
        elif self.state == 'ACTIVE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'time-to-charge':
                self.state = 'MY_COIN!'
                self.doSendNextCoin(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---FINISHED---
        elif self.state == 'FINISHED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---UNCLEAR---
        elif self.state == 'UNCLEAR':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'recheck':
                self.state = 'READ_CHAIN?'
                self.doRequestCoins(arg)
        #---READ_CHAIN?---
        elif self.state == 'READ_CHAIN?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'chain-2-state':
                self.state = 'ACTIVE'
                self.doSchedulePayment(arg)
            elif event == 'timer-1min' or event == 'query-failed':
                self.state = 'UNCLEAR'
            elif event == 'chain-empty':
                self.state = 'CUSTOMER_SIGN?'
                self.doRequestCustomerSignature(arg)
            elif event == 'chain-1-state':
                self.state = 'CUSTOMER_COIN?'
            elif event == 'chain-closed':
                self.state = 'FINISHED'
        #---CUSTOMER_SIGN?---
        elif self.state == 'CUSTOMER_SIGN?':
            if event == 'timer-30sec':
                self.state = 'UNCLEAR'
            elif event == 'contract-signed':
                self.state = 'MY_COIN!'
                self.doSendFirstCoin(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        return None

    def isCustomerCoinExist(self, coins):
        """
        Condition method.
        """
        if not coins:
            return False
        # TODO: 
        return True

    def isChainClosed(self, coins):
        """
        Condition method.
        """
        if not coins:
            return False
        # TODO: 
        return True

    def isMyCoinExist(self, coins):
        """
        Condition method.
        """
        if not coins:
            return False
        # TODO: 
        return True

    def doRequestCoins(self, arg):
        """
        Action method.
        """
        contract_chain_node.get_coins_by_chain(
            chain='supplier_customer',
            provider_idurl=my_id.getLocalID(),
            consumer_idurl=self.customer_idurl,
        ).addCallbacks(
            self._on_query_result,
            self._on_query_failed,
        )

    def doRequestCustomerSignature(self, arg):
        """
        Action method.
        """
        bytes_allocated = accounting.get_customer_quota(self.customer_idurl)
        assert bytes_allocated is not None
        assert bytes_allocated > 0
        coin_json = coins_io.storage_contract_open(
            self.customer_idurl,
            self.current_duration,
            bytes_allocated,
        )
        coin_json_sined = coins_io.add_signature(coin_json, 'creator')
        p2p_service.SendCoin(
            self.customer_idurl,
            [coin_json_sined, ],
            callbacks={
                commands.Ack(): self._on_signature_ack,
                commands.Fail(): self._on_signature_fail,
            }
        )

    def doSendFirstCoin(self, arg):
        """
        Action method.
        """
        coin_json = arg
        contract_chain_node.send_to_miner(
            [coin_json, ],
        ).addCallbacks(
            self._on_coin_mined,
            self._on_coin_failed,
        )

    def doSendNextCoin(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()

    def doRemoveCustomer(self, arg):
        """
        Action method.
        """

    def doSchedulePayment(self, arg):
        """
        Action method.
        """

    def _on_query_result(self, coins):
        if _Debug:
            lg.out(_DebugLevel, 'supplier_contract_executor._on_coins_received %s' % coins)
        if coins is None:
            self.automat('query-failed', [])
            return
        if len(coins) == 0:
            self.automat('chain-empty', [])
            return
        if len(coins) % 2 == 1:
            self.automat('chain-1-state', coins)
            return
        if len(coins) % 2 == 0:
            self.automat('chain-2-state', coins)
            return
        self.automat('query-failed', coins)

    def _on_query_failed(self, fails):
        if _Debug:
            lg.warn(str(fails))
        self.automat('query-failed', fails)

    def _on_signature_ack(self, response, info):
        pass

    def _on_signature_fail(self, response, info):
        pass
