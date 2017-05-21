#!/usr/bin/env python
# p2p_service_seeker.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

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

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when p2p_service_seeker() state were
        changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in
        the p2p_service_seeker() but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python
        <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READY'
                self.doInit(arg)
        #---RANDOM_USER---
        elif self.state == 'RANDOM_USER':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopLookup(arg)
                self.doDestroyMe(arg)
            elif event == 'users-not-found':
                self.state = 'READY'
                self.doNotifyLookupFailed(arg)
            elif event == 'found-users':
                self.state = 'ACK?'
                self.doSelectOneUser(arg)
                self.Attempts+=1
                self.doSendMyIdentity(arg)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'ack-received':
                self.state = 'SERVICE?'
                self.doSendRequestService(arg)
            elif event == 'timer-3sec':
                self.doSendMyIdentity(arg)
            elif event == 'timer-10sec' and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doLookupRandomNode(arg)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'service-accepted':
                self.state = 'READY'
                self.doNotifyLookupSuccess(arg)
            elif ( event == 'timer-10sec' or event == 'service-denied' ) and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doLookupRandomNode(arg)
            elif self.Attempts==5 and ( event == 'timer-10sec' or event == 'service-denied' ):
                self.state = 'READY'
                self.doNotifyLookupFailed(arg)
        #---READY---
        elif self.state == 'READY':
            if event == 'start':
                self.state = 'RANDOM_USER'
                self.doSetRequest(arg)
                self.doSetCallback(arg)
                self.Attempts=0
                self.doLookupRandomNode(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, arg):
        """
        Action method.
        """
        self.exclude_nodes = arg[0]
        callback.insert_inbox_callback(0, self._inbox_packet_received)

    def doSetRequest(self, arg):
        """
        Action method.
        """
        self.target_service, self.request_service_params = arg[:2]

    def doSetCallback(self, arg):
        """
        Action method.
        """
        self.result_callback = arg[-1]

    def doLookupRandomNode(self, arg):
        """
        Action method.
        """
        self.lookup_task = lookup.start()
        self.lookup_task.result_defer.addCallback(self._nodes_lookup_finished)
        self.lookup_task.result_defer.addErrback(lambda err: self.automat('users-not-found'))

    def doStopLookup(self, arg):
        """
        Action method.
        """
        self.lookup_task.stop()

    def doSelectOneUser(self, arg):
        """
        Action method.
        """
        self.target_idurl = arg[0]

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        p2p_service.SendIdentity(self.target_idurl, wide=True)

    def doSendRequestService(self, arg):
        """
        Action method.
        """
        service_info = self.target_service
        if self.request_service_params is not None:
            service_info += ' {}'.format(self.request_service_params)
        out_packet = p2p_service.SendRequestService(
            self.target_idurl, service_info, callbacks={
                commands.Ack(): self._node_acked,
                commands.Fail(): self._node_failed,
            }
        )
        self.requested_packet_id = out_packet.PacketID

    def doNotifyLookupSuccess(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker.doNotifyLookupSuccess with %s' % arg)
        if self.result_callback:
            self.result_callback('node-connected', arg)
        self.result_callback = None

    def doNotifyLookupFailed(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service_seeker.doNotifyLookupFailed, Attempts=%d' % self.Attempts)
        if self.result_callback:
            self.result_callback('lookup-failed', arg)
        self.result_callback = None

    def doDestroyMe(self, arg):
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
        automat.objects().pop(self.index)
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
        if not response.Payload.startswith('accepted'):
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
        found_idurls = set()
        for idurl in idurls:
            if idurl in self.exclude_nodes:
                continue
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if len(myprotos.intersection(remoteprotos)) > 0:
                found_idurls.add(idurl)
        if found_idurls:
            self.automat('found-users', found_idurls)
        else:
            self.automat('users-not-found')

#------------------------------------------------------------------------------

def connect_random_node(service_name, service_params=None, exclude_nodes=[]):
    """
    """
    result = Deferred()
    p2p_service_seeker = P2PServiceSeeker('p2p_service_seeker', 'AT_STARTUP', _DebugLevel, _Debug)
    p2p_service_seeker.automat('init', (exclude_nodes, ))

    def _on_lookup_result(event, arg):
        p2p_service_seeker.automat('shutdown')
        if event == 'node-connected':
            result.callback(arg)
        else:
            result.errback(arg)

    p2p_service_seeker.automat('start', (service_name, service_params, _on_lookup_result, ))
    return result
