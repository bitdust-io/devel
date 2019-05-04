#!/usr/bin/python
# backup_matrix.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (backup_matrix.py) is part of BitDust Software.
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
.. module:: backup_matrix.

The software stores all backup IDs in the memory.
Also we need to keep track of every piece of data.
I have a matrix for every backup: blocks by suppliers.
Every cell in the matrix store short info about single piece (file) of your data.

There are two types of matrix:
1. "remote files"
2. "local files"

A "remote" matrix keeps info about files stored on your suppliers.
They will report this info to you in the command "ListFiles".

A "local" matrix keeps info about local files stored on your machine.
When you doing a backup you create a two copies of your data.
At first it will be stored on your local HDD and then transferred to suppliers.

The local and remote copies of your data is absolutely equal, have same structure and dimension.

Local files can be removed as soon as corresponding remote files gets delivered to suppliers.
But local files is needed to rebuild the data - the "Parity" pieces is used in the RAID code
to reconstruct "Data" pieces. So need to keep track of both "surfaces".
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range
from io import BytesIO

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 12

#------------------------------------------------------------------------------

import os
import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in backup_matrix.py')

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from lib import packetid
from lib import misc
from lib import strng

from main import settings

from contacts import contactsdb

from services import driver

from storage import backup_fs

from userid import my_id
from userid import global_id

#------------------------------------------------------------------------------

_RemoteFiles = {}
_LocalFiles = {}
_RemoteMaxBlockNumbers = {}
_LocalMaxBlockNumbers = {}
_LocalBackupSize = {}
_BackupsInProcess = []
_BackupStatusNotifyCallback = None
_StatusCallBackForGuiBackup = None
_LocalFilesNotifyCallback = None
_UpdatedBackupIDs = set()
_RepaintingTask = None
_RepaintingTaskDelay = 2.0

#------------------------------------------------------------------------------


def init():
    """
    Call this method before all others here. Prepare several things here:

    * start a loop to repaint the GUI when needed
    * scan local files and build the "local" matrix
    * read latest (stored on local disk) ListFiles for suppliers to build "remote" matrix
    """
    lg.out(4, 'backup_matrix.init')
    RepaintingProcess(True)
    ReadLocalFiles()
    ReadLatestRawListFiles()


def shutdown():
    """
    Correct way to finish all things here.
    """
    lg.out(4, 'backup_matrix.shutdown')
    RepaintingProcess(False)

#------------------------------------------------------------------------------


def remote_files():
    """
    This is a "remote" matrix. Here is stored info for all remote files (on
    suppliers HDD's) stored in dictionary. The values are integers::

      -1 : this mean file is missing
      0  : no info comes yet
      1  : this file exist on given remote machine

    This is a dictionary of dictionaries of dictionaries of lists. :-)))
    Values can be accessed this way::

      remote_files()[backupID][blockNumber][dataORparity][supplierNumber]

    Here the keys are:

    - backupID - a unique identifier of that backup, see ``lib.packetid`` module
    - blockNumber - a number of block started from 0, look at ``p2p.backup``
    - dataORparity - can be 'D' for Data packet or 'P' for Parity packets
    - supplierNumber - who should keep that piece?
    """
    global _RemoteFiles
    return _RemoteFiles


def remote_max_block_numbers():
    """
    This is a dictionary to store max block number for every remote backup, by
    backup ID.
    """
    global _RemoteMaxBlockNumbers
    return _RemoteMaxBlockNumbers


def local_files():
    """
    This is a "local" matrix, same structure like ``remote_files()``.

    Keeps info for all local files stored on your HDD. The values are
    integers: 0 or 1 to know that local file exists or not.
    """
    global _LocalFiles
    return _LocalFiles


def local_max_block_numbers():
    """
    Dictionary to store max block number for every local backup.
    """
    global _LocalMaxBlockNumbers
    return _LocalMaxBlockNumbers


def local_backup_size():
    """
    The pieces can have different sizes.

    To get the size of the particular backup need to count size of all
    pieces. Here is a dictionary of counters for every backup.
    """
    global _LocalBackupSize
    return _LocalBackupSize

#------------------------------------------------------------------------------


def GetActiveArray(customer_idurl=None):
    """
    Loops all suppliers and returns who is alive at the moment.

    Return a list with integers: 0 for offline suppler and 1 if he is
    available right now. Uses ``p2p.online_status.isOnline()`` to see
    the current state of supplier.
    """
    from p2p import online_status
    activeArray = [0, ] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    for i in range(contactsdb.num_suppliers(customer_idurl=customer_idurl)):
        suplier_idurl = contactsdb.supplier(i, customer_idurl=customer_idurl)
        if not suplier_idurl:
            activeArray[i] = 0
            continue
        if online_status.isOnline(suplier_idurl):
            activeArray[i] = 1
        else:
            activeArray[i] = 0
    return activeArray


def SuppliersChangedNumbers(oldSupplierList, customer_idurl=None):
    """
    Return list of positions of changed suppliers, say if suppliers 1 and 3
    were changed it should return [1,3].
    """
    changedList = []
    for i in range(len(oldSupplierList)):
        suplier_idurl = oldSupplierList[i]
        if not suplier_idurl:
            continue
        if contactsdb.supplier(i, customer_idurl=customer_idurl) != suplier_idurl:
            changedList.append(i)
    return changedList

#------------------------------------------------------------------------------

def SaveLatestRawListFiles(supplier_idurl, raw_data, customer_idurl=None):
    """
    Save a ListFiles packet from given supplier on local HDD.
    """
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    lg.out(4, 'backup_matrix.SaveLatestRawListFiles, %s, customer_idurl=%s' % (supplier_idurl, customer_idurl))
    supplierPath = settings.SupplierPath(supplier_idurl, customer_idurl)
    if not os.path.isdir(supplierPath):
        try:
            os.makedirs(supplierPath)
        except:
            lg.exc()
            return
    bpio.WriteTextFile(settings.SupplierListFilesFilename(supplier_idurl, customer_idurl), raw_data)


