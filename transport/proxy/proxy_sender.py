#!/usr/bin/env python
# proxy_sender.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred
from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from automats import automat

from logs import lg

from lib import nameurl
from lib import serialization

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


def A(event=None, *args, **kwargs):
    """
    Access method to interact with proxy_sender machine.
    """
    global _ProxySender
    if event is None and not args:
        return _ProxySender
    if _ProxySender is None:
        # set automat name and starting state here
        _ProxySender = ProxySender('proxy_sender', 'AT_STARTUP',
                                   debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, )
    if event is not None:
        _ProxySender.automat(event, *args, **kwargs)
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

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when proxy_sender state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in
        the proxy_sender but its state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python
        <http://code.google.com/p/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'start' and proxy_receiver.A().state is not 'LISTEN':
                self.state = 'ROUTER?'
                self.doStartFilterOutgoingTraffic(*args, **kwargs)
            elif event == 'start' and proxy_receiver.A().state is 'LISTEN':
                self.state = 'REDIRECTING'
                self.doStartFilterOutgoingTraffic(*args, **kwargs)
        #---ROUTER?---
        elif self.state == 'ROUTER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopFilterOutgoingTraffic(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif (event == 'proxy_receiver.state' and args[0] == 'OFFLINE'):
                self.state = 'STOPPED'
            elif (event == 'proxy_receiver.state' and args[0] == 'LISTEN'):
                self.state = 'REDIRECTING'
                self.doSendAllPendingPackets(*args, **kwargs)
        #---REDIRECTING---
        elif self.state == 'REDIRECTING':
            if event == 'outbox-packet-sent':
                self.doCountTraffic(*args, **kwargs)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doStopFilterOutgoingTraffic(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopFilterOutgoingTraffic(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'proxy_receiver.state' is not 'LISTEN':
                self.state = 'ROUTER?'
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.traffic_out = 0
        self.pending_packets = []
        self.max_pending_packets = 100  # TODO: read from settings

    def doStartFilterOutgoingTraffic(self, *args, **kwargs):
        """
        Action method.
        """
        callback.insert_outbox_filter_callback(0, self._on_first_outbox_packet)

    def doStopFilterOutgoingTraffic(self, *args, **kwargs):
        """
        Action method.
        """
        callback.remove_finish_file_sending_callback(self._on_first_outbox_packet)

    def doCountTraffic(self, *args, **kwargs):
        """
        Action method.
        """
        _, newpacket, _ = args[0]
        self.traffic_out += len(newpacket.Payload)

    def doSendAllPendingPackets(self, *args, **kwargs):
        """
        Action method.
        """
        def _do_send():
            while len(self.pending_packets):
                outpacket, wide, callbacks, pending_result = self.pending_packets.pop(0)
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_sender.doSendAllPendingPackets populate one more item, %d more in the queue' % (
                        len(self.pending_packets)))
                result_packet = self._on_first_outbox_packet(outpacket, wide, callbacks)
                if not isinstance(result_packet, packet_out.PacketOut):
                    lg.warn('failed sending pending packet %s, skip all pending packets' % outpacket)
                    self.pending_packets = []
                    break
                pending_result.callback(result_packet)
        reactor.callLater(0, _do_send)  # @UndefinedVariable

    def doDestroyMe(self, *args, **kwargs):
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
            return None
        pending_result = Deferred()
        self.pending_packets.append((outpacket, wide, callbacks, pending_result))
        if _Debug:
            lg.out(_DebugLevel, 'proxy_sender._add_pending_packet %s' % outpacket)
        return pending_result

    def _on_first_outbox_packet(self, outpacket, wide, callbacks, target=None, route=None, response_timeout=None, keep_alive=True):
        """
        Will be called first for every outgoing packet.
        Must to return None if that packet should be send normal way.
        Otherwise will create another "routerd" packet instead and return it.
        """
        if not driver.is_on('service_proxy_transport'):
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_first_outbox_packet SKIP because service_proxy_transport is not started')
            return None
        if proxy_receiver.A() and proxy_receiver.A().state != 'LISTEN':
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_first_outbox_packet DELLAYED because proxy_receiver state is not LISTEN yet')
            return self._add_pending_packet(outpacket, wide, callbacks)
        router_idurl = proxy_receiver.GetRouterIDURL()
        router_identity_obj = proxy_receiver.GetRouterIdentity()
        router_proto_host = proxy_receiver.GetRouterProtoHost()
        router_proto, router_host = router_proto_host
        publickey = router_identity_obj.publickey
        my_original_identity_src = proxy_receiver.ReadMyOriginalIdentitySource()
        if not router_idurl or not router_identity_obj or not router_proto_host or not my_original_identity_src:
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_first_outbox_packet SKIP because remote router not ready')
            return self._add_pending_packet(outpacket, wide, callbacks)
        if outpacket.RemoteID == router_idurl:
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_first_outbox_packet SKIP, packet addressed to router and must be sent in a usual way')
            return None
        try:
            raw_data = outpacket.Serialize()
        except:
            lg.exc('failed to Serialize %s' % outpacket)
            return None
        # see proxy_router.ProxyRouter : doForwardOutboxPacket() for receiving part
        json_payload = {
            'f': my_id.getLocalID(),    # from
            't': outpacket.RemoteID,    # to
            'w': wide,                  # wide
            'p': raw_data,              # payload
        }
        raw_bytes = serialization.DictToBytes(json_payload)
        block = encrypted.Block(
            CreatorID=my_id.getLocalID(),
            BackupID='routed outgoing data',
            BlockNumber=0,
            SessionKey=key.NewSessionKey(),
            SessionKeyType=key.SessionKeyType(),
            LastBlock=True,
            Data=raw_bytes,
            EncryptKey=lambda inp: key.EncryptOpenSSHPublicKey(publickey, inp),
        )
        block_encrypted = block.Serialize()
        newpacket = signed.Packet(
            Command=commands.Relay(),
            OwnerID=outpacket.OwnerID,
            CreatorID=my_id.getLocalID(),
            PacketID=outpacket.PacketID,
            Payload=block_encrypted,
            RemoteID=router_idurl,
        )
        routed_packet = packet_out.create(
            outpacket,
            wide=wide,
            callbacks=callbacks,
            route={
                'packet': newpacket,
                # pointing "newpacket" to another node
                'proto': router_proto,
                'host': router_host,
                'remoteid': router_idurl,
                'description': 'Relay_%s[%s]_%s' % (outpacket.Command, outpacket.PacketID, nameurl.GetName(router_idurl)),
            },
            response_timeout=response_timeout,
            keep_alive=keep_alive,
        )
        self.event('outbox-packet-sent', (outpacket, newpacket, routed_packet))
        if _Debug:
            lg.out(_DebugLevel, '>>>Relay-OUT %s' % str(outpacket))
            lg.out(_DebugLevel, '        sent to %s://%s with %d bytes' % (
                router_proto, router_host, len(block_encrypted)))
        del raw_bytes
        del block
        del newpacket
        del outpacket
        del router_identity_obj
        del router_idurl
        del router_proto_host
        return routed_packet

#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor  # @UnresolvedImport
    reactor.callWhenRunning(A, 'init')  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable

#------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
