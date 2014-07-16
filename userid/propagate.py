#!/usr/bin/python
#propagate.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: propagate

When a user starts up he needs to run the stun.py to check what his IP is,
and if it has changed he needs to generate a new identity and send it to
his identity server and all of his contacts.

We also just request new copies of all identities from their servers when
we start up. This is simple and effective.

We should try contacting each contact every hour and if we have not been
able to contact them in 2 or 3 hours then fetch copy of identity from
their server.
"""

import os
import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in propagate.py')

from twisted.internet.defer import DeferredList, Deferred

import lib.bpio as bpio
import lib.misc as misc
import lib.nameurl as nameurl
import lib.signed_packet as signed_packet
import lib.crypto as crypto
import lib.contacts as contacts
import lib.commands as commands
import lib.settings as settings
import lib.stun as stun
import lib.tmpfile as tmpfile

import userid.identitycache as identitycache
import userid.known_servers as known_servers

import transport.gate as gate
import transport.callback as callback
import transport.stats as stats
import transport.packet_out as packet_out

import dht.dht_service as dht_service

#------------------------------------------------------------------------------ 

_SlowSendIsWorking = False

#------------------------------------------------------------------------------

def init():
    """
    Need to call that at start up to link with transport_control. 
    """
    bpio.log(4, "propagate.init ")


def shutdown():
    """
    """
    bpio.log(4, "propagate.shutdown ")

#------------------------------------------------------------------------------ 

def propagate(selected_contacts, AckHandler=None, wide=False):
    """
    Run the "propagate" process. 
    First need to fetch ``selected_contacts`` IDs from id server.
    And then send our Identity file to that contacts. 
    """
    bpio.log(6, "propagate.propagate to %d contacts" % len(selected_contacts))
    d = Deferred()
    def contacts_fetched(x):
        bpio.log(6, "propagate.propagate.contacts_fetched")
        SendToIDs(selected_contacts, AckHandler, wide)
        d.callback(list(selected_contacts))
        return x
    fetch(selected_contacts).addBoth(contacts_fetched)
    return d


def fetch(list_ids): 
    """
    Request a list of identity files.
    """
    bpio.log(6, "propagate.fetch identities for %d users" % len(list_ids))
    dl = []
    for url in list_ids:
        if url:
            if not identitycache.FromCache(url):
                dl.append(identitycache.scheduleForCaching(url))
    return DeferredList(dl, consumeErrors=True)


def start(AckHandler=None, wide=False):
    """
    Call ``propagate()`` for all known contacts.
    """
    bpio.log(6, 'propagate.start')
    return propagate(contacts.getRemoteContacts(), AckHandler, wide)


def suppliers(AckHandler=None, wide=False):
    """
    Call ``propagate()`` for all suppliers.
    """
    bpio.log(6, 'propagate.suppliers')
    return propagate(contacts.getSupplierIDs(), AckHandler, wide)


def customers(AckHandler=None, wide=False):
    """
    Call ``propagate()`` for all known customers.
    """
    bpio.log(6, 'propagate.customers')
    return propagate(contacts.getCustomerIDs(), AckHandler, wide)


def allcontacts(AckHandler=None, wide=False):
    """
    Call ``propagate()`` for all contacts and correspondents, almost the same to ``start()``.
    """
    bpio.log(6, 'propagate.allcontacts')
    return propagate(contacts.getContactsAndCorrespondents(), AckHandler, wide)


def single(idurl, AckHandler=None, wide=False):
    """
    Do "propagate" for a single contact.
    """
    FetchSingle(idurl).addBoth(lambda x: SendToIDs([idurl], AckHandler, wide))
    

def update():
    """
    A wrapper of ``SendServers()`` method.
    """
    bpio.log(6, "propagate.update")
    return SendServers()

def write_to_dht():
    """
    """
    bpio.log(6, "propagate.write_to_dht")
    LocalIdentity = misc.getLocalIdentity()
    dht_service.set_value(LocalIdentity.getIDURL(), LocalIdentity.serialize())

#------------------------------------------------------------------------------ 

def FetchSingle(idurl):
    """
    Fetch single identity file from given ``idurl``.
    """
    bpio.log(6, "propagate.fetch_single " + idurl)
    return identitycache.scheduleForCaching(idurl)


def Fetch(idslist):
    """
    Just a wrapper for ``fetch()`` method.
    """
    return fetch(idslist)


def FetchSuppliers():
    """
    Fetch identity files of all supplier.
    """
    return fetch(contacts.getSupplierIDs())


def FetchCustomers():
    """
    Fetch identity files of all customers.
    """
    return fetch(contacts.getCustomerIDs())

#------------------------------------------------------------------------------ 

def SendServers():
    """
    My identity file can be stored in different locations, see the "sources" field.
    So I can use different identity servers to store more secure.
    This method will send my identity file to all my identity servers via transport_tcp.
    """
    sendfile, sendfilename = tmpfile.make("propagate")
    os.close(sendfile)
    LocalIdentity = misc.getLocalIdentity()
    bpio.WriteFile(sendfilename, LocalIdentity.serialize())
    dlist = []
    for idurl in LocalIdentity.sources:
        # sources for out identity are servers we need to send to
        protocol, host, port, filename = nameurl.UrlParse(idurl)
        # if host == settings.IdentityServerName():
        #     host = '67.207.147.183'
        webport, tcpport = known_servers.by_host().get(host, 
            (settings.IdentityWebPort(), settings.IdentityServerPort()))
        srvhost = '%s:%d'%(host, int(tcpport))
        dlist.append(gate.send_file_single('tcp', srvhost, sendfilename, 'Identity'))
    dl = DeferredList(dlist, consumeErrors=True)
    return dl


def SendSuppliers():
    """
    Send my identity file to all my suppliers, calls to ``SendToIDs()`` method. 
    """
    bpio.log(6, "propagate.SendSuppliers")
    SendToIDs(contacts.getSupplierIDs(), HandleSuppliersAck)


def SendCustomers():
    """
    Calls ``SendToIDs()`` to send identity to all my customers.
    """
    bpio.log(8, "propagate.SendCustomers")
    SendToIDs(contacts.getCustomerIDs(), HandleCustomersAck)


def SlowSendSuppliers(delay=1):
    """
    Doing same thing, but puts delays before sending to every next supplier.
    This is used when need to "ping" suppliers.
    """
    global _SlowSendIsWorking
    if _SlowSendIsWorking:
        bpio.log(8, "propagate.SlowSendSuppliers  is working at the moment. skip.")
        return
    bpio.log(8, "propagate.SlowSendSuppliers delay=%s" % str(delay))

    def _send(index, payload, delay):
        global _SlowSendIsWorking
        idurl = contacts.getSupplierID(index)
        if not idurl:
            _SlowSendIsWorking = False
            return
        # transport_control.ClearAliveTime(idurl)
        SendToID(idurl, Payload=payload, wide=True)
        reactor.callLater(delay, _send, index+1, payload, delay)

    _SlowSendIsWorking = True
    payload = misc.getLocalIdentity().serialize()
    _send(0, payload, delay)


def SlowSendCustomers(delay=1):
    """
    Same, "slowly" send my identity file to all my customers.
    """
    
    global _SlowSendIsWorking
    if _SlowSendIsWorking:
        bpio.log(8, "propagate.SlowSendCustomers  slow send is working at the moment. skip.")
        return
    bpio.log(8, "propagate.SlowSendCustomers delay=%s" % str(delay))

    def _send(index, payload, delay):
        global _SlowSendIsWorking
        idurl = contacts.getCustomerID(index)
        if not idurl:
            _SlowSendIsWorking = False
            return
        # transport_control.ClearAliveTime(idurl)
        SendToID(idurl, Payload=payload, wide=True)
        reactor.callLater(delay, _send, index+1, payload, delay)

    _SlowSendIsWorking = True
    payload = misc.getLocalIdentity().serialize()
    _send(0, payload, delay)


def HandleSuppliersAck(ackpacket, info):
    """
    Called when supplier is "Acked" to my after call to ``SendSuppliers()``. 
    """
    # Num = contacts.numberForSupplier(ackpacket.OwnerID)
    bpio.log(8, "propagate.HandleSupplierAck %s" % ackpacket.OwnerID)


def HandleCustomersAck(ackpacket, info):
    """
    Called when supplier is "Acked" to my after call to ``SendCustomers()``. 
    """
    # Num = contacts.numberForCustomer(ackpacket.OwnerID)
    bpio.log(8, "propagate.HandleCustomerAck %s" % ackpacket.OwnerID)


def HandleAck(ackpacket, info):
    bpio.log(16, "propagate.HandleAck %r %r" % (ackpacket, info))


def SendToID(idurl, AckHandler=None, Payload=None, NeedAck=False, wide=False):
    """
    Create ``packet`` with my Identity file and calls ``lib.transport_control.outbox()`` to send it.
    """
    bpio.log(8, "propagate.SendToID [%s] NeedAck=%s" % (nameurl.GetName(idurl), str(NeedAck)))
    if AckHandler is None:
        AckHandler = HandleAck
    thePayload = Payload
    if thePayload is None:
        thePayload = misc.getLocalIdentity().serialize()
    p = signed_packet.Packet(
        commands.Identity(),
        misc.getLocalID(), #MyID,
        misc.getLocalID(), #MyID,
        'identity', # misc.getLocalID(), #PacketID,
        thePayload,
        idurl)
    # callback.register_interest(AckHandler, p.RemoteID, p.PacketID)
    gate.outbox(p, wide, callbacks={
        commands.Ack(): AckHandler,
        commands.Fail(): AckHandler}) 
    if wide:
        # this is a ping packet - need to clear old info
        stats.ErasePeerProtosStates(idurl)
        stats.EraseMyProtosStates(idurl)


def SendToIDs(idlist, AckHandler=None, wide=False, NeedAck=False):
    """
    Same, but send to many IDs.
    """
    bpio.log(8, "propagate.SendToIDs to %d users" % len(idlist))
    if AckHandler is None:
        AckHandler = HandleAck
    MyID = misc.getLocalID()
    PacketID = MyID
    LocalIdentity = misc.getLocalIdentity()
    Payload = LocalIdentity.serialize()
    Hash = crypto.Hash(Payload)
    alreadysent = set()
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
            # now only 2 protocols is working: tcp and dhtudp
            bpio.log(8, '        skip sending to %s' % contact)
            continue
#        found_previous_packets = 0
#        for transfer_id in gate.transfers_out_by_idurl().get(contact, []):
#            ti = gate.transfers_out().get(transfer_id, None)
#            if ti and ti.description.count('Identity'):
#                found_previous_packets += 1
#                break
#        if found_previous_packets >= 3:
#            bpio.log(8, '        skip sending to %s' % contact)
#            continue    
        p = signed_packet.Packet(
            commands.Identity(),
            misc.getLocalID(), #MyID,
            misc.getLocalID(), #MyID,
            'identity', # misc.getLocalID(), #PacketID,
            Payload,
            contact)
        bpio.log(8, "        sending [Identity] to %s" % nameurl.GetName(contact))
        # callback.register_interest(AckHandler, signed_packet.RemoteID, signed_packet.PacketID)
        gate.outbox(p, wide, callbacks={
            commands.Ack(): AckHandler,
            commands.Fail(): AckHandler}) 
        if wide:
            # this is a ping packet - need to clear old info
            stats.ErasePeerProtosStates(contact)
            stats.EraseMyProtosStates(contact)
        alreadysent.add(contact)
    del alreadysent


def PingContact(idurl):
    """
    Called from outside when need to "ping" some user, this will just send my Identity to that guy, 
    he will need to respond.
    """
    SendToID(idurl, NeedAck=True)


