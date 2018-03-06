#!/usr/bin/env python
# shared_access_coordinator.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (shared_access_coordinator.py) is part of BitDust Software.
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
.. module:: shared_access_coordinator
.. role:: red

BitPie.NET shared_access_coordinator() Automat

EVENTS:
    * :red:`ack`
    * :red:`all-suppliers-connected`
    * :red:`customer-list-files-received`
    * :red:`fail`
    * :red:`private-key-received`
    * :red:`supplier-connected`
    * :red:`supplier-list-files-received`
    * :red:`timer-10sec`
    * :red:`timer-1sec`
"""

#------------------------------------------------------------------------------

from automats import automat

#------------------------------------------------------------------------------

class SharedAccessCoordinator(automat.Automat):
    """
    This class implements all the functionality of the ``shared_access_coordinator()`` state machine.
    """

    timers = {
        'timer-1sec': (1.0, ['SUPPLIERS?']),
        'timer-10sec': (10.0, ['SUPPLIERS?', 'LIST_FILES?', ]),
    }

    def __init__(self, state):
        """
        Create shared_access_coordinator() state machine.
        Use this method if you need to call Automat.__init__() in a special way.
        """
        super(SharedAccessCoordinator, self).__init__("shared_access_coordinator", state)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of shared_access_coordinator() machine.
        """

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when shared_access_coordinator() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the shared_access_coordinator()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'private-key-received':
                self.state = 'SUPPLIERS?'
                self.doConnectCustomerSuppliers(arg)
        #---SUPPLIERS?---
        elif self.state == 'SUPPLIERS?':
            if event == 'timer-10sec':
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'all-suppliers-connected' or ( event == 'timer-1sec' and self.isAnySuppliersConnected(arg) ):
                self.state = 'LIST_FILES?'
            elif event == 'supplier-list-files-received':
                self.doProcessSupplierListFile(arg)
            elif event == 'supplier-connected':
                self.doRequestSupplierListFiles(arg)
                self.doCheckAllConnected(arg)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---LIST_FILES?---
        elif self.state == 'LIST_FILES?':
            if event == 'timer-10sec':
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'supplier-connected':
                self.doRequestListFiles(arg)
            elif event == 'supplier-list-files-received':
                self.doProcessSupplierListFile(arg)
            elif event == 'customer-list-files-received':
                self.state = 'VERIFY?'
                self.doProcessCustomerListFiles(arg)
                self.doRequestRandomPacket(arg)
        #---SUCCESS---
        elif self.state == 'SUCCESS':
            pass
        #---VERIFY?---
        elif self.state == 'VERIFY?':
            if event == 'ack' and self.isPacketValid(arg):
                self.state = 'SUCCESS'
                self.doReportSuccess(arg)
                self.doDestroyMe(arg)
            elif event == 'fail' or ( event == 'ack' and not self.isPacketValid(arg) ):
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'supplier-list-files-received':
                self.doProcessSupplierListFile(arg)
        return None

    def isPacketValid(self, arg):
        """
        Condition method.
        """

    def isAnySuppliersConnected(self, arg):
        """
        Condition method.
        """

    def doConnectCustomerSuppliers(self, arg):
        """
        Action method.
        """

    def doRequestSupplierListFiles(self, arg):
        """
        Action method.
        """

    def doProcessSupplierListFile(self, arg):
        """
        Action method.
        """

    def doProcessCustomerListFiles(self, arg):
        """
        Action method.
        """

    def doCheckAllConnected(self, arg):
        """
        Action method.
        """

    def doRequestRandomPacket(self, arg):
        """
        Action method.
        """

    def doReportSuccess(self, arg):
        """
        Action method.
        """

    def doReportFailed(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()
