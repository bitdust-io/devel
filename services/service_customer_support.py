#!/usr/bin/python
# service_customer_support.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_customer_support.py) is part of BitDust Software.
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

module:: service_customer_support
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return CustomerSupportService()


class CustomerSupportService(LocalService):

    service_name = 'service_customer_support'
    config_path = 'services/customer-support/enabled'

    def dependent_on(self):
        return [
            'service_customer_patrol',
        ]

    def start(self):
        from supplier import customer_assistant
        from contacts import contactsdb
        from transport import callback
        for customer_idurl in contactsdb.customers():
            if customer_idurl and not customer_assistant.by_idurl(customer_idurl):
                ca = customer_assistant.create(customer_idurl)
                ca.automat('init')
        callback.add_outbox_callback(self._on_outbox_packet_sent)
        callback.append_inbox_callback(self._on_inbox_packet_received)
        return True

    def stop(self):
        from supplier import customer_assistant
        from transport import callback
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        callback.remove_outbox_callback(self._on_outbox_packet_sent)
        for ca in customer_assistant.assistants().values():
            ca.automat('shutdown')
        return True

    def health_check(self):
        return True

    def _on_outbox_packet_sent(self, pkt_out):
        from p2p import commands
        from contacts import contactsdb
        from supplier import customer_assistant
        if pkt_out.outpacket.Command == commands.Identity():
            if contactsdb.is_customer(pkt_out.outpacket.RemoteID):
                ca = customer_assistant.by_idurl(pkt_out.outpacket.RemoteID)
                if ca:
                    ca.automat('propagate', pkt_out)
        return False

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from p2p import commands
        from contacts import contactsdb
        from supplier import customer_assistant
        if newpacket.Command in [commands.Ack(), commands.Fail()]:
            if contactsdb.is_customer(newpacket.OwnerID):
                ca = customer_assistant.by_idurl(newpacket.OwnerID)
                if ca:
                    ca.automat(newpacket.Command.lower(), newpacket)
                    return True
        return False
