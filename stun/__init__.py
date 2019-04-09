#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
#
#
#
#

"""
.. module:: stun.

To detect my external IP and PORT I need to contact someone and ask for response.
This is a STUN server and client idea, very simple.

Every user starts own STUN server - he listen on UDP port for incoming datagrams.

Another user use DHT to pick a random peer in the network
and tries to connect to his STUN server to detect own IP address.
"""
