#!/usr/bin/env python
# customer_space.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (customer_space.py) is part of BitDust Software.
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
#
#
#
"""
.. module:: customer_space.

"""

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import time
import base64

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import strng
from bitdust.lib import packetid
from bitdust.lib import serialization
from bitdust.lib import jsn

from bitdust.system import bpio

from bitdust.main import settings
from bitdust.main import events

from bitdust.contacts import contactsdb

from bitdust.services import driver

from bitdust.p2p import p2p_service
from bitdust.p2p import commands

from bitdust.storage import accounting

from bitdust.crypt import signed
from bitdust.crypt import my_keys

from bitdust.transport import gateway
from bitdust.transport import callback

from bitdust.stream import p2p_queue

from bitdust.dht import dht_service
from bitdust.dht import dht_records
from bitdust.dht import known_nodes

from bitdust.supplier import list_files
from bitdust.supplier import local_tester

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_SupplierFileModifiedLatest = {}
_SupplierFileModifiedNotifyTasks = {}

#------------------------------------------------------------------------------


def init():
    callback.append_inbox_callback(on_inbox_packet_received)
    events.add_subscriber(on_identity_url_changed, 'identity-url-changed')
    events.add_subscriber(on_customer_accepted, 'existing-customer-accepted')
    events.add_subscriber(on_customer_accepted, 'new-customer-accepted')
    events.add_subscriber(on_customer_terminated, 'existing-customer-denied')
    events.add_subscriber(on_customer_terminated, 'existing-customer-terminated')
    space_dict, _ = accounting.read_customers_quotas()
    for customer_idurl in contactsdb.customers():
        known_customer_meta_info = contactsdb.get_customer_meta_info(customer_idurl)
        # yapf: disable
        events.send('existing-customer-accepted', data=dict(
            idurl=customer_idurl,
            allocated_bytes=space_dict.get(customer_idurl.to_bin()),
            ecc_map=known_customer_meta_info.get('ecc_map'),
            position=known_customer_meta_info.get('position'),
        ))
        # yapf: enable
    if driver.is_on('service_entangled_dht'):
        connect_suppliers_dht_layer()
    else:
        lg.warn('service service_entangled_dht is OFF')
    events.add_subscriber(on_dht_layer_connected, 'dht-layer-connected')


def shutdown():
    events.remove_subscriber(on_dht_layer_connected, 'dht-layer-connected')
    if driver.is_on('service_entangled_dht'):
        dht_service.suspend(layer_id=dht_records.LAYER_SUPPLIERS)
    events.remove_subscriber(on_customer_accepted, 'existing-customer-accepted')
    events.remove_subscriber(on_customer_accepted, 'new-customer-accepted')
    events.remove_subscriber(on_customer_terminated, 'existing-customer-denied')
    events.remove_subscriber(on_customer_terminated, 'existing-customer-terminated')
    events.remove_subscriber(on_identity_url_changed, 'identity-url-changed')
    callback.remove_inbox_callback(on_inbox_packet_received)


#------------------------------------------------------------------------------


def connect_suppliers_dht_layer():
    known_seeds = known_nodes.nodes()
    d = dht_service.open_layer(
        layer_id=dht_records.LAYER_SUPPLIERS,
        seed_nodes=known_seeds,
        connect_now=True,
        attach=True,
    )
    d.addCallback(on_suppliers_dht_layer_connected)
    d.addErrback(lambda *args: lg.err(str(args)))
    return d


#------------------------------------------------------------------------------


def register_customer_key(customer_public_key_id, customer_public_key):
    """
    Check/refresh/store customer public key locally.
    """
    if not customer_public_key_id or not customer_public_key:
        lg.warn('customer public key was not provided in the request')
        return False
    customer_public_key_id = my_keys.latest_key_id(customer_public_key_id)
    if my_keys.is_key_registered(customer_public_key_id):
        known_customer_public_key = my_keys.get_public_key_raw(customer_public_key_id)
        if known_customer_public_key == customer_public_key:
            lg.info('customer public key %r already known and public key is matching' % customer_public_key_id)
        else:
            lg.warn('rewriting customer public key %r' % customer_public_key_id)
            my_keys.erase_key(customer_public_key_id)
    key_id, key_object = my_keys.read_key_info(customer_public_key)
    if not my_keys.register_key(key_id, key_object):
        lg.err('failed to register customer public key: %r' % customer_public_key_id)
        return False
    lg.info('new customer public key registered: %r' % customer_public_key_id)
    return True


#------------------------------------------------------------------------------


