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

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.internet import reactor

#------------------------------------------------------------------------------

from logs import lg

from services.local_service import LocalService

#------------------------------------------------------------------------------


def create_service():
    return SupplierService()


class SupplierService(LocalService):

    service_name = 'service_supplier'
    config_path = 'services/supplier/enabled'

    def dependent_on(self):
        return ['service_p2p_hookups',
                ]

    def installed(self):
        from userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def start(self):
        from transport import callback
        callback.append_inbox_callback(self._on_inbox_packet_received)
        return True

    def stop(self):
        from transport import callback
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        return True

    def request(self, request, info):
        from main import events
        from p2p import p2p_service
        from contacts import contactsdb
        from storage import accounting
        words = request.Payload.split(' ')
        try:
            bytes_for_customer = int(words[1])
        except:
            lg.exc()
            bytes_for_customer = None
        if not bytes_for_customer or bytes_for_customer < 0:
            lg.warn("wrong storage value : %s" % request.Payload)
            return p2p_service.SendFail(request, 'wrong storage value')
        current_customers = contactsdb.customers()
        if accounting.check_create_customers_quotas():
            lg.out(6, 'service_supplier.request created a new space file')
        space_dict = accounting.read_customers_quotas()
        try:
            free_bytes = int(space_dict['free'])
        except:
            lg.exc()
            return p2p_service.SendFail(request, 'broken space file')
        if (request.OwnerID not in current_customers and request.OwnerID in space_dict.keys()):
            lg.warn("broken space file")
            return p2p_service.SendFail(request, 'broken space file')
        if (request.OwnerID in current_customers and request.OwnerID not in space_dict.keys()):
            lg.warn("broken customers file")
            return p2p_service.SendFail(request, 'broken customers file')
        if request.OwnerID in current_customers:
            free_bytes += int(space_dict[request.OwnerID])
            space_dict['free'] = free_bytes
            current_customers.remove(request.OwnerID)
            space_dict.pop(request.OwnerID)
            new_customer = False
        else:
            new_customer = True
        from supplier import local_tester
        if free_bytes <= bytes_for_customer:
            contactsdb.update_customers(current_customers)
            contactsdb.save_customers()
            accounting.write_customers_quotas(space_dict)
            reactor.callLater(0, local_tester.TestUpdateCustomers)
            if new_customer:
                lg.out(8, "    NEW CUSTOMER: DENIED !!!!!!!!!!!    not enough space available")
                events.send('new-customer-denied', dict(idurl=request.OwnerID))
            else:
                lg.out(8, "    OLD CUSTOMER: DENIED !!!!!!!!!!!    not enough space available")
                events.send('existing-customer-denied', dict(idurl=request.OwnerID))
            return p2p_service.SendAck(request, 'deny')
        space_dict['free'] = free_bytes - bytes_for_customer
        current_customers.append(request.OwnerID)
        space_dict[request.OwnerID] = bytes_for_customer
        contactsdb.update_customers(current_customers)
        contactsdb.save_customers()
        accounting.write_customers_quotas(space_dict)
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        if new_customer:
            lg.out(8, "    NEW CUSTOMER: ACCEPTED !!!!!!!!!!!!!!")
            events.send('new-customer-accepted', dict(idurl=request.OwnerID))
        else:
            lg.out(8, "    OLD CUSTOMER: ACCEPTED !!!!!!!!!!!!!!")
            events.send('existing-customer-accepted', dict(idurl=request.OwnerID))
        return p2p_service.SendAck(request, 'accepted')

    def cancel(self, request, info):
        from main import events
        from p2p import p2p_service
        from contacts import contactsdb
        from storage import accounting
        if not contactsdb.is_customer(request.OwnerID):
            lg.warn(
                "got packet from %s, but he is not a customer" %
                request.OwnerID)
            return p2p_service.SendFail(request, 'not a customer')
        if accounting.check_create_customers_quotas():
            lg.out(6, 'service_supplier.cancel created a new space file')
        space_dict = accounting.read_customers_quotas()
        if request.OwnerID not in space_dict.keys():
            lg.warn(
                "got packet from %s, but not found him in space dictionary" %
                request.OwnerID)
            return p2p_service.SendFail(request, 'not a customer')
        try:
            free_bytes = int(space_dict['free'])
            space_dict['free'] = free_bytes + int(space_dict[request.OwnerID])
        except:
            lg.exc()
            return p2p_service.SendFail(request, 'broken space file')
        new_customers = list(contactsdb.customers())
        new_customers.remove(request.OwnerID)
        contactsdb.update_customers(new_customers)
        contactsdb.save_customers()
        space_dict.pop(request.OwnerID)
        accounting.write_customers_quotas(space_dict)
        from supplier import local_tester
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        lg.out(8, "    OLD CUSTOMER: TERMINATED !!!!!!!!!!!!!!")
        events.send('existing-customer-terminated', dict(idurl=request.OwnerID))
        return p2p_service.SendAck(request, 'accepted')

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
        from system import bpio
        from userid import my_id
        from userid import global_id
        from p2p import p2p_service
        if newpacket.Payload == '':
            ids = [newpacket.PacketID, ]
        else:
            ids = newpacket.Payload.split('\n')
        filescount = 0
        dirscount = 0
        for pcktID in ids:
            glob_path = global_id.ParseGlobalID(pcktID)
            if not glob_path['path']:
                # backward compatible check
                glob_path = global_id.ParseGlobalID(my_id.getGlobalID() + ':' + newpacket.PacketID)
            if not glob_path['path']:
                lg.err("got incorrect PacketID")
                p2p_service.SendFail(newpacket, 'incorrect PacketID')
                return
            # TODO: add validation of customerGlobID
            # TODO: process requests from another customer
            filename = p2p_service.makeFilename(newpacket.OwnerID, glob_path['path'])
            if filename == "":
                filename = p2p_service.constructFilename(newpacket.OwnerID, glob_path['path'])
                if not os.path.exists(filename):
                    lg.err("had unknown customer: %s or pathID is not correct or not exist: %s" % (
                        newpacket.OwnerID, glob_path['path']))
                    return p2p_service.SendFail(newpacket, 'not a customer, or file not found')
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
        self.log(self.debug_level, "service_supplier._on_delete_file from [%s] with %d IDs, %d files and %d folders were removed" % (
            newpacket.OwnerID, len(ids), filescount, dirscount))
        p2p_service.SendAck(newpacket)
        return True

    def _on_delete_backup(self, newpacket):
        from system import bpio
        from userid import global_id
        from p2p import p2p_service
        if newpacket.Payload == '':
            ids = [newpacket.PacketID]
        else:
            ids = newpacket.Payload.split('\n')
        count = 0
        for bkpID in ids:
            glob_path = global_id.ParseGlobalID(bkpID)
            if not glob_path['path']:
                lg.err("got incorrect backupID")
                p2p_service.SendFail(newpacket, 'incorrect backupID')
                return
            # TODO: add validation of customerGlobID
            # TODO: process requests from another customer
            filename = p2p_service.makeFilename(newpacket.OwnerID, glob_path['path'])
            if filename == "":
                filename = p2p_service.constructFilename(newpacket.OwnerID, glob_path['path'])
                if not os.path.exists(filename):
                    lg.err("had unknown customer: %s or backupID: %s" (bkpID, newpacket.OwnerID))
                    return p2p_service.SendFail(newpacket, 'not a customer, or file not found')
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
        p2p_service.SendAck(newpacket)
        self.log(self.debug_level, "supplier_service._on_delete_backup from [%s] with %d IDs, %d were removed" % (
            newpacket.OwnerID, len(ids), count))

    def _on_retreive(self, newpacket):
        from system import bpio
        from userid import my_id
        from userid import global_id
        from crypt import signed
        from contacts import contactsdb
        from transport import gateway
        from p2p import p2p_service
        if not contactsdb.is_customer(newpacket.OwnerID):
            lg.err("had unknown customer %s" % newpacket.OwnerID)
            p2p_service.SendFail(newpacket, 'not a customer')
            return False
        glob_path = global_id.ParseGlobalID(newpacket.PacketID)
        if not glob_path['path']:
            # backward compatible check
            glob_path = global_id.ParseGlobalID(my_id.getGlobalID() + ':' + newpacket.PacketID)
        if not glob_path['path']:
            lg.err("got incorrect PacketID")
            p2p_service.SendFail(newpacket, 'incorrect PacketID')
            return False
        if glob_path['idurl']:
            if newpacket.CreatorID == glob_path['idurl']:
                pass  # same customer, based on CreatorID : OK!
            else:
                lg.warn('one of customers requesting a Data from another customer!')
        else:
            lg.warn('no customer global id found in PacketID: %s' % newpacket.PacketID)
        # TODO: process requests from another customer : glob_path['idurl']
        filename = p2p_service.makeFilename(newpacket.OwnerID, glob_path['path'])
        if not filename:
            if True:
                # TODO: settings.getCustomersDataSharingEnabled() and
                filename = p2p_service.makeFilename(glob_path['idurl'], glob_path['path'])
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
        self.log(self.debug_level, "service_supplier._on_retreive %r : sending %r back to %s" % (
            newpacket, outpacket, outpacket.CreatorID))
        gateway.outbox(outpacket, target=outpacket.CreatorID)
        return True

    def _on_data(self, newpacket):
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
            glob_path = global_id.ParseGlobalID(my_id.getGlobalID() + ':' + newpacket.PacketID)
        if not glob_path['path']:
            lg.err("got incorrect PacketID")
            p2p_service.SendFail(newpacket, 'incorrect PacketID')
            return False
        # TODO: process files from another customer : glob_path['idurl']
        filename = p2p_service.makeFilename(newpacket.OwnerID, glob_path['path'])
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
        p2p_service.SendAck(newpacket, str(len(newpacket.Payload)))
        from supplier import local_tester
        reactor.callLater(0, local_tester.TestSpaceTime)
        sz = len(data)
        del data
        self.log(self.debug_level, "service_supplier._on_data %r saved from [%s | %s] to %s with %d bytes" % (
            newpacket, newpacket.OwnerID, newpacket.CreatorID, filename, sz, ))
        return True

    def _on_list_files(self, newpacket):
        from supplier import list_files
        list_files.send(newpacket.OwnerID, newpacket.PacketID, newpacket.Payload)
        return True
