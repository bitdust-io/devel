#!/usr/bin/env python
# proxy_node.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (proxy_node.py) is part of BitDust Software.
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
.. module:: proxy_node.

.. role:: red

BitDust proxy_node(AT_STARTUP) Automat

.. raw:: html

    <i>generated using <a href="http://bitdust.io/visio2python/" target="_blank">visio2python</a> tool</i><br>
    <a href="proxy_node.png" target="_blank">
    <img src="proxy_node.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`init`
    * :red:`other-transports-ready`
    * :red:`proxy_connector.state`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-60sec`
"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 14

#------------------------------------------------------------------------------

from automats import automat

from main import config

import proxy_connector
from transport.proxy import proxy_receiver
import proxy_sender

#------------------------------------------------------------------------------

_ProxyNode = None

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with proxy_node machine.
    """
    global _ProxyNode
    if _ProxyNode is None:
        # set automat name and starting state here
        _ProxyNode = ProxyNode('proxy_node', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _ProxyNode.automat(event, arg)
    return _ProxyNode

#------------------------------------------------------------------------------


class ProxyNode(automat.Automat):
    """
    This class implements all the functionality of the ``proxy_node()`` state
    machine.
    """

    timers = {
        'timer-60sec': (60.0, ['TRANSPORTS?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of proxy_node() machine.
        """
        self.router_idurl = None
        self.router_identity = None
        self.router_proto_host = None
        self.request_service_packet_id = []

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when proxy_node() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in
        the proxy_node() but its state was not changed.
        """

    def A(self, event, arg):
        """
        The core proxy_node() code, generated using `visio2python
        <http://bitdust.io/visio2python/>`_ tool.
        """
        #---TRANSPORTS?---
        if self.state == 'TRANSPORTS?':
            if event == 'other-transports-ready':
                self.state = 'ROUTER?'
                proxy_connector.A('start')
            elif event == 'timer-60sec':
                self.state = 'STOPPED'
                proxy_connector.A('shutdown')
                self.doReportStopped(arg)
        #---LISTENING---
        elif self.state == 'LISTENING':
            if event == 'stop':
                self.state = 'STOPPED'
                proxy_sender.A('stop')
                proxy_receiver.A('stop')
            elif event == 'shutdown':
                self.state = 'CLOSED'
                proxy_sender.A('shutdown')
                proxy_receiver.A('shutdown')
                self.doDestroyMe(arg)
        #---ROUTER?---
        elif self.state == 'ROUTER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                proxy_connector.A('shutdown')
                proxy_sender.A('shutdown')
                proxy_receiver.A('shutdown')
                self.doDestroyMe(arg)
            elif (event == 'proxy_connector.state' and arg == 'CONNECTED!'):
                self.state = 'LISTENING'
                proxy_sender.A('start')
                proxy_receiver.A('start')
            elif (event == 'proxy_connector.state' and arg == 'CLOSED'):
                self.state = 'STOPPED'
                self.doReportStopped(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(arg)
                proxy_sender.A('init')
                proxy_receiver.A('init')
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'start':
                self.state = 'TRANSPORTS?'
                self.doWaitOtherTransports(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                proxy_sender.A('shutdown')
                proxy_receiver.A('shutdown')
                self.doDestroyMe(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, arg):
        """
        Action method.
        """

    def doReportStopped(self, arg):
        """
        Action method.
        """

    def doWaitOtherTransports(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()
        global _ProxyNode
        del _ProxyNode
        _ProxyNode = None

#------------------------------------------------------------------------------


def GetRouterIDURL():
    global _ProxyReceiver
    if not _ProxyReceiver:
        return None
    return _ProxyReceiver.router_idurl


def GetRouterIdentity():
    global _ProxyReceiver
    if not _ProxyReceiver:
        return None
    return _ProxyReceiver.router_identity


def GetRouterProtoHost():
    global _ProxyReceiver
    if not _ProxyReceiver:
        return None
    return _ProxyReceiver.router_proto_host


def GetMyOriginalIdentitySource():
    return config.conf().getData('services/proxy-transport/my-original-identity')

#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

if __name__ == "__main__":
    main()
