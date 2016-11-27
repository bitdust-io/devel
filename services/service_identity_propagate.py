#!/usr/bin/python
# service_identity_propagate.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

from services.local_service import LocalService


def create_service():
    return IdentityPropagateService()


class IdentityPropagateService(LocalService):

    service_name = 'service_identity_propagate'
    config_path = 'services/identity-propagate/enabled'

    def dependent_on(self):
        return ['service_gateway',
                'service_tcp_connections',
                ]

    def start(self):
        from userid import my_id
        my_id.loadLocalIdentity()
        if my_id._LocalIdentity is None:
            from logs import lg
            lg.warn('Loading local identity failed - need to register first')
            return False
        from contacts import identitycache
        identitycache.init()
        from contacts import contactsdb
        contactsdb.init()
        from p2p import propagate
        propagate.init()
        return True

    def stop(self):
        from p2p import propagate
        propagate.shutdown()
        from contacts import contactsdb
        contactsdb.shutdown()
        from contacts import identitycache
        identitycache.shutdown()
        from userid import my_id
        my_id.shutdown()
        return True
