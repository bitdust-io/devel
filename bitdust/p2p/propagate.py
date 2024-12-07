#!/usr/bin/python
# propagate.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
_DebugLevel = 24

#------------------------------------------------------------------------------

import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in propagate.py')

from twisted.internet.defer import DeferredList, Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import nameurl
from bitdust.lib import net_misc
from bitdust.lib import strng
from bitdust.lib import packetid

from bitdust.contacts import contactsdb
from bitdust.contacts import identitycache

from bitdust.main import settings

from bitdust.userid import my_id
from bitdust.userid import id_url

from bitdust.p2p import commands
from bitdust.p2p import p2p_stats

from bitdust.crypt import signed

from bitdust.transport import gateway
from bitdust.transport import packet_out

from bitdust.dht import dht_records

#------------------------------------------------------------------------------

_SlowSendIsWorking = False
_PropagateCounter = 0
_StartupPropagateList = set()

#------------------------------------------------------------------------------


def init():
    """
    Need to call that at start up to link with transport_control.
    """
    if _Debug:
        lg.out(_DebugLevel, 'propagate.init')
    # callback.add_finish_file_sending_callback(OnFileSent)


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'propagate.shutdown')


def startup_list():
    global _StartupPropagateList
    return _StartupPropagateList


#------------------------------------------------------------------------------


def propagate(selected_contacts, ack_handler=None, wide=False, refresh_cache=False, wait_packets=False, response_timeout=None):
    """
    Run the "propagate" process.

    First need to fetch ``selected_contacts`` IDs from id servers. And
    then send our Identity file to that contacts.
    """
    if response_timeout is None:
        response_timeout = settings.P2PTimeOut()
    if _Debug:
        lg.out(_DebugLevel, 'propagate.propagate to %d contacts' % len(selected_contacts))
    result = Deferred()

    def contacts_fetched(x):
        res = SendToIDs(
            idlist=selected_contacts,
            ack_handler=ack_handler,
            wide=wide,
            wait_packets=wait_packets,
            response_timeout=response_timeout,
        )
        if _Debug:
            lg.out(_DebugLevel, 'propagate.contacts_fetched with %d identities, sending my identity to %d remote nodes: %r' % (len(x), len(selected_contacts), res))
        if wait_packets:
            if not res:
                result.callback([])
                return result
            res.addCallback(result.callback)
            res.addErrback(result.errback)
            return result
        result.callback(list(selected_contacts))
        return result

    fetch(list_ids=selected_contacts, refresh_cache=refresh_cache).addBoth(contacts_fetched)
    return result


def fetch(list_ids, refresh_cache=False, timeout=15, try_other_sources=True):
    """
    Request a list of identity files.
    """
    if _Debug:
        lg.out(_DebugLevel, 'propagate.fetch %d identities' % len(list_ids))
    dl = []
    for url in list_ids:
        if not url:
            continue
        if identitycache.FromCache(url) and not refresh_cache:
            continue
        dl.append(identitycache.immediatelyCaching(
            idurl=id_url.to_original(url),
            timeout=timeout,
            try_other_sources=try_other_sources,
        ))
    return DeferredList(dl, consumeErrors=True)


def start(ack_handler=None, wide=False, refresh_cache=False, include_all=True, include_enabled=True, include_startup=False, wait_packets=False, response_timeout=None):
    """
    Call ``propagate()`` for all known contacts or only for those which are related to enabled/active services.
    """
    if response_timeout is None:
        response_timeout = settings.P2PTimeOut()
    selected_contacts = set(filter(None, contactsdb.contacts_remote(include_all=include_all, include_enabled=include_enabled)))
    if include_startup and startup_list():
        lg.warn('going to propagate my identity also to %d nodes from startup list' % len(startup_list()))
        selected_contacts.update(startup_list())
        startup_list().clear()
    if _Debug:
        lg.args(_DebugLevel, wide=wide, refresh_cache=refresh_cache, all=include_all, enabled=include_enabled, selected=len(selected_contacts))
    return propagate(
        selected_contacts=list(selected_contacts),
        ack_handler=ack_handler,
        wide=wide,
        refresh_cache=refresh_cache,
        wait_packets=wait_packets,
        response_timeout=response_timeout,
    )


def suppliers(ack_handler=None, wide=False, customer_idurl=None, wait_packets=False):
    """
    Call ``propagate()`` for all suppliers.
    """
    if _Debug:
        lg.out(_DebugLevel, 'propagate.suppliers')
    return propagate(
        selected_contacts=contactsdb.suppliers(customer_idurl=customer_idurl),
        ack_handler=ack_handler,
        wide=wide,
        wait_packets=wait_packets,
    )


def customers(ack_handler=None, wide=False, wait_packets=False):
    """
    Call ``propagate()`` for all known customers.
    """
    if _Debug:
        lg.out(_DebugLevel, 'propagate.customers')
    return propagate(
        selected_contacts=contactsdb.customers(),
        ack_handler=ack_handler,
        wide=wide,
        wait_packets=wait_packets,
    )


