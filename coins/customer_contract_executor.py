#!/usr/bin/env python
# customer_contract_executor.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
    * :red:`coins-received`
    * :red:`contract-extended`
    * :red:`contract-finished`
    * :red:`init`
    * :red:`my-coin-failed`
    * :red:`my-coin-sent`
    * :red:`recheck`
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

_ActiveContracts = dict()  # provides CustomerContractExecutor object by supplier idurl

#------------------------------------------------------------------------------

def all_contracts():
    """
    """
    global _ActiveContracts
    return _ActiveContracts


def init_contract(supplier_idurl):
    """
    """
    global _ActiveContracts
    if supplier_idurl in _ActiveContracts:
        lg.warn('this supplier already have a contract started')
        return _ActiveContracts[supplier_idurl]
    cce = CustomerContractExecutor(supplier_idurl)
    cce.automat('init')
    _ActiveContracts[supplier_idurl] = cce
    return _ActiveContracts[supplier_idurl]


def shutdown_contract(supplier_idurl):
    """
    """
    global _ActiveContracts
    if supplier_idurl not in _ActiveContracts:
        lg.warn('no contract started for given supplier')
        return False
    _ActiveContracts[supplier_idurl].automat('shutdown')
    _ActiveContracts.pop(supplier_idurl)
    return True


def get_contract(supplier_idurl):
    """
    """
    global _ActiveContracts
    if supplier_idurl not in _ActiveContracts:
        return None
    return _ActiveContracts[supplier_idurl]


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
        name = 'executor_%s' % nameurl.GetName(self.supplier_idurl)
        automat.Automat.__init__(self, name, 'AT_STARTUP', _DebugLevel, _Debug)

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READ_COINS?'
                self.doRequestCoins(arg)
        #---READ_COINS?---
        elif self.state == 'READ_COINS?':
            if event == 'coins-received':
                self.state = 'SUPERVISE'
                self.doSchedulePayment(arg)
                self.doSuperviseSupplier(arg)
            elif event == 'timer-1min':
                self.state = 'OBSCURE'
        #---SUPERVISE---
        elif self.state == 'SUPERVISE':
            if event == 'time-to-pay':
                self.state = 'NEW_COIN!'
                self.doSendSuccessCoin(arg)
            elif event == 'timer-5min':
                self.doSuperviseSupplier(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doCancelPayment(arg)
                self.doDestroyMe(arg)
            elif event == 'supplier-failed':
                self.state = 'FINISHED'
                self.doCancelPayment(arg)
                self.doSendFailedCoin(arg)
                self.doReplaceSupplier(arg)
        #---NEW_COIN!---
        elif self.state == 'NEW_COIN!':
            if event == 'my-coin-sent' and self.isOkToContinue(arg):
                self.state = 'SUPPLIER_COIN?'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'my-coin-failed':
                self.state = 'OBSCURE'
            elif event == 'my-coin-sent' and not self.isOkToContinue(arg):
                self.state = 'FINISHED'
                self.doSendFinishCoin(arg)
                self.doReplaceSupplier(arg)
        #---SUPPLIER_COIN?---
        elif self.state == 'SUPPLIER_COIN?':
            if event == 'supplier-coin-mined':
                self.state = 'EXTENSION?'
                self.doRequestExtension(arg)
            elif event == 'timer-30min':
                self.state = 'OBSCURE'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---EXTENSION?---
        elif self.state == 'EXTENSION?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'contract-extended':
                self.state = 'SUPERVISE'
                self.doSchedulePayment(arg)
                self.doSuperviseSupplier(arg)
            elif event == 'contract-finished' or event == 'timer-30sec':
                self.state = 'FINISHED'
                self.doSendFinishCoin(arg)
                self.doReplaceSupplier(arg)
        #---FINISHED---
        elif self.state == 'FINISHED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---OBSCURE---
        elif self.state == 'OBSCURE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'recheck':
                self.state = 'READ_COINS?'
                self.doRequestCoins(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isOkToContinue(self, arg):
        """
        Condition method.
        """

    def doRequestCoins(self, arg):
        """
        Action method.
        """
        from coins import contract_chain_node
        contract_chain_node.get_coins_by_chain(
            provider_idurl=self.supplier_idurl,
            consumer_idurl=my_id.getLocalID(),
        )

    def doSuperviseSupplier(self, arg):
        """
        Action method.
        """
        #TODO: create supplier_supervisor() machine

    def doSchedulePayment(self, arg):
        """
        Action method.
        """

    def doCancelPayment(self, arg):
        """
        Action method.
        """

    def doRequestExtension(self, arg):
        """
        Action method.
        """

    def doReplaceSupplier(self, arg):
        """
        Action method.
        """

    def doSendSuccessCoin(self, arg):
        """
        Action method.
        """

    def doSendFailedCoin(self, arg):
        """
        Action method.
        """

    def doSendFinishCoin(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()