def verify_ownership(newpacket, raise_exception=False):
    """
    At that point packet creator is already verified via signature,
    but creator could be not authorized to store data on that node.
    Based on owner ID, creator ID and packet ID decision must be made what to do with the packet.
    Returns customer IDURL and authorized IDURL of the user who should receive the Ack() or (None, None, ) if not authorized.
    """
    # SECURITY
    owner_idurl = newpacket.OwnerID
    creator_idurl = newpacket.CreatorID
    owner_id = owner_idurl.to_id()
    creator_id = creator_idurl.to_id()
    packet_key_alias, packet_owner_id, _ = packetid.SplitKeyOwnerData(newpacket.PacketID)
    customer_idurl = global_id.glob2idurl(packet_owner_id)
    packet_key_id = my_keys.latest_key_id(my_keys.make_key_id(packet_key_alias, creator_idurl, creator_glob_id=packet_owner_id))
    packet_key_id_registered = my_keys.is_key_registered(packet_key_id)
    if _Debug:
        lg.args(_DebugLevel, owner_id=owner_id, creator_id=creator_id, customer_id=packet_owner_id, key_registered=packet_key_id_registered)
    if newpacket.Command == commands.Data():
        if id_url.is_the_same(owner_idurl, creator_idurl):
            if contactsdb.is_customer(creator_idurl):
                if _Debug:
                    lg.dbg(_DebugLevel, 'OK, scenario 1: customer is sending own data to own supplier')
                return customer_idurl, creator_idurl
            if packet_key_id_registered:
                if _Debug:
                    lg.dbg(_DebugLevel, 'OK, scenario 10: data sender is not my customer but packet key is registered')
                return customer_idurl, creator_idurl
            lg.err('FAIL, scenario 6: data sender is not my customer and also packet key is not registered')
            if raise_exception:
                raise Exception('non-authorized user is trying to store data')
            return None, None
        if contactsdb.is_customer(creator_idurl):
            if _Debug:
                lg.dbg(_DebugLevel, 'OK, scenario 2: customer wants to store data for someone else on own supplier')
            # TODO: check that, why do we need that?
            return customer_idurl, creator_idurl
        if packet_owner_id == owner_id:
            if contactsdb.is_customer(owner_idurl):
                if packet_key_id_registered:
                    if _Debug:
                        lg.dbg(_DebugLevel, 'OK, scenario 3: another authorized user is sending data to customer to be stored on the supplier')
                    return customer_idurl, creator_idurl
        if _Debug:
            lg.dbg(_DebugLevel, 'non-authorized user is trying to store data on the supplier')
        return None, None
    if newpacket.Command in [commands.DeleteFile(), commands.DeleteBackup()]:
        if owner_idurl == creator_idurl:
            if contactsdb.is_customer(creator_idurl):
                if _Debug:
                    lg.dbg(_DebugLevel, 'OK, scenario 4: customer wants to remove already stored data on own supplier')
                return customer_idurl, creator_idurl
            lg.err('FAIL, scenario 7: non-authorized user is trying to erase data owned by customer from the supplier')
            if raise_exception:
                raise Exception('non-authorized user is trying to erase data owned by customer from the supplier')
            return None, None
        if contactsdb.is_customer(creator_idurl):
            # TODO: check that, why do we need that?
            if _Debug:
                lg.dbg(_DebugLevel, 'OK, scenario 8: customer wants to erase existing data that belongs to someone else but stored on the supplier')
            return customer_idurl, creator_idurl
        if packet_owner_id == owner_id:
            if contactsdb.is_customer(owner_idurl):
                if packet_key_id_registered:
                    if _Debug:
                        lg.dbg(_DebugLevel, 'OK, scenario 5: another authorized user wants to remove already stored data from the supplier')
                    return customer_idurl, creator_idurl
        lg.err('non-authorized user is trying to erase data on the supplier')
        return None, None
    if driver.is_enabled('service_proxy_server'):
        if _Debug:
            lg.dbg(_DebugLevel, 'IGNORE, scenario 9: received Data() was not authorized, but proxy router service is enabled')
        return None, None
    # TODO:
    # scenario 11: make possible to set "active" flag True/False for any key
    # this way customer can make virtual location available for other user but in read-only mode
    raise Exception('scenario not implemented yet, received %r' % newpacket)


#------------------------------------------------------------------------------


def make_filename(customerGlobID, filePath, keyAlias=None):
    keyAlias = keyAlias or 'master'
    customerDirName = str(customerGlobID)
    customersDir = settings.getCustomersFilesDir()
    if not os.path.exists(customersDir):
        if _Debug:
            lg.dbg(_DebugLevel, 'making a new folder: %s' % customersDir)
        bpio._dir_make(customersDir)
    ownerDir = os.path.join(customersDir, customerDirName)
    if not os.path.exists(ownerDir):
        if _Debug:
            lg.dbg(_DebugLevel, 'making a new folder: %s' % ownerDir)
        bpio._dir_make(ownerDir)
    keyAliasDir = os.path.join(ownerDir, keyAlias)
    if not os.path.exists(keyAliasDir):
        if _Debug:
            lg.dbg(_DebugLevel, 'making a new folder: %s' % keyAliasDir)
        bpio._dir_make(keyAliasDir)
    if packetid.IsIndexFileName(filePath):
        filePath = settings.BackupIndexFileName()
    filename = os.path.join(keyAliasDir, filePath)
    return filename


def make_valid_filename(customerIDURL, glob_path):
    """
    Must be a customer, and then we make full path filename for where this
    packet is stored locally.
    """
    keyAlias = glob_path['key_alias'] or 'master'
    filePath = glob_path['path']
    customerGlobID = glob_path['customer']
    if not customerGlobID:
        lg.warn('customer id is empty: %r' % glob_path)
        return ''
    if filePath != settings.BackupIndexFileName() and not packetid.IsIndexFileName(filePath):
        # SECURITY
        if not packetid.Valid(filePath):
            lg.warn('invalid file path')
            return ''
    filename = make_filename(customerGlobID, filePath, keyAlias)
    return filename


#------------------------------------------------------------------------------


def do_notify_supplier_file_modified(key_alias, remote_path, action, customer_idurl, authorized_idurl):
    global _SupplierFileModifiedNotifyTasks
    global _SupplierFileModifiedLatest
    task_id = '{}_{}${}'.format(action, key_alias, customer_idurl.to_id())
    latest_event_time = _SupplierFileModifiedLatest.get(task_id)
    current_task = _SupplierFileModifiedNotifyTasks.get(task_id)
    if not latest_event_time or (time.time() - latest_event_time > 60):
        if _Debug:
            lg.args(_DebugLevel, t=task_id, cur=current_task)
        if current_task:
            if not current_task.called and not current_task.cancelled:
                current_task.cancel()
            _SupplierFileModifiedNotifyTasks.pop(task_id)
        _SupplierFileModifiedLatest[task_id] = time.time()
        events.send('supplier-file-modified', data=dict(
            action=action,
            remote_path=remote_path,
            key_alias=key_alias,
            authorized_idurl=authorized_idurl,
            customer_idurl=customer_idurl,
            supplier_idurl=my_id.getIDURL(),
        ))
        return
    new_delay = latest_event_time + 60 + 1 - time.time()
    if _Debug:
        lg.args(_DebugLevel, t=task_id, delay=new_delay, cur=current_task)
    if current_task:
        if not current_task.called and not current_task.cancelled:
            current_task.cancel()
        _SupplierFileModifiedNotifyTasks.pop(task_id)
    _SupplierFileModifiedNotifyTasks[task_id] = reactor.callLater(  # @UndefinedVariable
        new_delay,
        do_notify_supplier_file_modified,
        key_alias,
        remote_path,
        action,
        customer_idurl,
        authorized_idurl,
    )


