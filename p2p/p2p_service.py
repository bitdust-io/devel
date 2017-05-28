#!/usr/bin/python
# p2p_service.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys
import json

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in p2p_service.py')

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from userid import my_id
from contacts import contactsdb

from userid import identity

from contacts import identitycache

from p2p import commands

from lib import packetid
from lib import nameurl

from crypt import signed

from main import settings

from transport import gateway
from transport import callback

from services import driver

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.init')
    callback.append_inbox_callback(inbox)


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_service.shutdown')
    callback.remove_inbox_callback(inbox)

#------------------------------------------------------------------------------


def inbox(newpacket, info, status, error_message):
    """
    """
    if newpacket.CreatorID != my_id.getLocalID() and newpacket.RemoteID != my_id.getLocalID():
        # packet is NOT for us, skip
        return False

    commandhandled = False
    if newpacket.Command == commands.Ack():
        # a response from remote node, typically handled in other places
        Ack(newpacket, info)
        commandhandled = False
    elif newpacket.Command == commands.Fail():
        # some operation was failed on other side
        Fail(newpacket)
        commandhandled = False
    elif newpacket.Command == commands.Retrieve():
        # retrieve some packet customer stored with us
        Retrieve(newpacket)
        commandhandled = True
    elif newpacket.Command == commands.RequestService():
        # other node send us a request to get some service
        RequestService(newpacket, info)
        commandhandled = True
    elif newpacket.Command == commands.CancelService():
        # other node wants to stop the service we gave him
        CancelService(newpacket, info)
        commandhandled = True
    elif newpacket.Command == commands.Data():
        # new packet to store for customer
        commandhandled = Data(newpacket)
    elif newpacket.Command == commands.ListFiles():
        # customer wants list of their files
        ListFiles(newpacket)
        commandhandled = True
    elif newpacket.Command == commands.Files():
        # supplier sent us list of files
        Files(newpacket, info)
        commandhandled = True
    elif newpacket.Command == commands.DeleteFile():
        # will Delete a customer file for them
        DeleteFile(newpacket)
        commandhandled = True
    elif newpacket.Command == commands.DeleteBackup():
        # will Delete all files starting in a backup
        DeleteBackup(newpacket)
        commandhandled = True
#     elif newpacket.Command == commands.RequestIdentity():
#         # contact asking for our current identity
#         RequestIdentity(newpacket)
#         commandhandled = True
    elif newpacket.Command == commands.Message():
        # contact asking for our current identity
        if driver.is_started('service_private_messages'):
            from chat import message
            message.Message(newpacket)
            commandhandled = True
    elif newpacket.Command == commands.Correspondent():
        # contact asking for our current identity
        Correspondent(newpacket)
        commandhandled = True
    elif newpacket.Command == commands.Broadcast():
        # handled by service_broadcasting()
        Broadcast(newpacket, info)
        commandhandled = False
    elif newpacket.Command == commands.Coin():
        # handled by service_accountant()
        Coin(newpacket, info)
        commandhandled = False
    elif newpacket.Command == commands.RetreiveCoin():
        # handled by service_accountant()
        RetreiveCoin(newpacket, info)
        commandhandled = False

    return commandhandled


def outbox(outpacket):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.outbox [%s] to %s" % (outpacket.Command, nameurl.GetName(outpacket.RemoteID)))
    return True

#------------------------------------------------------------------------------


def constructFilename(customerID, packetID):
    customerDirName = nameurl.UrlFilename(customerID)
    customersDir = settings.getCustomersFilesDir()
    if not os.path.exists(customersDir):
        bpio._dir_make(customersDir)
    ownerDir = os.path.join(customersDir, customerDirName)
    if not os.path.exists(ownerDir):
        bpio._dir_make(ownerDir)
    filename = os.path.join(ownerDir, packetID)
    return filename


