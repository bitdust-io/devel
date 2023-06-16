#!/usr/bin/python
# known_bismuth_nodes.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (known_bismuth_nodes.py) is part of BitDust Software.
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

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_KnownBismuthNodes = None

#------------------------------------------------------------------------------


def default_nodes():
    """
    A set of Bismuth nodes currently maintained, see file `default_network.json` in the root folder.
    """
    from bitdust.main import network_config
    network_info = network_config.read_network_config_file()
    nodes = {}
    for node in network_info['service_bismuth_blockchain']['known_nodes']:
        nodes[node['host']] = {
            'host': node['host'],
            'node_tcp_port': node.get('node_tcp_port'),
            'mining_pool_tcp_port': node.get('mining_pool_tcp_port'),
            'explorer_http_port': node.get('explorer_http_port'),
        }
    return nodes


def by_host():
    global _KnownBismuthNodes

    if _KnownBismuthNodes is not None:
        return _KnownBismuthNodes

    _KnownBismuthNodes = default_nodes()
    return _KnownBismuthNodes


def nodes_by_host():
    return {node['host']: node['node_tcp_port'] for node in by_host().values() if node.get('node_tcp_port')}


def mining_pools_by_host():
    return {node['host']: node['mining_pool_tcp_port'] for node in by_host().values() if node.get('mining_pool_tcp_port')}


def explorers_by_host():
    return {node['host']: node['explorer_http_port'] for node in by_host().values() if node.get('explorer_http_port')}


def foundation_miners():
    from bitdust.main import network_config
    network_info = network_config.read_network_config_file()
    return network_info['service_bismuth_blockchain']['foundation_miners']
