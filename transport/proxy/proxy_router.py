#!/usr/bin/env python
# proxy_router.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

#------------------------------------------------------------------------------

import time

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import nameurl
from lib import serialization
from lib import strng

from main import config

from crypt import key
from crypt import signed
from crypt import encrypted

from userid import identity
from userid import my_id

from contacts import identitycache
from contacts import contactsdb

from transport import callback
from transport import packet_out
from transport import gateway

from p2p import p2p_service
from p2p import commands
from p2p import network_connector

#------------------------------------------------------------------------------

_ProxyRouter = None
_MaxRoutesNumber = 20

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
        self.acks = []

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when proxy_router() state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in
        the proxy_router() but its state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python
        <http://code.google.com/p/visio2python/>`_ tool.
        """
        #---LISTEN---
        if self.state == 'LISTEN':
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
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(*args, **kwargs)
        #---TRANSPORTS?---
        elif self.state == 'TRANSPORTS?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop' or event == 'network-disconnected':
                self.state = 'STOPPED'
            elif event == 'network-connected':
                self.state = 'LISTEN'
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'start':
                self.state = 'TRANSPORTS?'
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
        self._load_routes()
        network_connector.A().addStateChangedCallback(self._on_network_connector_state_changed)
        callback.insert_inbox_callback(0, self._on_inbox_packet_received)
        callback.add_finish_file_sending_callback(self._on_finish_file_sending)

    def doProcessRequest(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_process_request(args[0])

    def doUnregisterRoute(self, *args, **kwargs):
        """
        Action method.
        """
        idurl = args[0]
        identitycache.StopOverridingIdentity(idurl)
        self.routes.pop(idurl)
        self._remove_route(idurl)

    def doUnregisterAllRouts(self, *args, **kwargs):
        """
        Action method.
        """
        for idurl in self.routes.keys():
            identitycache.StopOverridingIdentity(idurl)
        self.routes.clear()
        self._clear_routes()

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
        self.routes[idurl]['address'].append((strng.to_text(item.proto), strng.to_text(item.host), ))
        self._write_route(idurl)
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router.doSaveRouteProtoHost : active address %s://%s added for %s' % (
                item.proto, item.host, nameurl.GetName(idurl)))

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
        # gateway.remove_transport_state_changed_callback(self._on_transport_state_changed)
        if network_connector.A():
            network_connector.A().removeStateChangedCallback(self._on_network_connector_state_changed)
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        callback.remove_finish_file_sending_callback(self._on_finish_file_sending)
        self.unregister()
        global _ProxyRouter
        del _ProxyRouter
        _ProxyRouter = None

    def _do_process_request(self, *args, **kwargs):
        global _MaxRoutesNumber
        json_payload, request, info = args[0]
        user_id = request.CreatorID
        #--- commands.RequestService()
        if request.Command == commands.RequestService():
            if len(self.routes) >= _MaxRoutesNumber:
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_server.doProcessRequest RequestService rejected: too many routes')
                    lg.out(_DebugLevel, '    %r' % self.routes)
                p2p_service.SendAck(request, 'rejected', wide=True)
            else:
                try:
                    # idsrc = strng.to_bin(json_payload['identity'])
                    idsrc = json_payload['identity']
                    cached_id = identity.identity(xmlsrc=idsrc)
                except:
                    lg.out(_DebugLevel, 'payload: [%s]' % request.Payload)
                    lg.exc()
                    return
                if not cached_id.Valid():
                    lg.warn('incoming identity is not valid')
                    return
                if not cached_id.isCorrect():
                    lg.warn('incoming identity is not correct')
                    return
                if user_id != cached_id.getIDURL():
                    lg.warn('incoming identity is not belong to request packet creator')
                    return
                if contactsdb.is_supplier(user_id):
                    if _Debug:
                        lg.out(_DebugLevel, 'proxy_server.doProcessRequest RequestService rejected: this user is my supplier')
                    p2p_service.SendAck(request, 'rejected', wide=True)
                    return
                oldnew = ''
                if user_id not in list(self.routes.keys()):
                    # accept new route
                    oldnew = 'NEW'
                    self.routes[user_id] = {}
                else:
                    # accept existing routed user
                    oldnew = 'OLD'
                if not self._is_my_contacts_present_in_identity(cached_id):
                    if _Debug:
                        lg.out(_DebugLevel, '    DO OVERRIDE identity for %s' % user_id)
                    identitycache.OverrideIdentity(user_id, cached_id.serialize())
                else:
                    if _Debug:
                        lg.out(_DebugLevel, '        SKIP OVERRIDE identity for %s' % user_id)
                self.routes[user_id]['time'] = time.time()
                self.routes[user_id]['identity'] = cached_id.serialize(as_text=True)
                self.routes[user_id]['publickey'] = strng.to_text(cached_id.publickey)
                self.routes[user_id]['contacts'] = cached_id.getContactsAsTuples(as_text=True)
                self.routes[user_id]['address'] = []
                self._write_route(user_id)
                active_user_sessions = gateway.find_active_session(info.proto, info.host)
                if active_user_sessions:
                    user_connection_info = {
                        'id': active_user_sessions[0].id,
                        'index': active_user_sessions[0].index,
                        'proto': info.proto,
                        'host': info.host,
                        'idurl': user_id,
                    }
                    active_user_session_machine = automat.objects().get(user_connection_info['index'], None)
                    if active_user_session_machine:
                        active_user_session_machine.addStateChangedCallback(
                            lambda o, n, e, a: self._on_user_session_disconnected(user_id, o, n, e, a),
                            oldstate='CONNECTED',
                        )
                        if _Debug:
                            lg.out(_DebugLevel, 'proxy_server.doProcessRequest connected %s routed user, set active session: %s' % (
                                oldnew.capitalize(), user_connection_info))
                    else:
                        lg.err('not found session state machine: %s' % user_connection_info['index'])
                else:
                    if _Debug:
                        lg.out(_DebugLevel, 'proxy_server.doProcessRequest active connection with user %s at %s:%s not yet exist' % (
                            user_id, info.proto, info.host, ))
                        lg.out(_DebugLevel, '    current active sessions: %d' % len(gateway.list_active_sessions(info.proto)))
                self.acks.append(
                    p2p_service.SendAck(request, 'accepted', wide=True))
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_server.doProcessRequest !!!!!!! ACCEPTED %s ROUTE for %s  contacts=%s' % (
                        oldnew.capitalize(), user_id, self.routes[user_id]['contacts'], ))
        #--- commands.CancelService()
        elif request.Command == commands.CancelService():
            if user_id in self.routes:
                # cancel existing route
                self._remove_route(user_id)
                self.routes.pop(user_id)
                identitycache.StopOverridingIdentity(user_id)
                p2p_service.SendAck(request, 'accepted', wide=True)
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_server.doProcessRequest !!!!!!! CANCELLED ROUTE for %s' % user_id)
            else:
                p2p_service.SendAck(request, 'rejected', wide=True)
                if _Debug:
                    lg.out(_DebugLevel, 'proxy_server.doProcessRequest CancelService rejected : %s is not found in routes' % user_id)
                    lg.out(_DebugLevel, '    %r' % self.routes)
        else:
            p2p_service.SendFail(request, 'rejected', wide=True)

    def _do_forward_inbox_packet(self, *args, **kwargs):
        # encrypt with proxy_receiver()'s key and sent to man behind my proxy
        receiver_idurl, newpacket, info = args[0]
        route_info = self.routes.get(receiver_idurl, None)
        if not route_info:
            lg.warn('route with %s not found for inbox packet: %s' % (receiver_idurl, newpacket))
            return
        hosts = route_info['address']
        if len(hosts) == 0:
            lg.warn('route with %s do not have actual info about the host, use identity contacts instead' % receiver_idurl)
            hosts = route_info['contacts']
        if len(hosts) == 0:
            lg.warn('has no known contacts for route with %s' % receiver_idurl)
            return
        if len(hosts) > 1:
            lg.warn('found more then one channel with receiver %s : %r' % (receiver_idurl, hosts, ))
        receiver_proto, receiver_host = strng.to_bin(hosts[0][0]), strng.to_bin(hosts[0][1])
        publickey = route_info['publickey']
        block = encrypted.Block(
            CreatorID=my_id.getLocalID(),
            BackupID='routed incoming data',
            BlockNumber=0,
            SessionKey=key.NewSessionKey(),
            SessionKeyType=key.SessionKeyType(),
            LastBlock=True,
            Data=newpacket.Serialize(),
            EncryptKey=lambda inp: key.EncryptOpenSSHPublicKey(publickey, inp),
        )
        raw_data = block.Serialize()
        routed_packet = signed.Packet(
            commands.Relay(),
            newpacket.OwnerID,
            my_id.getLocalID(),
            newpacket.PacketID,
            raw_data,
            receiver_idurl,
        )
        pout = packet_out.create(
            newpacket,
            wide=False,
            callbacks={},
            route={
                'packet': routed_packet,
                'proto': receiver_proto,
                'host': receiver_host,
                'remoteid': receiver_idurl,
                'description': ('Relay_%s[%s]_%s' % (
                    newpacket.Command, newpacket.PacketID,
                    nameurl.GetName(receiver_idurl))),
            },
        )
        if _Debug:
            lg.out(_DebugLevel, '<<<Relay-IN-OUT %s %s:%s' % (
                str(newpacket), info.proto, info.host,))
            lg.out(_DebugLevel, '           sent to %s://%s with %d bytes in %s' % (
                receiver_proto, receiver_host, len(raw_data), pout))
        del raw_data
        del block
        del newpacket
        del routed_packet

    def _do_set_contacts_override(self, *args, **kwargs):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router.doSetContactsOverride identity for %s' % args[0].CreatorID)
        user_id = args[0].CreatorID
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
        current_overridden_identity = identitycache.ReadOverriddenIdentityXMLSource(user_id)
        try:
            current_contacts = identity.identity(xmlsrc=current_overridden_identity).getContacts()
        except:
            current_contacts = []
        identitycache.StopOverridingIdentity(user_id)
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
        block = encrypted.Unserialize(newpacket.Payload)
        if block is None:
            lg.out(2, 'proxy_router.doForwardOutboxPacket ERROR reading data from %s' % newpacket.RemoteID)
            return
        try:
            session_key = key.DecryptLocalPrivateKey(block.EncryptedSessionKey)
            padded_data = key.DecryptWithSessionKey(session_key, block.EncryptedData)
            inpt = BytesIO(padded_data[:int(block.Length)])
            # see proxy_sender.ProxySender : _on_first_outbox_packet() for sending part
            json_payload = serialization.BytesToDict(inpt.read(), keys_to_text=True)
            inpt.close()
            sender_idurl = json_payload['f']                 # from
            receiver_idurl = json_payload['t']               # to
            wide = json_payload['w']                         # wide
            routed_data = json_payload['p']                  # payload
        except:
            lg.out(2, 'proxy_router.doForwardOutboxPacket ERROR reading data from %s' % newpacket.RemoteID)
            lg.exc()
            try:
                inpt.close()
            except:
                pass
            return
        route = self.routes.get(sender_idurl, None)
        if not route:
            inpt.close()
            lg.warn('route with %s not found' % (sender_idurl))
            p2p_service.SendFail(newpacket, 'route not exist', remote_idurl=sender_idurl)
            return
        routed_packet = signed.Unserialize(routed_data)
        if not routed_packet or not routed_packet.Valid():
            lg.out(2, 'proxy_router.doForwardOutboxPacket ERROR unserialize packet from %s' % newpacket.RemoteID)
            return
        # send the packet directly to target user_id
        # we pass not callbacks because all response packets from this call will be also re-routed
        pout = packet_out.create(
            routed_packet,
            wide=wide,
            callbacks={},
            target=receiver_idurl,
        )
        if _Debug:
            lg.out(_DebugLevel, '>>>Relay-IN-OUT %d bytes from %s at %s://%s :' % (
                len(routed_data), nameurl.GetName(sender_idurl), info.proto, info.host,))
            lg.out(_DebugLevel, '    routed to %s : %s' % (nameurl.GetName(receiver_idurl), pout))
        del block
        del routed_data
        del padded_data
        del route
        del inpt
        del session_key
        del routed_packet

    def _on_outbox_packet(self):
        # TODO: if node A is my supplier need to add special case here
        # need to filter my own packets here addressed to node A but Relay packets
        # in this case we need to send packet to the real address
        # because contacts in his identity are same that my own contacts
        return None

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router._on_inbox_packet_received %s from %s://%s' % (newpacket, info.proto, info.host, ))
            lg.out(_DebugLevel, '    creator=%s owner=%s' % (newpacket.CreatorID, newpacket.OwnerID, ))
            lg.out(_DebugLevel, '    sender=%s remote_id=%s' % (info.sender_idurl, newpacket.RemoteID, ))
            for k, v in self.routes.items():
                lg.out(_DebugLevel, '        route with %s :  address=%s  contacts=%s' % (k, v.get('address'), v.get('contacts'), ))
        # first filter all traffic addressed to me
        if newpacket.RemoteID == my_id.getLocalID():
            # check command type, filter Routed traffic first
            if newpacket.Command == commands.Relay():
                # look like this is a routed packet addressed to someone else
                if newpacket.CreatorID in list(self.routes.keys()):
                    # sent by proxy_sender() from node A : a man behind proxy_router()
                    # addressed to some third node B in outside world - need to route
                    # A is my consumer and B is a recipient which A wants to contact
                    if _Debug:
                        lg.out(_DebugLevel, '        sending "routed-outbox-packet-received" event')
                    self.automat('routed-outbox-packet-received', (newpacket, info))
                    return True
                # looks like we do not know this guy, so why he is sending us routed traffic?
                lg.warn('unknown %s from %s received, no known routes with %s' % (
                    newpacket, newpacket.CreatorID, newpacket.CreatorID))
                self.automat('unknown-packet-received', (newpacket, info))
                return True
            # and this is not a Relay packet, Identity
            elif newpacket.Command == commands.Identity():
                # this is a "propagate" packet from node A addressed to this proxy router
                if newpacket.CreatorID in list(self.routes.keys()):
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
            # it can be a RequestService or CancelService packets...
#             elif newpacket.Command == commands.RequestService():
#                 self.automat(event_string, *args, **kwargs)
#                 'request-route-received'....
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
        known_remote_id = newpacket.RemoteID in list(self.routes.keys())
        known_creator_id = newpacket.CreatorID in list(self.routes.keys())
        known_owner_id = newpacket.OwnerID in list(self.routes.keys())
        if known_remote_id:
            # incoming packet from node B addressed to node A behind that proxy, capture it!
            receiver_idurl = newpacket.RemoteID
            if _Debug:
                lg.out(_DebugLevel, '        proxy_router() ROUTED packet %s from %s to %s' % (
                    newpacket, info.sender_idurl, receiver_idurl))
            self.automat('routed-inbox-packet-received', (receiver_idurl, newpacket, info))
            return True
        # uknown RemoteID...
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
            self.automat('routed-inbox-packet-received', (receiver_idurl, newpacket, info))
            return True
        # this packet is not related to any of the routes
        if _Debug:
            lg.out(_DebugLevel, '        proxy_router() SKIP packet %s from %s : no relations found' % (
                newpacket, newpacket.CreatorID))
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
        if RemoteID not in list(self.routes.keys()):
            return False
        found = False
        for ack in list(self.acks):
            if PacketID.lower() == ack.PacketID.lower() and RemoteID == ack.RemoteID:
                self.acks.remove(ack)
                # TODO: clean up self.acks for un-acked requests
                self.automat('request-route-ack-sent', (RemoteID, pkt_out, item, status, size, error_message))
                found = True
        return found

    def _on_user_session_disconnected(self, user_id, oldstate, newstate, event_string, *args, **kwargs):
        lg.warn('user session disconnected: %s->%s' % (oldstate, newstate))
        self.automat('routed-session-disconnected', user_id)

    def _is_my_contacts_present_in_identity(self, ident):
        for my_contact in my_id.getLocalIdentity().getContacts():
            if ident.getContactIndex(contact=my_contact) >= 0:
                if _Debug:
                    lg.out(_DebugLevel, '        found %s in identity : %s' % (
                        my_contact, ident.getIDURL()))
                return True
        return False

    def _load_routes(self):
        src = config.conf().getData('services/proxy-server/current-routes')
        if src is None:
            lg.warn('setting [services/proxy-server/current-routes] not exist')
            return
        try:
            dct = serialization.BytesToDict(strng.to_bin(src), keys_to_text=True, values_to_text=True)
        except:
            dct = {}
        for k, v in dct.items():
            self.routes[strng.to_bin(k)] = v
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
        config.conf().setData('services/proxy-server/current-routes', '{}')
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router._clear_routes')

    def _write_route(self, user_id):
        src = config.conf().getData('services/proxy-server/current-routes')
        try:
            dct = serialization.BytesToDict(strng.to_bin(src), keys_to_text=True, values_to_text=True)
        except:
            dct = {}
        dct[user_id] = self.routes[user_id]
        newsrc = strng.to_text(serialization.DictToBytes(dct, keys_to_text=True, values_to_text=True))
        config.conf().setData('services/proxy-server/current-routes', newsrc)
        if _Debug:
            lg.out(_DebugLevel, 'proxy_router._write_route %d bytes wrote' % len(newsrc))

    def _remove_route(self, user_id):
        src = config.conf().getData('services/proxy-server/current-routes')
        try:
            dct = serialization.BytesToDict(strng.to_bin(src), keys_to_text=True, values_to_text=True)
        except:
            dct = {}
        if user_id in dct:
            dct.pop(user_id)
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
