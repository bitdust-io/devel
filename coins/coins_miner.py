#!/usr/bin/env python
#coins_miner.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
.. module:: coins_miner
.. role:: red

BitDust coins_miner() Automat

EVENTS:
    * :red:`accountants-connected`
    * :red:`coin-confirmed`
    * :red:`coin-mined`
    * :red:`coin-rejected`
    * :red:`init`
    * :red:`lookup-failed`
    * :red:`new-job-received`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------ 

import random
import string
import json
import hashlib

#------------------------------------------------------------------------------ 

from automats import automat

from userid import my_id

#------------------------------------------------------------------------------ 

_CoinsMiner = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _CoinsMiner
    if event is None and arg is None:
        return _CoinsMiner
    if _CoinsMiner is None:
        # set automat name and starting state here
        _CoinsMiner = CoinsMiner('coins_miner', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _CoinsMiner.automat(event, arg)
    return _CoinsMiner

def Destroy():
    """
    Destroy the state machine and remove the instance from memory. 
    """
    global _CoinsMiner
    if _CoinsMiner is None:
        return
    _CoinsMiner.destroy()
    del _CoinsMiner
    _CoinsMiner = None

#------------------------------------------------------------------------------ 

class CoinsMiner(automat.Automat):
    """
    This class implements all the functionality of the ``coins_miner()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['PUBLISH_COIN','ACCOUNTANTS?']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of coins_miner() machine.
        """
        self.connected_accountants = []
        self.stopped = False

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(arg)
        elif self.state == 'READY':
            if event == 'stop':
                self.state = 'STOPPED'
            elif event == 'new-job-received':
                self.state = 'MINING'
                self.doStartMining(arg)
        elif self.state == 'MINING':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doStopMining(arg)
            elif event == 'coin-mined':
                self.state = 'PUBLISH_COIN'
                self.doSendCoinToAccountants(arg)
        elif self.state == 'STOPPED':
            if event == 'start':
                self.state = 'ACCOUNTANTS?'
                self.doLookupAccountants(arg)
        elif self.state == 'PUBLISH_COIN':
            if event == 'coin-confirmed':
                self.state = 'READY'
            elif event == 'stop':
                self.state = 'STOPPED'
            elif event == 'coin-rejected':
                self.state = 'MINING'
                self.doStartMining(arg)
        elif self.state == 'ACCOUNTANTS?':
            if event == 'stop' or event == 'lookup-failed':
                self.state = 'STOPPED'
            elif event == 'accountants-connected':
                self.state = 'READY'
        return None

    def doInit(self, arg):
        """
        Action method.
        """

    def doLookupAccountants(self, arg):
        """
        Action method.
        """
        # TODO :

    def doStartMining(self, arg):
        """
        Action method.
        """
        self.stopped = False

    def doStopMining(self, arg):
        """
        Action method.
        """
        self.stopped = True

    def doSendCoinToAccountants(self, arg):
        """
        Action method.
        """

    def _mining_process(self, data, difficulty):
        starter = ''.join([random.choice(string.uppercase+string.lowercase+string.digits) for _ in range(5)])    
        on = 0
        data_dump = json.dumps(data)
        while True:
            if self.stopped:
                return None
            check = starter + str(on)
            if data is not None:
                check += data_dump
            hexdigest = hashlib.sha1(check).hexdigest()
            if not hexdigest.startswith("1"*difficulty):
                continue
            return {
                "miner": my_id.getLocalID(),
                "starter": starter+str(on), 
                "hash": hexdigest,
                "data": data,
            }
