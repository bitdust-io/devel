# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive

""" Kademlia DHT implementation

This package contains Entangled's implementation of the Kademlia
distributed hash table (DHT).

The main modules in this package are "C{node}" (which contains the Kademlia
implementation's main interface, namely the C{Node} class), "C{datastore}"
(physical data storage mechanisms), "C{constants}" (several constant values
defining the Kademlia network), "C{routingtable}" (different Kademlia routing
table implementations) and "C{protocol}" (actual network communications).

The Node class is directly exposed in the main Entangled package
("C{entangled}") as KademliaNode, and as Node in this package
("C{entangled.kademlia}"). It is designed to be customizable; the data storage
mechansims may (and should) be directly specified by client applications via
the node's contructor. The same holds true for the node's routing table and
network protocol used. This potentially allows the Kademlia node to be used
with a TCP-based protocol, instead of the provided UDP-based one.

Client applications should also modify the values found in
C{entangled.kademlia.constants} to suit their needs. Refer to the C{constants}
module for documentation on what these values control. 
"""

from node import Node
from datastore import DictDataStore, SQLiteDataStore