#------------------------------------------------------------------------------


def on_data(newpacket):
    if id_url.is_the_same(newpacket.OwnerID, my_id.getIDURL()):
        # this Data belong to us, SKIP
        return False
    # SECURITY
    # processing files from another customer
    glob_path = global_id.ParseGlobalID(newpacket.PacketID)
    if not glob_path['path']:
        # backward compatible check
        glob_path = global_id.ParseGlobalID(my_id.getGlobalID('master') + ':' + newpacket.PacketID)
    if not glob_path['path']:
        lg.err('got incorrect PacketID')
        # p2p_service.SendFail(newpacket, 'incorrect path')
        return False
    remote_path = glob_path['path']
    key_alias = glob_path['key_alias']
    customer_idurl, authorized_idurl = verify_ownership(newpacket)
    if authorized_idurl is None or customer_idurl is None:
        if _Debug:
            lg.dbg(_DebugLevel, 'ownership verification failed for %r' % newpacket)
        # p2p_service.SendFail(newpacket, 'ownership verification failed')
        return False
    filename = make_valid_filename(newpacket.OwnerID, glob_path)
    if not filename:
        lg.warn('got empty filename, bad customer or wrong packetID?')
        # p2p_service.SendFail(newpacket, 'empty filename')
        return False
    # dirname = os.path.dirname(filename)
    # if not os.path.exists(dirname):
    #     try:
    #         bpio._dirs_make(dirname)
    #     except:
    #         lg.err('can not create sub dir %s' % dirname)
    #         p2p_service.SendFail(newpacket, 'write error', remote_idurl=authorized_idurl)
    #         return False
    new_data = newpacket.Serialize()
    donated_bytes = settings.getDonatedBytes()
    accounting.check_create_customers_quotas(donated_bytes)
    space_dict, _ = accounting.read_customers_quotas()
    known_customers_quoats = list(space_dict.keys())
    if id_url.is_not_in(customer_idurl, known_customers_quoats, as_field=False, as_bin=True):
        lg.err('customer space is broken, no info about donated space can be found for %s' % newpacket)
        p2p_service.SendFail(newpacket, 'customer space is broken, no info found about donated space', remote_idurl=authorized_idurl)
        return False
    used_space_dict = accounting.read_customers_usage()
    known_customers_usage = list(used_space_dict.keys())
    if id_url.is_in(customer_idurl, known_customers_usage, as_field=False, as_bin=True):
        try:
            bytes_used_by_customer = int(used_space_dict[customer_idurl.to_bin()])
            bytes_donated_to_customer = int(space_dict[customer_idurl.to_bin()])
            if bytes_donated_to_customer - bytes_used_by_customer < len(new_data):
                lg.warn('no free space left for customer data for %s' % customer_idurl)
                p2p_service.SendFail(newpacket, 'no free space left for customer data', remote_idurl=authorized_idurl)
                return False
        except:
            lg.exc()
    data_existed = os.path.exists(filename)
    # data_changed = True
    # if data_exists:
    #     if remote_path == settings.BackupIndexFileName() or packetid.IsIndexFileName(remote_path):
    #         current_data = bpio.ReadBinaryFile(filename)
    #         if current_data == new_data:
    #             data_changed = False
    # if data_changed:
    if True:
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            try:
                bpio._dirs_make(dirname)
            except:
                lg.err('can not create sub dir %s' % dirname)
                p2p_service.SendFail(newpacket, 'write error', remote_idurl=authorized_idurl)
                return False
        if not bpio.WriteBinaryFile(filename, new_data):
            lg.err('can not write to %s' % str(filename))
            p2p_service.SendFail(newpacket, 'write error', remote_idurl=authorized_idurl)
            return False
    # Here Data() packet was stored as it is on supplier node (current machine)
    del new_data
    sz = len(newpacket.Payload)
    p2p_service.SendAck(newpacket, response=strng.to_text(sz), remote_idurl=authorized_idurl)
    reactor.callLater(0, local_tester.TestSpaceTime)  # @UndefinedVariable
    if key_alias != 'master':  # and data_changed:
        if remote_path == settings.BackupIndexFileName() or packetid.IsIndexFileName(remote_path):
            do_notify_supplier_file_modified(key_alias, settings.BackupIndexFileName(), 'write', customer_idurl, authorized_idurl)
        else:
            if packetid.BlockNumber(newpacket.PacketID) == 0:
                do_notify_supplier_file_modified(key_alias, remote_path, 'write', customer_idurl, authorized_idurl)
    if _Debug:
        lg.args(_DebugLevel, sz=sz, fn=filename, remote_idurl=authorized_idurl, pid=newpacket.PacketID, existed=data_existed)
    return True