def single(idurl, ack_handler=None, wide=False, fail_handler=None):
    """
    Do "propagate" for a single contact.
    """
    d = FetchSingle(idurl)
    d.addCallback(lambda x: SendToIDs(
        [
            idurl,
        ],
        ack_handler=ack_handler,
        wide=wide,
    ))
    if ack_handler:
        d.addErrback(fail_handler or ack_handler)
    return d


def update():
    """
    A wrapper of ``SendServers()`` method.
    """
    if _Debug:
        lg.out(_DebugLevel, 'propagate.update')
    return SendServers()


def write_to_dht():
    """

    """
    if _Debug:
        lg.out(_DebugLevel, 'propagate.write_to_dht')
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
    if _Debug:
        lg.out(_DebugLevel, 'propagate.fetch_single ' + idurl)
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
    My identity file can be stored in different locations, see the "sources" field.
    So I can use different identity servers to store more secure and reliable. This
    method will send my identity file to all my identity servers with HTTP POST method.
    """
    LocalIdentity = my_id.getLocalIdentity()
    payload = LocalIdentity.serialize(as_text=False)
    dlist = []
    for idurl in LocalIdentity.getSources(as_originals=True):
        _, host, webport, filename = nameurl.UrlParse(idurl)
        url = net_misc.pack_address(
            (
                host,
                webport,
            ),
            proto='http',
        )
        dlist.append(net_misc.http_post_data(
            url=url,
            data=payload,
            connectTimeout=15,
        ))
        if _Debug:
            lg.args(_DebugLevel, url=url, filename=filename, size=len(payload))
    dl = DeferredList(dlist, consumeErrors=True)
    return dl


def SendSuppliers(customer_idurl=None):
    """
    Send my identity file to all my suppliers, calls to ``SendToIDs()`` method.
    """
    if _Debug:
        lg.out(_DebugLevel, 'propagate.SendSuppliers')
    SendToIDs(contactsdb.suppliers(customer_idurl=customer_idurl), ack_handler=HandleSuppliersAck, wide=True)


def SendCustomers():
    """
    Calls ``SendToIDs()`` to send identity to all my customers.
    """
    if _Debug:
        lg.out(_DebugLevel, 'propagate.SendCustomers')
    SendToIDs(contactsdb.customers(), ack_handler=HandleCustomersAck, wide=True)


def SlowSendSuppliers(delay=1, customer_idurl=None):
    """
    Doing same thing, but puts delays before sending to every next supplier.

    This is used when need to "ping" suppliers.
    """
    global _SlowSendIsWorking
    if _SlowSendIsWorking:
        if _Debug:
            lg.out(_DebugLevel, 'propagate.SlowSendSuppliers  is working at the moment. skip.')
        return
    if _Debug:
        lg.out(_DebugLevel, 'propagate.SlowSendSuppliers delay=%s' % str(delay))

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
        if _Debug:
            lg.out(_DebugLevel, 'propagate.SlowSendCustomers  slow send is working at the moment. skip.')
        return
    if _Debug:
        lg.out(_DebugLevel, 'propagate.SlowSendCustomers delay=%s' % str(delay))

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
    if _Debug:
        lg.out(_DebugLevel, 'propagate.HandleSupplierAck %s' % ackpacket.OwnerID)


def HandleCustomersAck(ackpacket, info):
    """
    Called when supplier is "Acked" to my after call to ``SendCustomers()``.
    """
    if _Debug:
        lg.out(_DebugLevel, 'propagate.HandleCustomerAck %s' % ackpacket.OwnerID)


def HandleAck(ackpacket, info):
    if _Debug:
        lg.out(_DebugLevel, 'propagate.HandleAck %r %r' % (ackpacket, info))


def HandleTimeOut(pkt_out):
    if _Debug:
        lg.out(_DebugLevel, 'propagate.HandleTimeOut %r' % pkt_out)


def OnFileSent(pkt_out, item, status, size, error_message):
    return False


def SendToID(
    idurl,
    Payload=None,
    wide=False,
    ack_handler=None,
    timeout_handler=None,
    response_timeout=None,
):
    """
    Create ``packet`` with my Identity file and calls
    ``transport.gateway.outbox()`` to send it.
    """
    global _PropagateCounter
    if _Debug:
        lg.out(_DebugLevel, 'propagate.SendToID [%s] wide=%s' % (nameurl.GetName(idurl), str(wide)))
    if response_timeout is None:
        response_timeout = settings.P2PTimeOut()
    if ack_handler is None:
        ack_handler = HandleAck
    if timeout_handler is None:
        timeout_handler = HandleTimeOut
    thePayload = Payload
    if thePayload is None:
        thePayload = strng.to_bin(my_id.getLocalIdentity().serialize())
    p = signed.Packet(
        Command=commands.Identity(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=('propagate:%d:%s' % (_PropagateCounter, packetid.UniqueID())),
        Payload=thePayload,
        RemoteID=idurl,
    )
    _PropagateCounter += 1
    result = gateway.outbox(
        p,
        wide,
        response_timeout=response_timeout,
        callbacks={
            commands.Ack(): ack_handler,
            commands.Fail(): ack_handler,
            None: timeout_handler,
        },
    )
    if wide:
        # this is a ping packet - need to clear old info
        p2p_stats.ErasePeerProtosStates(idurl)
        p2p_stats.EraseMyProtosStates(idurl)
    return result


def SendToIDs(idlist, wide=False, ack_handler=None, timeout_handler=None, response_timeout=None, wait_packets=False):
    """
    Same, but send to many IDs and also check previous packets to not re-send.
    """
    global _PropagateCounter
    if response_timeout is None:
        response_timeout = settings.P2PTimeOut()
    if ack_handler is None:
        ack_handler = HandleAck
    if timeout_handler is None:
        timeout_handler = HandleTimeOut
    LocalIdentity = my_id.getLocalIdentity()
    Payload = strng.to_bin(LocalIdentity.serialize())
    if _Debug:
        lg.out(_DebugLevel, 'propagate.SendToIDs to %d users, rev=%r wide=%s' % (len(idlist), LocalIdentity.getRevisionValue(), wide))
    alreadysent = set()
    totalsent = 0
    inqueue = {}
    found_previous_packets = 0
    for pkt_out in packet_out.queue():
        if id_url.is_in(pkt_out.remote_idurl, idlist, as_field=False):
            if pkt_out.description.count('Identity'):
                if pkt_out.remote_idurl not in inqueue:
                    inqueue[pkt_out.remote_idurl] = 0
                inqueue[pkt_out.remote_idurl] += 1
                found_previous_packets += 1
    wait_list = []
    for contact in idlist:
        if not contact:
            continue
        if contact in alreadysent:
            # just want to send once even if both customer and supplier
            continue
        if contact in inqueue and inqueue[contact] > 2:
            # now only 2 protocols is working: tcp and udp
            if _Debug:
                lg.out(_DebugLevel, '        skip sending [Identity] to %s, packet already in the queue' % contact)
            continue
        p = signed.Packet(
            Command=commands.Identity(),
            OwnerID=my_id.getIDURL(),
            CreatorID=my_id.getIDURL(),
            PacketID=('propagate:%d:%s' % (_PropagateCounter, packetid.UniqueID())),
            Payload=Payload,
            RemoteID=contact,
        )
        _PropagateCounter += 1
        if _Debug:
            lg.out(_DebugLevel, '        sending %r to %s' % (p, nameurl.GetName(contact)))
        res = gateway.outbox(
            p,
            wide,
            response_timeout=response_timeout,
            callbacks={
                commands.Ack(): ack_handler,
                commands.Fail(): ack_handler,
                None: timeout_handler,
            },
        )
        if not res:
            lg.warn('my Identity() was not sent to %r' % contact)
            continue
        if wide:
            # this is a ping packet - need to clear old info
            p2p_stats.ErasePeerProtosStates(contact)
            p2p_stats.EraseMyProtosStates(contact)
        alreadysent.add(contact)
        totalsent += 1
        if wait_packets and res:
            if isinstance(res, Deferred):
                wait_list.append(res)
            elif res.finished_deferred and isinstance(res.finished_deferred, Deferred):
                wait_list.append(res.finished_deferred)
    del alreadysent
    if not wait_packets:
        return totalsent
    return DeferredList(wait_list, consumeErrors=True)


#------------------------------------------------------------------------------


def ping_suppliers(customer_idurl=None, timeout=None):
    if timeout is None:
        timeout = settings.P2PTimeOut()
    from bitdust.p2p import online_status
    l = []
    for supplier_idurl in contactsdb.suppliers(customer_idurl=customer_idurl):
        if supplier_idurl:
            l.append(online_status.ping(idurl=supplier_idurl, ack_timeout=timeout, channel='ping_suppliers', keep_alive=True))
    return DeferredList(l, consumeErrors=True)


def ping_customers(timeout=None):
    if timeout is None:
        timeout = settings.P2PTimeOut()
    from bitdust.p2p import online_status
    l = []
    for customer_idurl in contactsdb.customers():
        if customer_idurl:
            l.append(online_status.ping(idurl=customer_idurl, ack_timeout=timeout, channel='ping_customers', keep_alive=True))
    return DeferredList(l, consumeErrors=True)


def ping_nodes(idurl_list, timeout=None, channel='ping_nodes', keep_alive=True):
    if timeout is None:
        timeout = settings.P2PTimeOut()
    from bitdust.p2p import online_status
    l = []
    for idurl in idurl_list:
        if idurl:
            l.append(online_status.ping(idurl=idurl, ack_timeout=timeout, channel=channel, keep_alive=keep_alive))
    return DeferredList(l, consumeErrors=True)
