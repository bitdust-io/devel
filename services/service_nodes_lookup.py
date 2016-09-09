#!/usr/bin/python
#service_nodes_lookup.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_nodes_lookup

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
