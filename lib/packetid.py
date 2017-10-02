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
.. module:: packetid.

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
    if _LastUniqueNumber == 0:
        _LastUniqueNumber = int(time.time() * 100.0)
    _LastUniqueNumber += 1
    if _LastUniqueNumber > 100000000000000:
        _LastUniqueNumber = int(time.time() * 100.0)
    # inttime = int(time.time() * 100.0)
    # if _LastUniqueNumber < inttime:
    #     _LastUniqueNumber = inttime
    return str(_LastUniqueNumber)


def MakePacketID(backupID, blockNumber, supplierNumber, dataORparity):
    """
    Create a full packet ID from backup ID and other parts
    Such call:

        MakePacketID('alice@idhost.org:0/0/1/0/F20131120053803PM', 1234, 63, 'Data')

    will return:

        'alice@idhost.org:0/0/1/0/F20131120053803PM/1234-63-Data'
    """
    return backupID + '/' + str(blockNumber) + '-' + str(supplierNumber) + '-' + dataORparity


def MakeBackupID(customer, path_id):
    """
    Will create something like:

        "alice@idhost.org:0/0/1/0/F20131120053803PM"
    """
    return '{}:{}'.format(customer, path_id)


def Valid(packetID):
    """
    The packet ID may have a different forms:

        - full:     alice@idhost.org:0/0/1/0/F20131120053803PM/0-1-Data
        - backupID: alice@idhost.org:0/0/1/0/F20131120053803PM
        - pathID:   alice@idhost.org:0/0/1/0

    Here is:
        - customer:      alice@idhost.org
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
    Split a full packet ID into tuple of 5 parts:

        packetid.Split("alice@idhost.org:0/0/1/0/F20131120053803PM/0-1-Data")
        ('alice@idhost.org', '0/0/1/0/F20131120053803PM', 0, 1, 'Data')
    """
    try:
        backupID, _, fileName = packetID.rpartition('/')
        blockNum, supplierNum, dataORparity = fileName.split('-')
        blockNum = int(blockNum)
        supplierNum = int(supplierNum)
        customerGlobalID, remotePathWithVersion = backupID.rsplit(':')
    except:
        return None, None, None, None, None
    return customerGlobalID, remotePathWithVersion, blockNum, supplierNum, dataORparity


def SplitFull(packetID):
    """
    Almost the same but return 6 parts:

        packetid.SplitFull("alice@idhost.org:0/0/1/0/F20131120053803PM/0-1-Data")
        ('alice@idhost.org', '0/0/1/0', 'F20131120053803PM', 0, 1, 'Data')
    """
    try:
        backupID, _, fileName = packetID.rpartition('/')
        pathID, _, versionName = backupID.rpartition('/')
        blockNum, supplierNum, dataORparity = fileName.split('-')
        blockNum = int(blockNum)
        supplierNum = int(supplierNum)
        customerGlobalID, remotePath = pathID.rsplit(':')
    except:
        return None, None, None, None, None, None
    return customerGlobalID, remotePath, versionName, blockNum, supplierNum, dataORparity


def SplitVersionFilename(packetID):
    """
    Return 4 parts:

        packetid.SplitVersionFilename("alice@idhost.org:0/0/1/0/F20131120053803PM/0-1-Data")
        ('alice@idhost.org', '0/0/1/0', 'F20131120053803PM', '0-1-Data')
    """
    try:
        backupID, _, fileName = packetID.rpartition('/')
        pathID, _, versionName = backupID.rpartition('/')
        customerGlobalID, remotePath = pathID.rsplit(':')
    except:
        return None, None, None, None
    return customerGlobalID, remotePath, versionName, fileName


def SplitBackupID(backupID):
    """
    This takes a backup ID string and split by 3 parts:

        packetid.SplitBackupID('alice@idhost.org:0/0/1/0/F20131120053803PM')
        ('alice@idhost.org', '0/0/1/0', 'F20131120053803PM')
    """
    try:
        pathID, _, versionName = backupID.rpartition('/')
        customerGlobalID, remotePath = pathID.rsplit(':')
    except:
        return None, None, None
    return customerGlobalID, remotePath, versionName


