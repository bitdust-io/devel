#!/usr/bin/python
# service_customer.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (service_customer.py) is part of BitDust Software.
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

module:: service_customer
"""

from services.local_service import LocalService


def create_service():
    return CustomerService()


class CustomerService(LocalService):

    service_name = 'service_customer'
    config_path = 'services/customer/enabled'

    def dependent_on(self):
        return ['service_p2p_notifications',
                ]

    def installed(self):
        from userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def start(self):
        from contacts import contactsdb
        from crypt import my_keys
        from customer import supplier_connector
        from customer import customer_state
        from transport import callback
        from userid import my_id
        from logs import lg
        if not my_keys.is_key_registered(customer_state.customer_key_id()):
            lg.warn('customer key was not found, generate new key: %s' % customer_state.customer_key_id())
            my_keys.generate_key(customer_state.customer_key_id())
        for supplier_idurl in contactsdb.suppliers():
            if supplier_idurl and not supplier_connector.by_idurl(supplier_idurl, customer_idurl=my_id.getLocalID()):
                supplier_connector.create(supplier_idurl, customer_idurl=my_id.getLocalID())
        # TODO: read from dht and connect to other suppliers - from other customers who shared data to me
        callback.append_inbox_callback(self._on_inbox_packet_received)
        return True

    def stop(self):
        from customer import supplier_connector
        from transport import callback
        from userid import my_id
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        for sc in supplier_connector.connectors(my_id.getLocalID()).values():
            sc.automat('shutdown')
        # TODO: disconnect other suppliers
        return True

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        import json
        from logs import lg
        from p2p import commands
        from p2p import p2p_service
        from main import settings
        from storage import backup_fs
        from storage import backup_control
        from crypt import encrypted
        if newpacket.Command == commands.ListFiles():
            if newpacket.Payload == settings.ListFilesFormat():
                return False
            block = encrypted.Unserialize(newpacket.Payload)
            if block is None:
                lg.out(2, 'key_ring.on_key_received ERROR reading data from %s' % newpacket.RemoteID)
                return False
            try:
                raw_list_files = block.Data()
                try:
                    json_data = json.loads(raw_list_files, encoding='utf-8')
                    json_data['items']
                except Exception as exc:
                    lg.exc()
                    p2p_service.SendFail(newpacket, str(exc))
                    return False
                customer_idurl = block.CreatorID
                count = backup_fs.Unserialize(
                    raw_data=json_data,
                    iter=backup_fs.fs(customer_idurl),
                    iterID=backup_fs.fsID(customer_idurl),
                    from_json=True,
                )
            except Exception as exc:
                lg.exc()
                p2p_service.SendFail(newpacket, str(exc))
                return False
            if count > 0:
                backup_control.Save()
            p2p_service.SendAck(newpacket, str(count))
            return True
        return False
