#!/usr/bin/python
# p2p_queue.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (p2p_queue.py) is part of BitDust Software.
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
.. module:: p2p_queue.


Methods to establish a messages queue between two or more nodes.:

    + Producers will send a messages to the queue
    + Consumers will listen to the queue and read the messages comming
    + Producer only start sending if he have a Public Key
    + Consumer can only listen if he posses the correct Private Key
    + Queue is only stored on given node: both producer and conumer must be connected to that machine
    + Global queue ID is unique : mykey!alice@somehost.net:queue_xyz
    + Queue size is limited by a parameter, you can not publish when queue is overloaded

"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys
import json

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in p2p_queue.py')

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from userid import my_id
from userid import identity
from userid import global_id

#------------------------------------------------------------------------------

def init():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.init')


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.shutdown')

#------------------------------------------------------------------------------
