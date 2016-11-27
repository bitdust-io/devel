#!/usr/bin/python
# service_nodes_lookup.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
        # or some broadcasting, or other ways
        # then we redefine that in lookup_method
        return ['service_entangled_dht',
                'service_identity_propagate',
                ]

    def start(self):
        from p2p import lookup
        lookup.init(lookup_method=self.lookup_in_dht,
                    observe_method=self.observe_dht_node,
                    process_method=self.process_idurl)
        lookup.start(count=5, consume=False)
        return True

    def stop(self):
        from p2p import lookup
        lookup.shutdown()
        return True

    def lookup_in_dht(self, **kwargs):
        from dht import dht_service
        return dht_service.find_node(dht_service.random_key())

    def observe_dht_node(self, node):
        from twisted.internet.defer import Deferred
        result = Deferred()
        d = node.request('idurl')
        d.addCallback(lambda response: result.callback(response.get('idurl')))
        d.addErrback(result.errback)
        return result

    def process_idurl(self, idurl, node):
        from twisted.internet.defer import Deferred
        from contacts import identitycache
        result = Deferred()
        d = identitycache.immediatelyCaching(idurl)
        d.addCallback(lambda src: result.callback(idurl))
        d.addErrback(result.errback)
        return result
