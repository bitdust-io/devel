#!/usr/bin/env python
# p2p_service_seeker.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (p2p_service_seeker.py) is part of BitDust Software.
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
.. module:: p2p_service_seeker

.. role:: red

BitDust p2p_service_seeker() Automat

EVENTS:
    * :red:`fail`
    * :red:`found-users`
    * :red:`service-accepted`
    * :red:`service-denied`
    * :red:`shook-hands`
    * :red:`start`
    * :red:`users-not-found`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import strng

from p2p import commands
from p2p import p2p_service
from p2p import handshaker

from contacts import identitycache

from userid import my_id

#------------------------------------------------------------------------------

class P2PServiceSeeker(automat.Automat):
    """
    This class implements all the functionality of the ``p2p_service_seeker()``
    state machine.
    """

    fast = True

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of p2p_service_seeker() machine.
        """
        self.lookup_method = None
        self.target_idurl = None
        self.target_service = None
        self.request_service_params = None
        self.exclude_nodes = []
        self.lookup_task = None
        self.requested_packet_id = None

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when p2p_service_seeker() state were
        changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in
        the p2p_service_seeker() but its state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python
        <https://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'RANDOM_USER?'
                self.doInit(*args, **kwargs)
                self.Attempts=0
                self.doLookupRandomNode(*args, **kwargs)
        #---RANDOM_USER?---
        elif self.state == 'RANDOM_USER?':
            if event == 'found-users':
                self.state = 'HANDSHAKE?'
                self.doSelectOneUser(*args, **kwargs)
                self.Attempts+=1
                self.doHandshake(*args, **kwargs)
            elif event == 'users-not-found':
                self.state = 'FAILED'
                self.doNotifyLookupFailed(*args, **kwargs)
        #---HANDSHAKE?---
        elif self.state == 'HANDSHAKE?':
            if event == 'shook-hands':
                self.state = 'SERVICE?'
                self.doSendRequestService(*args, **kwargs)
            elif event == 'fail' and self.Attempts<5:
                self.state = 'RANDOM_USER?'
                self.doLookupRandomNode(*args, **kwargs)
            elif self.Attempts==5 and event == 'fail':
                self.state = 'FAILED'
                self.doNotifyHandshakeFailed(*args, **kwargs)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'service-accepted':
                self.state = 'SUCCESS'
                self.doNotifyServiceAccepted(*args, **kwargs)
            elif ( event == 'fail' or event == 'service-denied' ) and self.Attempts<5:
                self.state = 'RANDOM_USER?'
                self.doLookupRandomNode(*args, **kwargs)
            elif self.Attempts==5 and ( event == 'fail' or event == 'service-denied' ):
                self.state = 'FAILED'
                self.doNotifyServiceRequestFailed(*args, **kwargs)
        #---SUCCESS---
        elif self.state == 'SUCCESS':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.lookup_method = kwargs['lookup_method']
        self.target_service = kwargs['target_service']
        self.request_service_params = kwargs.get('request_service_params', None)
        self.result_callback = kwargs.get('result_callback', None)
        self.exclude_nodes = kwargs.get('exclude_nodes', [])

    def doLookupRandomNode(self, *args, **kwargs):
        """
        Action method.
        """
        self.lookup_task = self.lookup_method()
        if self.lookup_task.result_defer:
            self.lookup_task.result_defer.addCallback(self._nodes_lookup_finished)
            self.lookup_task.result_defer.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='p2p_service_seeker.doLookupRandomNode')
            self.lookup_task.result_defer.addErrback(lambda err: self.automat('users-not-found'))
        else:
            self.automat('users-not-found')

    def doSelectOneUser(self, *args, **kwargs):
        """
        Action method.
        """
        self.target_idurl = args[0][0]

    def doHandshake(self, *args, **kwargs):
        """
        Action method.
        """
        d = handshaker.ping(
            idurl=self.target_idurl,
            channel='p2p_service_seeker',
            keep_alive=True,
            force_cache=False,
        )
        d.addCallback(lambda ok: self.automat('shook-hands'))
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='p2p_service_seeker.doHandshake')
        d.addErrback(lambda err: self.automat('fail'))

    def doSendRequestService(self, *args, **kwargs):
        """
        Action method.
        """
        service_request_payload = self.request_service_params
        if callable(service_request_payload):
            service_request_payload = service_request_payload(self.target_idurl)
        out_packet = p2p_service.SendRequestService(
            remote_idurl=self.target_idurl,
            service_name=self.target_service,
            json_payload=service_request_payload,
            callbacks={
                commands.Ack(): self._node_acked,
                commands.Fail(): self._node_failed,
                None: lambda pkt_out: self.automat('fail'),
            }
        )
        self.requested_packet_id = out_packet.PacketID

    def doNotifyServiceAccepted(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker.doNotifyServiceAccepted %r from %r with %s' % (
                self.target_service, self.target_idurl, args[0]))
        if self.result_callback:
            self.result_callback('node-connected', *args, **kwargs)
        self.result_callback = None

    def doNotifyLookupFailed(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker.doNotifyLookupFailed, Attempts=%d' % self.Attempts)
        if self.result_callback:
            self.result_callback('lookup-failed', *args, **kwargs)
        self.result_callback = None

    def doNotifyServiceRequestFailed(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker.doNotifyServiceRequestFailed, Attempts=%d' % self.Attempts)
        if self.result_callback:
            self.result_callback('request-failed', *args, **kwargs)
        self.result_callback = None

    def doNotifyHandshakeFailed(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker.doNotifyHandshakeFailed, Attempts=%d' % self.Attempts)
        if self.result_callback:
            self.result_callback('handshake-failed', *args, **kwargs)
        self.result_callback = None

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.lookup_method = None
        self.target_idurl = None
        self.target_service = None
        self.request_service_params = None
        self.exclude_nodes = []
        self.requested_packet_id = None
        self.lookup_task = None
        self.destroy()

    #------------------------------------------------------------------------------

    def _node_acked(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._node_acked %r %r' % (response, info))
        if not strng.to_text(response.Payload).startswith('accepted'):
            if _Debug:
                lg.out(_DebugLevel, 'p2p_service_seeker._node_acked with service denied %r %r' % (response, info))
            self.automat('service-denied')
            return
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._node_acked %s is connected' % response.CreatorID)
        self.automat('service-accepted', response.CreatorID)

    def _node_failed(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._node_failed %r %r' % (response, info))
        self.automat('service-denied')

    def _nodes_lookup_finished(self, idurls):
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._nodes_lookup_finished : %r' % idurls)
        found_idurls = []
        for idurl in idurls:
            if idurl in self.exclude_nodes:
                continue
            if idurl in found_idurls:
                continue
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if len(myprotos.intersection(remoteprotos)) > 0:
                found_idurls.append(idurl)
        if found_idurls:
            self.automat('found-users', found_idurls)
        else:
            self.automat('users-not-found')

#------------------------------------------------------------------------------


def on_lookup_result(event, arg, result_defer):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service_seeker.on_lookup_result %r with %r' % (event, arg, ))
    if event == 'node-connected':
        result_defer.callback(arg)
    else:
        result_defer.callback(None)

def connect_random_node(lookup_method, service_name, service_params=None, exclude_nodes=[]):
    """
    """
    result = Deferred()
    p2p_seeker = P2PServiceSeeker('p2p_service_seeker', 'AT_STARTUP', _DebugLevel, _Debug)
    p2p_seeker.automat(
        'start',
        lookup_method=lookup_method,
        target_service=service_name,
        request_service_params=service_params,
        result_callback=lambda evt, arg: on_lookup_result(evt, arg, result),
        exclude_nodes=exclude_nodes,
    )
    return result
