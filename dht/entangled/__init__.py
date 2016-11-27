#!/usr/bin/env python
#__init__.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (__init__.py) is part of BitDust Software.
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
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive

""" Entangled DHT and distributed tuple space

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

from kademlia.node import Node as KademliaNode
from node import EntangledNode
from dtuple import DistributedTupleSpacePeer
