#!/usr/bin/python
#p2p_service.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: p2p_service

This serves requests from peers:

    * Data          - save packet to a file      (a commands.Data() packet)
    * Retrieve      - read packet from a file    (a commands.Data() packet)
    * ListFiles     - list files we have for customer
    * Delete        - delete a file
    * Identity      - contact or id server sending us a current identity
    * Ack           - response from remote peer after my request
    * Message       - a message from remote peer
    * Correspondent - request to be my correspondent

For listed customers we will save and retrieve data up to their specified limits.
BitPie.NET tells us who our customers are and limits, we get their identities.
If a customer does not contact us for more than 30 hours (or something) then we can process
requests from that customers scrubbers.

Security:

    * Transport_control has checked that it is signed by a contact, 
      but we need to check that this is a customer.

    * Since we have control over suppliers, and may not change them much,
      it feels like customers are more of a risk.

    * Code treats suppliers and customers differently.  Fun that stores
      have customers come in the front door and suppliers in the back door.
    
    * But I don't see anything really worth doing.
      On Unix machines we could run customers in a chrooted environment.
      There would be a main code and any time it got a change
      in the list of customers, it could restart the customer code.
      The customer code could be kept very small this way.
      Again, I doubt it.  We only have XML and binary.
   
    * Real risk is probably the code for SSH, Email, Vetex, etc.
      Once it is a packet object, we are probably ok.

    * We will store in a file and be able to read it back when requested.
      Request comes as a packet and we just verify it signature to be sure about sender.

    * Resource limits.
      A ``local_tester`` checks that someone is not trying to use more than they are supposed to
      and we could also do it here

"""

import os
import sys
import time
import cStringIO
import zlib

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in p2p_service.py')

from twisted.internet.defer import Deferred

try:
    import lib.bpio as bpio
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))
    try:
        import lib.bpio as bpio
    except:
        sys.exit()

import lib.signed_packet as signed_packet
import lib.contacts as contacts
import lib.commands as commands
import lib.misc as misc
import lib.settings as settings
import lib.packetid as packetid
import lib.nameurl as nameurl
import lib.diskspace as diskspace

import userid.identity as identity
import userid.identitycache as identitycache

import transport.gate as gate
import transport.callback as callback 
import transport.packet_out as packet_out

import message
import local_tester
import backup_control

#------------------------------------------------------------------------------

def init():
    bpio.log(4, 'p2p_service.init')
    callback.add_inbox_callback(inbox)

#------------------------------------------------------------------------------

def inbox(newpacket, info, status, error_message):
    """
    """
    if newpacket.Command == commands.Identity():
        # contact sending us current identity we might not have
        # so we handle it before check that packet is valid
        # because we might not have his identity on hands and so can not verify the packet  
        # so we check that his Identity is valid and save it into cache
        # than we check the packet to be valid too.
        Identity(newpacket)            
        return True

    # check that signed by a contact of ours
    if not newpacket.Valid():              
        bpio.log(1, 'p2p_service.inbox ERROR new packet is not Valid')
        return False
  
    if newpacket.CreatorID != misc.getLocalID() and newpacket.RemoteID != misc.getLocalID():
        bpio.log(1, "p2p_service.inbox  ERROR packet is NOT for us")
        bpio.log(1, "p2p_service.inbox  getLocalID=" + misc.getLocalID() )
        bpio.log(1, "p2p_service.inbox  CreatorID=" + newpacket.CreatorID )
        bpio.log(1, "p2p_service.inbox  RemoteID=" + newpacket.RemoteID )
        bpio.log(1, "p2p_service.inbox  PacketID=" + newpacket.PacketID )
        return False

    commandhandled = False
    if newpacket.Command == commands.Fail():
        Fail(newpacket)
        commandhandled = True
    elif newpacket.Command == commands.Retrieve():
        Retrieve(newpacket) # retrieve some packet customer stored with us
        commandhandled = True
    elif newpacket.Command == commands.Ack():
        Ack(newpacket)
        commandhandled = True 
    elif newpacket.Command == commands.RequestService():
        RequestService(newpacket)
        commandhandled = True
    elif newpacket.Command == commands.CancelService():
        CancelService(newpacket) # new packet to store for customer
        commandhandled = True    
    elif newpacket.Command == commands.Data():
        Data(newpacket) # new packet to store for customer
        commandhandled = True
    elif newpacket.Command == commands.ListFiles():
        ListFiles(newpacket) # customer wants list of their files
        commandhandled = True
    elif newpacket.Command == commands.Files():
        Files(newpacket) # supplier sent us list of files
        commandhandled = True
    elif newpacket.Command == commands.DeleteFile():
        DeleteFile(newpacket) # will Delete a customer file for them
        commandhandled = True
    elif newpacket.Command == commands.DeleteBackup():
        DeleteBackup(newpacket) # will Delete all files starting in a backup
        commandhandled = True
    elif newpacket.Command == commands.RequestIdentity():
        RequestIdentity(newpacket) # contact asking for our current identity
        commandhandled = True
    elif newpacket.Command == commands.Message():
        message.Message(newpacket) # contact asking for our current identity
        commandhandled = True
    elif newpacket.Command == commands.Correspondent():
        Correspondent(newpacket) # contact asking for our current identity
        commandhandled = True
    
    if not commandhandled:
        bpio.log(6, "p2p_service.inbox WARNING [%s] from %s|%s (%s://%s) NOT handled" % (
            newpacket.Command, nameurl.GetName(newpacket.CreatorID), 
            nameurl.GetName(newpacket.OwnerID), info.proto, info.host))

    return commandhandled


def outbox(outpacket):
    bpio.log(6, "p2p_service.outbox [%s] to %s" % (outpacket.Command, nameurl.GetName(outpacket.RemoteID)))
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
    Must be a customer, and then we make full path filename for where this packet is stored locally.
    """
    if not packetid.Valid(packetID): # SECURITY
        if packetID not in [    settings.BackupInfoFileName(), 
                                settings.BackupInfoFileNameOld(), 
                                settings.BackupInfoEncryptedFileName(), 
                                settings.BackupIndexFileName() ]:
            # bpio.log(1, "p2p_service.makeFilename ERROR failed packetID format: " + packetID )
            return ''
    if not contacts.IsCustomer(customerID):  # SECURITY
        bpio.log(4, "p2p_service.makeFilename WARNING %s not a customer: %s" % (customerID, str(contacts.getCustomerNames())))
        return ''
    return constructFilename(customerID, packetID)

