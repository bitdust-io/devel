#!/usr/bin/python
# signed.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (signed.py) is part of BitDust Software.
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
.. module:: signed.

These packets usually hold on the order of 1 MB.
Something equal to a packet number so we can detect duplicates in transport.
Packet Fields are all strings (no integers, objects, etc)
    - Command : Legal Commands are in bitdust/lib/commands.py
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

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys

from twisted.internet import threads

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from p2p import commands

from lib import packetid
from lib import nameurl
from lib import utime
from lib import strng
from lib import serialization

from contacts import contactsdb

from crypt import key
from crypt import my_keys

from userid import my_id

#------------------------------------------------------------------------------


class Packet(object):
    """
    Init with: Command, OwnerID, CreatorID, PacketID, Payload, RemoteID The
    core class.

    Represents a data packet in the network. Payload can be encrypted
    using bitdust.key.encrypted.Block. We expect remote user run the
    correct software. His BitDust must verify signature of that packet .
    If you want to encrypt the fields and so hide that service traffic
    completely - do that in the transport protocols. Need to transfer
    our public key to remote peer and than he can send us a safe
    messages. This is outside work, here is most important things to
    make all network working.
    """

    def __init__(self, Command, OwnerID, CreatorID, PacketID, Payload, RemoteID, KeyID=None, Date=None, Signature=None, ):
        """
        Init all fields and sign the packet.
        """
        # Legal Commands are in commands.py
        self.Command = strng.to_text(Command)
        # who owns this data and pays bills - http://cate.com/id1.xml
        self.OwnerID = strng.to_bin(OwnerID)
        # signer - http://cate.com/id1.xml - might be an authorized scrubber
        self.CreatorID = strng.to_bin(CreatorID)
        # string of the above 4 "Number"s with "-" separator to uniquely identify a packet
        # on the local machine.  Can be used for filenames, and to prevent duplicates.
        self.PacketID = strng.to_text(PacketID)
        # create a string to remember current world time
        self.Date = strng.to_text(Date or utime.sec1970_to_datetime_utc().strftime("%Y/%m/%d %I:%M:%S %p"))
        # datetime.datetime.now().strftime("%Y/%m/%d %I:%M:%S %p")
        # main body of binary data
        self.Payload = strng.to_bin(Payload)
        # want full IDURL for other party so troublemaker could not
        # use his packets to mess up other nodes by sending it to them
        self.RemoteID = strng.to_bin(RemoteID)
        # which private key to use to generate signature
        self.KeyID = strng.to_text(KeyID or my_id.getGlobalID(key_alias='master'))
        if Signature:
            self.Signature = Signature
        else:
            # signature on Hash is always by CreatorID
            self.Signature = None
            # must be signed to be valid
            self.Sign()
        # stores list of related objects packet_in() or packet_out()
        self.Packets = []

    def __repr__(self):
        args = '%s(%s)' % (str(self.Command), str(self.PacketID))
        if _Debug:
            if lg.is_debug(_DebugLevel):
                args += ' %s|%s for %s' % (
                    nameurl.GetName(self.OwnerID),
                    nameurl.GetName(self.CreatorID),
                    nameurl.GetName(self.RemoteID))
        return 'signed{%s}' % args

    def Sign(self):
        """
        Call ``GenerateSignature`` and save the result.
        Usually just done at packet creation.
        """
        self.Signature = self.GenerateSignature()
        return self

    def GenerateHashBase(self):
        """
        This make a long string containing all needed fields of ``packet``
        (without Signature).
        Just to be able to generate a hash of the whole packet .
        """
        sep = b"-"
        stufftosum = b""
        try:
            stufftosum += strng.to_bin(self.Command)
            stufftosum += sep
            stufftosum += strng.to_bin(self.OwnerID)
            stufftosum += sep
            stufftosum += strng.to_bin(self.CreatorID)
            stufftosum += sep
            stufftosum += strng.to_bin(self.PacketID)
            stufftosum += sep
            stufftosum += strng.to_bin(self.Date)
            stufftosum += sep
            stufftosum += strng.to_bin(self.Payload)
            stufftosum += sep
            stufftosum += strng.to_bin(self.RemoteID)
            if self.KeyID:
                stufftosum += sep
                stufftosum += strng.to_bin(self.KeyID)
        except Exception as exc:
            lg.exc()
            raise exc
        return stufftosum

    def GenerateHash(self):
        """
        Call ``crypt.key.Hash`` to create a hash code for that ``packet``.
        """
        return key.Hash(self.GenerateHashBase())

    def GenerateSignature(self):
        """
        Call ``crypt.key.Sign`` to generate digital signature.
        """
        _hash_base = self.GenerateHash()
        if not self.KeyID or self.KeyID == my_id.getGlobalID(key_alias='master'):
            return key.Sign(_hash_base)
        return my_keys.sign(self.KeyID, _hash_base)

    def SignatureChecksOut(self):
        """
        This check correctness of signature, uses ``crypt.key.Verify``. To
        verify we need 3 things:

        - the packet ``Creator`` identity ( it keeps the public key ),
        - hash of that packet - just call ``GenerateHash()`` to make it,
        - the signature itself.
        """
        CreatorIdentity = contactsdb.get_contact_identity(self.CreatorID)
        if CreatorIdentity is None:
            OwnerIdentity = contactsdb.get_contact_identity(self.OwnerID)
            if OwnerIdentity is None:
                lg.out(1, "signed.SignatureChecksOut ERROR could not get Identity for " + self.CreatorID + " so returning False")
                return False
            CreatorIdentity = OwnerIdentity
        Result = key.Verify(CreatorIdentity, self.GenerateHash(), self.Signature)
        return Result

    def Ready(self):
        """
        I was playing with generating signatures in separate thread, so this is
        just to check that Signature already exists.
        """
        return self.Signature is not None

    def Valid(self):
        """
        ``Valid()`` should check every one of packet header fields: 1) that
        command is one of the legal commands 2) signature is good (which means
        the hashcode is good) Rest PREPRO: 3) all the number fields are just
        numbers 4) length is within legal limits 5) check that URL is a good
        URL 6) that DataOrParity is either "data" or "parity" 7) that Creator
        is equal to owner or a scrubber for owner 8) etc.
        """
        if not self.Ready():
            lg.out(4, "signed.Valid packet is not ready yet " + str(self))
            return False
        if not commands.IsCommand(self.Command):
            lg.warn("signed.Valid bad Command " + str(self.Command))
            return False
        if not self.SignatureChecksOut():
            lg.warn("signed.Valid Signature IS NOT VALID!!!")
            return False
        return True

    def BackupID(self):
        """
        """
        backupID, _, _ = self.PacketID.rpartition('/')
        return backupID

    def BlockNumber(self):
        """
        A wrapper for ``lib.packetid.BlockNumber`` on top of self.PacketID.
        """
        return packetid.BlockNumber(self.PacketID)

    def DataOrParity(self):
        """
        A wrapper for ``lib.packetid.DataOrParity`` on top of self.PacketID.
        """
        return packetid.DataOrParity(self.PacketID)

    def SupplierNumber(self):
        """
        A wrapper for ``lib.packetid.SupplierNumber`` on top of self.PacketID.
        """
        return packetid.SupplierNumber(self.PacketID)

    def Serialize(self):
        """
        Create a string from packet object.
        This is useful when need to save the packet on disk or send via network.
        """
        dct = {
            'm': self.Command,
            'o': self.OwnerID,
            'c': self.CreatorID,
            'i': self.PacketID,
            'd': self.Date,
            'p': self.Payload,
            'r': self.RemoteID,
            'k': self.KeyID,
            's': self.Signature,
        }        
        if _Debug:
            lg.out(_DebugLevel, 'signed.Serialize %r' % dct)
        src = serialization.DictToBytes(dct, encoding='latin1')
        return src

    def __len__(self):
        """
        Return a length of serialized packet .
        """
        return len(self.Serialize())