def ReadRawListFiles(supplierNum, listFileText, customer_idurl=None, is_in_sync=None):
    """
    Read ListFiles packet for given supplier and build a "remote" matrix. All
    lines are something like that:

      Kmaster
      Findex 5456
      D0 -1
      D0/1 -1
      V0/1/F20090709034221PM 3 0-1000 7463434
      D0/0/123/4567 -1
      V0/0/123/4567/F20090709034221PM 3 0-11 434353 missing Data:1,3
      V0/0/123/4/F20090709012331PM 3 0-5 434353 missing Data:1,3 Parity:0,1,2
      Kkey_abc_123
      Findex 205
      D0 -1
      D0/1 -1
      V0/1/F20090709010203PM 3 0-3 174634

    First character can be:

      "K" for keys
      "F" for files
      "D" for folders
      "V" for stored data
    """
    from storage import backup_control
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if is_in_sync is None:
        if driver.is_on('service_backup_db'):
            from storage import index_synchronizer
            is_in_sync = index_synchronizer.is_synchronized() and backup_control.revision() > 0
        else:
            is_in_sync = False
    lg.out(4, 'backup_matrix.ReadRawListFiles, %s : %d bytes, is_in_sync=%s, rev:%d, customer_idurl=%s' % (
        supplierNum, len(listFileText), is_in_sync, backup_control.revision(), customer_idurl))
    backups2remove = set()
    paths2remove = set()
    missed_backups = set(remote_files().keys())
    oldfiles = ClearSupplierRemoteInfo(supplierNum, global_id.UrlToGlobalID(customer_idurl))
    newfiles = 0
    remote_files_changed = False
    current_key_alias = 'master'
    inpt = BytesIO(strng.to_bin(listFileText))
    while True:
        line = strng.to_text(inpt.readline())
        if line == '':
            break
        typ = line[0]
        line = line[1:]
        line = line.rstrip('\n')
        if line.strip() == '':
            continue
        # also don't consider the identity a backup
        if line.find('http://') != -1 or line.find('.xml') != -1:
            continue
        lg.out(8, '    %s:{%s}' % (typ, line))
        if typ == 'K':
            current_key_alias = line.strip()

        elif typ == 'F':
            # we don't have this path in the index
            # so we have several cases:
            #    1. this is old file and we need to remove it and all its backups
            #    2. we loose our local index and did not restore it from one of suppliers yet
            #    3. we did restore our account and did not restore the index yet
            #    4. we lost our index at all and we do not have nor local nor remote copy
            # what to do now:
            #    - in first case we just need to remove the file from remote supplier
            #    - in other cases we must keep all remote data and believe we can restore the index
            #         and get all file names and backed up data
            # how to recognize that? how to be sure we have the correct index?
            # because it should be empty right after we recover our account
            # or we may loose it if the local index file were lost
            # the first idea:  check index_synchronizer() state - IN_SYNC means index is fine
            # the second idea: check revision number of the local index - 0 means we have no index yet
            try:
                pth, filesz = line.split(' ')
                filesz = int(filesz)
            except:
                pth = line
                filesz = -1
            if not backup_fs.IsFileID(pth, iterID=backup_fs.fsID(customer_idurl)):
                # remote supplier have some file - but we don't have it in the index
                if pth.strip('/') in [settings.BackupIndexFileName(), ]:
                    # this is the index file saved on remote supplier
                    # let's remember its size and put it in the backup_fs
                    item = backup_fs.FSItemInfo(
                        name=pth.strip('/'),
                        path_id=pth.strip('/'),
                        typ=backup_fs.FILE,
                        # key_id=global_id.MakeGlobalID(idurl=customer_idurl, key_alias=current_key_alias),
                    )
                    item.size = filesz
                    backup_fs.SetFile(
                        item,
                        iter=backup_fs.fs(customer_idurl),
                        iterID=backup_fs.fsID(customer_idurl),
                    )
                else:
                    if is_in_sync:
                        # so we have some modifications in the index - it is not empty!
                        # index_synchronizer() did his job - so we have up to date index on hands
                        # now we are sure that this file is old and must be removed from remote supplier
                        paths2remove.add(
                            packetid.MakeBackupID(
                                customer=global_id.UrlToGlobalID(customer_idurl),
                                path_id=pth,
                                key_alias=current_key_alias,
                                version=None,
                            )
                        )
                        if _Debug:
                            lg.out(2, '        F%s - remove, not found in the index' % pth)
                    else:
                        if _Debug:
                            lg.out(2, '        F%s - skip removing, not found in the index, but we are not in sync' % pth)
                # what to do now? let's hope we still can restore our index and this file is our remote data
        elif typ == 'D':
            try:
                pth = line.split(' ')[0]
            except:
                pth = line
            if not backup_fs.ExistsID(pth, iterID=backup_fs.fsID(customer_idurl)):
                if is_in_sync:
                    paths2remove.add(
                        packetid.MakeBackupID(
                            customer=global_id.UrlToGlobalID(customer_idurl),
                            path_id=pth,
                            key_alias=current_key_alias,
                            version=None,
                        )
                    )
                    if _Debug:
                        lg.out(2, '        D%s - remove, not found in the index' % pth)
                else:
                    if _Debug:
                        lg.out(2, '        D%s - skip removing, not found in the index, but we are not in sync' % pth)
        elif typ == 'V':
            # minimum is 4 words: "0/0/F20090709034221PM", "3", "0-1000" "123456"
            words = line.split(' ')
            if len(words) < 4:
                lg.warn('incorrect line (words count): [%s]' % line)
                continue
            try:
                _, remotePath, versionName = packetid.SplitBackupID(words[0])
                backupID = packetid.MakeBackupID(
                    customer=global_id.UrlToGlobalID(customer_idurl),
                    path_id=remotePath,
                    key_alias=current_key_alias,
                    version=versionName,
                )
            except:
                lg.warn('incorrect line (global id format): [%s]' % line)
                continue
            try:
                lineSupplierNum = int(words[1])
                _, maxBlockNum = words[2].split('-')
                maxBlockNum = int(maxBlockNum)
                versionSize = int(words[3])
            except:
                lg.warn('incorrect line (digits format): [%s]' % line)
                continue
            if lineSupplierNum != supplierNum:
                # this mean supplier have old files and we do not need those files
                backups2remove.add(backupID)
                if _Debug:
                    lg.out(2, '        V%s - remove, different supplier number' % backupID)
                continue
            iter_path = backup_fs.WalkByID(remotePath, iterID=backup_fs.fsID(customer_idurl))
            if iter_path is None:
                # this version is not found in the index
                if is_in_sync:
                    backups2remove.add(backupID)
                    paths2remove.add(
                        packetid.MakeBackupID(
                            customer=global_id.UrlToGlobalID(customer_idurl),
                            path_id=remotePath,
                            key_alias=current_key_alias,
                            version=None,
                        )
                    )
                    if _Debug:
                        lg.out(2, '        V%s - remove, path not found in the index' % remotePath)
                else:
                    if _Debug:
                        lg.out(2, '        V%s - skip removing, path is not found in the index, but we are not in sync' % remotePath)
                continue
            item, _ = iter_path
            if isinstance(item, dict):
                try:
                    item = item[backup_fs.INFO_KEY]
                except:
                    item = None
            if not item or not item.has_version(versionName):
                if is_in_sync:
                    backups2remove.add(backupID)
                    if _Debug:
                        lg.out(2, '        V%s - remove, version is not found in the index' % backupID)
                else:
                    if _Debug:
                        lg.out(2, '        V%s - skip removing, we are not in sync, but version is not found in the index' % backupID)
                continue
            item_version_info = item.get_version_info(versionName)
            missingBlocksSet = {'Data': set(), 'Parity': set()}
            if len(words) > 4:
                # "0/0/123/4567/F20090709034221PM/0-Data" "3" "0-5" "434353" "missing" "Data:1,3" "Parity:0,1,2"
                if words[4].strip() != 'missing':
                    lg.warn('incorrect line:[%s]' % line)
                    continue
                for missingBlocksString in words[5:]:
                    try:
                        dp, blocks = missingBlocksString.split(':')
                        missingBlocksSet[dp] = set(blocks.split(','))
                    except:
                        lg.exc()
                        break
            if backupID not in remote_files():
                remote_files()[backupID] = {}
                # lg.out(6, 'backup_matrix.ReadRawListFiles new remote entry for %s created in the memory' % backupID)
            # +1 because range(2) give us [0,1] but we want [0,1,2]
            for blockNum in range(maxBlockNum + 1):
                if blockNum not in remote_files()[backupID]:
                    remote_files()[backupID][blockNum] = {
                        'D': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl),
                        'P': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl), }
                for dataORparity in ['Data', 'Parity', ]:
                    # we set -1 if the file is missing and 1 if exist, so 0 mean "no info yet" ... smart!
                    bit = -1 if str(blockNum) in missingBlocksSet[dataORparity] else 1
                    remote_files()[backupID][blockNum][dataORparity[0]][supplierNum] = bit
                    newfiles += int((bit + 1) / 2)  # this should switch -1 or 1 to 0 or 1
            # save max block number for this backup
            if backupID not in remote_max_block_numbers():
                remote_max_block_numbers()[backupID] = -1
            if maxBlockNum > remote_max_block_numbers()[backupID]:
                remote_max_block_numbers()[backupID] = maxBlockNum
            if len(missingBlocksSet['Data']) == 0 and len(missingBlocksSet['Parity']) == 0:
                missed_backups.discard(backupID)
            if item_version_info[0] != maxBlockNum or item_version_info[1] != versionSize:
                lg.warn('updating version %s info with %s / %s from recent ListFiles()' % (
                    backupID, maxBlockNum, versionSize, ))
                item.set_version_info(versionName, maxBlockNum, versionSize)
                remote_files_changed = True
            # mark this backup to be repainted
            RepaintBackup(backupID)
    inpt.close()
    lg.out(8, '            remote_files_changed:%s, old:%d, new:%d, backups2remove:%d, paths2remove:%d' % (
        remote_files_changed, oldfiles, newfiles, len(backups2remove), len(paths2remove)))
    if remote_files_changed and is_in_sync:
        backup_control.Save()
    # finally return list of items which are too old but stored on suppliers machines
    return backups2remove, paths2remove, missed_backups