def makeFilename(customerID, packetID):
    """
    Must be a customer, and then we make full path filename for where this
    packet is stored locally.
    """
    if not packetid.Valid(packetID):  # SECURITY
        if packetID not in [settings.BackupInfoFileName(),
                            settings.BackupInfoFileNameOld(),
                            settings.BackupInfoEncryptedFileName(),
                            settings.BackupIndexFileName()]:
            # lg.out(1, "p2p_service.makeFilename ERROR failed packetID format: " + packetID )
            return ''
    if not contactsdb.is_customer(customerID):  # SECURITY
        lg.warn("%s is not a customer" % (customerID))
        return ''
    return constructFilename(customerID, packetID)

#------------------------------------------------------------------------------


def Ack(newpacket, info):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.Ack %s from [%s] at %s://%s : %s" % (
            newpacket.PacketID, nameurl.GetName(newpacket.CreatorID),
            info.proto, info.host, newpacket.Payload))


def SendAck(packettoack, response='', wide=False, callbacks={}, packetid=None):
    result = signed.Packet(
        commands.Ack(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packetid or packettoack.PacketID,
        response,
        packettoack.OwnerID)
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendAck %s to %s    response: %s ..." % (result.PacketID, result.RemoteID, str(response)[:15]))
    gateway.outbox(result, wide=wide, callbacks=callbacks)
    return result


def SendAckNoRequest(remoteID, packetid, response='', wide=False, callbacks={}):
    result = signed.Packet(
        commands.Ack(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packetid,
        response,
        remoteID)
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendAckNoRequest %s to %s    response: %s ..." % (result.PacketID, result.RemoteID, str(response)[:15]))
    gateway.outbox(result, wide=wide, callbacks=callbacks)

#------------------------------------------------------------------------------


def Fail(newpacket):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.Fail from [%s]: %s" % (newpacket.CreatorID, newpacket.Payload))


def SendFail(request, response='', remote_idurl=None):
    if remote_idurl is None:
        remote_idurl = request.OwnerID
    result = signed.Packet(
        commands.Fail(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        request.PacketID,  # This is needed to identify Fail on remote side
        response,
        remote_idurl,
    )
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendFail %s to %s    response: %s ..." % (
            result.PacketID, result.RemoteID, str(response)[:40]))
    gateway.outbox(result)
    return result


def SendFailNoRequest(remoteID, packetID, response):
    result = signed.Packet(
        commands.Fail(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packetID,
        response,
        remoteID,
    )
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendFailNoRequest %s to %s" % (result.PacketID, result.RemoteID))
    gateway.outbox(result)
    return result

#------------------------------------------------------------------------------


def Identity(newpacket):
    """
    Contact or identity server is sending us a new copy of an identity for a
    contact of ours.

    Checks that identity is signed correctly.
    """
    newxml = newpacket.Payload
    newidentity = identity.identity(xmlsrc=newxml)
    # SECURITY
    # check that identity is signed correctly
    # old public key matches new one
    # this is done in `UpdateAfterChecking()`
    idurl = newidentity.getIDURL()
    if not identitycache.UpdateAfterChecking(idurl, newxml):
        lg.warn("ERROR has non-Valid identity")
        return False
    # Now that we have ID we can check packet
    if not newpacket.Valid():
        # If not valid do nothing
        lg.warn("not Valid packet from %s" % idurl)
        return False
    if newpacket.OwnerID == idurl:
        # TODO: this needs to be moved to a service
        # wide=True : a small trick to respond to all contacts if we receive pings
        SendAck(newpacket, wide=True)
        if _Debug:
            lg.out(_DebugLevel, "p2p_service.Identity from [%s], sent wide Acks" % nameurl.GetName(idurl))
    else:
        if _Debug:
            lg.out(_DebugLevel, "p2p_service.Identity from [%s]" % nameurl.GetName(idurl))
    return True


def _RequestIdentity(request):
    """
    Someone is requesting a copy of our current identity.

    Already verified that they are a contact. Can also be used as a sort
    of "ping" test to make sure we are alive.
    """
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RequestIdentity from %s" % request.OwnerID)
    MyID = my_id.getLocalID()
    RemoteID = request.OwnerID
    PacketID = request.PacketID
    identitystr = my_id.getLocalIdentity().serialize()
    result = signed.Packet(commands.Identity(), MyID, MyID, PacketID, identitystr, RemoteID)
    gateway.outbox(result, False)


def SendIdentity(remote_idurl, wide=False, callbacks={}):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendIdentity to %s" % nameurl.GetName(remote_idurl))
    result = signed.Packet(
        commands.Identity(), my_id.getLocalID(),
        my_id.getLocalID(), 'identity',
        my_id.getLocalIdentity().serialize(), remote_idurl)
    gateway.outbox(result, wide=wide, callbacks=callbacks)
    return result

#------------------------------------------------------------------------------


def RequestService(request, info):
    """
    """
    if len(request.Payload) > 1024 * 10:
        return SendFail(request, 'too long payload')
    # TODO: move code into driver module, use callback module here instead of direct call
    words = request.Payload.split(' ')
    if len(words) < 1:
        lg.warn("got wrong payload in %s" % request)
        return SendFail(request, 'wrong payload')
    service_name = words[0]
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RequestService %s : %s" % (request.OwnerID, service_name))
    if not driver.is_exist(service_name):
        lg.warn("got wrong payload in %s" % service_name)
        return SendFail(request, 'service %s not exist' % service_name)
    if not driver.is_started(service_name):
        return SendFail(request, 'service %s is off' % service_name)
    return driver.request(service_name, request, info)


def SendRequestService(remote_idurl, service_info, wide=False, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendRequestService to %s [%s]" % (
            nameurl.GetName(remote_idurl), service_info.replace('\n', ' ')[:40]))
    result = signed.Packet(
        commands.RequestService(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packetid.UniqueID(),
        service_info,
        remote_idurl)
    gateway.outbox(result, wide=wide, callbacks=callbacks)
    return result


def CancelService(request, info):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.CancelService")
    # TODO: move code into driver module, use callback module here instead of direct call
    words = request.Payload.split(' ')
    if len(words) < 1:
        lg.warn("got wrong payload in %s" % request)
        return SendFail(request, 'wrong payload')
    service_name = words[0]
    # TODO: add validation
    if not driver.is_exist(service_name):
        lg.warn("got wrong payload in %s" % request)
        return SendFail(request, 'service %s not exist' % service_name)
    if not driver.is_started(service_name):
        return SendFail(request, 'service %s is off' % service_name)
    return driver.cancel(service_name, request, info)


def SendCancelService(remote_idurl, service_info, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendCancelService [%s]" % service_info.replace('\n', ' ')[:40])
    result = signed.Packet(commands.CancelService(), my_id.getLocalID(), my_id.getLocalID(),
                           packetid.UniqueID(), service_info, remote_idurl)
    gateway.outbox(result, callbacks=callbacks)
    return result

#------------------------------------------------------------------------------

def ListFiles(request):
    """
    We will want to use this to see what needs to be resent, and expect normal
    case is very few missing.

    This is to build the ``Files()`` we are holding for a customer.
    """
    if not driver.is_started('service_supplier'):
        return SendFail(request, 'supplier service is off')
    # TODO: use callback module here instead of direct call
    from supplier import list_files
    return list_files.send(request.OwnerID, request.PacketID, request.Payload)


def Files(newpacket, info):
    """
    A directory list came in from some supplier.
    """
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.Files from [%s] at %s://%s" % (
            nameurl.GetName(newpacket.OwnerID), info.proto, info.host))
    # TODO: use callback module here instead of direct call
    from storage import backup_control
    backup_control.IncomingSupplierListFiles(newpacket)

#------------------------------------------------------------------------------


def Data(request):
    """
    This is when we 1) save my requested data to restore the backup 2) or save
    the customer file on our local HDD.
    """
    # 1. this is our Data!
    if request.OwnerID == my_id.getLocalID():
        if _Debug:
            lg.out(_DebugLevel, "p2p_service.Data %r for us from %s" % (
                request, nameurl.GetName(request.RemoteID)))
        if driver.is_started('service_backups'):
            if request.PacketID in [settings.BackupIndexFileName(), ]:
                from storage import backup_control
                backup_control.IncomingSupplierBackupIndex(request)
                return True
        return False
    # 2. this Data is not belong to us
    if not driver.is_started('service_supplier'):
        return SendFail(request, 'supplier service is off')
    if not contactsdb.is_customer(request.OwnerID):  # SECURITY
        lg.warn("%s not a customer, packetID=%s" % (request.OwnerID, request.PacketID))
        SendFail(request, 'not a customer')
        return
    filename = makeFilename(request.OwnerID, request.PacketID)
    if filename == "":
        lg.warn("got empty filename, bad customer or wrong packetID? ")
        SendFail(request, 'empty filename')
        return
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        try:
            bpio._dirs_make(dirname)
        except:
            lg.warn("ERROR can not create sub dir " + dirname)
            SendFail(request, 'write error')
            return
    data = request.Serialize()
    donated_bytes = settings.getDonatedBytes()
    if not os.path.isfile(settings.CustomersSpaceFile()):
        bpio._write_dict(settings.CustomersSpaceFile(), {'free': donated_bytes})
        if _Debug:
            lg.out(_DebugLevel, 'p2p_service.Data created a new space file')
    space_dict = bpio._read_dict(settings.CustomersSpaceFile())
    if request.OwnerID not in space_dict.keys():
        lg.warn("no info about donated space for %s" % request.OwnerID)
        SendFail(request, 'no info about donated space')
        return
    used_space_dict = bpio._read_dict(settings.CustomersUsedSpaceFile(), {})
    if request.OwnerID in used_space_dict.keys():
        try:
            bytes_used_by_customer = int(used_space_dict[request.OwnerID])
            bytes_donated_to_customer = int(space_dict[request.OwnerID])
            if bytes_donated_to_customer - bytes_used_by_customer < len(data):
                lg.warn("no free space for %s" % request.OwnerID)
                SendFail(request, 'no free space')
                return
        except:
            lg.exc()
    if not bpio.WriteFile(filename, data):
        lg.warn("ERROR can not write to " + str(filename))
        SendFail(request, 'write error')
        return
    SendAck(request, str(len(request.Payload)))
    from supplier import local_tester
    reactor.callLater(0, local_tester.TestSpaceTime)
    del data
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.Data saved from [%s/%s] to %s" % (
            nameurl.GetName(request.OwnerID), nameurl.GetName(request.CreatorID), filename,))


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
        remoteID)
    result = gateway.outbox(newpacket, callbacks=callbacks)
    return result


