#!/usr/bin/python
# p2p_service.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.contacts import contactsdb

from bitdust.main import settings

from bitdust.p2p import commands

from bitdust.lib import packetid
from bitdust.lib import nameurl
from bitdust.lib import serialization

from bitdust.crypt import signed
from bitdust.crypt import my_keys

from bitdust.transport import gateway
from bitdust.transport import callback

from bitdust.userid import my_id

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.init')
    callback.insert_outbox_filter_callback(0, outbox)


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.shutdown')
    callback.remove_outbox_filter_callback(outbox)


#------------------------------------------------------------------------------


def inbox(newpacket, info, status, error_message):
    #     if newpacket.CreatorID != my_id.getIDURL() and newpacket.RemoteID != my_id.getIDURL():
    #         # packet is NOT for us, skip
    #         return False

    if newpacket.Command == commands.Identity():
        # a response from remote node, typically handled in other places
        Identity(newpacket, info)

    elif newpacket.Command == commands.Ack():
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

    elif newpacket.Command == commands.AuditKey():
        # handled by service_keys_registry()
        AuditKey(newpacket, info)

    elif newpacket.Command == commands.Event():
        # handled by service_p2p_hookups()
        Event(newpacket, info)

    elif newpacket.Command == commands.Message():
        # handled by service_private_messages()
        Message(newpacket, info)

    elif newpacket.Command == commands.Contacts():
        # handled by service_customer_family()
        Contacts(newpacket, info)

    else:
        lg.warn('unexpected command received: %r from %r' % (newpacket, info))

    return False


def outbox(outpacket, wide, callbacks, target=None, route=None, response_timeout=None, keep_alive=True):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.outbox [%s:%s] to %s with route %r' % (outpacket.Command, outpacket.PacketID, nameurl.GetName(outpacket.RemoteID), route))
    return None


#------------------------------------------------------------------------------


