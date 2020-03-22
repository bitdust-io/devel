#!/usr/bin/python
# service_supplier.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_supplier.py) is part of BitDust Software.
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
#

"""
..

module:: service_supplier
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return SupplierService()


class SupplierService(LocalService):

    service_name = 'service_supplier'
    config_path = 'services/supplier/enabled'

    publish_event_supplier_file_modified = False

    def dependent_on(self):
        return [
            'service_keys_registry',
        ]

    def installed(self):
        from userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def start(self):
        from logs import lg
        from transport import callback
        from main import events
        from contacts import contactsdb
        from storage import accounting
        from services import driver
        callback.append_inbox_callback(self._on_inbox_packet_received)
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        events.add_subscriber(self._on_customer_accepted, 'existing-customer-accepted')
        events.add_subscriber(self._on_customer_accepted, 'new-customer-accepted')
        events.add_subscriber(self._on_customer_terminated, 'existing-customer-denied')
        events.add_subscriber(self._on_customer_terminated, 'existing-customer-terminated')
        space_dict, _ = accounting.read_customers_quotas()
        for customer_idurl in contactsdb.customers():
            known_customer_meta_info = contactsdb.get_customer_meta_info(customer_idurl)
            events.send('existing-customer-accepted', data=dict(
                idurl=customer_idurl,
                allocated_bytes=space_dict.get(customer_idurl.to_bin()),
                ecc_map=known_customer_meta_info.get('ecc_map'),
                position=known_customer_meta_info.get('position'),
            ))
        if driver.is_on('service_entangled_dht'):
            self._do_connect_suppliers_dht_layer()
        else:
            lg.warn('service service_entangled_dht is OFF')
        events.add_subscriber(self._on_dht_layer_connected, event_id='dht-layer-connected')
        return True

    def stop(self):
        from transport import callback
        from main import events
        from services import driver
        events.remove_subscriber(self._on_dht_layer_connected, event_id='dht-layer-connected')
        if driver.is_on('service_entangled_dht'):
            from dht import dht_service
            from dht import dht_records
            dht_service.suspend(layer_id=dht_records.LAYER_SUPPLIERS)
        events.remove_subscriber(self._on_customer_accepted, 'existing-customer-accepted')
        events.remove_subscriber(self._on_customer_accepted, 'new-customer-accepted')
        events.remove_subscriber(self._on_customer_terminated, 'existing-customer-denied')
        events.remove_subscriber(self._on_customer_terminated, 'existing-customer-terminated')
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        return True

    def request(self, json_payload, newpacket, info):
        from twisted.internet import reactor  # @UnresolvedImport
        from logs import lg
        from main import events
        from crypt import my_keys
        from p2p import p2p_service
        from contacts import contactsdb
        from storage import accounting
        from userid import id_url
        from userid import global_id
        customer_idurl = newpacket.OwnerID
        customer_id = global_id.UrlToGlobalID(customer_idurl)
        bytes_for_customer = 0
        try:
            bytes_for_customer = int(json_payload['needed_bytes'])
        except:
            lg.warn("wrong payload" % newpacket.Payload)
            return p2p_service.SendFail(newpacket, 'wrong payload')
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
        key_id = json_payload.get('key_id')
        target_customer_id = json_payload.get('customer_id')
        if key_id:
            # this is a request from external user to access shared data stored by one of my customers
            # this is "second" customer requesting data from "first" customer
            if not key_id or not my_keys.is_valid_key_id(key_id):
                lg.warn('missed or invalid key id')
                return p2p_service.SendFail(newpacket, 'invalid key id')
            target_customer_idurl = global_id.GlobalUserToIDURL(target_customer_id)
            if not contactsdb.is_customer(target_customer_idurl):
                lg.warn("target user %s is not a customer" % target_customer_id)
                return p2p_service.SendFail(newpacket, 'not a customer')
            if target_customer_idurl == customer_idurl:
                lg.warn('customer %s requesting shared access to own files' % customer_idurl)
                return p2p_service.SendFail(newpacket, 'invalid case')
            if not my_keys.is_key_registered(key_id):
                lg.warn('key not registered: %s' % key_id)
                p2p_service.SendFail(newpacket, 'key not registered')
                return False
            data_owner_idurl = my_keys.split_key_id(key_id)[1]
            if data_owner_idurl != target_customer_idurl and data_owner_idurl != customer_idurl:
                # pretty complex scenario:
                # external customer requesting access to data which belongs not to that customer
                # this is "third" customer accessing data belongs to "second" customer
                # TODO: for now just stop it
                lg.warn('under construction, key_id=%s customer_idurl=%s target_customer_idurl=%s' % (
                    key_id, customer_idurl, target_customer_idurl, ))
                p2p_service.SendFail(newpacket, 'under construction')
                return False
            self._do_register_customer_key(customer_public_key_id, customer_public_key)
            # do not create connection with that customer, only accept the request
            lg.info('external customer %s requested access to shared data at %s' % (customer_id, key_id, ))
            return p2p_service.SendAck(newpacket, 'accepted')
        # key_id is not present in the request:
        # this is a request to connect new customer (or reconnect existing one) to that supplier
        if not bytes_for_customer or bytes_for_customer < 0:
            lg.warn("wrong payload : %s" % newpacket.Payload)
            return p2p_service.SendFail(newpacket, 'wrong storage value')
        current_customers = contactsdb.customers()
        lg.args(8, current_customers=current_customers)
        if accounting.check_create_customers_quotas():
            lg.info('created new customers quotas file')
        space_dict, free_space = accounting.read_customers_quotas()
        try:
            free_bytes = int(free_space)
        except:
            lg.exc()
            return p2p_service.SendFail(newpacket, 'broken space file')
        if (customer_idurl not in current_customers and customer_idurl.to_bin() in list(space_dict.keys())):
            lg.warn("broken space file")
            return p2p_service.SendFail(newpacket, 'broken space file')
        if (customer_idurl in current_customers and customer_idurl.to_bin() not in list(space_dict.keys())):
            # seems like customer's idurl was rotated, but space file still have the old idurl
            # need to find that old idurl value and replace with the new one
            for other_customer_idurl in space_dict.keys():
                if other_customer_idurl and other_customer_idurl != 'free' and id_url.field(other_customer_idurl) == customer_idurl:
                    lg.info('found rotated customer identity in space file, switching: %r -> %r' % (
                        other_customer_idurl, customer_idurl.to_bin()))
                    space_dict[customer_idurl.to_bin()] = space_dict.pop(other_customer_idurl)
                    break
            if customer_idurl.to_bin() not in list(space_dict.keys()):
                lg.warn("broken customers file")
                return p2p_service.SendFail(newpacket, 'broken customers file')
        if customer_idurl in current_customers:
            free_bytes += int(space_dict.get(customer_idurl.to_bin(), 0))
            current_customers.remove(customer_idurl)
            space_dict.pop(customer_idurl.to_bin())
            new_customer = False
        else:
            new_customer = True
        lg.args(8, new_customer=new_customer, current_allocated_bytes=space_dict.get(customer_idurl.to_bin()))
        from supplier import local_tester
        if free_bytes <= bytes_for_customer:
            contactsdb.remove_customer_meta_info(customer_idurl)
            accounting.write_customers_quotas(space_dict, free_bytes)
            contactsdb.update_customers(current_customers)
            contactsdb.save_customers()
            if customer_public_key_id:
                my_keys.erase_key(customer_public_key_id)
            reactor.callLater(0, local_tester.TestUpdateCustomers)  # @UndefinedVariable
            if new_customer:
                lg.out(8, "    NEW CUSTOMER: DENIED !!!!!!!!!!!    not enough space available")
                events.send('new-customer-denied', dict(idurl=customer_idurl))
            else:
                lg.out(8, "    OLD CUSTOMER: DENIED !!!!!!!!!!!    not enough space available")
                events.send('existing-customer-denied', dict(idurl=customer_idurl))
            return p2p_service.SendAck(newpacket, 'deny')
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
        self._do_register_customer_key(customer_public_key_id, customer_public_key)
        reactor.callLater(0, local_tester.TestUpdateCustomers)  # @UndefinedVariable
        if new_customer:
            lg.out(8, "    NEW CUSTOMER: ACCEPTED   %s family_position=%s ecc_map=%s allocated_bytes=%s" % (
                customer_idurl, family_position, ecc_map, bytes_for_customer))
            lg.out(8, "        family_snapshot=%r !!!!!!!!!!!!!!" % family_snapshot, )
            events.send('new-customer-accepted', dict(
                idurl=customer_idurl,
                allocated_bytes=bytes_for_customer,
                ecc_map=ecc_map,
                position=family_position,
                family_snapshot=family_snapshot,
                key_id=customer_public_key_id,
            ))
        else:
            lg.out(8, "    OLD CUSTOMER: ACCEPTED  %s family_position=%s ecc_map=%s allocated_bytes=%s" % (
                customer_idurl, family_position, ecc_map, bytes_for_customer))
            lg.out(8, "        family_snapshot=%r !!!!!!!!!!!!!!" % family_snapshot)
            events.send('existing-customer-accepted', dict(
                idurl=customer_idurl,
                allocated_bytes=bytes_for_customer,
                ecc_map=ecc_map,
                position=family_position,
                key_id=customer_public_key_id,
                family_snapshot=family_snapshot,
            ))
        return p2p_service.SendAck(newpacket, 'accepted')

    def cancel(self, json_payload, newpacket, info):
        from twisted.internet import reactor  # @UnresolvedImport
        from logs import lg
        from main import events
        from p2p import p2p_service
        from contacts import contactsdb
        from storage import accounting
        from crypt import my_keys
        customer_idurl = newpacket.OwnerID
        try:
            customer_public_key = json_payload['customer_public_key']
            customer_public_key_id = customer_public_key['key_id']
        except:
            customer_public_key = None
            customer_public_key_id = None
        customer_ecc_map = json_payload.get('ecc_map')
        if not contactsdb.is_customer(customer_idurl):
            lg.warn("got packet from %s, but he is not a customer" % customer_idurl)
            return p2p_service.SendFail(newpacket, 'not a customer')
        if accounting.check_create_customers_quotas():
            lg.out(6, 'service_supplier.cancel created a new space file')
        space_dict, free_space = accounting.read_customers_quotas()
        if customer_idurl.to_bin() not in list(space_dict.keys()):
            lg.warn("got packet from %s, but not found him in space dictionary" % customer_idurl)
            return p2p_service.SendFail(newpacket, 'not a customer')
        try:
            free_bytes = int(free_space)
            free_space = free_bytes + int(space_dict[customer_idurl.to_bin()])
        except:
            lg.exc()
            return p2p_service.SendFail(newpacket, 'broken space file')
        new_customers = list(contactsdb.customers())
        new_customers.remove(customer_idurl)
        space_dict.pop(customer_idurl.to_bin())
        accounting.write_customers_quotas(space_dict, free_space)
        contactsdb.remove_customer_meta_info(customer_idurl)
        contactsdb.update_customers(new_customers)
        contactsdb.save_customers()
        if customer_public_key_id:
            my_keys.erase_key(customer_public_key_id)
        from supplier import local_tester
        reactor.callLater(0, local_tester.TestUpdateCustomers)  # @UndefinedVariable
        lg.out(8, "    OLD CUSTOMER: TERMINATED !!!!!!!!!!!!!!")
        events.send('existing-customer-terminated', dict(idurl=customer_idurl, ecc_map=customer_ecc_map))
        return p2p_service.SendAck(newpacket, 'accepted')

    def _do_construct_filename(self, customerGlobID, packetID, keyAlias=None):
        import os
        from logs import lg
        from main import settings
        from system import bpio
        keyAlias = keyAlias or 'master'
        customerDirName = str(customerGlobID)
        customersDir = settings.getCustomersFilesDir()
        if not os.path.exists(customersDir):
            lg.info('making a new folder: ' + customersDir)
            bpio._dir_make(customersDir)
        ownerDir = os.path.join(customersDir, customerDirName)
        if not os.path.exists(ownerDir):
            lg.info('making a new folder: ' + ownerDir)
            bpio._dir_make(ownerDir)
        keyAliasDir = os.path.join(ownerDir, keyAlias)
        if not os.path.exists(keyAliasDir):
            lg.info('making a new folder: ' + keyAliasDir)
            bpio._dir_make(keyAliasDir)
        filename = os.path.join(keyAliasDir, packetID)
        return filename

    def _do_make_valid_filename(self, customerIDURL, glob_path):
        """
        Must be a customer, and then we make full path filename for where this
        packet is stored locally.
        """
        from logs import lg
        from lib import packetid
        from main import settings
        from contacts import contactsdb
        keyAlias = glob_path['key_alias'] or 'master'
        packetID = glob_path['path']
        customerGlobID = glob_path['customer']
        if not customerGlobID:
            lg.warn("customer id is empty")
            return ''
        if not packetid.Valid(packetID):  # SECURITY
            if packetID not in [settings.BackupInfoFileName(),
                                settings.BackupInfoFileNameOld(),
                                settings.BackupInfoEncryptedFileName(),
                                settings.BackupIndexFileName()]:
                lg.warn('invalid file path')
                return ''
        if not contactsdb.is_customer(customerIDURL):  # SECURITY
            lg.warn("%s is not my customer" % (customerIDURL))
        if customerGlobID:
            if glob_path['idurl'] != customerIDURL:
                lg.warn('making filename for another customer: %s != %s' % (
                    glob_path['idurl'], customerIDURL))
        filename = self._do_construct_filename(customerGlobID, packetID, keyAlias)
        return filename

    def _do_register_customer_key(self, customer_public_key_id, customer_public_key):
        """
        Check/refresh/store customer public key locally.
        """
        from crypt import my_keys
        from logs import lg
        if not customer_public_key_id or not customer_public_key:
            lg.warn('customer public key was not provided in the request')
            return
        if my_keys.is_key_registered(customer_public_key_id):
            known_customer_public_key = my_keys.get_public_key_raw(customer_public_key_id)
            if known_customer_public_key == customer_public_key:
                lg.warn('customer public key %r already known' % customer_public_key_id)
                return
            lg.warn('rewriting customer public key %r' % customer_public_key_id)
            my_keys.erase_key(customer_public_key_id)
        key_id, key_object = my_keys.read_key_info(customer_public_key)
        if my_keys.register_key(key_id, key_object):
            lg.info('new customer public key registered: %r' % customer_public_key_id)
        else:
            lg.err('failed to register customer public key: %r' % customer_public_key_id)

    def _do_connect_suppliers_dht_layer(self):
        from logs import lg
        from dht import dht_service
        from dht import dht_records
        from dht import known_nodes
        known_seeds = known_nodes.nodes()
        d = dht_service.open_layer(
            layer_id=dht_records.LAYER_SUPPLIERS,
            seed_nodes=known_seeds,
            connect_now=True,
            attach=True,
        )
        d.addCallback(self._on_suppliers_dht_layer_connected)
        d.addErrback(lambda *args: lg.err(str(args)))

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from p2p import commands
        if newpacket.Command == commands.DeleteFile():
            return self._on_delete_file(newpacket)
        elif newpacket.Command == commands.DeleteBackup():
            return self._on_delete_backup(newpacket)
        elif newpacket.Command == commands.Retrieve():
            return self._on_retrieve(newpacket)
        elif newpacket.Command == commands.Data():
            return self._on_data(newpacket)
        elif newpacket.Command == commands.ListFiles():
            return self._on_list_files(newpacket)
        return False

    def _on_delete_file(self, newpacket):
        import os
        from logs import lg
        from system import bpio
        from lib import strng
        from userid import global_id
        from p2p import p2p_service
        from main import events
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
                lg.warn('trying to delete file stored for another cusomer')
                continue
            # TODO: add validation of customerGlobID
            # TODO: process requests from another customer
            filename = self._do_make_valid_filename(newpacket.OwnerID, glob_path)
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
                lg.warn("path not found %s" % filename)
            if self.publish_event_supplier_file_modified:
                events.send('supplier-file-modified', data=dict(
                    action='delete',
                    glob_path=glob_path['path'],
                    owner_id=newpacket.OwnerID,
                ))
        lg.out(self.debug_level, "service_supplier._on_delete_file from [%s] with %d IDs, %d files and %d folders were removed" % (
            newpacket.OwnerID, len(ids), filescount, dirscount))
        p2p_service.SendAck(newpacket)
        return True

    def _on_delete_backup(self, newpacket):
        import os
        from logs import lg
        from lib import strng
        from system import bpio
        from userid import global_id
        from p2p import p2p_service
        from main import events
        if not newpacket.Payload:
            ids = [newpacket.PacketID, ]
        else:
            ids = strng.to_text(newpacket.Payload).split('\n')
        count = 0
        lg.warn('going to erase backup ids: %s' % ids)
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
            filename = self._do_make_valid_filename(newpacket.OwnerID, glob_path)
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
            if self.publish_event_supplier_file_modified:
                events.send('supplier-file-modified', data=dict(
                    action='delete',
                    glob_path=glob_path['path'],
                    owner_id=newpacket.OwnerID,
                ))
        lg.out(self.debug_level, "supplier_service._on_delete_backup from [%s] with %d IDs, %d were removed" % (
            newpacket.OwnerID, len(ids), count))
        p2p_service.SendAck(newpacket)
        return True

    def _on_retrieve(self, newpacket):
        import os
        from logs import lg
        from system import bpio
        from userid import my_id
        from userid import global_id
        from crypt import signed
        from transport import gateway
        from p2p import p2p_service
        from p2p import commands
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
            p2p_service.SendFail(newpacket, 'incorrect path')
            return False
        if not glob_path['idurl']:
            lg.warn('no customer global id found in PacketID: %s' % newpacket.PacketID)
            p2p_service.SendFail(newpacket, 'incorrect retrieve request')
            return False
        if newpacket.CreatorID != glob_path['idurl']:
            lg.warn('one of customers requesting a Data from another customer!')
        else:
            pass  # same customer, based on CreatorID : OK!
        recipient_idurl = newpacket.OwnerID
        # TODO: process requests from another customer : glob_path['idurl']
        filename = self._do_make_valid_filename(newpacket.OwnerID, glob_path)
        if not filename:
            if True:
                # TODO: settings.getCustomersDataSharingEnabled() and
                # SECURITY
                # TODO: add more validations for receiver idurl
                # recipient_idurl = glob_path['idurl']
                filename = self._do_make_valid_filename(glob_path['idurl'], glob_path)
        if not filename:
            lg.warn("had empty filename")
            p2p_service.SendFail(newpacket, 'empty filename')
            return False
        if not os.path.exists(filename):
            lg.warn("did not found requested file locally : %s" % filename)
            p2p_service.SendFail(newpacket, 'did not found requested file locally')
            return False
        if not os.access(filename, os.R_OK):
            lg.warn("no read access to requested packet %s" % filename)
            p2p_service.SendFail(newpacket, 'no read access to requested packet')
            return False
        data = bpio.ReadBinaryFile(filename)
        if not data:
            lg.warn("empty data on disk %s" % filename)
            p2p_service.SendFail(newpacket, 'empty data on disk')
            return False
        stored_packet = signed.Unserialize(data)
        del data
        if stored_packet is None:
            lg.warn("Unserialize failed, not Valid packet %s" % filename)
            p2p_service.SendFail(newpacket, 'unserialize failed')
            return False
        if not stored_packet.Valid():
            lg.warn("Stored packet is not Valid %s" % filename)
            p2p_service.SendFail(newpacket, 'stored packet is not valid')
            return False
        if stored_packet.Command != commands.Data():
            lg.warn('sending back packet which is not a Data')
        # here Data() packet is sent back as it is...
        # that means outpacket.RemoteID=my_id.getLocalID() - it was addressed to that node and stored as it is
        # need to take that in account every time you receive Data() packet
        # it can be not a new Data(), but the old data returning back as a response to Retreive() packet
        # let's create a new Data() packet which will be addressed directly to recipient and "wrap" stored data inside it
        routed_packet = signed.Packet(
            Command=commands.Data(),
            OwnerID=stored_packet.OwnerID,
            CreatorID=my_id.getLocalID(),
            PacketID=stored_packet.PacketID,
            Payload=stored_packet.Serialize(),
            RemoteID=recipient_idurl,
        )
        if recipient_idurl == stored_packet.OwnerID:
            lg.out(self.debug_level, 'service_supplier._on_retrieve   from request %r : sending %r back to owner: %s' % (
                newpacket, stored_packet, recipient_idurl))
            gateway.outbox(routed_packet)  # , target=recipient_idurl)
            return True
        lg.out(self.debug_level, 'service_supplier._on_retrieve   from request %r : returning data owned by %s to %s' % (
            newpacket, stored_packet.OwnerID, recipient_idurl))
        gateway.outbox(routed_packet)
        return True

    def _on_data(self, newpacket):
        import os
        from twisted.internet import reactor  # @UnresolvedImport
        from logs import lg
        from system import bpio
        from main import settings
        from userid import my_id
        from userid import global_id
        from contacts import contactsdb
        from p2p import p2p_service
        from storage import accounting
        if newpacket.OwnerID == my_id.getLocalID():
            # this Data belong to us, SKIP
            return False
        if not contactsdb.is_customer(newpacket.OwnerID):
            # SECURITY
            # TODO: process files from another customer : glob_path['idurl']
            lg.warn("skip, %s not a customer, packetID=%s" % (newpacket.OwnerID, newpacket.PacketID))
            # p2p_service.SendFail(newpacket, 'not a customer')
            return False
        glob_path = global_id.ParseGlobalID(newpacket.PacketID)
        if not glob_path['path']:
            # backward compatible check
            glob_path = global_id.ParseGlobalID(my_id.getGlobalID('master') + ':' + newpacket.PacketID)
        if not glob_path['path']:
            lg.err("got incorrect PacketID")
            p2p_service.SendFail(newpacket, 'incorrect path')
            return False
        filename = self._do_make_valid_filename(newpacket.OwnerID, glob_path)
        if not filename:
            lg.warn("got empty filename, bad customer or wrong packetID?")
            p2p_service.SendFail(newpacket, 'empty filename')
            return False
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            try:
                bpio._dirs_make(dirname)
            except:
                lg.err("can not create sub dir %s" % dirname)
                p2p_service.SendFail(newpacket, 'write error')
                return False
        data = newpacket.Serialize()
        donated_bytes = settings.getDonatedBytes()
        accounting.check_create_customers_quotas(donated_bytes)
        space_dict, free_space = accounting.read_customers_quotas()
        if newpacket.OwnerID.to_bin() not in list(space_dict.keys()):
            lg.err("no info about donated space for %s" % newpacket.OwnerID)
            p2p_service.SendFail(newpacket, 'no info about donated space')
            return False
        used_space_dict = accounting.read_customers_usage()
        if newpacket.OwnerID.to_bin() in list(used_space_dict.keys()):
            try:
                bytes_used_by_customer = int(used_space_dict[newpacket.OwnerID.to_bin()])
                bytes_donated_to_customer = int(space_dict[newpacket.OwnerID.to_bin()])
                if bytes_donated_to_customer - bytes_used_by_customer < len(data):
                    lg.warn("no free space for %s" % newpacket.OwnerID)
                    p2p_service.SendFail(newpacket, 'no free space')
                    return False
            except:
                lg.exc()
        if not bpio.WriteBinaryFile(filename, data):
            lg.err("can not write to %s" % str(filename))
            p2p_service.SendFail(newpacket, 'write error')
            return False
        # Here Data() packet was stored as it is on supplier node (current machine)
        sz = len(data)
        del data
        lg.out(self.debug_level, "service_supplier._on_data %r" % newpacket)
        lg.out(self.debug_level, "    from [ %s | %s ]" % (newpacket.OwnerID, newpacket.CreatorID, ))
        lg.out(self.debug_level, "        saved with %d %s" % (sz, filename, ))
        p2p_service.SendAck(newpacket, str(len(newpacket.Payload)))
        from supplier import local_tester
        reactor.callLater(0, local_tester.TestSpaceTime)  # @UndefinedVariable
        if self.publish_event_supplier_file_modified:
            from main import events
            events.send('supplier-file-modified', data=dict(
                action='write',
                glob_path=glob_path['path'],
                owner_id=newpacket.OwnerID,
            ))
        return True

    def _on_list_files(self, newpacket):
        from logs import lg
        from lib import strng
        from main import settings
        if strng.to_text(newpacket.Payload) != settings.ListFilesFormat():
            lg.exc('unknown ListFilesFormat() received: %r' % newpacket.Payload)
            return False
        # TODO: perform validations before sending back list of files
        from supplier import list_files
        from crypt import my_keys
        from userid import global_id
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
        list_files.send(
            customer_idurl=customer_idurl,
            packet_id=newpacket.PacketID,
            format_type=settings.ListFilesFormat(),
            key_id=key_id,
            remote_idurl=newpacket.OwnerID,  # send back to the requestor
        )
        return True

    def _on_customer_accepted(self, e):
        from logs import lg
        from p2p import p2p_queue
        from crypt import my_keys
        from userid import global_id
        from userid import my_id
        customer_idurl = e.data.get('idurl')
        if not customer_idurl:
            lg.warn('unknown customer idurl in event data payload')
            return
        customer_glob_id = global_id.idurl2glob(customer_idurl)
        queue_id = global_id.MakeGlobalQueueID(
            queue_alias='supplier-file-modified',
            owner_id=customer_glob_id,
            supplier_id=my_id.getGlobalID(),
        )
        if not p2p_queue.is_queue_exist(queue_id):
            customer_key_id = global_id.MakeGlobalID(customer=customer_glob_id, key_alias='customer')
            if my_keys.is_key_registered(customer_key_id):
                try:
                    p2p_queue.open_queue(queue_id)
                except Exception as exc:
                    lg.warn('failed to open queue %s : %s' % (queue_id, str(exc)))
            else:
                lg.warn('customer key %r for supplier queue not registered' % customer_key_id)
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

    def _on_customer_terminated(self, e):
        from logs import lg
        from userid import my_id
        from userid import global_id
        from p2p import p2p_queue
        customer_idurl = e.data.get('idurl')
        if not customer_idurl:
            lg.warn('unknown customer idurl in event data payload')
            return
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

    def _on_identity_url_changed(self, evt):
        import os
        from logs import lg
        from userid import id_url
        from userid import global_id
        from contacts import contactsdb
        from storage import accounting
        from system import bpio
        from supplier import local_tester
        from main import settings
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

    def _on_suppliers_dht_layer_connected(self, ok):
        from logs import lg
        from dht import dht_service
        from dht import dht_records
        from userid import my_id
        lg.info('connected to DHT layer for suppliers: %r' % ok)
        if my_id.getLocalID():
            dht_service.set_node_data('idurl', my_id.getLocalID().to_text(), layer_id=dht_records.LAYER_SUPPLIERS)
        return ok

    def _on_dht_layer_connected(self, evt):
        if evt.data['layer_id'] == 0:
            self._do_connect_suppliers_dht_layer()
