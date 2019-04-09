#!/usr/bin/python
# p2p_service.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (p2p_service.py) is part of BitDust Software.
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
.. module:: p2p_service.

This serves requests from peers:

    * Data          - save packet to a file      (a commands.Data() packet)
    * Retrieve      - read packet from a file    (a commands.Data() packet)
    * ListFiles     - list files we have for customer
    * Delete        - delete a file
    * Identity      - contact or id server sending us a current identity
    * Ack           - response from remote peer after my request
    * Message       - a message from remote peer
    * Correspondent - request to be my correspondent
    TODO: describe other packets here

TODO: need to move logic from this monolitic file into a services
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 2

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from userid import my_id
from userid import identity
from userid import global_id

from contacts import contactsdb

from contacts import identitycache

from p2p import commands

from lib import packetid
from lib import nameurl
from lib import serialization
from lib import strng

from crypt import signed

from main import settings

from transport import gateway

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.init')


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.shutdown')

#------------------------------------------------------------------------------


def inbox(newpacket, info, status, error_message):
    """
    """
    if newpacket.CreatorID != my_id.getLocalID() and newpacket.RemoteID != my_id.getLocalID():
        # packet is NOT for us, skip
        return False

    if newpacket.Command == commands.Ack():
        # a response from remote node, typically handled in other places
        Ack(newpacket, info)

    elif newpacket.Command == commands.Fail():
        # some operation was failed on other side
        Fail(newpacket)

    elif newpacket.Command == commands.Retrieve():
        # retrieve some packet customer stored with us
        # handled by service_supplier()
        Retrieve(newpacket)

    elif newpacket.Command == commands.RequestService():
        # other node send us a request to get some service
        # handled by service_p2p_hookups()
        RequestService(newpacket, info)

    elif newpacket.Command == commands.CancelService():
        # other node wants to stop the service we gave him
        # handled by service_p2p_hookups()
        CancelService(newpacket, info)

    elif newpacket.Command == commands.Data():
        # new packet to store for customer, or data coming back from supplier
        # handled by service_backups() and service_supplier()
        Data(newpacket)

    elif newpacket.Command == commands.ListFiles():
        # customer wants list of their files
        # handled by service_supplier()
        ListFiles(newpacket, info)

    elif newpacket.Command == commands.Files():
        # supplier sent us list of files
        # handled by service_backups()
        Files(newpacket, info)

    elif newpacket.Command == commands.DeleteFile():
        # handled by service_supplier()
        DeleteFile(newpacket)

    elif newpacket.Command == commands.DeleteBackup():
        # handled by service_supplier()
        DeleteBackup(newpacket)

    elif newpacket.Command == commands.Correspondent():
        # TODO: contact asking for our current identity, not implemented yet
        Correspondent(newpacket)

    elif newpacket.Command == commands.Broadcast():
        # handled by service_broadcasting()
        Broadcast(newpacket, info)

    elif newpacket.Command == commands.Coin():
        # handled by service_accountant()
        Coin(newpacket, info)

    elif newpacket.Command == commands.RetrieveCoin():
        # handled by service_accountant()
        RetrieveCoin(newpacket, info)

    elif newpacket.Command == commands.Key():
        # handled by service_keys_registry()
        Key(newpacket, info)

    elif newpacket.Command == commands.Event():
        # handled by service_p2p_hookups()
        Event(newpacket, info)

    elif newpacket.Command == commands.Message():
        # handled by service_private_messages()
        Message(newpacket, info)

    elif newpacket.Command == commands.Contacts():
        # handled by service_customer_family()
        Contacts(newpacket, info)

    return False


def outbox(outpacket):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.outbox [%s] to %s" % (outpacket.Command, nameurl.GetName(outpacket.RemoteID)))
    return True

#------------------------------------------------------------------------------


def Ack(newpacket, info):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.Ack %s from [%s] at %s://%s with %d bytes payload" % (
            newpacket.PacketID, nameurl.GetName(newpacket.CreatorID),
            info.proto, info.host, len(newpacket.Payload)))


