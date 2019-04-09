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
        my_id.loadLocalIdentity()
        if my_id._LocalIdentity is None:
            lg.warn('Loading local identity failed - need to create an identity first')
            return False
        from contacts import identitycache
        identitycache.init()
        from contacts import contactsdb
        contactsdb.init()
        from p2p import propagate
        propagate.init()
        from userid import known_servers
        lg.info('known ID servers are : %r' % known_servers.by_host())
        return True

    def stop(self):
        from p2p import propagate
        propagate.shutdown()
        from contacts import contactsdb
        contactsdb.shutdown()
        from contacts import identitycache
        identitycache.shutdown()
        return True
