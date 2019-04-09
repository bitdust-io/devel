#!/usr/bin/env python
# accountants_finder.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (accountants_finder.py) is part of BitDust Software.
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
.. module:: accountants_finder.

.. role:: red

BitDust accountants_finder() Automat

EVENTS:
    * :red:`ack-received`
    * :red:`found-one-user`
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

_AccountantsFinder = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _AccountantsFinder
    if event is None and not args:
        return _AccountantsFinder
    if _AccountantsFinder is None:
        # set automat name and starting state here
        _AccountantsFinder = AccountantsFinder('accountants_finder', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _AccountantsFinder.automat(event, *args, **kwargs)
    return _AccountantsFinder

#------------------------------------------------------------------------------


class AccountantsFinder(automat.Automat):
    """
    This class implements all the functionality of the ``accountants_finder()``
    state machine.
    """

    timers = {
        'timer-3sec': (3.0, ['ACK?']),
        'timer-10sec': (10.0, ['ACK?', 'SERVICE?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of accountants_finder() machine.
        """
        self.target_idurl = None
        self.requested_packet_id = None
        self.request_service_params = None

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when accountants_finder() state were
        changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in
        the accountants_finder() but its state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python
        <https://bitdust.io/visio2python/>`_ tool.
        """
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READY'
                self.doInit(*args, **kwargs)
        elif self.state == 'RANDOM_USER':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'found-one-user':
                self.state = 'ACK?'
                self.doRememberUser(*args, **kwargs)
                self.Attempts += 1
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'users-not-found':
                self.state = 'READY'
                self.doNotifyLookupFailed(*args, **kwargs)
        elif self.state == 'ACK?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-received':
                self.state = 'SERVICE?'
                self.doSendRequestService(*args, **kwargs)
            elif event == 'timer-10sec' and self.Attempts < 5:
                self.state = 'RANDOM_USER'
                self.doLookupRandomUser(*args, **kwargs)
            elif event == 'timer-3sec':
                self.doSendMyIdentity(*args, **kwargs)
        elif self.state == 'SERVICE?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'service-accepted':
                self.state = 'READY'
                self.doNotifyLookupSuccess(*args, **kwargs)
            elif self.Attempts == 5 and (event == 'timer-10sec' or event == 'service-denied'):
                self.state = 'READY'
                self.doNotifyLookupFailed(*args, **kwargs)
            elif (event == 'timer-10sec' or event == 'service-denied') and self.Attempts < 5:
                self.state = 'RANDOM_USER'
                self.doLookupRandomUser(*args, **kwargs)
        elif self.state == 'READY':
            if event == 'start':
                self.state = 'RANDOM_USER'
                self.doSetNotifyCallback(*args, **kwargs)
                self.Attempts = 0
                self.doLookupRandomUser(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        callback.append_inbox_callback(self._inbox_packet_received)

    def doSetNotifyCallback(self, *args, **kwargs):
        """
        Action method.
        """
        self.result_callback, self.request_service_params = args[0]

    def doLookupRandomUser(self, *args, **kwargs):
        """
        Action method.
        """
        t = lookup.start()
        t.result_defer.addCallback(self._nodes_lookup_finished)
        t.result_defer.addErrback(lambda err: self.automat('users-not-found'))

    def doRememberUser(self, *args, **kwargs):
        """
        Action method.
        """
        self.target_idurl = args[0]

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        p2p_service.SendIdentity(self.target_idurl, wide=True)

    def doSendRequestService(self, *args, **kwargs):
        """
        Action method.
        """
        out_packet = p2p_service.SendRequestService(
            self.target_idurl, 'service_accountant', json_payload=self.request_service_params, callbacks={
                commands.Ack(): self._node_acked,
                commands.Fail(): self._node_failed,
            }
        )
        self.requested_packet_id = out_packet.PacketID

    def doNotifyLookupSuccess(self, *args, **kwargs):
        """
        Action method.
        """
        if self.result_callback:
            self.result_callback('accountant-connected', *args, **kwargs)
        self.result_callback = None
        self.request_service_params = None

    def doNotifyLookupFailed(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'accountants_finder.doNotifyLookupFailed, Attempts=%d' % self.Attempts)
        if self.result_callback:
            self.result_callback('lookup-failed', *args, **kwargs)
        self.result_callback = None
        self.request_service_params = None

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        callback.remove_inbox_callback(self._inbox_packet_received)
        self.unregister()
        global _AccountantsFinder
        del _AccountantsFinder
        _AccountantsFinder = None

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
            lg.out(_DebugLevel, 'accountants_finder._node_acked %r %r' % (response, info))
        if not strng.to_text(response.Payload).startswith('accepted'):
            if _Debug:
                lg.out(_DebugLevel, 'accountants_finder._node_acked with service denied %r %r' % (response, info))
            self.automat('service-denied')
            return
        if _Debug:
            lg.out(_DebugLevel, 'accountants_finder._node_acked !!!! accountant %s connected' % response.CreatorID)
        self.automat('service-accepted', response.CreatorID)

    def _node_failed(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'accountants_finder._node_failed %r %r' % (response, info))
        self.automat('service-denied')

    def _nodes_lookup_finished(self, idurls):
        # TODO: this is still under construction - so I am using this node for tests
        # idurls = ['http://veselin-p2p.ru/bitdust_vps1000_k.xml', ]
        if _Debug:
            lg.out(_DebugLevel, 'accountants_finder._nodes_lookup_finished : %r' % idurls)
        for idurl in idurls:
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if len(myprotos.intersection(remoteprotos)) > 0:
                self.automat('found-one-user', idurl)
                return
        self.automat('users-not-found')
