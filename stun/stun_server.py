#!/usr/bin/env python
# stun_server.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (stun_server.py) is part of BitDust Software.
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


"""
.. module:: stun_server.

BitDust stun_server() Automat

EVENTS:
    * :red:`datagram-received`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

import os
import sys

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

from automats import automat

from lib import net_misc
from lib import udp

from dht import dht_service

#------------------------------------------------------------------------------

_StunServer = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _StunServer
    if _StunServer is None:
        # set automat name and starting state here
        _StunServer = StunServer(
            name='stun_server',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _StunServer.automat(event, *args, **kwargs)
    return _StunServer


def Destroy():
    """
    Destroy stun_server() automat and remove its instance from memory.
    """
    global _StunServer
    if _StunServer is None:
        return
    _StunServer.destroy()
    del _StunServer
    _StunServer = None


class StunServer(automat.Automat):
    """
    This class implements all the functionality of the ``stun_server()`` state
    machine.
    """

    fast = True

    def init(self):
        self.listen_port = None

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state is 'AT_STARTUP':
            if event == 'start':
                self.state = 'LISTEN'
                self.doInit(*args, **kwargs)
        #---LISTEN---
        elif self.state is 'LISTEN':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doStop(*args, **kwargs)
            elif event == 'datagram-received' and self.isSTUN(*args, **kwargs):
                self.doSendYourIPPort(*args, **kwargs)
        #---STOPPED---
        elif self.state is 'STOPPED':
            if event == 'start':
                self.state = 'LISTEN'
                self.doInit(*args, **kwargs)

    def isSTUN(self, *args, **kwargs):
        """
        Condition method.
        """
        try:
            datagram, address = args[0]
            command, payload = datagram
        except:
            return False
        return command == udp.CMD_STUN

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.listen_port = args[0]
        if udp.proto(self.listen_port):
            udp.proto(self.listen_port).add_callback(self._datagramReceived)
            lg.info('callback added to listen on UDP port %d' % self.listen_port)
        else:
            lg.err('udp port %s is not opened' % self.listen_port)
        # try:
        #     externalPort = int(bpio.ReadTextFile(settings.ExternalUDPPortFilename()))
        # except:
        #     lg.exc()
        externalPort = self.listen_port
        dht_service.set_node_data('stun_port', externalPort)

    def doStop(self, *args, **kwargs):
        """
        Action method.
        """
        if udp.proto(self.listen_port):
            udp.proto(self.listen_port).remove_callback(self._datagramReceived)
        else:
            lg.err('udp port %s is not opened' % self.listen_port)

    def doSendYourIPPort(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            datagram, address = args[0]
            command, payload = datagram
        except:
            return False
        youripport = net_misc.pack_address((address[0], address[1]))
        udp.send_command(self.listen_port, udp.CMD_MYIPPORT, youripport, address)
        if _Debug:
            lg.out(_DebugLevel, 'stun_server.doSendYourIPPort [%s] to %s' % (
                youripport, address))

    def _datagramReceived(self, datagram, address):
        """
        """
        self.automat('datagram-received', (datagram, address))
        return False

#------------------------------------------------------------------------------

def main():
    from twisted.internet import reactor  # @UnresolvedImport
    lg.set_debug_level(24)
    bpio.init()
    settings.init()
    dht_port = settings.getDHTPort()
    if len(sys.argv) > 1:
        dht_port = int(sys.argv[1])
    udp_port = settings.getUDPPort()
    if len(sys.argv) > 2:
        udp_port = int(sys.argv[2])
    dht_service.init(dht_port)
    d = dht_service.connect()
    udp.listen(udp_port)

    def _go(live_nodes):
        A('start', udp_port)

    d.addCallback(_go)

    reactor.run()  # @UndefinedVariable

#------------------------------------------------------------------------------


if __name__ == '__main__':
    main()
