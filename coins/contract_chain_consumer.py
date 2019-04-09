#!/usr/bin/env python
# contract_chain_consumer.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from p2p import p2p_service
from p2p import p2p_service_seeker

#------------------------------------------------------------------------------

_ContractChainConsumer = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _ContractChainConsumer
    if event is None and not args:
        return _ContractChainConsumer
    if _ContractChainConsumer is None:
        # set automat name and starting state here
        _ContractChainConsumer = ContractChainConsumer('contract_chain_consumer', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _ContractChainConsumer.automat(event, *args, **kwargs)
    return _ContractChainConsumer

#------------------------------------------------------------------------------

class ContractChainConsumer(automat.Automat):
    """
    This class implements all the functionality of the ``contract_chain_consumer()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['MINER?', 'ACCOUNTANTS?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of contract_chain_consumer() machine.
        """
        self.connected_accountants = []
        self.connected_miner = None

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://bitdust.io/visio2python/>`_ tool.
        """
        #---MINER?---
        if self.state == 'MINER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'miner-connected':
                self.state = 'CONNECTED'
            elif event == 'stop' or event == 'timer-1min' or event == 'miner-failed':
                self.state = 'DISCONNECTED'
                self.doDisconnectAccountants(*args, **kwargs)
                self.doDisconnectMiner(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'DISCONNECTED'
                self.doInit(*args, **kwargs)
        #---ACCOUNTANTS?---
        elif self.state == 'ACCOUNTANTS?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop' or event == 'timer-1min' or event == 'accountants-failed':
                self.state = 'DISCONNECTED'
                self.doDisconnectAccountants(*args, **kwargs)
            elif event == 'accountants-connected':
                self.state = 'MINER?'
                self.doConnectMiner(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'start':
                self.state = 'ACCOUNTANTS?'
                self.doConnectAccountants(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop':
                self.state = 'DISCONNECTED'
                self.doDisconnectAccountants(*args, **kwargs)
                self.doDisconnectMiner(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doConnectAccountants(self, *args, **kwargs):
        """
        Action method.
        """
        self.accountant_lookups = 0
        self._lookup_next_accountant()

    def doDisconnectAccountants(self, *args, **kwargs):
        """
        Action method.
        """
        for idurl in self.connected_accountants:
            p2p_service.SendCancelService(idurl, 'service_accountant')
        self.connected_accountants = []

    def doConnectMiner(self, *args, **kwargs):
        """
        Action method.
        """
        self.miner_lookups = 0
        self._lookup_miner()

    def doDisconnectMiner(self, *args, **kwargs):
        """
        Action method.
        """
        if self.connected_miner:
            p2p_service.SendCancelService(self.connected_miner, 'service_miner')
        self.connected_miner = None

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.unregister()
        global _ContractChainConsumer
        del _ContractChainConsumer
        _ContractChainConsumer = None

    #------------------------------------------------------------------------------

    def _on_accountant_lookup_finished(self, idurl):
        if self.state != 'ACCOUNTANTS?':
            lg.warn('internal state was changed during accountant lookup, SKIP next lookup')
            return None
        if not idurl:
            if _Debug:
                lg.out(_DebugLevel, 'contract_chain_consumer._on_accountant_lookup_finished with no results, try again')
            reactor.callLater(0, self._lookup_next_accountant)  # @UndefinedVariable
            return None
        if idurl in self.connected_accountants:
            lg.warn('node %s already connected as accountant')
        else:
            self.connected_accountants.append(idurl)
            if _Debug:
                lg.out(_DebugLevel, 'contract_chain_consumer._on_accountant_lookup_finished !!!!!!!! %s CONNECTED as new accountant' % idurl)
        reactor.callLater(0, self._lookup_next_accountant)  # @UndefinedVariable
        return None

    def _lookup_next_accountant(self):
        if len(self.connected_accountants) >= 3:  # TODO: read from settings.: max accountants
            if _Debug:
                lg.out(_DebugLevel, 'contract_chain_consumer._lookup_next_accountant SUCCESS, %d accountants connected' % len(self.connected_accountants))
            self.automat('accountants-connected')
            return
        if self.accountant_lookups >= 10:  # TODO: read from settings.
            if len(self.connected_accountants) >= 1:  # TODO: read from settings: min accountants
                if _Debug:
                    lg.out(_DebugLevel, 'contract_chain_consumer._lookup_next_accountant FAILED after %d retries, but %d accountants connected' % (
                        self.accountant_lookups, len(self.connected_accountants)))
                self.automat('accountants-connected')
                return
            if _Debug:
                lg.out(_DebugLevel, 'contract_chain_consumer._lookup_next_accountant FAILED after %d retries with no results' % self.accountant_lookups)
            self.automat('accountants-failed')
            return
        self.accountant_lookups += 1
        p2p_service_seeker.connect_random_node(
            'service_accountant',
            service_params={'action': 'read', },
            exclude_nodes=self.connected_accountants,
        ).addBoth(self._on_accountant_lookup_finished)

    def _on_miner_lookup_finished(self, idurl):
        if not idurl:
            if _Debug:
                lg.out(_DebugLevel, 'contract_chain_consumer._on_miner_lookup_finished with no results, try again')
            reactor.callLater(0, self._lookup_miner)  # @UndefinedVariable
            return None
        self.connected_miner = idurl
        if _Debug:
            lg.out(_DebugLevel, 'contract_chain_consumer._on_miner_lookup_finished SUCCESS, miner %s connected' % self.connected_miner)
        self.automat('miner-connected')

    def _lookup_miner(self):
        if self.miner_lookups >= 5:  # TODO: read value from settings
            if _Debug:
                lg.out(_DebugLevel, 'contract_chain_consumer._lookup_miner FAILED after %d retries' % self.miner_lookups)
            self.automat('miner-failed')
            return
        self.miner_lookups += 1
        p2p_service_seeker.connect_random_node('service_miner').addBoth(self._on_miner_lookup_finished)
