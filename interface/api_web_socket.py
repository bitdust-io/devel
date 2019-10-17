#!/usr/bin/python
# api_web_socket.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (api_web_socket.py) is part of BitDust Software.
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

module:: api_web_socket
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.internet.protocol import Protocol, Factory
from twisted.application.strports import listen

#------------------------------------------------------------------------------

from lib import txws

#------------------------------------------------------------------------------

_WebSocketListener = None

#------------------------------------------------------------------------------

def init():
    """
    """
    global _WebSocketListener
    _WebSocketListener = listen("tcp:5600", txws.WebSocketFactory(EchoFactory()))


def shutdown():
    """
    """
    global _WebSocketListener
    _WebSocketListener

#------------------------------------------------------------------------------

class EchoProtocol(Protocol):
    def dataReceived(self, data):
        self.transport.write(data)

class EchoFactory(Factory):
    protocol = EchoProtocol

#------------------------------------------------------------------------------
