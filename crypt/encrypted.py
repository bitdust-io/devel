#!/usr/bin/python
#encrypted.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: encrypted_block

Higher level code interfaces with ``encrypted`` so that it does not have to deal
with ECC stuff.  We write or read a large block at a time (maybe 64 MB say).
When writing we generate all the ECC information, and when reading we will
use ECC to recover lost information so user sees whole block still.

We have to go to disk. The normal mode is probably that there are a few machines that
are slow and the rest move along. We want to get the backup secure as soon as possible.
It can be secure even if 5 to 10 suppliers are not finished yet.  But this could be
a lot of storage, so we should be using disk.

We want to generate a pool of writes to do, and put in more as it gets below some
MB limit. But we should not be limited by a particular nodes speed.

The ``packet`` will have all the info about where it is going etc.
We number them with our block number and the supplier numbers.

Going to disk should let us do restarts after crashes without much trouble.

Digital signatures and timestamps are done on ``encrypted_blocks``.
Signatures are also done on ``packets``.

RAIDMAKE:
    This object can be asked to generate any/all ``packet(s)`` that would come from this ``encrypted_block``.
RAIDREAD:
    It can also rebuild the ``encrypted_block`` from packets and will
    generate the read requests to get fetch the packets.
"""

#------------------------------------------------------------------------------ 

from logs import lg

from lib import misc

from userid import contacts
from userid import my_id

import key

#------------------------------------------------------------------------------ 

class Block:
    """
    A class to represent an encrypted Data block.
    The only 2 things secret in here will be the ``EncryptedSessionKey`` and ``EncryptedData``.
    Scrubbers may combine-packets/unserialize/inspect-blocks/check-signatures.

    CreatorID              http://cate.com/id1.xml  - so people can check signature - says PK type too
    BackupID               Creator's ID for the backup this packet is part of
    BlockNumber            number of this block
    EncryptedData          data may have some padding so multiple of crypto chunck size
                           and multiple of #nodes in eccmap (usually 64) for division
                           into packets
    Length                 real length of data when cleartext (encrypted may be padded)
    LastBlock              should now be "True" or "False" - careful in using
    SessionKeyType         which crypto is used for session key
    EncryptedSessionKey    encrypted with our public key so only we can read this
    Other                  could be be for professional timestamp company or other future features
    Signature              digital signature by Creator - verifiable by public key in creator identity
    """

    def __init__ (self, CreatorID, BackupID, BlockNumber, SessionKey, SessionKeyType, LastBlock, Data,):
        self.CreatorID = CreatorID
        self.BackupID = BackupID
        self.BlockNumber = BlockNumber
        self.EncryptedSessionKey = key.EncryptLocalPK(SessionKey)
        self.SessionKeyType = SessionKeyType
        self.Length = len(Data)
        self.LastBlock = bool(LastBlock)               
        self.EncryptedData = key.EncryptWithSessionKey(SessionKey, Data) # DataLonger
        self.Signature = None
        self.Sign()

    def __repr__(self):
        return 'encrypted_block (BackupID=%s BlockNumber=%s Length=%s LastBlock=%s)' % (str(self.BackupID), str(self.BlockNumber), str(self.Length), self.LastBlock)

    def SessionKey(self):
        """
        Return original SessionKey from ``EncryptedSessionKey`` using ``crypt.key.DecryptLocalPK()`` method.
        """
        return key.DecryptLocalPK(self.EncryptedSessionKey)

    def GenerateHashBase(self):
        """
        Generate a single string with all data fields, used to create a hash for that ``encrypted_block``.
        """
        sep = "::::"
        StringToHash = self.CreatorID
        StringToHash += sep + self.BackupID
        StringToHash += sep + str(self.BlockNumber)
        StringToHash += sep + self.SessionKeyType
        StringToHash += sep + self.EncryptedSessionKey
        StringToHash += sep + str(self.Length)
        StringToHash += sep + str(self.LastBlock)
        StringToHash += sep + self.EncryptedData
        return StringToHash

    def GenerateHash(self):
        """
        Create a hash for that ``encrypted_block`` using ``crypt.key.Hash()``.
        """
        return key.Hash(self.GenerateHashBase())

    def Sign(self):
        """
        Generate digital signature for that ``encrypted_block``.
        """
        self.Signature = self.GenerateSignature()  # usually just done at packet creation
        return self

    def GenerateSignature(self):
        """
        Call ``crypt.key.Sign()`` to generate signature.
        """
        return key.Sign(self.GenerateHash())

    def Ready(self):
        """
        Just return True if signature is already created.
        """
        return self.Signature is not None

    def Valid(self):
        """
        Validate signature to verify the ``encrypted_block``.
        """
        if not self.Ready():
            # lg.warn("block is not ready yet " + str(self))
            lg.warn("block is not ready yet " + str(self))
            return False
        hashsrc = self.GenerateHash()
        ConIdentity = contacts.getContact(my_id.getLocalID())
        if ConIdentity is None:
            lg.warn("could not get Identity so returning False")
            return False
        result = key.Verify(ConIdentity, hashsrc, self.Signature)    # At block level only work on own stuff
        return result

    def Data(self):
        """
        Return an original data, decrypt using ``EnctryptedData`` and ``EncryptedSessionKey``.
        """
        SessionKey = self.SessionKey()
        ClearLongData = key.DecryptWithSessionKey(SessionKey, self.EncryptedData)
        return ClearLongData[0:self.Length]    # remove padding

    def Serialize(self):
        """
        Create a string that stores all data fields of that ``encrypted.Block`` object.
        """
        e = misc.ObjectToString(self)
        return e


def Unserialize(data):
    """
    A method to create a ``encrypted.Block`` instance from input string.
    """
    newobject = misc.StringToObject(data)
    return newobject