def SendAck(packettoack, response='', wide=False, callbacks={}, remote_idurl=None):
    if remote_idurl is None:
        remote_idurl = packettoack.OwnerID
    result = signed.Packet(
        Command=commands.Ack(),
        OwnerID=my_id.getLocalID(),
        CreatorID=my_id.getLocalID(),
        PacketID=packettoack.PacketID,
        Payload=response,
        RemoteID=remote_idurl,
    )
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendAck %s to %s  with %d bytes" % (
            result.PacketID, result.RemoteID, len(response)))
    gateway.outbox(result, wide=wide, callbacks=callbacks)
    return result


def SendAckNoRequest(remoteID, packetid, response='', wide=False, callbacks={}):
    result = signed.Packet(
        Command=commands.Ack(),
        OwnerID=my_id.getLocalID(),
        CreatorID=my_id.getLocalID(),
        PacketID=packetid,
        Payload=response,
        RemoteID=remoteID,
    )
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendAckNoRequest packetID=%s to %s  with %d bytes" % (
            result.PacketID, result.RemoteID, len(response)))
    gateway.outbox(result, wide=wide, callbacks=callbacks)

#------------------------------------------------------------------------------


def Fail(newpacket):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.Fail from [%s]: %s" % (newpacket.CreatorID, newpacket.Payload))


def SendFail(request, response='', remote_idurl=None, wide=False):
    if remote_idurl is None:
        remote_idurl = request.OwnerID
    result = signed.Packet(
        Command=commands.Fail(),
        OwnerID=my_id.getLocalID(),
        CreatorID=my_id.getLocalID(),
        PacketID=request.PacketID,  # This is needed to identify Fail on remote side
        Payload=response,
        RemoteID=remote_idurl,
    )
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendFail packetID=%s to %s  with %d bytes" % (
            result.PacketID, result.RemoteID, len(response)))
    gateway.outbox(result, wide=wide)
    return result


def SendFailNoRequest(remoteID, packetID, response=''):
    result = signed.Packet(
        Command=commands.Fail(),
        OwnerID=my_id.getLocalID(),
        CreatorID=my_id.getLocalID(),
        PacketID=packetID,
        Payload=response,
        RemoteID=remoteID,
    )
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendFailNoRequest packetID=%s to %s" % (result.PacketID, result.RemoteID))
    gateway.outbox(result)
    return result

#------------------------------------------------------------------------------


def Identity(newpacket, send_ack=True):
    """
    Normal node or Identity server is sending us a new copy of an identity for a contact of ours.
    Checks that identity is signed correctly.
    Sending requests to cache all sources (other identity servers) holding that identity.
    """
    # TODO:  move to service_gateway
    newxml = newpacket.Payload
    newidentity = identity.identity(xmlsrc=newxml)
    # SECURITY
    # check that identity is signed correctly
    # old public key matches new one
    # this is done in `UpdateAfterChecking()`
    idurl = newidentity.getIDURL()
    if not identitycache.HasKey(idurl):
        lg.info('received new identity: %s' % idurl)
    if not identitycache.UpdateAfterChecking(idurl, newxml):
        lg.warn("ERROR has non-Valid identity")
        return False
    # Now that we have ID we can check packet
    if not newpacket.Valid():
        # If not valid do nothing
        lg.warn("not Valid packet from %s" % idurl)
        return False
    # TODO: after receiving full list of identity sources we can call ALL OF THEM or those which are not cached yet.
    # this way we can be sure that even if first source (server holding your public key) is not responding
    # other sources still can give you required user info: public key, contacts, etc..
    # TODO: we can also consolidate few "idurl" sources for every public key - basically identify user by public key
    # something like:
    # for source in identitycache.FromCache(idurl).getSources():
    #     if source not in identitycache.FromCache(idurl):
    #         d = identitycache.immediatelyCaching(source)
    #         d.addCallback(lambda xml_src: identitycache.UpdateAfterChecking(idurl, xml_src))
    #         d.addErrback(lambda err: lg.warn('caching filed: %s' % err))
    if not send_ack:
        if _Debug:
            lg.out(_DebugLevel, "p2p_service.Identity idurl=%s   skip sending Ack()" % idurl)
        return True
    if newpacket.OwnerID == idurl:
        if _Debug:
            lg.out(_DebugLevel, "p2p_service.Identity idurl=%s   sending wide Ack()" % idurl)
    else:
        if _Debug:
            lg.out(_DebugLevel, "p2p_service.Identity idurl=%s   but packet ownerID=%s   sending wide Ack()" % (
                idurl, newpacket.OwnerID, ))
    # wide=True : a small trick to respond to all his contacts
    reactor.callLater(0, SendAck, newpacket, wide=True)  # @UndefinedVariable
    return True


