#!/usr/bin/env python
# broadcast_listener.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (broadcast_listener.py) is part of BitDust Software.
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
.. module:: broadcast_listener.

.. role:: red

BitDust broadcast_listener() Automat

EVENTS:
    * :red:`broadcaster-connected`
    * :red:`connect`
    * :red:`disconnect`
    * :red:`incoming-message`
    * :red:`init`
    * :red:`lookup-failed`
    * :red:`message-failed`
    * :red:`outbound-message`
    * :red:`shutdown`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import json

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from transport import callback

from p2p import p2p_service
from p2p import commands

#------------------------------------------------------------------------------

_BroadcastListener = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _BroadcastListener
    if event is None and not args:
        return _BroadcastListener
    if _BroadcastListener is None:
        # set automat name and starting state here
        _BroadcastListener = BroadcastListener('broadcast_listener', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _BroadcastListener.automat(event, *args, **kwargs)
    return _BroadcastListener

#------------------------------------------------------------------------------


class BroadcastListener(automat.Automat):
    """
    This class implements all the functionality of the ``broadcast_listener()``
    state machine.
    """

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of broadcast_listener() machine.
        """
        self.broadcaster_idurl = None
        self.incoming_broadcast_message_callback = None

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python
        <https://bitdust.io/visio2python/>`_ tool.
        """
        #--- AT_STARTUP
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(*args, **kwargs)
        #--- BROADCASTER?
        elif self.state == 'BROADCASTER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'disconnect' or event == 'lookup-failed':
                self.state = 'OFFLINE'
            elif event == 'broadcaster-connected':
                self.state = 'LISTENING'
                self.doSetBroadcaster(*args, **kwargs)
        #--- LISTENING
        elif self.state == 'LISTENING':
            if event == 'disconnect' or event == 'message-failed':
                self.state = 'OFFLINE'
                self.doRemoveBroadcaster(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doRemoveBroadcaster(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'outbound-message':
                self.doSendMessageToBroadcaster(*args, **kwargs)
            elif event == 'incoming-message':
                self.doNotifyInputMessage(*args, **kwargs)
        #--- OFFLINE
        elif self.state == 'OFFLINE':
            if event == 'connect':
                self.state = 'BROADCASTER?'
                self.doStartBroadcasterLookup(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #--- CLOSED
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.incoming_broadcast_message_callback = args[0]
        callback.append_inbox_callback(self._on_inbox_packet)

    def doStartBroadcasterLookup(self, *args, **kwargs):
        """
        Action method.
        """
        from broadcast import broadcasters_finder
        scope = args[0]
        if not scope:
            scope = []
        broadcasters_finder.A('start', (self.automat, {'action': 'listen', 'scopes': json.dumps(scope), }, []))

    def doSetBroadcaster(self, *args, **kwargs):
        """
        Action method.
        """
        self.broadcaster_idurl = args[0]

    def doRemoveBroadcaster(self, *args, **kwargs):
        """
        Action method.
        """
        self.broadcaster_idurl = None

    def doSendMessageToBroadcaster(self, *args, **kwargs):
        """
        Action method.
        """
        from broadcast import broadcast_service
        outpacket = broadcast_service.packet_for_broadcaster(
            self.broadcaster_idurl, *args, **kwargs)
        p2p_service.SendBroadcastMessage(outpacket)

    def doNotifyInputMessage(self, *args, **kwargs):
        """
        Action method.
        """
        msg, newpacket = args[0]
        if self.incoming_broadcast_message_callback is not None:
            self.incoming_broadcast_message_callback(msg)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.incoming_broadcast_message_callback = None
        callback.remove_inbox_callback(self._on_inbox_packet)
        self.unregister()
        global _BroadcastListener
        del _BroadcastListener
        _BroadcastListener = None

    #-----------------------------------------------------------------------------

    def _on_inbox_packet(self, newpacket, info, status, error_message):
        if newpacket.Command == commands.Broadcast():
            from broadcast import broadcast_service
            msg = broadcast_service.read_message_from_packet(newpacket)
            if not msg:
                lg.warn('not valid message in payload')
                return False
            if newpacket.CreatorID == self.broadcaster_idurl:
                # message from broadcaster - process incoming broadcast
                self.automat('incoming-message', (msg, newpacket))
                return True
            else:
                lg.warn('received broadcast message from another broadcaster? : %s != %s' % (
                    newpacket.CreatorID, self.broadcaster_idurl))
        return False