#------------------------------------------------------------------------------

def SendAck(packettoack, response=''):
    result = signed_packet.Packet(commands.Ack(), misc.getLocalID(), misc.getLocalID(), 
                                 packettoack.PacketID, response, packettoack.OwnerID)
    bpio.log(8, "p2p_service.SendAck %s to %s" % (result.PacketID, result.RemoteID))
    gate.outbox(result)
    return result
    

def Ack(newpacket):
    bpio.log(8, "p2p_service.Ack %s from [%s] : %s" % (newpacket.PacketID, newpacket.CreatorID, newpacket.Payload))
    # for p in packet_out.search_by_packet_id(newpacket.CreatorID, newpacket.PacketID):
    #     bpio.log(8, '        found matched outbox packet : %r' % p)
    #     p.automat('ack', newpacket)
     
    
def SendFail(request, response=''):
    result = signed_packet.Packet(commands.Fail(), misc.getLocalID(), misc.getLocalID(), 
                                 request.PacketID, response, request.OwnerID) # request.CreatorID)
    bpio.log(8, "transport_control.SendFail %s to %s" % (result.PacketID, result.RemoteID))
    gate.outbox(result)
    return result
    

def Fail(newpacket):
    bpio.log(8, "p2p_service.Fail from [%s]: %s" % (newpacket.CreatorID, newpacket.Payload))
    # for p in packet_out.search_by_packet_id(newpacket.RemoteID, newpacket.PacketID):
    #     bpio.log(8, '        found matched outbox packet : %r' % p)
    #     p.automat('fail', newpacket)
 
#------------------------------------------------------------------------------ 

def Identity(newpacket):
    """
    Contact or identity server is sending us a new copy of an identity for a contact of ours.
    Checks that identity is signed correctly.
    """
    newxml = newpacket.Payload
    newidentity = identity.identity(xmlsrc=newxml)

    # SECURITY - check that identity is signed correctly
    # if not newidentity.Valid():
    #     bpio.log(1,"p2p_service.Identity ERROR has non-Valid identity")
    #     return

    idurl = newidentity.getIDURL()

    if not identitycache.UpdateAfterChecking(idurl, newxml):
        bpio.log(1,"p2p_service.Identity ERROR has non-Valid identity")
        return
        

    # if contacts.isKnown(idurl):
        # This checks that old public key matches new
    #     identitycache.UpdateAfterChecking(idurl, newxml)

    # else:
        # TODO
        # may be we need to make some temporary storage
        # for identities who we did not know yet
        # just to be able to receive packets from them
    #     identitycache.UpdateAfterChecking(idurl, newxml)

    # Now that we have ID we can check packet
    if not newpacket.Valid():
        # If not valid do nothing
        bpio.log(6, "p2p_service.Identity WARNING not Valid packet from %s" % idurl)
        return

    if newpacket.OwnerID == idurl:
        SendAck(newpacket)
        bpio.log(8, "p2p_service.Identity from [%s], sent Ack" % nameurl.GetName(idurl))
    else:
        bpio.log(8, "p2p_service.Identity from [%s]" % nameurl.GetName(idurl))

