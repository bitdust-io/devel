#!/usr/bin/env python
# proxy_sender.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
    * :red:`proxy_receiver.state`
    * :red:`relay-ack`
    * :red:`relay-failed`
    * :red:`relay-out`
    * :red:`retry`
    * :red:`retry-cache-failed`
    * :red:`retry-failed`
    * :red:`retry-send-failed`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 16

_PacketLogFileEnabled = False

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred
from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.automats import automat

from bitdust.logs import lg

from bitdust.lib import nameurl
from bitdust.lib import serialization
from bitdust.lib import net_misc

from bitdust.main import config
from bitdust.main import settings

from bitdust.crypt import encrypted
from bitdust.crypt import key
from bitdust.crypt import signed

from bitdust.services import driver

from bitdust.contacts import identitycache

from bitdust.p2p import commands
from bitdust.p2p import network_connector

from bitdust.transport import callback
from bitdust.transport import packet_out

from bitdust.transport.proxy import proxy_receiver

from bitdust.userid import id_url
from bitdust.userid import global_id
from bitdust.userid import my_id

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
        _ProxySender = ProxySender(
            name='proxy_sender',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=False,
            log_transitions=_Debug,
        )
    if event is not None:
        _ProxySender.automat(event, *args, **kwargs)
    return _ProxySender


#------------------------------------------------------------------------------


