#!/usr/bin/python
# message_subscriber.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (message_subscriber.py) is part of BitDust Software.
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

module:: message_subscriber
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import sys
import datetime
import time
import StringIO

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in message_subscriber.py')

from twisted.internet.defer import fail

#------------------------------------------------------------------------------

from logs import lg

from p2p import commands

from lib import packetid

from lib import misc

from crypt import signed
from crypt import key
from crypt import my_keys

from contacts import identitycache

from userid import my_id
from userid import global_id

from transport import gateway

#------------------------------------------------------------------------------

def init():
    lg.out(4, "message_subscriber.init")


def shutdown():
    lg.out(4, "message_subscriber.shutdown")


#------------------------------------------------------------------------------

if __name__ == "__main__":
    init()
    reactor.run()
