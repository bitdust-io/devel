#!/usr/bin/python
# service_identity_propagate.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
from services.local_service import LocalService


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
        from userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def start(self):
        from logs import lg
        from userid import my_id
        from main.config import conf
        my_id.loadLocalIdentity()
        if my_id._LocalIdentity is None:
            lg.warn('Loading local identity failed - need to create an identity first')
            return False
        from contacts import identitycache
        from userid import known_servers
        from p2p import propagate
        from contacts import contactsdb
        identitycache.init()
        d = contactsdb.init()
        propagate.init()
        conf().addConfigNotifier('services/identity-propagate/known-servers', self._on_known_servers_changed)
        lg.info('known ID servers are : %r' % known_servers.by_host())
        return d

    def stop(self):
        from main.config import conf
        from p2p import propagate
        from contacts import contactsdb
        from contacts import identitycache
        conf().removeConfigNotifier('services/identity-propagate/known-servers')
        propagate.shutdown()
        contactsdb.shutdown()
        identitycache.shutdown()
        return True

    def _on_known_servers_changed(self, path, value, oldvalue, result):
        from userid import known_servers
        known_servers._KnownServers = None
