#!/usr/bin/python
# known_nodes.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (known_nodes.py) is part of BitDust Software.
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

module:: known_nodes
"""

#------------------------------------------------------------------------------


def nodes():
    """
    Here is a well known DHT nodes, this is "genesis" network.
    Every new node in the network will first connect one or several of those nodes,
    and then will be routed to some other nodes already registered.

    Right now we have started several BitDust nodes on vps hostsing across the world.
    If you willing to support the project and already started your own BitDust node on reliable machine,
    contact us and we will include your address here.
    So other nodes will be able to use your machine to connect to DHT network.

    The load is not big and as network will grow we will have more machines listed here,
    so all traffic will be distributed accross the web.
    """
    return [
        ('208.78.96.185', 14441),  # datahaven.net
        ('67.207.147.183', 14441), # identity.datahaven.net
        ('185.5.250.123', 14441),  # p2p-id.ru
        ('86.110.117.159', 14441), # veselin-p2p.ru
        ('185.65.200.231', 14441), # bitdust.io
        ('45.32.246.95', 14441),   # bitdust.ai
        ('209.59.119.33', 14441),  # work.offshore.ai
    ]
