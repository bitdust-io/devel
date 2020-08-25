#!/usr/bin/env python
# proxy_router.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (proxy_router.py) is part of BitDust Software.
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
.. module:: proxy_router.

.. role:: red

BitDust proxy_router() Automat

.. raw:: html

    <a href="proxy_router.png" target="_blank">
    <img src="proxy_router.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`cancel-route-received`
    * :red:`init`
    * :red:`known-identity-received`
    * :red:`network-connected`
    * :red:`network-disconnected`
    * :red:`request-route-ack-sent`
    * :red:`request-route-received`
    * :red:`routed-inbox-packet-received`
    * :red:`routed-outbox-packet-received`
    * :red:`routed-session-disconnected`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`unknown-identity-received`
    * :red:`unknown-packet-received`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import BytesIO

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

_PacketLogFileEnabled = False

#------------------------------------------------------------------------------

import time

#------------------------------------------------------------------------------

from twisted.internet.defer import DeferredList  #@UnresolvedImport
from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import nameurl
from lib import serialization
from lib import strng
from lib import net_misc

from main import config
from main import events

from crypt import key
from crypt import signed
from crypt import encrypted

from userid import identity
from userid import my_id
from userid import id_url
from userid import global_id

from contacts import identitydb
from contacts import identitycache
from contacts import contactsdb

from transport import callback
from transport import packet_out
from transport import packet_in
from transport import gateway

from p2p import p2p_service
from p2p import commands
from p2p import network_connector

#------------------------------------------------------------------------------

