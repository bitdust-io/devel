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
    * :red:`dht-lookup-ok`
    * :red:`fail`
    * :red:`new-private-key-registered`
    * :red:`restart`
    * :red:`shutdown`
    * :red:`supplier-connected`
    * :red:`timer-10sec`
    * :red:`timer-15sec`
    * :red:`timer-3sec`
"""

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from dht import dht_relations

from userid import global_id

from customer import supplier_connector

#------------------------------------------------------------------------------

class SharedAccessCoordinator(automat.Automat):
    """
    This class implements all the functionality of the ``shared_access_coordinator()`` state machine.
    """

    timers = {
        'timer-3sec': (3.0, ['SUPPLIERS?']),
        'timer-10sec': (10.0, ['SUPPLIERS?', 'LIST_FILES?']),
        'timer-15sec': (15.0, ['DHT_LOOKUP']),
    }

    def __init__(self, key_id, debug_level=0, log_events=False, publish_events=False, **kwargs):
        """
        Create shared_access_coordinator() state machine.
        Use this method if you need to call Automat.__init__() in a special way.
        """
        self.key_id = key_id
        glob_id = global_id.ParseGlobalID(self.key_id)
        self.customer_idurl = glob_id['idurl']
        super(SharedAccessCoordinator, self).__init__(
            name="shared_%s$%s" % (glob_id['key_alias'], glob_id['user']),
            state='AT_STARTUP',
            debug_level=debug_level,
            log_events=log_events,
            publish_events=publish_events,
            **kwargs
        )

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of shared_access_coordinator() machine.
        """
        self.suppliers_list = []
        self.result_defer = None

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
            if event == 'restart' or event == 'new-private-key-registered':
                self.state = 'DHT_LOOKUP'
                self.doInit(arg)
                self.doDHTLookupSuppliers(arg)
        #---SUPPLIERS?---
        elif self.state == 'SUPPLIERS?':
            if event == 'supplier-connected':
                self.doRequestSupplierFiles(arg)
                self.doCheckAllConnected(arg)
            elif event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'timer-10sec':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(arg)
            elif ( event == 'all-suppliers-connected' or ( event == 'timer-3sec' and self.isAnySupplierConnected(arg) ) ) and not self.isAnyFilesShared(arg):
                self.state = 'LIST_FILES?'
            elif ( event == 'all-suppliers-connected' or ( event == 'timer-3sec' and self.isAnySupplierConnected(arg) ) ) and self.isAnyFilesShared(arg):
                self.state = 'CONNECTED'
                self.doRequestRandomPacket(arg)
        #---LIST_FILES?---
        elif self.state == 'LIST_FILES?':
            if event == 'supplier-connected':
                self.doRequestSupplierFiles(arg)
            elif event == 'customer-list-files-received':
                self.state = 'VERIFY?'
                self.doProcessCustomerListFiles(arg)
                self.doRequestRandomPacket(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'timer-10sec':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(arg)
        #---VERIFY?---
        elif self.state == 'VERIFY?':
            if event == 'supplier-connected':
                self.doRequestSupplierFiles(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'ack' and self.isPacketValid(arg):
                self.state = 'CONNECTED'
                self.doReportSuccess(arg)
                self.doDestroyMe(arg)
            elif event == 'fail' or ( event == 'ack' and not self.isPacketValid(arg) ):
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(arg)
        #---DHT_LOOKUP---
        elif self.state == 'DHT_LOOKUP':
            if event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(arg)
            elif event == 'dht-lookup-ok':
                self.state = 'SUPPLIERS?'
                self.doConnectCustomerSuppliers(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'fail' or event == 'timer-15sec':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(arg)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'restart':
                self.state = 'DHT_LOOKUP'
                self.doDHTLookupSuppliers(arg)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'restart':
                self.state = 'DHT_LOOKUP'
                self.doDHTLookupSuppliers(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isPacketValid(self, arg):
        """
        Condition method.
        """

    def isAnySupplierConnected(self, arg):
        """
        Condition method.
        """

    def isAnyFilesShared(self, arg):
        """
        Condition method.
        """

    def doInit(self, arg):
        """
        Action method.
        """

    def doDHTLookupSuppliers(self, arg):
        """
        Action method.
        """
        d = dht_relations.scan_customer_supplier_relations(self.customer_idurl)
        d.addCallback(lambda result_list: self.automat('dht-lookup-ok', result_list))
        d.addErrback(lambda err: self.automat('fail', err))

    def doConnectCustomerSuppliers(self, arg):
        """
        Action method.
        """
        self.suppliers_list.extend(filter(None, arg))
        for supplier_idurl in self.suppliers_list:
            sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
            if sc is None:
                sc = supplier_connector.create(
                    supplier_idurl=supplier_idurl,
                    customer_idurl=self.customer_idurl,
                    needed_bytes=0,
                )
            sc.set_callback('shared_access_coordinator', self._on_supplier_connector_state_changed)
            # self.connect_list.append(supplier_idurl)
            sc.automat('connect')  # we only want to read the data, so requesting 0 bytes from that supplier

    def doRequestSupplierFiles(self, arg):
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

    def doReportDisconnected(self, arg):
        """
        Action method.
        """

    def doReportSuccess(self, arg):
        """
        Action method.
        """
        if self.result_defer:
            self.result_defer.callback(True)

    def doReportFailed(self, arg):
        """
        Action method.
        """
        if self.result_defer:
            self.result_defer.errback(Exception(arg))

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.result_defer = None
        self.unregister()

    def _on_supplier_connector_state_changed(self, idurl, newstate):
        lg.out(14, 'fire_hire._supplier_connector_state_changed %s to %s, own state is %s' % (
            idurl, newstate, self.state))
        supplier_connector.by_idurl(idurl).remove_callback('shared_access_coordinator')
        if newstate == 'CONNECTED':
            self.automat('supplier-connected', idurl)