def RequestIdentity(request):
    """
    Someone is requesting a copy of our current identity.
    Already verified that they are a contact.
    Can also be used as a sort of "ping" test to make sure we are alive.
    """
    bpio.log(6, "p2p_service.RequestIdentity starting")
    MyID = misc.getLocalID()
    RemoteID = request.OwnerID
    PacketID = request.PacketID
    identitystr = misc.getLocalIdentity().serialize()
    bpio.log(8, "p2p_service.RequestIdentity returning ")
    result = signed_packet.Packet(commands.Identity(), MyID, MyID, PacketID, identitystr, RemoteID)
    gate.outbox(result, False)
       
def SendIdentity(remote_idurl, wide=False):
    """
    """
    bpio.log(8, "p2p_service.SendIdentity to %s" % nameurl.GetName(remote_idurl))
    result = signed_packet.Packet(commands.Identity(), misc.getLocalID(), 
                                 misc.getLocalID(), 'identity', # misc.getLocalID(),
                                 misc.getLocalIdentity().serialize(), remote_idurl)
    gate.outbox(result, wide)
    return result       
    
#------------------------------------------------------------------------------ 

def RequestService(request):
    bpio.log(8, "p2p_service.RequestService %s" % request.OwnerID)
    words = request.Payload.split(' ')
    if len(words) <= 1:
        bpio.log(6, "p2p_service.RequestService WARNING got wrong payload in %s" % request)
        return SendFail(request, 'wrong payload')
    if words[0] == 'storage':
        try:
            mb_for_customer = round(float(words[1]), 2)
        except:
            bpio.exception()
            mb_for_customer = None
        if not mb_for_customer or mb_for_customer < 0:
            bpio.log(6, "p2p_service.RequestService WARNING wrong storage value : %s" % request.Payload)
            return SendFail(request, 'wrong storage value')
        current_customers = contacts.getCustomerIDs()
        mb_donated = diskspace.GetMegaBytesFromString(settings.getMegabytesDonated())
        if not os.path.isfile(settings.CustomersSpaceFile()):
            bpio._write_dict(settings.CustomersSpaceFile(), {'free': str(mb_donated)})
            bpio.log(6, 'p2p_service.RequestService created a new space file')
        space_dict = bpio._read_dict(settings.CustomersSpaceFile())
        free_mb = round(float(space_dict['free']), 2)
        if ( request.OwnerID not in current_customers and request.OwnerID in space_dict.keys() ):
            bpio.log(6, "p2p_service.RequestService WARNING broken space file")
            return SendFail(request, 'broken space file')
        if ( request.OwnerID in current_customers and request.OwnerID not in space_dict.keys() ):
            bpio.log(6, "p2p_service.RequestService WARNING broken customers file")
            return SendFail(request, 'broken customers file')
        if request.OwnerID in current_customers:
            free_mb += round(float(space_dict[request.OwnerID]), 2)
            space_dict['free'] = str(free_mb)
            current_customers.remove(request.OwnerID)  
            space_dict.pop(request.OwnerID)
            new_customer = False
        else:
            new_customer = True
        if free_mb <= mb_for_customer:
            contacts.setCustomerIDs(current_customers)
            contacts.saveCustomerIDs()
            bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
            reactor.callLater(0, local_tester.TestUpdateCustomers)
            if new_customer:
                bpio.log(8, "    NEW CUSTOMER - DENIED !!!!!!!!!!!    not enough space")
            else:
                bpio.log(8, "    OLD CUSTOMER - DENIED !!!!!!!!!!!    not enough space")
            return SendAck(request, 'deny')
        space_dict['free'] = str(round(free_mb - mb_for_customer, 2))
        current_customers.append(request.OwnerID)  
        space_dict[request.OwnerID] = str(mb_for_customer)
        contacts.setCustomerIDs(current_customers)
        contacts.saveCustomerIDs()
        bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        if new_customer:
            bpio.log(8, "    NEW CUSTOMER ACCEPTED !!!!!!!!!!!!!!")
        else:
            bpio.log(8, "    OLD CUSTOMER ACCEPTED !!!!!!!!!!!!!!")
        return SendAck(request, 'accepted')
    bpio.log(6, "p2p_service.RequestService WARNING wrong service request in %s" % request)
    return SendFail(request, 'wrong service request')
    
