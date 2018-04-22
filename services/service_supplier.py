#!/usr/bin/python
# service_supplier.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

from services.local_service import LocalService


def create_service():
    return SupplierService()


class SupplierService(LocalService):

    service_name = 'service_supplier'
    config_path = 'services/supplier/enabled'

    def dependent_on(self):
        return [
            'service_p2p_notifications',
        ]

    def installed(self):
        from userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def start(self):
        from transport import callback
        from main import events
        from contacts import contactsdb
        from storage import accounting
        callback.append_inbox_callback(self._on_inbox_packet_received)
        events.add_subscriber(self._on_customer_accepted, 'existing-customer-accepted')
        events.add_subscriber(self._on_customer_accepted, 'new-customer-accepted')
        events.add_subscriber(self._on_customer_terminated, 'existing-customer-denied')
        events.add_subscriber(self._on_customer_terminated, 'existing-customer-terminated')
        space_dict = accounting.read_customers_quotas()
        for customer_idurl in contactsdb.customers():
            events.send('existing-customer-accepted', data=dict(
                idurl=customer_idurl,
                allocated_bytes=space_dict.get(customer_idurl),
            ))
        return True

    def stop(self):
        from transport import callback
        from main import events
        from contacts import contactsdb
        # for customer_idurl in contactsdb.customers():
        #     events.send('existing-customer-terminated', data=dict(idurl=customer_idurl))
        events.remove_subscriber(self._on_customer_accepted, 'existing-customer-accepted')
        events.remove_subscriber(self._on_customer_accepted, 'new-customer-accepted')
        events.remove_subscriber(self._on_customer_terminated, 'existing-customer-denied')
        events.remove_subscriber(self._on_customer_terminated, 'existing-customer-terminated')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        return True

    def request(self, json_payload, newpacket, info):
        from twisted.internet import reactor
        from logs import lg
        from main import events
        from crypt import my_keys
        from p2p import p2p_service
        from contacts import contactsdb
        from storage import accounting
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
        # if not bytes_for_customer or bytes_for_customer < 0:
        #     lg.warn("wrong payload : %s" % newpacket.Payload)
        #     return p2p_service.SendFail(newpacket, 'wrong storage value')
        current_customers = contactsdb.customers()
        if accounting.check_create_customers_quotas():
            lg.out(6, 'service_supplier.request created a new space file')
        space_dict = accounting.read_customers_quotas()
        try:
            free_bytes = int(space_dict['free'])
        except:
            lg.exc()
            return p2p_service.SendFail(newpacket, 'broken space file')
        if (newpacket.OwnerID not in current_customers and newpacket.OwnerID in space_dict.keys()):
            lg.warn("broken space file")
            return p2p_service.SendFail(newpacket, 'broken space file')
        if (newpacket.OwnerID in current_customers and newpacket.OwnerID not in space_dict.keys()):
            lg.warn("broken customers file")
            return p2p_service.SendFail(newpacket, 'broken customers file')
        if newpacket.OwnerID in current_customers:
            free_bytes += int(space_dict[newpacket.OwnerID])
            space_dict['free'] = free_bytes
            current_customers.remove(newpacket.OwnerID)
            space_dict.pop(newpacket.OwnerID)
            new_customer = False
        else:
            new_customer = True
        from supplier import local_tester
        if free_bytes <= bytes_for_customer:
            contactsdb.update_customers(current_customers)
            contactsdb.save_customers()
            accounting.write_customers_quotas(space_dict)
            if customer_public_key_id:
                my_keys.erase_key(customer_public_key_id)
            reactor.callLater(0, local_tester.TestUpdateCustomers)
            if new_customer:
                lg.out(8, "    NEW CUSTOMER: DENIED !!!!!!!!!!!    not enough space available")
                events.send('new-customer-denied', dict(idurl=newpacket.OwnerID))
            else:
                lg.out(8, "    OLD CUSTOMER: DENIED !!!!!!!!!!!    not enough space available")
                events.send('existing-customer-denied', dict(idurl=newpacket.OwnerID))
            return p2p_service.SendAck(newpacket, 'deny')
        space_dict['free'] = free_bytes - bytes_for_customer
        current_customers.append(newpacket.OwnerID)
        space_dict[newpacket.OwnerID] = bytes_for_customer
        contactsdb.update_customers(current_customers)
        contactsdb.save_customers()
        accounting.write_customers_quotas(space_dict)
        if customer_public_key_id:
            my_keys.erase_key(customer_public_key_id)
            try:
                if not my_keys.is_key_registered(customer_public_key_id):
                    key_id, key_object = my_keys.read_key_info(customer_public_key)
                    if not my_keys.register_key(key_id, key_object):
                        lg.warn('failed to register customer public key')
            except:
                lg.exc()
        else:
            lg.warn('customer public key was not provided in the request')
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        if new_customer:
            lg.out(8, "    NEW CUSTOMER: ACCEPTED !!!!!!!!!!!!!!")
            events.send('new-customer-accepted', dict(
                idurl=newpacket.OwnerID,
                allocated_bytes=bytes_for_customer,
                key_id=customer_public_key_id,
            ))
        else:
            lg.out(8, "    OLD CUSTOMER: ACCEPTED !!!!!!!!!!!!!!")
            events.send('existing-customer-accepted', dict(idurl=newpacket.OwnerID))
        return p2p_service.SendAck(newpacket, 'accepted')

    def cancel(self, json_payload, newpacket, info):
        from twisted.internet import reactor
        from logs import lg
        from main import events
        from p2p import p2p_service
        from contacts import contactsdb
        from storage import accounting
        from services import driver
        if not contactsdb.is_customer(newpacket.OwnerID):
            lg.warn("got packet from %s, but he is not a customer" % newpacket.OwnerID)
            return p2p_service.SendFail(newpacket, 'not a customer')
        if accounting.check_create_customers_quotas():
            lg.out(6, 'service_supplier.cancel created a new space file')
        space_dict = accounting.read_customers_quotas()
        if newpacket.OwnerID not in space_dict.keys():
            lg.warn("got packet from %s, but not found him in space dictionary" % newpacket.OwnerID)
            return p2p_service.SendFail(newpacket, 'not a customer')
        try:
            free_bytes = int(space_dict['free'])
            space_dict['free'] = free_bytes + int(space_dict[newpacket.OwnerID])
        except:
            lg.exc()
            return p2p_service.SendFail(newpacket, 'broken space file')
        new_customers = list(contactsdb.customers())
        new_customers.remove(newpacket.OwnerID)
        contactsdb.update_customers(new_customers)
        contactsdb.save_customers()
        space_dict.pop(newpacket.OwnerID)
        accounting.write_customers_quotas(space_dict)
        from supplier import local_tester
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        if driver.is_on('service_supplier_relations'):
            from dht import dht_relations
            reactor.callLater(0, dht_relations.close_customer_supplier_relation, newpacket.OwnerID)
        lg.out(8, "    OLD CUSTOMER: TERMINATED !!!!!!!!!!!!!!")
        events.send('existing-customer-terminated', dict(idurl=newpacket.OwnerID))
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
            lg.warn("%s is not a customer" % (customerIDURL))
            return ''
        if customerGlobID:
            if glob_path['idurl'] != customerIDURL:
                lg.warn('making filename for another customer: %s != %s' % (
                    glob_path['idurl'], customerIDURL))
        filename = self._do_construct_filename(customerGlobID, packetID, keyAlias)
        return filename

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from p2p import commands
        if newpacket.Command == commands.DeleteFile():
            return self._on_delete_file(newpacket)
        elif newpacket.Command == commands.Retrieve():
            return self._on_retreive(newpacket)
        elif newpacket.Command == commands.Data():
            return self._on_data(newpacket)
        elif newpacket.Command == commands.ListFiles():
            return self._on_list_files(newpacket)
        return False

    def _on_delete_file(self, newpacket):
        import os
        from logs import lg
        from system import bpio
        from userid import global_id
        from p2p import p2p_service
        from main import events
        if newpacket.Payload == '':
            ids = [newpacket.PacketID, ]
        else:
            ids = newpacket.Payload.split('\n')
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
        from system import bpio
        from userid import global_id
        from p2p import p2p_service
        from main import events
        if newpacket.Payload == '':
            ids = [newpacket.PacketID, ]
        else:
            ids = newpacket.Payload.split('\n')
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
            events.send('supplier-file-modified', data=dict(
                action='delete',
                glob_path=glob_path['path'],
                owner_id=newpacket.OwnerID,
            ))
        lg.out(self.debug_level, "supplier_service._on_delete_backup from [%s] with %d IDs, %d were removed" % (
            newpacket.OwnerID, len(ids), count))
        p2p_service.SendAck(newpacket)
        return True

    def _on_retreive(self, newpacket):
        import os
        from logs import lg
        from system import bpio
        from userid import my_id
        from userid import global_id
        from crypt import signed
        from contacts import contactsdb
        from transport import gateway
        from p2p import p2p_service
        from p2p import commands
        if not contactsdb.is_customer(newpacket.OwnerID):
            lg.err("had unknown customer %s" % newpacket.OwnerID)
            p2p_service.SendFail(newpacket, 'not a customer')
            return False
        glob_path = global_id.ParseGlobalID(newpacket.PacketID)
        if not glob_path['path']:
            # backward compatible check
            glob_path = global_id.ParseGlobalID(my_id.getGlobalID('master') + ':' + newpacket.PacketID)
        if not glob_path['path']:
            lg.err("got incorrect PacketID")
            p2p_service.SendFail(newpacket, 'incorrect path')
            return False
        if glob_path['idurl']:
            if newpacket.CreatorID == glob_path['idurl']:
                pass  # same customer, based on CreatorID : OK!
            else:
                lg.warn('one of customers requesting a Data from another customer!')
        else:
            lg.warn('no customer global id found in PacketID: %s' % newpacket.PacketID)
        # TODO: process requests from another customer : glob_path['idurl']
        filename = self._do_make_valid_filename(newpacket.OwnerID, glob_path)
        if not filename:
            if True:
                # TODO: settings.getCustomersDataSharingEnabled() and
                # SECURITY
                filename = self._do_make_valid_filename(glob_path['idurl'], glob_path)
        if not filename:
            lg.warn("had empty filename")
            p2p_service.SendFail(newpacket, 'empty filename')
            return False
        if not os.path.exists(filename):
            lg.warn("did not find requested file locally : %s" % filename)
            p2p_service.SendFail(newpacket, 'did not find requested file locally')
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
        outpacket = signed.Unserialize(data)
        del data
        if outpacket is None:
            lg.warn("Unserialize fails, not Valid packet %s" % filename)
            p2p_service.SendFail(newpacket, 'unserialize fails')
            return False
        if not outpacket.Valid():
            lg.warn("unserialized packet is not Valid %s" % filename)
            p2p_service.SendFail(newpacket, 'unserialized packet is not Valid')
            return False
        if outpacket.Command != commands.Data():
            lg.warn('sending back packet which is not a Data')
        # here Data() packet is sent back as it is...
        # that means outpacket.RemoteID=my_id.getLocalID() - it was addressed to that node and stored as it is
        # need to take that in account every time you receive Data() packet
        # it can be not a new Data(), but the old data returning back as a response to Retreive() packet
        lg.warn('from request %r : sending %r back to %s' % (newpacket, outpacket, outpacket.CreatorID))
        gateway.outbox(outpacket, target=outpacket.CreatorID)
        return True

    def _on_data(self, newpacket):
        import os
        from twisted.internet import reactor
        from logs import lg
        from system import bpio
        from main import settings
        from userid import my_id
        from userid import global_id
        from contacts import contactsdb
        from p2p import p2p_service
        if newpacket.OwnerID == my_id.getLocalID():
            # this Data belong to us, SKIP
            return False
        if not contactsdb.is_customer(newpacket.OwnerID):  # SECURITY
            lg.err("%s not a customer, packetID=%s" % (newpacket.OwnerID, newpacket.PacketID))
            p2p_service.SendFail(newpacket, 'not a customer')
            return False
        glob_path = global_id.ParseGlobalID(newpacket.PacketID)
        if not glob_path['path']:
            # backward compatible check
            glob_path = global_id.ParseGlobalID(my_id.getGlobalID('master') + ':' + newpacket.PacketID)
        if not glob_path['path']:
            lg.err("got incorrect PacketID")
            p2p_service.SendFail(newpacket, 'incorrect path')
            return False
        # TODO: process files from another customer : glob_path['idurl']
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
        if not os.path.isfile(settings.CustomersSpaceFile()):
            bpio._write_dict(settings.CustomersSpaceFile(), {'free': donated_bytes, })
            lg.warn('created a new space file: %s' % settings.CustomersSpaceFile())
        space_dict = bpio._read_dict(settings.CustomersSpaceFile())
        if newpacket.OwnerID not in space_dict.keys():
            lg.err("no info about donated space for %s" % newpacket.OwnerID)
            p2p_service.SendFail(newpacket, 'no info about donated space')
            return False
        used_space_dict = bpio._read_dict(settings.CustomersUsedSpaceFile(), {})
        if newpacket.OwnerID in used_space_dict.keys():
            try:
                bytes_used_by_customer = int(used_space_dict[newpacket.OwnerID])
                bytes_donated_to_customer = int(space_dict[newpacket.OwnerID])
                if bytes_donated_to_customer - bytes_used_by_customer < len(data):
                    lg.warn("no free space for %s" % newpacket.OwnerID)
                    p2p_service.SendFail(newpacket, 'no free space')
                    return False
            except:
                lg.exc()
        if not bpio.WriteFile(filename, data):
            lg.err("can not write to %s" % str(filename))
            p2p_service.SendFail(newpacket, 'write error')
            return False
        # Here Data() packet was stored as it is on supplier node (current machine)
        sz = len(data)
        del data
        lg.out(self.debug_level, "service_supplier._on_data %r saved from [%s | %s] to %s with %d bytes" % (
            newpacket, newpacket.OwnerID, newpacket.CreatorID, filename, sz, ))
        p2p_service.SendAck(newpacket, str(len(newpacket.Payload)))
        from supplier import local_tester
        reactor.callLater(0, local_tester.TestSpaceTime)
        # temporary disabled
        # from main import events
        # events.send('supplier-file-modified', data=dict(
        #     action='write',
        #     glob_path=glob_path['path'],
        #     owner_id=newpacket.OwnerID,
        # ))
        return True

    def _on_list_files(self, newpacket):
        from main import settings
        if newpacket.Payload != settings.ListFilesFormat():
            return False
        # TODO: perform validations before sending back list of files
        from supplier import list_files
        from crypt import my_keys
        from userid import global_id
        list_files_global_id = global_id.ParseGlobalID(newpacket.PacketID)
        list_files.send(
            customer_idurl=newpacket.OwnerID,
            packet_id=newpacket.PacketID,
            format_type=settings.ListFilesFormat(),
            key_id=(
                list_files_global_id['key_id'] or
                my_keys.make_key_id(alias='customer', creator_idurl=newpacket.OwnerID)
            ),
        )
        return True

    def _on_customer_accepted(self, e):
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
        if not p2p_queue.is_queue_exist(queue_id):
            try:
                p2p_queue.open_queue(queue_id)
            except Exception as exc:
                lg.warn('failed to open queue %s : %s' % (queue_id, str(exc)))
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
