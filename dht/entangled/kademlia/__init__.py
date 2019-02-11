#!/usr/bin/env python
#__init__.py
#
#
# Copyright (C) 2007-2008 Francois Aucamp, Meraka Institute, CSIR
# See AUTHORS for all authors and contact information. 
# 
# License: GNU Lesser General Public License, version 3 or later; see COPYING
#          included in this archive for details.
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

"""
Kademlia DHT implementation.

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

from __future__ import absolute_import
from . node import Node  # @UnresolvedImport
from . datastore import DictDataStore, SQLiteVersionedJsonDataStore  # @UnresolvedImport
