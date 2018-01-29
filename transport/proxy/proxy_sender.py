#!/usr/bin/env python
# proxy_sender.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (proxy_sender.py) is part of BitDust Software.
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
.. module:: proxy_sender.

.. role:: red

BitDust proxy_sender() Automat

.. raw:: html

    <a href="proxy_sender.png" target="_blank">
    <img src="proxy_sender.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`init`
    * :red:`outbox-packet-sent`
    * :red:`proxy_receiver.state`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred, fail
from twisted.internet import reactor

#------------------------------------------------------------------------------

from automats import automat

from logs import lg


from lib import nameurl

from crypt import encrypted
from crypt import key
from crypt import signed

from services import driver

from p2p import commands

from userid import my_id

from transport import callback
from transport import packet_out

from transport.proxy import proxy_receiver

#------------------------------------------------------------------------------

_ProxySender = None

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with proxy_sender machine.
    """
    global _ProxySender
    if event is None and arg is None:
        return _ProxySender
    if _ProxySender is None:
        # set automat name and starting state here
        _ProxySender = ProxySender('proxy_sender', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _ProxySender.automat(event, arg)
    return _ProxySender

#------------------------------------------------------------------------------


class ProxySender(automat.Automat):
    """
    This class implements all the functionality of the ``proxy_sender()`` state
    machine.
    """

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of proxy_sender machine.
        """

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when proxy_sender state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in
        the proxy_sender but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python
        <http://code.google.com/p/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start' and proxy_receiver.A().state is not 'LISTEN':
                self.state = 'ROUTER?'
                self.doStartFilterOutgoingTraffic(arg)
            elif event == 'start' and proxy_receiver.A().state is 'LISTEN':
                self.state = 'REDIRECTING'
                self.doStartFilterOutgoingTraffic(arg)
        #---ROUTER?---
        elif self.state == 'ROUTER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopFilterOutgoingTraffic(arg)
                self.doDestroyMe(arg)
            elif (event == 'proxy_receiver.state' and arg == 'OFFLINE'):
                self.state = 'STOPPED'
            elif (event == 'proxy_receiver.state' and arg == 'LISTEN'):
                self.state = 'REDIRECTING'
                self.doSendAllPendingPackets(arg)
        #---REDIRECTING---
        elif self.state == 'REDIRECTING':
            if event == 'outbox-packet-sent':
                self.doCountTraffic(arg)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doStopFilterOutgoingTraffic(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopFilterOutgoingTraffic(arg)
                self.doDestroyMe(arg)
            elif event == 'proxy_receiver.state' is not 'LISTEN':
                self.state = 'ROUTER?'
        return None

    def doInit(self, arg):
        """
        Action method.
        """
        self.traffic_out = 0
        self.pending_packets = []
        self.max_pending_packets = 100  # TODO: read from settings

    def doStartFilterOutgoingTraffic(self, arg):
        """
        Action method.
        """
        callback.insert_outbox_filter_callback(0, self._on_outbox_packet)

    def doStopFilterOutgoingTraffic(self, arg):
        """
        Action method.
        """
        callback.remove_finish_file_sending_callback(self._on_outbox_packet)

    def doCountTraffic(self, arg):
        """
        Action method.
        """
        _, newpacket, _ = arg
        self.traffic_out += len(newpacket.Payload)

    def doSendAllPendingPackets(self, arg):
        """
        Action method.
        """
        def _do_send():
            while len(self.pending_packets):
                outpacket, wide, callbacks, pending_result = self.pending_packets.pop(0)
                result_packet = self._on_outbox_packet(outpacket, wide, callbacks)
                if not isinstance(result_packet, packet_out.PacketOut):
                    lg.warn('failed sending pending packet %s, skip all pending packets' % outpacket)
                    self.pending_packets = []
                    break
                pending_result.callback(result_packet)
        reactor.callLater(0.2, _do_send)

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()
        global _ProxySender
        del _ProxySender
        _ProxySender = None

    def _add_pending_packet(self, outpacket, wide, callbacks):
        if len(self.pending_packets) > self.max_pending_packets:
            if _Debug:
                lg.warn('pending packets queue is full, skip sending outgoing packet')
            return fail((outpacket, wide, callbacks))
        pending_result = Deferred()
        self.pending_packets.append((outpacket, wide, callbacks, pending_result))
        if _Debug:
            lg.out(_DebugLevel, 'proxy_sender._add_pending_packet %s' % outpacket)
        return pending_result

    def _on_outbox_packet(self, outpacket, wide, callbacks, **kwargs):
        """
        """
        if not driver.is_on('service_proxy_transport'):
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_outbox_packet SKIP because service_proxy_transport is not started')
            return None
        if proxy_receiver.A() and proxy_receiver.A().state != 'LISTEN':
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_outbox_packet SKIP because proxy_receiver state is not LISTEN')
            return self._add_pending_packet(outpacket, wide, callbacks)
        router_idurl = proxy_receiver.GetRouterIDURL()
        router_identity_obj = proxy_receiver.GetRouterIdentity()
        router_proto_host = proxy_receiver.GetRouterProtoHost()
        router_proto, router_host = router_proto_host
        publickey = router_identity_obj.publickey
        my_original_identity_src = proxy_receiver.ReadMyOriginalIdentitySource()
        if not router_idurl or not router_identity_obj or not router_proto_host or not my_original_identity_src:
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_outbox_packet SKIP because remote router not ready')
            return self._add_pending_packet(outpacket, wide, callbacks)
        if outpacket.RemoteID == router_idurl:
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_outbox_packet SKIP, packet addressed to router and must be sent in a usual way')
            return None
        src = ''
        src += my_id.getLocalID() + '\n'
        src += outpacket.RemoteID + '\n'
        src += 'wide\n' if wide else '\n'
        src += outpacket.Serialize()
        block = encrypted.Block(
            my_id.getLocalID(),
            'routed outgoing data',
            0,
            key.NewSessionKey(),
            key.SessionKeyType(),
            True,
            src,
            EncryptKey=lambda inp: key.EncryptOpenSSHPublicKey(publickey, inp))
        block_encrypted = block.Serialize()
        newpacket = signed.Packet(
            commands.Relay(),
            outpacket.OwnerID,
            my_id.getLocalID(),
            outpacket.PacketID,
            block_encrypted,
            router_idurl)
        result_packet = packet_out.create(
            outpacket,
            wide=wide,
            callbacks=callbacks,
            route={
                'packet': newpacket,
                'proto': router_proto,
                'host': router_host,
                'remoteid': router_idurl,
                'description': 'Relay_%s[%s]_%s' % (outpacket.Command, outpacket.PacketID, nameurl.GetName(router_idurl)),
            })
        self.event('outbox-packet-sent', (outpacket, newpacket, result_packet))
        if _Debug:
            lg.out(_DebugLevel, '>>>Relay-OUT %s' % str(outpacket))
            lg.out(_DebugLevel, '        sent to %s://%s with %d bytes' % (
                router_proto, router_host, len(block_encrypted)))
        del src
        del block
        del newpacket
        del outpacket
        del router_identity_obj
        del router_idurl
        del router_proto_host
        return result_packet

#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

#------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
