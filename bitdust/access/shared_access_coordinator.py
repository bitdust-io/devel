#!/usr/bin/env python
# shared_access_coordinator.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
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

BitDust shared_access_coordinator() Automat

EVENTS:
    * :red:`all-suppliers-connected`
    * :red:`all-suppliers-disconnected`
    * :red:`dht-lookup-ok`
    * :red:`fail`
    * :red:`index-failed`
    * :red:`index-missing`
    * :red:`index-received`
    * :red:`index-sent`
    * :red:`index-up-to-date`
    * :red:`key-not-registered`
    * :red:`key-sent`
    * :red:`list-files-failed`
    * :red:`list-files-received`
    * :red:`list-files-verified`
    * :red:`new-private-key-registered`
    * :red:`restart`
    * :red:`shutdown`
    * :red:`supplier-connected`
    * :red:`supplier-failed`
    * :red:`supplier-file-modified`
    * :red:`timer-1min`
    * :red:`timer-30sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import time
import base64

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.system import bpio

from bitdust.lib import strng
from bitdust.lib import serialization
from bitdust.lib import packetid

from bitdust.main import events
from bitdust.main import settings
from bitdust.main import listeners

from bitdust.dht import dht_relations

from bitdust.p2p import commands
from bitdust.p2p import p2p_service
from bitdust.p2p import online_status

from bitdust.contacts import identitycache
from bitdust.contacts import contactsdb

from bitdust.crypt import my_keys
from bitdust.crypt import key
from bitdust.crypt import signed
from bitdust.crypt import encrypted

from bitdust.access import key_ring

from bitdust.storage import backup_control
from bitdust.storage import backup_matrix
from bitdust.storage import backup_fs

from bitdust.customer import supplier_connector

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_ActiveShares = {}
_ActiveSharesByIDURL = {}

#------------------------------------------------------------------------------


def register_share(A):
    global _ActiveShares
    global _ActiveSharesByIDURL
    if A.key_id in _ActiveShares:
        raise Exception('share already exist')
    if id_url.is_not_in(A.customer_idurl, _ActiveSharesByIDURL):
        _ActiveSharesByIDURL[A.customer_idurl] = []
    _ActiveSharesByIDURL[A.customer_idurl].append(A)
    _ActiveShares[A.key_id] = A


def unregister_share(A):
    global _ActiveShares
    global _ActiveSharesByIDURL
    _ActiveShares.pop(A.key_id, None)
    if id_url.is_not_in(A.customer_idurl, _ActiveSharesByIDURL):
        lg.warn('given customer idurl not found in active shares list')
    else:
        _ActiveSharesByIDURL[A.customer_idurl] = []


#------------------------------------------------------------------------------


def list_active_shares():
    global _ActiveShares
    return list(_ActiveShares.keys())


def get_active_share(key_id):
    global _ActiveShares
    if key_id not in _ActiveShares:
        return None
    return _ActiveShares[key_id]


def find_active_shares(customer_idurl):
    global _ActiveSharesByIDURL
    result = []
    for automat_index in _ActiveSharesByIDURL.values():
        A = automat.by_index(automat_index)
        if not A:
            continue
        if A.customer_idurl == customer_idurl:
            result.append(A)
    return result


#-----------------------------------------------------------------------------


def populate_shares():
    global _ActiveShares
    for share_instance in _ActiveShares.values():
        listeners.push_snapshot('shared_location', snap_id=share_instance.key_id, data=share_instance.to_json())


#------------------------------------------------------------------------------


def open_known_shares():
    to_be_opened = []
    to_be_cached = []
    for key_id in my_keys.known_keys():
        if not key_id.startswith('share_'):
            continue
        if not my_keys.is_key_private(key_id):
            continue
        if not my_keys.is_active(key_id):
            continue
        active_share = get_active_share(key_id)
        if active_share:
            continue
        to_be_opened.append(key_id)
        _, customer_idurl = my_keys.split_key_id(key_id)
        if not id_url.is_cached(customer_idurl):
            to_be_cached.append(customer_idurl)
    if _Debug:
        lg.args(_DebugLevel, to_be_opened=to_be_opened, to_be_cached=to_be_cached)
    if to_be_cached:
        d = identitycache.start_multiple(to_be_cached)
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='shared_access_coordinator.open_known_shares')
        d.addBoth(lambda _: start_known_shares(to_be_opened))
        return
    start_known_shares(to_be_opened)


def start_known_shares(to_be_opened):
    populate_shared_files = listeners.is_populate_required('shared_file')
    for key_id in to_be_opened:
        _, customer_idurl = my_keys.split_key_id(key_id)
        if not id_url.is_cached(customer_idurl):
            lg.err('not able to open share %r, customer IDURL %r still was not cached' % (key_id, customer_idurl))
            continue
        try:
            active_share = SharedAccessCoordinator(key_id, log_events=True, publish_events=False)
        except:
            lg.exc()
            continue
        active_share.automat('restart')
        if populate_shared_files:
            backup_fs.populate_shared_files(key_id=key_id)
    if listeners.is_populate_required('shared_location'):
        populate_shares()


#------------------------------------------------------------------------------


def get_deleted_path_ids(customer_idurl, key_alias):
    key_id = global_id.MakeGlobalID(idurl=customer_idurl, key_alias=key_alias)
    if not my_keys.is_key_registered(key_id):
        return []
    if not my_keys.is_active(key_id):
        return []
    active_share = get_active_share(key_id)
    if not active_share:
        return []
    if _Debug:
        lg.args(_DebugLevel, k=key_id, ret=active_share.files_to_be_deleted)
    return active_share.files_to_be_deleted


#------------------------------------------------------------------------------


def on_file_deleted(customer_idurl, key_alias, path_id):
    key_id = global_id.MakeGlobalID(idurl=customer_idurl, key_alias=key_alias)
    if _Debug:
        lg.args(_DebugLevel, k=key_id, path=path_id)
    if not my_keys.is_key_registered(key_id):
        return
    if not my_keys.is_active(key_id):
        return
    active_share = get_active_share(key_id)
    if not active_share:
        lg.warn('index file was updated and key is active, but share %s is not known' % key_id)
        return
    active_share.files_to_be_deleted.append(path_id)


def on_index_file_updated(customer_idurl, key_alias):
    key_id = global_id.MakeGlobalID(idurl=customer_idurl, key_alias=key_alias)
    if _Debug:
        lg.args(_DebugLevel, k=key_id)
    if not my_keys.is_key_registered(key_id):
        return
    if not my_keys.is_active(key_id):
        return
    active_share = get_active_share(key_id)
    if not active_share:
        lg.warn('index file was updated and key is active, but share %s is not known' % key_id)
        return
    if active_share.state == 'DISCONNECTED':
        active_share.automat('restart')
        return
    if active_share.state != 'CONNECTED':
        active_share.to_be_restarted = True
        return
    active_share.automat('restart')


def on_supplier_file_modified(evt):
    if evt.data['key_alias'] == 'master':
        return
    key_id = global_id.MakeGlobalID(idurl=evt.data['customer_idurl'], key_alias=evt.data['key_alias'])
    if _Debug:
        lg.args(_DebugLevel, e=evt, d=evt.data, k=key_id)
    if not my_keys.is_key_registered(key_id):
        return
    if not my_keys.is_active(key_id):
        return
    active_share = get_active_share(key_id)
    if not active_share:
        lg.warn('supplier file was modified and key is active, but share %s is not known' % key_id)
        return
    if active_share.state == 'DISCONNECTED':
        active_share.automat('restart')
        return
    # if active_share.state != 'CONNECTED':
    #     active_share.to_be_restarted = True
    active_share.automat('supplier-file-modified', supplier_idurl=evt.data['supplier_idurl'], remote_path=evt.data['remote_path'])


def on_key_registered(evt):
    if not evt.data['key_id'].startswith('share_'):
        return
    active_share = get_active_share(evt.data['key_id'])
    if _Debug:
        lg.args(_DebugLevel, e=evt, active_share=active_share)
    if active_share:
        active_share.automat('new-private-key-registered')
        return

    def _run_coordinator():
        new_share = SharedAccessCoordinator(
            key_id=evt.data['key_id'],
            log_events=True,
            publish_events=False,
        )
        new_share.add_connected_callback('key_registered' + strng.to_text(time.time()), lambda _id, _result: on_share_first_connected(evt.data['key_id'], _id, _result))
        new_share.automat('new-private-key-registered')

    glob_id = global_id.NormalizeGlobalID(evt.data['key_id'])
    if id_url.is_cached(glob_id['idurl']):
        _run_coordinator()
    else:
        d = identitycache.immediatelyCaching(glob_id['idurl'])
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='shared_access_coordinator.on_key_registered')
        d.addCallback(lambda *args: _run_coordinator())


def on_key_erased(evt):
    if not evt.data['key_id'].startswith('share_'):
        return
    from bitdust.access import shared_access_coordinator
    active_share = shared_access_coordinator.get_active_share(evt.data['key_id'])
    if _Debug:
        lg.args(_DebugLevel, e=evt, active_share=active_share)
    if active_share:
        active_share.automat('shutdown')


def on_share_connected(evt):
    if _Debug:
        lg.args(_DebugLevel, e=evt)


def on_share_first_connected(key_id, callback_id, result):
    if not result:
        return
    active_share = get_active_share(key_id)
    if _Debug:
        lg.args(_DebugLevel, key_id=key_id, result=result, active_share=active_share)
    if active_share:
        active_share.remove_connected_callback(callback_id)
        backup_fs.populate_shared_files(key_id=key_id)


def on_supplier_modified(evt):
    if _Debug:
        lg.args(_DebugLevel, e=evt)
    if evt.data['new_idurl']:
        my_keys_to_be_republished = []
        for key_id in my_keys.known_keys():
            if not key_id.startswith('share_'):
                continue
            _glob_id = global_id.NormalizeGlobalID(key_id)
            if _glob_id['idurl'].to_bin() == my_id.getIDURL().to_bin():
                # only send public keys of my own shares
                my_keys_to_be_republished.append(key_id)
        for key_id in my_keys_to_be_republished:
            d = key_ring.transfer_key(key_id, trusted_idurl=evt.data['new_idurl'], include_private=False, include_signature=False)
            d.addErrback(lambda *a: lg.err('transfer key failed: %s' % str(*a)))


def on_my_list_files_refreshed(evt):
    if _Debug:
        lg.args(_DebugLevel, e=evt)
    for key_id in list_active_shares():
        cur_share = get_active_share(key_id)
        if not cur_share:
            continue
        if cur_share.state == 'DISCONNECTED':
            cur_share.automat('restart')
            continue
        if cur_share.state != 'CONNECTED':
            continue
        if not cur_share.connected_last_time:
            cur_share.automat('restart')
            continue
        if time.time() - cur_share.connected_last_time < 60:
            continue
        cur_share.automat('restart')


def on_list_files_verified(newpacket, list_files_info):
    incoming_key_id = list_files_info['key_id']
    # incoming_key_alias = list_files_info['key_alias']
    active_share = get_active_share(incoming_key_id)
    if not active_share:
        lg.warn('active share was not found for incoming key %r' % incoming_key_id)
        return False
    if active_share.state == 'DISCONNECTED':
        lg.warn('active share is currently disconnect for incoming key %r, restarting' % incoming_key_id)
        active_share.automat('restart')
        return False
    try:
        block = encrypted.Unserialize(
            newpacket.Payload,
            decrypt_key=incoming_key_id,
        )
    except:
        lg.exc(newpacket.Payload)
        return False
    if block is None:
        lg.warn('failed reading data from %s' % newpacket.RemoteID)
        return False
    try:
        raw_files = block.Data()
    except:
        lg.exc()
        return False
    # otherwise this must be an external supplier sending us a files he stores for trusted customer
    external_supplier_idurl = block.CreatorID
    #     supplier_index_file_revision = active_share.received_index_file_revision.get(external_supplier_idurl)
    #     if supplier_index_file_revision:
    #         _rev = backup_fs.revision(customer_idurl=active_share.customer_idurl, key_alias=incoming_key_alias)
    #         if supplier_index_file_revision <= _rev:
    #             lg.warn('shared location index file is not in sync, local revision is %r but revision by supplier is %r' % (_rev, supplier_index_file_revision))
    #             return False
    try:
        supplier_raw_list_files = backup_control.UnpackListFiles(raw_files, settings.ListFilesFormat())
    except:
        lg.exc()
        return False
    # need to detect supplier position from the list of packets
    # and place that supplier on the correct position in contactsdb
    supplier_pos = backup_matrix.DetectSupplierPosition(supplier_raw_list_files)
    known_supplier_pos = contactsdb.supplier_position(external_supplier_idurl, active_share.customer_idurl)
    if known_supplier_pos < 0:
        lg.warn('received %r from an unknown node %r which is not a supplier of %r' % (newpacket, external_supplier_idurl, active_share.customer_idurl))
        return False
    if _Debug:
        lg.args(_DebugLevel, sz=len(supplier_raw_list_files), s=external_supplier_idurl, pos=supplier_pos, known_pos=known_supplier_pos, pid=newpacket.PacketID)
    if supplier_pos >= 0:
        if known_supplier_pos != supplier_pos:
            lg.err('known external supplier %r position %d is not matching with received list files position %d for customer %s' % (external_supplier_idurl, known_supplier_pos, supplier_pos, active_share.customer_idurl))
            return False
    else:
        lg.warn('not possible to detect external supplier position for customer %s from received list files, known position is %s' % (active_share.customer_idurl, known_supplier_pos))
        supplier_pos = known_supplier_pos
    active_share.automat(
        'list-files-verified',
        newpacket=newpacket,
        supplier_pos=supplier_pos,
        supplier_idurl=external_supplier_idurl,
        payload=supplier_raw_list_files,
    )
    # finally sending Ack() packet back
    p2p_service.SendAck(newpacket)
    return True


#------------------------------------------------------------------------------


class SharedAccessCoordinator(automat.Automat):

    """
    This class implements all the functionality of the ``shared_access_coordinator()`` state machine.
    """
    fast = False

    timers = {
        'timer-1min': (60, ['DHT_LOOKUP']),
        'timer-30sec': (30.0, ['SUPPLIERS?']),
    }

    def __init__(self, key_id, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Create shared_access_coordinator() state machine.
        Use this method if you need to call Automat.__init__() in a special way.
        """
        self.key_id = key_id
        self.glob_id = global_id.NormalizeGlobalID(self.key_id)
        self.key_alias = self.glob_id['key_alias']
        self.customer_idurl = self.glob_id['idurl']
        self.known_suppliers_list = []
        self.known_ecc_map = None
        self.critical_suppliers_number = 1
        self.dht_lookup_use_cache = True
        self.received_index_file_revision = {}
        self.last_time_in_sync = -1
        self.suppliers_in_progress = []
        self.suppliers_succeed = []
        self.to_be_restarted = False
        self.files_to_be_deleted = []
        self.connected_last_time = None
        super(SharedAccessCoordinator, self).__init__(
            name='%s$%s' % (self.key_alias, self.glob_id['customer']),
            state='AT_STARTUP',
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs,
        )

    def to_json(self):
        j = super().to_json()
        j.update(
            {
                'active': my_keys.is_active(self.key_id),
                'key_id': self.key_id,
                'alias': self.key_alias,
                'label': my_keys.get_label(self.key_id) or '',
                'creator': self.customer_idurl.to_id(),
                'suppliers': [id_url.idurl_to_id(s) for s in self.known_suppliers_list],
                'ecc_map': self.known_ecc_map,
                'revision': backup_fs.revision(self.customer_idurl, self.key_alias),
            }
        )
        return j

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

    def register(self):
        automat_index = automat.Automat.register(self)
        register_share(self)
        return automat_index

    def unregister(self):
        unregister_share(self)
        return automat.Automat.unregister(self)

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `shared_access_coordinator()` state were changed.
        """
        if _Debug:
            lg.out(_DebugLevel, '%s : [%s]->[%s]' % (self.name, oldstate, newstate))
        if newstate == 'CONNECTED':
            lg.info('share connected : %s' % self.key_id)
            self.connected_last_time = time.time()
            listeners.push_snapshot('shared_location', snap_id=self.key_id, data=self.to_json())
            self.files_to_be_deleted = []
            if self.to_be_restarted:
                self.to_be_restarted = False
                reactor.callLater(1, self.automat, 'restart')  # @UndefinedVariable
        elif newstate == 'DISCONNECTED' and oldstate != 'AT_STARTUP':
            lg.info('share disconnected : %s' % self.key_id)
            self.connected_last_time = None
            listeners.push_snapshot('shared_location', snap_id=self.key_id, data=self.to_json())
            if self.to_be_restarted:
                self.to_be_restarted = False
                reactor.callLater(1, self.automat, 'restart')  # @UndefinedVariable
        elif newstate in ['DHT_LOOKUP', 'SUPPLIERS?', 'CLOSED'] and oldstate != 'AT_STARTUP':
            listeners.push_snapshot('shared_location', snap_id=self.key_id, data=self.to_json())

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
            if event == 'dht-lookup-ok':
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
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'list-files-received':
                self.doSupplierSendIndexFile(*args, **kwargs)
            elif event == 'key-not-registered':
                self.doSupplierTransferPubKey(*args, **kwargs)
            elif event == 'supplier-connected' or event == 'key-sent':
                self.doSupplierRequestIndexFile(*args, **kwargs)
            elif event == 'index-sent' or event == 'index-up-to-date' or event == 'index-failed' or event == 'list-files-failed' or event == 'supplier-failed':
                self.doRemember(event, *args, **kwargs)
                self.doCheckAllConnected(*args, **kwargs)
            elif event == 'list-files-verified':
                self.doSupplierProcessListFiles(*args, **kwargs)
            elif event == 'supplier-file-modified' or event == 'index-received' or event == 'index-missing':
                self.doSupplierRequestListFiles(event, *args, **kwargs)
            elif (event == 'timer-30sec' and not self.isEnoughConnected(*args, **kwargs)) or event == 'all-suppliers-disconnected':
                self.state = 'DISCONNECTED'
                self.doReportDisconnected(*args, **kwargs)
            elif (event == 'timer-30sec' and self.isEnoughConnected(*args, **kwargs)) or event == 'all-suppliers-connected':
                self.state = 'CONNECTED'
                self.doReportConnected(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'restart':
                self.state = 'DHT_LOOKUP'
                self.doDHTLookupSuppliers(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'supplier-failed' or event == 'restart':
                self.state = 'DHT_LOOKUP'
                self.doDHTLookupSuppliers(*args, **kwargs)
            elif event == 'supplier-file-modified' or event == 'index-received' or event == 'index-missing':
                self.doSupplierRequestListFiles(event, *args, **kwargs)
            elif event == 'list-files-verified':
                self.doSupplierProcessListFiles(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isEnoughConnected(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, progress=len(self.suppliers_in_progress), succeed=self.suppliers_succeed, critical_suppliers_number=self.critical_suppliers_number)
        return len(self.suppliers_succeed) >= self.critical_suppliers_number

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        # TODO : put in a separate state in the state machine
        self.result_defer = kwargs.get('result_defer', None)
        identitycache.immediatelyCaching(self.customer_idurl, ignore_errors=True)

    def doDHTLookupSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_relations.read_customer_suppliers(self.customer_idurl, use_cache=self.dht_lookup_use_cache)
        # TODO: add more validations of dht_result
        d.addCallback(self._on_read_customer_suppliers)
        d.addErrback(lambda err: self.automat('fail', err))

    def doConnectCustomerSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            self.known_suppliers_list = [s for s in args[0]['suppliers'] if s]
        except:
            lg.exc()
            self.automat('all-suppliers-disconnected')
            return
        self.known_ecc_map = args[0].get('ecc_map')
        self.critical_suppliers_number = 1
        if self.known_ecc_map:
            from bitdust.raid import eccmap
            self.critical_suppliers_number = eccmap.GetCorrectableErrors(eccmap.GetEccMapSuppliersNumber(self.known_ecc_map))
        self.suppliers_in_progress.clear()
        self.suppliers_succeed.clear()
        for supplier_idurl in self.known_suppliers_list:
            self.suppliers_in_progress.append(id_url.field(supplier_idurl))
            if id_url.is_cached(supplier_idurl):
                self._do_connect_with_supplier(supplier_idurl)
            else:
                d = identitycache.immediatelyCaching(supplier_idurl)
                d.addCallback(lambda *a: self._do_connect_with_supplier(supplier_idurl))
                d.addErrback(self._on_supplier_failed, supplier_idurl=kwargs['supplier_idurl'], reason='failed caching supplier identity')
        if _Debug:
            lg.args(_DebugLevel, known_ecc_map=self.known_ecc_map, known_suppliers_list=self.known_suppliers_list)

    def doSupplierRequestIndexFile(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_retrieve_index_file(kwargs['supplier_idurl'])

    def doSupplierRequestListFiles(self, event, *args, **kwargs):
        """
        Action method.
        """
        supplier_idurl = id_url.field(kwargs['supplier_idurl'])
        pkt_out = None
        if event == 'supplier-file-modified':
            remote_path = kwargs['remote_path']
            if remote_path == settings.BackupIndexFileName() or packetid.IsIndexFileName(remote_path):
                if self.state == 'CONNECTED':
                    self.automat('restart')
                else:
                    self.to_be_restarted = True
            else:
                _, remote_path, _, _ = packetid.SplitVersionFilename(remote_path)
                iter_path = backup_fs.WalkByID(remote_path, iterID=backup_fs.fsID(self.customer_idurl, self.key_alias))
                if not iter_path:
                    lg.warn('did not found modified file %r in the catalog, restarting %r' % (kwargs['remote_path'], self))
                    self.automat('restart')
                else:
                    sc = supplier_connector.by_idurl(
                        supplier_idurl,
                        customer_idurl=self.customer_idurl,
                    )
                    if sc is not None and sc.state == 'CONNECTED':
                        pkt_out = p2p_service.SendListFiles(
                            target_supplier=supplier_idurl,
                            customer_idurl=self.customer_idurl,
                            key_id=self.key_id,
                            timeout=settings.P2PTimeOut(),
                            callbacks={
                                commands.Files(): lambda r, i: self._on_list_files_response(r, i, self.customer_idurl, supplier_idurl, self.key_id),
                                commands.Fail(): lambda r, i: self._on_list_files_failed(r, i, self.customer_idurl, supplier_idurl, self.key_id),
                                None: lambda pkt_out: self._on_list_files_timeout(self.customer_idurl, supplier_idurl, self.key_id),
                            },
                        )
        else:
            pkt_out = p2p_service.SendListFiles(
                target_supplier=supplier_idurl,
                customer_idurl=self.customer_idurl,
                key_id=self.key_id,
                timeout=settings.P2PTimeOut(),
                callbacks={
                    commands.Files(): lambda r, i: self._on_list_files_response(r, i, self.customer_idurl, supplier_idurl, self.key_id),
                    commands.Fail(): lambda r, i: self._on_list_files_failed(r, i, self.customer_idurl, supplier_idurl, self.key_id),
                    None: lambda pkt_out: self._on_list_files_timeout(self.customer_idurl, supplier_idurl, self.key_id),
                },
            )
        if _Debug:
            lg.args(_DebugLevel, e=event, s=supplier_idurl, outgoing=pkt_out)

    def doSupplierTransferPubKey(self, *args, **kwargs):
        """
        Action method.
        """
        d = key_ring.transfer_key(kwargs['key_id'], kwargs['supplier_idurl'], include_private=False, include_signature=False)
        d.addCallback(lambda r: self._on_key_transfer_success(**kwargs))
        d.addErrback(self._on_supplier_failed, supplier_idurl=kwargs['supplier_idurl'], reason='failed sending key %r' % kwargs['key_id'])

    def doSupplierSendIndexFile(self, *args, **kwargs):
        """
        Action method.
        """
        supplier_index_file_revision = self.received_index_file_revision.get(kwargs['supplier_idurl'])
        if supplier_index_file_revision:
            _rev = backup_fs.revision(customer_idurl=self.customer_idurl, key_alias=self.key_alias)
            if _Debug:
                lg.args(_DebugLevel, s=kwargs['supplier_idurl'], supplier_rev=supplier_index_file_revision, my_rev=_rev)
            if supplier_index_file_revision >= _rev:
                self.automat('index-up-to-date', supplier_idurl=kwargs['supplier_idurl'])
                return
        self._do_send_index_file(kwargs['supplier_idurl'])

    def doSupplierProcessListFiles(self, *args, **kwargs):
        """
        Action method.
        """
        is_in_sync = False
        supplier_index_file_revision = self.received_index_file_revision.get(kwargs['supplier_idurl'])
        if supplier_index_file_revision:
            _rev = backup_fs.revision(customer_idurl=self.customer_idurl, key_alias=self.key_alias)
            if supplier_index_file_revision <= _rev:
                is_in_sync = True
        if _Debug:
            lg.args(_DebugLevel, rev=supplier_index_file_revision, is_in_sync=is_in_sync)
        remote_files_changed, backups2remove, paths2remove, _ = backup_matrix.process_raw_list_files(
            supplier_num=kwargs['supplier_pos'],
            list_files_text_body=kwargs['payload'],
            customer_idurl=self.customer_idurl,
            is_in_sync=is_in_sync,
        )
        if remote_files_changed:
            backup_matrix.SaveLatestRawListFiles(
                supplier_idurl=kwargs['supplier_idurl'],
                raw_data=kwargs['payload'],
                customer_idurl=self.customer_idurl,
            )
            if _Debug:
                lg.dbg(_DebugLevel, 'received updated list of files from external supplier %s for customer %s' % (kwargs['supplier_idurl'], self.customer_idurl))
            if len(backups2remove) > 0:
                p2p_service.RequestDeleteListBackups(backups2remove)
                if _Debug:
                    lg.out(_DebugLevel, '    also sent requests to remove %d shared backups' % len(backups2remove))
            if len(paths2remove) > 0:
                p2p_service.RequestDeleteListPaths(paths2remove)
                if _Debug:
                    lg.out(_DebugLevel, '    also sent requests to remove %d shared paths' % len(paths2remove))

    def doRemember(self, event, *args, **kwargs):
        """
        Action method.
        """
        supplier_idurl = id_url.field(kwargs['supplier_idurl'])
        if id_url.is_in(supplier_idurl, self.suppliers_in_progress):
            self.suppliers_in_progress.remove(supplier_idurl)
            if event in ['index-sent', 'index-up-to-date']:
                if supplier_idurl not in self.suppliers_succeed:
                    self.suppliers_succeed.append(supplier_idurl)
        if _Debug:
            lg.args(_DebugLevel, e=event, s=supplier_idurl, progress=len(self.suppliers_in_progress), succeed=len(self.suppliers_succeed))

    def doCheckAllConnected(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, progress=len(self.suppliers_in_progress), succeed=self.suppliers_succeed, critical_suppliers_number=self.critical_suppliers_number)
        if len(self.suppliers_in_progress) == 0:
            if len(self.suppliers_succeed) >= self.critical_suppliers_number:
                self.automat('all-suppliers-connected')
            else:
                self.automat('all-suppliers-disconnected')

    def doReportConnected(self, *args, **kwargs):
        """
        Action method.
        """
        self.dht_lookup_use_cache = True
        events.send('share-connected', data=dict(self.to_json()))
        if self.result_defer:
            self.result_defer.callback(True)
        for cb_id in list(self.connected_callbacks.keys()):
            cb = self.connected_callbacks.get(cb_id)
            if cb:
                cb(cb_id, True)
        if _Debug:
            lg.args(_DebugLevel, key_id=self.key_id, ecc_map=self.known_ecc_map)

    def doReportDisconnected(self, *args, **kwargs):
        """
        Action method.
        """
        self.dht_lookup_use_cache = False
        events.send('share-disconnected', data=dict(self.to_json()))
        if self.result_defer:
            self.result_defer.errback(Exception('disconnected'))
        for cb_id in list(self.connected_callbacks.keys()):
            if cb_id in self.connected_callbacks:
                cb = self.connected_callbacks[cb_id]
                cb(cb_id, False)
        if _Debug:
            lg.args(_DebugLevel, key_id=self.key_id, ecc_map=self.known_ecc_map)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.result_defer = None
        self.destroy()

    def _do_connect_with_supplier(self, supplier_idurl):
        if _Debug:
            lg.args(_DebugLevel, supplier_idurl=supplier_idurl, customer_idurl=self.customer_idurl)
        sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
        if sc is None:
            sc = supplier_connector.create(
                supplier_idurl=supplier_idurl,
                customer_idurl=self.customer_idurl,
                needed_bytes=0,  # we only want to read the data at the moment - requesting 0 bytes from the supplier
                key_id=self.key_id,
                queue_subscribe=True,
            )
        if sc.state in ['CONNECTED', 'QUEUE?']:
            self.automat('supplier-connected', supplier_idurl=supplier_idurl)
        else:
            sc.set_callback('shared_access_coordinator', self._on_supplier_connector_state_changed)
            sc.automat('connect')

    def _do_retrieve_index_file(self, supplier_idurl):
        packetID = global_id.MakeGlobalID(
            key_id=self.key_id,
            path=packetid.MakeIndexFileNamePacketID(),
        )
        sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
        if sc is None or sc.state != 'CONNECTED':
            lg.warn('supplier connector for %r is not found or offline' % supplier_idurl)
            self.automat('supplier-failed', supplier_idurl=supplier_idurl)
            return
        if online_status.isOffline(supplier_idurl):
            lg.warn('supplier %r is offline' % supplier_idurl)
            self.automat('supplier-failed', supplier_idurl=supplier_idurl)
            return
        public_test_sample = key.NewSessionKey(session_key_type=key.SessionKeyType())
        signed_test_sample = my_keys.sign(self.key_id, public_test_sample)
        json_payload = {
            't': base64.b64encode(public_test_sample),
            's': strng.to_text(signed_test_sample),
        }
        raw_payload = serialization.DictToBytes(json_payload, values_to_text=True)
        p2p_service.SendRetreive(
            ownerID=self.customer_idurl,
            creatorID=my_id.getIDURL(),
            packetID=packetID,
            remoteID=supplier_idurl,
            response_timeout=settings.P2PTimeOut(),
            payload=raw_payload,
            callbacks={
                commands.Data(): self._on_index_file_response,
                commands.Fail(): self._on_index_file_fail_received,
                None: lambda pkt_out: self._on_index_file_request_failed(supplier_idurl, self.customer_idurl, packetID),
                'failed': lambda pkt_out, errmsg: self._on_index_file_request_failed(supplier_idurl, self.customer_idurl, packetID),
            },
        )
        if _Debug:
            lg.args(_DebugLevel, pid=packetID, supplier=supplier_idurl)

    def _do_process_index_file(self, wrapped_packet, supplier_idurl):
        if not wrapped_packet or not wrapped_packet.Valid():
            lg.err('incoming Data() is not valid from supplier %r' % supplier_idurl)
            self.automat('supplier-failed', supplier_idurl=supplier_idurl)
            return
        if id_url.is_cached(supplier_idurl):
            self._do_read_index_file(wrapped_packet, supplier_idurl)
        else:
            d = identitycache.start_one(supplier_idurl)
            d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='shared_access_coordinator._do_process_index_file')
            d.addBoth(lambda _: self._do_read_index_file(wrapped_packet, supplier_idurl))

    def _do_read_index_file(self, wrapped_packet, supplier_idurl):
        supplier_revision = backup_control.IncomingSupplierBackupIndex(
            wrapped_packet,
            key_id=self.key_id,
            deleted_path_ids=self.files_to_be_deleted,
        )
        self.received_index_file_revision[supplier_idurl] = supplier_revision
        if _Debug:
            lg.dbg(_DebugLevel, 'received %s from %r with rev: %s' % (wrapped_packet, supplier_idurl, supplier_revision))
        self.automat('index-received', supplier_idurl=supplier_idurl)

    def _do_send_index_file(self, supplier_idurl):
        packetID = global_id.MakeGlobalID(
            key_id=self.key_id,
            path=packetid.MakeIndexFileNamePacketID(),
        )
        data = bpio.ReadBinaryFile(settings.BackupIndexFilePath(self.customer_idurl, self.key_alias))
        b = encrypted.Block(
            CreatorID=my_id.getIDURL(),
            BackupID=packetID,
            BlockNumber=0,
            SessionKey=key.NewSessionKey(session_key_type=key.SessionKeyType()),
            SessionKeyType=key.SessionKeyType(),
            LastBlock=True,
            Data=data,
            EncryptKey=self.key_id,
        )
        Payload = b.Serialize()
        sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
        if sc is None or sc.state != 'CONNECTED':
            lg.warn('supplier connector for %r is not found or offline' % supplier_idurl)
            self.automat('supplier-failed', supplier_idurl=supplier_idurl)
            return
        if online_status.isOffline(supplier_idurl):
            lg.warn('supplier %r is offline' % supplier_idurl)
            self.automat('supplier-failed', supplier_idurl=supplier_idurl)
            return
        p2p_service.SendData(
            raw_data=Payload,
            ownerID=self.customer_idurl,
            creatorID=my_id.getIDURL(),
            remoteID=supplier_idurl,
            packetID=packetID,
            callbacks={
                commands.Ack(): self._on_send_index_file_ack,
                commands.Fail(): self._on_send_index_file_ack,
            },
        )
        self.automat('index-sending', supplier_idurl=supplier_idurl)
        if _Debug:
            lg.args(_DebugLevel, pid=packetID, sz=len(data), supplier=supplier_idurl)

    def _on_supplier_failed(self, err, supplier_idurl, reason):
        lg.err('supplier %s failed with %r : %r' % (supplier_idurl, reason, err))
        self.automat('supplier-failed', supplier_idurl=supplier_idurl)
        return None

    def _on_read_customer_suppliers(self, dht_value):
        if _Debug:
            lg.args(_DebugLevel, dht_value=dht_value)
        if dht_value and isinstance(dht_value, dict) and len(dht_value.get('suppliers', [])) > 0:
            self.dht_lookup_use_cache = True
            self.automat('dht-lookup-ok', dht_value)
        else:
            self.dht_lookup_use_cache = False
            self.automat('fail', Exception('customer suppliers not found in DHT'))

    def _on_supplier_connector_state_changed(self, idurl, newstate, **kwargs):
        if _Debug:
            lg.out(_DebugLevel, 'shared_access_coordinator._supplier_connector_state_changed %s to %s, own state is %s' % (idurl, newstate, self.state))
        sc = supplier_connector.by_idurl(idurl, customer_idurl=self.customer_idurl)
        if sc:
            sc.remove_callback('shared_access_coordinator', self._on_supplier_connector_state_changed)
        if newstate == 'CONNECTED':
            self.automat('supplier-connected', supplier_idurl=idurl)

    def _on_list_files_response(self, response, info, customer_idurl, supplier_idurl, key_id):
        if _Debug:
            lg.args(_DebugLevel, response=response, customer_idurl=customer_idurl, supplier_idurl=supplier_idurl, key_id=key_id)
        self.automat('list-files-received', supplier_idurl=supplier_idurl, customer_idurl=customer_idurl, key_id=key_id)

    def _on_list_files_failed(self, response, info, customer_idurl, supplier_idurl, key_id):
        if strng.to_text(response.Payload) == 'key not registered':
            if _Debug:
                lg.dbg(_DebugLevel, 'supplier %r of customer %r do not possess public key %r yet, sending it now' % (supplier_idurl, customer_idurl, key_id))
            self.automat('key-not-registered', supplier_idurl=supplier_idurl, customer_idurl=customer_idurl, key_id=key_id)
            return None
        lg.err('failed requesting ListFiles() with %r for customer %r from supplier %r' % (key_id, customer_idurl, supplier_idurl))
        self.automat('list-files-failed', supplier_idurl=supplier_idurl, customer_idurl=customer_idurl, key_id=key_id)
        return None

    def _on_list_files_timeout(self, customer_idurl, supplier_idurl, key_id):
        lg.err('timeout requesting ListFiles() with %r for customer %r from supplier %r' % (key_id, customer_idurl, supplier_idurl))
        self.automat('list-files-failed', supplier_idurl=supplier_idurl, customer_idurl=customer_idurl, key_id=key_id)
        return None

    def _on_key_transfer_success(self, customer_idurl, supplier_idurl, key_id):
        if _Debug:
            lg.out(_DebugLevel, 'shared_access_coordinator._on_key_transfer_success public key %r shared to supplier %r of customer %r, now will send ListFiles() again' % (key_id, supplier_idurl, customer_idurl))
        self.automat('key-sent', supplier_idurl=supplier_idurl, customer_idurl=customer_idurl, key_id=key_id)

    def _on_index_file_response(self, newpacket, info):
        wrapped_packet = signed.Unserialize(newpacket.Payload)
        supplier_idurl = wrapped_packet.RemoteID if wrapped_packet else newpacket.CreatorID
        if _Debug:
            lg.args(_DebugLevel, sz=len(newpacket.Payload), s=supplier_idurl, i=info)
        if not wrapped_packet:
            lg.err('incoming Data() is not valid %r' % newpacket)
            self.automat('supplier-failed', supplier_idurl=supplier_idurl)
            return
        if not identitycache.HasKey(wrapped_packet.CreatorID):
            if _Debug:
                lg.dbg(_DebugLevel, ' will cache remote identity %s before processing incoming packet %s' % (wrapped_packet.CreatorID, wrapped_packet))
            d = identitycache.immediatelyCaching(wrapped_packet.CreatorID)
            d.addCallback(lambda _: self._do_process_index_file(wrapped_packet, supplier_idurl))
            d.addErrback(lambda err: lg.err('failed caching remote %s identity: %s' % (wrapped_packet.CreatorID, str(err))) and self.automat('supplier-failed', supplier_idurl=supplier_idurl))
            return
        self._do_process_index_file(wrapped_packet, supplier_idurl)

    def _on_index_file_fail_received(self, newpacket, info):
        if _Debug:
            lg.args(_DebugLevel, newpacket=newpacket)
        supplier_idurl = newpacket.CreatorID
        self.received_index_file_revision[supplier_idurl] = None
        if strng.to_text(newpacket.Payload) == 'key not registered':
            if _Debug:
                lg.dbg(_DebugLevel, 'supplier %r of customer %r do not possess public key %r yet, sending it now' % (supplier_idurl, self.customer_idurl, self.key_id))
            self.automat('key-not-registered', supplier_idurl=supplier_idurl, customer_idurl=self.customer_idurl, key_id=self.key_id)
            return None
        if _Debug:
            lg.out(_DebugLevel, 'shared_access_coordinator._on_index_file_fail_received %s from %r' % (newpacket, supplier_idurl))
        self.automat('index-missing', supplier_idurl=supplier_idurl)

    def _on_index_file_request_failed(self, supplier_idurl, customer_idurl, packet_id):
        if _Debug:
            lg.args(_DebugLevel, s=supplier_idurl, c=customer_idurl, pid=packet_id)
        self.received_index_file_revision[supplier_idurl] = None
        self.automat('index-failed', supplier_idurl=supplier_idurl)

    def _on_send_index_file_ack(self, newpacket, info):
        supplier_idurl = newpacket.CreatorID
        sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl=self.customer_idurl)
        if sc:
            sc.automat(newpacket.Command.lower(), newpacket)
        else:
            lg.warn('did not found supplier connector for %r' % supplier_idurl)
        if _Debug:
            lg.out(_DebugLevel, 'shared_access_coordinator._on_send_index_file_ack %s from %r' % (newpacket, supplier_idurl))
        if newpacket.Command == commands.Ack():
            self.automat('index-sent', supplier_idurl=supplier_idurl)
        else:
            self.automat('index-failed', supplier_idurl=supplier_idurl)
