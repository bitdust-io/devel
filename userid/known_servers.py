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
    Keys are domain names or global IP address (not recommended) of the ID server.
    Values are ``Web port`` (reading) and ``TCP port`` (writing) numbers.

    This is some kind of "genesis" network.
    If you willing to support the project and started your own BitDust node on reliable machine,
    contact us and we will include your address here.
    So other nodes will be able to use your machine to host their identities.
    """
    return {
        'bitdust.io': (8084, 6661),
        'p2p-id.ru': (80, 6661),
        # 'veselin-p2p.ru': (80, 6661),
        # 'bitdust.ai': (80, 6661),
        'datahaven.net': (80, 6661),
        'identity.datahaven.net': (80, 6661),
        'work.offshore.ai': (8084, 6661),
        # 'whmcs.whois.ai': (8084, 6661),
        # 'p2p-machines.net': (80, 6661),
    }
