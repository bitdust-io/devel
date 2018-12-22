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
    * :red:`supplier-failed`
    * :red:`timer-10sec`
    * :red:`timer-1min`
    * :red:`timer-3sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from main import events

from dht import dht_relations

from userid import global_id

from p2p import p2p_service

from contacts import identitycache

from storage import backup_fs

from customer import supplier_connector

#------------------------------------------------------------------------------

_ActiveShares = {}
_ActiveSharesByIDURL = {}

#------------------------------------------------------------------------------

def register_share(A):
    """
    """
    global _ActiveShares
    global _ActiveSharesByIDURL
    if A.key_id in _ActiveShares:
        raise Exception('share already exist')
    if A.customer_idurl not in _ActiveSharesByIDURL:
        _ActiveSharesByIDURL[A.customer_idurl] = []
    _ActiveSharesByIDURL[A.customer_idurl].append(A)
    _ActiveShares[A.key_id] = A


def unregister_share(A):
    """
    """
    global _ActiveShares
    global _ActiveSharesByIDURL
    _ActiveShares.pop(A.key_id, None)
    if A.customer_idurl not in _ActiveSharesByIDURL:
        lg.warn('given customer idurl not found in active shares list')
    else:
        _ActiveSharesByIDURL[A.customer_idurl] = []

#------------------------------------------------------------------------------

def list_active_shares():
    """
    """
    global _ActiveShares
    return list(_ActiveShares.keys())

def get_active_share(key_id):
    """
    """
    global _ActiveShares
    if key_id not in _ActiveShares:
        return None
    return _ActiveShares[key_id]


def find_active_shares(customer_idurl):
    """
    """
    global _ActiveSharesByIDURL
    result = []
    for automat_index in _ActiveSharesByIDURL.values():
        A = automat.objects().get(automat_index, None)
        if not A:
            continue
        if A.customer_idurl == customer_idurl:
            result.append(A)
    return result

#-----------------------------------------------------------------------------


class SharedAccessCoordinator(automat.Automat):
    """
    This class implements all the functionality of the ``shared_access_coordinator()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['CONNECTED', 'DHT_LOOKUP']),
        'timer-3sec': (3.0, ['SUPPLIERS?']),
        'timer-10sec': (10.0, ['SUPPLIERS?', 'LIST_FILES?']),
    }

    def __init__(self,
                 key_id,
                 debug_level=_DebugLevel,
                 log_events=_Debug,
                 log_transitions=_Debug,
                 publish_events=False,
                 **kwargs):
        """
        Create shared_access_coordinator() state machine.
        Use this method if you need to call Automat.__init__() in a special way.
        """
        self.key_id = key_id
        self.glob_id = global_id.ParseGlobalID(self.key_id)
        self.customer_idurl = self.glob_id['idurl']
        self.known_suppliers_list = []
        super(SharedAccessCoordinator, self).__init__(
            name="%s$%s" % (self.glob_id['key_alias'], self.glob_id['user']),
            state='AT_STARTUP',
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

    def to_json(self):
        return {
            'key_id': self.key_id,
            'global_id': self.glob_id,
            'idurl': self.customer_idurl,
            'state': self.state,
            'suppliers': self.known_suppliers_list,
        }

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of shared_access_coordinator() machine.
        """
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

    def register(self):
        """
        """
        automat_index = automat.Automat.register(self)
        register_share(self)
        return automat_index

    def unregister(self):
        """
        """
        unregister_share(self)
        return automat.Automat.unregister(self)

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
            elif event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(arg)
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
            elif event == 'fail' or event == 'timer-1min':
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
            elif event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(arg)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(arg)
            elif event == 'timer-1min':
                self.doCheckReconnectSuppliers(arg)
            elif event == 'supplier-failed' or event == 'restart':
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
        # TODO:
        return True

    def isAnySupplierConnected(self, arg):
        """
        Condition method.
        """
        for supplier_idurl in self.known_suppliers_list:
            sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
            if sc is not None and sc.state == 'CONNECTED':
                return True
        return False

    def isAnyFilesShared(self, arg):
        """
        Condition method.
        """
        return backup_fs.HasChilds('', iter=backup_fs.fs(self.customer_idurl))

    def doInit(self, arg):
        """
        Action method.
        """
        # TODO : put in a seprate state in the state machine
        identitycache.immediatelyCaching(self.customer_idurl)

    def doDHTLookupSuppliers(self, arg):
        """
        Action method.
        """
        d = dht_relations.read_customer_suppliers(self.customer_idurl)
        # TODO: add more validations of dht_result
        d.addCallback(lambda dht_result: self.automat('dht-lookup-ok', dht_result))
        d.addErrback(lambda err: self.automat('fail', err))

    def doConnectCustomerSuppliers(self, arg):
        """
        Action method.
        """
        try:
            self.known_suppliers_list = [_f for _f in arg['suppliers'] if _f]
        except:
            lg.exc()
            return
        for supplier_idurl in self.known_suppliers_list:
            sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
            if sc is None:
                sc = supplier_connector.create(
                    supplier_idurl=supplier_idurl,
                    customer_idurl=self.customer_idurl,
                    # we only want to read the data at the moment,
                    # so requesting 0 bytes from that supplier
                    needed_bytes=0,
                    key_id=self.key_id,
                    queue_subscribe=False,
                )
            sc.set_callback('shared_access_coordinator', self._on_supplier_connector_state_changed)
            sc.automat('connect')

    def doRequestSupplierFiles(self, arg):
        """
        Action method.
        """
        p2p_service.SendListFiles(
            target_supplier=arg,
            customer_idurl=self.customer_idurl,
            key_id=self.key_id,
        )

    def doProcessCustomerListFiles(self, arg):
        """
        Action method.
        """

    def doCheckAllConnected(self, arg):
        """
        Action method.
        """
        for supplier_idurl in self.known_suppliers_list:
            sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
            if sc is None or sc.state != 'CONNECTED':
                return
        self.automat('all-suppliers-connected')

    def doCheckReconnectSuppliers(self, arg):
        """
        Action method.
        """
        # TODO:

    def doRequestRandomPacket(self, arg):
        """
        Action method.
        """
        # TODO: take random packet from random file that was shared and send RequestData() packet
        # to one of suppliers - this way we can be sure that shared data is available
        self.automat('ack')

    def doReportSuccess(self, arg):
        """
        Action method.
        """
        events.send('share-connected', dict(self.to_json()))
        if self.result_defer:
            self.result_defer.callback(True)

    def doReportDisconnected(self, arg):
        """
        Action method.
        """
        events.send('share-disconnected', dict(self.to_json()))
        if self.result_defer:
            self.result_defer.errback(Exception('disconnected'))

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.result_defer = None
        self.unregister()

    def _on_supplier_connector_state_changed(self, idurl, newstate):
        if _Debug:
            lg.out(_DebugLevel, 'shared_access_coordinator._supplier_connector_state_changed %s to %s, own state is %s' % (
                idurl, newstate, self.state))
        sc = supplier_connector.by_idurl(idurl)
        if sc:
            sc.remove_callback('shared_access_coordinator')
        if newstate == 'CONNECTED':
            self.automat('supplier-connected', idurl)