def on_retrieve(newpacket):
    # external customer must be able to request
    # TODO: add validation of public key
    # if not contactsdb.is_customer(newpacket.OwnerID):
    #     lg.err("had unknown customer %s" % newpacket.OwnerID)
    #     p2p_service.SendFail(newpacket, 'not a customer')
    #     return False
    glob_path = global_id.ParseGlobalID(newpacket.PacketID)
    if not glob_path['path']:
        # backward compatible check
        glob_path = global_id.ParseGlobalID(my_id.getGlobalID('master') + ':' + newpacket.PacketID)
    if not glob_path['path']:
        lg.err('got incorrect PacketID')
        p2p_service.SendFail(newpacket, 'incorrect path', remote_idurl=newpacket.CreatorID)
        return False
    if not glob_path['idurl']:
        lg.warn('no customer global id found in PacketID: %s' % newpacket.PacketID)
        p2p_service.SendFail(newpacket, 'incorrect retrieve request', remote_idurl=newpacket.CreatorID)
        return False
    key_id = glob_path['key_id']
    recipient_idurl = newpacket.OwnerID
    if newpacket.CreatorID != glob_path['idurl'] and newpacket.CreatorID != newpacket.OwnerID:
        # SECURITY
        lg.warn('one of customers requesting a Data from another customer!')
        if not my_keys.is_key_registered(key_id):
            lg.warn('key %s is not registered' % key_id)
            p2p_service.SendFail(newpacket, 'key not registered', remote_idurl=newpacket.CreatorID)
            return False
        verified = False
        if _Debug:
            lg.args(_DebugLevel, Payload=newpacket.Payload)
        try:
            json_payload = serialization.BytesToDict(newpacket.Payload, keys_to_text=True, values_to_text=True)
            test_sample_bin = base64.b64decode(json_payload['t'])
            test_signature_bin = strng.to_bin(json_payload['s'])
            verified = my_keys.verify(key_id, test_sample_bin, test_signature_bin)
        except:
            lg.exc()
            return False
        if not verified:
            lg.warn('request is not authorized, test sample signature verification failed')
            return False
        # requester signed the test sample with the private key and we verified the signature with the public key
        # now we checked the signature of the test sample and can be sure that requester really possess the same key
        recipient_idurl = newpacket.CreatorID
    filename = make_valid_filename(newpacket.OwnerID, glob_path)
    if not filename:
        filename = make_valid_filename(glob_path['idurl'], glob_path)
        # if True:
        # TODO: settings.getCustomersDataSharingEnabled() and
        # SECURITY
        # TODO: add more validations for receiver idurl
        # recipient_idurl = glob_path['idurl']
        # filename = make_valid_filename(glob_path['idurl'], glob_path)
    if not filename:
        lg.warn('had empty filename')
        p2p_service.SendFail(newpacket, 'empty filename', remote_idurl=recipient_idurl)
        return False
    if not os.path.exists(filename):
        lg.warn('did not found requested file locally : %s' % filename)
        p2p_service.SendFail(newpacket, 'did not found requested file locally', remote_idurl=recipient_idurl)
        return False
    if not os.access(filename, os.R_OK):
        lg.warn('no read access to requested packet %s' % filename)
        p2p_service.SendFail(newpacket, 'failed reading requested file', remote_idurl=recipient_idurl)
        return False
    data = bpio.ReadBinaryFile(filename)
    if not data:
        lg.warn('empty data on disk %s' % filename)
        p2p_service.SendFail(newpacket, 'empty data on disk', remote_idurl=recipient_idurl)
        return False
    stored_packet = signed.Unserialize(data)
    sz = len(data)
    del data
    if stored_packet is None:
        lg.warn('Unserialize failed, not Valid packet %s' % filename)
        p2p_service.SendFail(newpacket, 'unserialize failed', remote_idurl=recipient_idurl)
        return False
    if not stored_packet.Valid():
        lg.warn('Stored packet is not Valid %s' % filename)
        p2p_service.SendFail(newpacket, 'stored packet is not valid', remote_idurl=recipient_idurl)
        return False
    if stored_packet.Command != commands.Data():
        lg.warn('sending back packet which is not a Data')
    # here Data() packet is sent back as it is...
    # that means outpacket.RemoteID=my_id.getIDURL() - it was addressed to that node and stored as it is
    # need to take that into account: every time you receive Data() packet
    # it can be not a new Data(), but the old data returning back as a response to Retreive() packet
    # to solve the issue we will create a new Data() packet
    # which will be addressed directly to recipient and "wrap" stored data inside it
    return_packet_id = stored_packet.PacketID
    if packetid.IsIndexFileName(glob_path['path']):
        return_packet_id = newpacket.PacketID
    payload = stored_packet.Serialize()
    return_packet = signed.Packet(
        Command=commands.Data(),
        OwnerID=stored_packet.OwnerID,
        CreatorID=my_id.getIDURL(),
        PacketID=return_packet_id,
        Payload=payload,
        RemoteID=recipient_idurl,
    )
    if _Debug:
        lg.args(_DebugLevel, file_size=sz, payload_size=len(payload), fn=filename, recipient=recipient_idurl)
    if recipient_idurl == stored_packet.OwnerID:
        if _Debug:
            lg.dbg(_DebugLevel, 'from request %r : sending back %r in %r to owner: %s' % (newpacket, stored_packet, return_packet, recipient_idurl))
        gateway.outbox(return_packet)
        return True
    if _Debug:
        lg.dbg(_DebugLevel, 'from request %r : returning data %r in %r owned by %s to %s' % (newpacket, stored_packet, return_packet, stored_packet.OwnerID, recipient_idurl))
    gateway.outbox(return_packet)
    return True


#------------------------------------------------------------------------------


def on_list_files(newpacket):
    json_query = {}
    try:
        j = serialization.BytesToDict(newpacket.Payload, keys_to_text=True, values_to_text=True)
        j['items'][0]
        json_query = j
    except:
        if strng.to_text(newpacket.Payload) == settings.ListFilesFormat():
            json_query = {
                'items': ['*'],
            }
    if json_query is None:
        lg.exc('unrecognized ListFiles() query received')
        return False
    # TODO: perform validations before sending back list of files
    list_files_global_id = global_id.ParseGlobalID(newpacket.PacketID)
    if list_files_global_id['key_id']:
        # customer id and data id can be recognized from packet id
        # return back list of files according to the request
        customer_idurl = list_files_global_id['idurl']
        key_id = list_files_global_id['key_id']
    else:
        # packet id format is unknown
        # by default returning back all files from that recipient if he is a customer
        customer_idurl = newpacket.OwnerID
        key_id = my_keys.make_key_id(alias='customer', creator_idurl=customer_idurl)
    key_id = my_keys.latest_key_id(key_id)
    list_files.send(
        customer_idurl=customer_idurl,
        packet_id=newpacket.PacketID,
        format_type=settings.ListFilesFormat(),
        key_id=key_id,
        remote_idurl=newpacket.OwnerID,  # send back to the requesting node
        query_items=json_query['items'],
    )
    if _Debug:
        lg.args(_DebugLevel, r=newpacket.OwnerID, c=customer_idurl, k=key_id, pid=newpacket.PacketID)
    return True


