#!/usr/bin/env python
# udp_connector.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (udp_connector.py) is part of BitDust Software.
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
.. module:: udp_connector.

.. role:: red
BitDust udp_connector() Automat


EVENTS:
    * :red:`abort`
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`start`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

import time

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from dht import dht_service

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 12

#------------------------------------------------------------------------------

_ConnectorsDict = {}

#------------------------------------------------------------------------------


def connectors():
    """
    
    """
    global _ConnectorsDict
    return _ConnectorsDict


def create(node, peer_id):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'udp_connector.create peer_id=%s' % peer_id)
    c = DHTUDPConnector(node, peer_id)
    connectors()[c.id] = c
    return c


def get(peer_id):
    """
    """
    for c in connectors().values():
        if c.peer_id == peer_id:
            return c
    return None

#------------------------------------------------------------------------------


class DHTUDPConnector(automat.Automat):
    """
    This class implements all the functionality of the ``udp_connector()``
    state machine.
    """

    fast = True

    def __init__(self, node, peer_id):
        self.node = node
        self.peer_id = peer_id
        name = 'udp_connector[%s]' % self.peer_id
        automat.Automat.__init__(self, name, 'AT_STARTUP', 18)

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.listen_port = None
        self.my_id = None
        self.my_address = None
        self.working_deferred = None

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'DHT_LOOP'
                self.doInit(*args, **kwargs)
                self.KeyPosition = 0
                self.doDHTReadIncoming(*args, **kwargs)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'dht-write-success':
                self.state = 'DHT_READ'
                self.doDHTReadPeerAddress(*args, **kwargs)
            elif event == 'dht-write-failed':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'abort':
                self.state = 'ABORTED'
                self.doDestroyMe(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'dht-read-success':
                self.state = 'DONE'
                self.doStartNewSession(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-read-failed':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'abort':
                self.state = 'ABORTED'
                self.doDestroyMe(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---DHT_LOOP---
        elif self.state == 'DHT_LOOP':
            if event == 'dht-read-failed':
                self.state = 'DHT_WRITE'
                self.doDHTWriteIncoming(*args, **kwargs)
            elif event == 'dht-read-success' and self.KeyPosition >= 10:
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-read-success' and self.KeyPosition < 10 and not self.isMyIncoming(*args, **kwargs):
                self.KeyPosition += 1
                self.doDHTReadIncoming(*args, **kwargs)
            elif event == 'dht-read-success' and self.isMyIncoming(*args, **kwargs):
                self.state = 'DHT_READ'
                self.doDHTReadPeerAddress(*args, **kwargs)
            elif event == 'abort':
                self.state = 'ABORTED'
                self.doDestroyMe(*args, **kwargs)
        #---ABORTED---
        elif self.state == 'ABORTED':
            pass
        return None

    def isMyIncoming(self, *args, **kwargs):
        """
        Condition method.
        """
        incoming_peer_id, incoming_user_address = args[0]
        return incoming_peer_id == self.my_id and incoming_user_address == self.my_address

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.listen_port, self.my_id, self.my_address = args[0]

    def doDHTReadIncoming(self, *args, **kwargs):
        """
        Action method.
        """
        key = self.peer_id + ':incoming' + str(self.KeyPosition)
        self.working_deferred = dht_service.get_value(key)
        if not self.working_deferred:
            self.automat('dht-read-failed')
        else:
            self.working_deferred.addCallback(
                self._got_peer_incoming, key, self.KeyPosition)
            self.working_deferred.addErrback(
                lambda x: self.automat('dht-read-failed'))

    def doDHTWriteIncoming(self, *args, **kwargs):
        """
        Action method.
        """
        key = self.peer_id + ':incoming' + str(self.KeyPosition)
        value = '%s %s:%d %s\n' % (str(self.my_id), self.my_address[0], self.my_address[1], str(time.time()))
        if _Debug:
            lg.out(_DebugLevel, 'doDHTWriteIncoming  key=%s' % key)
        self.working_deferred = dht_service.set_value(key, value, age=int(time.time()))
        if not self.working_deferred:
            self.automat('dht-write-failed')
        else:
            try:
                self.working_deferred.addCallback(self._wrote_peer_incoming)
                self.working_deferred.addErrback(
                    lambda x: self.automat('dht-write-failed'))
            except:
                self.automat('dht-write-failed')

    def doStartNewSession(self, *args, **kwargs):
        """
        Action method.
        """
        from transport.udp import udp_session
        peer_address = args[0]
        if self.node.my_address is None:
            if _Debug:
                lg.out(
                    _DebugLevel,
                    'udp_connector.doStartNewSession to %s at %s SKIP because my_address is None' %
                    (self.peer_id,
                     peer_address))
            return
        active_sessions = udp_session.get(peer_address)
        if active_sessions:
            if _Debug:
                lg.out(_DebugLevel, 'udp_connector.doStartNewSession SKIP because found existing by peer address %s : %s' % (
                    peer_address, active_sessions, ))
            return
        active_sessions = udp_session.get_by_peer_id(self.peer_id)
        if active_sessions:
            if _Debug:
                lg.out(_DebugLevel, 'udp_connector.doStartNewSession SKIP because found existing by peer id %s : %s' % (
                    self.peer_id, active_sessions, ))
            return
        s = udp_session.create(self.node, peer_address, self.peer_id)
        s.automat('init', (self.listen_port, self.my_id, self.my_address))

    def doDHTReadPeerAddress(self, *args, **kwargs):
        """
        Action method.
        """
        key = self.peer_id + ':address'
        self.working_deferred = dht_service.get_value(key)
        if not self.working_deferred:
            self.automat('dht-read-failed')
        else:
            self.working_deferred.addCallback(self._got_peer_address, key)
            self.working_deferred.addErrback(
                lambda x: self.automat('dht-read-failed'))

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        from transport.udp import udp_session
        udp_session.report_and_remove_pending_outbox_files_to_host(
            self.peer_id, 'unable to establish connection')

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        if self.working_deferred:
            self.working_deferred.cancel()
            self.working_deferred = None
        self.node = None
        connectors().pop(self.id)
        self.destroy()

    def _got_peer_incoming(self, value, key, position):
        if _Debug:
            lg.out(
                _DebugLevel, 'udp_connector._got_peer_incoming at position %d: %d' %
                (position, len(
                    str(value))))
        self.working_deferred = None
        incoming = None
        if not isinstance(value, dict):
            self.automat('dht-read-failed')
            return
        try:
            # incoming = value.values()[0]
            incoming = value[dht_service.key_to_hash(key)]
        except:
            lg.out(2, '%r' % value)
            lg.exc()
            self.automat('dht-read-failed')
            return
        try:
            incoming_peer_id, incoming_user_address, _ = incoming.split(b' ')
            incoming_user_address = incoming_user_address.split(b':')
            incoming_user_address = (incoming_user_address[0], int(incoming_user_address[1]))
        except:
            lg.out(2, '%r' % incoming)
            lg.exc()
            self.automat('dht-read-failed')
            return
        self.automat('dht-read-success', (incoming_peer_id, incoming_user_address))

    def _wrote_peer_incoming(self, nodes):
        self.working_deferred = None
        if len(nodes) > 0:
            self.automat('dht-write-success')
        else:
            self.automat('dht-write-failed')

    def _got_peer_address(self, value, key):
        if not isinstance(value, dict):
            self.automat('dht-read-failed')
            return
        try:
            peer_ip, peer_port = value[dht_service.key_to_hash(key)].split(b':')
            peer_port = int(peer_port)
        except:
            lg.exc()
            self.automat('dht-read-failed')
            return
        if _Debug:
            lg.out(
                _DebugLevel, 'udp_connector._got_peer_address %s:%d ~ %s' %
                (peer_ip, peer_port, self.peer_id))
        self.automat('dht-read-success', (peer_ip, peer_port))
