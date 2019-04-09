#!/usr/bin/python
# known_nodes.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import

import os
import re

#------------------------------------------------------------------------------

def default_nodes():
    """
    List of DHT nodes currently maintained : (host, UDP port number)
    """
    from system import bpio
    from system import local_fs
    from lib import serialization
    from lib import strng
    from main import settings
    # from logs import lg
    networks_json = serialization.BytesToDict(
        local_fs.ReadBinaryFile(os.path.join(bpio.getExecutableDir(), 'networks.json')),
        keys_to_text=True,
        values_to_text=True,
    )
    my_network = local_fs.ReadTextFile(settings.NetworkFileName()).strip()
    if not my_network:
        my_network = 'main'
    if my_network not in networks_json:
        my_network = 'main'
    network_info = networks_json[my_network]
    dht_seeds = []
    for dht_seed in network_info['dht-seeds']:
        dht_seeds.append((strng.to_bin(dht_seed['host']), dht_seed['udp_port'], ))
    # lg.info('Active network is [%s]   dht_seeds=%s' % (my_network, dht_seeds, ))
    return dht_seeds


def nodes():
    """
    Here is a well known DHT nodes, this is "genesis" network.
    Every new node in the network will first connect one or several of those nodes,
    and then will be routed to some other nodes already registered.

    Right now we have started several BitDust nodes on vps hosting across the world.
    If you willing to support the project and already started your own BitDust node on reliable machine,
    contact us and we will include your address here.
    So other nodes will be able to use your machine to connect to DHT network.

    The load is not big, but as network will grow we will have more machines listed here,
    so all traffic, maintanance and ownership will be distributed across the world.

    You can override those "genesis" nodes (before you join network first time)
    by configuring list of your preferred DHT nodes (host or IP address) in the program settings:

        api.config_set(
            "services/entangled-dht/known-nodes",
            "firstnode.net:14441, secondmachine.com:1234, 123.45.67.89:9999",
        )

    This way you can create your own DHT network, inside BitDust, under your full control.
    """

    from main import config
    from lib import strng

    try:
        overridden_dht_nodes_str = str(config.conf().getData('services/entangled-dht/known-nodes'))
    except:
        overridden_dht_nodes_str = ''

    if overridden_dht_nodes_str in ['genesis', 'root', b'genesis', b'root', ]:
        # "genesis" node must not connect anywhere
        return []

    if not overridden_dht_nodes_str:
        return default_nodes()

    overridden_dht_nodes = []
    for dht_node_str in re.split('\n|;|,| ', overridden_dht_nodes_str):
        if dht_node_str.strip():
            try:
                dht_node = dht_node_str.strip().split(':')
                dht_node_host = strng.to_bin(dht_node[0].strip())
                dht_node_port = int(dht_node[1].strip())
            except:
                continue
            overridden_dht_nodes.append((dht_node_host, dht_node_port, ))

    if overridden_dht_nodes:
        # from logs import lg
        # lg.info('DHT seeds was overridden in local settings: %s' % overridden_dht_nodes)
        return overridden_dht_nodes

    return default_nodes()