#------------------------------------------------------------------------------


def on_delete_file(newpacket):
    # TODO: call verify_ownership()
    # SECURITY
    if not newpacket.Payload:
        ids = [
            newpacket.PacketID,
        ]
    else:
        ids = strng.to_text(newpacket.Payload).split('\n')
    filescount = 0
    dirscount = 0
    lg.warn('going to erase files: %s' % ids)
    customer_id = global_id.UrlToGlobalID(newpacket.OwnerID)
    for pcktID in ids:
        glob_path = global_id.ParseGlobalID(pcktID)
        if not glob_path['customer']:
            glob_path = global_id.ParseGlobalID(customer_id + ':' + pcktID)
        if not glob_path['path']:
            lg.err('got incorrect PacketID')
            p2p_service.SendFail(newpacket, 'incorrect path')
            return False
        if customer_id != glob_path['customer']:
            # TODO: check that out if this actually suppose to be allowed
            lg.warn('trying to delete a file stored for another customer')
            continue
        # TODO: add validation of customerGlobID
        # TODO: process requests from another customer
        # SECURITY
        filename = make_valid_filename(newpacket.OwnerID, glob_path)
        if not filename:
            lg.warn('got empty filename, bad customer or wrong packetID?')
            p2p_service.SendFail(newpacket, 'not a customer, or file not found')
            return False
        if os.path.isfile(filename):
            try:
                os.remove(filename)
                filescount += 1
            except:
                lg.exc()
        elif os.path.isdir(filename):
            try:
                bpio._dir_remove(filename)
                dirscount += 1
            except:
                lg.exc()
        else:
            lg.warn('path was not found %s' % filename)
        do_notify_supplier_file_modified(glob_path['key_alias'], glob_path['path'], 'delete', newpacket.OwnerID, newpacket.CreatorID)
    p2p_service.SendAck(newpacket)
    if _Debug:
        lg.dbg(_DebugLevel, 'from [%s] with %d IDs, %d files and %d folders were removed' % (newpacket.OwnerID, len(ids), filescount, dirscount))
    return True


def on_delete_backup(newpacket):
    # TODO: call verify_ownership()
    # SECURITY
    if not newpacket.Payload:
        ids = [
            newpacket.PacketID,
        ]
    else:
        ids = strng.to_text(newpacket.Payload).split('\n')
    count = 0
    if _Debug:
        lg.args(_DebugLevel, ids=ids)
    customer_id = global_id.UrlToGlobalID(newpacket.OwnerID)
    for bkpID in ids:
        glob_path = global_id.ParseGlobalID(bkpID)
        if not glob_path['customer']:
            glob_path = global_id.ParseGlobalID(customer_id + ':' + bkpID)
        if not glob_path['path']:
            lg.err('got incorrect BackupID')
            p2p_service.SendFail(newpacket, 'incorrect backupID')
            return False
        if customer_id != glob_path['customer']:
            lg.warn('trying to delete file stored for another cusomer')
            continue
        # TODO: add validation of customerGlobID
        # TODO: process requests from another customer
        filename = make_valid_filename(newpacket.OwnerID, glob_path)
        if not filename:
            lg.warn('got empty filename, bad customer or wrong packetID?')
            p2p_service.SendFail(newpacket, 'not a customer, or file not found')
            return False
        if os.path.isdir(filename):
            try:
                bpio._dir_remove(filename)
                count += 1
            except:
                lg.exc()
        elif os.path.isfile(filename):
            try:
                os.remove(filename)
                count += 1
            except:
                lg.exc()
        else:
            if _Debug:
                lg.dbg(_DebugLevel, 'path not found %s' % filename)
        do_notify_supplier_file_modified(glob_path['key_alias'], glob_path['path'], 'delete', newpacket.OwnerID, newpacket.CreatorID)
    p2p_service.SendAck(newpacket)
    if _Debug:
        lg.dbg(_DebugLevel, 'from [%s] with %d IDs, %d were removed' % (newpacket.OwnerID, len(ids), count))
    return True


#------------------------------------------------------------------------------


def on_customer_accepted(evt):
    customer_idurl = id_url.field(evt.data.get('idurl'))
    if not customer_idurl:
        lg.warn('unknown customer idurl in event data payload')
        return False
    customer_glob_id = global_id.idurl2glob(customer_idurl)
    queue_id = global_id.MakeGlobalQueueID(
        queue_alias='supplier-file-modified',
        owner_id=customer_glob_id,
        supplier_id=my_id.getGlobalID(),
    )
    if not p2p_queue.is_queue_exist(queue_id):
        # customer_key_id = global_id.MakeGlobalID(customer=customer_glob_id, key_alias='customer')
        # if my_keys.is_key_registered(customer_key_id):
        # TODO: re-think again about the customer key, do we really need it?
        if True:
            try:
                p2p_queue.open_queue(queue_id)
            except Exception as exc:
                lg.warn('failed to open queue %s : %s' % (queue_id, str(exc)))
        # else:
        #     lg.warn('customer key %r for supplier queue not registered' % customer_key_id)
    if p2p_queue.is_queue_exist(queue_id):
        if not p2p_queue.is_producer_exist(my_id.getGlobalID()):
            try:
                p2p_queue.add_producer(my_id.getGlobalID())
            except Exception as exc:
                lg.warn('failed to add producer: %s' % str(exc))
        if p2p_queue.is_producer_exist(my_id.getGlobalID()):
            if not p2p_queue.is_producer_connected(my_id.getGlobalID(), queue_id):
                try:
                    p2p_queue.connect_producer(my_id.getGlobalID(), queue_id)
                except Exception as exc:
                    lg.warn('failed to connect producer: %s' % str(exc))
            if p2p_queue.is_producer_connected(my_id.getGlobalID(), queue_id):
                if not p2p_queue.is_event_publishing(my_id.getGlobalID(), 'supplier-file-modified'):
                    try:
                        p2p_queue.start_event_publisher(my_id.getGlobalID(), 'supplier-file-modified')
                    except Exception as exc:
                        lg.warn('failed to start event publisher: %s' % str(exc))
    if _Debug:
        lg.args(_DebugLevel, c=customer_glob_id, q=queue_id)
    return True