def ReadLatestRawListFiles(customer_idurl=None):
    """
    Call ``ReadRawListFiles()`` for every local file we have on hands and build
    whole "remote" matrix.
    """
    lg.out(4, 'backup_matrix.ReadLatestRawListFiles')
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    for idurl in contactsdb.suppliers(customer_idurl=customer_idurl):
        if idurl:
            filename = os.path.join(settings.SupplierPath(idurl, customer_idurl, 'listfiles'))
            if os.path.isfile(filename):
                listFileText = bpio.ReadTextFile(filename).strip()
                if listFileText:
                    ReadRawListFiles(
                        contactsdb.supplier_position(idurl),
                        listFileText,
                        customer_idurl=customer_idurl
                    )


def ReadLocalFiles():
    """
    This method scans local backups and build the whole "local" matrix.
    """
    global _LocalFilesNotifyCallback
    local_files().clear()
    local_max_block_numbers().clear()
    local_backup_size().clear()
    _counter = [0, ]

    def visit(customer, realpath, subpath, name):
        # subpath is something like 0/0/1/0/F20131120053803PM/0-1-Data
        if not os.path.isfile(realpath):
            return True
        if realpath.startswith('newblock-'):
            return False
        if subpath in [settings.BackupIndexFileName(), settings.BackupInfoFileName(), settings.BackupInfoFileNameOld(), settings.BackupInfoEncryptedFileName()]:
            return False
        try:
            version = subpath.split('/')[-2]
        except:
            return False
        if not packetid.IsCanonicalVersion(version):
            return True
        LocalFileReport(packetID=packetid.MakeBackupID(customer, subpath))
        _counter[0] += 1
        return False

    for customer in os.listdir(settings.getLocalBackupsDir()):
        customer_path = os.path.join(settings.getLocalBackupsDir(), customer)
        if not global_id.IsValidGlobalUser(customer):
            lg.warn('found incorrect folder name, not a customer: %s' % customer_path)
            continue
        if os.path.isdir(customer_path):
            bpio.traverse_dir_recursive(
                lambda r, s, n: visit(customer, r, s, n), customer_path)
        else:
            lg.warn('not a folder: %s' % customer_path)

    if _Debug:
        lg.out(_DebugLevel, 'backup_matrix.ReadLocalFiles %d files indexed' % _counter[0])
        if lg.is_debug(_DebugLevel + 2):
            try:
                if sys.version_info >= (2, 6):
                    #localSZ = sys.getsizeof(local_files())
                    #remoteSZ = sys.getsizeof(remote_files())
                    import lib.getsizeof
                    localSZ = lib.getsizeof.total_size(local_files())
                    remoteSZ = lib.getsizeof.total_size(remote_files())
                    indexByName = lib.getsizeof.total_size(backup_fs.fs())
                    indexByID = lib.getsizeof.total_size(backup_fs.fsID())
                    lg.out(_DebugLevel + 2, '    all local info uses %d bytes in the memory' % localSZ)
                    lg.out(_DebugLevel + 2, '    all remote info uses %d bytes in the memory' % remoteSZ)
                    lg.out(_DebugLevel + 2, '    index by name takes %d bytes in the memory' % indexByName)
                    lg.out(_DebugLevel + 2, '    index by ID takes %d bytes in the memory' % indexByID)
            except:
                lg.exc()
    if _LocalFilesNotifyCallback is not None:
        _LocalFilesNotifyCallback()