def Ack(newpacket, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Ack %s from [%s] at %s://%s with %d bytes payload' % (newpacket.PacketID, nameurl.GetName(newpacket.CreatorID), info.proto, info.host, len(newpacket.Payload)))


def SendAck(packettoack, response='', wide=False, callbacks={}, remote_idurl=None):
    if remote_idurl is None:
        remote_idurl = packettoack.OwnerID
    result = signed.Packet(
        Command=commands.Ack(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packettoack.PacketID,
        Payload=response,
        RemoteID=remote_idurl,
    )
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendAck %s to %s  with %d bytes' % (result.PacketID, result.RemoteID, len(response)))
    gateway.outbox(result, wide=wide, callbacks=callbacks)
    return result


def SendAckNoRequest(remoteID, packetid, response='', wide=False, callbacks={}):
    result = signed.Packet(
        Command=commands.Ack(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packetid,
        Payload=response,
        RemoteID=remoteID,
    )
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendAckNoRequest packetID=%s to %s  with %d bytes' % (result.PacketID, result.RemoteID, len(response)))
    gateway.outbox(result, wide=wide, callbacks=callbacks)
    return result


#------------------------------------------------------------------------------


def Fail(newpacket):
    if _Debug:
        if newpacket.Payload:
            lg.warn('%r received from [%s] in %r' % (newpacket.Payload, newpacket.CreatorID, newpacket))
        else:
            lg.out(_DebugLevel, 'p2p_service.Fail from %s|%s packetID=%s : %s' % (newpacket.CreatorID, newpacket.OwnerID, newpacket.PacketID, newpacket.Payload))


def SendFail(request, response='', remote_idurl=None, wide=False):
    if remote_idurl is None:
        remote_idurl = request.OwnerID
    result = signed.Packet(
        Command=commands.Fail(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=request.PacketID,  # This is needed to identify Fail on remote side
        Payload=response,
        RemoteID=remote_idurl,
    )
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendFail packetID=%s to %s  with %d bytes' % (result.PacketID, result.RemoteID, len(response)))
    gateway.outbox(result, wide=wide)
    return result


def SendFailNoRequest(remoteID, packetID, response=''):
    result = signed.Packet(
        Command=commands.Fail(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packetID,
        Payload=response,
        RemoteID=remoteID,
    )
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendFailNoRequest packetID=%s to %s' % (result.PacketID, result.RemoteID))
    gateway.outbox(result)
    return result


#------------------------------------------------------------------------------


def Identity(newpacket, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Identity %s from [%s] at %s://%s with %d bytes payload' % (newpacket.PacketID, nameurl.GetName(newpacket.CreatorID), info.proto, info.host, len(newpacket.Payload)))


#     """
#     Normal node or Identity server is sending us a new copy of an identity for a contact of ours.
#     Checks that identity is signed correctly.
#     Sending requests to cache all sources (other identity servers) holding that identity.
#     """
#     # TODO:  move to service_gateway
#     newxml = newpacket.Payload
#     newidentity = identity.identity(xmlsrc=newxml)
#     # SECURITY
#     # check that identity is signed correctly
#     # old public key matches new one
#     # this is done in `UpdateAfterChecking()`
#     idurl = newidentity.getIDURL()
#     if not identitycache.HasKey(idurl):
#         lg.info('received new identity %s rev %r' % (idurl, newidentity.getRevisionValue()))
#     if not identitycache.UpdateAfterChecking(idurl, newxml):
#         lg.warn("ERROR has non-Valid identity")
#         return False
#     if my_id.isLocalIdentityReady():
#         if newidentity.getPublicKey() == my_id.getLocalIdentity().getPublicKey():
#             if newidentity.getRevisionValue() > my_id.getLocalIdentity().getRevisionValue():
#                 lg.warn('received my own identity from another user, but with higher revision number')
#                 reactor.callLater(0, my_id.rebuildLocalIdentity, new_revision=newidentity.getRevisionValue() + 1)  # @UndefinedVariable
#                 return False
#     latest_identity = id_url.get_latest_ident(newidentity.getPublicKey())
#     if latest_identity:
#         if latest_identity.getRevisionValue() > newidentity.getRevisionValue():
#             # check if received identity is the most recent revision number we every saw for that remote user
#             # in case we saw same identity with higher revision number need to reply with Fail packet and notify user
#             # this may happen after identity restore - the user starts counting revision number from 0
#             # but other nodes already store previous copies, user just need to jump to the most recent revision number
#             lg.warn('received new identity with out-dated revision number from %r' % idurl)
#             ident_packet = signed.Packet(
#                 Command=commands.Identity(),
#                 OwnerID=latest_identity.getIDURL(),
#                 CreatorID=latest_identity.getIDURL(),
#                 PacketID='identity:%s' % packetid.UniqueID(),
#                 Payload=latest_identity.serialize(),
#                 RemoteID=idurl,
#             )
#             reactor.callLater(0, packet_out.create, outpacket=ident_packet, wide=True, callbacks={}, keep_alive=False)  # @UndefinedVariable
#             return False
#     # Now that we have ID we can check the packet
#     if not newpacket.Valid():
#         # If not valid do nothing
#         lg.warn("not Valid packet from %s" % idurl)
#         return False
#     if not send_ack:
#         if _Debug:
#             lg.out(_DebugLevel, "p2p_service.Identity %s  idurl=%s  remoteID=%r  skip sending Ack()" % (
#                 newpacket.PacketID, idurl, newpacket.RemoteID))
#         return True
#     if newpacket.OwnerID == idurl:
#         if _Debug:
#             lg.out(_DebugLevel, "p2p_service.Identity %s  idurl=%s  remoteID=%r  sending wide Ack()" % (
#                 newpacket.PacketID, idurl, newpacket.RemoteID))
#     else:
#         if _Debug:
#             lg.out(_DebugLevel, "p2p_service.Identity %s  idurl=%s  remoteID=%r  but packet ownerID=%s   sending wide Ack()" % (
#                 newpacket.PacketID, idurl, newpacket.RemoteID, newpacket.OwnerID, ))
#     # wide=True : a small trick to respond to all known contacts of the remote user
#     reactor.callLater(0, SendAck, newpacket, wide=True)  # @UndefinedVariable
#     return True


def SendIdentity(remote_idurl, wide=False, timeout=None, callbacks={}):
    if timeout is None:
        timeout = settings.P2PTimeOut()
    packet_id = 'identity:%s' % packetid.UniqueID()
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendIdentity to %s wide=%s packet_id=%r' % (nameurl.GetName(remote_idurl), wide, packet_id))
    result = signed.Packet(
        Command=commands.Identity(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packet_id,
        Payload=my_id.getLocalIdentity().serialize(),
        RemoteID=remote_idurl,
    )
    gateway.outbox(result, wide=wide, callbacks=callbacks, response_timeout=timeout)
    return result


#------------------------------------------------------------------------------


def RequestService(request, info):
    if _Debug:
        try:
            service_info = serialization.BytesToDict(request.Payload)
        except:
            lg.exc()
            service_info = {}
        lg.out(_DebugLevel, 'p2p_service.RequestService %s with "%s" in %d bytes' % (request.PacketID, service_info.get('name', 'unknown service name'), len(request.Payload)))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))


def SendRequestService(remote_idurl, service_name, json_payload={}, wide=False, callbacks={}, timeout=None, packet_id=None):
    if timeout is None:
        timeout = settings.P2PTimeOut()
    service_info = {
        'name': service_name,
        'payload': json_payload,
    }
    service_info_raw = serialization.DictToBytes(service_info)
    if packet_id is None:
        packet_id = packetid.UniqueID()
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendRequestService "%s" to %s with %d bytes pid:%s timeout:%r' % (service_name, remote_idurl, len(service_info_raw), packet_id, timeout))
    result = signed.Packet(
        Command=commands.RequestService(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packet_id,
        Payload=service_info_raw,
        RemoteID=remote_idurl,
    )
    gateway.outbox(result, wide=wide, callbacks=callbacks, response_timeout=timeout)
    return result


def CancelService(request, info):
    if _Debug:
        try:
            service_info = serialization.BytesToDict(request.Payload)
        except:
            lg.exc()
            service_info = {}
        lg.out(_DebugLevel, 'p2p_service.CancelService %s with "%s" in %d bytes' % (request.PacketID, service_info.get('name', 'unknown service name'), len(request.Payload)))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))


def SendCancelService(remote_idurl, service_name, json_payload={}, wide=False, callbacks={}, timeout=None):
    if timeout is None:
        timeout = settings.P2PTimeOut()
    service_info = {
        'name': service_name,
        'payload': json_payload,
    }
    service_info_raw = serialization.DictToBytes(service_info)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendCancelService "%s" to %s with %d bytes payload' % (service_name, remote_idurl, len(service_info_raw)))
    result = signed.Packet(
        Command=commands.CancelService(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packetid.UniqueID(),
        Payload=service_info_raw,
        RemoteID=remote_idurl,
    )
    gateway.outbox(result, wide=wide, callbacks=callbacks, response_timeout=timeout)
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
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))


def SendListFiles(target_supplier, customer_idurl=None, key_id=None, query_items=[], wide=False, callbacks={}, timeout=None):
    """
    This is used as a request method from your supplier : if you send him a ListFiles() packet
    he will reply you with a list of stored files in a Files() packet.
    """
    if timeout is None:
        timeout = settings.P2PTimeOut()
    MyID = my_id.getIDURL()
    if not customer_idurl:
        customer_idurl = MyID
    if not str(target_supplier).isdigit():
        RemoteID = target_supplier
    else:
        RemoteID = contactsdb.supplier(target_supplier, customer_idurl=customer_idurl)
    if not RemoteID:
        lg.warn('RemoteID is empty target_supplier=%s' % str(target_supplier))
        return None
    if not key_id:
        # key_id = global_id.MakeGlobalID(idurl=customer_idurl, key_alias='customer')
        # TODO: due to issue with "customer" key backup/restore decided to always use my "master" key
        # to retrieve my list files info from supplier
        # expect remote user always poses my master public key from my identity.
        # probably require more work to build more reliable solution without using my master key at all
        # when my identity rotated supplier first needs to receive my new identity and then sending ListFiles()
        key_id = my_id.getGlobalID(key_alias='master')
    else:
        key_id = my_keys.latest_key_id(key_id)
    if not my_keys.is_key_registered(key_id) or not my_keys.is_key_private(key_id):
        lg.warn('key %r not exist or public, my "master" key to be used with ListFiles() packet' % key_id)
        key_id = my_id.getGlobalID(key_alias='master')
    PacketID = '%s:%s' % (
        key_id,
        packetid.UniqueID(),
    )
    if not query_items:
        query_items = ['*']
    Payload = serialization.DictToBytes({'items': query_items})
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendListFiles %r to %r of customer %r with query : %r' % (PacketID, nameurl.GetName(RemoteID), nameurl.GetName(customer_idurl), query_items))
    result = signed.Packet(
        Command=commands.ListFiles(),
        OwnerID=MyID,
        CreatorID=MyID,
        PacketID=PacketID,
        Payload=Payload,
        RemoteID=RemoteID,
    )
    gateway.outbox(result, wide=wide, callbacks=callbacks, response_timeout=timeout)
    return result


#------------------------------------------------------------------------------


def Files(request, info):
    """
    A directory list came in from some supplier or another customer.
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Files %d bytes in [%s] from %s by %s|%s' % (len(request.Payload), request.PacketID, nameurl.GetName(request.RemoteID), nameurl.GetName(request.OwnerID), nameurl.GetName(request.CreatorID)))


def SendFiles(idurl, raw_list_files_info, packet_id, callbacks={}, timeout=None):
    """
    Sending information about known files stored locally for given customer (if you are supplier).
    You can also send a list of your files to another user if you wish to grand access.
    This will not send any personal data : only file names, ids, versions, etc.
    So pass list of files in encrypted form in the `payload` or leave it empty.
    """
    if timeout is None:
        timeout = settings.P2PTimeOut()
    MyID = my_id.getIDURL()
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
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))


def SendData(raw_data, ownerID, creatorID, remoteID, packetID, callbacks={}):
    newpacket = signed.Packet(
        Command=commands.Data(),
        OwnerID=ownerID,
        CreatorID=creatorID,
        PacketID=packetID,
        Payload=raw_data,
        RemoteID=remoteID,
    )
    result = gateway.outbox(newpacket, callbacks=callbacks)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendData %d bytes in packetID=%s' % (len(raw_data), packetID))
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
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))


def SendRetreive(ownerID, creatorID, packetID, remoteID, payload='', response_timeout=None, callbacks={}):
    newpacket = signed.Packet(
        Command=commands.Retrieve(),
        OwnerID=ownerID,
        CreatorID=creatorID,
        PacketID=packetID,
        Payload=payload,
        RemoteID=remoteID,
    )
    result = gateway.outbox(newpacket, callbacks=callbacks, response_timeout=response_timeout)
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
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))


def SendDeleteFile(SupplierID, pathID):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendDeleteFile SupplierID=%s PathID=%s' % (SupplierID, pathID))
    MyID = my_id.getIDURL()
    PacketID = pathID
    RemoteID = SupplierID
    result = signed.Packet(
        Command=commands.DeleteFile(),
        OwnerID=MyID,
        CreatorID=MyID,
        PacketID=PacketID,
        Payload='',
        RemoteID=RemoteID,
    )
    gateway.outbox(result)
    return result


def SendDeleteListPaths(SupplierID, ListPathIDs):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendDeleteListPaths SupplierID=%s PathIDs: %s' % (SupplierID, ListPathIDs))
    MyID = my_id.getIDURL()
    PacketID = packetid.UniqueID()
    RemoteID = SupplierID
    Payload = '\n'.join(ListPathIDs)
    result = signed.Packet(
        Command=commands.DeleteFile(),
        OwnerID=MyID,
        CreatorID=MyID,
        PacketID=PacketID,
        Payload=Payload,
        RemoteID=RemoteID,
    )
    gateway.outbox(result)
    return result


#------------------------------------------------------------------------------


def DeleteBackup(request):
    """
    Delete one or multiple backups on my machine.
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.DeleteBackup %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))


def SendDeleteBackup(SupplierID, BackupID):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendDeleteBackup SupplierID=%s  BackupID=%s' % (SupplierID, BackupID))
    MyID = my_id.getIDURL()
    PacketID = packetid.RemotePath(BackupID)
    RemoteID = SupplierID
    result = signed.Packet(
        Command=commands.DeleteBackup(),
        OwnerID=MyID,
        CreatorID=MyID,
        PacketID=PacketID,
        Payload='',
        RemoteID=RemoteID,
    )
    gateway.outbox(result)
    return result


def SendDeleteListBackups(SupplierID, ListBackupIDs):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendDeleteListBackups SupplierID=%s BackupIDs: %s' % (SupplierID, ListBackupIDs))
    MyID = my_id.getIDURL()
    PacketID = packetid.UniqueID()
    RemoteID = SupplierID
    Payload = '\n'.join(ListBackupIDs)
    result = signed.Packet(
        Command=commands.DeleteBackup(),
        OwnerID=MyID,
        CreatorID=MyID,
        PacketID=PacketID,
        Payload=Payload,
        RemoteID=RemoteID,
    )
    gateway.outbox(result)
    return result


#------------------------------------------------------------------------------


def Correspondent(request):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Correspondent %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))
    # TODO: need to connect users here


