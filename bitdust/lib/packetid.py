#!/usr/bin/python
# packetid.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

Backup ID is just a short form:
    <path ID>/<version Name>

Remote ID may have a different forms:
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


See module ``p2p.backup_fs`` to learn how Path ID is generated from file or folder path.
"""

from __future__ import absolute_import
import time
import re
import random

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
        _LastUniqueNumber = int(time.time()*100.0)
    _LastUniqueNumber += 1
    if _LastUniqueNumber > 100000000000000:
        _LastUniqueNumber = int(time.time()*100.0)
    return str(int(random.getrandbits(8))) + str(_LastUniqueNumber)


def MakePacketID(backupID, blockNumber, supplierNumber, dataORparity, normalize_key_alias=True):
    """
    Create a full packet ID from backup ID and other parts
    Such call:

        MakePacketID('alice@idhost.org:0/0/1/0/F20131120053803PM', 1234, 63, 'Data')

    will return:

        'master$alice@idhost.org:0/0/1/0/F20131120053803PM/1234-63-Data'
    """
    if normalize_key_alias:
        if '$' not in backupID:
            backupID = 'master$' + backupID
    return '%s/%d-%d-%s' % (
        backupID,
        blockNumber,
        supplierNumber,
        dataORparity,
    )


def MakeBackupID(customer=None, path_id='0', version=None, normalize_key_alias=True, key_alias=None):
    """
    Run:

        MakeBackupID('alice@idhost.org', '0/0/1/0', 'F20131120053803PM')

    Will create a string like that:

        "master$alice@idhost.org:0/0/1/0/F20131120053803PM"
    """
    if normalize_key_alias:
        if not customer:
            from bitdust.userid import my_id
            customer = my_id.getGlobalID(key_alias=key_alias or 'master')
    if customer:
        if '$' not in customer and normalize_key_alias:
            customer = '{}${}'.format(key_alias or 'master', customer)
        if version:
            return '{}:{}/{}'.format(customer, path_id, version)
        return '{}:{}'.format(customer, path_id)
    if version:
        return '{}/{}'.format(path_id, version)
    return path_id


def Valid(packetID):
    """
    Must be in short form, without global user ID:

        0/1/2/F20131120053803PM/3-4-Data
        0/1/2/F20131120053803PM
        0/1/2

    """
    user, _, shortPacketID = packetID.rpartition(':')
    if user:
        return False
    head, x, tail = shortPacketID.rpartition('/')
    pathID = ''
    version = ''
    if not x and not head:
        # this seems to be a shortest pathID: 0, 1, 2, ...
        try:
            int(tail)
        except:
            return False
        pathID = tail
    if tail.endswith('-Data') or tail.endswith('-Parity'):
        if not IsPacketNameCorrect(tail):
            return False
        pathID, _, version = head.rpartition('/')
    else:
        pathID = shortPacketID
        if IsCanonicalVersion(tail):
            version = tail
            pathID = head
    if version and not IsCanonicalVersion(version):
        return False
    if not IsPathIDCorrect(pathID):
        return False
    return True


def Split(packetID, normalize_key_alias=True):
    """
    Split a full packet ID into tuple of 5 parts:

        packetid.Split("alice@idhost.org:0/0/1/0/F20131120053803PM/0-1-Data")
        ('master$alice@idhost.org', '0/0/1/0/F20131120053803PM', 0, 1, 'Data')
    """
    try:
        backupID, _, fileName = packetID.rpartition('/')
        blockNum, supplierNum, dataORparity = fileName.split('-')
        blockNum = int(blockNum)
        supplierNum = int(supplierNum)
        customerGlobalID, _, remotePathWithVersion = backupID.rpartition(':')
    except:
        return None, None, None, None, None
    if normalize_key_alias:
        if '$' not in customerGlobalID:
            customerGlobalID = 'master$' + customerGlobalID
    return customerGlobalID, remotePathWithVersion, blockNum, supplierNum, dataORparity


def SplitFull(packetID, normalize_key_alias=True):
    """
    Almost the same but return 6 parts:

        packetid.SplitFull("alice@idhost.org:0/0/1/0/F20131120053803PM/0-1-Data")
        ('master$alice@idhost.org', '0/0/1/0', 'F20131120053803PM', 0, 1, 'Data')
    """
    try:
        backupID, _, fileName = packetID.rpartition('/')
        pathID, _, versionName = backupID.rpartition('/')
        blockNum, supplierNum, dataORparity = fileName.split('-')
        blockNum = int(blockNum)
        supplierNum = int(supplierNum)
        customerGlobalID, _, remotePath = pathID.rpartition(':')
    except:
        return None, None, None, None, None, None
    if normalize_key_alias:
        if '$' not in customerGlobalID:
            customerGlobalID = 'master$' + customerGlobalID
    return customerGlobalID, remotePath, versionName, blockNum, supplierNum, dataORparity


def SplitVersionFilename(packetID, normalize_key_alias=True):
    """
    Return 4 parts:

        packetid.SplitVersionFilename("alice@idhost.org:0/0/1/0/F20131120053803PM/0-1-Data")
        ('master$alice@idhost.org', '0/0/1/0', 'F20131120053803PM', '0-1-Data')
    """
    try:
        backupID, _, fileName = packetID.rpartition('/')
        pathID, _, versionName = backupID.rpartition('/')
        customerGlobalID, _, remotePath = pathID.rpartition(':')
    except:
        return None, None, None, None
    if normalize_key_alias:
        if '$' not in customerGlobalID:
            customerGlobalID = 'master$' + customerGlobalID
    return customerGlobalID, remotePath, versionName, fileName


def SplitBackupID(backupID, normalize_key_alias=True):
    """
    This takes a backup ID string and split by 3 parts:

        packetid.SplitBackupID('alice@idhost.org:0/0/1/0/F20131120053803PM')
        ('master$alice@idhost.org', '0/0/1/0', 'F20131120053803PM')
    """
    try:
        pathID, _, versionName = backupID.rpartition('/')
        customerGlobalID, _, pathID = pathID.rpartition(':')
    except:
        return None, None, None
    if normalize_key_alias:
        if '$' not in customerGlobalID:
            customerGlobalID = 'master$' + customerGlobalID
    return customerGlobalID, pathID, versionName


def SplitBackupIDFull(backupID, normalize_key_alias=True):
    """
    This takes a backup ID string and split by 4 parts:

        packetid.SplitBackupID('share_1234$alice@idhost.org:0/0/1/0/F20131120053803PM')
        ('share_1234', 'alice@idhost.org', '0/0/1/0', 'F20131120053803PM')
    """
    try:
        pathID, _, versionName = backupID.rpartition('/')
        customerGlobalID, _, pathID = pathID.rpartition(':')
        keyAlias, _, customerGlobalID = customerGlobalID.partition('$')
    except:
        return None, None, None, None
    if normalize_key_alias:
        if not keyAlias:
            keyAlias = 'master'
    return keyAlias, customerGlobalID, pathID, versionName


def SplitPacketID(packetID, normalize_key_alias=True):
    """
    This takes a full packet ID string and split by 2 parts:

        packetid.SplitBackupID('alice@idhost.org:0/0/1/0/F20131120053803PM/1-2-Data')
        ('master$alice@idhost.org', '0/0/1/0/F20131120053803PM/1-2-Data')
    """
    try:
        customerGlobalID, _, dataID = packetID.rpartition(':')
    except:
        return None, None
    if normalize_key_alias:
        if '$' not in customerGlobalID:
            customerGlobalID = 'master$' + customerGlobalID
    return customerGlobalID, dataID


def SplitKeyOwnerData(packetID):
    """
    This takes a full packet ID string and split by 3 parts:

        packetid.SplitBackupID('abcd$alice@idhost.org:0/0/1/0/F20131120053803PM/1-2-Data')
        ('abcd', 'alice@idhost.org', '0/0/1/0/F20131120053803PM/1-2-Data')
    """
    try:
        fullGlobalID, _, dataID = packetID.rpartition(':')
    except:
        return None, None
    if '$' not in fullGlobalID:
        fullGlobalID = 'master$' + fullGlobalID
    keyAlias, _, customerID = fullGlobalID.partition('$')
    return keyAlias, customerID, dataID


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
            user, _, host = customerGlobalID.rpartition('@')
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
    pathID, _, version = backupID.rpartition('/')
    if not IsCanonicalVersion(version):
        return False
    if not IsPathIDCorrect(pathID, customer_id_mandatory=customer_id_mandatory):
        return False
    # TODO: more strict validation
    return True


def IsGlobalPathCorrect(globPath, customer_id_mandatory=False):
    """
    Validate a given ``globPath``, must have such format:

        some_key$alice@idhost.org:myfiles/flowers/cactus.png
    """
    customerGlobalID, remotePath = SplitPacketID(globPath)
    if customer_id_mandatory:
        from bitdust.userid import global_id
        return global_id.IsValidGlobalUser(customerGlobalID)
    if not remotePath:
        return False
    parts = remotePath.split('/')
    if len(parts) > 50:
        return False
    # TODO: more strict validation
    return True


def BidBnSnDp(packetID):
    """
    A wrapper for ``Split()`` method, returns tuple of 4 items.
    """
    tupl5 = Split(packetID)
    return MakeBackupID(tupl5[0], tupl5[1]), tupl5[2], tupl5[3], tupl5[4]


def UsrBidBnSnDp(packetID):
    """
    Another wrapper for ``Split()`` method.
    """
    return Split(packetID)


def KeyAlias(inp, normalize_key_alias=True):
    if not inp:
        return None
    customerGlobalID = inp
    if ':' in inp:
        try:
            customerGlobalID, _, _ = inp.partition(':')
        except:
            return None
    if '$' not in customerGlobalID and normalize_key_alias:
        customerGlobalID = 'master$' + customerGlobalID
    keyAlias, _, _ = customerGlobalID.partition('$')
    return str(keyAlias)


def CustomerIDURL(backupID, as_field=True):
    """
    A wrapper for ``Split()`` method to get customer idurl from backup ID.
    """
    user, _, _ = backupID.strip().rpartition(':')
    if not user:
        from bitdust.userid import my_id
        if as_field:
            return my_id.getIDURL()
        return my_id.getIDURL().to_bin()
    from bitdust.userid import global_id
    return global_id.GlobalUserToIDURL(user, as_field=as_field)


def KeyAliasCustomer(backupID, as_field=True):
    """
    A wrapper for ``Split()`` method to get key alias and customer idurl from backup ID.
    """
    user, _, _ = backupID.strip().rpartition(':')
    if not user:
        from bitdust.userid import my_id
        if as_field:
            return 'master', my_id.getIDURL()
        return 'master', my_id.getIDURL().to_bin()
    key_alias, _, user = user.strip().partition('$')
    from bitdust.userid import global_id
    return key_alias, global_id.GlobalUserToIDURL(user, as_field=as_field)


def RemotePath(backupID):
    """
    A wrapper for ``Split()`` method to get only remote_path from backup ID.
    """
    _, _, remote_path = backupID.strip().rpartition(':')
    if not remote_path:
        return ''
    return remote_path


def BackupID(packetID):
    """
    A wrapper for ``Split()`` method to get the first part - backup ID.
    """
    customerGlobalID, remotePathWithVersion, _, _, _ = Split(packetID)[1]
    return MakeBackupID(customer=customerGlobalID, path_id=remotePathWithVersion)


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

    ['0', '0/0', '0/0/1', '0/0/1/0', '0/0/1/0/F20131120053803PM', '0/0/1/0/F20131120053803PM/0-1-Data']
    """
    path = ''
    for word in ID.split('/'):
        if path:
            path += '/'
        path += word
        yield path


def LatestBackupID(backupID):
    """
    Create IDURL object from input key_id and return new key_id (with same key_alias) from that IDURL object.
    This way you can be sure that given key_id is pointing to the correct owner IDURL.
    """
    if not backupID:
        return backupID
    from bitdust.userid import global_id
    glob_id = global_id.ParseGlobalID(backupID, as_field=True)
    if not glob_id['idurl']:
        from bitdust.logs import lg
        lg.err('invalid backupID: %r' % backupID)
        return backupID
    return global_id.MakeGlobalID(
        key_id=glob_id['key_id'],
        path=glob_id['path'],
        version=glob_id['version'],
    )


def MakeQueueMessagePacketID(queue_id, unique_id):
    """
    Prepare text string to be used as PacketID when sending queue message.
    """
    return 'queue_{}_{}'.format(queue_id, unique_id)


def SplitQueueMessagePacketID(packet_id):
    """
    Extract `queue_id` and `unique_id` from PacketID expecting to have queue_message format.
    """
    if packet_id.startswith('queue_'):
        packet_id = packet_id[6:]
    queue_id, _, unique_id = packet_id.rpartition('_')
    return queue_id, unique_id
