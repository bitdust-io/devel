#!/usr/bin/env python
#__init__.py
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
Entangled DHT and distributed tuple space.

The distributed hash table (DHT) used by Entangled is based on Kademlia,
and be accessed by the C{entangled.kademlia package}, or by simply
instantiating/subclassing the exposed C{KademliaNode} in the main C{entangled}
package.

On top of this Kademlia node Entangled provides some extra functionality
in the form of a "C{DELETE}" RPC and keyword-based search operations; these
functions are accessible via the C{EntangledNode} class in the main
C{entangled} package.

The Entangled distributed tuple space is exposed as the
C{DistributedTupleSpacePeer} class, accessible via the main C{entangled}
package or its C{dtuple} module.
"""

from __future__ import absolute_import
from .kademlia.node import Node as KademliaNode
from .node import EntangledNode
from .dtuple import DistributedTupleSpacePeer