def SendIdentity(remote_idurl, wide=False, timeout=10, callbacks={}):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendIdentity to %s wide=%s" % (nameurl.GetName(remote_idurl), wide, ))
    result = signed.Packet(
        Command=commands.Identity(),
        OwnerID=my_id.getLocalID(),
        CreatorID=my_id.getLocalID(),
        PacketID='identity',
        Payload=my_id.getLocalIdentity().serialize(),
        RemoteID=remote_idurl,
    )
    gateway.outbox(result, wide=wide, callbacks=callbacks, response_timeout=timeout)
    return result

#------------------------------------------------------------------------------


def RequestService(request, info):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.RequestService %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))


def SendRequestService(remote_idurl, service_name, json_payload={}, wide=False, callbacks={}, timeout=10):
    service_info = {
        'name': service_name,
        'payload': json_payload,
    }
    service_info_raw = serialization.DictToBytes(service_info)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendRequestService "%s" to %s with %r' % (
            service_name, remote_idurl, service_info))
    result = signed.Packet(
        commands.RequestService(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packetid.UniqueID(),
        service_info_raw,
        remote_idurl, )
    gateway.outbox(result, wide=wide, callbacks=callbacks, response_timeout=timeout)
    return result


def CancelService(request, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.CancelService %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))


def SendCancelService(remote_idurl, service_name, json_payload={}, wide=False, callbacks={}):
    service_info = {
        'name': service_name,
        'payload': json_payload,
    }
    service_info_raw = serialization.DictToBytes(service_info)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendCancelService "%s" to %s with %d bytes payload' % (
            service_name, remote_idurl, len(service_info_raw)))
    result = signed.Packet(
        commands.CancelService(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packetid.UniqueID(),
        service_info_raw,
        remote_idurl, )
    gateway.outbox(result, wide=wide, callbacks=callbacks)
    return result

#------------------------------------------------------------------------------

def ListFiles(request, info):
    """
    We will want to use this to see what needs to be resent, and expect normal
    case is very few missing.
    This is to build the ``Files()`` we are holding for a customer.
    You run service_list_files locally and send ListFiles() to your suppliers
    They repply fith Files() if service_supplier is started on their side
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.ListFiles %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))


def SendListFiles(target_supplier, customer_idurl=None, key_id=None, wide=False, callbacks={}):
    """
    This is used as a request method from your supplier : if you send him a ListFiles() packet
    he will reply you with a list of stored files in a Files() packet.
    """
    MyID = my_id.getLocalID()
    if not customer_idurl:
        customer_idurl = MyID
    if not str(target_supplier).isdigit():
        RemoteID = target_supplier
    else:
        RemoteID = contactsdb.supplier(target_supplier, customer_idurl=customer_idurl)
    if not RemoteID:
        lg.warn("RemoteID is empty target_supplier=%s" % str(target_supplier))
        return None
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendListFiles to %s" % nameurl.GetName(RemoteID))
    if not key_id:
        key_id = global_id.MakeGlobalID(idurl=customer_idurl, key_alias='customer')
    PacketID = "%s:%s" % (key_id, packetid.UniqueID(), )
    Payload = settings.ListFilesFormat()
    result = signed.Packet(
        Command=commands.ListFiles(),
        OwnerID=MyID,
        CreatorID=MyID,
        PacketID=PacketID,
        Payload=Payload,
        RemoteID=RemoteID,
    )
    gateway.outbox(result, wide=wide, callbacks=callbacks)
    return result

#------------------------------------------------------------------------------

def Files(request, info):
    """
    A directory list came in from some supplier or another customer.
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Files %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))