def SendRequestService(remote_idurl, service_info, response_callback=None):
    bpio.log(8, "p2p_service.SendRequestService to %s [%s]" % (nameurl.GetName(remote_idurl), service_info))
    result = signed_packet.Packet(commands.RequestService(), misc.getLocalID(), misc.getLocalID(), 
                                 packetid.UniqueID(), service_info, remote_idurl)
    gate.outbox(result, callbacks={
        commands.Ack(): response_callback,
        commands.Fail(): response_callback})
    return result       

def CancelService(request):
    bpio.log(8, "p2p_service.CancelService")
    if request.Payload.startswith('storage'):
        if not contacts.IsCustomer(request.OwnerID):
            bpio.log(6, "p2p_service.CancelService WARNING got packet from %s, but he is not a customer" % request.OwnerID)
            return SendFail(request, 'not a customer')
        mb_donated = diskspace.GetMegaBytesFromString(settings.getMegabytesDonated())
        space_dict = bpio._read_dict(settings.CustomersSpaceFile(), {'free': str(mb_donated)})
        if request.OwnerID not in space_dict.keys():
            bpio.log(6, "p2p_service.CancelService WARNING got packet from %s, but not found him in space dictionary" % request.OwnerID)
            return SendFail(request, 'not a customer')
        free_mb = float(space_dict['free'])
        space_dict['free'] = str(round(free_mb + float(space_dict[request.OwnerID]), 2))
        new_customers = list(contacts.getCustomerIDs())
        new_customers.remove(request.OwnerID)
        contacts.setCustomerIDs(new_customers)
        contacts.saveCustomerIDs()
        space_dict.pop(request.OwnerID)
        bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
        reactor.callLater(0, local_tester.TestUpdateCustomers)
        return SendAck(request, 'accepted')
    bpio.log(6, "p2p_service.CancelService WARNING got wrong payload in %s" % request)
    return SendFail(request, 'wrong service request')

def SendCancelService(remote_idurl, service_info, response_callback=None):
    bpio.log(8, "p2p_service.SendCancelService [%s]" % service_info)
    result = signed_packet.Packet(commands.CancelService(), misc.getLocalID(), misc.getLocalID(), 
                                 packetid.UniqueID(), service_info, remote_idurl)
    gate.outbox(result, callbacks={
        commands.Ack(): response_callback,
        commands.Fail(): response_callback})
    return result   

#------------------------------------------------------------------------------ 

def ListFiles(request):
    """
    We will want to use this to see what needs to be resent, 
    and expect normal case is very few missing.
    This is to build the ``Files()`` we are holding for a customer.
    """
    MyID = misc.getLocalID()
    RemoteID = request.OwnerID
    PacketID = request.PacketID
    Payload = request.Payload
    bpio.log(8, "p2p_service.ListFiles from [%s], format is %s" % (nameurl.GetName(request.OwnerID), Payload))
    custdir = settings.getCustomersFilesDir()
    ownerdir = os.path.join(custdir, nameurl.UrlFilename(request.OwnerID))
    if not os.path.isdir(ownerdir):
        bpio.log(8, "p2p_service.ListFiles did not find customer dir " + ownerdir)
        src = PackListFiles('', Payload)
        result = signed_packet.Packet(commands.Files(), MyID, MyID, PacketID, src, RemoteID)
        gate.outbox(result)
        return result
    plaintext = TreeSummary(ownerdir)
    src = PackListFiles(plaintext, Payload)
    result = signed_packet.Packet(commands.Files(), MyID, MyID, PacketID, src, RemoteID)
    gate.outbox(result)
    return result       


def Files(newpacket):
    """
    A directory list came in from some supplier.
    """
    bpio.log(8, "p2p_service.Files from [%s]" % nameurl.GetName(newpacket.OwnerID))
    backup_control.IncomingSupplierListFiles(newpacket)
   
#------------------------------------------------------------------------------ 