def on_customer_terminated(evt):
    customer_idurl = evt.data.get('idurl')
    if not customer_idurl:
        lg.warn('unknown customer idurl in event data payload')
        return False
    customer_glob_id = global_id.idurl2glob(customer_idurl)
    queue_id = global_id.MakeGlobalQueueID(
        queue_alias='supplier-file-modified',
        owner_id=customer_glob_id,
        supplier_id=my_id.getGlobalID(),
    )
    # TODO: need to decide when to stop producing
    # might be that other customers needs that info still
    if p2p_queue.is_event_publishing(my_id.getGlobalID(), 'supplier-file-modified'):
        try:
            p2p_queue.stop_event_publisher(my_id.getGlobalID(), 'supplier-file-modified')
        except Exception as exc:
            lg.warn('failed to stop event publisher: %s' % str(exc))
    if p2p_queue.is_producer_connected(my_id.getGlobalID(), queue_id):
        try:
            p2p_queue.disconnect_producer(my_id.getGlobalID(), queue_id)
        except Exception as exc:
            lg.warn('failed to disconnect producer: %s' % str(exc))
    if p2p_queue.is_producer_exist(my_id.getGlobalID()):
        try:
            p2p_queue.remove_producer(my_id.getGlobalID())
        except Exception as exc:
            lg.warn('failed to remove producer: %s' % str(exc))
    if p2p_queue.is_queue_exist(queue_id):
        try:
            p2p_queue.close_queue(queue_id)
        except Exception as exc:
            lg.warn('failed to stop queue %s : %s' % (queue_id, str(exc)))
    if _Debug:
        lg.args(_DebugLevel, c=customer_glob_id, q=queue_id)
    return True


#------------------------------------------------------------------------------


def on_identity_url_changed(evt):
    old_idurl = id_url.field(evt.data['old_idurl'])
    # update customer idurl in "space" file
    contacts_changed = False
    for customer_idurl in contactsdb.customers():
        if old_idurl == customer_idurl:
            customer_idurl.refresh()
            contacts_changed = True
            lg.info('found customer idurl rotated : %r -> %r' % (evt.data['old_idurl'], evt.data['new_idurl']))
            lg.admin('found customer %r idurl rotated to %r' % (evt.data['old_idurl'], evt.data['new_idurl']))
    if contacts_changed:
        contactsdb.save_customers()
    # update meta info for that customer
    meta_info_changed = False
    all_meta_info = contactsdb.read_customers_meta_info_all()
    for customer_idurl_bin in list(all_meta_info.keys()):
        if id_url.is_cached(old_idurl) and id_url.is_cached(customer_idurl_bin):
            if old_idurl == id_url.field(customer_idurl_bin):
                latest_customer_idurl_bin = id_url.field(customer_idurl_bin).to_bin()
                if latest_customer_idurl_bin != customer_idurl_bin:
                    all_meta_info[latest_customer_idurl_bin] = all_meta_info.pop(customer_idurl_bin)
                    meta_info_changed = True
                    lg.info('found customer idurl rotated in customers meta info : %r -> %r' % (latest_customer_idurl_bin, customer_idurl_bin))
    if meta_info_changed:
        contactsdb.write_customers_meta_info_all(all_meta_info)
    # update customer idurl in "space" file
    space_dict, free_space = accounting.read_customers_quotas()
    space_changed = False
    for customer_idurl_bin in list(space_dict.keys()):
        if id_url.is_cached(old_idurl) and id_url.is_cached(customer_idurl_bin):
            if id_url.field(customer_idurl_bin) == old_idurl:
                latest_customer_idurl_bin = id_url.field(customer_idurl_bin).to_bin()
                if latest_customer_idurl_bin != customer_idurl_bin:
                    space_dict[latest_customer_idurl_bin] = space_dict.pop(customer_idurl_bin)
                    space_changed = True
                    lg.info('found customer idurl rotated in customer quotas dictionary : %r -> %r' % (latest_customer_idurl_bin, customer_idurl_bin))
    if space_changed:
        accounting.write_customers_quotas(space_dict, free_space)
    # rename customer folder where I store all his files
    old_customer_dirname = str(global_id.UrlToGlobalID(evt.data['old_idurl']))
    new_customer_dirname = str(global_id.UrlToGlobalID(evt.data['new_idurl']))
    customers_dir = settings.getCustomersFilesDir()
    old_owner_dir = os.path.join(customers_dir, old_customer_dirname)
    new_owner_dir = os.path.join(customers_dir, new_customer_dirname)
    if os.path.isdir(old_owner_dir):
        try:
            bpio.move_dir_recursive(old_owner_dir, new_owner_dir)
            lg.info('copied %r into %r' % (old_owner_dir, new_owner_dir))
            if os.path.exists(old_owner_dir):
                bpio._dir_remove(old_owner_dir)
                lg.warn('removed %r' % old_owner_dir)
        except:
            lg.exc()
    # update customer idurl in "spaceused" file
    local_tester.TestSpaceTime()
    # TODO: reconnect "supplier-file-modified" consumers & producers
    return True


#------------------------------------------------------------------------------


