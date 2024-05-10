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
    * :red:`connect-known-user`
    * :red:`fail`
    * :red:`found-users`
    * :red:`lookup-random-user`
    * :red:`request-timeout`
    * :red:`service-accepted`
    * :red:`service-denied`
    * :red:`shook-hands`
    * :red:`users-not-found`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import strng
from bitdust.lib import packetid

from bitdust.main import settings

from bitdust.p2p import commands
from bitdust.p2p import p2p_service
from bitdust.p2p import handshaker

from bitdust.contacts import identitycache

from bitdust.userid import id_url
from bitdust.userid import global_id
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_P2PServiceSeekerInstaceCounter = 0

#------------------------------------------------------------------------------


class P2PServiceSeeker(automat.Automat):

    """
    This class implements all the functionality of the ``p2p_service_seeker()``
    state machine.
    """

    fast = True

    def __repr__(self):
        return '%s[%s@%s%s%s](%s)' % (self.id, self.target_service or '', self.target_id or '', '#' if self.RandomLookup else '!', self.Attempts, self.state)

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of p2p_service_seeker() machine.
        """
        self.Attempts = 0
        self.RandomLookup = False
        self.lookup_method = None
        self.target_idurl = None
        self.target_id = None
        self.target_service = None
        self.request_service_params = None
        self.request_service_timeout = None
        self.ping_retries = None
        self.ack_timeout = None
        self.force_handshake = None
        self.exclude_nodes = []
        self.verify_accepted = None
        self.lookup_task = None
        self.requested_packet_id = None

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python
        <https://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'connect-known-user':
                self.state = 'HANDSHAKE?'
                self.doInit(*args, **kwargs)
                self.Attempts = 0
                self.RandomLookup = False
                self.doSelectOneUser(*args, **kwargs)
                self.doHandshake(*args, **kwargs)
            elif event == 'lookup-random-user':
                self.state = 'RANDOM_USER?'
                self.doInit(*args, **kwargs)
                self.Attempts = 0
                self.RandomLookup = True
                self.doLookupRandomNode(*args, **kwargs)
        #---RANDOM_USER?---
        elif self.state == 'RANDOM_USER?':
            if event == 'found-users':
                self.state = 'HANDSHAKE?'
                self.doSelectOneUser(*args, **kwargs)
                self.Attempts += 1
                self.doHandshake(*args, **kwargs)
            elif event == 'users-not-found' and not self.isRetries(*args, **kwargs):
                self.state = 'FAILED'
                self.doNotifyLookupFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'users-not-found' and self.isRetries(*args, **kwargs):
                self.Attempts += 1
                self.doLookupRandomNode(*args, **kwargs)
        #---HANDSHAKE?---
        elif self.state == 'HANDSHAKE?':
            if event == 'shook-hands':
                self.state = 'SERVICE?'
                self.doSendRequestService(*args, **kwargs)
            elif event == 'fail' and self.isRetries(*args, **kwargs) and self.RandomLookup:
                self.state = 'RANDOM_USER?'
                self.doLookupRandomNode(*args, **kwargs)
            elif (not self.isRetries(*args, **kwargs) or not self.RandomLookup) and event == 'fail':
                self.state = 'FAILED'
                self.doNotifyHandshakeFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'service-accepted':
                self.state = 'SUCCESS'
                self.doNotifyServiceAccepted(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif (event == 'request-timeout' or event == 'fail' or event == 'service-denied') and (not self.RandomLookup or (not self.isRetries(*args, **kwargs) and self.RandomLookup)):
                self.state = 'FAILED'
                self.doNotifyServiceRequestFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif (event == 'request-timeout' or event == 'fail' or event == 'service-denied') and self.isRetries(*args, **kwargs) and self.RandomLookup:
                self.state = 'RANDOM_USER?'
                self.doLookupRandomNode(*args, **kwargs)
        #---SUCCESS---
        elif self.state == 'SUCCESS':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def isRetries(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.Attempts < self.retries

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.lookup_method = kwargs.get('lookup_method', None)
        self.target_service = kwargs['target_service']
        self.request_service_params = kwargs.get('request_service_params', None)
        self.request_service_timeout = kwargs.get('request_service_timeout', 120)
        self.ping_retries = kwargs.get('ping_retries', None)
        self.ack_timeout = kwargs.get('ack_timeout', None)
        self.force_handshake = kwargs.get('force_handshake', False)
        self.result_callback = kwargs.get('result_callback', None)
        self.verify_accepted = kwargs.get('verify_accepted', True)
        self.exclude_nodes = id_url.to_bin_list(kwargs.get('exclude_nodes', []))
        self.retries = kwargs.get('attempts', 5)

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
        if 'remote_idurl' in kwargs:
            self.target_idurl = kwargs['remote_idurl']
        else:
            self.target_idurl = args[0][0]
        self.target_idurl = id_url.field(self.target_idurl)
        self.target_id = global_id.idurl2glob(self.target_idurl)

    def doHandshake(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, target_idurl=self.target_idurl)
        d = handshaker.ping(
            idurl=self.target_idurl,
            channel='p2p_service_seeker',
            keep_alive=True,
            force_cache=False,
            ping_retries=(1 if self.ping_retries is None else self.ping_retries),
            ack_timeout=(settings.P2PTimeOut() if self.ack_timeout is None else self.ack_timeout),
            cancel_running=self.force_handshake,
        )
        d.addCallback(lambda ok: self.automat('shook-hands'))
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='p2p_service_seeker.doHandshake')
        d.addErrback(lambda err: self.automat('fail', reason='handshake-failed'))

    def doSendRequestService(self, *args, **kwargs):
        """
        Action method.
        """
        self.target_idurl.refresh()
        packet_id = packetid.UniqueID()
        if _Debug:
            lg.args(_DebugLevel, idurl=self.target_idurl, service=self.target_service, packet_id=packet_id)
        service_request_payload = self.request_service_params
        if callable(service_request_payload):
            service_request_payload = service_request_payload(self.target_idurl)
        out_packet = p2p_service.SendRequestService(
            remote_idurl=self.target_idurl,
            service_name=self.target_service,
            json_payload=service_request_payload,
            timeout=self.request_service_timeout,
            callbacks={
                commands.Ack(): self._node_acked,
                commands.Fail(): self._node_failed,
                None: self._node_timed_out,
            },
            packet_id=packet_id,
        )
        self.requested_packet_id = out_packet.PacketID

    def doNotifyServiceAccepted(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker.doNotifyServiceAccepted %r from %r with %s' % (self.target_service, self.target_id, args[0]))
        if self.result_callback:
            self.result_callback('node-connected', *args, **kwargs)
        self.result_callback = None

    def doNotifyLookupFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, event=event, attempts=self.Attempts, args=args, kwargs=kwargs)
        if self.result_callback:
            self.result_callback('lookup-failed', *args, **kwargs)
        self.result_callback = None

    def doNotifyServiceRequestFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, event=event, attempts=self.Attempts, args=args, kwargs=kwargs)
        if self.result_callback:
            self.result_callback('request-failed', *args, **kwargs)
        self.result_callback = None

    def doNotifyHandshakeFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, event=event, attempts=self.Attempts, args=args, kwargs=kwargs)
        if self.result_callback:
            self.result_callback('handshake-failed', *args, **kwargs)
        self.result_callback = None

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.lookup_method = None
        self.target_idurl = None
        self.target_id = None
        self.target_service = None
        self.request_service_params = None
        self.request_service_timeout = None
        self.ping_retries = None
        self.ack_timeout = None
        self.force_handshake = None
        self.exclude_nodes = []
        self.verify_accepted = None
        self.requested_packet_id = None
        self.lookup_task = None
        self.destroy()

    #------------------------------------------------------------------------------

    def _node_acked(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._node_acked %r %r' % (response, info))
        if self.verify_accepted and not strng.to_text(response.Payload).startswith('accepted'):
            if _Debug:
                lg.out(_DebugLevel, 'p2p_service_seeker._node_acked with "service denied" response: %r %r' % (response, info))
            self.automat('service-denied', (response, info), reason='service-denied')
            return
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._node_acked %s is connected' % response.CreatorID)
        self.automat('service-accepted', (response, info))

    def _node_failed(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._node_failed %r %r' % (response, info))
        self.automat('service-denied', (response, info), reason='service-denied')

    def _node_timed_out(self, pkt_out):
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._node_timed_out for outgoing packet %r' % pkt_out)
        self.automat('fail', pkt_out, reason='service-request-timeout')

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


def on_lookup_result(event, result_defer, *args, **kwargs):
    if _Debug:
        lg.args(_DebugLevel, event=event, args=args, kwargs=kwargs)
    if event == 'node-connected':
        result_defer.callback(*args, **kwargs)
    else:
        result_defer.errback(Exception(event, args, kwargs))


#------------------------------------------------------------------------------


def connect_random_node(lookup_method, service_name, service_params=None, verify_accepted=True, exclude_nodes=[], attempts=5, request_service_timeout=None, ping_retries=None, ack_timeout=None, force_handshake=False):
    global _P2PServiceSeekerInstaceCounter
    _P2PServiceSeekerInstaceCounter += 1
    result = Deferred()
    p2p_seeker = P2PServiceSeeker(
        name='p2p_service_seeker%d' % _P2PServiceSeekerInstaceCounter,
        state='AT_STARTUP',
        debug_level=_DebugLevel,
        log_events=_Debug,
        log_transitions=_Debug,
        publish_events=False,
    )
    p2p_seeker.automat(
        'lookup-random-user',
        lookup_method=lookup_method,
        target_service=service_name,
        request_service_params=service_params,
        request_service_timeout=request_service_timeout,
        ping_retries=ping_retries,
        attempts=attempts,
        ack_timeout=ack_timeout,
        force_handshake=force_handshake,
        verify_accepted=verify_accepted,
        result_callback=lambda evt, *a, **kw: on_lookup_result(evt, result, *a, **kw),
        exclude_nodes=exclude_nodes,
    )
    if _Debug:
        lg.args(_DebugLevel, service_name=service_name, exclude_nodes=exclude_nodes, inst=p2p_seeker)
    return result


def connect_known_node(remote_idurl, service_name, service_params=None, verify_accepted=True, exclude_nodes=[], attempts=2, request_service_timeout=None, ping_retries=None, ack_timeout=None, force_handshake=False):
    global _P2PServiceSeekerInstaceCounter
    _P2PServiceSeekerInstaceCounter += 1
    result = Deferred()
    p2p_seeker = P2PServiceSeeker(
        name='p2p_service_seeker%d' % _P2PServiceSeekerInstaceCounter,
        state='AT_STARTUP',
        debug_level=_DebugLevel,
        log_events=_Debug,
        log_transitions=_Debug,
        publish_events=False,
    )
    p2p_seeker.automat(
        'connect-known-user',
        remote_idurl=remote_idurl,
        target_service=service_name,
        request_service_params=service_params,
        request_service_timeout=request_service_timeout,
        ping_retries=ping_retries,
        attempts=attempts,
        ack_timeout=ack_timeout,
        force_handshake=force_handshake,
        verify_accepted=verify_accepted,
        result_callback=lambda evt, *a, **kw: on_lookup_result(evt, result, *a, **kw),
        exclude_nodes=exclude_nodes,
    )
    if _Debug:
        lg.args(_DebugLevel, service_name=service_name, exclude_nodes=exclude_nodes, inst=p2p_seeker)
    return result