def Data(request):
    """
    This is when we 
        1) save my requested data to restore the backup 
        2) or save the customer file on our local HDD 
    """
    # 1. this is our Data! 
    if request.OwnerID == misc.getLocalID():
        bpio.log(8, "p2p_service.Data %r for us from %s" % (
            request, nameurl.GetName(request.CreatorID)))
        if request.PacketID in [ settings.BackupIndexFileName(), ]:
            backup_control.IncomingSupplierBackupIndex(request)
#        elif request.PacketID in [ settings.BackupInfoFileName(), settings.BackupInfoFileNameOld(), settings.BackupInfoEncryptedFileName(), ]:
#            return
        return
    # 2. this Data is not belong to us
    if not contacts.IsCustomer(request.OwnerID):  # SECURITY
        # may be we did not get the ListCustomers packet from the Central yet?
        bpio.log(6, "p2p_service.Data WARNING %s not a customer, packetID=%s" % (request.OwnerID, request.PacketID))
        SendFail(request, 'not a customer')
        # central_service.SendRequestCustomers()
        return
    filename = makeFilename(request.OwnerID, request.PacketID)
    if filename == "":
        bpio.log(6,"p2p_service.Data WARNING got empty filename, bad customer or wrong packetID? ")
        SendFail(request, 'empty filename')
        return
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        try:
            bpio._dirs_make(dirname)
        except:
            bpio.log(2, "p2p_service.Data ERROR can not create sub dir " + dirname)
            SendFail(request, 'write error')
            return 
    data = request.Serialize()
    mb_donated = diskspace.GetMegaBytesFromString(settings.getMegabytesDonated())
    if not os.path.isfile(settings.CustomersSpaceFile()):
        bpio._write_dict(settings.CustomersSpaceFile(), {'free': str(mb_donated)})
        bpio.log(6, 'p2p_service.Data created a new space file')
    space_dict = bpio._read_dict(settings.CustomersSpaceFile())
    if request.OwnerID not in space_dict.keys():
        bpio.log(6, "p2p_service.Data WARNING no info about donated space for %s" % request.OwnerID)
        SendFail(request, 'no info about donated space')
        return
    used_space_dict = bpio._read_dict(settings.CustomersUsedSpaceFile(), {})
    if request.OwnerID in used_space_dict.keys():
        try:
            bytes_used_by_customer = int(used_space_dict[request.OwnerID])
            bytes_donated_to_customer = int(float(space_dict[request.OwnerID]) * 1024 * 1024)  
            if bytes_donated_to_customer - bytes_used_by_customer < len(data):
                bpio.log(6, "p2p_service.Data WARNING no free space for %s" % request.OwnerID)
                SendFail(request, 'no free space')
                return
        except:
            bpio.exception()
    if not bpio.WriteFile(filename, data):
        bpio.log(2, "p2p_service.Data ERROR can not write to " + str(filename))
        SendFail(request, 'write error')
        return
    SendAck(request, str(len(request.Payload)))
    reactor.callLater(0, local_tester.TestSpaceTime)
    del data
    bpio.log(8, "p2p_service.Data saved from [%s/%s] to %s" % (
        nameurl.GetName(request.OwnerID), nameurl.GetName(request.CreatorID), filename,))


def Retrieve(request):
    """
    Customer is asking us for data he previously stored with us.
    We send with ``outboxNoAck()`` method because he will ask again if he does not get it
    """
    if not contacts.IsCustomer(request.OwnerID):
        bpio.log(4, "p2p_service.Retrieve WARNING had unknown customer " + request.OwnerID)
        SendFail(request, 'not a customer')
        return
    filename = makeFilename(request.OwnerID, request.PacketID)
    if filename == '':
        bpio.log(4, "p2p_service.Retrieve WARNING had empty filename")
        SendFail(request, 'empty filename')
        return
    if not os.path.exists(filename):
        bpio.log(4, "p2p_service.Retrieve WARNING did not find requested packet " + filename)
        SendFail(request, 'did not find requested packet')
        return
    if not os.access(filename, os.R_OK):
        bpio.log(4, "p2p_service.Retrieve WARNING no read access to requested packet " + filename)
        SendFail(request, 'no read access to requested packet')
        return
    data = bpio.ReadBinaryFile(filename)
    if not data:
        bpio.log(4, "p2p_service.Retrieve WARNING empty data on disk " + filename)
        SendFail(request, 'empty data on disk')
        return
    outpacket = signed_packet.Unserialize(data)
    del data 
    if outpacket is None:
        bpio.log(4, "p2p_service.Retrieve WARNING Unserialize fails, not Valid packet " + filename)
        SendFail(request, 'unserialize fails')
        return
    if not outpacket.Valid():
        bpio.log(4, "p2p_service.Retrieve WARNING unserialized packet is not Valid " + filename)
        SendFail(request, 'unserialized packet is not Valid')
        return
    bpio.log(8, "p2p_service.Retrieve sending %r back to %s" % (outpacket, nameurl.GetName(outpacket.CreatorID)))
    gate.outbox(outpacket)

