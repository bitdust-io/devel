#!/usr/bin/python
# service_nodes_lookup.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_nodes_lookup.py) is part of BitDust Software.
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

module:: service_nodes_lookup
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return NodesLookupService()


class NodesLookupService(LocalService):

    service_name = 'service_nodes_lookup'
    config_path = 'services/nodes-lookup/enabled'

    def dependent_on(self):
        # TODO:
        # in future we can use other methods to discover nodes
        # it can be hard-coded list of nodes
        # blockchains, or some kind of broadcasting solution, or other ways
        # then we redefine that logic in lookup_method
        return [
            'service_entangled_dht',
            'service_p2p_hookups',
        ]

    def start(self):
        from p2p import lookup
        lookup.init(lookup_method=lookup.lookup_in_dht,
                    observe_method=lookup.observe_dht_node,
                    process_method=lookup.process_idurl)
        lookup.start(count=2, consume=False)
        return True

    def stop(self):
        from p2p import lookup
        lookup.shutdown()
        return True
