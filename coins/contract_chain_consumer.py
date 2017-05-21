#!/usr/bin/env python
# contract_chain_consumer.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (contract_chain_consumer.py) is part of BitDust Software.
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
.. module:: contract_chain_consumer
.. role:: red

BitDust contract_chain_consumer() Automat

EVENTS:
    * :red:`accountants-connected`
    * :red:`accountants-failed`
    * :red:`init`
    * :red:`miner-connected`
    * :red:`miner-failed`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-1min`
"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from twisted.internet import reactor

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from p2p import p2p_service
from p2p import p2p_service_seeker

#------------------------------------------------------------------------------

_ContractChainConsumer = None

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _ContractChainConsumer
    if event is None and arg is None:
        return _ContractChainConsumer
    if _ContractChainConsumer is None:
        # set automat name and starting state here
        _ContractChainConsumer = ContractChainConsumer('contract_chain_consumer', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _ContractChainConsumer.automat(event, arg)
    return _ContractChainConsumer

#------------------------------------------------------------------------------

class ContractChainConsumer(automat.Automat):
    """
    This class implements all the functionality of the ``contract_chain_consumer()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['MINER?', 'ACCOUNTANTS?']),
    }

    def __init__(self, state):
        """
        Create contract_chain_consumer() state machine.
        Use this method if you need to call Automat.__init__() in a special way.
        """
        super(ContractChainConsumer, self).__init__("contract_chain_consumer", state)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of contract_chain_consumer() machine.
        """
        self.accountants = []
        self.miner = None

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when contract_chain_consumer() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the contract_chain_consumer()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---MINER?---
        if self.state == 'MINER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'miner-connected':
                self.state = 'CONNECTED'
            elif event == 'stop' or event == 'timer-1min' or event == 'miner-failed':
                self.state = 'DISCONNECTED'
                self.doDisconnectAccountants(arg)
                self.doDisconnectMiner(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'DISCONNECTED'
                self.doInit(arg)
        #---ACCOUNTANTS?---
        elif self.state == 'ACCOUNTANTS?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop' or event == 'timer-1min' or event == 'accountants-failed':
                self.state = 'DISCONNECTED'
                self.doDisconnectAccountants(arg)
            elif event == 'accountants-connected':
                self.state = 'MINER?'
                self.doConnectMiner(arg)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'start':
                self.state = 'ACCOUNTANTS?'
                self.doConnectAccountants(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop':
                self.state = 'DISCONNECTED'
                self.doDisconnectAccountants(arg)
                self.doDisconnectMiner(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, arg):
        """
        Action method.
        """

    def doConnectAccountants(self, arg):
        """
        Action method.
        """
        self.accountant_lookups = 0
        self._lookup_next_accountant()

    def doDisconnectAccountants(self, arg):
        """
        Action method.
        """
        for idurl in self.accountants:
            p2p_service.SendCancelService(idurl, 'service_accountant')
        self.accountants = []

    def doConnectMiner(self, arg):
        """
        Action method.
        """
        self.miner_lookups = 0
        self._lookup_miner()

    def doDisconnectMiner(self, arg):
        """
        Action method.
        """
        if self.miner:
            p2p_service.SendCancelService(self.miner, 'service_miner')
        self.miner = None

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        automat.objects().pop(self.index)
        global _ContractChainConsumer
        del _ContractChainConsumer
        _ContractChainConsumer = None

    #------------------------------------------------------------------------------

    def _on_accountant_connected(self, idurl):
        if self.state != 'ACCOUNTANTS?':
            lg.warn('internal state was changed during accountant lookup, SKIP next lookup')
            return
        if idurl in self.accountants:
            lg.warn('node %s already connected as accountant')
        else:
            self.accountants.append(idurl)
        reactor.callLater(0, self._lookup_next_accountant)

    def _on_accountant_failed(self, x):
        if self.state != 'ACCOUNTANTS?':
            lg.warn('internal state was changed during accountant lookup, SKIP next lookup')
            return
        reactor.callLater(0, self._lookup_next_accountant)

    def _lookup_next_accountant(self):
        if len(self.accountants) > 3:  # TODO: read from settings.
            self.automat('accountants-connected')
            return
        if self.accountant_lookups > 10:  # TODO: read from settings.
            self.automat('accountants-failed')
            return
        self.accountant_lookups += 1
        p2p_service_seeker.connect_random_node(
            'service_accountant',
            service_params='read',
            exclude_nodes=self.accountants,
        ).addCallbacks(
            self._on_accountant_connected,
            self._on_accountant_failed,
        )

    def _on_miner_connected(self, idurl):
        self.miner = idurl
        self.automat('miner-connected')

    def _on_miner_failed(self, x):
        reactor.callLater(0, self._lookup_miner)

    def _lookup_miner(self):
        if self.miner_lookups > 3:  # TODO: read from settings.
            self.automat('miner-failed')
            return
        self.miner_lookups += 1
        p2p_service_seeker.connect_random_node('service_miner').addCallbacks(
            self._on_miner_connected,
            self._on_miner_failed,
        )