#------------------------------------------------------------------------------ 

def DeleteFile(request):
    """
    Delete one ore multiple files or folders on my machine.
    """
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
                bpio.log(1, "p2p_service.DeleteFile WARNING had unknown customer: %s or pathID is not correct or not exist: %s" % (nameurl.GetName(request.OwnerID), pathID))
                return
        if os.path.isfile(filename):
            try:
                os.remove(filename)
                filescount += 1
            except:
                bpio.exception()
        elif os.path.isdir(filename):
            try:
                bpio._dir_remove(filename)
                dirscount += 1
            except:
                bpio.exception()
        else:
            bpio.log(1, "p2p_service.DeleteFile WARNING path not found %s" % filename)
    bpio.log(8, "p2p_service.DeleteFile from [%s] with %d IDs, %d files and %d folders were removed" % (
        nameurl.GetName(request.OwnerID), len(ids), filescount, dirscount))
    SendAck(request)
    

def SendDeleteFile(SupplierID, pathID):
    bpio.log(8, "p2p_service.SendDeleteFile SupplierID=%s PathID=%s " % (SupplierID, pathID))
    MyID = misc.getLocalID()
    PacketID = pathID
    RemoteID = SupplierID
    result = signed_packet.Packet(commands.DeleteFile(),  MyID, MyID, PacketID, "", RemoteID)
    gate.outbox(result)
    return result
    
    
def SendDeleteListPaths(SupplierID, ListPathIDs):
    bpio.log(8, "p2p_service.SendDeleteListPaths SupplierID=%s PathIDs number: %d" % (SupplierID, len(ListPathIDs)))
    MyID = misc.getLocalID()
    PacketID = packetid.UniqueID()
    RemoteID = SupplierID
    Payload = '\n'.join(ListPathIDs)
    result = signed_packet.Packet(commands.DeleteFile(),  MyID, MyID, PacketID, Payload, RemoteID)
    gate.outbox(result)
    return result

#------------------------------------------------------------------------------ 

def DeleteBackup(request):
    """
    Delete one or multiple backups on my machine.
    """
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
                bpio.log(1, "p2p_service.DeleteBackup WARNING had unknown customer " + request.OwnerID + " or backupID " + backupID)
                return
        if os.path.isdir(filename):
            try:
                bpio._dir_remove(filename)
                count += 1
            except:
                bpio.exception()
        elif os.path.isfile(filename):
            try:
                os.remove(filename)
                count += 1
            except:
                bpio.exception()
        else:
            bpio.log(1, "p2p_service.DeleteBackup WARNING path not found %s" % filename)
    SendAck(request)
    bpio.log(8, "p2p_service.DeleteBackup from [%s] with %d IDs, %d were removed" % (nameurl.GetName(request.OwnerID), len(ids), count))


def SendDeleteBackup(SupplierID, BackupID):
    bpio.log(8, "p2p_service.SendDeleteBackup SupplierID=%s  BackupID=%s " % (SupplierID, BackupID))
    MyID = misc.getLocalID()
    PacketID = BackupID
    RemoteID = SupplierID
    result = signed_packet.Packet(commands.DeleteBackup(),  MyID, MyID, PacketID, "", RemoteID)
    gate.outbox(result)
    return result

def SendDeleteListBackups(SupplierID, ListBackupIDs):
    bpio.log(8, "p2p_service.SendDeleteListBackups SupplierID=%s BackupIDs number: %d" % (SupplierID, len(ListBackupIDs)))
    MyID = misc.getLocalID()
    PacketID = packetid.UniqueID()
    RemoteID = SupplierID
    Payload = '\n'.join(ListBackupIDs)
    result = signed_packet.Packet(commands.DeleteBackup(),  MyID, MyID, PacketID, Payload, RemoteID)
    gate.outbox(result)
    return result

#------------------------------------------------------------------------------ 

def Correspondent(request):
    bpio.log(8, "p2p_service.Correspondent")
    MyID = misc.getLocalID()
    RemoteID = request.OwnerID
    PacketID = request.PacketID
    Msg = misc.decode64(request.Payload)
    # TODO !!!

#------------------------------------------------------------------------------ 