def Retrieve(request):
    """
    Customer is asking us for data he previously stored with us.

    We send with ``outboxNoAck()`` method because he will ask again if
    he does not get it
    """
    # TODO: rename to RetreiveData()
    if not driver.is_started('service_supplier'):
        return SendFail(request, 'supplier service is off')
    if not contactsdb.is_customer(request.OwnerID):
        lg.warn("had unknown customer " + request.OwnerID)
        SendFail(request, 'not a customer')
        return
    filename = makeFilename(request.OwnerID, request.PacketID)
    if filename == '':
        lg.warn("had empty filename")
        SendFail(request, 'empty filename')
        return
    if not os.path.exists(filename):
        lg.warn("did not find requested file locally " + filename)
        SendFail(request, 'did not find requested file locally')
        return
    if not os.access(filename, os.R_OK):
        lg.warn("no read access to requested packet " + filename)
        SendFail(request, 'no read access to requested packet')
        return
    data = bpio.ReadBinaryFile(filename)
    if not data:
        lg.warn("empty data on disk " + filename)
        SendFail(request, 'empty data on disk')
        return
    outpacket = signed.Unserialize(data)
    del data
    if outpacket is None:
        lg.warn("Unserialize fails, not Valid packet " + filename)
        SendFail(request, 'unserialize fails')
        return
    if not outpacket.Valid():
        lg.warn("unserialized packet is not Valid " + filename)
        SendFail(request, 'unserialized packet is not Valid')
        return
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.Retrieve sending %r back to %s" % (outpacket, nameurl.GetName(outpacket.CreatorID)))
    gateway.outbox(outpacket, target=outpacket.CreatorID)