class ProxySender(automat.Automat):
    """
    This class implements all the functionality of the ``proxy_sender()`` state
    machine.
    """
    def init(self, **kwargs):
        global _PacketLogFileEnabled
        _PacketLogFileEnabled = config.conf().getBool('logs/packet-enabled')
        self._sending_enabled = settings.enablePROXYsending()

    def to_json(self):
        j = super().to_json()
        j.update(
            {
                'proto': proxy_receiver.GetRouterProtoHost()[0] if proxy_receiver.GetRouterProtoHost() else '',
                'host': net_misc.pack_address_text(proxy_receiver.GetRouterProtoHost()[1]) if proxy_receiver.GetRouterProtoHost() else '',
                'idurl': proxy_receiver.GetRouterIDURL(),
                'bytes_received': 0,
                'bytes_sent': self.traffic_out,
            }
        )
        return j

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
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'start' and proxy_receiver.A().state != 'LISTEN' and self.isSendingEnabled(*args, **kwargs):
                self.state = 'ROUTER?'
                self.doStartFilterOutgoingTraffic(*args, **kwargs)
            elif ((event == 'proxy_receiver.state' and args[0] == 'LISTEN') or (event == 'start' and proxy_receiver.A().state == 'LISTEN')) and self.isSendingEnabled(*args, **kwargs):
                self.state = 'REDIRECTING'
                self.doStartFilterOutgoingTraffic(*args, **kwargs)
        #---ROUTER?---
        elif self.state == 'ROUTER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopFilterOutgoingTraffic(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif (event == 'proxy_receiver.state' and args[0] == 'LISTEN'):
                self.state = 'REDIRECTING'
                self.doSendAllPendingPackets(*args, **kwargs)
            elif (event == 'proxy_receiver.state' and args[0] == 'OFFLINE'):
                self.state = 'STOPPED'
                self.doStopFilterOutgoingTraffic(*args, **kwargs)
        #---REDIRECTING---
        elif self.state == 'REDIRECTING':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doStopFilterOutgoingTraffic(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopFilterOutgoingTraffic(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'relay-failed':
                self.doRetryCancelPacket(*args, **kwargs)
            elif event == 'retry' or event == 'retry-cache-failed' or event == 'retry-send-failed' or event == 'retry-failed':
                self.doReportRetry(event, *args, **kwargs)
            elif event == 'relay-ack':
                self.doCleanPacket(*args, **kwargs)
            elif event == 'relay-out':
                self.doCountTraffic(*args, **kwargs)
            elif (event == 'proxy_receiver.state' and args[0] != 'LISTEN'):
                self.state = 'ROUTER?'
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isSendingEnabled(self, *args, **kwargs):
        """
        Condition method.
        """
        return self._sending_enabled

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.traffic_out = 0
        self.pending_packets = []
        self.pending_ping_packets = []
        self.max_pending_packets = 100  # TODO: read from settings
        self.packets_retries = {}
        self.sent_packets = {}

    def doStartFilterOutgoingTraffic(self, *args, **kwargs):
        """
        Action method.
        """
        callback.insert_outbox_filter_callback(0, self._on_first_outbox_packet)

    def doStopFilterOutgoingTraffic(self, *args, **kwargs):
        """
        Action method.
        """
        callback.remove_outbox_filter_callback(self._on_first_outbox_packet)

    def doCountTraffic(self, *args, **kwargs):
        """
        Action method.
        """
        _, newpacket, _ = args[0]
        self.traffic_out += len(newpacket.Payload)

    def doCleanPacket(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_clean_sent_packet(args[0])

    def doRetryCancelPacket(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_retry_one_time(args[0])

    def doReportRetry(self, event, *args, **kwargs):
        """
        Action method.
        """
        if _PacketLogFileEnabled:
            label = event.upper().replace('-', ' ')
            fail_info = args[0]
            lg.out(
                0,
                '\033[0;49;36m%s %s(%s) from %s to %s %s\033[0m' % (label, fail_info['command'], fail_info['packet_id'], global_id.UrlToGlobalID(fail_info['from']), global_id.UrlToGlobalID(fail_info['to']), fail_info['error']),
                log_name='packet',
                showtime=True,
            )

    def doSendAllPendingPackets(self, *args, **kwargs):
        """
        Action method.
        """
        def _do_send():
            while len(self.pending_packets):
                outpacket, callbacks, wide, response_timeout, keep_alive, pending_result = self.pending_packets.pop(0)
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_sender.doSendAllPendingPackets populate one more item, %d more in the queue' % (len(self.pending_packets)))
                result_packet = self._on_first_outbox_packet(outpacket, wide, callbacks, response_timeout=response_timeout, keep_alive=keep_alive)
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
        global _PacketLogFileEnabled
        _PacketLogFileEnabled = False
        self.traffic_out = 0
        self.pending_packets = []
        self.pending_ping_packets = []
        self.max_pending_packets = 0
        self.packets_retries.clear()
        self.sent_packets.clear()
        self.destroy()
        global _ProxySender
        del _ProxySender
        _ProxySender = None

    def _do_add_pending_packet(self, outpacket, callbacks, wide, response_timeout, keep_alive):
        if len(self.pending_packets) > self.max_pending_packets:
            if _Debug:
                lg.warn('pending packets queue is full, skip sending outgoing packet')
            return None
        pending_result = Deferred()
        self.pending_packets.append((outpacket, callbacks, wide, response_timeout, keep_alive, pending_result))
        if _Debug:
            lg.out(_DebugLevel, 'proxy_sender._do_add_pending_packet %s' % outpacket)
        return pending_result

    def _do_send_packet_to_router(self, outpacket, callbacks, wide, response_timeout, keep_alive, is_retry=False):
        router_idurl = proxy_receiver.GetRouterIDURL()
        router_identity_obj = proxy_receiver.GetRouterIdentity()
        router_proto_host = proxy_receiver.GetRouterProtoHost()
        router_proto, router_host = router_proto_host
        publickey = router_identity_obj.publickey
        my_original_identity_src = proxy_receiver.ReadMyOriginalIdentitySource()
        if not router_idurl or not router_identity_obj or not router_proto_host or not my_original_identity_src:
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._do_send_packet_to_router SKIP because router not ready yet')
            return self._do_add_pending_packet(outpacket, callbacks, wide, response_timeout, keep_alive)
        if outpacket.RemoteID.to_bin() == router_idurl.to_bin():
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._do_send_packet_to_router SKIP, packet addressed to router and must be sent in a usual way')
            return None
        try:
            raw_data = outpacket.Serialize()
        except:
            lg.exc('failed to Serialize %s' % outpacket)
            return None
        # see proxy_router.ProxyRouter : doForwardOutboxPacket() for receiving part
        json_payload = {
            'f': my_id.getIDURL().to_bin(),  # from
            't': outpacket.RemoteID.to_bin(),  # to
            'p': raw_data,  # payload
            'w': wide,  # wide
            'i': response_timeout,
            'a': keep_alive,
            'r': is_retry,
        }
        if not json_payload['t']:
            raise ValueError('receiver idurl was not set')
        raw_bytes = serialization.DictToBytes(json_payload)
        block = encrypted.Block(
            CreatorID=my_id.getIDURL(),
            BackupID='routed outgoing data',
            BlockNumber=0,
            SessionKey=key.NewSessionKey(session_key_type=key.SessionKeyType()),
            SessionKeyType=key.SessionKeyType(),
            LastBlock=True,
            Data=raw_bytes,
            EncryptKey=lambda inp: key.EncryptOpenSSHPublicKey(publickey, inp),
        )
        block_encrypted = block.Serialize()
        newpacket = signed.Packet(
            Command=commands.RelayOut(),
            OwnerID=outpacket.OwnerID,
            CreatorID=my_id.getIDURL(),
            PacketID=outpacket.PacketID,
            Payload=block_encrypted,
            RemoteID=router_idurl,
        )
        if response_timeout is not None:
            # must give some extra time for the proxy re-routing
            response_timeout += 10.0
        routed_packet = packet_out.create(
            outpacket=outpacket,
            wide=False,
            callbacks={},
            route={
                'packet': newpacket,  # pointing "newpacket" to router node
                'proto': router_proto,
                'host': router_host,
                'remoteid': router_idurl,
                'description': 'RelayOut_%s[%s]_%s' % (outpacket.Command, outpacket.PacketID, nameurl.GetName(router_idurl)),
            },
            response_timeout=response_timeout,
            keep_alive=True,
        )
        for command, cb_list in callbacks.items():
            if isinstance(cb_list, list):
                for cb in cb_list:
                    routed_packet.set_callback(command, cb)
            else:
                routed_packet.set_callback(command, cb_list)
        if not is_retry:
            _key = (outpacket.Command, outpacket.PacketID, outpacket.RemoteID.to_bin())
            self.sent_packets[_key] = (routed_packet, outpacket)
        self.event('relay-out', (outpacket, newpacket, routed_packet))
        if _Debug:
            lg.out(_DebugLevel, '>>>Relay-OUT %s sent to %s://%s with %d bytes, timeout=%r' % (str(outpacket), router_proto, router_host, len(block_encrypted), response_timeout))
        if _PacketLogFileEnabled:
            lg.out(
                0, '\033[0;49;36mRELAY OUT %s(%s) with %s bytes from %s to %s via %s\033[0m' %
                (outpacket.Command, outpacket.PacketID, len(raw_bytes), global_id.UrlToGlobalID(outpacket.CreatorID), global_id.UrlToGlobalID(outpacket.RemoteID), global_id.UrlToGlobalID(router_idurl)), log_name='packet', showtime=True
            )
        del raw_bytes
        del block
        del newpacket
        del outpacket
        del router_identity_obj
        del router_idurl
        del router_proto_host
        return routed_packet

    def _do_cancel_outbox_packets(self, fail_info):
        to_idurl = id_url.field(fail_info['to'])
        from_idurl = id_url.field(fail_info['from'])
        for p in packet_out.search_by_packet_id(fail_info['packet_id']):
            if p.outpacket.Command == fail_info['command']:
                if id_url.to_bin(to_idurl) == p.outpacket.RemoteID.to_bin():
                    if p.outpacket.CreatorID.to_bin() == id_url.to_bin(from_idurl) or p.outpacket.OwnerID.to_bin() == id_url.to_bin(from_idurl):
                        if _Debug:
                            lg.dbg(_DebugLevel, 'about to cancel %r because sending via proxy transport is failed' % p)
                        p.automat('cancel')

    def _do_retry_one_time(self, fail_info):
        to_idurl = id_url.field(fail_info['to']).to_bin()
        from_idurl = id_url.field(fail_info['from']).to_bin()
        _key = (fail_info['command'], fail_info['packet_id'], from_idurl, to_idurl)
        current_retries = self.packets_retries.get(_key, 0)
        if _Debug:
            lg.args(_DebugLevel, key=_key, retries=current_retries)
        if fail_info.get('error') != 'route already closed':
            if _Debug:
                lg.dbg(_DebugLevel, 'failed sending routed packet : %r' % fail_info)
            self._do_clean_sent_packet(fail_info)
            self._do_cancel_outbox_packets(fail_info)
            self.packets_retries.pop(_key, None)
            return
        if current_retries >= 1:
            if _Debug:
                lg.dbg(_DebugLevel, 'failed sending routed packet after few attempts : %r' % fail_info)
            self.automat('retry-failed', fail_info)
            self._do_clean_sent_packet(fail_info)
            self._do_cancel_outbox_packets(fail_info)
            self.packets_retries.pop(_key, None)
            return
        self.packets_retries[_key] = current_retries + 1
        d = identitycache.immediatelyCaching(fail_info['to'])
        d.addCallback(self._on_cache_retry_success, fail_info)
        d.addErrback(self._on_cache_retry_failed, fail_info)

    def _do_clean_sent_packet(self, info):
        to_idurl = id_url.to_bin(info['to'])
        to_remove = []
        for _key in self.sent_packets.keys():
            routed_packet, outpacket = self.sent_packets.get(_key, (
                None,
                None,
            ))
            if not outpacket:
                if _Debug:
                    lg.dbg(_DebugLevel, 'found empty outpacket : %r' % routed_packet)
                to_remove.append(_key)
                continue
            if outpacket.Command != info['command']:
                continue
            if outpacket.PacketID != info['packet_id']:
                continue
            if outpacket.RemoteID.to_bin() != to_idurl:
                continue
            to_remove.append(_key)
        for _key in to_remove:
            routed_packet, outpacket = self.sent_packets.pop(_key, (
                None,
                None,
            ))

    def _on_cache_retry_success(self, xmlsrc, fail_info):
        if _Debug:
            lg.args(_DebugLevel, sent_packets=len(self.sent_packets), fail_info=fail_info)
        to_idurl = id_url.to_bin(fail_info['to'])
        for _key in self.sent_packets.keys():
            routed_packet, outpacket = self.sent_packets.get(_key, (
                None,
                None,
            ))
            if not outpacket:
                if _Debug:
                    lg.dbg(_DebugLevel, 'found empty outpacket : %r' % routed_packet)
                continue
            if outpacket.Command != fail_info['command']:
                continue
            if outpacket.PacketID != fail_info['packet_id']:
                continue
            if outpacket.RemoteID.to_bin() != to_idurl:
                continue
            routed_retry_packet = self._do_send_packet_to_router(
                outpacket=outpacket,
                callbacks=routed_packet.callbacks,
                wide=fail_info.get('wide', False),
                keep_alive=fail_info.get('keep_alive', False),
                response_timeout=fail_info.get('response_timeout', None),
                is_retry=True,
            )
            if not routed_retry_packet:
                self.automat('retry-send-failed', fail_info)
            else:
                self.sent_packets[_key] = (
                    routed_retry_packet,
                    outpacket,
                )
                self.automat('retry', fail_info)
            del routed_packet
        return None

    def _on_cache_retry_failed(self, err, fail_info):
        if _Debug:
            lg.args(_DebugLevel, err=err, fail_info=fail_info)
        self.automat('retry-cache-failed', fail_info)
        self._do_cancel_outbox_packets(fail_info)
        return None

    def _on_first_outbox_packet(self, outpacket, wide, callbacks, target=None, route=None, response_timeout=None, keep_alive=True):
        """
        Will be called first for every outgoing packet.
        Must return `None` if that packet should be sent in a normal way.
        Otherwise will create another "routed" packet instead and return it.
        """
        if not driver.is_on('service_proxy_transport'):
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_first_outbox_packet SKIP sending %r because service_proxy_transport is not started yet' % outpacket)
            return None
        if not proxy_receiver.A():
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_first_outbox_packet SKIP sending %r because proxy_receiver() not exist' % outpacket)
            return None
        if outpacket.Command == commands.Identity() and outpacket.CreatorID == my_id.getIDURL():
            if proxy_receiver.GetPossibleRouterIDURL() and proxy_receiver.GetPossibleRouterIDURL().to_bin() == outpacket.RemoteID.to_bin():
                if network_connector.A().state == 'DISCONNECTED':
                    if _Debug:
                        lg.out(_DebugLevel, 'proxy_sender._on_first_outbox_packet SKIP sending %r because network_connector() is DISCONNECTED' % outpacket)
                    return None
                if network_connector.A().state == 'CONNECTED':
                    lg.warn('sending %r to "possible" proxy router %r' % (outpacket, proxy_receiver.GetPossibleRouterIDURL()))
                    pkt_out = packet_out.create(outpacket, wide, callbacks, target, route, response_timeout, keep_alive)
                    return pkt_out
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_sender._on_first_outbox_packet SKIP sending %r, network_connector() have transition state' % outpacket)
                return None
        if proxy_receiver.A().state != 'LISTEN':
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_first_outbox_packet DELLAYED %r because proxy_receiver state is not LISTEN yet' % outpacket)
            return self._do_add_pending_packet(outpacket, callbacks, wide, response_timeout, keep_alive)
        return self._do_send_packet_to_router(
            outpacket=outpacket,
            callbacks=callbacks,
            wide=wide,
            keep_alive=keep_alive,
            response_timeout=response_timeout,
        )

    def _on_network_connector_state_changed(self, oldstate, newstate, event_string, *args, **kwargs):
        if newstate == 'CONNECTED' and oldstate != newstate:
            if _Debug:
                lg.out(_DebugLevel, 'proxy_sender._on_network_connector_state_changed will send %d pending "ping" packets' % len(self.pending_ping_packets))
            while len(self.pending_ping_packets):
                outpacket, wide, callbacks, target, route, response_timeout, keep_alive, pending_result = self.pending_ping_packets.pop(0)
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_sender._on_network_connector_state_changed populate one more item, %d more in the queue' % (len(self.pending_packets)))
                result_packet = self._on_first_outbox_packet(outpacket, wide, callbacks, target, route, response_timeout, keep_alive)
                if not isinstance(result_packet, packet_out.PacketOut):
                    lg.warn('failed sending pending packet %s, skip all pending packets' % outpacket)
                    self.pending_ping_packets = []
                    break
                pending_result.callback(result_packet)


#------------------------------------------------------------------------------


def main():
    reactor.callWhenRunning(A, 'init')  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable


#------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