def on_service_supplier_request(json_payload, newpacket, info):
    # SECURITY
    customer_idurl = newpacket.OwnerID
    customer_id = global_id.UrlToGlobalID(customer_idurl)
    bytes_for_customer = 0
    try:
        bytes_for_customer = int(json_payload['needed_bytes'])
    except:
        lg.exc()
        return p2p_service.SendFail(newpacket, 'invalid payload')
    try:
        customer_public_key = json_payload['customer_public_key']
        customer_public_key_id = customer_public_key['key_id']
    except:
        customer_public_key = None
        customer_public_key_id = None
    data_owner_idurl = None
    target_customer_idurl = None
    family_position = json_payload.get('position')
    ecc_map = json_payload.get('ecc_map')
    family_snapshot = json_payload.get('family_snapshot')
    if family_snapshot:
        family_snapshot = id_url.to_bin_list(family_snapshot)
    target_customer_id = json_payload.get('customer_id')
    key_id = my_keys.latest_key_id(json_payload.get('key_id'))
    if key_id:
        # this is a request from external user to access shared data stored by one of my customers
        # this is "second" customer requesting data from "first" customer
        if not key_id or not my_keys.is_valid_key_id(key_id):
            lg.warn('missed or invalid key id')
            return p2p_service.SendFail(newpacket, 'invalid key id')
        target_customer_idurl = global_id.GlobalUserToIDURL(target_customer_id)
        if not contactsdb.is_customer(target_customer_idurl):
            lg.warn('target user %s is not a customer' % target_customer_id)
            return p2p_service.SendFail(newpacket, 'not a customer')
        if target_customer_idurl == customer_idurl:
            lg.warn('customer %s requesting shared access to own files' % customer_idurl)
            return p2p_service.SendFail(newpacket, 'invalid case')
        if not my_keys.is_key_registered(key_id):
            lg.warn('key not registered: %s' % key_id)
            p2p_service.SendFail(newpacket, 'key not registered')
            return False
        data_owner_idurl = my_keys.split_key_id(key_id)[1]
        if not id_url.is_the_same(data_owner_idurl, target_customer_idurl) and not id_url.is_the_same(data_owner_idurl, customer_idurl):
            # pretty complex scenario:
            # external customer requesting access to data which belongs not to that customer
            # this is "third" customer accessing data belongs to "second" customer
            # TODO: for now just refuse it
            lg.warn('under construction, key_id=%s customer_idurl=%s target_customer_idurl=%s' % (key_id, customer_idurl, target_customer_idurl))
            p2p_service.SendFail(newpacket, 'under construction')
            return False
        register_customer_key(customer_public_key_id, customer_public_key)
        # do not create connection with that customer, only accept the request
        lg.info('external customer %s requested access to shared data at %s' % (customer_id, key_id))
        return p2p_service.SendAck(newpacket, 'accepted')
    # key_id is not present in the request:
    # this is a request to connect new customer (or reconnect existing one) to that supplier
    if not bytes_for_customer or bytes_for_customer < 0:
        lg.warn('wrong payload : %s' % newpacket.Payload)
        return p2p_service.SendFail(newpacket, 'wrong storage value')
    current_customers = contactsdb.customers()
    if accounting.check_create_customers_quotas():
        lg.info('created new customers quotas file')
    space_dict, free_space = accounting.read_customers_quotas()
    try:
        free_bytes = int(free_space)
    except:
        lg.exc()
        return p2p_service.SendFail(newpacket, 'broken quotas file')
    if (customer_idurl not in current_customers and customer_idurl.to_bin() in list(space_dict.keys())):
        lg.err('broken quotas file: %r is not a customer, but found in the quotas file' % customer_idurl.to_bin())
        return p2p_service.SendFail(newpacket, 'broken quotas file')
    if (customer_idurl in current_customers and customer_idurl.to_bin() not in list(space_dict.keys())):
        # seems like customer's idurl was rotated, but space file still have the old idurl
        # need to find that old idurl value and replace with the new one
        for other_customer_idurl in space_dict.keys():
            if other_customer_idurl and other_customer_idurl != 'free' and id_url.field(other_customer_idurl) == customer_idurl:
                lg.info('found rotated customer identity in space file, switching: %r -> %r' % (other_customer_idurl, customer_idurl.to_bin()))
                space_dict[customer_idurl.to_bin()] = space_dict.pop(other_customer_idurl)
                break
        if customer_idurl.to_bin() not in list(space_dict.keys()):
            lg.err('broken customers file: %r is a customer, but not found in the quotas file' % customer_idurl.to_bin())
            return p2p_service.SendFail(newpacket, 'broken customers file')
    # check/verify/create/update contract with requestor customer
    # the contracts are needed to keep track of consumed resources
    current_contract = {}
    if driver.is_on('service_supplier_contracts'):
        from bitdust.supplier import storage_contract
        try:
            current_contract = storage_contract.prepare_customer_contract(customer_idurl, details={
                'allocated_bytes': bytes_for_customer,
                'ecc_position': family_position,
                'ecc_map': ecc_map,
            })
        except:
            lg.exc()
            current_contract = {}
        if current_contract and current_contract.get('deny'):
            lg.warn('contract processing denied with user %s' % customer_idurl)
            # TODO: disabled for now...
            current_contract = {}
            # return p2p_service.SendFail(newpacket, 'deny:' + jsn.dumps(current_contract))
    # check if this is a new customer or an existing one
    # for existing one, we have to first release currently allocated resources
    if customer_idurl in current_customers:
        current_allocated_byes = int(space_dict.get(customer_idurl.to_bin(), 0))
        free_bytes += current_allocated_byes
        current_customers.remove(customer_idurl)
        space_dict.pop(customer_idurl.to_bin())
        new_customer = False
    else:
        new_customer = True
    # lg.args(8, new_customer=new_customer, current_allocated_bytes=space_dict.get(customer_idurl.to_bin()))
    if free_bytes <= bytes_for_customer:
        contactsdb.remove_customer_meta_info(customer_idurl)
        accounting.write_customers_quotas(space_dict, free_bytes)
        contactsdb.update_customers(current_customers)
        contactsdb.save_customers()
        if customer_public_key_id:
            my_keys.erase_key(customer_public_key_id)
        reactor.callLater(0, local_tester.TestUpdateCustomers)  # @UndefinedVariable
        if new_customer:
            lg.info('NEW CUSTOMER: DENIED     not enough space available')
            events.send('new-customer-denied', data=dict(idurl=customer_idurl))
        else:
            lg.info('OLD CUSTOMER: DENIED     not enough space available')
            events.send('existing-customer-denied', data=dict(idurl=customer_idurl))
            lg.admin('existing customer %s service denied because of not enough space available' % customer_idurl)
        return p2p_service.SendAck(newpacket, 'deny:{"reason": "not enough space available"}')
    free_bytes = free_bytes - bytes_for_customer
    current_customers.append(customer_idurl)
    space_dict[customer_idurl.to_bin()] = bytes_for_customer
    contactsdb.add_customer_meta_info(customer_idurl, {
        'ecc_map': ecc_map,
        'position': family_position,
        'family_snapshot': family_snapshot,
    })
    accounting.write_customers_quotas(space_dict, free_bytes)
    contactsdb.update_customers(current_customers)
    contactsdb.save_customers()
    register_customer_key(customer_public_key_id, customer_public_key)
    reactor.callLater(0, local_tester.TestUpdateCustomers)  # @UndefinedVariable
    if new_customer:
        lg.info('NEW CUSTOMER: ACCEPTED   %s family_position=%s ecc_map=%s allocated_bytes=%s' % (customer_idurl, family_position, ecc_map, bytes_for_customer))
        events.send(
            'new-customer-accepted', data=dict(
                idurl=customer_idurl,
                allocated_bytes=bytes_for_customer,
                ecc_map=ecc_map,
                position=family_position,
                family_snapshot=family_snapshot,
                key_id=customer_public_key_id,
                contract=current_contract,
            )
        )
        lg.admin('new customer %s service accepted' % customer_idurl)
    else:
        lg.info('EXISTING CUSTOMER: ACCEPTED  %s family_position=%s ecc_map=%s allocated_bytes=%s' % (customer_idurl, family_position, ecc_map, bytes_for_customer))
        events.send(
            'existing-customer-accepted', data=dict(
                idurl=customer_idurl,
                allocated_bytes=bytes_for_customer,
                ecc_map=ecc_map,
                position=family_position,
                key_id=customer_public_key_id,
                family_snapshot=family_snapshot,
                contract=current_contract,
            )
        )
    if current_contract:
        return p2p_service.SendAck(newpacket, 'accepted:' + jsn.dumps(current_contract))
    return p2p_service.SendAck(newpacket, 'accepted')


