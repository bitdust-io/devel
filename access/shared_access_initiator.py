#!/usr/bin/env python
# shared_access_initiator.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (shared_access_initiator.py) is part of BitDust Software.
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
.. module:: shared_access_initiator
.. role:: red

BitDust shared_access_initiator() Automat

EVENTS:
    * :red:`ack`
    * :red:`all-suppliers-acked`
    * :red:`fail`
    * :red:`init`
    * :red:`timer-10sec`
    * :red:`timer-5sec`
"""


from automats import automat


class SharedAccessInitiator(automat.Automat):
    """
    This class implements all the functionality of the ``shared_access_initiator()`` state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['PUB_KEY']),
        'timer-5sec': (5.0, ['PING?','PRIV_KEY','VERIFY?']),
        }

    def __init__(self, state):
        """
        Create shared_access_initiator() state machine.
        Use this method if you need to call Automat.__init__() in a special way.
        """
        super(SharedAccessInitiator, self).__init__("shared_access_initiator", state)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of shared_access_initiator() machine.
        """

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when shared_access_initiator() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the shared_access_initiator()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'PING?'
                self.doSendMyIdentityToUser(arg)
        #---PING?---
        elif self.state == 'PING?':
            if event == 'ack':
                self.state = 'VERIFY?'
                self.doSendEncryptedSample(arg)
            elif event == 'fail' or event == 'timer-5sec':
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---PRIV_KEY---
        elif self.state == 'PRIV_KEY':
            if event == 'fail' or event == 'timer-5sec':
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'ack':
                self.state = 'PUB_KEY'
                self.doSendPubKeyToSuppliers(arg)
        #---PUB_KEY---
        elif self.state == 'PUB_KEY':
            if event == 'all-suppliers-acked' or event == 'timer-10sec':
                self.state = 'CLOSED'
                self.doReportDone(arg)
                self.doDestroyMe(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---VERIFY?---
        elif self.state == 'VERIFY?':
            if ( event == 'ack' and not self.isResponseValid(arg) ) or event == 'fail' or event == 'timer-5sec':
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'ack' and self.isResponseValid(arg):
                self.state = 'PRIV_KEY'
                self.doSendPrivKeyToUser(arg)


    def isResponseValid(self, arg):
        """
        Condition method.
        """

    def doReportDone(self, arg):
        """
        Action method.
        """

    def doSendPrivKeyToUser(self, arg):
        """
        Action method.
        """

    def doSendPubKeyToSuppliers(self, arg):
        """
        Action method.
        """

    def doSendEncryptedSample(self, arg):
        """
        Action method.
        """

    def doSendMyIdentityToUser(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()

    def doReportFailed(self, arg):
        """
        Action method.
        """

