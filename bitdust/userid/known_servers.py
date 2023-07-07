#!/usr/bin/python
# known_servers.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (known_servers.py) is part of BitDust Software.
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

_KnownServers = None

#------------------------------------------------------------------------------


def default_nodes():
    """
    A set of identity servers currently maintained, see file `default_network.json` in the root folder.
    """
    from bitdust.lib import strng
    from bitdust.main import network_config
    network_info = network_config.read_network_config_file()
    identity_servers = {}
    for identity_server in network_info['service_identity_propagate']['known_servers']:
        identity_servers[strng.to_bin(identity_server['host'])] = (
            identity_server['http_port'],
            identity_server.get('tcp_port', 6661),
        )
    return identity_servers


def by_host():
    """
    Here is a "well known" identity servers to support the network.
    Keys are domain names or global IP address (not recommended) of the ID server.
    Values are ``Web port`` (reading) and ``TCP port`` (writing) numbers.

    This is some kind of "genesis" network.
    If you willing to support the project and started your own BitDust node on reliable machine,
    contact us and we will include your address here.
    So other nodes will be able to use your machine to host their identities.

    You can override those "genesis" nodes by configuring list of your preferred identity servers
    in the program settings:

        api.config_set(
            "services/identity-propagate/known-servers",
            "myfirstserver.net:80, secondmachine.net:8080, thirdnode.gov.eu:80",
        )

    Also check file `default_network.json` in the repository root.

    Both ways you can create your own BitDust network, under your full control.
    """
    global _KnownServers
    from bitdust.main import config
    from bitdust.lib import strng

    if _KnownServers is not None:
        return _KnownServers

    try:
        overridden_identity_servers_str = str(config.conf().getString('services/identity-propagate/known-servers'))
    except:
        overridden_identity_servers_str = ''

    if not overridden_identity_servers_str:
        _KnownServers = default_nodes()
        return _KnownServers

    overridden_identity_servers = {}
    for id_server_str in overridden_identity_servers_str.split(','):
        if id_server_str.strip():
            try:
                id_server = id_server_str.strip().split(':')
                id_server_host = strng.to_bin(id_server[0].strip())
                id_server_web_port = int(id_server[1].strip())
                if len(id_server) > 2:
                    id_server_tcp_port = int(id_server[2].strip())
                else:
                    id_server_tcp_port = 6661
            except:
                continue
            overridden_identity_servers[id_server_host] = (
                id_server_web_port,
                id_server_tcp_port,
            )

    if overridden_identity_servers:
        _KnownServers = overridden_identity_servers
        return _KnownServers

    _KnownServers = default_nodes()
    return _KnownServers
