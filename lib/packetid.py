#!/usr/bin/python
# packetid.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (packetid.py) is part of BitDust Software.
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
.. module:: packetid

Various methods to work with packet/path/backup ID.

We have a standard way of making the PacketID strings for many packets.
Note - we return strings and not integers.

Packet ID consists of several parts:
    <path ID>/<version Name>/<block number>-<supplier number>-<'Data'|'Parity'>

So Backup ID is just a short form:
    <path ID>/<version Name>

See module ``p2p.backup_fs`` to learn how Path ID is generated from file or folder path.
"""

import time
import re

#------------------------------------------------------------------------------

_LastUniqueNumber = 0

#------------------------------------------------------------------------------


def UniqueID():
    """
    Generate a unique string ID.
    We wrap around every billion, old packets should be gone by then
    """
    global _LastUniqueNumber
    _LastUniqueNumber += 1
    if _LastUniqueNumber > 1000000000:
        _LastUniqueNumber = 0
    inttime = int(time.time() * 100.0)
    if _LastUniqueNumber < inttime:
        _LastUniqueNumber = inttime
    return str(_LastUniqueNumber)


def MakePacketID(backupID, blockNumber, supplierNumber, dataORparity):
    """
    Create a full packet ID from backup ID and other parts.
        import packetid
        packetid.MakePacketID('0/0/1/0/F20131120053803PM', 1234, 63, 'Data')
        '0/0/1/0/F20131120053803PM/1234-63-Data'
    """
    return backupID + '/' + str(blockNumber) + '-' + str(supplierNumber) + '-' + dataORparity


def Valid(packetID):
    """
    The packet ID may have a different forms:
        - full:     0/0/1/0/F20131120053803PM/0-1-Data
        - backupID: 0/0/1/0/F20131120053803PM
        - pathID:   0/0/1/0

    Here is:
        - pathID:        0/0/1/0
        - versionName:   F20131120053803PM
        - blockNum :     0
        - supplierNum :  1
        - dataORparity : Data
    """
    head, x, tail = packetID.rpartition('/')
    if x == '' and head == '':
        # this seems to be a shortest pathID: 0, 1, 2, ...
        try:
            x = int(tail)
        except:
            return False
        return True
    if tail.endswith('-Data') or tail.endswith('-Parity'):
        # seems to be in the full form
        if not IsPacketNameCorrect(tail):
            return False
        pathID, x, versionName = head.rpartition('/')
        if not IsCanonicalVersion(versionName):
            return False
        if not IsPathIDCorrect(pathID):
            return False
        return True
    if IsPathIDCorrect(packetID):
        # we have only two options now, let's if this is a pathID
        return True
        # this should be a backupID - no other cases
    if IsCanonicalVersion(tail) and IsPathIDCorrect(head):
        return True
    # something is not fine with that string
    return False


def Split(packetID):
    """
    Split a full packet ID into tuple of 4 parts.
        packetid.Split("0/0/1/0/F20131120053803PM/0-1-Data")
        ('0/0/1/0/F20131120053803PM', 0, 1, 'Data')
    """
    try:
        backupID, x, fileName = packetID.rpartition('/')
        blockNum, supplierNum, dataORparity = fileName.split('-')
        blockNum = int(blockNum)
        supplierNum = int(supplierNum)
    except:
        return None, None, None, None
    return backupID, blockNum, supplierNum, dataORparity


def SplitFull(packetID):
    """
    Almost the same but return 5 parts:
        packetid.SplitFull("0/0/1/0/F20131120053803PM/0-1-Data")
        ('0/0/1/0', 'F20131120053803PM', 0, 1, 'Data')
    """
    try:
        backupID, x, fileName = packetID.rpartition('/')
        pathID, x, versionName = backupID.rpartition('/')
        blockNum, supplierNum, dataORparity = fileName.split('-')
        blockNum = int(blockNum)
        supplierNum = int(supplierNum)
    except:
        return None, None, None, None, None
    return pathID, versionName, blockNum, supplierNum, dataORparity


def SplitVersionFilename(packetID):
    """
    Return 3 parts:
        packetid.SplitVersionFilename("0/0/1/0/F20131120053803PM/0-1-Data")
        ('0/0/1/0', 'F20131120053803PM', '0-1-Data')
    """
    try:
        backupID, x, fileName = packetID.rpartition('/')
        pathID, x, versionName = backupID.rpartition('/')
    except:
        return None, None, None
    return pathID, versionName, fileName


def SplitBackupID(backupID):
    """
    This takes a short string, only backup ID:
        packetid.SplitBackupID('0/0/1/0/F20131120053803PM')
        ('0/0/1/0', 'F20131120053803PM')
    """
    try:
        pathID, x, versionName = backupID.rpartition('/')
    except:
        return None, None
    return pathID, versionName


def IsCanonicalVersion(versionName):
    """
    Check given ``versionName`` to have a valid format.
    """
    return re.match('^F\d+?(AM|PM)\d*?$', versionName) is not None


def IsPacketNameCorrect(fileName):
    """
    Check the ``fileName`` (this is a last 3 parts of packet ID) to have a valid format.
    """
    return re.match('^\d+?\-\d+?\-(Data|Parity)$', fileName) is not None


def IsPathIDCorrect(pathID):
    """
    Validate a given ``pathID``, should have only digits and '/' symbol.
    """
    # TODO more strict validation
    return pathID.replace('/', '').isdigit()


def IsBackupIDCorrect(backupID):
    """
    Validate a given ``backupID``, must have such format: 0/0/1/0/F20131120053803PM.
    """
    pathID, x, version = backupID.rpartition('/')
    if not IsCanonicalVersion(version):
        return False
    if not IsPathIDCorrect(pathID):
        return False
    return True


def BidBnSnDp(packetID):
    """
    A wrapper for ``Split()`` method.
    """
    return Split(packetID)


def BackupID(packetID):
    """
    A wrapper for ``Split()`` method to get the first part - backup ID.
    """
    return Split(packetID)[0]


def BlockNumber(packetID):
    """
    A wrapper for ``Split()`` method to get the second part - block number.
    """
    return Split(packetID)[1]


def SupplierNumber(packetID):
    """
    A wrapper for ``Split()`` method to get the third part - supplier number.
    """
    return Split(packetID)[2]


def DataOrParity(packetID):
    """
    A wrapper for ``Split()`` method to get the last part - is this Data or Parity packet .
    """
    return Split(packetID)[3]


def parentPathsList(ID):
    """
    Return an iterator to go thru all parent paths of the given path ``ID``:
        list(packetid.parentPathsList('0/0/1/0/F20131120053803PM/0-1-Data'))
        ['0', '0/0', '0/0/1', '0/0/1/0', '0/0/1/0/F20131120053803PM', '0/0/1/0/F20131120053803PM/0-1-Data']
    """
    path = ''
    for word in ID.split('/'):
        if path:
            path += '/'
        path += word
        yield path
