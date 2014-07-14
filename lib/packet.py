#!/usr/bin/python
#packet.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: packet

These packets usually hold on the order of 1 MB.
Something equal to a packet number so we can detect duplicates in transport.
Packet Fields are all strings (no integers, objects, etc)
    - Command : Legal Commands are in bitpie/lib/commands.py               
    - OwnerID : who owns this data and pays bills - http://cate.com/id1.xml                
    - CreatorID : this is signer - http://cate.com/id1.xml - might be an authorized scrubber            
    - PacketID : string of the above 4 "Number"s with "-" separator to uniquely identify a packet
                on the local machine.  Can be used for filenames, and to prevent duplicates.               
    - Date : create a string to remember current world time
    - Payload : main body of binary data                
    - RemoteID : want full IDURL for other party so troublemaker could not
                use his packets to mess up other nodes by sending it to them
    - Signature : signature on Hash is always by CreatorID
"""

import os
import sys

from twisted.internet import threads
from twisted.internet.defer import Deferred


import types
import datetime


import io
import commands
import misc
import crypto
import packetid
import contacts


class Signed:
    """
    The core class.
    Represents a data packet in the network. 
    Payload can be encrypted using bitpie.lib.dhnblock.
    We expect remote user run the correct software.
    His BitPie.NET must verify signature of that packet.
    If you want to encrypt the fields and so hide that service traffic completely - 
    do that in the transport protocols. 
    Need to transfer our public key to remote peer and than he can send us a safe messages.
    This is outside work, here is most important things to make all network working. 
    """
    def __init__(self, Command, OwnerID, CreatorID, PacketID, Payload, RemoteID,):
        """
        Init all fields and sign the packet.
        """
        # Legal Commands are in commands.py
        self.Command = Command               
        # who owns this data and pays bills - http://cate.com/id1.xml
        self.OwnerID = OwnerID                
        # signer - http://cate.com/id1.xml - might be an authorized scrubber
        self.CreatorID = CreatorID         
        # string of the above 4 "Number"s with "-" separator to uniquely identify a packet
        # on the local machine.  Can be used for filenames, and to prevent duplicates.   
        self.PacketID = PacketID
        # create a string to remember current world time              
        self.Date = datetime.datetime.now().strftime("%Y/%m/%d %I:%M:%S %p")
        # main body of binary data
        self.Payload = Payload                
        # want full IDURL for other party so troublemaker could not
        # use his packets to mess up other nodes by sending it to them
        self.RemoteID = RemoteID             
        # signature on Hash is always by CreatorID
        self.Signature = None
        # must be signed to be valid
        self.Sign()

    def __repr__(self):
        return 'packet (command=%s id=%s)' % (str(self.Command), str(self.PacketID))

    def Sign(self):
        """
        Call ``GenerateSignature`` and save the result. Usually just done at packet creation.
        """
        self.Signature = self.GenerateSignature()  
        return self

    def GenerateHashBase(self):
        """
        This make a long string containing all needed fields of ``packet`` (without Signature).
        Just to be able to generate a hash of the whole packet.
        """
        sep = "-"
        stufftosum = self.Command + sep + self.OwnerID + sep + self.CreatorID + sep + self.PacketID + sep + self.Date + sep + self.Payload + sep + self.RemoteID
        return stufftosum

    def GenerateHash(self):
        """
        Call ``lib.crypto.Hash`` to create a hash code for that ``packet``.
        """
        return crypto.Hash(self.GenerateHashBase())

    def GenerateSignature(self):
        """
        Call ``lib.crypto.Sign`` to generate digital signature.
        """
        return crypto.Sign(self.GenerateHash())

    def SignatureChecksOut(self):
        """
        This check correctness of signature, uses ``lib.crypto.Verify``.
        To verify we need 3 things:
            - the packet ``Creator`` identity ( it keeps the public key ),
            - hash of that packet - just call ``GenerateHash()`` to make it,
            - the signature itself.
        """
        ConIdentity = contacts.getContact(self.CreatorID)
        if ConIdentity is None:
            io.log(1, "packet.SignatureChecksOut ERROR could not get Identity for " + self.CreatorID + " so returning False")
            return False
        Result = crypto.Verify(ConIdentity, self.GenerateHash(), self.Signature)
        return Result

    def Ready(self):
        """
        I was playing with generating signatures in separate thread, 
        so this is just to check that Signature already exists.
        """
        return self.Signature is not None

    def Valid(self):
        """
        ``Valid()`` should check every one of packet header fields:
            1) that command is one of the legal commands
            2) signature is good (which means the hashcode is good)
        Rest PREPRO:
            3) all the number fields are just numbers
            4) length is within legal limits
            5) check that URL is a good URL
            6) that DataOrParity is either "data" or "parity"
            7) that Creator is equal to owner or a scrubber for owner
            8) etc.
        """
        if not self.Ready():
            io.log(4, "packet.Valid WARNING packet is not ready yet " + str(self))
            return False
        if not commands.IsCommand(self.Command):
            io.log(1, "packet.Valid bad Command " + str(self.Command))
            return False
        if not self.SignatureChecksOut():
            io.log(1, "packet.Valid failed Signature")
            return False
        return True

    def BackupID(self):
        """
        A wrapper for ``lib.packetid.BackupID``.
        """
        return packetid.BackupID(self.PacketID)

    def BlockNumber(self):
        """
        A wrapper for ``lib.packetid.BlockNumber``.
        """
        return packetid.BlockNumber(self.PacketID)

    def DataOrParity(self):
        """
        A wrapper for ``lib.packetid.DataOrParity``.
        """
        return packetid.DataOrParity(self.PacketID)

    def SupplierNumber(self):
        """
        A wrapper for ``lib.packetid.SupplierNumber``.
        """
        return packetid.SupplierNumber(self.PacketID)

    def Serialize(self):
        """
        Create a string from packet object using ``lib.misc.ObjectToString``.
        This is useful when need to save the packet on disk.
        """
        return misc.ObjectToString(self)

    def __len__(self):
        """
        Return a length of serialized packet. 
        """
        return len(self.Serialize())


class packet_0signed(Signed):
    """
    I was playing with hacking packets and do some debug also.
    """    
    def GenerateSignature(self):
        return '0'


def Unserialize(data):
    """
    We expect here a string containing a whole packet object in text form.
    Here is used a special libraries in ``twisted.spread``: ``banana`` and ``jelly`` to do that work.
    This stuff is placed in the ``lib.misc.StringToObject``. 
    So return a real object in the memory from given string.
    All class fields are loaded, signature can be verified to be sure - it was  truly original string.
    """
    if data is None:
        return None
    newobject = misc.StringToObject(data)
    if newobject is None:
        # io.log(6, "packet.Unserialize WARNING result is None")
        return None
    if type(newobject) != types.InstanceType:
        io.log(6, "packet.Unserialize WARNING not an instance: " + str(newobject))
        return None
    if not str(newobject.__class__).count('packet.Signed'):
        io.log(6, "packet.Unserialize WARNING not a packet: " + str(newobject.__class__))
        return None
    return newobject

def MakePacket(Command, OwnerID, CreatorID, PacketID, Payload, RemoteID):
    """
    Just calls the constructor of packet class.
    """
    result = Signed(Command, OwnerID, CreatorID, PacketID, Payload, RemoteID)
    return result

def MakePacketInThread(CallBackFunc, Command, OwnerID, CreatorID, PacketID, Payload, RemoteID):
    """
    Signing packets is not atomic operation, so can be moved out from the main thread. 
    """
    d = threads.deferToThread(MakePacket, Command, OwnerID, CreatorID, PacketID, Payload, RemoteID)
    d.addCallback(CallBackFunc)

def MakePacketDeferred(Command, OwnerID, CreatorID, PacketID, Payload, RemoteID):
    """
    Another nice way to create a signed packet.
    """
    return threads.deferToThread(MakePacket, Command, OwnerID, CreatorID, PacketID, Payload, RemoteID)

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    io.init()
    io.SetDebug(18)
    import settings
    settings.init()
    crypto.InitMyKey()
    p = Unserialize(io.ReadBinaryFile(sys.argv[1]))
    print p
    
    
    