def DetectSupplierPosition(raw_list_file_text):
    """
    """
    inpt = BytesIO(strng.to_bin(raw_list_file_text))
    all_positions = {}
    while True:
        line = strng.to_text(inpt.readline())
        if line == '':
            break
        typ = line[0]
        line = line[1:]
        line = line.rstrip('\n')
        if line.strip() == '':
            continue
        if line.find('http://') != -1 or line.find('.xml') != -1:
            continue
        if typ == 'V':
            # minimum is 4 words: "0/0/F20090709034221PM", "3", "0-1000" "123456"
            words = line.split(' ')
            if len(words) < 4:
                lg.warn('incorrect line (words count): [%s]' % line)
                continue
            try:
                supplier_pos = int(words[1])
            except:
                lg.warn('incorrect line: [%s]' % line)
                continue
            if supplier_pos not in all_positions:
                all_positions[supplier_pos] = 0
            all_positions[supplier_pos] += 1
    inpt.close()
    lg.out(4, 'backup_matrix.DetectSupplierPosition from %d bytes found: %s' % (
        len(raw_list_file_text), all_positions))
    if not all_positions:
        return -1
    all_positions = list(all_positions.items())
    all_positions.sort(key=lambda i: i[1], reverse=True)
    return all_positions[0][0]

#------------------------------------------------------------------------------


def RemoteFileReport(backupID, blockNum, supplierNum, dataORparity, result):
    """
    Writes info for a single piece of data into "remote" matrix.

    May be called when you got an Ack packet from remote supplier after
    you sent him some Data packet .
    """
    blockNum = int(blockNum)
    supplierNum = int(supplierNum)
    customer_idurl = packetid.CustomerIDURL(backupID)
    if supplierNum > contactsdb.num_suppliers(customer_idurl=customer_idurl):
        lg.out(4, 'backup_matrix.RemoteFileReport got too big supplier number, possible this is an old packet')
        return
    if backupID not in remote_files():
        remote_files()[backupID] = {}
        lg.info('new remote entry for %s created in the memory' % backupID)
    if blockNum not in remote_files()[backupID]:
        remote_files()[backupID][blockNum] = {
            'D': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl),
            'P': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl), }
    # save backed up block info into remote info structure, synchronize on hand info
    flag = 1 if result else 0
    if dataORparity == 'Data':
        remote_files()[backupID][blockNum]['D'][supplierNum] = flag
    elif dataORparity == 'Parity':
        remote_files()[backupID][blockNum]['P'][supplierNum] = flag
    else:
        lg.warn('incorrect backup ID: %s' % backupID)
    # if we know only 5 blocks stored on remote machine
    # but we have backed up 6th block - remember this
    remote_max_block_numbers()[backupID] = max(remote_max_block_numbers().get(backupID, -1), blockNum)
    # mark to repaint this backup in gui
    RepaintBackup(backupID)


def LocalFileReport(packetID=None, backupID=None, blockNum=None, supplierNum=None, dataORparity=None):
    """
    Writes info for a single piece of data into "local" matrix.

    You can use two forms:
    * pass ``packetID`` parameter only
    * pass all other parameters and do not use ``packetID``

    This is called when new local file created, for example during rebuilding process.
    """
    if packetID is not None:
        customer, remotePath, blockNum, supplierNum, dataORparity = packetid.Split(packetID)
        if remotePath is None:
            lg.warn('incorrect filename: ' + packetID)
            return
        backupID = packetid.MakeBackupID(customer, remotePath)
    else:
        blockNum = int(blockNum)
        supplierNum = int(supplierNum)
        dataORparity = dataORparity
        packetID = packetid.MakePacketID(backupID, blockNum, supplierNum, dataORparity)
    customer, filename = packetid.SplitPacketID(packetID)
    customer_idurl = global_id.GlobalUserToIDURL(customer)
    if dataORparity not in ['Data', 'Parity']:
        lg.warn('Data or Parity? ' + filename)
        return
    if supplierNum >= contactsdb.num_suppliers(customer_idurl=customer_idurl):
        if _Debug:
            lg.out(_DebugLevel, 'backup_matrix.LocalFileReport SKIP supplier position is invalid %d > %d for customer %s : %s' % (
                supplierNum, contactsdb.num_suppliers(), customer_idurl, filename))
        return
    supplier_idurl = contactsdb.supplier(supplierNum, customer_idurl=customer_idurl)
    if not supplier_idurl:
        lg.warn('empty supplier at position %s for customer %s' % (supplierNum, customer_idurl, ))
        return
    localDest = os.path.join(settings.getLocalBackupsDir(), customer, filename)
    if backupID not in local_files():
        local_files()[backupID] = {}
    if blockNum not in local_files()[backupID]:
        local_files()[backupID][blockNum] = {
            'D': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl),
            'P': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl), }
    if not os.path.isfile(localDest):
        local_files()[backupID][blockNum][dataORparity[0]][supplierNum] = 0
        return
    local_files()[backupID][blockNum][dataORparity[0]][supplierNum] = 1
    if backupID not in local_max_block_numbers():
        local_max_block_numbers()[backupID] = -1
    if local_max_block_numbers()[backupID] < blockNum:
        local_max_block_numbers()[backupID] = blockNum
    if backupID not in local_backup_size():
        local_backup_size()[backupID] = 0
    try:
        local_backup_size()[backupID] += os.path.getsize(localDest)
    except:
        lg.exc()
    RepaintBackup(backupID)