def SendFiles(idurl, raw_list_files_info, packet_id, callbacks={}, timeout=10, ):
    """
    Sending information about known files stored locally for given customer (if you are supplier).
    You can also send a list of your files to another user if you wish to grand access.
    This will not send any personal data : only file names, ids, versions, etc.
    So pass list of files in encrypted form in the `payload` or leave it empty.
    """
    MyID = my_id.getLocalID()
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendFiles %d bytes in packetID=%s' % (len(raw_list_files_info), packet_id))
        lg.out(_DebugLevel, '  to remoteID=%s' % idurl)
    newpacket = signed.Packet(
        Command=commands.Files(),
        OwnerID=MyID,
        CreatorID=MyID,
        PacketID=packet_id,
        Payload=raw_list_files_info,
        RemoteID=idurl,
    )
    result = gateway.outbox(newpacket, callbacks=callbacks, response_timeout=timeout)
    return result

#------------------------------------------------------------------------------


def Data(request):
    """
    This is when we 1) save my requested data to restore the backup 2) or save
    the customer file on our local HDD.
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Data %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))


def SendData(raw_data, ownerID, creatorID, remoteID, packetID, callbacks={}):
    """
    """
    # TODO:
    newpacket = signed.Packet(
        commands.Data(),
        ownerID,
        creatorID,
        packetID,
        raw_data,
        remoteID,
    )
    result = gateway.outbox(newpacket, callbacks=callbacks)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendData %d bytes in packetID=%s' % (
            len(raw_data), packetID))
        lg.out(_DebugLevel, '  to remoteID=%s  ownerID=%s  creatorID=%s' % (remoteID, ownerID, creatorID))
    return newpacket, result


def Retrieve(request):
    """
    Customer is asking us for data he previously stored with us.

    We send with ``outboxNoAck()`` method because he will ask again if
    he does not get it
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Retrieve %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))


def SendRetreive(ownerID, creatorID, packetID, remoteID, payload='', callbacks={}):
    """
    """
    newpacket = signed.Packet(
        commands.Retrieve(),
        ownerID,
        creatorID,
        packetID,
        payload,
        remoteID,
    )
    result = gateway.outbox(newpacket, callbacks=callbacks)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendRetreive packetID=%s' % packetID)
        lg.out(_DebugLevel, '  remoteID=%s  ownerID=%s  creatorID=%s' % (remoteID, ownerID, creatorID))
    return result

#------------------------------------------------------------------------------


def DeleteFile(request):
    """
    Delete one ore multiple files (that belongs to another user) or folders on my machine.
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.DeleteFile %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))


def SendDeleteFile(SupplierID, pathID):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendDeleteFile SupplierID=%s PathID=%s" % (SupplierID, pathID))
    MyID = my_id.getLocalID()
    PacketID = pathID
    RemoteID = SupplierID
    result = signed.Packet(commands.DeleteFile(), MyID, MyID, PacketID, "", RemoteID)
    gateway.outbox(result)
    return result


def SendDeleteListPaths(SupplierID, ListPathIDs):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendDeleteListPaths SupplierID=%s PathIDs: %s" % (SupplierID, ListPathIDs))
    MyID = my_id.getLocalID()
    PacketID = packetid.UniqueID()
    RemoteID = SupplierID
    Payload = '\n'.join(ListPathIDs)
    result = signed.Packet(commands.DeleteFile(), MyID, MyID, PacketID, Payload, RemoteID)
    gateway.outbox(result)
    return result

#------------------------------------------------------------------------------


def DeleteBackup(request):
    """
    Delete one or multiple backups on my machine.
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.DeleteBackup %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))


