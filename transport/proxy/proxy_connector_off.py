#!/usr/bin/env python
# proxy_connector.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (proxy_connector.py) is part of BitDust Software.
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
.. module:: proxy_connector.

.. role:: red

BitDust proxy_connector(AT_STARTUP) Automat

.. raw:: html

    <i>generated using <a href="http://bitdust.io/visio2python/" target="_blank">visio2python</a> tool</i><br>
    <a href="proxy_connector.png" target="_blank">
    <img src="proxy_connector.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`ack-received`
    * :red:`fail-received`
    * :red:`found-one-node`
    * :red:`my-identity-ready`
    * :red:`service-accepted`
    * :red:`service-refused`
    * :red:`shutdown`
    * :red:`start`
    * :red:`timer-10sec`
    * :red:`timer-20sec`
    * :red:`timer-5sec`
"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 14

#------------------------------------------------------------------------------

from automats import automat

#------------------------------------------------------------------------------

_ProxyConnector = None

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with proxy_connector machine.
    """
    global _ProxyConnector
    if _ProxyConnector is None:
        # set automat name and starting state here
        _ProxyConnector = ProxyConnector('proxy_connector', 'AT_STARTUP')
    if event is not None:
        _ProxyConnector.automat(event, arg)
    return _ProxyConnector

#------------------------------------------------------------------------------


def Destroy():
    """
    Destroy proxy_connector() automat and remove its instance from memory.
    """
    global _ProxyConnector
    if _ProxyConnector is None:
        return
    _ProxyConnector.destroy()
    del _ProxyConnector
    _ProxyConnector = None

#------------------------------------------------------------------------------


class ProxyConnector(automat.Automat):
    """
    This class implements all the functionality of the ``proxy_connector()``
    state machine.
    """

    timers = {
        'timer-20sec': (20.0, ['ACK?']),
        'timer-5sec': (5.0, ['ACK?']),
        'timer-10sec': (10.0, ['SERVICE?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of proxy_connector() machine.
        """

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when proxy_connector() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in
        the proxy_connector() but its state was not changed.
        """

    def A(self, event, arg):
        """
        The core proxy_connector() code, generated using `visio2python
        <http://bitdust.io/visio2python/>`_ tool.
        """
        #---MY_IDENTITY---
        if self.state == 'MY_IDENTITY':
            if event == 'my-identity-ready' and self.isCurrentRouterExist(arg):
                self.state = 'ACK?'
                self.doLoadRouterInfo(arg)
                self.doSendMyIdentity(arg)
            elif event == 'my-identity-ready' and not self.isCurrentRouterExist(arg):
                self.state = 'RANDOM_NODE'
                self.doDHTFindRandomNode(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'MY_IDENTITY'
                self.doInit(arg)
                self.doRebuildMyIdentity(arg)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'ack-received':
                self.state = 'SERVICE?'
                self.doSendRequestService(arg)
            elif event == 'timer-5sec':
                self.doSendMyIdentity(arg)
            elif event == 'timer-20sec' or event == 'fail-received':
                self.state = 'RANDOM_NODE'
                self.doDHTFindRandomNode(arg)
        #---RANDOM_NODE---
        elif self.state == 'RANDOM_NODE':
            if event == 'found-one-node':
                self.state = 'ACK?'
                self.doRememberNode(arg)
                self.doSendMyIdentity(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'service-accepted':
                self.state = 'PROPAGATE'
                self.doSaveRouterInfo(arg)
                self.doRebuildMyIdentity(arg)
                self.doPropagateToRouter(arg)
            elif event == 'timer-10sec' or event == 'service-refused':
                self.state = 'RANDOM_NODE'
                self.doDHTFindRandomNode(arg)
            elif event == 'ack-received':
                self.doSendRequestService(arg)
        #---PROPAGATE---
        elif self.state == 'PROPAGATE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass

    def isCurrentRouterExist(self, arg):
        """
        Condition method.
        """

    def doInit(self, arg):
        """
        Action method.
        """

    def doRebuildMyIdentity(self, arg):
        """
        Action method.
        """

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        p2p_service.SendIdentity(
            self.router_idurl,
            wide=True,
            callbacks={
                commands.Ack(): lambda response, info: self.automat('ack-received', (response, info)),
                commands.Fail(): lambda x: self.automat('nodes-not-found')})

    def doPropagateToRouter(self, arg):
        """
        Action method.
        """

    def doSaveRouterInfo(self, arg):
        """
        Action method.
        """

    def doRememberNode(self, arg):
        """
        Action method.
        """

    def doLoadRouterInfo(self, arg):
        """
        Action method.
        """

    def doSendRequestService(self, arg):
        """
        Action method.
        """
        if len(self.request_service_packet_id) >= 3:
            if _Debug:
                lg.warn('too many service requests to %s' % self.router_idurl)
            self.automat('service-refused', arg)
            return
        from transport import gateway
        service_info = 'service_proxy_server \n'
        orig_identity = config.conf().getData('services/proxy-transport/my-original-identity').strip()
        if not orig_identity:
            orig_identity = my_id.getLocalIdentity().serialize()
        service_info += orig_identity
        request = p2p_service.SendRequestService(
            self.router_idurl, service_info,
            callbacks={
                commands.Ack(): self._request_service_ack,
                commands.Fail(): self._request_service_fail})
        self.request_service_packet_id.append(request.PacketID)

    def doDHTFindRandomNode(self, arg):
        """
        Action method.
        """
        self._find_random_node()

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()
        global _ProxyConnector
        del _ProxyConnector
        _ProxyConnector = None

#------------------------------------------------------------------------------
