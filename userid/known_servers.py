#!/usr/bin/python
# known_servers.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
#
#
#


def by_host():
    """
    Here is a well known identity servers to support the network.
    Values are ``Web port`` and ``TCP port`` numbers.
    Keys are domain names or global IP address of the server.
    """
    return {
        'p2p-machines.net': (80, 6661),  # 37.18.255.32
        'p2p-id.ru': (80, 6661),  # 37.18.255.33
        'veselin-p2p.ru': (80, 6661),  # 37.18.255.34
        'bitdust.io': (8084, 6661),
    }
