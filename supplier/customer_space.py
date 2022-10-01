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

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import time
import base64

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from lib import strng
from lib import packetid
from lib import serialization

from system import bpio

from main import settings
from main import events

from contacts import contactsdb

from services import driver

from p2p import p2p_service
from p2p import commands

from storage import accounting

from crypt import signed
from crypt import my_keys

from transport import gateway

from stream import p2p_queue

from supplier import list_files
from supplier import local_tester

from userid import global_id
from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

_SupplierFileModifiedLatest = {}
_SupplierFileModifiedNotifyTasks = {}

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
        if owner_idurl == creator_idurl:
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
    if newpacket.Command in [commands.DeleteFile(), commands.DeleteBackup(), ]:
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
        lg.warn("customer id is empty: %r" % glob_path)
        return ''
    if filePath != settings.BackupIndexFileName():
        if not packetid.Valid(filePath):  # SECURITY
            lg.warn('invalid file path')
            return ''
    # if not contactsdb.is_customer(customerIDURL):  # SECURITY
    #     lg.warn("%s is not my customer" % (customerIDURL))
    # if customerGlobID:
    #     if glob_path['idurl'] != customerIDURL:
    #         lg.warn('making filename for another customer: %s != %s' % (
    #             glob_path['idurl'], customerIDURL))
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
        new_delay, do_notify_supplier_file_modified, key_alias, remote_path, action, customer_idurl, authorized_idurl)

#------------------------------------------------------------------------------

def on_data(newpacket):
    if id_url.is_the_same(newpacket.OwnerID, my_id.getIDURL()):
        # this Data belong to us, SKIP
        return False
#     if not contactsdb.is_customer(newpacket.OwnerID):
#         # SECURITY
#         # TODO: process files from another customer : glob_path['idurl']
#         lg.warn("skip, %s not a customer, packetID=%s" % (newpacket.OwnerID, newpacket.PacketID))
#         # p2p_service.SendFail(newpacket, 'not a customer')
#         return False
    glob_path = global_id.ParseGlobalID(newpacket.PacketID)
    if not glob_path['path']:
        # backward compatible check
        glob_path = global_id.ParseGlobalID(my_id.getGlobalID('master') + ':' + newpacket.PacketID)
    if not glob_path['path']:
        lg.err("got incorrect PacketID")
        # p2p_service.SendFail(newpacket, 'incorrect path')
        return False
    remote_path = glob_path['path']
    key_alias = glob_path['key_alias']
    customer_idurl, authorized_idurl = verify_ownership(newpacket)
    if authorized_idurl is None or customer_idurl is None:
        if _Debug:
            lg.dbg(_DebugLevel, "ownership verification failed for %r" % newpacket)
        # p2p_service.SendFail(newpacket, 'ownership verification failed')
        return False
    filename = make_valid_filename(newpacket.OwnerID, glob_path)
    if not filename:
        lg.warn("got empty filename, bad customer or wrong packetID?")
        # p2p_service.SendFail(newpacket, 'empty filename')
        return False
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        try:
            bpio._dirs_make(dirname)
        except:
            lg.err("can not create sub dir %s" % dirname)
            p2p_service.SendFail(newpacket, 'write error', remote_idurl=authorized_idurl)
            return False
    new_data = newpacket.Serialize()
    donated_bytes = settings.getDonatedBytes()
    accounting.check_create_customers_quotas(donated_bytes)
    space_dict, _ = accounting.read_customers_quotas()
    known_customers_quoats = list(space_dict.keys())
    if id_url.is_not_in(customer_idurl, known_customers_quoats, as_field=False, as_bin=True):
        lg.err("customer space is broken, no info about donated space can be found for %s" % newpacket)
        p2p_service.SendFail(newpacket, 'customer space is broken, no info found about donated space', remote_idurl=authorized_idurl)
        return False
    used_space_dict = accounting.read_customers_usage()
    known_customers_usage = list(used_space_dict.keys())
    if id_url.is_in(customer_idurl, known_customers_usage, as_field=False, as_bin=True):
        try:
            bytes_used_by_customer = int(used_space_dict[customer_idurl.to_bin()])
            bytes_donated_to_customer = int(space_dict[customer_idurl.to_bin()])
            if bytes_donated_to_customer - bytes_used_by_customer < len(new_data):
                lg.warn("no free space left for customer data for %s" % customer_idurl)
                p2p_service.SendFail(newpacket, 'no free space left for customer data', remote_idurl=authorized_idurl)
                return False
        except:
            lg.exc()
    data_exists = not os.path.exists(filename)
    data_changed = True
    if not data_exists:
        if remote_path == settings.BackupIndexFileName():
            current_data = bpio.ReadBinaryFile(filename)
            if current_data == new_data:
                lg.warn('skip rewriting existing file %s' % filename)
                data_changed = False
    if data_changed:
        if not bpio.WriteBinaryFile(filename, new_data):
            lg.err("can not write to %s" % str(filename))
            p2p_service.SendFail(newpacket, 'write error', remote_idurl=authorized_idurl)
            return False
    # Here Data() packet was stored as it is on supplier node (current machine)
    del new_data
    sz = len(newpacket.Payload)
    p2p_service.SendAck(newpacket, response=strng.to_text(sz), remote_idurl=authorized_idurl)
    reactor.callLater(0, local_tester.TestSpaceTime)  # @UndefinedVariable
    if key_alias != 'master' and data_changed:
        if remote_path == settings.BackupIndexFileName():
            do_notify_supplier_file_modified(key_alias, remote_path, 'write', customer_idurl, authorized_idurl)
        else:
            if packetid.BlockNumber(newpacket.PacketID) == 0:
                do_notify_supplier_file_modified(key_alias, remote_path, 'write', customer_idurl, authorized_idurl)
    if _Debug:
        lg.args(_DebugLevel, sz=sz, fn=filename, remote_idurl=authorized_idurl, pid=newpacket.PacketID)
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
        lg.err("got incorrect PacketID")
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
        lg.warn("had empty filename")
        p2p_service.SendFail(newpacket, 'empty filename', remote_idurl=recipient_idurl)
        return False
    if not os.path.exists(filename):
        lg.warn("did not found requested file locally : %s" % filename)
        p2p_service.SendFail(newpacket, 'did not found requested file locally', remote_idurl=recipient_idurl)
        return False
    if not os.access(filename, os.R_OK):
        lg.warn("no read access to requested packet %s" % filename)
        p2p_service.SendFail(newpacket, 'failed reading requested file', remote_idurl=recipient_idurl)
        return False
    data = bpio.ReadBinaryFile(filename)
    if not data:
        lg.warn("empty data on disk %s" % filename)
        p2p_service.SendFail(newpacket, 'empty data on disk', remote_idurl=recipient_idurl)
        return False
    stored_packet = signed.Unserialize(data)
    sz = len(data)
    del data
    if stored_packet is None:
        lg.warn("Unserialize failed, not Valid packet %s" % filename)
        p2p_service.SendFail(newpacket, 'unserialize failed', remote_idurl=recipient_idurl)
        return False
    if not stored_packet.Valid():
        lg.warn("Stored packet is not Valid %s" % filename)
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
    payload = stored_packet.Serialize()
    routed_packet = signed.Packet(
        Command=commands.Data(),
        OwnerID=stored_packet.OwnerID,
        CreatorID=my_id.getIDURL(),
        PacketID=stored_packet.PacketID,
        Payload=payload,
        RemoteID=recipient_idurl,
    )
    if _Debug:
        lg.args(_DebugLevel, file_size=sz, payload_size=len(payload), fn=filename, recipient=recipient_idurl)
    if recipient_idurl == stored_packet.OwnerID:
        if _Debug:
            lg.dbg(_DebugLevel, 'from request %r : sending %r back to owner: %s' % (
                newpacket, stored_packet, recipient_idurl))
        gateway.outbox(routed_packet)
        return True
    if _Debug:
        lg.dbg(_DebugLevel, 'from request %r : returning data owned by %s to %s' % (
            newpacket, stored_packet.OwnerID, recipient_idurl))
    gateway.outbox(routed_packet)
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
            json_query = {'items': ['*', ], }
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
        ids = [newpacket.PacketID, ]
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
            lg.err("got incorrect PacketID")
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
            lg.warn("got empty filename, bad customer or wrong packetID?")
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
            lg.warn("path was not found %s" % filename)
        do_notify_supplier_file_modified(glob_path['key_alias'], glob_path['path'], 'delete', newpacket.OwnerID, newpacket.CreatorID)
    p2p_service.SendAck(newpacket)
    if _Debug:
        lg.dbg(_DebugLevel, "from [%s] with %d IDs, %d files and %d folders were removed" % (
            newpacket.OwnerID, len(ids), filescount, dirscount))
    return True


