#!/usr/bin/env python
# p2p_service_seeker.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
    * :red:`ack-received`
    * :red:`found-users`
    * :red:`init`
    * :red:`service-accepted`
    * :red:`service-denied`
    * :red:`shutdown`
    * :red:`start`
    * :red:`timer-10sec`
    * :red:`timer-3sec`
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
from p2p import lookup

from contacts import identitycache

from userid import my_id

from transport import callback

#------------------------------------------------------------------------------

class P2PServiceSeeker(automat.Automat):
    """
    This class implements all the functionality of the ``p2p_service_seeker()``
    state machine.
    """

    fast = True

    timers = {
        'timer-3sec': (3.0, ['ACK?']),
        'timer-10sec': (10.0, ['ACK?', 'SERVICE?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of p2p_service_seeker() machine.
        """
        self.target_idurl = None
        self.target_service = None
        self.requested_packet_id = None
        self.request_service_params = None
        self.lookup_task = None
        self.exclude_nodes = []

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
            if event == 'init':
                self.state = 'READY'
                self.doInit(*args, **kwargs)
        #---RANDOM_USER---
        elif self.state == 'RANDOM_USER':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopLookup(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'users-not-found':
                self.state = 'READY'
                self.doNotifyLookupFailed(*args, **kwargs)
            elif event == 'found-users':
                self.state = 'ACK?'
                self.doSelectOneUser(*args, **kwargs)
                self.Attempts+=1
                self.doSendMyIdentity(*args, **kwargs)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-received':
                self.state = 'SERVICE?'
                self.doSendRequestService(*args, **kwargs)
            elif event == 'timer-3sec':
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'timer-10sec' and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doLookupRandomNode(*args, **kwargs)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'service-accepted':
                self.state = 'READY'
                self.doNotifyLookupSuccess(*args, **kwargs)
            elif ( event == 'timer-10sec' or event == 'service-denied' ) and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doLookupRandomNode(*args, **kwargs)
            elif self.Attempts==5 and ( event == 'timer-10sec' or event == 'service-denied' ):
                self.state = 'READY'
                self.doNotifyLookupFailed(*args, **kwargs)
        #---READY---
        elif self.state == 'READY':
            if event == 'start':
                self.state = 'RANDOM_USER'
                self.doSetRequest(*args, **kwargs)
                self.doSetCallback(*args, **kwargs)
                self.Attempts=0
                self.doLookupRandomNode(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.exclude_nodes = args[0][0]
        callback.append_inbox_callback(self._inbox_packet_received)

    def doSetRequest(self, *args, **kwargs):
        """
        Action method.
        """
        self.target_service, self.request_service_params = args[0][:2]

    def doSetCallback(self, *args, **kwargs):
        """
        Action method.
        """
        self.result_callback = args[0][-1]

    def doLookupRandomNode(self, *args, **kwargs):
        """
        Action method.
        """
        self.lookup_task = lookup.start()
        if self.lookup_task.result_defer:
            self.lookup_task.result_defer.addCallback(self._nodes_lookup_finished)
            self.lookup_task.result_defer.addErrback(lambda err: self.automat('users-not-found'))
        else:
            self.automat('users-not-found')

    def doStopLookup(self, *args, **kwargs):
        """
        Action method.
        """
        self.lookup_task.stop()

    def doSelectOneUser(self, *args, **kwargs):
        """
        Action method.
        """
        self.target_idurl = args[0][0]

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        p2p_service.SendIdentity(self.target_idurl, wide=True)

    def doSendRequestService(self, *args, **kwargs):
        """
        Action method.
        """
        # service_info = self.target_service
        # if self.request_service_params is not None:
        #     service_info += ' {}'.format(self.request_service_params)
        out_packet = p2p_service.SendRequestService(
            self.target_idurl, self.target_service, json_payload=self.request_service_params, callbacks={
                commands.Ack(): self._node_acked,
                commands.Fail(): self._node_failed,
            }
        )
        self.requested_packet_id = out_packet.PacketID

    def doNotifyLookupSuccess(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker.doNotifyLookupSuccess with %s' % args[0])
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

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.target_idurl = None
        self.target_service = None
        self.requested_packet_id = None
        self.request_service_params = None
        self.lookup_task = None
        self.exclude_nodes = []
        callback.remove_inbox_callback(self._inbox_packet_received)
        self.unregister()
        # global _P2PServiceSeeker
        # del _P2PServiceSeeker
        # _P2PServiceSeeker = None

    #------------------------------------------------------------------------------

    def _inbox_packet_received(self, newpacket, info, status, error_message):
        if newpacket.Command == commands.Ack() and \
                newpacket.OwnerID == self.target_idurl and \
                newpacket.PacketID == 'identity' and \
                self.state == 'ACK?':
            self.automat('ack-received', self.target_idurl)
            return True
        return False

    def _node_acked(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._node_acked %r %r' % (response, info))
        if not strng.to_text(response.Payload).startswith('accepted'):
            if _Debug:
                lg.out(_DebugLevel, 'p2p_service_seeker._node_acked with service denied %r %r' % (response, info))
            self.automat('service-denied')
            return
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker._node_acked !!!! node %s connected' % response.CreatorID)
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

def on_lookup_result(event, arg, result_defer, p2p_seeker_instance):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service_seeker.on_lookup_result %s with %s' % (event, arg))
    p2p_seeker_instance.automat('shutdown')
    if event == 'node-connected':
        result_defer.callback(arg)
    else:
        result_defer.callback(None)

def connect_random_node(service_name, service_params=None, exclude_nodes=[]):
    """
    """
    result = Deferred()
    p2p_seeker = P2PServiceSeeker('p2p_service_seeker', 'AT_STARTUP', _DebugLevel, _Debug)
    p2p_seeker.automat('init', (exclude_nodes, ))
    p2p_seeker.automat(
        'start', (
            service_name, service_params, lambda evt, arg: on_lookup_result(evt, arg, result, p2p_seeker)
        )
    )
    return result
