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
                    process_method=self.process_dht_node)
        lookup.start(count=5)
        return True
    
    def stop(self):
        from p2p import lookup
        lookup.shutdown()
        return True

    def lookup_in_dht(self, **kwargs):
        from twisted.internet.defer import Deferred
        from dht import dht_service
        result = Deferred()
        d = dht_service.find_node(dht_service.random_key())
        d.addErrback(lambda err: result.callback([]))
        return result

    def observe_dht_node(self, node, key):
        return node.request(key)

    def process_dht_node(self, response, key):
        try:
            value = response[key]
        except:
            value = None
        if not value or value == 'None':
            return None
        if key == 'idurl':
            from contacts import identitycache
            return identitycache.immediatelyCaching(value)
        from twisted.internet.defer import Deferred
        result = Deferred()
        result.callback(value)
        return result