def on_delete_backup(newpacket):
    # TODO: call verify_ownership()
    # SECURITY
    if not newpacket.Payload:
        ids = [newpacket.PacketID, ]
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
            lg.err("got incorrect BackupID")
            p2p_service.SendFail(newpacket, 'incorrect backupID')
            return False
        if customer_id != glob_path['customer']:
            lg.warn('trying to delete file stored for another cusomer')
            continue
        # TODO: add validation of customerGlobID
        # TODO: process requests from another customer
        filename = make_valid_filename(newpacket.OwnerID, glob_path)
        if not filename:
            lg.warn("got empty filename, bad customer or wrong packetID?")
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
            lg.warn("path not found %s" % filename)
        do_notify_supplier_file_modified(glob_path['key_alias'], glob_path['path'], 'delete', newpacket.OwnerID, newpacket.CreatorID)
    p2p_service.SendAck(newpacket)
    if _Debug:
        lg.dbg(_DebugLevel, "from [%s] with %d IDs, %d were removed" % (
            newpacket.OwnerID, len(ids), count))
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
            lg.info('found customer idurl rotated : %r -> %r' % (
                evt.data['old_idurl'], evt.data['new_idurl'], ))
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
                    lg.info('found customer idurl rotated in customers meta info : %r -> %r' % (
                        latest_customer_idurl_bin, customer_idurl_bin, ))
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
                    lg.info('found customer idurl rotated in customer quotas dictionary : %r -> %r' % (
                        latest_customer_idurl_bin, customer_idurl_bin, ))
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
            lg.info('copied %r into %r' % (old_owner_dir, new_owner_dir, ))
            if os.path.exists(old_owner_dir):
                bpio._dir_remove(old_owner_dir)
                lg.warn('removed %r' % old_owner_dir)
        except:
            lg.exc()
    # update customer idurl in "spaceused" file
    local_tester.TestSpaceTime()
    return True
