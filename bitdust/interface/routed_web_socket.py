#!/usr/bin/env python
# api_routed_device.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (api_routed_device.py) is part of BitDust Software.
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
.. module:: api_routed_device
.. role:: red

BitDust api_routed_device() Automat

EVENTS:
    * :red:`api-message`
    * :red:`auth-error`
    * :red:`client-code-input-received`
    * :red:`client-pub-key-received`
    * :red:`lookup-failed`
    * :red:`router-disconnected`
    * :red:`routers-connected`
    * :red:`routers-failed`
    * :red:`routers-selected`
    * :red:`start`
    * :red:`stop`
    * :red:`valid-server-code-received`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

#------------------------------------------------------------------------------

from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.p2p import p2p_service

from bitdust.services import driver

#------------------------------------------------------------------------------


class RoutedWebSocket(automat.Automat):

    """
    This class implements all the functionality of ``api_routed_device()`` state machine.
    """

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `api_routed_device()` state machine.
        """
        super(RoutedWebSocket, self).__init__(name='api_routed_device', state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `api_routed_device()` machine.
        """
        # TODO: read known routers from local file
        self.connected_routers = []

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `api_routed_device()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `api_routed_device()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://github.com/vesellov/visio2python>`_ tool.
        """
        #---READY---
        if self.state == 'READY':
            if event == 'api-message':
                self.doProcess(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'router-disconnected':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
        #---WEB_SOCKET?---
        elif self.state == 'WEB_SOCKET?':
            if event == 'routers-connected' and not self.isAuthenticated(*args, **kwargs):
                self.state = 'CLIENT_PUB?'
                self.doSaveRouters(*args, **kwargs)
                self.doPrepareWebSocketURL(*args, **kwargs)
            elif event == 'routers-connected' and self.isAuthenticated(*args, **kwargs):
                self.state = 'READY'
                self.doInit(*args, **kwargs)
                self.doLoadAuthInfo(*args, **kwargs)
            elif event == 'routers-failed':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---ROUTERS?---
        elif self.state == 'ROUTERS?':
            if event == 'routers-selected':
                self.state = 'WEB_SOCKET?'
                self.doConnectRouters(*args, **kwargs)
            elif event == 'stop' or event == 'lookup-failed':
                self.state = 'CLOSED'
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---CLIENT_CODE?---
        elif self.state == 'CLIENT_CODE?':
            if event == 'client-code-input-received':
                self.state = 'READY'
                self.doSaveAuthInfo(*args, **kwargs)
                self.doSendClientCode(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'router-disconnected':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'start' and not self.isKnownRouters(*args, **kwargs):
                self.state = 'ROUTERS?'
                self.doInit(*args, **kwargs)
                self.doLookupRequestRouters(*args, **kwargs)
            elif event == 'start' and self.isKnownRouters(*args, **kwargs):
                self.state = 'WEB_SOCKET?'
                self.doInit(*args, **kwargs)
                self.doConnectRouters(*args, **kwargs)
        #---CLIENT_PUB?---
        elif self.state == 'CLIENT_PUB?':
            if event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'router-disconnected':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
        #---SERVER_CODE?---
        elif self.state == 'SERVER_CODE?':
            if event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'valid-server-code-received':
                self.state = 'CLIENT_CODE?'
                self.doWaitClientCodeInput(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'router-disconnected':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isAuthenticated(self, *args, **kwargs):
        """
        Condition method.
        """

    def isKnownRouters(self, *args, **kwargs):
        """
        Condition method.
        """

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doLookupRequestRouters(self, *args, **kwargs):
        """
        Action method.
        """

    def doConnectRouters(self, *args, **kwargs):
        """
        Action method.
        """
        self.router_lookups = 0
        self._lookup_next_router()

    def doDisconnectRouters(self, event, *args, **kwargs):
        """
        Action method.
        """
        for idurl in self.connected_routers:
            p2p_service.SendCancelService(idurl, 'service_web_socket_router')
        # TODO: notify about failed result
        self.connected_routers = []

    def doSaveRouters(self, *args, **kwargs):
        """
        Action method.
        """

    def doPrepareWebSocketURL(self, *args, **kwargs):
        """
        Action method.
        """

    def doLoadAuthInfo(self, *args, **kwargs):
        """
        Action method.
        """

    def doSaveAuthInfo(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendServerPubKey(self, *args, **kwargs):
        """
        Action method.
        """

    def doGenerateAuthToken(self, *args, **kwargs):
        """
        Action method.
        """

    def doRemoveAuthToken(self, event, *args, **kwargs):
        """
        Action method.
        """

    def doGenerateServerCode(self, *args, **kwargs):
        """
        Action method.
        """

    def doWaitClientCodeInput(self, *args, **kwargs):
        """
        Action method.
        """

    def doSaveClientPublicKey(self, *args, **kwargs):
        """
        Action method.
        """

    def doProcess(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendClientCode(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

    #------------------------------------------------------------------------------

    def _on_router_lookup_finished(self, idurl):
        if self.state != 'ROUTERS?':
            lg.warn('internal state was changed during router lookup, SKIP next lookup')
            return None
        if not idurl or isinstance(idurl, Exception) or isinstance(idurl, Failure):
            if _Debug:
                lg.dbg(_DebugLevel, 'no results, try again')
            reactor.callLater(0, self._lookup_next_router)  # @UndefinedVariable
            return None
        if idurl in self.connected_routers:
            lg.warn('node %s already connected as web socket router')
        else:
            self.connected_routers.append(idurl)
            lg.info('node %s connected as new web socket router' % idurl)
        reactor.callLater(0, self._lookup_next_router)  # @UndefinedVariable
        return None

    def _lookup_next_router(self):
        if len(self.connected_routers) >= 3:  # TODO: read from settings.: max web socket routers
            if _Debug:
                lg.dbg(_DebugLevel, 'currently %d web socket routers are connected' % len(self.connected_routers))
            self.automat('routers-selected')
            return
        if self.router_lookups >= 10:  # TODO: read from settings.
            if len(self.connected_routers) >= 3:  # TODO: read from settings: min web socket routers
                if _Debug:
                    lg.dbg(_DebugLevel, 'failed after %d retries, but %d web socket routers are currently connected' % (self.router_lookups, len(self.connected_routers)))
                self.automat('routers-selected')
                return
            if _Debug:
                lg.dbg(_DebugLevel, 'failed after %d retries with no results' % self.router_lookups)
            self.automat('lookup-failed')
            return
        if not driver.is_on('service_nodes_lookup'):
            self.automat('lookup-failed')
            return
        self.router_lookups += 1
        from bitdust.p2p import p2p_service_seeker
        from bitdust.p2p import lookup
        p2p_service_seeker.connect_random_node(
            'service_web_socket_router',
            lookup_method=lookup.random_web_socket_router,
            service_params={
                'action': 'connect',
            },
            exclude_nodes=self.connected_routers,
        ).addBoth(self._on_router_lookup_finished)
