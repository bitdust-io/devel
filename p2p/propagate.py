#!/usr/bin/python
# propagate.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (propagate.py) is part of BitDust Software.
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
#
#
#
#

"""
.. module:: propagate.

.. role:: red

When a user starts up he needs to run the stun.py to check what his IP is,
and if it has changed he needs to generate a new identity and send it to
his identity server and all of his contacts.

We also just request new copies of all identities from their servers when
we start up. This is simple and effective.

We should try contacting each contact every hour and if we have not been
able to contact them in 2 or 3 hours then fetch copy of identity from
their server.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------


import os
import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in propagate.py')

from twisted.internet.defer import DeferredList, Deferred

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from lib import nameurl
from lib import net_misc
from lib import strng

from contacts import contactsdb
from contacts import identitycache

from userid import known_servers
from userid import my_id

from p2p import commands
from p2p import p2p_stats

from main import settings

from system import tmpfile

from crypt import signed

from transport import gateway
from transport import packet_out

from dht import dht_records

#------------------------------------------------------------------------------

_SlowSendIsWorking = False

#------------------------------------------------------------------------------


def init():
    """
    Need to call that at start up to link with transport_control.
    """
    lg.out(4, "propagate.init ")
    # callback.add_finish_file_sending_callback(OnFileSent)


def shutdown():
    """
    """
    lg.out(4, "propagate.shutdown")

#------------------------------------------------------------------------------


def propagate(selected_contacts, AckHandler=None, wide=False):
    """
    Run the "propagate" process.

    First need to fetch ``selected_contacts`` IDs from id server. And
    then send our Identity file to that contacts.
    """
    lg.out(6, "propagate.propagate to %d contacts" % len(selected_contacts))
    d = Deferred()

    def contacts_fetched(x):
        lg.out(6, "propagate.propagate.contacts_fetched")
        SendToIDs(selected_contacts, ack_handler=AckHandler, wide=wide)
        d.callback(list(selected_contacts))
        return x
    fetch(selected_contacts).addBoth(contacts_fetched)
    return d


def fetch(list_ids):
    """
    Request a list of identity files.
    """
    lg.out(6, "propagate.fetch %d identities" % len(list_ids))
    dl = []
    for url in list_ids:
        if not url:
            continue
        if identitycache.FromCache(url):
            continue
        dl.append(identitycache.scheduleForCaching(url))
    return DeferredList(dl, consumeErrors=True)


def start(AckHandler=None, wide=False):
    """
    Call ``propagate()`` for all known contacts.
    """
    lg.out(6, 'propagate.start')
    return propagate(contactsdb.contacts_remote(), AckHandler, wide)


def suppliers(AckHandler=None, wide=False, customer_idurl=None):
    """
    Call ``propagate()`` for all suppliers.
    """
    lg.out(6, 'propagate.suppliers')
    return propagate(contactsdb.suppliers(customer_idurl=customer_idurl), AckHandler, wide)


def customers(AckHandler=None, wide=False):
    """
    Call ``propagate()`` for all known customers.
    """
    lg.out(6, 'propagate.customers')
    return propagate(contactsdb.customers(), AckHandler, wide)


def allcontacts(AckHandler=None, wide=False):
    """
    Call ``propagate()`` for all contacts and correspondents, almost the same
    to ``start()``.
    """
    lg.out(6, 'propagate.allcontacts')
    return propagate(contactsdb.contacts_full(), AckHandler, wide)


def single(idurl, ack_handler=None, wide=False, fail_handler=None):
    """
    Do "propagate" for a single contact.
    """
    d = FetchSingle(idurl)
    d.addCallback(lambda x: SendToIDs([idurl, ], ack_handler=ack_handler, wide=wide))
    if ack_handler:
        d.addErrback(fail_handler or ack_handler)
    return d


def update():
    """
    A wrapper of ``SendServers()`` method.
    """
    lg.out(6, "propagate.update")
    return SendServers()


def write_to_dht():
    """

    """
    lg.out(6, "propagate.write_to_dht")
    LocalIdentity = my_id.getLocalIdentity()
    return dht_records.set_identity(
        LocalIdentity.getIDURL(),
        LocalIdentity.serialize(as_text=True),
    )

#------------------------------------------------------------------------------


def FetchSingle(idurl):
    """
    Fetch single identity file from given ``idurl``.
    """
    lg.out(6, "propagate.fetch_single " + idurl)
    return identitycache.scheduleForCaching(idurl)


def Fetch(idslist):
    """
    Just a wrapper for ``fetch()`` method.
    """
    return fetch(idslist)


def FetchSuppliers(customer_idurl=None):
    """
    Fetch identity files of all supplier.
    """
    return fetch(contactsdb.suppliers(customer_idurl=customer_idurl))


def FetchCustomers():
    """
    Fetch identity files of all customers.
    """
    return fetch(contactsdb.customers())

#------------------------------------------------------------------------------


def SendServers():
    """
    My identity file can be stored in different locations, see the "sources"
    field.

    So I can use different identity servers to store more secure and reliable. This
    method will send my identity file to all my identity servers via
    transport_tcp.
    """
    from transport.tcp import tcp_node
    sendfile, sendfilename = tmpfile.make("propagate")
    os.close(sendfile)
    LocalIdentity = my_id.getLocalIdentity()
    bpio.WriteTextFile(sendfilename, LocalIdentity.serialize(as_text=True))
    dlist = []
    for idurl in LocalIdentity.sources:
        # sources for out identity are servers we need to send to
        protocol, host, port, filename = nameurl.UrlParse(idurl)
        # TODO: rebuild identity-server logic to be able to send my identity via HTTP POST instead of TCP and
        # get rid of second TCP port at all 
        webport, tcpport = known_servers.by_host().get(host, (
            # by default use "expected" port numbers
            settings.IdentityWebPort(), settings.IdentityServerPort()))
        dlist.append(tcp_node.send(
            sendfilename, net_misc.normalize_address((host, int(tcpport), )), 'Identity', keep_alive=False,
        ))
    dl = DeferredList(dlist, consumeErrors=True)
    return dl


def SendSuppliers(customer_idurl=None):
    """
    Send my identity file to all my suppliers, calls to ``SendToIDs()`` method.
    """
    lg.out(6, "propagate.SendSuppliers")
    SendToIDs(contactsdb.suppliers(customer_idurl=customer_idurl), ack_handler=HandleSuppliersAck, wide=True)


def SendCustomers():
    """
    Calls ``SendToIDs()`` to send identity to all my customers.
    """
    lg.out(8, "propagate.SendCustomers")
    SendToIDs(contactsdb.customers(), ack_handler=HandleCustomersAck, wide=True)


def SlowSendSuppliers(delay=1, customer_idurl=None):
    """
    Doing same thing, but puts delays before sending to every next supplier.

    This is used when need to "ping" suppliers.
    """
    global _SlowSendIsWorking
    if _SlowSendIsWorking:
        lg.out(8, "propagate.SlowSendSuppliers  is working at the moment. skip.")
        return
    lg.out(8, "propagate.SlowSendSuppliers delay=%s" % str(delay))

    def _send(index, payload, delay):
        global _SlowSendIsWorking
        idurl = contactsdb.supplier(index, customer_idurl=customer_idurl)
        if not idurl:
            _SlowSendIsWorking = False
            return
        # transport_control.ClearAliveTime(idurl)
        SendToID(idurl, Payload=payload, wide=True)
        reactor.callLater(delay, _send, index + 1, payload, delay)  # @UndefinedVariable

    _SlowSendIsWorking = True
    payload = strng.to_bin(my_id.getLocalIdentity().serialize())
    _send(0, payload, delay)


def SlowSendCustomers(delay=1):
    """
    Same, "slowly" send my identity file to all my customers.
    """

    global _SlowSendIsWorking
    if _SlowSendIsWorking:
        lg.out(8, "propagate.SlowSendCustomers  slow send is working at the moment. skip.")
        return
    lg.out(8, "propagate.SlowSendCustomers delay=%s" % str(delay))

    def _send(index, payload, delay):
        global _SlowSendIsWorking
        idurl = contactsdb.customer(index)
        if not idurl:
            _SlowSendIsWorking = False
            return
        # transport_control.ClearAliveTime(idurl)
        SendToID(idurl, Payload=payload, wide=True)
        reactor.callLater(delay, _send, index + 1, payload, delay)  # @UndefinedVariable

    _SlowSendIsWorking = True
    payload = strng.to_bin(my_id.getLocalIdentity().serialize())
    _send(0, payload, delay)


def HandleSuppliersAck(ackpacket, info):
    """
    Called when supplier is "Acked" to my after call to ``SendSuppliers()``.
    """
    lg.out(8, "propagate.HandleSupplierAck %s" % ackpacket.OwnerID)


def HandleCustomersAck(ackpacket, info):
    """
    Called when supplier is "Acked" to my after call to ``SendCustomers()``.
    """
    lg.out(8, "propagate.HandleCustomerAck %s" % ackpacket.OwnerID)


def HandleAck(ackpacket, info):
    lg.out(8, "propagate.HandleAck %r %r" % (ackpacket, info))


def HandleTimeOut(pkt_out):
    lg.out(8, "propagate.HandleTimeOut %r" % pkt_out)


def OnFileSent(pkt_out, item, status, size, error_message):
    """
    """
    return False


def SendToID(idurl, Payload=None, wide=False, ack_handler=None, timeout_handler=None, response_timeout=20, ):
    """
    Create ``packet`` with my Identity file and calls
    ``transport.gateway.outbox()`` to send it.
    """
    lg.out(8, "propagate.SendToID [%s] wide=%s" % (nameurl.GetName(idurl), str(wide)))
    if ack_handler is None:
        ack_handler = HandleAck
    if timeout_handler is None:
        timeout_handler = HandleTimeOut
    thePayload = Payload
    if thePayload is None:
        thePayload = strng.to_bin(my_id.getLocalIdentity().serialize())
    p = signed.Packet(
        commands.Identity(),
        my_id.getLocalID(),  # MyID,
        my_id.getLocalID(),  # MyID,
        commands.Identity(),  #  'Identity',  # my_id.getLocalID(), #PacketID,
        thePayload,
        idurl,
    )
    # callback.register_interest(AckHandler, p.RemoteID, p.PacketID)
    result = gateway.outbox(p, wide, response_timeout=response_timeout, callbacks={
        commands.Ack(): ack_handler,
        commands.Fail(): ack_handler,
        None: timeout_handler,
    })
    if wide:
        # this is a ping packet - need to clear old info
        p2p_stats.ErasePeerProtosStates(idurl)
        p2p_stats.EraseMyProtosStates(idurl)
    return result


def SendToIDs(idlist, wide=False, ack_handler=None, timeout_handler=None, response_timeout=20):
    """
    Same, but send to many IDs and also check previous packets to not re-send.
    """
    lg.out(8, "propagate.SendToIDs to %d users, wide=%s" % (len(idlist), wide))
    if ack_handler is None:
        ack_handler = HandleAck
    if timeout_handler is None:
        timeout_handler = HandleTimeOut
    # MyID = my_id.getLocalID()
    # PacketID = MyID
    LocalIdentity = my_id.getLocalIdentity()
    Payload = strng.to_bin(LocalIdentity.serialize())
    # Hash = key.Hash(Payload)
    alreadysent = set()
    totalsent = 0
    inqueue = {}
    found_previous_packets = 0
    for pkt_out in packet_out.queue():
        if pkt_out.remote_idurl in idlist:
            if pkt_out.description.count('Identity'):
                if pkt_out.remote_idurl not in inqueue:
                    inqueue[pkt_out.remote_idurl] = 0
                inqueue[pkt_out.remote_idurl] += 1
                found_previous_packets += 1
    for contact in idlist:
        if not contact:
            continue
        if contact in alreadysent:
            # just want to send once even if both customer and supplier
            continue
        if contact in inqueue and inqueue[contact] > 2:
            # now only 2 protocols is working: tcp and udp
            lg.out(8, '        skip sending [Identity] to %s, packet already in the queue' % contact)
            continue
#        found_previous_packets = 0
#        for transfer_id in gate.transfers_out_by_idurl().get(contact, []):
#            ti = gate.transfers_out().get(transfer_id, None)
#            if ti and ti.description.count('Identity'):
#                found_previous_packets += 1
#                break
#        if found_previous_packets >= 3:
#            lg.out(8, '        skip sending to %s' % contact)
#            continue
        p = signed.Packet(
            commands.Identity(),
            my_id.getLocalID(),  # MyID,
            my_id.getLocalID(),  # MyID,
            commands.Identity(),  #'Identity',  # my_id.getLocalID(), #PacketID,
            Payload,
            contact,
        )
        lg.out(8, "        sending [Identity] to %s" % nameurl.GetName(contact))
        # callback.register_interest(AckHandler, signed.RemoteID, signed.PacketID)
        gateway.outbox(p, wide, response_timeout=response_timeout, callbacks={
            commands.Ack(): ack_handler,
            commands.Fail(): ack_handler,
            None: timeout_handler,
        })
        if wide:
            # this is a ping packet - need to clear old info
            p2p_stats.ErasePeerProtosStates(contact)
            p2p_stats.EraseMyProtosStates(contact)
        alreadysent.add(contact)
        totalsent += 1
    del alreadysent
    return totalsent


def PingContact(idurl, timeout=30, retries=2):
    """
    Can be called when you need to "ping" another user.
    This will send your Identity to that node, and it must respond.
    """
    if _Debug:
        lg.out(_DebugLevel, "propagate.PingContact [%s]" % nameurl.GetName(idurl))
    ping_result = Deferred()

    def _ack_handler(response, info, attempts):
        lg.out(_DebugLevel, "propagate.PingContact [%s] SUCCESS after %d attempts : %s from %s://%s" % (
            nameurl.GetName(idurl), attempts, response, info.proto, info.host, ))
        if not ping_result.called:
            ping_result.callback((response, info, ))
        return None

    def _try_to_ping(attempts):
        if attempts > retries + 1:
            if not ping_result.called:
                ping_result.errback(Exception('remote user did not responded after %d ping attempts : %s' % (attempts, idurl, )))
            return None
        SendToIDs(
            idlist=[idurl, ],
            ack_handler=lambda response, info: _ack_handler(response, info, attempts),
            timeout_handler=lambda pkt_out: _response_timed_out(pkt_out, attempts),
            response_timeout=timeout,
            wide=True,
        )
        return None

    def _response_timed_out(pkt_out, attempts):
        lg.out(_DebugLevel, "propagate.PingContact._response_timed_out : %s" % pkt_out)
        # if not ping_result.called:
        #     ping_result.errback(TimeoutError('remote user did not responded'))
        _try_to_ping(attempts + 1)
        return None

    def _identity_cached(idsrc, idurl):
        lg.out(_DebugLevel, "propagate.PingContact._identity_cached %s bytes for [%s]" % (
            len(idsrc), idurl))
        # TODO: Verify()
        _try_to_ping(1)
        return idsrc

    def _identity_cache_failed(err, idurl, attempts):
        try:
            msg = err.getErrorMessage()
        except:
            msg = str(err)
        if _Debug:
            lg.out(_DebugLevel, "propagate.PingContact._identity_cache_failed attempts=%d %s : %s" % (attempts, idurl, msg, ))
        # if not ping_result.called:
        #     ping_result.errback(Exception('failed to fetch remote identity %s: %s' % (idurl, msg, )))
        _try_to_cache(attempts + 1)
        return None

    def _try_to_cache(attempts):
        if attempts > retries + 1:
            if not ping_result.called:
                ping_result.errback(Exception('failed to fetch remote identity after %d attempts : %s' % (attempts, idurl, )))
            return None
        idcache_defer = identitycache.scheduleForCaching(strng.to_text(idurl), timeout=timeout)
        idcache_defer.addCallback(_identity_cached, idurl)
        idcache_defer.addErrback(_identity_cache_failed, idurl, attempts)
        # ping_result.addErrback(lg.errback)
        return None

    _try_to_cache(1)
    return ping_result