_ProxyRouter = None
_MaxRoutesNumber = 100

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with proxy_router() machine.
    """
    global _ProxyRouter
    if event is None and not args:
        return _ProxyRouter
    if _ProxyRouter is None:
        # set automat name and starting state here
        _ProxyRouter = ProxyRouter(
            name='proxy_router',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _ProxyRouter.automat(event, *args, **kwargs)
    return _ProxyRouter

#------------------------------------------------------------------------------


class ProxyRouter(automat.Automat):
    """
    This class implements all the functionality of the ``proxy_router()`` state
    machine.
    """

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of proxy_router() machine.
        """
        self.routes = {}
        self.closed_routes = {}
        self.acks = {}

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when proxy_router() state were changed.
        """
        if oldstate != 'TRANSPORTS?' and newstate == 'TRANSPORTS?':
            if network_connector.A().state == 'CONNECTED':
                reactor.callLater(0, self.automat, 'network-connected')  # @UndefinedVariable
            elif network_connector.A().state == 'DISCONNECTED':
                reactor.callLater(0, self.automat, 'network-disconnected')  # @UndefinedVariable

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
            if event == 'start':
                self.state = 'TRANSPORTS?'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---LISTEN---
        elif self.state == 'LISTEN':
            if event == 'routed-inbox-packet-received':
                self.doForwardInboxPacket(*args, **kwargs)
                self.doCountIncomingTraffic(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doUnregisterAllRouts(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'routed-outbox-packet-received':
                self.doForwardOutboxPacket(*args, **kwargs)
                self.doCountOutgoingTraffic(*args, **kwargs)
            elif event == 'stop' or event == 'network-disconnected':
                self.state = 'STOPPED'
                self.doUnregisterAllRouts(*args, **kwargs)
            elif event == 'request-route-ack-sent':
                self.doSaveRouteProtoHost(*args, **kwargs)
            elif event == 'known-identity-received':
                self.doSetContactsOverride(*args, **kwargs)
            elif event == 'unknown-identity-received':
                self.doClearContactsOverride(*args, **kwargs)
            elif event == 'unknown-packet-received':
                self.doSendFail(*args, **kwargs)
            elif event == 'request-route-received' or event == 'cancel-route-received':
                self.doProcessRequest(*args, **kwargs)
            elif event == 'routed-session-disconnected':
                self.doUnregisterRoute(*args, **kwargs)
        #---TRANSPORTS?---
        elif self.state == 'TRANSPORTS?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop' or event == 'network-disconnected':
                self.state = 'STOPPED'
            elif event == 'network-connected':
                self.state = 'LISTEN'
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        global _PacketLogFileEnabled
        _PacketLogFileEnabled = config.conf().getBool('logs/packet-enabled')
        # TODO: need to check again...
        # looks like we do not need to load routes at all...
        # proxy router must always start with no routes and keep them in memory
        # when proxy router restarts all connections with other nodes will be stopped anyway
        # self._load_routes()
        network_connector.A().addStateChangedCallback(self._on_network_connector_state_changed)
        callback.insert_inbox_callback(0, self._on_first_inbox_packet_received)
        callback.add_finish_file_sending_callback(self._on_finish_file_sending)
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')

    def doProcessRequest(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_process_request(args[0])

    def doUnregisterRoute(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_unregister_route(args[0])

    def doUnregisterAllRouts(self, *args, **kwargs):
        """
        Action method.
        """
        for idurl in list(self.routes.keys()):
            self._do_unregister_route(idurl)
        self.routes.clear()
        self.closed_routes.clear()

    def doForwardOutboxPacket(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_forward_outbox_packet(args[0])

    def doForwardInboxPacket(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_forward_inbox_packet(args[0])

    def doCountOutgoingTraffic(self, *args, **kwargs):
        """
        Action method.
        """

    def doCountIncomingTraffic(self, *args, **kwargs):
        """
        Action method.
        """

    def doSaveRouteProtoHost(self, *args, **kwargs):
        """
        Action method.
        """
        idurl, _, item, _, _, _ = args[0]
        idurl = id_url.field(idurl).original()
        new_address = (strng.to_text(item.proto), strng.to_text(item.host), )
        if idurl in self.routes and (new_address not in self.routes[idurl]['address']):
            self.routes[idurl]['address'].append(new_address)
            lg.info('added new active address %r for %s' % (new_address, nameurl.GetName(idurl), ))

    def doSetContactsOverride(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_set_contacts_override(args[0])

    def doClearContactsOverride(self, *args, **kwargs):
        """
        Action method.
        """
        result = identitycache.StopOverridingIdentity(args[0].CreatorID)
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router.doClearContactsOverride identity for %s, result=%s' % (
                args[0].CreatorID, result, ))

    def doSendFail(self, *args, **kwargs):
        """
        Action method.
        """
        newpacket, _ = args[0]
        p2p_service.SendFail(newpacket, wide=True)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _PacketLogFileEnabled
        _PacketLogFileEnabled = False
        self.acks.clear()
        for idurl in list(self.routes.keys()):
            self._do_unregister_route(idurl)
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        if network_connector.A():
            network_connector.A().removeStateChangedCallback(self._on_network_connector_state_changed)
        callback.remove_inbox_callback(self._on_first_inbox_packet_received)
        callback.remove_finish_file_sending_callback(self._on_finish_file_sending)
        self.destroy()
        global _ProxyRouter
        del _ProxyRouter
        _ProxyRouter = None

    def _get_session_proto_host(self, sender_idurl, info=None):
        route_info = self.routes.get(sender_idurl.original(), None)
        if not route_info:
            route_info = self.routes.get(sender_idurl.to_bin(), None)
        if not route_info:
            lg.warn('route with %s was not found, can not send Relay packet' % sender_idurl)
            return None, None
        connection_info = route_info.get('connection_info', {})
        active_user_session_machine = None
        if info is not None and not connection_info or not connection_info.get('index'):
            active_user_sessions = gateway.find_active_session(info.proto, idurl=sender_idurl.original())
            if not active_user_sessions:
                active_user_sessions = gateway.find_active_session(info.proto, idurl=sender_idurl.to_bin())
            if not active_user_sessions:
                lg.err('route with %s found but no active sessions found with %s://%s, can not send Relay packet' % (
                    sender_idurl, info.proto, info.host, ))
                return None, None
            active_user_session_machine = automat.objects().get(active_user_sessions[0].index, None)
        if not active_user_session_machine:
            if connection_info.get('index'):
                active_user_session_machine = automat.objects().get(connection_info['index'], None)
        if not active_user_session_machine:
            lg.warn('route with %s found but no active user session, can not send Relay packet' % sender_idurl)
            return None, None
        if not active_user_session_machine.is_connected():
            lg.warn('route with %s found but session is not connected, can not send Relay packet' % sender_idurl)
            return None, None
        hosts = []
        try:
            hosts.append((active_user_session_machine.get_proto(), active_user_session_machine.get_host(), ))
        except:
            lg.exc()
        if not hosts:
            lg.warn('found active user session but host is empty in %r, try use recorded info' % active_user_session_machine)
            hosts = route_info['address']
        if len(hosts) == 0:
            lg.warn('route with %s do not have actual info about the host, use identity contacts instead' % sender_idurl)
            hosts = route_info['contacts']
        if len(hosts) == 0:
            lg.warn('has no known contacts for route with %s, can not send Relay packet' % sender_idurl)
            return None, None
        if len(hosts) > 1:
            lg.warn('found more then one channel with %s : %r' % (sender_idurl, hosts, ))
        receiver_proto, receiver_host = strng.to_bin(hosts[0][0]), strng.to_bin(hosts[0][1])
        if _Debug:
            lg.args(_DebugLevel, proto=receiver_proto, host=receiver_host, user_session=active_user_session_machine)
        return receiver_proto, receiver_host

    def _do_process_request(self, *args, **kwargs):
        global _MaxRoutesNumber
        json_payload, request, info = args[0]
        user_idurl = request.CreatorID
        #--- commands.RequestService()
        if request.Command == commands.RequestService():
            if len(self.routes) >= _MaxRoutesNumber:
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_server.doProcessRequest RequestService rejected: too many routes')
                p2p_service.SendAck(request, 'rejected', wide=True)
            else:
                try:
                    idsrc = json_payload['identity']
                    cached_ident = identity.identity(xmlsrc=idsrc)
                except:
                    lg.out(_DebugLevel, 'payload: [%s]' % request.Payload)
                    lg.exc()
                    return
                if not cached_ident.Valid():
                    lg.warn('incoming identity is not valid')
                    return
                if not cached_ident.isCorrect():
                    lg.warn('incoming identity is not correct')
                    return
                if user_idurl.original() != cached_ident.getIDURL().original():
                    lg.warn('incoming identity is not belong to request packet creator: %r != %r' % (
                        user_idurl.original(), cached_ident.getIDURL().original()))
                    return
                identitycache.UpdateAfterChecking(cached_ident.getIDURL().original(), idsrc)
                oldnew = ''
                if user_idurl.original() not in list(self.routes.keys()) and user_idurl.to_bin() not in list(self.routes.keys()):
                    # accept new route
                    oldnew = 'NEW'
                    self.routes[user_idurl.original()] = {}
                else:
                    # accept existing routed user
                    oldnew = 'OLD'
                if not self._is_my_contacts_present_in_identity(cached_ident):
                    if _Debug:
                        lg.out(_DebugLevel, '    DO OVERRIDE identity for %s' % user_idurl)
                    identitycache.OverrideIdentity(user_idurl, cached_ident.serialize())
                else:
                    if _Debug:
                        lg.out(_DebugLevel, '        SKIP OVERRIDE identity for %s' % user_idurl)
                self.routes[user_idurl.original()]['time'] = time.time()
                self.routes[user_idurl.original()]['identity'] = cached_ident.serialize(as_text=True)
                self.routes[user_idurl.original()]['identity_rev'] = cached_ident.getRevisionValue()
                self.routes[user_idurl.original()]['publickey'] = strng.to_text(cached_ident.publickey)
                self.routes[user_idurl.original()]['contacts'] = cached_ident.getContactsAsTuples(as_text=True)
                self.routes[user_idurl.original()]['address'] = []
                self.routes[user_idurl.original()]['connection_info'] = None
                self.closed_routes.pop(user_idurl.original(), None)
                self.closed_routes.pop(user_idurl.to_bin(), None)
                active_user_sessions = gateway.find_active_session(info.proto, info.host)
                if not active_user_sessions:
                    active_user_sessions = gateway.find_active_session(info.proto, idurl=user_idurl.original())
                if not active_user_sessions:
                    active_user_sessions = gateway.find_active_session(info.proto, idurl=user_idurl.to_bin())
                if active_user_sessions:
                    user_connection_info = {
                        'id': active_user_sessions[0].id,
                        'index': active_user_sessions[0].index,
                        'proto': info.proto,
                        'host': info.host,
                        'idurl': user_idurl,
                    }
                    active_user_session_machine = automat.objects().get(user_connection_info['index'], None)
                    if active_user_session_machine:
                        self.routes[user_idurl.original()]['connection_info'] = user_connection_info
                        active_user_session_machine.addStateChangedCallback(
                            cb=lambda oldstate, newstate, event_string, *args, **kwargs:
                                self._on_user_session_disconnected(user_idurl.original(), oldstate, newstate, event_string, *args, **kwargs),
                            oldstate='CONNECTED',
                            callback_id='proxy_router',
                        )
                        lg.info('connected %s routed user %r and set active session: %r' % (oldnew.upper(), user_idurl, active_user_session_machine))
                    else:
                        lg.err('not found session state machine by index %s' % user_connection_info['index'])
                else:
                    if _Debug:
                        lg.dbg(_DebugLevel, 'active connection with user %s at %s:%s not yet exist' % (
                            user_idurl.original(), info.proto, info.host, ))
                        lg.dbg(_DebugLevel, 'current active sessions: %d' % len(gateway.list_active_sessions(info.proto)))
                out_ack = p2p_service.SendAck(request, 'accepted', wide=True)
                if out_ack.PacketID in self.acks:
                    raise Exception('Ack() already sent: %r' % out_ack.PacketID)
                self.acks[out_ack.PacketID] = out_ack.RemoteID
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_server.doProcessRequest !!!!!!! ACCEPTED %s ROUTE for %r  contacts=%s' % (
                        oldnew.upper(), user_idurl, self.routes.get(user_idurl.original(), {}).get('contacts'), ))
        #--- commands.CancelService()
        elif request.Command == commands.CancelService():
            if user_idurl.original() in list(self.routes.keys()) or user_idurl.to_bin() in list(self.routes.keys()):
                # cancel existing route
                active_user_session_machine_index = self.routes.get(user_idurl.original(), {}).get('connection_info', {}).get('index', None)
                if active_user_session_machine_index is None:
                    active_user_session_machine_index = self.routes.get(user_idurl.to_bin(), {}).get('connection_info', {}).get('index', None)
                if active_user_session_machine_index is not None:
                    active_user_session_machine = automat.objects().get(active_user_session_machine_index, None)
                    if active_user_session_machine is not None:
                        active_user_session_machine.removeStateChangedCallback(callback_id='proxy_router')
                self.routes.pop(user_idurl.original(), None)
                self.routes.pop(user_idurl.to_bin(), None)
                self.closed_routes[user_idurl.original()] = time.time()
                self.closed_routes[user_idurl.to_bin()] = time.time()
                identitycache.StopOverridingIdentity(user_idurl.original())
                identitycache.StopOverridingIdentity(user_idurl.to_bin())
                p2p_service.SendAck(request, 'accepted', wide=True)
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_server.doProcessRequest !!!!!!! CANCELLED ROUTE for %r' % user_idurl.original())
            else:
                p2p_service.SendAck(request, 'rejected', wide=True)
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_server.doProcessRequest CancelService rejected : %r is not found in routes' % user_idurl.original())
                    lg.out(_DebugLevel, '    %r' % self.routes)
        else:
            p2p_service.SendFail(request, 'rejected', wide=True)

    def _do_forward_inbox_packet(self, *args, **kwargs):
        # encrypt with proxy_receiver()'s key and sent to man behind my proxy
        receiver_idurl, newpacket, info = args[0]
        receiver_idurl = id_url.field(receiver_idurl)
        route_info = self.routes.get(receiver_idurl.original(), None)
        if not route_info:
            route_info = self.routes.get(receiver_idurl.to_bin(), None)
        if _Debug:
            lg.args(_DebugLevel, newpacket=newpacket, info=info, receiver_idurl=receiver_idurl, route_info=route_info)
        if not route_info:
            lg.warn('route with %s not found for inbox packet: %s' % (receiver_idurl, newpacket))
            return
        connection_info = route_info.get('connection_info', {})
        active_user_session_machine = None
        if not connection_info or not connection_info.get('index'):
            active_user_sessions = gateway.find_active_session(info.proto, idurl=receiver_idurl.original())
            if not active_user_sessions:
                active_user_sessions = gateway.find_active_session(info.proto, idurl=receiver_idurl.to_bin())
            if not active_user_sessions:
                lg.warn('route with %s found but no active sessions found with %s://%s, fire "routed-session-disconnected" event' % (
                    receiver_idurl, info.proto, info.host, ))
                self.automat('routed-session-disconnected', receiver_idurl)
                return
            user_connection_info = {
                'id': active_user_sessions[0].id,
                'index': active_user_sessions[0].index,
                'proto': info.proto,
                'host': info.host,
                'idurl': receiver_idurl,
            }
            active_user_session_machine = automat.objects().get(user_connection_info['index'], None)
            if active_user_session_machine:
                if receiver_idurl.original() in self.routes:
                    self.routes[receiver_idurl.original()]['connection_info'] = user_connection_info
                    lg.info('found and remember active connection info: %r' % user_connection_info)
                if receiver_idurl.to_bin() in self.routes:
                    self.routes[receiver_idurl.to_bin()]['connection_info'] = user_connection_info
                    lg.info('found and remember active connection info (for latest IDURL): %r' % user_connection_info)
        if not active_user_session_machine:
            if connection_info.get('index'):
                active_user_session_machine = automat.objects().get(connection_info['index'], None)
        if not active_user_session_machine:
            lg.warn('route with %s found but no active user session, fire "routed-session-disconnected" event' % receiver_idurl)
            self.automat('routed-session-disconnected', receiver_idurl)
            return
        if not active_user_session_machine.is_connected():
            lg.warn('route with %s found but session is not connected, fire "routed-session-disconnected" event' % receiver_idurl)
            self.automat('routed-session-disconnected', receiver_idurl)
            return
        hosts = []
        try:
            hosts.append((active_user_session_machine.get_proto(), active_user_session_machine.get_host(), ))
        except:
            lg.exc()
        if not hosts:
            lg.warn('found active user session but host is empty in %r, try use recorded info' % active_user_session_machine)
            hosts = route_info['address']
        if len(hosts) == 0:
            lg.warn('route with %s do not have actual info about the host, use identity contacts instead' % receiver_idurl)
            hosts = route_info['contacts']
        if len(hosts) == 0:
            lg.warn('has no known contacts for route with %s' % receiver_idurl)
            self.automat('routed-session-disconnected', receiver_idurl)
            return
        if len(hosts) > 1:
            lg.warn('found more then one channel with receiver %s : %r' % (receiver_idurl, hosts, ))
        receiver_proto, receiver_host = strng.to_bin(hosts[0][0]), strng.to_bin(hosts[0][1])
        #--- route is healthy, sending forward incoming routed packet
        raw_data, pout = self._do_send_relay_packet(
            relay_cmd=commands.RelayIn(),
            inbox_packet=newpacket,
            data=newpacket.Serialize(),
            publickey=route_info['publickey'],
            receiver_idurl=receiver_idurl,
            receiver_proto=receiver_proto,
            receiver_host=receiver_host,
            failed_callback=lambda pkt_out, msg: self._on_routed_in_packet_failed(pkt_out, msg, newpacket, info, receiver_idurl)
        )
        if _Debug:
            lg.out(_DebugLevel, '<<<Route-IN %s %s:%s' % (
                str(newpacket), strng.to_text(info.proto), strng.to_text(info.host),))
            lg.out(_DebugLevel, '           sent to %s://%s with %d bytes in %s' % (
                strng.to_text(receiver_proto), strng.to_text(receiver_host), len(raw_data), pout))
        active_user_session_machine = None
        del raw_data
        del pout

    def _do_set_contacts_override(self, *args, **kwargs):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router.doSetContactsOverride identity for %s' % args[0].CreatorID)
        user_idurl = args[0].CreatorID
        idsrc = args[0].Payload
        try:
            new_ident = identity.identity(xmlsrc=idsrc)
        except:
            lg.out(_DebugLevel, 'payload: [%s]' % idsrc)
            lg.exc()
            return
        if not new_ident.isCorrect() or not new_ident.Valid():
            lg.warn('incoming identity is not valid')
            return
        current_overridden_identity = identitycache.ReadOverriddenIdentityXMLSource(user_idurl)
        try:
            current_contacts = identity.identity(xmlsrc=current_overridden_identity).getContacts()
        except:
            current_contacts = []
        identitycache.StopOverridingIdentity(user_idurl)
        result = identitycache.OverrideIdentity(args[0].CreatorID, idsrc)
        if _Debug:
            lg.out(_DebugLevel, '    current overridden contacts is : %s' % current_contacts)
            lg.out(_DebugLevel, '    new override contacts will be : %s' % new_ident.getContacts())
            lg.out(_DebugLevel, '    result=%s' % result)

    def _do_forward_outbox_packet(self, outpacket_info_tuple):
        """
        This packet addressed to me but contain routed data to be transferred to another node.
        I will decrypt with my private key and send to outside world further.
        """
        newpacket, info = outpacket_info_tuple
        if _Debug:
            lg.args(_DebugLevel, newpacket=newpacket, info=info)
        block = encrypted.Unserialize(newpacket.Payload)
        if block is None:
            lg.err('failed reading data from %s' % newpacket.RemoteID)
            return
        inpt = None
        try:
            session_key = key.DecryptLocalPrivateKey(block.EncryptedSessionKey)
            padded_data = key.DecryptWithSessionKey(session_key, block.EncryptedData, session_key_type=block.SessionKeyType)
            inpt = BytesIO(padded_data[:int(block.Length)])
            # see proxy_sender.ProxySender : _on_first_outbox_packet() for sending part
            json_payload = serialization.BytesToDict(inpt.read(), keys_to_text=True)
            inpt.close()
            sender_idurl = strng.to_bin(json_payload['f'])   # from
            receiver_idurl = strng.to_bin(json_payload['t']) # to
            wide = json_payload['w']                         # wide
            routed_data = json_payload['p']                  # payload
            response_timeout = json_payload.get('i', None)
            keep_alive = json_payload.get('a', False)
            is_retry = json_payload.get('r', False)
        except:
            lg.err('failed reading data from %s' % newpacket.RemoteID)
            lg.exc()
            try:
                inpt.close()
            except:
                pass
            return
        del session_key
        del padded_data
        del inpt
        del block
        if identitycache.HasKey(sender_idurl) and identitycache.HasKey(receiver_idurl) and not is_retry:
            return self._do_verify_routed_data(newpacket, info, sender_idurl, receiver_idurl, routed_data, wide, response_timeout, keep_alive, is_retry)
        lg.warn('will send routed data after caching, is_retry=%s sender_idurl=%r receiver_idurl=%r' % (is_retry, sender_idurl, receiver_idurl, ))
        dl = []
        if not identitycache.HasKey(sender_idurl) or is_retry:
            dl.append(identitycache.immediatelyCaching(sender_idurl))
        if not identitycache.HasKey(receiver_idurl) or is_retry:
            dl.append(identitycache.immediatelyCaching(receiver_idurl))
        d = DeferredList(dl, consumeErrors=True)
        d.addCallback(self._do_check_cached_idurl, newpacket, info, sender_idurl, receiver_idurl, routed_data, wide, response_timeout, keep_alive, is_retry)
        if _Debug:
            d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='_do_forward_outbox_packet')
        d.addErrback(lambda err: self._do_verify_routed_data(newpacket, info, None, None, routed_data, wide, response_timeout, keep_alive, is_retry))
        return True

    def _do_check_cached_idurl(self, cache_results, newpacket, info, sender_idurl, receiver_idurl, routed_data, wide, response_timeout, keep_alive, is_retry):
        sender_id_rev = self.routes.get(sender_idurl, {}).get('identity_rev', None)
        receiver_id_rev = self.routes.get(receiver_idurl, {}).get('identity_rev', None)
        if _Debug:
            lg.args(_DebugLevel, sender_id_rev=sender_id_rev, receiver_id_rev=receiver_id_rev, is_retry=is_retry, cache_results=len(cache_results))
        some_failed = False
        for result, _ in cache_results:
            if not result:
                some_failed = True
        route_changed = False
        if sender_idurl in self.routes:
            sender_ident = identitydb.get_ident(sender_idurl)
            if sender_ident and sender_id_rev is not None and sender_id_rev != sender_ident.getRevisionValue():
                route_changed = True
                self.routes[sender_idurl]['identity_rev'] = sender_ident.getRevisionValue()
                self.closed_routes.pop(sender_idurl, None)
        if receiver_idurl in self.routes:
            receiver_ident = identitydb.get_ident(receiver_idurl)
            if receiver_ident and receiver_id_rev is not None and receiver_id_rev != receiver_ident.getRevisionValue():
                route_changed = True
                self.routes[receiver_idurl]['identity_rev'] = receiver_ident.getRevisionValue()
                self.closed_routes.pop(receiver_idurl, None)
        if some_failed:
            self._do_verify_routed_data(newpacket, info, None, None, routed_data, wide, response_timeout, keep_alive, is_retry, route_changed)
        else:
            self._do_verify_routed_data(newpacket, info, sender_idurl, receiver_idurl, routed_data, wide, response_timeout, keep_alive, is_retry, route_changed)
        return None

    def _do_verify_routed_data(self, newpacket, info, sender_idurl, receiver_idurl, routed_data, wide, response_timeout, keep_alive, is_retry, route_changed=False):
        if sender_idurl is None or receiver_idurl is None:
            lg.warn('failed sending %r, sender or receiver IDURL was not cached' % newpacket)
            self._do_send_fail_packet(newpacket, info, wide, response_timeout, keep_alive, newpacket.CreatorID, receiver_idurl, 'sender or receiver IDURL was not found')
            return
        # those must be already cached
        sender_idurl = id_url.field(sender_idurl)
        receiver_idurl = id_url.field(receiver_idurl)
        route = self.routes.get(sender_idurl.original(), None)
        if not route:
            route = self.routes.get(sender_idurl.to_bin(), None)
        #--- route not exist
        if not route:
            lg.warn('route with %s not exist' % (sender_idurl))
            self._do_send_fail_packet(newpacket, info, wide, response_timeout, keep_alive, sender_idurl, receiver_idurl, 'route not exist')
            return
        routes_keys = list(self.routes.keys())
        closed_route_keys = list(self.closed_routes.keys())
        if _Debug:
            lg.args(_DebugLevel, newpacket=newpacket, info=info, sender_idurl=sender_idurl,
                    receiver_idurl=receiver_idurl, route_contacts=route['contacts'],
                    closed_routes=closed_route_keys, is_retry=is_retry, route_changed=route_changed)
        routed_packet = signed.Unserialize(routed_data)
        #--- invalid packet
        if not routed_packet:
            lg.err('failed to unserialize incoming packet from %s' % newpacket.RemoteID)
            self._do_send_fail_packet(newpacket, info, wide, response_timeout, keep_alive, sender_idurl, receiver_idurl, 'invalid packet')
            return
        routed_command = routed_packet.Command
        routed_packet_id = routed_packet.PacketID
        routed_remote_id = routed_packet.RemoteID
        try:
            is_signature_valid = routed_packet.Valid(raise_signature_invalid=False)
        except:
            is_signature_valid = False
        #--- signature invalid
        if not is_signature_valid:
            lg.err('new packet from %s is NOT VALID:\n\n%r\n\n\n%r\n' % (
                sender_idurl, routed_data, routed_packet.Serialize()))
            self._do_send_fail_packet(newpacket, info, wide, response_timeout, keep_alive, sender_idurl, receiver_idurl, 'signature invalid')
            return
        #--- packet addressed to me
        if receiver_idurl.to_bin() == my_id.getLocalID().to_bin():
            if _Debug:
                lg.out(_DebugLevel, '        proxy_router() passing by INCOMING packet %r from %s to me' % (
                    routed_packet, sender_idurl))
            # node A sending routed data but I am the actual recipient, so need to handle the packet right away
            packet_in.process(routed_packet, info)
            return
        #--- route already closed
        if False:
        # if receiver_idurl.original() in closed_route_keys or receiver_idurl.to_bin() in closed_route_keys:
        # if not route_changed and ( receiver_idurl.original() in closed_route_keys or receiver_idurl.to_bin() in closed_route_keys ):
            route_closed_time = max(self.closed_routes.get(receiver_idurl.original(), 0), self.closed_routes.get(receiver_idurl.to_bin(), 0))
            if _Debug:
                lg.args(_DebugLevel, route_closed_time=route_closed_time, time=time.time())
            if time.time() - route_closed_time < 900:
                # route was closed but just recently - can not send outgoing data
                lg.err('can not send routed data, route with %s already closed' % (receiver_idurl))
                self._do_send_fail_packet(routed_packet, info, wide, response_timeout, keep_alive, sender_idurl, receiver_idurl, 'route already closed')
                return
        #--- routed-inbox-packet-received
        if receiver_idurl.original() in routes_keys or receiver_idurl.to_bin() in routes_keys:
            # if both node A and node B are behind my proxy I need to send routed packet directly to B
            if _Debug:
                lg.out(_DebugLevel, '        proxy_router() ROUTED (same router) packet %s from %s to %s' % (
                    routed_packet, sender_idurl, receiver_idurl))
            self.event('routed-inbox-packet-received', (receiver_idurl, routed_packet, info))
            return
        #--- forward outgoing routed packet
        # send the packet directly to target user
        # do not pass callbacks, because all response packets from this call will be also re-routed
        pout = packet_out.create(
            routed_packet,
            wide=wide,
            callbacks={
                'item-failed': lambda pkt_out, out_info: self._on_routed_out_packet_failed(
                    pkt_out, out_info.status, newpacket, info, sender_idurl, routed_command, routed_packet_id, routed_remote_id, wide, response_timeout, keep_alive,
                ),
                'item-sent': lambda pkt_out, out_info: self._on_routed_out_packet_sent(
                    pkt_out, out_info.status, newpacket, info, sender_idurl, routed_command, routed_packet_id, routed_remote_id, wide, response_timeout, keep_alive,
                ),
            },
            target=receiver_idurl,
            response_timeout=response_timeout,
            keep_alive=keep_alive,
            skip_ack=True,
        )
        if _Debug:
            lg.out(_DebugLevel, '>>>Route-OUT %d bytes from %s at %s://%s :' % (
                len(routed_data), nameurl.GetName(sender_idurl), strng.to_text(info.proto), strng.to_text(info.host),))
            lg.out(_DebugLevel, '    routed to %s : %s' % (nameurl.GetName(receiver_idurl), pout))
        if _PacketLogFileEnabled:
            lg.out(0, '                \033[0;49;36mROUTE OUT %s(%s) %s %s for %s forwarded to %s\033[0m' % (
                routed_packet.Command, routed_packet.PacketID,
                global_id.UrlToGlobalID(routed_packet.OwnerID),
                global_id.UrlToGlobalID(routed_packet.CreatorID),
                global_id.UrlToGlobalID(routed_packet.RemoteID),
                global_id.UrlToGlobalID(receiver_idurl),
            ), log_name='packet', showtime=True)
        del routed_data
        del route
        del routed_packet

    def _do_send_fail_packet(self, newpacket, info, wide, response_timeout, keep_alive, sender_idurl, receiver_idurl, error):
        if _Debug:
            lg.args(_DebugLevel, error=error, newpacket=newpacket, sender_idurl=sender_idurl, receiver_idurl=receiver_idurl)
        publickey = identitycache.GetPublicKey(newpacket.CreatorID)
        if not publickey:
            lg.err('%r : but can not send RelayFail(), identity %r is not cached' % (error, newpacket.CreatorID, ))
            return
        receiver_proto, receiver_host = self._get_session_proto_host(sender_idurl, info)
        raw_data, pout = self._do_send_relay_packet(
            relay_cmd=commands.RelayFail(),
            inbox_packet=newpacket,
            data=serialization.DictToBytes({
                'command': newpacket.Command,
                'packet_id': newpacket.PacketID,
                'from': sender_idurl,
                'to': receiver_idurl,
                'error': error,
                'wide': wide,
                'response_timeout': response_timeout,
                'keep_alive': keep_alive,
            }),
            publickey=publickey,
            receiver_idurl=sender_idurl,
            receiver_proto=receiver_proto,
            receiver_host=receiver_host,
            error=error,
        )
        if _Debug:
            lg.out(_DebugLevel, '<<<Route-FAIL %s from %s:%s   sent to %s://%s with %d bytes in %s' % (
                str(newpacket), strng.to_text(info.proto), strng.to_text(info.host),
                strng.to_text(info.proto), strng.to_text(info.host), len(raw_data), pout, ))
        del raw_data
        del pout

    def _do_send_relay_packet(self, relay_cmd, inbox_packet, data, publickey, receiver_idurl, receiver_proto=None, receiver_host=None, failed_callback=None, error=None):
        if _Debug:
            lg.args(_DebugLevel, relay_cmd=relay_cmd, inbox_packet=inbox_packet, receiver_idurl=receiver_idurl, receiver_proto=receiver_proto, receiver_host=receiver_host)
        block = encrypted.Block(
            CreatorID=my_id.getLocalID(),
            BackupID='routed incoming data',
            BlockNumber=0,
            SessionKey=key.NewSessionKey(session_key_type=key.SessionKeyType()),
            SessionKeyType=key.SessionKeyType(),
            LastBlock=True,
            Data=data,
            EncryptKey=lambda inp: key.EncryptOpenSSHPublicKey(publickey, inp),
        )
        raw_data = block.Serialize()
        routed_packet = signed.Packet(
            Command=relay_cmd,
            OwnerID=inbox_packet.OwnerID,
            CreatorID=my_id.getLocalID(),
            PacketID=inbox_packet.PacketID,
            Payload=raw_data,
            RemoteID=receiver_idurl,
        )
        cbs = {}
        if failed_callback is not None:
            cbs = {
                'failed': failed_callback,
            }
        route = {
            'packet': routed_packet,
            'remoteid': receiver_idurl,
            'description': ('%s_%s[%s]_%s' % (
                relay_cmd, inbox_packet.Command, inbox_packet.PacketID,
                nameurl.GetName(receiver_idurl))),
        }
        if receiver_proto is not None and receiver_host is not None:
            route['proto'] = receiver_proto
            route['host'] = receiver_host
        pout = packet_out.create(
            inbox_packet,
            wide=False,
            callbacks=cbs,
            route=route,
            skip_ack=True,
        )
        if _PacketLogFileEnabled:
            label = relay_cmd.upper().replace('RELAY', 'ROUTE ')
            reason = error if relay_cmd == commands.RelayFail() else ''
            lg.out(0, '                \033[0;49;32m%s %s(%s) %s %s for %s forwarded to %s at %s://%s %s\033[0m' % (
                label,
                inbox_packet.Command, inbox_packet.PacketID,
                global_id.UrlToGlobalID(inbox_packet.OwnerID),
                global_id.UrlToGlobalID(inbox_packet.CreatorID),
                global_id.UrlToGlobalID(inbox_packet.RemoteID),
                global_id.UrlToGlobalID(receiver_idurl),
                strng.to_text(receiver_proto), strng.to_text(receiver_host),
                reason,
            ), log_name='packet', showtime=True)
        del block
        del routed_packet
        return raw_data, pout

    def _do_unregister_route(self, idurl):
        idurl = id_url.field(idurl)
        if _Debug:
            lg.args(_DebugLevel, idurl=idurl)
        active_user_session_machine_index = ((self.routes.get(idurl.original()) or {}).get('connection_info') or {}).get('index', None)
        if active_user_session_machine_index is None:
            active_user_session_machine_index = ((self.routes.get(idurl.to_bin()) or {}).get('connection_info') or {}).get('index', None)
        if active_user_session_machine_index is not None:
            active_user_session_machine = automat.objects().get(active_user_session_machine_index, None)
            if active_user_session_machine is not None:
                active_user_session_machine.removeStateChangedCallback(callback_id='proxy_router')
                lg.info('removed "proxy_router" callback from active user session %r' % active_user_session_machine)
        identitycache.StopOverridingIdentity(idurl.original())
        self.routes.pop(idurl.original(), None)
        self.routes.pop(idurl.to_bin(), None)
        self.closed_routes[idurl.original()] = time.time()
        self.closed_routes[idurl.to_bin()] = time.time()

    def _on_routed_in_packet_failed(self, pkt_out, msg, newpacket, info, receiver_idurl):
        lg.err('routed packet transfer failed: %r %r %r %r %r' % ( pkt_out, msg, newpacket, info, receiver_idurl))
        p2p_service.SendFail(newpacket, 'routed packet transfer failed', remote_idurl=newpacket.CreatorID)

    def _on_routed_out_packet_sent(self, pkt_out, msg, newpacket, info, sender_idurl, routed_command, routed_packet_id, routed_remote_id, wide, response_timeout, keep_alive):
        if _Debug:
            lg.args(_DebugLevel, pkt_out=pkt_out, msg=msg, newpacket=newpacket, sender_idurl=sender_idurl,
                    routed_command=routed_command, routed_packet_id=routed_packet_id, routed_remote_id=routed_remote_id)
        publickey = identitycache.GetPublicKey(newpacket.CreatorID)
        if not publickey:
            lg.err('routed packet sent but can not send RelayAck(), identity %r is not cached' % newpacket.CreatorID)
            return
        receiver_proto, receiver_host = self._get_session_proto_host(sender_idurl, info)
        raw_data, pout = self._do_send_relay_packet(
            relay_cmd=commands.RelayAck(),
            inbox_packet=newpacket,
            data=serialization.DictToBytes({
                'command': routed_command,
                'packet_id': routed_packet_id,
                'from': sender_idurl,
                'to': routed_remote_id,
                'error': '',
                'wide': wide,
                'response_timeout': response_timeout,
                'keep_alive': keep_alive,
            }),
            publickey=publickey,
            receiver_idurl=sender_idurl,
            receiver_proto=receiver_proto,
            receiver_host=receiver_host,
            error='',
        )
        if _Debug:
            lg.out(_DebugLevel, '<<<Route-ACK %s %s:%s' % (str(newpacket), receiver_proto, receiver_host, ))
            lg.out(_DebugLevel, '           sent to %s://%s with %d bytes in %s' % (receiver_proto, receiver_host, len(raw_data), pout))
        del raw_data
        del pout
        return None

    def _on_routed_out_packet_failed(self, pkt_out, msg, newpacket, info, sender_idurl, routed_command, routed_packet_id, routed_remote_id, wide, response_timeout, keep_alive):
        if _Debug:
            lg.args(_DebugLevel, pkt_out=pkt_out, msg=msg, newpacket=newpacket, sender_idurl=sender_idurl,
                    routed_command=routed_command, routed_packet_id=routed_packet_id, routed_remote_id=routed_remote_id)
        publickey = identitycache.GetPublicKey(newpacket.CreatorID)
        if not publickey:
            lg.err('routed packet delivery failed but can not send RelayFail(), identity %r is not cached' % newpacket.CreatorID)
            return
        receiver_proto, receiver_host = self._get_session_proto_host(sender_idurl, info)
        raw_data, pout = self._do_send_relay_packet(
            relay_cmd=commands.RelayFail(),
            inbox_packet=newpacket,
            data=serialization.DictToBytes({
                'command': routed_command,
                'packet_id': routed_packet_id,
                'from': sender_idurl,
                'to': routed_remote_id,
                'error': 'routed packet delivery failed',
                'wide': wide,
                'response_timeout': response_timeout,
                'keep_alive': keep_alive,
            }),
            publickey=publickey,
            receiver_idurl=sender_idurl,
            receiver_proto=receiver_proto,
            receiver_host=receiver_host,
            error='routed packet delivery failed',
        )
        if _Debug:
            lg.out(_DebugLevel, '<<<Route-FAIL %s %s:%s' % (str(newpacket), receiver_proto, receiver_host, ))
            lg.out(_DebugLevel, '           sent to %s://%s with %d bytes in %s' % (receiver_proto, receiver_host, len(raw_data), pout))
        del raw_data
        del pout
        return None

    def _on_first_inbox_packet_received(self, newpacket, info, status, error_message):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router._on_first_inbox_packet_received %s from %s://%s' % (newpacket, info.proto, info.host, ))
            lg.out(_DebugLevel, '    creator=%s owner=%s' % (newpacket.CreatorID.original(), newpacket.OwnerID.original(), ))
            lg.out(_DebugLevel, '    sender=%s remote_id=%s' % (info.sender_idurl, newpacket.RemoteID.original(), ))
            for k, v in self.routes.items():
                lg.out(_DebugLevel, '        route with %r :  address=%s  contacts=%s' % (k, v.get('address'), v.get('contacts'), ))
        # first filter all traffic addressed to me
        if newpacket.RemoteID == my_id.getLocalID():
            # check command type, filter Routed traffic first
            if newpacket.Command in [commands.Relay(), commands.RelayOut(), ]:
                # look like this is a routed packet from node behind my proxy addressed to someone else
                if (newpacket.CreatorID.original() in list(self.routes.keys()) or
                    newpacket.CreatorID.to_bin() in list(self.routes.keys()) or 
                    newpacket.OwnerID.original() in list(self.routes.keys()) or
                    newpacket.OwnerID.to_bin() in list(self.routes.keys())
                ):
                    # sent by proxy_sender() from node A : a man behind proxy_router()
                    # addressed to some third node B in outside world - need to route
                    # A is my consumer and B is a recipient which A wants to contact
                    if _Debug:
                        lg.out(_DebugLevel, '        sending "routed-outbox-packet-received" event')
                    self.event('routed-outbox-packet-received', (newpacket, info))
                    return True
                # looks like we do not know this guy, so why he is sending us routed traffic?
                lg.err('unknown %s from %s received, no known routes with %s' % (
                    newpacket, newpacket.CreatorID, newpacket.CreatorID))
                self.automat('unknown-packet-received', (newpacket, info))
                return True
            # and this is not a Relay packet, Identity
            elif newpacket.Command == commands.Identity():
                # this is a "propagate" packet from node A addressed to this proxy router
                if (newpacket.CreatorID.original() in list(self.routes.keys()) or
                    newpacket.CreatorID.to_bin() in list(self.routes.keys())
                ):
                    # also we need to "reset" overriden identity
                    # return False so that other services also can process that Identity()
                    if _Debug:
                        lg.out(_DebugLevel, '        sending "known-identity-received" event')
                    self.automat('known-identity-received', newpacket)
                    return False
                # this node is not yet in routers list,
                # but seems like it tries to contact me
                # return False so that other services also can process that Identity()
                if _Debug:
                    lg.out(_DebugLevel, '        sending "unknown-identity-received" event')
                self.automat('unknown-identity-received', newpacket)
                return False
            # so this packet may be of any kind, but addressed to me
            # for example if I am a supplier for node A he will send me packets in usual way
            # need to skip this packet here and process it as a normal inbox packet
            if _Debug:
                lg.out(_DebugLevel, '        proxy_router() SKIP packet %s from %s addressed to me' % (
                    newpacket, newpacket.CreatorID))
            return False
        # this packet was addressed to someone else
        # it can be different scenarios, if can not found valid scenario - must skip the packet
        receiver_idurl = None
        known_remote_id = newpacket.RemoteID.original() in list(self.routes.keys()) or newpacket.RemoteID.to_bin() in list(self.routes.keys())
        known_creator_id = newpacket.CreatorID.original() in list(self.routes.keys()) or newpacket.CreatorID.to_bin() in list(self.routes.keys())
        known_owner_id = newpacket.OwnerID.original() in list(self.routes.keys()) or newpacket.OwnerID.to_bin() in list(self.routes.keys())
        if known_remote_id:
            # incoming packet from node B addressed to node A behind that proxy, capture it!
            receiver_idurl = newpacket.RemoteID
            if _Debug:
                lg.out(_DebugLevel, '        proxy_router() ROUTED packet %s from %s to %s' % (
                    newpacket, info.sender_idurl, receiver_idurl))
            self.event('routed-inbox-packet-received', (receiver_idurl, newpacket, info))
            return True
        # unknown RemoteID...
        # Data() packets may have two cases: a new Data or response with existing Data
        # in that case RemoteID of the Data packet is not pointing to the real recipient
        # need to filter this scenario here and do workaround
        if known_creator_id or known_owner_id:
            # response from node B addressed to node A, after Retrieve() from A who owns this Data()
            # a Data packet sent by node B : a man from outside world
            # addressed to a man behind this proxy_router() - need to route to node A
            # but who is node A? Creator or Owner?
            based_on = ''
            if known_creator_id:
                receiver_idurl = newpacket.CreatorID
                based_on = 'creator'
            else:
                receiver_idurl = newpacket.OwnerID
                based_on = 'owner'
            if _Debug:
                lg.out(_DebugLevel, '        proxy_router() based on %s ROUTED packet %s from %s to %s' % (
                    based_on, newpacket, info.sender_idurl, receiver_idurl))
            self.event('routed-inbox-packet-received', (receiver_idurl, newpacket, info))
            return True
        # this packet is not related to any of the routes
        lg.err('unknown %r received, no relations found' % newpacket)
        self.automat('unknown-packet-received', (newpacket, info))
        return False

    def _on_network_connector_state_changed(self, oldstate, newstate, event, *args, **kwargs):
        if oldstate != 'CONNECTED' and newstate == 'CONNECTED':
            self.automat('network-connected')
        if oldstate != 'DISCONNECTED' and newstate == 'DISCONNECTED':
            self.automat('network-disconnected')

    def _on_finish_file_sending(self, pkt_out, item, status, size, error_message):
        if status != 'finished':
            return False
        try:
            Command = pkt_out.outpacket.Command
            RemoteID = pkt_out.outpacket.RemoteID
            PacketID = pkt_out.outpacket.PacketID
        except:
            lg.exc()
            return False
        if Command != commands.Ack():
            return False
        if RemoteID.original() not in list(self.routes.keys()) and RemoteID.to_bin() not in list(self.routes.keys()):
            return False
        found = False
        to_remove = []
        for ack_packet_id, ack_remote_idurl in self.acks.items():
            if PacketID.lower() == ack_packet_id.lower() and RemoteID == ack_remote_idurl:
                if _Debug:
                    lg.dbg(_DebugLevel, 'found outgoing Ack() packet %r to %r' % (ack_packet_id, ack_remote_idurl))
                to_remove.append(ack_packet_id)
                # TODO: clean up self.acks for un-acked requests
                self.automat('request-route-ack-sent', (RemoteID, pkt_out, item, status, size, error_message))
                found = True
        for ack_packet_id in to_remove:
            self.acks.pop(ack_packet_id)
        return found

    def _on_user_session_disconnected(self, user_id, oldstate, newstate, event_string, *args, **kwargs):
        lg.warn('user session disconnected  %r : %s->%s' % (user_id, oldstate, newstate))
        self.automat('routed-session-disconnected', user_id)

    def _on_identity_url_changed(self, evt):
        old = id_url.to_bin(evt.data['old_idurl'])
        new = id_url.to_bin(evt.data['new_idurl'])
        if old in self.routes and new not in self.routes:
            current_route = self.routes[old]
            identitycache.StopOverridingIdentity(old)
            self.routes.pop(old)
            self.routes[new] = current_route
            new_ident = identitydb.get_ident(new)
            if new_ident and not self._is_my_contacts_present_in_identity(new_ident):
                if _Debug:
                    lg.out(_DebugLevel, '    DO OVERRIDE identity for %r' % new)
                identitycache.OverrideIdentity(new, new_ident.serialize(as_text=True))
            if new_ident:
                self.routes[new]['identity_rev'] = new_ident.getRevisionValue()
            lg.info('replaced route for user after identity rotate detected : %r -> %r' % (old, new))

    def _is_my_contacts_present_in_identity(self, ident):
        for my_contact in my_id.getLocalIdentity().getContacts():
            if ident.getContactIndex(contact=my_contact) >= 0:
                if _Debug:
                    lg.out(_DebugLevel, '        found %s in identity : %s' % (my_contact, ident.getIDURL()))
                return True
        return False

    def _load_routes(self):
        # TODO: move services/proxy-server/current-routes out from settings into a separate file
        src = config.conf().getData('services/proxy-server/current-routes')
        if src is None:
            lg.warn('setting [services/proxy-server/current-routes] not exist')
            return
        try:
            dct = serialization.BytesToDict(strng.to_bin(src), keys_to_text=True, values_to_text=True)
        except:
            dct = {}
        for k, v in dct.items():
            self.routes[id_url.field(k).original()] = v
            ident = identity.identity(xmlsrc=v['identity'])
            if not self._is_my_contacts_present_in_identity(ident):
                if _Debug:
                    lg.out(_DebugLevel, '    DO OVERRIDE identity for %s' % k)
                identitycache.OverrideIdentity(k, v['identity'])
            else:
                if _Debug:
                    lg.out(_DebugLevel, '        skip overriding %s' % k)
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router._load_routes %d routes total' % len(self.routes))

    def _clear_routes(self):
        # TODO: move services/proxy-server/current-routes out from settings into a separate file
        config.conf().setData('services/proxy-server/current-routes', '{}')
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router._clear_routes')

    def _write_route(self, user_idurl):
        # TODO: move services/proxy-server/current-routes out from settings into a separate file
        src = config.conf().getData('services/proxy-server/current-routes')
        try:
            dct = serialization.BytesToDict(strng.to_bin(src), keys_to_text=True, values_to_text=True)
        except:
            dct = {}
        user_idurl_txt = strng.to_text(id_url.field(user_idurl).original())
        dct[user_idurl_txt] = self.routes[id_url.field(user_idurl).original()]
        newsrc = strng.to_text(serialization.DictToBytes(dct, keys_to_text=True, values_to_text=True))
        config.conf().setData('services/proxy-server/current-routes', newsrc)
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router._write_route %d bytes wrote' % len(newsrc))

    def _remove_route(self, user_idurl):
        # TODO: move services/proxy-server/current-routes out from settings into a separate file
        src = config.conf().getData('services/proxy-server/current-routes')
        try:
            dct = serialization.BytesToDict(strng.to_bin(src), keys_to_text=True, values_to_text=True)
        except:
            dct = {}
        user_idurl_txt = strng.to_text(id_url.field(user_idurl).original())
        if user_idurl_txt in dct:
            dct.pop(user_idurl_txt)
            newsrc = strng.to_text(serialization.DictToBytes(dct, keys_to_text=True, values_to_text=True))
            config.conf().setData('services/proxy-server/current-routes', newsrc)
            if _Debug:
                lg.out(_DebugLevel, 'proxy_router._remove_route %d bytes wrote' % len(newsrc))

#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor  # @UnresolvedImport
    reactor.callWhenRunning(A, 'init')  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable


if __name__ == "__main__":
    main()