def ListCustomerFiles(customer_idurl):
    filename = nameurl.UrlFilename(customer_idurl)
    customer_dir = os.path.join(settings.getCustomersFilesDir(), filename)
    result = cStringIO.StringIO()
    def cb(realpath, subpath, name):
        if os.path.isdir(realpath):
            result.write('D%s\n' % subpath)
        else:
            result.write('F%s\n' % subpath)
        return True
    bpio.traverse_dir_recursive(cb, customer_dir)
    src = result.getvalue()
    result.close()
    return src

def ListCustomerFiles1(customerNumber):
    """
    On the status form when clicking on a customer, 
    find out what files we're holding for that customer
    """
    idurl = contacts.getCustomerID(customerNumber)
    filename = nameurl.UrlFilename(idurl)
    customerDir = os.path.join(settings.getCustomersFilesDir(), filename)
    if os.path.exists(customerDir) and os.path.isdir(customerDir):
        backupFilesList = os.listdir(customerDir)
        if len(backupFilesList) > 0:
            return ListSummary(backupFilesList)
    return "No files stored for this customer"


def RequestListFilesAll():
    r = []
    for supi in range(contacts.numSuppliers()):
        r.append(RequestListFiles(supi))
    return r


def RequestListFiles(supplierNumORidurl):
    if isinstance(supplierNumORidurl, str):
        RemoteID = supplierNumORidurl
    else:
        RemoteID = contacts.getSupplierID(supplierNumORidurl)
    if not RemoteID:
        bpio.log(4, "p2p_service.RequestListFiles WARNING RemoteID is empty supplierNumORidurl=%s" % str(supplierNumORidurl))
        return None
    bpio.log(8, "p2p_service.RequestListFiles [%s]" % nameurl.GetName(RemoteID))
    MyID = misc.getLocalID()
    PacketID = packetid.UniqueID()
    Payload = settings.ListFilesFormat()
    result = signed_packet.Packet(commands.ListFiles(), MyID, MyID, PacketID, Payload, RemoteID)
    gate.outbox(result)
    return result

#------------------------------------------------------------------------------ 

def ListSummary(dirlist):
    """
    Take directory listing and make summary of format::
        BackupID-1-Data 1-1873 missing for 773,883,
        BackupID-1-Parity 1-1873 missing for 777,982,
    """
    BackupMax={}
    BackupAll={}
    result=""
    for filename in dirlist:
        if not packetid.Valid(filename):       # if not type we can summarize
            result += filename + "\n"            #    then just include filename
        else:
            BackupID, BlockNum, SupNum, DataOrParity = packetid.BidBnSnDp(filename)
            LocalID = BackupID + "-" + str(SupNum) + "-" + DataOrParity
            blocknum = int(BlockNum)
            BackupAll[(LocalID,blocknum)]=True
            if LocalID in BackupMax:
                if BackupMax[LocalID] < blocknum:
                    BackupMax[LocalID] = blocknum
            else:
                BackupMax[LocalID] = blocknum
    for BackupName in sorted(BackupMax.keys()):
        missing = []
        thismax = BackupMax[BackupName]
        for blocknum in range(0, thismax):
            if not (BackupName, blocknum) in BackupAll:
                missing.append(str(blocknum))
        result += BackupName + " from 0-" + str(thismax)
        if len(missing) > 0:
            result += ' missing '
            result += ','.join(missing)
#            for m in missing:
#                result += str(m) + ","
        result += "\n"
    return result