#------------------------------------------------------------------------------


def DeleteFile(request):
    """
    Delete one ore multiple files or folders on my machine.
    """
    if not driver.is_started('service_supplier'):
        return SendFail(request, 'supplier service is off')
    if request.Payload == '':
        ids = [request.PacketID]
    else:
        ids = request.Payload.split('\n')
    filescount = 0
    dirscount = 0
    for pathID in ids:
        filename = makeFilename(request.OwnerID, pathID)
        if filename == "":
            filename = constructFilename(request.OwnerID, pathID)
            if not os.path.exists(filename):
                lg.warn("had unknown customer: %s or pathID is not correct or not exist: %s" % (nameurl.GetName(request.OwnerID), pathID))
                return SendFail(request, 'not a customer, or file not found')
        if os.path.isfile(filename):
            try:
                os.remove(filename)
                filescount += 1
            except:
                lg.exc()
        elif os.path.isdir(filename):
            try:
                bpio._dir_remove(filename)
                dirscount += 1
            except:
                lg.exc()
        else:
            lg.warn("path not found %s" % filename)
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.DeleteFile from [%s] with %d IDs, %d files and %d folders were removed" % (
            nameurl.GetName(request.OwnerID), len(ids), filescount, dirscount))
    SendAck(request)


def SendDeleteFile(SupplierID, pathID):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendDeleteFile SupplierID=%s PathID=%s " % (SupplierID, pathID))
    MyID = my_id.getLocalID()
    PacketID = pathID
    RemoteID = SupplierID
    result = signed.Packet(commands.DeleteFile(), MyID, MyID, PacketID, "", RemoteID)
    gateway.outbox(result)
    return result