def on_service_supplier_cancel(json_payload, newpacket, info):
    customer_idurl = newpacket.OwnerID
    try:
        customer_public_key = json_payload['customer_public_key']
        customer_public_key_id = customer_public_key['key_id']
    except:
        customer_public_key = None
        customer_public_key_id = None
    customer_ecc_map = json_payload.get('ecc_map')
    if driver.is_on('service_supplier_contracts'):
        from bitdust.supplier import storage_contract
        storage_contract.cancel_customer_contract(customer_idurl)
    if not contactsdb.is_customer(customer_idurl):
        lg.warn('got packet from %s, but he is not a customer' % customer_idurl)
        return p2p_service.SendFail(newpacket, 'not a customer')
    if accounting.check_create_customers_quotas():
        lg.info('created a new space file')
    space_dict, free_space = accounting.read_customers_quotas()
    if customer_idurl.to_bin() not in list(space_dict.keys()):
        lg.warn('got packet from %s, but not found him in space dictionary' % customer_idurl)
        return p2p_service.SendFail(newpacket, 'not a customer')
    try:
        free_bytes = int(free_space)
        free_space = free_bytes + int(space_dict[customer_idurl.to_bin()])
    except:
        lg.exc()
        return p2p_service.SendFail(newpacket, 'broken quotas file')
    new_customers = list(contactsdb.customers())
    new_customers.remove(customer_idurl)
    space_dict.pop(customer_idurl.to_bin())
    accounting.write_customers_quotas(space_dict, free_space)
    contactsdb.remove_customer_meta_info(customer_idurl)
    contactsdb.update_customers(new_customers)
    contactsdb.save_customers()
    if customer_public_key_id:
        my_keys.erase_key(customer_public_key_id)
    # SECURITY
    # TODO: erase customer's groups keys also
    reactor.callLater(0, local_tester.TestUpdateCustomers)  # @UndefinedVariable
    lg.info('EXISTING CUSTOMER TERMINATED %r' % customer_idurl)
    events.send('existing-customer-terminated', data=dict(idurl=customer_idurl, ecc_map=customer_ecc_map))
    lg.admin('existing customer %s service terminated' % customer_idurl)
    return p2p_service.SendAck(newpacket, 'accepted')


#------------------------------------------------------------------------------


def on_inbox_packet_received(newpacket, info, status, error_message):
    if newpacket.Command == commands.DeleteFile():
        return on_delete_file(newpacket)
    elif newpacket.Command == commands.DeleteBackup():
        return on_delete_backup(newpacket)
    elif newpacket.Command == commands.Retrieve():
        return on_retrieve(newpacket)
    elif newpacket.Command == commands.Data():
        return on_data(newpacket)
    elif newpacket.Command == commands.ListFiles():
        return on_list_files(newpacket)
    return False


def on_suppliers_dht_layer_connected(ok):
    lg.info('connected to DHT layer for suppliers: %r' % ok)
    if my_id.getIDURL():
        dht_service.set_node_data('idurl', my_id.getIDURL().to_text(), layer_id=dht_records.LAYER_SUPPLIERS)
    return ok


def on_dht_layer_connected(evt):
    if evt.data['layer_id'] == 0:
        connect_suppliers_dht_layer()
    elif evt.data['layer_id'] == dht_records.LAYER_SUPPLIERS:
        on_suppliers_dht_layer_connected(True)
