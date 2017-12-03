#!/usr/bin/python
# service_nodes_lookup.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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
                'service_p2p_hookups',
                ]

    def start(self):
        from p2p import lookup
        lookup.init(lookup_method=self._lookup_in_dht,
                    observe_method=self._observe_dht_node,
                    process_method=self._process_idurl)
        lookup.start(count=2, consume=False)
        return True

    def stop(self):
        from p2p import lookup
        lookup.shutdown()
        return True

    def _lookup_in_dht(self, **kwargs):
        from dht import dht_service
        from logs import lg
        lg.out(12, 'service_nodes_lookup._lookup_in_dht')
        return dht_service.find_node(dht_service.random_key())

    def _on_node_observed(self, idurl_response):
        from logs import lg
        lg.out(12, 'service_nodes_lookup._on_node_observed : %s' % idurl_response)
        return idurl_response

    def _observe_dht_node(self, node):
        from twisted.internet.defer import Deferred
        from logs import lg
        lg.out(12, 'service_nodes_lookup._observe_dht_node %s' % node)
        result = Deferred()
        d = node.request('idurl')
        d.addCallback(lambda response: result.callback(response.get('idurl')))
        d.addErrback(result.errback)
        result.addCallback(self._on_node_observed)
        return result

    def _process_idurl(self, idurl, node):
        from twisted.internet.defer import Deferred
        from contacts import identitycache
        from logs import lg
        lg.out(12, 'service_nodes_lookup._process_idurl %s' % idurl)
        result = Deferred()
        d = identitycache.immediatelyCaching(idurl)
        d.addCallback(lambda src: result.callback(idurl))
        d.addErrback(result.errback)
        return result
