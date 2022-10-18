#!/usr/bin/python
# service_customer_support.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from bitdust.services.local_service import LocalService


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
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.userid import id_url
        from bitdust.main import events
        from bitdust.supplier import customer_assistant
        from bitdust.contacts import contactsdb
        from bitdust.transport import callback
        for customer_idurl in contactsdb.customers():
            if id_url.is_cached(customer_idurl):
                if customer_idurl and not customer_assistant.by_idurl(customer_idurl):
                    ca = customer_assistant.create(customer_idurl)
                    reactor.callLater(0, ca.automat, 'init')  # @UndefinedVariable
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        callback.add_outbox_callback(self._on_outbox_packet_sent)
        callback.append_inbox_callback(self._on_inbox_packet_received)
        return True

    def stop(self):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.main import events
        from bitdust.supplier import customer_assistant
        from bitdust.transport import callback
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        callback.remove_outbox_callback(self._on_outbox_packet_sent)
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        for ca in customer_assistant.assistants().values():
            reactor.callLater(0, ca.automat, 'shutdown')  # @UndefinedVariable
        return True

    def health_check(self):
        return True

    def _on_outbox_packet_sent(self, pkt_out):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.p2p import commands
        from bitdust.contacts import contactsdb
        from bitdust.supplier import customer_assistant
        if pkt_out.outpacket.Command == commands.Identity():
            if contactsdb.is_customer(pkt_out.outpacket.RemoteID):
                ca = customer_assistant.by_idurl(pkt_out.outpacket.RemoteID)
                if ca:
                    reactor.callLater(0, ca.automat, 'propagate', pkt_out)  # @UndefinedVariable
        return False

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.p2p import commands
        from bitdust.contacts import contactsdb
        from bitdust.supplier import customer_assistant
        if newpacket.Command in [commands.Ack(), commands.Fail()]:
            if contactsdb.is_customer(newpacket.OwnerID):
                ca = customer_assistant.by_idurl(newpacket.OwnerID)
                if ca:
                    reactor.callLater(0, ca.automat, newpacket.Command.lower(), newpacket)  # @UndefinedVariable
                    return True
        return False

    def _on_identity_url_changed(self, evt):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.userid import id_url
        from bitdust.supplier import customer_assistant
        for customer_idurl, ca in customer_assistant.assistants().items():
            if customer_idurl == id_url.field(evt.data['old_idurl']):
                customer_idurl.refresh(replace_original=True)
                ca.customer_idurl.refresh(replace_original=True)
                lg.info('found %r to be refreshed after rotated identity: %r' % (ca, customer_idurl))
                reactor.callLater(0, ca.automat, 'connect')  # @UndefinedVariable