def SendDeleteListPaths(SupplierID, ListPathIDs):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendDeleteListPaths SupplierID=%s PathIDs number: %d" % (SupplierID, len(ListPathIDs)))
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
    if not driver.is_started('service_supplier'):
        return SendFail(request, 'supplier service is off')
    if request.Payload == '':
        ids = [request.PacketID]
    else:
        ids = request.Payload.split('\n')
    count = 0
    for backupID in ids:
        filename = makeFilename(request.OwnerID, backupID)
        if filename == "":
            filename = constructFilename(request.OwnerID, backupID)
            if not os.path.exists(filename):
                lg.warn("had unknown customer " + request.OwnerID + " or backupID " + backupID)
                return SendFail(request, 'not a customer, or file not found')
        if os.path.isdir(filename):
            try:
                bpio._dir_remove(filename)
                count += 1
            except:
                lg.exc()
        elif os.path.isfile(filename):
            try:
                os.remove(filename)
                count += 1
            except:
                lg.exc()
        else:
            lg.warn("path not found %s" % filename)
    SendAck(request)
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.DeleteBackup from [%s] with %d IDs, %d were removed" % (nameurl.GetName(request.OwnerID), len(ids), count))


def SendDeleteBackup(SupplierID, BackupID):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendDeleteBackup SupplierID=%s  BackupID=%s " % (SupplierID, BackupID))
    MyID = my_id.getLocalID()
    PacketID = BackupID
    RemoteID = SupplierID
    result = signed.Packet(commands.DeleteBackup(), MyID, MyID, PacketID, "", RemoteID)
    gateway.outbox(result)
    return result


def SendDeleteListBackups(SupplierID, ListBackupIDs):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendDeleteListBackups SupplierID=%s BackupIDs number: %d" % (SupplierID, len(ListBackupIDs)))
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
        lg.out(_DebugLevel, "p2p_service.Correspondent")
    # TODO: need to connect users here

#------------------------------------------------------------------------------

def RequestListFilesAll():
    r = []
    for supi in range(contactsdb.num_suppliers()):
        r.append(SendRequestListFiles(supi))
    return r