class PacketZeroSigned(Packet):
    """
    I was playing with hacking packets and do some debug also.
    """

    def GenerateSignature(self):
        return '0'


def Unserialize(data):
    """
    We expect here a string containing a whole packet object in text form.
    Will return a real object in the memory from given string.
    All class fields are loaded, signature can be verified to be sure - it was truly original string.
    """
    if data is None:
        return None

    dct = serialization.BytesToDict(data, keys_to_text=True, encoding='latin1')

    if _Debug:
        lg.out(_DebugLevel, 'signed.Unserialize %r' % dct)

    try:
        newobject = Packet(
            Command=strng.to_text(dct['m']),
            OwnerID=dct['o'],
            CreatorID=dct['c'],
            PacketID=strng.to_text(dct['i']),
            Date=strng.to_text(dct['d']),
            Payload=dct['p'],
            RemoteID=dct['r'],
            KeyID=strng.to_text(dct['k']),
            Signature=dct['s'],
        )
    except:
        lg.exc()
        newobject = None
    
    if newobject is None:
        lg.warn("result is None")
        return None

    return newobject


def MakePacket(Command, OwnerID, CreatorID, PacketID, Payload, RemoteID):
    """
    Just calls the constructor of packet class.
    """
    result = Packet(Command, OwnerID, CreatorID, PacketID, Payload, RemoteID)
    return result


def MakePacketInThread(CallBackFunc, Command, OwnerID, CreatorID, PacketID, Payload, RemoteID):
    """
    Signing packets is not atomic operation, so can be moved out from the main
    thread.
    """
    d = threads.deferToThread(MakePacket, Command, OwnerID, CreatorID, PacketID, Payload, RemoteID)
    d.addCallback(CallBackFunc)


def MakePacketDeferred(Command, OwnerID, CreatorID, PacketID, Payload, RemoteID):
    """
    Another nice way to create a signed packet .
    """
    return threads.deferToThread(MakePacket, Command, OwnerID, CreatorID, PacketID, Payload, RemoteID)

#------------------------------------------------------------------------------


if __name__ == '__main__':
    bpio.init()
    lg.set_debug_level(18)
    from main import settings
    settings.init()
    key.InitMyKey()
    p = Unserialize(bpio.ReadBinaryFile(sys.argv[1]))
    print(p)