#------------------------------------------------------------------------------


def RequestDeleteBackup(BackupID):
    """
    Need to send a "DeleteBackup" command to all suppliers.
    """
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.RequestDeleteBackup with BackupID=' + str(BackupID))
    for supplier_idurl in contactsdb.suppliers(customer_idurl=packetid.CustomerIDURL(BackupID)):
        if not supplier_idurl:
            continue
        SendDeleteBackup(supplier_idurl, BackupID)


def RequestDeleteListBackups(backupIDs):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.RequestDeleteListBackups wish to delete %d backups' % len(backupIDs))
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
        lg.out(_DebugLevel, 'p2p_service.RequestDeleteListPaths wish to delete %d paths' % len(pathIDs))
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
        lg.out(_DebugLevel, 'p2p_service.CheckWholeBackup with BackupID=' + BackupID)


#-------------------------------------------------------------------------------


def Broadcast(request, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Broadcast %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s  sender_idurl=%s' % (request.RemoteID, request.OwnerID, request.CreatorID, info.sender_idurl))


def SendBroadcastMessage(outpacket):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendBroadcastMessage to %s' % outpacket.RemoteID)
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
        lg.out(_DebugLevel, 'p2p_service.Coin from %s with %d coins' % (nameurl.GetName(info.sender_idurl), len(input_coins)))


def SendCoin(remote_idurl, coins, packet_id=None, wide=False, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendCoin to %s with %d records' % (remote_idurl, len(coins)))
    if packet_id is None:
        packet_id = packetid.UniqueID()
    outpacket = signed.Packet(
        Command=commands.Coin(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packet_id,
        Payload=serialization.DictToBytes(coins, keys_to_text=True),
        RemoteID=remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks)
    return outpacket


def RetrieveCoin(request, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.RetrieveCoin from %s : %s' % (nameurl.GetName(info.sender_idurl), request.Payload))


def SendRetrieveCoin(remote_idurl, query, wide=False, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendRetrieveCoin to %s' % remote_idurl)
    outpacket = signed.Packet(
        Command=commands.RetrieveCoin(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packetid.UniqueID(),
        Payload=serialization.DictToBytes(query),
        RemoteID=remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks)
    return outpacket


#------------------------------------------------------------------------------


def Key(request, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Key %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from senderID=%s to remoteID=%s  ownerID=%s  creatorID=%s  ' % (info.sender_idurl, request.RemoteID, request.OwnerID, request.CreatorID))


def SendKey(
    remote_idurl,
    encrypted_key_data,
    packet_id=None,
    wide=False,
    callbacks={},
    timeout=None,
):
    if timeout is None:
        timeout = settings.P2PTimeOut()
    if packet_id is None:
        packet_id = packetid.UniqueID()
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendKey [%s] to %s with %d bytes encrypted key data' % (packet_id, remote_idurl, len(encrypted_key_data)))
    outpacket = signed.Packet(
        Command=commands.Key(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packet_id,
        Payload=encrypted_key_data,
        RemoteID=remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks, response_timeout=timeout)
    return outpacket


def AuditKey(request, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.AuditKey %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s  sender_idurl=%s' % (request.RemoteID, request.OwnerID, request.CreatorID, info.sender_idurl))


def SendAuditKey(remote_idurl, encrypted_payload, packet_id=None, timeout=None, wide=False, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendAuditKey to %s with %d bytes in json payload data' % (remote_idurl, len(encrypted_payload)))
    if timeout is None:
        timeout = settings.P2PTimeOut()
    if packet_id is None:
        packet_id = packetid.UniqueID()
    outpacket = signed.Packet(
        Command=commands.AuditKey(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packet_id,
        Payload=encrypted_payload,
        RemoteID=remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks, response_timeout=timeout)
    return outpacket


#------------------------------------------------------------------------------


def Event(request, info):
    if _Debug:
        try:
            e_json = serialization.BytesToDict(request.Payload, keys_to_text=True)
            e_json['event_id']
            e_json['payload']
        except:
            lg.exc()
            return
        lg.out(_DebugLevel, 'p2p_service.Event %s from %s with %d bytes in json' % (e_json['event_id'], info.sender_idurl, len(request.Payload)))


def SendEvent(remote_idurl, event_id, payload=None, producer_id=None, consumer_id=None, queue_id=None, message_id=None, created=None, packet_id=None, wide=False, callbacks={}, response_timeout=None):
    if response_timeout is None:
        response_timeout = settings.P2PTimeOut()
    if packet_id is None:
        packet_id = packetid.UniqueID()
    e_json = {
        'event_id': event_id,
        'payload': payload,
    }
    if producer_id is not None:
        e_json['producer_id'] = producer_id
    if consumer_id is not None:
        e_json['consumer_id'] = consumer_id
    if queue_id is not None:
        e_json['queue_id'] = queue_id
    if message_id is not None:
        e_json['message_id'] = message_id
    if created is not None:
        e_json['created'] = created
    e_json_src = serialization.DictToBytes(e_json)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendEvent to %s with %d bytes message json data' % (remote_idurl, len(e_json_src)))
    outpacket = signed.Packet(
        Command=commands.Event(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packet_id,
        Payload=e_json_src,
        RemoteID=remote_idurl,
    )
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks, response_timeout=response_timeout)
    return outpacket


#------------------------------------------------------------------------------


def Message(request, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Message %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))


def SendMessage(remote_idurl, packet_id=None, payload=None, wide=True, callbacks={}, response_timeout=None):
    if packet_id is None:
        packet_id = packetid.UniqueID()
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendMessage to %s with packet_id=%s' % (nameurl.GetName(remote_idurl), packet_id))
    outpacket = signed.Packet(
        Command=commands.Message(),
        OwnerID=my_id.getIDURL(),
        CreatorID=my_id.getIDURL(),
        PacketID=packet_id,
        Payload=payload,
        RemoteID=remote_idurl,
    )
    result = gateway.outbox(outpacket, wide=wide, callbacks=callbacks, response_timeout=response_timeout)
    return result, outpacket


#------------------------------------------------------------------------------


def Contacts(request, info):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.Contacts %d bytes in [%s]' % (len(request.Payload), request.PacketID))
        lg.out(_DebugLevel, '  from remoteID=%s  ownerID=%s  creatorID=%s' % (request.RemoteID, request.OwnerID, request.CreatorID))


def SendContacts(remote_idurl, json_payload={}, wide=False, callbacks={}):
    MyID = my_id.getIDURL()
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.SendContacts to %s' % nameurl.GetName(remote_idurl))
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
