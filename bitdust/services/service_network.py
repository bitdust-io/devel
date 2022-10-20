#!/usr/bin/python
# service_network.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_network.py) is part of BitDust Software.
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

module:: service_network
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return NetworkService()


class NetworkService(LocalService):

    service_name = 'service_network'
    config_path = 'services/network/enabled'

    current_network_interfaces = None

    def dependent_on(self):
        return [
            # this is a top root service, everything in BitDust depends on networking
        ]

    def start(self):
        from twisted.internet import task
        from bitdust.main import events
        from bitdust.p2p import network_connector
        network_connector.A('init')
        self.task = task.LoopingCall(self._do_check_network_interfaces)
        self.task.start(20, now=False)
        events.add_subscriber(self._on_my_identity_rotate_complete, 'my-identity-rotate-complete')
        events.add_subscriber(self._on_my_external_ip_changed, 'my-external-ip-changed')
        return True

    def stop(self):
        from bitdust.main import events
        from bitdust.p2p import network_connector
        events.remove_subscriber(self._on_my_external_ip_changed, 'my-external-ip-changed')
        events.remove_subscriber(self._on_my_identity_rotate_complete, 'my-identity-rotate-complete')
        network_connector.Destroy()
        if self.task and self.task.running:
            self.task.stop()
            self.task = None
        return True

    def _on_my_external_ip_changed(self, evt):
        from bitdust.logs import lg
        if evt.data['old'].strip():
            lg.info('need to reconnect because my external IP changed %r -> %r' % (evt.data['old'], evt.data['new']))
            from bitdust.p2p import network_connector
            network_connector.A('reconnect')

    def _on_my_identity_rotate_complete(self, evt):
        from bitdust.logs import lg
        from bitdust.services import driver
        if driver.is_enabled('service_gateway'):
            lg.warn('my identity sources were rotated, need to restart service_gateway()')
            #             if driver.is_enabled('service_identity_propagate'):
            #                 from bitdust.p2p import propagate
            #                 from bitdust.contacts import contactsdb
            #                 selected_contacts = set(filter(None, contactsdb.contacts_remote(include_all=True)))
            #                 if propagate.startup_list():
            #                     selected_contacts.update(propagate.startup_list())
            #                     propagate.startup_list().clear()
            #                 propagate.propagate(
            #                     selected_contacts=selected_contacts,
            #                     wide=True,
            #                     refresh_cache=True,
            #                 ).addBoth(lambda err: driver.restart('service_gateway'))
            #             else:
            driver.restart('service_gateway')
        else:
            lg.warn('my identity sources were rotated, but service_gateway() is disabled')
        return None

    def _do_check_network_interfaces(self):
        from bitdust.lib.net_misc import getNetworkInterfaces
        from bitdust.p2p import network_connector
        from bitdust.logs import lg
        known_interfaces = getNetworkInterfaces()
        if '127.0.0.1' in known_interfaces:
            known_interfaces.remove('127.0.0.1')
        if self.current_network_interfaces is None:
            self.current_network_interfaces = known_interfaces
            lg.info('current network interfaces on START UP: %r' % self.current_network_interfaces)
        else:
            if self.current_network_interfaces != known_interfaces and known_interfaces:
                lg.info('need to reconnect, recognized changes in network interfaces: %r -> %r' % (self.current_network_interfaces, known_interfaces))
                self.current_network_interfaces = known_interfaces
                network_connector.A('reconnect')
