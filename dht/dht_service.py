#!/usr/bin/python
#dht_service.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: dht_service

"""

import os
import sys
import hashlib
import random
import base64
import optparse

from twisted.internet import reactor
from twisted.internet import task
from twisted.internet.defer import Deferred

from entangled.dtuple import DistributedTupleSpacePeer
from entangled.kademlia.datastore import SQLiteDataStore
from entangled.kademlia.node import rpcmethod
from entangled.kademlia.contact import Contact

try:
    import lib.dhnio as dhnio
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    try:
        import lib.dhnio as dhnio
    except:
        sys.exit()

import lib.settings as settings

import known_nodes

#------------------------------------------------------------------------------ 

_MyNode = None
_UDPListener = None

#------------------------------------------------------------------------------ 

def init(udp_port, db_file_path=None):
    global _MyNode
    if _MyNode is not None:
        dhnio.Dprint(4, 'dht_service.init WARNING, already created a DHTNode')
        return
    dhnio.Dprint(4, 'dht_service.init UDP port is %d' % udp_port)
    if db_file_path is None:
        # db_file_path = './dht%s' % str(udp_port)
        db_file_path = settings.DHTDBFile()
    dataStore = SQLiteDataStore(dbFile=db_file_path)
    # _MyNode = DistributedTupleSpacePeer(udp_port, dataStore)
    _MyNode = DHTNode(udp_port, dataStore)
    _MyNode.listenUDP()
    

def shutdown():
    global _MyNode
    if _MyNode is not None:
        _MyNode.listener.stopListening()
        _MyNode._dataStore._db.close()
        del _MyNode
        _MyNode = None
        dhnio.Dprint(4, 'dht_service.shutdown')
    else:
        dhnio.Dprint(4, 'dht_service.shutdown WARNING - DHTNode not exist')


def node():
    global _MyNode
    return _MyNode


def connect():
#    global _UDPListener
#    if _UDPListener:
#        dhnio.Dprint(6, 'dht_service.connect already connected, skip')
#        return _UDPListener
#    if len(knownnodes) == 0:
#        knownnodes += known_nodes.nodes()
#    _UDPListener = node().joinNetwork(knownnodes)
    if node().refresher:
        node().refresher.reset(0)
        dhnio.Dprint(6, 'dht_service.connect did RESET refresher task')
    else:
        node().joinNetwork(known_nodes.nodes())
        dhnio.Dprint(6, 'dht_service.connect with %d known nodes' % (len(known_nodes.nodes())))
    return True


def disconnect():
#    global _UDPListener
#    if _UDPListener is not None:
#        dhnio.Dprint(6, 'dht_service.disconnect')
#        d = _UDPListener.stopListening()
#        del _UDPListener
#        _UDPListener = None
#        return d
#    else:
#        dhnio.Dprint(6, 'dht_service.disconnect WARNING - UDPListener is None')
    return None


def reconnect():
    # dhnio.Dprint(16, 'dht_service.reconnect')
    return node().reconnect()


def key_to_hash(key):
    h = hashlib.sha1()
    h.update(key)
    return h.digest()


def okay(result, method, key, arg=None):
    if type(result) == dict:
        v = str(result.values())
    else:
        v = 'None'
    # dhnio.Dprint(16, 'dht_service.okay   %s(%s)   result=%s' % (method, key, v[:20]))
    return result


def error(err, method, key):
    dhnio.Dprint(6, 'dht_service.error %s(%s) returned an ERROR:\n%s' % (method, key, str(err)))
    return None  


def get_value(key):
    # dhnio.Dprint(16, 'dht_service.get_value key=[%s]' % key)
    d = node().iterativeFindValue(key_to_hash(key))
    d.addCallback(okay, 'get_value', key)
    d.addErrback(error, 'get_value', key)
    return d
        

def set_value(key, value):
    # dhnio.Dprint(16, 'dht_service.set_value key=[%s] value=[%s]' % (key, str(value)[:20]))
    d = node().iterativeStore(key_to_hash(key), value)
    d.addCallback(okay, 'set_value', key, value)
    d.addErrback(error, 'set_value', key)
    return d

def delete_key(key):
    # dhnio.Dprint(16, 'dht_service.delete_key [%s]' % key)
    d = node().iterativeDelete(key_to_hash(key))
    d.addCallback(okay, 'delete_value', key)
    d.addErrback(error, 'delete_key', key)
    return d


def find_node(node_id):
    node_id64 = base64.b64encode(node_id)
    # dhnio.Dprint(16, 'dht_service.find_node   node_id=[%s]' % node_id64)
    d = node().iterativeFindNode(node_id)
    d.addCallback(okay, 'find_node', node_id64)
    d.addErrback(error, 'find_node', node_id64)
    return d
    

def random_key():
    return key_to_hash(str(random.getrandbits(255)))


def set_node_data(key, value):
    dhnio.Dprint(16, 'dht_service.set_node_data key=[%s] value: %s' % (key, str(value)[:20]))
    node().data[key] = value    
  
#------------------------------------------------------------------------------ 

class DHTNode(DistributedTupleSpacePeer):
    def __init__(self, udpPort=4000, dataStore=None, routingTable=None, networkProtocol=None):
        DistributedTupleSpacePeer.__init__(self, udpPort, dataStore, routingTable, networkProtocol)
        self.data = {}
        
    @rpcmethod
    def store(self, key, value, originalPublisherID=None, age=0, **kwargs):
        # dhnio.Dprint(18, 'dht_service.DHTNode.store key=[%s], value=[%s]' % (
        #     base64.b32encode(key), str(value)[:10]))
        return DistributedTupleSpacePeer.store(self, key, value, originalPublisherID=originalPublisherID, age=age, **kwargs)

    @rpcmethod
    def request(self, key):
        value = str(self.data.get(key, None))
        # dhnio.Dprint(18, 'dht_service.DHTNode.request key=[%s], return value=[%s]' % (base64.b32encode(key), str(value)))
        return {str(key): value}

    def reconnect(self, knownNodeAddresses=None):
        """
        TODO:
        need to restart _scheduleNextNodeRefresh
        """
        d = Deferred()
        d.callback(1)
        return d

#------------------------------------------------------------------------------ 

def parseCommandLine():
    oparser = optparse.OptionParser()
    oparser.add_option("-p", "--udpport", dest="udpport", type="int", help="specify UDP port for DHT network")
    oparser.set_default('udpport', settings.DefaultDHTPort())
    (options, args) = oparser.parse_args()
    return options, args

def main():
    dhnio.init()
    settings.init()
    dhnio.SetDebug(18)
    (options, args) = parseCommandLine()
    init(options.udpport)
    connect()
    if len(args) == 0:
        pass
    elif len(args) > 0:
        def _r(x):
            reactor.stop()
        cmd = args[0] 
        if cmd == 'get':
            get_value(args[1]).addBoth(_r)
        elif cmd == 'set':
            set_value(args[1], args[2]).addBoth(_r)
        elif cmd == 'find':
            find_node(key_to_hash(args[1])).addBoth(_r)
    reactor.run()

if __name__ == '__main__':
    main()

