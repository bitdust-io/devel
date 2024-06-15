#!/usr/bin/python
# service_identity_propagate.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_identity_propagate.py) is part of BitDust Software.
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

module:: service_identity_propagate
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return IdentityPropagateService()


class IdentityPropagateService(LocalService):

    service_name = 'service_identity_propagate'
    config_path = 'services/identity-propagate/enabled'

    def dependent_on(self):
        return [
            'service_gateway',
            'service_tcp_connections',
        ]

    def installed(self):
        from bitdust.userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def network_configuration(self):
        import re
        from bitdust.main import config
        known_identity_servers_str = str(config.conf().getString('services/identity-propagate/known-servers'))
        known_identity_servers = []
        for id_server_str in re.split('\n|;|,| ', known_identity_servers_str):
            if id_server_str.strip():
                try:
                    id_server = id_server_str.strip().split(':')
                    id_server_host = id_server[0].strip()
                    id_server_http_port = int(id_server[1].strip())
                    if len(id_server) > 2:
                        id_server_tcp_port = int(id_server[2].strip())
                    else:
                        id_server_tcp_port = 6661
                except:
                    continue
                known_identity_servers.append({
                    'host': id_server_host,
                    'tcp_port': id_server_tcp_port,
                    'http_port': id_server_http_port,
                })
        if not known_identity_servers:
            from bitdust.main import network_config
            default_network_config = network_config.read_network_config_file()
            known_identity_servers = default_network_config['service_identity_propagate']['known_servers']
        return {
            'known_servers': known_identity_servers,
            'whitelisted_servers': [],
        }

    def start(self):
        from bitdust.logs import lg
        from bitdust.userid import my_id
        from bitdust.main.config import conf
        my_id.loadLocalIdentity()
        if not my_id.isLocalIdentityReady():
            lg.warn('Loading local identity failed - need to create an identity first')
            return False
        from bitdust.main import events
        from bitdust.contacts import identitycache
        from bitdust.userid import known_servers
        from bitdust.p2p import propagate
        from bitdust.contacts import contactsdb
        identitycache.init()
        d = contactsdb.init()
        propagate.init()
        conf().addConfigNotifier('services/identity-propagate/known-servers', self._on_known_servers_changed)
        lg.info('known ID servers are : %r' % known_servers.by_host())
        events.add_subscriber(self._on_local_identity_modified, 'local-identity-modified')
        events.add_subscriber(self._on_my_identity_rotated, 'my-identity-rotated')
        return d

    def stop(self):
        from bitdust.main.config import conf
        from bitdust.main import events
        from bitdust.p2p import propagate
        from bitdust.contacts import contactsdb
        from bitdust.contacts import identitycache
        events.remove_subscriber(self._on_my_identity_rotated, 'my-identity-rotated')
        events.remove_subscriber(self._on_local_identity_modified, 'local-identity-modified')
        conf().removeConfigNotifier('services/identity-propagate/known-servers')
        propagate.shutdown()
        contactsdb.shutdown()
        identitycache.shutdown()
        return True

    def _on_known_servers_changed(self, path, value, oldvalue, result):
        from bitdust.userid import known_servers
        known_servers._KnownServers = None

    def _on_local_identity_modified(self, evt):
        from bitdust.p2p import propagate
        propagate.update()

    def _on_my_identity_rotated(self, evt):
        from bitdust.logs import lg
        from bitdust.p2p import propagate
        from bitdust.contacts import contactsdb
        known_remote_contacts = set(contactsdb.contacts_remote(include_all=True))
        propagate.startup_list().update(known_remote_contacts)
        lg.warn('added %d known contacts to propagate startup list to be sent later' % len(known_remote_contacts))