def SendDeleteBackup(SupplierID, BackupID):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendDeleteBackup SupplierID=%s  BackupID=%s" % (SupplierID, BackupID))
    MyID = my_id.getLocalID()
    PacketID = packetid.RemotePath(BackupID)
    RemoteID = SupplierID
    result = signed.Packet(commands.DeleteBackup(), MyID, MyID, PacketID, "", RemoteID)
    gateway.outbox(result)
    return result


def SendDeleteListBackups(SupplierID, ListBackupIDs):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendDeleteListBackups SupplierID=%s BackupIDs: %s" % (SupplierID, ListBackupIDs))
    MyID = my_id.getLocalID()
    PacketID = packetid.UniqueID()
    RemoteID = SupplierID
    Payload = '\n'.join(ListBackupIDs)
    result = signed.Packet(commands.DeleteBackup(), MyID, MyID, PacketID, Payload, RemoteID)
    gateway.outbox(result)
    return result

#------------------------------------------------------------------------------


def Correspondent(request):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Correspondent %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))
    # TODO: need to connect users here

#------------------------------------------------------------------------------

def RequestDeleteBackup(BackupID):
    """
    Need to send a "DeleteBackup" command to all suppliers.
    """
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RequestDeleteBackup with BackupID=" + str(BackupID))
    for supplier_idurl in contactsdb.suppliers(customer_idurl=packetid.CustomerIDURL(BackupID)):
        if not supplier_idurl:
            continue
        SendDeleteBackup(supplier_idurl, BackupID)


def RequestDeleteListBackups(backupIDs):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RequestDeleteListBackups wish to delete %d backups" % len(backupIDs))
    customers = {}
    for backupID in backupIDs:
        customer_idurl = packetid.CustomerIDURL(backupID)
        if customer_idurl not in customers:
            customers[customer_idurl] = set()
        customers[customer_idurl].add(backupID)
    for customer_idurl, backupID_set in customers.items():
        for supplier_idurl in contactsdb.suppliers(customer_idurl=customer_idurl):
            if supplier_idurl:
                SendDeleteListBackups(supplier_idurl, list(backupID_set))


def RequestDeleteListPaths(pathIDs):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RequestDeleteListPaths wish to delete %d paths" % len(pathIDs))
    customers = {}
    for pathID in pathIDs:
        customer_idurl = packetid.CustomerIDURL(pathID)
        if customer_idurl not in customers:
            customers[customer_idurl] = set()
        customers[customer_idurl].add(pathID)
    for customer_idurl, pathID_set in customers.items():
        for supplier_idurl in contactsdb.suppliers(customer_idurl=customer_idurl):
            if supplier_idurl:
                SendDeleteListPaths(supplier_idurl, list(pathID_set))


def CheckWholeBackup(BackupID):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.CheckWholeBackup with BackupID=" + BackupID)

#-------------------------------------------------------------------------------


def Broadcast(request, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Broadcast %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s  sender_idurl=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID, info.sender_idurl))


def SendBroadcastMessage(outpacket):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendBroadcastMessage to %s" % outpacket.RemoteID)
    gateway.outbox(outpacket)
    return outpacket

#------------------------------------------------------------------------------


def Coin(request, info):
    if _Debug:
        try:
            input_coins = serialization.BytesToDict(request.Payload, keys_to_text=True)
        except:
            lg.exc()
            input_coins = []
        lg.out(_DebugLevel, "p2p_service.Coin from %s with %d coins" % (
            nameurl.GetName(info.sender_idurl), len(input_coins), ))


def SendCoin(remote_idurl, coins, packet_id=None, wide=False, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendCoin to %s with %d records" % (remote_idurl, len(coins)))
    if packet_id is None:
        packet_id = packetid.UniqueID()
    outpacket = signed.Packet(
        commands.Coin(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packet_id,
        serialization.DictToBytes(coins, keys_to_text=True),
        remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks)
    return outpacket


def RetrieveCoin(request, info):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RetrieveCoin from %s : %s" % (
            nameurl.GetName(info.sender_idurl), request.Payload))


