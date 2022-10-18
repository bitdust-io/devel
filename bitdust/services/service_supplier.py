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
from bitdust.services.local_service import LocalService


def create_service():
    return SupplierService()


class SupplierService(LocalService):

    service_name = 'service_supplier'
    config_path = 'services/supplier/enabled'

    def dependent_on(self):
        return [
            'service_keys_registry',
        ]

    def installed(self):
        from bitdust.userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def attached_dht_layers(self):
        from bitdust.dht import dht_records
        return [
            dht_records.LAYER_SUPPLIERS,
        ]

    def start(self):
        from bitdust.logs import lg
        from bitdust.transport import callback
        from bitdust.main import events
        from bitdust.contacts import contactsdb
        from bitdust.storage import accounting
        from bitdust.services import driver
        from bitdust.supplier import customer_space
        callback.append_inbox_callback(self._on_inbox_packet_received)
        events.add_subscriber(customer_space.on_identity_url_changed, 'identity-url-changed')
        events.add_subscriber(customer_space.on_customer_accepted, 'existing-customer-accepted')
        events.add_subscriber(customer_space.on_customer_accepted, 'new-customer-accepted')
        events.add_subscriber(customer_space.on_customer_terminated, 'existing-customer-denied')
        events.add_subscriber(customer_space.on_customer_terminated, 'existing-customer-terminated')
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
            self._do_connect_suppliers_dht_layer()
        else:
            lg.warn('service service_entangled_dht is OFF')
        events.add_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        return True

    def stop(self):
        from bitdust.transport import callback
        from bitdust.main import events
        from bitdust.services import driver
        from bitdust.supplier import customer_space
        events.remove_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        if driver.is_on('service_entangled_dht'):
            from bitdust.dht import dht_service
            from bitdust.dht import dht_records
            dht_service.suspend(layer_id=dht_records.LAYER_SUPPLIERS)
        events.remove_subscriber(customer_space.on_customer_accepted, 'existing-customer-accepted')
        events.remove_subscriber(customer_space.on_customer_accepted, 'new-customer-accepted')
        events.remove_subscriber(customer_space.on_customer_terminated, 'existing-customer-denied')
        events.remove_subscriber(customer_space.on_customer_terminated, 'existing-customer-terminated')
        events.remove_subscriber(customer_space.on_identity_url_changed, 'identity-url-changed')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        return True

    def request(self, json_payload, newpacket, info):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.main import events
        from bitdust.crypt import my_keys
        from bitdust.p2p import p2p_service
        from bitdust.contacts import contactsdb
        from bitdust.storage import accounting
        from bitdust.supplier import customer_space
        from bitdust.userid import id_url
        from bitdust.userid import global_id
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
        key_id = json_payload.get('key_id')
        key_id = my_keys.latest_key_id(key_id)
        target_customer_id = json_payload.get('customer_id')
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
                # TODO: for now just stop it
                lg.warn('under construction, key_id=%s customer_idurl=%s target_customer_idurl=%s' % (key_id, customer_idurl, target_customer_idurl))
                p2p_service.SendFail(newpacket, 'under construction')
                return False
            customer_space.register_customer_key(customer_public_key_id, customer_public_key)
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
            return p2p_service.SendFail(newpacket, 'broken space file')
        if (customer_idurl not in current_customers and customer_idurl.to_bin() in list(space_dict.keys())):
            lg.warn('broken space file')
            return p2p_service.SendFail(newpacket, 'broken space file')
        if (customer_idurl in current_customers and customer_idurl.to_bin() not in list(space_dict.keys())):
            # seems like customer's idurl was rotated, but space file still have the old idurl
            # need to find that old idurl value and replace with the new one
            for other_customer_idurl in space_dict.keys():
                if other_customer_idurl and other_customer_idurl != 'free' and id_url.field(other_customer_idurl) == customer_idurl:
                    lg.info('found rotated customer identity in space file, switching: %r -> %r' % (other_customer_idurl, customer_idurl.to_bin()))
                    space_dict[customer_idurl.to_bin()] = space_dict.pop(other_customer_idurl)
                    break
            if customer_idurl.to_bin() not in list(space_dict.keys()):
                lg.warn('broken customers file')
                return p2p_service.SendFail(newpacket, 'broken customers file')
        if customer_idurl in current_customers:
            free_bytes += int(space_dict.get(customer_idurl.to_bin(), 0))
            current_customers.remove(customer_idurl)
            space_dict.pop(customer_idurl.to_bin())
            new_customer = False
        else:
            new_customer = True
        # lg.args(8, new_customer=new_customer, current_allocated_bytes=space_dict.get(customer_idurl.to_bin()))
        from bitdust.supplier import local_tester
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
        customer_space.register_customer_key(customer_public_key_id, customer_public_key)
        reactor.callLater(0, local_tester.TestUpdateCustomers)  # @UndefinedVariable
        if new_customer:
            lg.info('NEW CUSTOMER: ACCEPTED   %s family_position=%s ecc_map=%s allocated_bytes=%s' % (customer_idurl, family_position, ecc_map, bytes_for_customer))
            events.send('new-customer-accepted', data=dict(
                idurl=customer_idurl,
                allocated_bytes=bytes_for_customer,
                ecc_map=ecc_map,
                position=family_position,
                family_snapshot=family_snapshot,
                key_id=customer_public_key_id,
            ))
        else:
            lg.info('OLD CUSTOMER: ACCEPTED  %s family_position=%s ecc_map=%s allocated_bytes=%s' % (customer_idurl, family_position, ecc_map, bytes_for_customer))
            events.send('existing-customer-accepted', data=dict(
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
        from bitdust.logs import lg
        from bitdust.main import events
        from bitdust.p2p import p2p_service
        from bitdust.contacts import contactsdb
        from bitdust.storage import accounting
        from bitdust.crypt import my_keys
        customer_idurl = newpacket.OwnerID
        try:
            customer_public_key = json_payload['customer_public_key']
            customer_public_key_id = customer_public_key['key_id']
        except:
            customer_public_key = None
            customer_public_key_id = None
        customer_ecc_map = json_payload.get('ecc_map')
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
        # TODO: erase customer's groups keys also
        from bitdust.supplier import local_tester
        reactor.callLater(0, local_tester.TestUpdateCustomers)  # @UndefinedVariable
        lg.info('OLD CUSTOMER TERMINATED %r' % customer_idurl)
        events.send('existing-customer-terminated', data=dict(idurl=customer_idurl, ecc_map=customer_ecc_map))
        return p2p_service.SendAck(newpacket, 'accepted')

    def _do_connect_suppliers_dht_layer(self):
        from bitdust.logs import lg
        from bitdust.dht import dht_service
        from bitdust.dht import dht_records
        from bitdust.dht import known_nodes
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
        from bitdust.p2p import commands
        from bitdust.supplier import customer_space
        if newpacket.Command == commands.DeleteFile():
            return customer_space.on_delete_file(newpacket)
        elif newpacket.Command == commands.DeleteBackup():
            return customer_space.on_delete_backup(newpacket)
        elif newpacket.Command == commands.Retrieve():
            return customer_space.on_retrieve(newpacket)
        elif newpacket.Command == commands.Data():
            return customer_space.on_data(newpacket)
        elif newpacket.Command == commands.ListFiles():
            return customer_space.on_list_files(newpacket)
        return False

    def _on_suppliers_dht_layer_connected(self, ok):
        from bitdust.logs import lg
        from bitdust.dht import dht_service
        from bitdust.dht import dht_records
        from bitdust.userid import my_id
        lg.info('connected to DHT layer for suppliers: %r' % ok)
        if my_id.getIDURL():
            dht_service.set_node_data('idurl', my_id.getIDURL().to_text(), layer_id=dht_records.LAYER_SUPPLIERS)
        return ok

    def _on_dht_layer_connected(self, evt):
        from bitdust.dht import dht_records
        if evt.data['layer_id'] == 0:
            self._do_connect_suppliers_dht_layer()
        elif evt.data['layer_id'] == dht_records.LAYER_SUPPLIERS:
            self._on_suppliers_dht_layer_connected(True)