def SendRequestListFiles(supplierNumORidurl):
    if not str(supplierNumORidurl).isdigit():
        RemoteID = supplierNumORidurl
    else:
        RemoteID = contactsdb.supplier(supplierNumORidurl)
    if not RemoteID:
        lg.warn("RemoteID is empty supplierNumORidurl=%s" % str(supplierNumORidurl))
        return None
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendRequestListFiles [%s]" % nameurl.GetName(RemoteID))
    MyID = my_id.getLocalID()
    PacketID = packetid.UniqueID()
    Payload = settings.ListFilesFormat()
    result = signed.Packet(commands.ListFiles(), MyID, MyID, PacketID, Payload, RemoteID)
    gateway.outbox(result)
    return result

#------------------------------------------------------------------------------

def RequestDeleteBackup(BackupID):
    """
    Need to send a "DeleteBackup" command to all suppliers.
    """
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RequestDeleteBackup with BackupID=" + str(BackupID))
    for supplier in contactsdb.suppliers():
        if not supplier:
            continue
#         prevItems = [] # transport_control.SendQueueSearch(BackupID)
#         found = False
#         for workitem in prevItems:
#             if workitem.remoteid == supplier:
#                 found = True
#                 break
#         if found:
#             continue
        SendDeleteBackup(supplier, BackupID)


def RequestDeleteListBackups(backupIDs):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RequestDeleteListBackups wish to delete %d backups" % len(backupIDs))
    for supplier in contactsdb.suppliers():
        if not supplier:
            continue
        # found = False
        # for workitem in transport_control.SendQueue():
        #     if workitem.command == commands.DeleteBackup() and workitem.remoteid == supplier:
        #         found = True
        #         break
        # if found:
        #     continue
        SendDeleteListBackups(supplier, backupIDs)


def RequestDeleteListPaths(pathIDs):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RequestDeleteListPaths wish to delete %d paths" % len(pathIDs))
    for supplier in contactsdb.suppliers():
        if not supplier:
            continue
        # found = False
        # for workitem in transport_control.SendQueue():
        #     if workitem.command == commands.DeleteFile() and workitem.remoteid == supplier:
        #         found = True
        #         break
        # if found:
        #     continue
        SendDeleteListPaths(supplier, pathIDs)


def CheckWholeBackup(BackupID):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.CheckWholeBackup with BackupID=" + BackupID)

#-------------------------------------------------------------------------------


def Broadcast(request, info):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.Broadcast   %r from %s" % (request, info.sender_idurl))


def SendBroadcastMessage(outpacket):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendBroadcastMessage to %s" % outpacket.RemoteID)
    gateway.outbox(outpacket)
    return outpacket

#------------------------------------------------------------------------------


def Coin(request, info):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.Coin from %r with %d coins" % (
            nameurl.GetName(info.sender_idurl), len(request.Payload), ))


def SendCoin(remote_idurl, coins, packet_id=None, wide=False, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendCoin to %s with %d records" % (remote_idurl, len(coins)))
    if packet_id is None:
        packet_id = packetid.UniqueID()
    outpacket = signed.Packet(
        commands.Coin(), my_id.getLocalID(),
        my_id.getLocalID(), packet_id,
        json.dumps(coins), remote_idurl)
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks)
    return outpacket


def RetreiveCoin(request, info):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.RetreiveCoin from %s : %s" % (
            nameurl.GetName(info.sender_idurl), request.Payload))


def SendRetreiveCoin(remote_idurl, query, wide=False, callbacks={}):
    if _Debug:
        lg.out(_DebugLevel, "p2p_service.SendRetreiveCoin to %s" % remote_idurl)
    outpacket = signed.Packet(
        commands.RetreiveCoin(), my_id.getLocalID(),
        my_id.getLocalID(), packetid.UniqueID(),
        json.dumps(query), remote_idurl)
    gateway.outbox(outpacket, wide=wide, callbacks=callbacks)
    return outpacket
