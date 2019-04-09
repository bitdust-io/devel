#!/usr/bin/env python
# customer_contract_executor.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (customer_contract_executor.py) is part of BitDust Software.
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
.. module:: customer_contract_executor
.. role:: red

EVENTS:
    * :red:`coin-failed`
    * :red:`coin-published`
    * :red:`coins-received`
    * :red:`contract-extended`
    * :red:`contract-finished`
    * :red:`init`
    * :red:`recheck`
    * :red:`request-failed`
    * :red:`shutdown`
    * :red:`supplier-coin-mined`
    * :red:`supplier-failed`
    * :red:`time-to-pay`
    * :red:`timer-1min`
    * :red:`timer-30min`
    * :red:`timer-30sec`
    * :red:`timer-5min`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
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

from userid import my_id

#------------------------------------------------------------------------------

_ActiveCustomerContracts = dict()  # provides CustomerContractExecutor object by supplier idurl

#------------------------------------------------------------------------------

def all_contracts():
    """
    """
    global _ActiveCustomerContracts
    return _ActiveCustomerContracts


def init_contract(supplier_idurl):
    """
    """
    global _ActiveCustomerContracts
    if supplier_idurl in _ActiveCustomerContracts:
        lg.warn('contract with supplier %s already started' % supplier_idurl)
        return _ActiveCustomerContracts[supplier_idurl]
    cce = CustomerContractExecutor(supplier_idurl)
    cce.automat('init')
    _ActiveCustomerContracts[supplier_idurl] = cce
    return _ActiveCustomerContracts[supplier_idurl]


def shutdown_contract(supplier_idurl):
    """
    """
    global _ActiveCustomerContracts
    if supplier_idurl not in _ActiveCustomerContracts:
        lg.warn('no contract started for given supplier')
        return False
    _ActiveCustomerContracts[supplier_idurl].automat('shutdown')
    _ActiveCustomerContracts.pop(supplier_idurl)
    return True


def get_contract(supplier_idurl):
    """
    """
    global _ActiveCustomerContracts
    if supplier_idurl not in _ActiveCustomerContracts:
        return None
    return _ActiveCustomerContracts[supplier_idurl]


def recheck_contract(supplier_idurl):
    """
    """
    contract_executor = get_contract(supplier_idurl)
    if contract_executor is None:
        contract_executor = init_contract(supplier_idurl)
    contract_executor.automat('recheck')

#------------------------------------------------------------------------------

class CustomerContractExecutor(automat.Automat):
    """
    This class implements all the functionality of the ``customer_contract_executor()`` state machine.
    """

    timers = {
        'timer-30min': (1800, ['SUPPLIER_COIN?']),
        'timer-1min': (60, ['READ_COINS?']),
        'timer-30sec': (30.0, ['EXTENSION?']),
        'timer-5min': (300, ['SUPERVISE']),
    }

    def __init__(self, supplier_idurl):
        self.supplier_idurl = supplier_idurl
        name = 'customer_executor_%s' % nameurl.GetName(self.supplier_idurl)
        automat.Automat.__init__(self, name, 'AT_STARTUP', _DebugLevel, _Debug)

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READ_COINS?'
                self.doRequestCoins(*args, **kwargs)
        #---READ_COINS?---
        elif self.state == 'READ_COINS?':
            if event == 'coins-received':
                self.state = 'SUPERVISE'
                self.doSchedulePayment(*args, **kwargs)
                self.doSuperviseSupplier(*args, **kwargs)
            elif event == 'timer-1min' or event == 'request-failed':
                self.state = 'UNCLEAR'
        #---SUPERVISE---
        elif self.state == 'SUPERVISE':
            if event == 'timer-5min':
                self.doSuperviseSupplier(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doCancelPayment(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'time-to-pay' and self.isOkToContinue(*args, **kwargs):
                self.state = 'MY_COIN!'
                self.doSendNextCoin(*args, **kwargs)
            elif event == 'time-to-pay' and not self.isOkToContinue(*args, **kwargs):
                self.state = 'MY_COIN!'
                self.doSendLastCoin(*args, **kwargs)
            elif event == 'supplier-failed':
                self.state = 'MY_COIN!'
                self.doCancelPayment(*args, **kwargs)
                self.doSendLastCoin(*args, **kwargs)
                self.doReplaceSupplier(*args, **kwargs)
        #---SUPPLIER_COIN?---
        elif self.state == 'SUPPLIER_COIN?':
            if event == 'supplier-coin-mined':
                self.state = 'EXTENSION?'
                self.doRequestService(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-30min':
                self.state = 'UNCLEAR'
        #---EXTENSION?---
        elif self.state == 'EXTENSION?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'contract-extended':
                self.state = 'SUPERVISE'
                self.doSchedulePayment(*args, **kwargs)
                self.doSuperviseSupplier(*args, **kwargs)
            elif event == 'contract-finished' or event == 'timer-30sec':
                self.state = 'FINISHED'
                self.doSendFinishCoin(*args, **kwargs)
                self.doReplaceSupplier(*args, **kwargs)
        #---FINISHED---
        elif self.state == 'FINISHED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---MY_COIN!---
        elif self.state == 'MY_COIN!':
            if event == 'coin-published' and not self.isChainClosed(*args, **kwargs):
                self.state = 'SUPPLIER_COIN?'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'coin-failed':
                self.state = 'UNCLEAR'
            elif event == 'coin-published' and self.isChainClosed(*args, **kwargs):
                self.state = 'FINISHED'
                self.doSendFinishCoin(*args, **kwargs)
                self.doReplaceSupplier(*args, **kwargs)
        #---UNCLEAR---
        elif self.state == 'UNCLEAR':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'recheck':
                self.state = 'READ_COINS?'
                self.doRequestCoins(*args, **kwargs)
        return None

    def isOkToContinue(self, *args, **kwargs):
        """
        Condition method.
        """

    def isChainClosed(self, *args, **kwargs):
        """
        Condition method.
        """

    def doRequestCoins(self, *args, **kwargs):
        """
        Action method.
        """
        from coins import contract_chain_node
        contract_chain_node.get_coins_by_chain(
            chain='supplier_customer',
            provider_idurl=self.supplier_idurl,
            consumer_idurl=my_id.getLocalID(),
        ).addCallbacks(
            self._on_coins_received,
            self._on_coins_failed,
        )

    def doSuperviseSupplier(self, *args, **kwargs):
        """
        Action method.
        """
        #TODO: create supplier_supervisor() machine

    def doSchedulePayment(self, *args, **kwargs):
        """
        Action method.
        """

    def doCancelPayment(self, *args, **kwargs):
        """
        Action method.
        """

    def doRequestService(self, *args, **kwargs):
        """
        Action method.
        """

    def doReplaceSupplier(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendNextCoin(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendLastCoin(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendSuccessCoin(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendFailedCoin(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendFinishCoin(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()

    def _on_coins_received(self, coins):
        if _Debug:
            lg.out(_DebugLevel, 'customer_contract_executor._on_coins_received %s' % coins)
        if not coins:
            self.automat('')
            return

    def _on_coins_failed(self, fails):
        if _Debug:
            lg.warn(str(fails))