def SendRetrieveCoin(remote_idurl, query, wide=False, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendRetrieveCoin to %s" % remote_idurl)
    outpacket = signed.Packet(
        commands.RetrieveCoin(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packetid.UniqueID(),
        serialization.DictToBytes(query),
        remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks)
    return outpacket

#------------------------------------------------------------------------------

def Key(request, info):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Key %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s  sender_idurl=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID, info.sender_idurl))


def SendKey(remote_idurl, encrypted_key_data, packet_id=None, wide=False, callbacks={}, timeout=10, ):
    if packet_id is None:
        packet_id = packetid.UniqueID()
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendKey [%s] to %s with %d bytes encrypted key data" % (
            packet_id, remote_idurl, len(encrypted_key_data)))
    outpacket = signed.Packet(
        Command=commands.Key(),
        OwnerID=my_id.getLocalID(),
        CreatorID=my_id.getLocalID(),
        PacketID=packet_id,
        Payload=encrypted_key_data,
        RemoteID=remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks, response_timeout=timeout)
    return outpacket


def AuditKey(request, info):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.AuditKey %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s  sender_idurl=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID, info.sender_idurl))


def SendAuditKey(remote_idurl, encrypted_payload, packet_id=None, timeout=10, wide=False, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendAuditKey to %s with %d bytes in json payload data" % (
            remote_idurl, len(encrypted_payload)))
    if packet_id is None:
        packet_id = packetid.UniqueID()
    outpacket = signed.Packet(
        Command=commands.AuditKey(),
        OwnerID=my_id.getLocalID(),
        CreatorID=my_id.getLocalID(),
        PacketID=packet_id,
        Payload=encrypted_payload,
        RemoteID=remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks, response_timeout=timeout)
    return outpacket

#------------------------------------------------------------------------------

def Event(request, info):
    """
    """
    if _Debug:
        try:
            e_json = serialization.BytesToDict(request.Payload, keys_to_text=True)
            e_json['event_id']
            e_json['payload']
        except:
            lg.exc()
            return
        lg.out(_DebugLevel, "p2p_service.Event %s from %s with %d bytes in json" % (
            e_json['event_id'], info.sender_idurl, len(request.Payload), ))


def SendEvent(remote_idurl, event_id, payload=None,
              producer_id=None, message_id=None, created=None,
              packet_id=None, wide=False, callbacks={}, response_timeout=5):
    if packet_id is None:
        packet_id = packetid.UniqueID()
    e_json = {
        'event_id': event_id,
        'payload': payload,
    }
    if producer_id and message_id:
        e_json['producer_id'] = producer_id
        e_json['message_id'] = message_id
    if created:
        e_json['created'] = created
    e_json_src = serialization.DictToBytes(e_json)
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendEvent to %s with %d bytes message json data" % (
            remote_idurl, len(e_json_src)))
    outpacket = signed.Packet(
        Command=commands.Event(),
        OwnerID=my_id.getLocalID(),
        CreatorID=my_id.getLocalID(),
        PacketID=packet_id,
        Payload=e_json_src,
        RemoteID=remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks, response_timeout=response_timeout)
    return outpacket

#------------------------------------------------------------------------------

def Message(request, info):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Message %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))

#------------------------------------------------------------------------------

def Contacts(request, info):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Contacts %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (
            request.RemoteID, request.OwnerID, request.CreatorID))


def SendContacts(remote_idurl, json_payload={}, wide=False, callbacks={}):
    """
    """
    MyID = my_id.getLocalID()
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendContacts to %s" % nameurl.GetName(remote_idurl))
    PacketID = packetid.UniqueID()
    try:
        json_payload['type']
        json_payload['space']
    except:
        lg.err()
        return None
    Payload = serialization.DictToBytes(json_payload)
    result = signed.Packet(
        Command=commands.Contacts(),
        OwnerID=MyID,
        CreatorID=MyID,
        PacketID=PacketID,
        Payload=Payload,
        RemoteID=remote_idurl,
    )
    gateway.outbox(result, wide=wide, callbacks=callbacks)
    return result

#------------------------------------------------------------------------------
