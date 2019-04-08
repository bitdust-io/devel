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
        self.known_ecc_map = None
        super(SharedAccessCoordinator, self).__init__(
            name="%s$%s" % (self.glob_id['key_alias'][:10], self.glob_id['customer']),
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
            'ecc_map': self.known_ecc_map,
        }

    def add_connected_callback(self, callback_id, callback_method):
        self.connected_callbacks[callback_id] = callback_method

    def remove_connected_callback(self, callback_id):
        self.connected_callbacks.pop(callback_id, None)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of shared_access_coordinator() machine.
        """
        self.result_defer = None
        self.connected_callbacks = {}

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when shared_access_coordinator() state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
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

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'restart' or event == 'new-private-key-registered':
                self.state = 'DHT_LOOKUP'
                self.doInit(*args, **kwargs)
                self.doDHTLookupSuppliers(*args, **kwargs)
        #---DHT_LOOKUP---
        elif self.state == 'DHT_LOOKUP':
            if event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(*args, **kwargs)
            elif event == 'dht-lookup-ok':
                self.state = 'SUPPLIERS?'
                self.doConnectCustomerSuppliers(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'fail' or event == 'timer-1min':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
        #---SUPPLIERS?---
        elif self.state == 'SUPPLIERS?':
            if event == 'supplier-connected':
                self.doRequestSupplierFiles(*args, **kwargs)
                self.doCheckAllConnected(*args, **kwargs)
            elif event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-10sec':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
            elif ( event == 'all-suppliers-connected' or ( event == 'timer-3sec' and self.isAnySupplierConnected(*args, **kwargs) ) ) and not self.isAnyFilesShared(*args, **kwargs):
                self.state = 'LIST_FILES?'
            elif ( event == 'all-suppliers-connected' or ( event == 'timer-3sec' and self.isAnySupplierConnected(*args, **kwargs) ) ) and self.isAnyFilesShared(*args, **kwargs):
                self.state = 'CONNECTED'
                self.doReportConnected(*args, **kwargs)
        #---LIST_FILES?---
        elif self.state == 'LIST_FILES?':
            if event == 'supplier-connected':
                self.doRequestSupplierFiles(*args, **kwargs)
            elif event == 'customer-list-files-received':
                self.state = 'VERIFY?'
                self.doProcessCustomerListFiles(*args, **kwargs)
                self.doRequestRandomPacket(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-10sec':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
        #---VERIFY?---
        elif self.state == 'VERIFY?':
            if event == 'supplier-connected':
                self.doRequestSupplierFiles(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack' and self.isPacketValid(*args, **kwargs):
                self.state = 'CONNECTED'
                self.doReportConnected(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'fail' or ( event == 'ack' and not self.isPacketValid(*args, **kwargs) ):
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
            elif event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'restart':
                self.state = 'DHT_LOOKUP'
                self.doDHTLookupSuppliers(*args, **kwargs)
            elif event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'customer-list-files-received':
                self.doProcessCustomerListFiles(*args, **kwargs)
            elif event == 'timer-1min':
                self.doCheckReconnectSuppliers(*args, **kwargs)
            elif event == 'supplier-failed' or event == 'restart':
                self.state = 'DHT_LOOKUP'
                self.doDHTLookupSuppliers(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isPacketValid(self, *args, **kwargs):
        """
        Condition method.
        """
        # TODO:
        return True

    def isAnySupplierConnected(self, *args, **kwargs):
        """
        Condition method.
        """
        for supplier_idurl in self.known_suppliers_list:
            sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
            if sc is not None and sc.state == 'CONNECTED':
                return True
        return False

    def isAnyFilesShared(self, *args, **kwargs):
        """
        Condition method.
        """
        return backup_fs.HasChilds('', iter=backup_fs.fs(self.customer_idurl))

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        # TODO : put in a seprate state in the state machine
        self.result_defer = kwargs.get('result_defer', None) 
        identitycache.immediatelyCaching(self.customer_idurl)

    def doDHTLookupSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_relations.read_customer_suppliers(self.customer_idurl)
        # TODO: add more validations of dht_result
        d.addCallback(self._on_read_customer_suppliers)
        d.addErrback(lambda err: self.automat('fail', err))

    def doConnectCustomerSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            self.known_suppliers_list = [_f for _f in args[0]['suppliers'] if _f]
        except:
            lg.exc()
            return
        self.known_ecc_map = args[0].get('ecc_map')
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

    def doRequestSupplierFiles(self, *args, **kwargs):
        """
        Action method.
        """
        p2p_service.SendListFiles(
            target_supplier=args[0],
            customer_idurl=self.customer_idurl,
            key_id=self.key_id,
        )

    def doProcessCustomerListFiles(self, *args, **kwargs):
        """
        Action method.
        """

    def doCheckAllConnected(self, *args, **kwargs):
        """
        Action method.
        """
        for supplier_idurl in self.known_suppliers_list:
            sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
            if sc is None or sc.state != 'CONNECTED':
                return
        self.automat('all-suppliers-connected')

    def doCheckReconnectSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        # TODO:

    def doRequestRandomPacket(self, *args, **kwargs):
        """
        Action method.
        """
        # TODO: take random packet from random file that was shared and send RequestData() packet
        # to one of suppliers - this way we can be sure that shared data is available
        self.automat('ack')

    def doReportConnected(self, *args, **kwargs):
        """
        Action method.
        """
        events.send('share-connected', dict(self.to_json()))
        if self.result_defer:
            self.result_defer.callback(True)
        for cb_id in list(self.connected_callbacks.keys()):
            cb = self.connected_callbacks.get(cb_id)
            if cb:
                cb(cb_id, True)

    def doReportDisconnected(self, *args, **kwargs):
        """
        Action method.
        """
        events.send('share-disconnected', dict(self.to_json()))
        if self.result_defer:
            self.result_defer.errback(Exception('disconnected'))
        for cb_id in list(self.connected_callbacks.keys()):
            if cb_id in self.connected_callbacks:
                cb = self.connected_callbacks[cb_id]
                cb(cb_id, False)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.result_defer = None
        self.unregister()

    def _on_read_customer_suppliers(self, dht_value):
        if _Debug:
            lg.args(_DebugLevel, dht_value)
        if dht_value and isinstance(dht_value, dict) and len(dht_value.get('suppliers', [])) > 0:
            self.automat('dht-lookup-ok', dht_value)
        else:
            self.automat('fail', Exception('customers suppliers not found in DHT'))

    def _on_supplier_connector_state_changed(self, idurl, newstate, **kwargs):
        if _Debug:
            lg.out(_DebugLevel, 'shared_access_coordinator._supplier_connector_state_changed %s to %s, own state is %s' % (
                idurl, newstate, self.state))
        sc = supplier_connector.by_idurl(idurl)
        if sc:
            sc.remove_callback('shared_access_coordinator')
        if newstate == 'CONNECTED':
            self.automat('supplier-connected', idurl)