def TreeSummary(ownerdir):
    out = cStringIO.StringIO()
    def cb(result, realpath, subpath, name):
        if not os.access(realpath, os.R_OK):
            return False
        if os.path.isfile(realpath):
            result.write('F%s\n' % subpath)
            return False
        if not packetid.IsCanonicalVersion(name):
            result.write('D%s\n' % subpath)
            return True
        maxBlock = -1
        dataBlocks = {}
        parityBlocks = {}
        dataMissing = {}
        parityMissing = {}
        for filename in os.listdir(realpath):
            packetID = subpath + '/' + filename
            pth = os.path.join(realpath, filename)
            if os.path.isdir(pth):
                result.write('D%s\n' % packetID)
                continue
            if not packetid.Valid(packetID):
                result.write('F%s\n' % packetID)
                continue
            pathID, versionName, blockNum, supplierNum, dataORparity = packetid.SplitFull(packetID)
            if None in [pathID, versionName, blockNum, supplierNum, dataORparity]:
                result.write('F%s\n' % packetID)
                continue
            if dataORparity == 'Data':
                if not dataBlocks.has_key(supplierNum):
                    dataBlocks[supplierNum] = set()
                    dataMissing[supplierNum] = []
                dataBlocks[supplierNum].add(blockNum)
            elif dataORparity == 'Parity':
                if not parityBlocks.has_key(supplierNum):
                    parityBlocks[supplierNum] = set()
                    parityMissing[supplierNum] = []
                parityBlocks[supplierNum].add(blockNum)
            else:
                result.write('F%s\n' % packetID)
                continue
            if maxBlock < blockNum:
                maxBlock = blockNum
        for blockNum in range(maxBlock+1):
            for supplierNum in dataBlocks.keys():
                if not blockNum in dataBlocks[supplierNum]:
                    dataMissing[supplierNum].append(str(blockNum))
            for supplierNum in parityBlocks.keys():
                if not blockNum in parityBlocks[supplierNum]:
                    parityMissing[supplierNum].append(str(blockNum))
        suppliers = set(dataBlocks.keys() + parityBlocks.keys())
        for supplierNum in suppliers:
            versionString = '%s %d 0-%d' % (subpath, supplierNum, maxBlock)
            dataMiss = []
            parityMiss = []
            if dataMissing.has_key(supplierNum):
                dataMiss = dataMissing[supplierNum]
            if parityMissing.has_key(supplierNum):
                parityMiss = parityMissing[supplierNum]   
            if len(dataMiss) > 0 or len(parityMiss) > 0:
                versionString += ' missing'
                if len(dataMiss) > 0:
                    versionString += ' Data:' + (','.join(dataMiss))
                if len(parityMiss) > 0:
                    versionString += ' Parity:' + (','.join(parityMiss))
            del dataMiss
            del parityMiss
            result.write('V%s\n' % versionString)
        del dataBlocks
        del parityBlocks
        del dataMissing
        del parityMissing
        return False
    bpio.traverse_dir_recursive(lambda realpath, subpath, name: cb(out, realpath, subpath, name), ownerdir)
    src = out.getvalue()
    out.close()
    return src

def PackListFiles(plaintext, method):
    if method == "Text":
        return plaintext 
    elif method == "Compressed":
        return zlib.compress(plaintext)
    return ''

def UnpackListFiles(payload, method): 
    if method == "Text":
        return payload
    elif method == "Compressed":
        return zlib.decompress(payload)
    return payload

#------------------------------------------------------------------------------ 

def RequestDeleteBackup(BackupID):
    """
    Need to send a "DeleteBackup" command to all suppliers.
    """
    bpio.log(8, "p2p_service.RequestDeleteBackup with BackupID=" + str(BackupID))
    for supplier in contacts.getSupplierIDs():
        if not supplier:
            continue
        prevItems = [] # transport_control.SendQueueSearch(BackupID)
        found = False
        for workitem in prevItems:
            if workitem.remoteid == supplier:
                found = True
                break
        if found:
            continue
        SendDeleteBackup(supplier, BackupID)


def RequestDeleteListBackups(backupIDs):
    bpio.log(8, "p2p_service.RequestDeleteListBackups wish to delete %d backups" % len(backupIDs))
    for supplier in contacts.getSupplierIDs():
        if not supplier:
            continue
        found = False
        # for workitem in transport_control.SendQueue():
        #     if workitem.command == commands.DeleteBackup() and workitem.remoteid == supplier:
        #         found = True
        #         break
        if found:
            continue
        SendDeleteListBackups(supplier, backupIDs)


def RequestDeleteListPaths(pathIDs):
    bpio.log(8, "p2p_service.RequestDeleteListPaths wish to delete %d paths" % len(pathIDs))
    for supplier in contacts.getSupplierIDs():
        if not supplier:
            continue
        found = False
        # for workitem in transport_control.SendQueue():
        #     if workitem.command == commands.DeleteFile() and workitem.remoteid == supplier:
        #         found = True
        #         break
        if found:
            continue
        SendDeleteListPaths(supplier, pathIDs)


def CheckWholeBackup(BackupID):
    bpio.log(8, "p2p_service.CheckWholeBackup with BackupID=" + BackupID)

#-------------------------------------------------------------------------------

def message2gui(proto, text):
    pass
#    statusline.setp(proto, text)


def getErrorString(error):
    try:
        return error.getErrorMessage()
    except:
        if error is None:
            return ''
        return str(error)


def getHostString(host):
    try:
        return str(host.host)+':'+str(host.port)
    except:
        if host is None:
            return ''
        return str(host)

if __name__ == '__main__':
    settings.init()