def LocalBlockReport(backupID, blockNumber, result):
    """
    This updates "local" matrix - a several pieces corresponding to given block of data.
    """
    if result is None:
        lg.warn('result is None')
        return
    try:
        blockNum = int(blockNumber)
    except:
        lg.exc()
        return
    customer, remotePath = packetid.SplitPacketID(backupID)
    customer_idurl = global_id.GlobalUserToIDURL(customer)
    repaint_flag = False
    if _Debug:
        lg.out(_DebugLevel, 'backup_matrix.LocalFileReport  in block %d at %s for %s' % (blockNumber, backupID, customer, ))
    num_suppliers = contactsdb.num_suppliers(customer_idurl=customer_idurl)
    for supplierNum in range(num_suppliers):
        supplier_idurl = contactsdb.supplier(supplierNum, customer_idurl=customer_idurl)
        if not supplier_idurl:
            lg.warn('unknown supplier_idurl supplierNum=%s for %s, customer_idurl=%s' % (
                supplierNum, backupID, customer_idurl))
            continue
        for dataORparity in ('Data', 'Parity'):
            packetID = packetid.MakePacketID(remotePath, blockNum, supplierNum, dataORparity)
            local_file = os.path.join(settings.getLocalBackupsDir(), customer, packetID)
            if backupID not in local_files():
                local_files()[backupID] = {}
                repaint_flag = True
                if _Debug:
                    lg.out(_DebugLevel, '    new local entry for %s created in the memory' % backupID)
            if blockNum not in local_files()[backupID]:
                local_files()[backupID][blockNum] = {
                    'D': [0, ] * num_suppliers,
                    'P': [0, ] * num_suppliers}
                repaint_flag = True
            if not os.path.isfile(local_file):
                local_files()[backupID][blockNum][dataORparity[0]][supplierNum] = 0
                repaint_flag = True
                continue
            local_files()[backupID][blockNum][dataORparity[0]][supplierNum] = 1
            if backupID not in local_backup_size():
                local_backup_size()[backupID] = 0
                repaint_flag = True
            try:
                local_backup_size()[backupID] += os.path.getsize(local_file)
                repaint_flag = True
            except:
                lg.exc()
            if _Debug:
                lg.out(_DebugLevel, '    OK, local backup size is %s and max block num is %s' % (
                    local_backup_size()[backupID], local_max_block_numbers()[backupID]))
    if backupID not in local_max_block_numbers():
        local_max_block_numbers()[backupID] = -1
    if local_max_block_numbers()[backupID] < blockNum:
        local_max_block_numbers()[backupID] = blockNum
    if repaint_flag:
        RepaintBackup(backupID)

#------------------------------------------------------------------------------


def ScanMissingBlocks(backupID):
    """
    Finally here is some real logic.

    This will compare both matrixes to find missing pieces on remote
    suppliers. Should return a list of numbers of missed blocks for
    given backup.
    """
    if _Debug:
        lg.out(_DebugLevel, 'backup_matrix.ScanMissingBlocks for %s' % backupID)
    customer_idurl = packetid.CustomerIDURL(backupID)
    missingBlocks = set()
    localMaxBlockNum = local_max_block_numbers().get(backupID, -1)
    remoteMaxBlockNum = remote_max_block_numbers().get(backupID, -1)
    supplierActiveArray = GetActiveArray(customer_idurl=customer_idurl)

    if backupID not in remote_files():
        if backupID not in local_files():
            # we have no local and no remote info for this backup
            # no chance to do some rebuilds...
            # TODO: but how we get here ?!
            if _Debug:
                lg.out(_DebugLevel, '    no local and no remote info found !!!')
        else:
            # we have no remote info, but some local files exists
            # so let's try to sent all of them
            # need to scan all block numbers
            if _Debug:
                lg.out(_DebugLevel, '    no remote info but found local info, maxBlockNum=%d' % localMaxBlockNum)
            for blockNum in range(localMaxBlockNum + 1):
                # we check for Data and Parity packets
                localData = GetLocalDataArray(backupID, blockNum)
                localParity = GetLocalParityArray(backupID, blockNum)
                for supplierNum in range(len(supplierActiveArray)):
                    # if supplier is not alive we can not send to him
                    # so no need to scan for missing blocks
                    if supplierActiveArray[supplierNum] != 1:
                        continue
                    if localData[supplierNum] == 1:
                        missingBlocks.add(blockNum)
                    if localParity[supplierNum] == 1:
                        missingBlocks.add(blockNum)
    else:
        # now we have some remote info
        # we take max block number from local and remote
        maxBlockNum = max(remoteMaxBlockNum, localMaxBlockNum)
        if _Debug:
            lg.out(_DebugLevel, '    found remote info, maxBlockNum=%d' % maxBlockNum)
        # and increase by one because range(3) give us [0, 1, 2], but we want [0, 1, 2, 3]
        for blockNum in range(maxBlockNum + 1):
            # if we have few remote files, but many locals - we want to send all missed
            if blockNum not in remote_files()[backupID]:
                missingBlocks.add(blockNum)
                continue
            # take remote info for this block
            remoteData = GetRemoteDataArray(backupID, blockNum)
            remoteParity = GetRemoteParityArray(backupID, blockNum)
            # now check every our supplier for every block
            for supplierNum in range(len(supplierActiveArray)):
                # if supplier is not alive we can not send to him
                # so no need to scan for missing blocks
                if supplierActiveArray[supplierNum] != 1:
                    continue
                if supplierNum >= len(remoteData) or supplierNum >= len(remoteParity):
                    missingBlocks.add(blockNum)
                    continue
                if remoteData[supplierNum] != 1:    # -1 means missing
                    missingBlocks.add(blockNum)     # 0 - no info yet
                if remoteParity[supplierNum] != 1:  # 1 - file exist on remote supplier
                    missingBlocks.add(blockNum)

    if _Debug:
        lg.out(_DebugLevel, '    missingBlocks=%s' % missingBlocks)
    return list(missingBlocks)


def ScanBlocksToRemove(backupID, check_all_suppliers=True):
    """
    This method compare both matrixes and found pieces which is present on both
    sides.

    If remote supplier got that file it can be removed from the local
    HDD.
    """
    from customer import io_throttle
    lg.out(10, 'backup_matrix.ScanBlocksToRemove for %s' % backupID)
    customer_idurl = packetid.CustomerIDURL(backupID)
    packets = []
    localMaxBlockNum = local_max_block_numbers().get(backupID, -1)
    if backupID not in remote_files() or backupID not in local_files():
        # no info about this backup yet - skip
        return packets
    for blockNum in range(localMaxBlockNum + 1):
        localArray = {'Data': GetLocalDataArray(backupID, blockNum),
                      'Parity': GetLocalParityArray(backupID, blockNum)}
        remoteArray = {'Data': GetRemoteDataArray(backupID, blockNum),
                       'Parity': GetRemoteParityArray(backupID, blockNum)}
        if (0 in remoteArray['Data']) or (0 in remoteArray['Parity']):
            # if some supplier do not have some data for that block - do not remove any local files for that block!
            # we do remove the local files only when we sure all suppliers got the all data pieces
            continue
        if (-1 in remoteArray['Data']) or (-1 in remoteArray['Parity']):
            # also if we do not have any info about this block for some supplier do not remove other local pieces
            continue
        for supplierNum in range(contactsdb.num_suppliers(customer_idurl=customer_idurl)):
            supplierIDURL = contactsdb.supplier(supplierNum, customer_idurl=customer_idurl)
            if not supplierIDURL:
                # supplier is unknown - skip
                continue
            for dataORparity in ['Data', 'Parity']:
                packetID = packetid.MakePacketID(backupID, blockNum, supplierNum, dataORparity)
                if io_throttle.HasPacketInSendQueue(supplierIDURL, packetID):
                    # if we do sending the packet at the moment - skip
                    continue
                if localArray[dataORparity][supplierNum] == 1:
                    packets.append(packetID)
                    # lg.out(10, '    mark to remove %s, blockNum:%d remote:%s local:%s' % (packetID, blockNum, str(remoteArray), str(localArray)))
