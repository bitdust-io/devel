#!/usr/bin/python
#dht_service.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (dht_service.py) is part of BitDust Software.
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
.. module:: dht_service

"""

#------------------------------------------------------------------------------ 

_Debug = False
_DebugLevel = 14

#------------------------------------------------------------------------------ 

import sys
import hashlib
import random
import base64
import optparse

from twisted.internet import reactor
from twisted.internet.defer import Deferred, fail

from entangled.dtuple import DistributedTupleSpacePeer
from entangled.kademlia.datastore import SQLiteDataStore
from entangled.kademlia.node import rpcmethod
from entangled.kademlia.protocol import KademliaProtocol, encoding, msgformat

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio

from main import settings

import known_nodes

#------------------------------------------------------------------------------ 

_MyNode = None
_UDPListener = None

#------------------------------------------------------------------------------ 

def init(udp_port, db_file_path=None):
    global _MyNode
    if _MyNode is not None:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.init SKIP, already created a DHTNode')
        return
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.init UDP port is %d' % udp_port)
    if db_file_path is None:
        db_file_path = settings.DHTDBFile()
    dbPath = bpio.portablePath(db_file_path)
    lg.out(4, 'dht_service.init UDP port is %d, DB file path: %s' % (udp_port, dbPath))
    dataStore = SQLiteDataStore(dbFile=dbPath)
    networkProtocol = KademliaProtocolConveyor
        # None, encoding.Bencode(), msgformat.DefaultFormat())
    _MyNode = DHTNode(udp_port, dataStore, networkProtocol=networkProtocol)
    # _MyNode._protocol.node = _MyNode
    

def shutdown():
    global _MyNode
    if _MyNode is not None:
        _MyNode.listener.stopListening()
        _MyNode._dataStore._db.close()
        _MyNode._protocol.node = None
        del _MyNode
        _MyNode = None
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.shutdown')
    else:
        lg.warn('DHTNode not exist')

#------------------------------------------------------------------------------ 

def node():
    global _MyNode
    return _MyNode


def connect():
    if not node().listener:
        node().listenUDP()
    if node().refresher and node().refresher.active():
        node().refresher.reset(0)
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect did RESET refresher task')
    else:
        node().joinNetwork(known_nodes.nodes())
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect with %d known nodes' % (len(known_nodes.nodes())))
    return True


def disconnect():
#    global _UDPListener
#    if _UDPListener is not None:
#        lg.out(6, 'dht_service.disconnect')
#        d = _UDPListener.stopListening()
#        del _UDPListener
#        _UDPListener = None
#        return d
#    else:
#        lg.warn('- UDPListener is None')
    return None


def reconnect():
    if _Debug:
        lg.out(_DebugLevel + 10, 'dht_service.reconnect')
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
    if _Debug:
        lg.out(_DebugLevel + 10, 'dht_service.okay   %s(%s)   result=%s ...' % (method, key, v[:20]))
    return result


def error(err, method, key):
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.error %s(%s) returned an ERROR:\n%s' % (method, key, str(err)))
    return err  


def get_value(key):
    if _Debug:
        lg.out(_DebugLevel + 10, 'dht_service.get_value key=[%s]' % key)
    if not node():
        return fail(Exception('DHT service is off'))
    d = node().iterativeFindValue(key_to_hash(key))
    d.addCallback(okay, 'get_value', key)
    d.addErrback(error, 'get_value', key)
    return d
        

def set_value(key, value, age=0):
    if _Debug:
        lg.out(_DebugLevel + 10, 'dht_service.set_value key=[%s] value=[%s]' % (key, str(value)[:20]))
    if not node():
        return fail(Exception('DHT service is off'))
    d = node().iterativeStore(key_to_hash(key), value, age=age)
    d.addCallback(okay, 'set_value', key, value)
    d.addErrback(error, 'set_value', key)
    return d


def delete_key(key):
    if _Debug:
        lg.out(_DebugLevel + 10, 'dht_service.delete_key [%s]' % key)
    if not node():
        return fail(Exception('DHT service is off'))
    d = node().iterativeDelete(key_to_hash(key))
    d.addCallback(okay, 'delete_value', key)
    d.addErrback(error, 'delete_key', key)
    return d
    

def random_key():
    return key_to_hash(str(random.getrandbits(255)))


def set_node_data(key, value):
    if not node():
        return
    if _Debug:
        lg.out(_DebugLevel + 10, 'dht_service.set_node_data key=[%s] value: %s' % (key, str(value)[:20]))
    node().data[key] = value    


def find_node(node_id):
    node_id64 = base64.b64encode(node_id)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.find_node   node_id=[%s]' % node_id64)
    if not node():
        return fail(Exception('DHT service is off'))
    d = node().iterativeFindNode(node_id)
    d.addCallback(okay, 'find_node', node_id64)
    d.addErrback(error, 'find_node', node_id64)
    return d

#------------------------------------------------------------------------------ 

class DHTNode(DistributedTupleSpacePeer):
    def __init__(self, udpPort=4000, dataStore=None, routingTable=None, networkProtocol=None):
        DistributedTupleSpacePeer.__init__(self, udpPort, dataStore, routingTable, networkProtocol)
        self.data = {}
        
    if _Debug:
        @rpcmethod
        def store(self, key, value, originalPublisherID=None, age=0, **kwargs):
            if _Debug:
                lg.out(_DebugLevel + 10, 'dht_service.DHTNode.store key=[%s], value=[%s]' % (
                    base64.b32encode(key), str(value)[:20]))
            return DistributedTupleSpacePeer.store(self, key, value, 
                originalPublisherID=originalPublisherID, age=age, **kwargs)

    @rpcmethod
    def request(self, key):
        value = str(self.data.get(key, None))
        if _Debug:
            lg.out(_DebugLevel + 10, 'dht_service.DHTNode.request key=[%s], return value=[%s]' % (
                base64.b32encode(key), str(value)[:20]))
        return {str(key): value}

    def reconnect(self, knownNodeAddresses=None):
        """
        TODO:
        need to restart _scheduleNextNodeRefresh
        """
        d = Deferred()
        if not self.listener:
            d.errback('Listener not started yet')
            return d
        if self.refresher and self.refresher.active():
            self.refresher.reset(0)
        d.callback(1)
        return d

#------------------------------------------------------------------------------ 

class KademliaProtocolConveyor(KademliaProtocol):
    
    def __init__(self, node, msgEncoder=encoding.Bencode(), msgTranslator=msgformat.DefaultFormat()):
        KademliaProtocol.__init__(self, node, msgEncoder, msgTranslator)
        self.datagrams_queue = []
        self.worker = None
    
    def datagramReceived(self, datagram, address):
        if len(self.datagrams_queue) > 10:
            # TODO: 
            # seems like DHT traffic is too huge at that moment
            # need to find some solution here probably
            return
        self.datagrams_queue.append((datagram, address))
        if self.worker is None:
            self.worker = reactor.callLater(0, self._process)

    def _process(self):
        if len(self.datagrams_queue) == 0:
            self.worker = None
            return
        # if _Debug:
        #     print '                dht._process, queue length:', len(self.datagrams_queue)
        datagram, address = self.datagrams_queue.pop(0)
        KademliaProtocol.datagramReceived(self, datagram, address)
        self.worker = reactor.callLater(0.005, self._process)

#------------------------------------------------------------------------------ 

def parseCommandLine():
    oparser = optparse.OptionParser()
    oparser.add_option("-p", "--udpport", dest="udpport", type="int", help="specify UDP port for DHT network")
    oparser.set_default('udpport', settings.DefaultDHTPort())
    oparser.add_option("-d", "--dhtdb", dest="dhtdb", help="specify DHT database file location")
    oparser.set_default('dhtdb', settings.DHTDBFile())
    (options, args) = oparser.parse_args()
    return options, args

def main():
    bpio.init()
    settings.init()
    lg.set_debug_level(18)
    (options, args) = parseCommandLine()
    init(options.udpport, options.dhtdb)
    connect()
    if len(args) == 0:
        pass
    elif len(args) > 0:
        def _r(x):
            print x
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