def SplitPacketID(backupID):
    """
    This takes a backup ID string and split by 2 parts:

        packetid.SplitBackupID('alice@idhost.org:0/0/1/0/F20131120053803PM')
        ('alice@idhost.org', '0/0/1/0/F20131120053803PM')
    """
    try:
        customerGlobalID, remotePath = backupID.rsplit(':')
    except:
        return None, None
    return customerGlobalID, remotePath


def IsCanonicalVersion(versionName):
    """
    Check given ``versionName`` to have a valid format.
    """
    return re.match('^F\d+?(AM|PM)\d*?$', versionName) is not None


def IsPacketNameCorrect(fileName):
    """
    Check the ``fileName`` (this is a last 3 parts of packet ID) to have a
    valid format.
    """
    return re.match('^\d+?\-\d+?\-(Data|Parity)$', fileName) is not None


def IsPathIDCorrect(pathID, customer_id_mandatory=False):
    """
    Validate a given ``pathID``, should have only digits and '/' symbol.
    """
    try:
        customerGlobalID, remotePath = SplitPacketID(pathID)
    except:
        return False
    if customer_id_mandatory:
        try:
            user, host = customerGlobalID.split('@')
        except:
            return False
        if not user:
            return False
        if not host:
            return False
    # TODO: more strict validation
    return remotePath.replace('/', '').isdigit()


def IsBackupIDCorrect(backupID, customer_id_mandatory=False):
    """
    Validate a given ``backupID``, must have such format:

        alice@idhost.org:0/0/1/0/F20131120053803PM.
    """
    if not IsPathIDCorrect(backupID, customer_id_mandatory=customer_id_mandatory):
        return False
    _, _, version = backupID.rpartition('/')
    if not IsCanonicalVersion(version):
        return False
    # TODO: more strict validation
    return True


def IsGlobalPathCorrect(globPath, customer_id_mandatory=False):
    """
    Validate a given ``globPath``, must have such format:

        alice@idhost.org:myfiles/flowers/cactus.png
    """
    customerGlobalID, remotePath = SplitPacketID(globPath)
    if not customerGlobalID and customer_id_mandatory:
        return False
    if not remotePath:
        return False
    parts = remotePath.split('/')
    if len(parts) > 50:
        return False
    # TODO: more strict validation
    return True


def BidBnSnDp(packetID):
    """
    A wrapper for ``Split()`` method.
    """
    return Split(packetID)[1:]


def UsrBidBnSnDp(packetID):
    """
    Another wrapper for ``Split()`` method.
    """
    return Split(packetID)


def CustomerIDURL(backupID):
    """
    A wrapper for ``Split()`` method to get customer idurl from backup ID.
    """
    from userid import global_id
    return global_id.GlobalIDToUrl(Split(backupID)[0])


def BackupID(packetID):
    """
    A wrapper for ``Split()`` method to get the first part - backup ID.
    """
    return Split(packetID)[1]


def BlockNumber(packetID):
    """
    A wrapper for ``Split()`` method to get the second part - block number.
    """
    return Split(packetID)[2]


def SupplierNumber(packetID):
    """
    A wrapper for ``Split()`` method to get the third part - supplier number.
    """
    return Split(packetID)[3]


def DataOrParity(packetID):
    """
    A wrapper for ``Split()`` method to get the last part - is this Data or Parity packet .
    """
    return Split(packetID)[4]


def parentPathsList(ID):
    """
    Return an iterator to go thru all parent paths of the given path ``ID``:
    list(packetid.parentPathsList('0/0/1/0/F20131120053803PM/0-1-Data'))

    ['0', '0/0', '0/0/1', '0/0/1/0', '0/0/1/0/F20131120053803PM',
    '0/0/1/0/F20131120053803PM/0-1-Data']
    """
    path = ''
    for word in ID.split('/'):
        if path:
            path += '/'
        path += word
        yield path