#                if check_all_suppliers:
#                    if localArray[dataORparity][supplierNum] == 1:
#                        packets.append(packetID)
#                else:
#                    if remoteArray[dataORparity][supplierNum] == 1 and localArray[dataORparity][supplierNum] == 1:
#                        packets.append(packetID)
    return packets


def ScanBlocksToSend(backupID):
    """
    Opposite method - search for pieces which is not yet delivered to remote suppliers.
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    if '' in contactsdb.suppliers(customer_idurl=customer_idurl) or b'' in contactsdb.suppliers(customer_idurl=customer_idurl):
        lg.warn('found empty suppliers, SKIP')
        return {}
    localMaxBlockNum = local_max_block_numbers().get(backupID, -1)
    supplierActiveArray = GetActiveArray(customer_idurl=customer_idurl)
    bySupplier = {}
    for supplierNum in range(len(supplierActiveArray)):
        bySupplier[supplierNum] = set()
    if backupID not in remote_files():
        for blockNum in range(localMaxBlockNum + 1):
            localData = GetLocalDataArray(backupID, blockNum)
            localParity = GetLocalParityArray(backupID, blockNum)
            for supplierNum in range(len(supplierActiveArray)):
                if supplierActiveArray[supplierNum] != 1:
                    continue
                if supplierNum >= len(localData) or supplierNum >= len(localParity):
                    continue
                if localData[supplierNum] == 1:
                    bySupplier[supplierNum].add(packetid.MakePacketID(backupID, blockNum, supplierNum, 'Data'))
                if localParity[supplierNum] == 1:
                    bySupplier[supplierNum].add(packetid.MakePacketID(backupID, blockNum, supplierNum, 'Parity'))
    else:
        for blockNum in range(localMaxBlockNum + 1):
            remoteData = GetRemoteDataArray(backupID, blockNum)
            remoteParity = GetRemoteParityArray(backupID, blockNum)
            localData = GetLocalDataArray(backupID, blockNum)
            localParity = GetLocalParityArray(backupID, blockNum)
            for supplierNum in range(len(supplierActiveArray)):
                if supplierActiveArray[supplierNum] != 1:
                    continue
                if supplierNum >= len(remoteData) or supplierNum >= len(remoteParity):
                    continue
                if remoteData[supplierNum] != 1 and localData[supplierNum] == 1:
                    bySupplier[supplierNum].add(packetid.MakePacketID(backupID, blockNum, supplierNum, 'Data'))
                if remoteParity[supplierNum] != 1 and localParity[supplierNum] == 1:
                    bySupplier[supplierNum].add(packetid.MakePacketID(backupID, blockNum, supplierNum, 'Parity'))
    return bySupplier

#------------------------------------------------------------------------------

def RepaintBackup(backupID):
    """
    Mark given backup to be "repainted" in the GUI during the next "frame".
    """
    global _UpdatedBackupIDs
    _UpdatedBackupIDs.add(backupID)


def RepaintingProcess(on_off):
    """
    This method is called in loop to repaint the GUI.
    """
    global _UpdatedBackupIDs
    global _BackupStatusNotifyCallback
    global _RepaintingTask
    global _RepaintingTaskDelay
    if on_off is False:
        _RepaintingTaskDelay = 2.0
        if _RepaintingTask is not None:
            if _RepaintingTask.active():
                _RepaintingTask.cancel()
            _RepaintingTask = None
            _UpdatedBackupIDs.clear()
            return
    # TODO:
    # Need to optimize that - do not call in loop!
    # Just make a single call and pass _UpdatedBackupIDs as param.
    for backupID in _UpdatedBackupIDs:
        if _BackupStatusNotifyCallback is not None:
            _BackupStatusNotifyCallback(backupID)
    minDelay = 2.0
    from storage import backup_control
    if backup_control.HasRunningBackup():
        minDelay = 8.0
    _RepaintingTaskDelay = misc.LoopAttenuation(_RepaintingTaskDelay, len(_UpdatedBackupIDs) > 0, minDelay, 8.0)
    _UpdatedBackupIDs.clear()
    _RepaintingTask = reactor.callLater(_RepaintingTaskDelay, RepaintingProcess, True)  # @UndefinedVariable

#------------------------------------------------------------------------------


def EraseBackupRemoteInfo(backupID):
    """
    Clear info only for given backup from "remote" matrix.
    """
    if backupID in remote_files():
        del remote_files()[backupID]  # remote_files().pop(backupID)
    if backupID in remote_max_block_numbers():
        del remote_max_block_numbers()[backupID]


def EraseBackupLocalInfo(backupID):
    """
    Clear info only for given backup from "local" matrix.
    """
    if backupID in local_files():
        del local_files()[backupID]  # local_files().pop(backupID)
    if backupID in local_max_block_numbers():
        del local_max_block_numbers()[backupID]
    if backupID in local_backup_size():
        del local_backup_size()[backupID]

#------------------------------------------------------------------------------


def ClearLocalInfo():
    """
    Completely clear the whole "local" matrix.
    """
    local_files().clear()
    local_max_block_numbers().clear()
    local_backup_size().clear()


def ClearRemoteInfo():
    """
    Completely clear the whole "remote" matrix, in other words - forget all info about suppliers files.
    """
    remote_files().clear()
    remote_max_block_numbers().clear()


def ClearSupplierRemoteInfo(supplierNum, customer_idurl=None):
    """
    Clear only "single column" in the "remote" matrix corresponding to given
    supplier.
    """
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    files = 0
    for backupID in remote_files().keys():
        _customer_idurl = packetid.CustomerIDURL(backupID)
        if _customer_idurl == customer_idurl:
            for blockNum in remote_files()[backupID].keys():
                try:
                    if remote_files()[backupID][blockNum]['D'][supplierNum] == 1:
                        files += 1
                        remote_files()[backupID][blockNum]['D'][supplierNum] = 0
                except:
                    pass
                try:
                    if remote_files()[backupID][blockNum]['P'][supplierNum] == 1:
                        files += 1
                        remote_files()[backupID][blockNum]['P'][supplierNum] = 0
                except:
                    pass
    return files

#------------------------------------------------------------------------------


def GetBackupStats(backupID):
    """
    Collect needed info from "remote" matrix and create a detailed report about
    given backup.
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    if backupID not in remote_files():
        return 0, 0, [(0, 0)] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    percentPerSupplier = 100.0 / contactsdb.num_suppliers(customer_idurl=customer_idurl)
    # ??? maxBlockNum = remote_max_block_numbers().get(backupID, -1)
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    fileNumbers = [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    totalNumberOfFiles = 0
    for blockNum in remote_files()[backupID].keys():
        for supplierNum in range(len(fileNumbers)):
            if supplierNum < contactsdb.num_suppliers(customer_idurl=customer_idurl):
                if remote_files()[backupID][blockNum]['D'][supplierNum] == 1:
                    fileNumbers[supplierNum] += 1
                    totalNumberOfFiles += 1
                if remote_files()[backupID][blockNum]['P'][supplierNum] == 1:
                    fileNumbers[supplierNum] += 1
                    totalNumberOfFiles += 1
    statsArray = []
    for supplierNum in range(contactsdb.num_suppliers(customer_idurl=customer_idurl)):
        if maxBlockNum > -1:
            # 0.5 because we count both Parity and Data.
            percent = percentPerSupplier * 0.5 * fileNumbers[supplierNum] / (maxBlockNum + 1)
        else:
            percent = 0.0
        statsArray.append((percent, fileNumbers[supplierNum]))
    del fileNumbers
    return totalNumberOfFiles, maxBlockNum, statsArray


def GetBackupLocalStats(backupID):
    """
    Provide detailed info about local files for that backup. Return a tuple::

    (totalPercent, totalNumberOfFiles, totalSize, maxBlockNum,
    statsArray)
    """
    # ??? maxBlockNum = local_max_block_numbers().get(backupID, -1)
    customer_idurl = packetid.CustomerIDURL(backupID)
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    if backupID not in local_files():
        return 0, 0, 0, maxBlockNum, [(0, 0)] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    percentPerSupplier = 100.0 / contactsdb.num_suppliers(customer_idurl=customer_idurl)
    totalNumberOfFiles = 0
    fileNumbers = [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    for blockNum in range(maxBlockNum + 1):
        if blockNum not in list(local_files()[backupID].keys()):
            continue
#    for blockNum in local_files()[backupID].keys():
        for supplierNum in range(len(fileNumbers)):
            if supplierNum < contactsdb.num_suppliers(customer_idurl=customer_idurl):
                if local_files()[backupID][blockNum]['D'][supplierNum] == 1:
                    fileNumbers[supplierNum] += 1
                    totalNumberOfFiles += 1
                if local_files()[backupID][blockNum]['P'][supplierNum] == 1:
                    fileNumbers[supplierNum] += 1
                    totalNumberOfFiles += 1
    statsArray = []
    for supplierNum in range(contactsdb.num_suppliers(customer_idurl=customer_idurl)):
        if maxBlockNum > -1:
            # 0.5 because we count both Parity and Data.
            percent = percentPerSupplier * 0.5 * fileNumbers[supplierNum] / (maxBlockNum + 1)
        else:
            percent = 0.0
        statsArray.append((percent, fileNumbers[supplierNum]))
    del fileNumbers
    totalPercent = 100.0 * 0.5 * totalNumberOfFiles / ((maxBlockNum + 1) * contactsdb.num_suppliers(customer_idurl=customer_idurl))
    return totalPercent, totalNumberOfFiles, local_backup_size().get(backupID, 0), maxBlockNum, statsArray


def GetBackupBlocksAndPercent(backupID):
    """
    Another method to get details about a backup.
    """
    if backupID not in remote_files():
        return 0, 0
    # get max block number
    # ??? maxBlockNum = remote_max_block_numbers().get(backupID, -1)
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    if maxBlockNum == -1:
        return 0, 0
    customer_idurl = packetid.CustomerIDURL(backupID)
    # we count all remote files for this backup
    fileCounter = 0
    for blockNum in remote_files()[backupID].keys():
        for supplierNum in range(contactsdb.num_suppliers(customer_idurl=customer_idurl)):
            if remote_files()[backupID][blockNum]['D'][supplierNum] == 1:
                fileCounter += 1
            if remote_files()[backupID][blockNum]['P'][supplierNum] == 1:
                fileCounter += 1
    # +1 since zero based and *0.5 because Data and Parity
    return maxBlockNum + 1, 100.0 * 0.5 * fileCounter / ((maxBlockNum + 1) * contactsdb.num_suppliers(customer_idurl=customer_idurl))


def GetBackupRemoteStats(backupID, only_available_files=True):
    """
    This method found a most "weak" block of that backup, this is a block which
    pieces is kept by less suppliers from all other blocks.

    This is needed to detect the whole backup availability.
    Because if you loose at least one block of the backup - you will loose the whole backup.!

    The backup condition is equal to the "worst" block condition.
    Return a tuple::

      (blocks, percent, weakBlock, weakBlockPercent)
    """
    if backupID not in remote_files():
        return -1, 0, -1, 0
    # get max block number
    # ??? maxBlockNum = remote_max_block_numbers().get(backupID, -1)
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    if maxBlockNum == -1:
        return -1, 0, -1, 0
    customer_idurl = packetid.CustomerIDURL(backupID)
    supplierCount = contactsdb.num_suppliers(customer_idurl=customer_idurl)
    fileCounter = 0
    weakBlockNum = -1
    lessSuppliers = supplierCount
    activeArray = GetActiveArray(customer_idurl=customer_idurl)
    # we count all remote files for this backup - scan all blocks
    for blockNum in range(maxBlockNum + 1):
        if blockNum not in list(remote_files()[backupID].keys()):
            lessSuppliers = 0
            weakBlockNum = blockNum
            continue
        goodSuppliers = supplierCount
        for supplierNum in range(supplierCount):
            if activeArray[supplierNum] != 1 and only_available_files:
                goodSuppliers -= 1
                continue
            try:
                remote_files()[backupID][blockNum]['D'][supplierNum]
                remote_files()[backupID][blockNum]['D'][supplierNum]
            except:
                goodSuppliers -= 1
                continue
            if remote_files()[backupID][blockNum]['D'][supplierNum] != 1 or remote_files()[backupID][blockNum]['P'][supplierNum] != 1:
                goodSuppliers -= 1
            if remote_files()[backupID][blockNum]['D'][supplierNum] == 1:
                fileCounter += 1
            if remote_files()[backupID][blockNum]['P'][supplierNum] == 1:
                fileCounter += 1
        if goodSuppliers < lessSuppliers:
            lessSuppliers = goodSuppliers
            weakBlockNum = blockNum
    # +1 since zero based and *0.5 because Data and Parity
    return (
        maxBlockNum + 1,
        100.0 * 0.5 * fileCounter / ((maxBlockNum + 1) * supplierCount),
        weakBlockNum,
        100.0 * float(lessSuppliers) / float(supplierCount),
    )


def GetBackupRemoteArray(backupID):
    """
    Get info for given backup from "remote" matrix.
    """
    if backupID not in remote_files():
        return None
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    if maxBlockNum == -1:
        return None
    return remote_files()[backupID]


def GetBackupLocalArray(backupID):
    """
    Get info for given backup from "local" matrix.
    """
    if backupID not in local_files():
        return None
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    if maxBlockNum == -1:
        return None
    return local_files()[backupID]


def GetBackupIDs(remote=True, local=False, sorted_ids=False):
    """
    Return a list of backup IDs which is present in the matrixes.

    You can choose which matrix to use.
    """
    s = set()
    if remote:
        s.update(list(remote_files().keys()))
    if local:
        s.update(list(local_files().keys()))
    if sorted_ids:
        return misc.sorted_backup_ids(list(s))
    return list(s)


def GetKnownMaxBlockNum(backupID):
    """
    Return a maximum "known" block number for given backup.
    """
    return max(remote_max_block_numbers().get(backupID, -1),
               local_max_block_numbers().get(backupID, -1))


def GetLocalMatrix(backupID, blockNum):
    """
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    if backupID not in local_files():
        return {'D': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl),
                'P': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl), }
    if blockNum not in local_files()[backupID]:
        return {'D': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl),
                'P': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl), }
    return local_files()[backupID][blockNum]


def GetLocalDataArray(backupID, blockNum):
    """
    Get "local" info for a single block of given backup, this is for "Data"
    surface.
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    if backupID not in local_files():
        return [0, ] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    if blockNum not in local_files()[backupID]:
        return [0, ] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    return local_files()[backupID][blockNum]['D']


def GetLocalParityArray(backupID, blockNum):
    """
    Get "local" info for a single block of given backup, this is for "Parity"
    surface.
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    if backupID not in local_files():
        return [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    if blockNum not in local_files()[backupID]:
        return [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    return local_files()[backupID][blockNum]['P']


def GetRemoteMatrix(backupID, blockNum):
    """
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    if backupID not in remote_files():
        return {'D': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl),
                'P': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl), }
    if blockNum not in remote_files()[backupID]:
        return {'D': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl),
                'P': [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl), }
    return remote_files()[backupID][blockNum]


def GetRemoteDataArray(backupID, blockNum):
    """
    Get "remote" info for a single block of given backup, this is for "Data"
    surface.
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    if backupID not in remote_files():
        return [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    if blockNum not in remote_files()[backupID]:
        return [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    return remote_files()[backupID][blockNum]['D']


def GetRemoteParityArray(backupID, blockNum):
    """
    Get "remote" info for a single block of given backup, this is for "Parity"
    surface.
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    if backupID not in remote_files():
        return [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    if blockNum not in remote_files()[backupID]:
        return [0] * contactsdb.num_suppliers(customer_idurl=customer_idurl)
    return remote_files()[backupID][blockNum]['P']


def GetSupplierStats(supplierNum, customer_idurl=None):
    """
    Collect info from "remote" matrix about given supplier.
    """
    result = {}
    files = total = 0
    for backupID in remote_files().keys():
        if customer_idurl != packetid.CustomerIDURL(backupID):
            continue
        result[backupID] = {'data': 0, 'parity': 0, 'total': 0, }
        for blockNum in remote_files()[backupID].keys():
            if remote_files()[backupID][blockNum]['D'][supplierNum] == 1:
                result[backupID]['data'] += 1
                files += 1
            if remote_files()[backupID][blockNum]['P'][supplierNum] == 1:
                result[backupID]['parity'] += 1
                files += 1
            result[backupID]['total'] += 2
            total += 2
    return files, total, result


def GetWeakLocalBlock(backupID):
    """
    Scan all "local" blocks for given backup and find the most "weak" block.
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    supplierCount = contactsdb.num_suppliers(customer_idurl=customer_idurl)
    if backupID not in local_files():
        return -1, 0, supplierCount
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    weakBlockNum = -1
    lessSuppliers = supplierCount
    for blockNum in range(maxBlockNum + 1):
        if blockNum not in list(local_files()[backupID].keys()):
            return blockNum, 0, supplierCount
        goodSuppliers = supplierCount
        for supplierNum in range(supplierCount):
            if local_files()[backupID][blockNum]['D'][supplierNum] != 1 or local_files()[backupID][blockNum]['P'][supplierNum] != 1:
                goodSuppliers -= 1
        if goodSuppliers < lessSuppliers:
            lessSuppliers = goodSuppliers
            weakBlockNum = blockNum
    return weakBlockNum, lessSuppliers, supplierCount


def GetWeakRemoteBlock(backupID):
    """
    Scan all "remote" blocks for given backup and find the most "weak" block -
    less suppliers keeps the data and stay online.
    """
    customer_idurl = packetid.CustomerIDURL(backupID)
    supplierCount = contactsdb.num_suppliers(customer_idurl=customer_idurl)
    if backupID not in remote_files():
        return -1, 0, supplierCount
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    weakBlockNum = -1
    lessSuppliers = supplierCount
    activeArray = GetActiveArray(customer_idurl=customer_idurl)
    for blockNum in range(maxBlockNum + 1):
        if blockNum not in list(remote_files()[backupID].keys()):
            return blockNum, 0, supplierCount
        goodSuppliers = supplierCount
        for supplierNum in range(supplierCount):
            if activeArray[supplierNum] != 1:
                goodSuppliers -= 1
                continue
            if remote_files()[backupID][blockNum]['D'][supplierNum] != 1 or remote_files()[backupID][blockNum]['P'][supplierNum] != 1:
                goodSuppliers -= 1
        if goodSuppliers < lessSuppliers:
            lessSuppliers = goodSuppliers
            weakBlockNum = blockNum
    return weakBlockNum, lessSuppliers, supplierCount

#------------------------------------------------------------------------------


def SetBackupStatusNotifyCallback(callBack):
    """
    This is to catch in the GUI when some backups stats were changed.
    """
    global _BackupStatusNotifyCallback
    _BackupStatusNotifyCallback = callBack


def SetLocalFilesNotifyCallback(callback):
    """
    This is to catch in the GUI when some local files were changed.
    """
    global _LocalFilesNotifyCallback
    _LocalFilesNotifyCallback = callback

#------------------------------------------------------------------------------


if __name__ == "__main__":
    init()
    # import pprint
    # pprint.pprint(GetBackupIds())
