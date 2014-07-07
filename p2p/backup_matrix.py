#!/usr/bin/python
#backup_matrix.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: backup_matrix

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

import os
import sys
import time
import random
import gc
import cStringIO


try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in backup_matrix.py')

from twisted.internet.defer import Deferred, maybeDeferred
from twisted.internet import threads


import lib.dhnio as dhnio
import lib.misc as misc
import lib.nameurl as nameurl
import lib.settings as settings
import lib.contacts as contacts
# import lib.eccmap as eccmap
import lib.tmpfile as tmpfile
import lib.diskspace as diskspace
import lib.packetid as packetid
from lib.automat import Automat


import backup_monitor
import backup_rebuilder  
import fire_hire
import list_files_orator
import backup_db_keeper

import p2p_service
import io_throttle
import contact_status
import backup_fs
import backup_control

#------------------------------------------------------------------------------ 

_RemoteFiles = {}
_LocalFiles = {}
_RemoteMaxBlockNumbers = {}
_LocalMaxBlockNumbers = {}
_LocalBackupSize = {}
_BackupsInProcess = []
_SuppliersSet = None
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
    dhnio.Dprint(4, 'backup_matrix.init')
    RepaintingProcess(True)
    ReadLocalFiles()
    ReadLatestRawListFiles()


def shutdown():
    """
    Correct way to finish all things here.
    """
    dhnio.Dprint(4, 'backup_matrix.shutdown')
    RepaintingProcess(False)

#------------------------------------------------------------------------------ 

def remote_files():
    """
    This is a "remote" matrix.
    Here is stored info for all remote files (on suppliers HDD's) 
    stored in dictionary. The values are integers::
    
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
    This is a dictionary to store max block number for every remote backup, by backup ID.
    """
    global _RemoteMaxBlockNumbers
    return _RemoteMaxBlockNumbers


def local_files():
    """
    This is a "local" matrix, same structure like ``remote_files()``. 
    Keeps info for all local files stored on your HDD.
    The values are integers: 0 or 1 to know that local file exists or not. 
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
    To get the size of the particular backup need to count size of all pieces.
    Here is a dictionary of counters for every backup. 
    """
    global _LocalBackupSize
    return _LocalBackupSize


def suppliers_set():
    """
    Return current set of suppliers, see ``SuppliersSet`` class.
    
    PREPRO: 
    Not sure do we need to duplicate suppliers IDs.
    In ``lib.contactsdb`` we already store this list.
    However scrubbers need to keep track of other suppliers also ...
    """
    global _SuppliersSet
    if _SuppliersSet is None:
        _SuppliersSet = SuppliersSet(contacts.getSupplierIDs())
    return _SuppliersSet

#------------------------------------------------------------------------------ 
class SuppliersSet:
    """
    This should represent a set of suppliers for either the user 
    or for a customer the user is acting as a scrubber for.
    """
    def __init__(self, supplierList):
        """
        Set initial list of suppliers, ``supplierList`` is an array with suppliers IDURL's.
        """
        self.suppliers = [] 
        self.supplierCount = 0 
        self.UpdateSuppliers(supplierList)

    def UpdateSuppliers(self, supplierList):
        """
        Called when your suppliers is changed and need to update current set of suppliers.
        Right now this list comes from Central server.
        """
        self.suppliers = list(supplierList)
        self.supplierCount = len(self.suppliers)

    def GetActiveArray(self):
        """
        Loops all suppliers in the set and returns who is alive at the moment.
        Return a list with integers: 0 for offline suppler and 1 if he is available right now.
        Uses ``p2p.contact_status.isOnline()`` to see the current state of supplier.
        """
        activeArray = [0] * self.supplierCount
        for i in xrange(self.supplierCount):
            if not self.suppliers[i]:
                continue
            if contact_status.isOnline(self.suppliers[i]):
                activeArray[i] = 1
            else:
                activeArray[i] = 0
        return activeArray

    def ChangedArray(self, supplierList):
        """
        Loops all suppliers in the set and compare with ``supplierList``.
        Return two lists:
        * array with integers where value 1 means that supplier is different
        * list of different user IDs
        """
        changedArray = [0] * self.supplierCount
        changedIdentities = []
        for i in xrange(self.supplierCount):
            if not self.suppliers[i]:
                continue
            if supplierList[i] != self.suppliers[i]:
                changedArray[i] = 1
                changedIdentities.append(supplierList[i])
        return changedArray, changedIdentities

    def SuppliersChanged(self, supplierList):
        """
        Return True if at least one from current set of suppliers is different from ``supplierList``.
        """
        if len(supplierList) != self.supplierCount:
            return True
        for i in xrange(self.supplierCount):
            if not self.suppliers[i]:
                continue
            if supplierList[i] != self.suppliers[i]:
                return True
        return False

    def SuppliersChangedNumbers(self, supplierList):
        """
        Return list of possitions of changed suppliers,
        say if suppliers 1 and 3 were changed it should return [1,3].
        """
        changedList = []
        for i in xrange(self.supplierCount):
            if not self.suppliers[i]:
                continue
            if supplierList[i] != self.suppliers[i]:
                changedList.append(i)
        return changedList

    def SupplierCountChanged(self, supplierList):
        """
        Return True if number of suppliers were changed.
        """
        if len(supplierList) != self.supplierCount:
            return True
        else:
            return False

#------------------------------------------------------------------------------ 

def SaveLatestRawListFiles(idurl, listFileText):
    """
    Save a ListFiles packet from given supplier on local HDD.
    """
    supplierPath = settings.SupplierPath(idurl)
    if not os.path.isdir(supplierPath):
        try:
            os.makedirs(supplierPath)
        except:
            dhnio.DprintException()
            return
    dhnio.WriteFile(settings.SupplierListFilesFilename(idurl), listFileText)


def ReadRawListFiles(supplierNum, listFileText):
    """
    Read ListFiles packet for given supplier and build a "remote" matrix.
    All lines are something like that::
    
      Findex
      D0
      D0/1 
      V0/1/F20090709034221PM 3 0-1000
      V0/1/F20090709034221PM 3 0-1000
      D0/0/123/4567
      V0/0/123/4567/F20090709034221PM 3 0-11 missing Data:1,3
      V0/0/123/4/F20090709012331PM 3 0-5 missing Data:1,3 Parity:0,1,2
        
    First character can be::
    
      "F" for files
      "D" for folders
      "V" for backed up data 
    """
    backups2remove = set()
    paths2remove = set()
    oldfiles = ClearSupplierRemoteInfo(supplierNum)
    newfiles = 0
    dhnio.Dprint(8, 'backup_matrix.ReadRawListFiles %d bytes to read' % len(listFileText))
    input = cStringIO.StringIO(listFileText)
    while True:
        line = input.readline()
        if line == '':
            break
        typ = line[0]
        line = line[1:] 
        line = line.rstrip('\n')
        # comment lines in Files reports start with blank,
        if line.strip() == '':
            continue
        # also don't consider the identity a backup,
        if line.find('http://') != -1 or line.find('.xml') != -1:
            continue
        # nor backup_info.xml, nor backup_db, nor index  files 
        if line in [ settings.BackupIndexFileName(), settings.BackupInfoFileName(), settings.BackupInfoFileNameOld(), settings.BackupInfoEncryptedFileName() ]:
            continue
        if typ == 'F':
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
            # the first idea:  check backup_db_keeper state - READY means index is fine
            # the second idea: check revision number of the local index - 0 means we have no index yet 
            if not backup_fs.IsFileID(line): # remote supplier have some file - but we don't have it in the index
                if backup_control.revision() > 0 and backup_db_keeper.A().IsSynchronized():  
                    # so we have some modifications in the index - it is not empty!
                    # backup_db_keeper did its job - so we have the correct index
                    paths2remove.add(line) # now we are sure that this file is old and must be removed
                    dhnio.Dprint(8, '        F%s - remove, not found in the index' % line)
                # what to do now? let's hope we still can restore our index and this file is our remote data
        elif typ == 'D':
            if not backup_fs.ExistsID(line):
                if backup_control.revision() > 0 and backup_db_keeper.A().IsSynchronized():
                    paths2remove.add(line)
                    dhnio.Dprint(8, '        D%s - remove, not found in the index' % line)
        elif typ == 'V':
            words = line.split(' ')
            # minimum is 3 words: "0/0/F20090709034221PM", "3", "0-1000"
            if len(words) < 3:
                dhnio.Dprint(2, 'backup_matrix.ReadRawListFiles WARNING incorrect line:[%s]' % line)
                continue
            try:
                pathID, versionName = packetid.SplitBackupID(words[0])
                backupID = pathID+'/'+versionName
                lineSupplierNum = int(words[1])
                minBlockNum, maxBlockNum = words[2].split('-')
                maxBlockNum = int(maxBlockNum)
            except:
                dhnio.Dprint(2, 'backup_matrix.ReadRawListFiles WARNING incorrect line:[%s]' % line)
                continue
            if lineSupplierNum != supplierNum:
                # this mean supplier have old files and we do not need that 
                backups2remove.add(backupID)
                dhnio.Dprint(8, '        V%s - remove, different supplier number' % backupID)
                continue
            iter_path = backup_fs.WalkByID(pathID)
            if iter_path is None:
                # this version is not found in the index
                if backup_control.revision() > 0 and backup_db_keeper.A().IsSynchronized():
                    backups2remove.add(backupID)
                    paths2remove.add(pathID)
                    dhnio.Dprint(8, '        V%s - remove, path not found in the index' % pathID)
                continue
            item, localPath = iter_path
            if isinstance(item, dict):
                try:
                    item = item[backup_fs.INFO_KEY]
                except:
                    item = None
            if not item or not item.has_version(versionName):
                if backup_control.revision() > 0 and backup_db_keeper.A().IsSynchronized():
                    backups2remove.add(backupID)
                    dhnio.Dprint(8, '        V%s - remove, version is not found in the index' % backupID)
                continue
            missingBlocksSet = {'Data': set(), 'Parity': set()}
            if len(words) > 3:
                # "0/0/123/4567/F20090709034221PM/0-Data" "3" "0-5" "missing" "Data:1,3" "Parity:0,1,2"
                if words[3].strip() != 'missing':
                    dhnio.Dprint(2, 'backup_matrix.ReadRawListFiles WARNING incorrect line:[%s]' % line)
                    continue
                for missingBlocksString in words[4:]:
                    try:
                        dp, blocks = missingBlocksString.split(':')
                        missingBlocksSet[dp] = set(blocks.split(','))
                    except:
                        dhnio.DprintException()
                        break
            if not remote_files().has_key(backupID):
                remote_files()[backupID] = {}
                # dhnio.Dprint(6, 'backup_matrix.ReadRawListFiles new remote entry for %s created in the memory' % backupID)
            # +1 because range(2) give us [0,1] but we want [0,1,2]
            for blockNum in xrange(maxBlockNum+1):
                if not remote_files()[backupID].has_key(blockNum):
                    remote_files()[backupID][blockNum] = {
                        'D': [0] * suppliers_set().supplierCount,
                        'P': [0] * suppliers_set().supplierCount,}
                for dataORparity in ['Data', 'Parity']:
                    # we set -1 if the file is missing and 1 if exist, so 0 mean "no info yet" ... smart!
                    bit = -1 if str(blockNum) in missingBlocksSet[dataORparity] else 1 
                    remote_files()[backupID][blockNum][dataORparity[0]][supplierNum] = bit
                    newfiles += int((bit + 1) / 2) # this should switch -1 or 1 to 0 or 1
            # save max block number for this backup
            if not remote_max_block_numbers().has_key(backupID):
                remote_max_block_numbers()[backupID] = -1 
            if maxBlockNum > remote_max_block_numbers()[backupID]:
                remote_max_block_numbers()[backupID] = maxBlockNum
            # mark this backup to be repainted
            RepaintBackup(backupID)
    input.close()
    dhnio.Dprint(8, 'backup_matrix.ReadRawListFiles for supplier %d, old/new files:%d/%d, backups2remove:%d, paths2remove:%d' % (
        supplierNum, oldfiles, newfiles, len(backups2remove), len(paths2remove)))
    # return list of backupID's which is too old but stored on suppliers machines 
    return backups2remove, paths2remove
            

def ReadLatestRawListFiles():
    """
    Call ``ReadRawListFiles()`` for every local file we have on hands and build whole "remote" matrix.
    """
    dhnio.Dprint(4, 'backup_matrix.ReadLatestRawListFiles')
    for idurl in contacts.getSupplierIDs():
        if idurl:
            filename = os.path.join(settings.SupplierPath(idurl, 'listfiles'))
            if os.path.isfile(filename):
                listFileText = dhnio.ReadTextFile(filename)
                if listFileText.strip() != '':
                    ReadRawListFiles(contacts.numberForSupplier(idurl), listFileText)

def ReadLocalFiles():
    """
    This method scans local backups and build the whole "local" matrix.
    """
    global _LocalFilesNotifyCallback
    local_files().clear()
    local_max_block_numbers().clear()
    local_backup_size().clear()
    _counter = [0,]
    def visit(realpath, subpath, name):
        # subpath is something like 0/0/1/0/F20131120053803PM/0-1-Data  
        if not os.path.isfile(realpath):
            return True
        if realpath.startswith('newblock-'):
            return False
        if subpath in [ settings.BackupIndexFileName(), settings.BackupInfoFileName(), settings.BackupInfoFileNameOld(), settings.BackupInfoEncryptedFileName() ]:
            return False
        try:
            version = subpath.split('/')[-2]
        except:
            return False
        if not packetid.IsCanonicalVersion(version):
            return True
        LocalFileReport(packetID=subpath)
        _counter[0] += 1
        return False
    dhnio.traverse_dir_recursive(visit, settings.getLocalBackupsDir())
    dhnio.Dprint(8, 'backup_matrix.ReadLocalFiles  %d files indexed' % _counter[0])
    if dhnio.Debug(8):
        try:
            if sys.version_info >= (2, 6):
                #localSZ = sys.getsizeof(local_files())
                #remoteSZ = sys.getsizeof(remote_files())
                import lib.getsizeof
                localSZ = lib.getsizeof.total_size(local_files())
                remoteSZ = lib.getsizeof.total_size(remote_files())
                indexByName = lib.getsizeof.total_size(backup_fs.fs())
                indexByID = lib.getsizeof.total_size(backup_fs.fsID())
                dhnio.Dprint(10, '    all local info uses %d bytes in the memory' % localSZ)
                dhnio.Dprint(10, '    all remote info uses %d bytes in the memory' % remoteSZ)
                dhnio.Dprint(10, '    index by name takes %d bytes in the memory' % indexByName)
                dhnio.Dprint(10, '    index by ID takes %d bytes in the memory' % indexByID)
        except:
            dhnio.DprintException()
    if _LocalFilesNotifyCallback is not None:
        _LocalFilesNotifyCallback()

#------------------------------------------------------------------------------ 

def RemoteFileReport(backupID, blockNum, supplierNum, dataORparity, result):
    """
    Writes info for a single piece of data into "remote" matrix.
    May be called when you got an Ack packet from remote supplier 
    after you sent him some Data packet. 
    """
    blockNum = int(blockNum)
    supplierNum = int(supplierNum)
    if supplierNum > suppliers_set().supplierCount:
        dhnio.Dprint(4, 'backup_matrix.RemoteFileReport got too big supplier number, possible this is an old packet')
        return
    if not remote_files().has_key(backupID):
        remote_files()[backupID] = {}
        dhnio.Dprint(8, 'backup_matrix.RemoteFileReport new remote entry for %s created in the memory' % backupID)
    if not remote_files()[backupID].has_key(blockNum):
        remote_files()[backupID][blockNum] = {
            'D': [0] * suppliers_set().supplierCount,
            'P': [0] * suppliers_set().supplierCount,}
    # save backed up block info into remote info structure, synchronize on hand info
    flag = 1 if result else 0
    if dataORparity == 'Data':
        remote_files()[backupID][blockNum]['D'][supplierNum] = flag 
    elif dataORparity == 'Parity':
        remote_files()[backupID][blockNum]['P'][supplierNum] = flag
    else:
        dhnio.Dprint(4, 'backup_matrix.RemoteFileReport WARNING incorrect backup ID: %s' % backupID)
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
        backupID, blockNum, supplierNum, dataORparity = packetid.Split(packetID)  
        if backupID is None:
            dhnio.Dprint(8, 'backup_matrix.LocalFileReport WARNING incorrect filename: ' + packetID)
            return
    else:
        blockNum = int(blockNum)
        supplierNum = int(supplierNum)
        dataORparity = dataORparity
        packetID = packetid.MakePacketID(backupID, blockNum, supplierNum, dataORparity)
    filename = packetID
    if dataORparity not in ['Data', 'Parity']:
        dhnio.Dprint(4, 'backup_matrix.LocalFileReport WARNING Data or Parity? ' + filename)
        return
    if supplierNum >= suppliers_set().supplierCount:
        dhnio.Dprint(4, 'backup_matrix.LocalFileReport WARNING supplier number %d > %d %s' % (supplierNum, suppliers_set().supplierCount, filename))
        return
    if not local_files().has_key(backupID):
        local_files()[backupID] = {}
        # dhnio.Dprint(14, 'backup_matrix.LocalFileReport new local entry for %s created in the memory' % backupID)
    if not local_files()[backupID].has_key(blockNum):
        local_files()[backupID][blockNum] = {
            'D': [0] * suppliers_set().supplierCount,
            'P': [0] * suppliers_set().supplierCount}
    local_files()[backupID][blockNum][dataORparity[0]][supplierNum] = 1
    if not local_max_block_numbers().has_key(backupID):
        local_max_block_numbers()[backupID] = -1
    if local_max_block_numbers()[backupID] < blockNum:
        local_max_block_numbers()[backupID] = blockNum
    # dhnio.Dprint(6, 'backup_matrix.LocalFileReport %s max block num is %d' % (backupID, local_max_block_numbers()[backupID]))
    if not local_backup_size().has_key(backupID):
        local_backup_size()[backupID] = 0
    localDest = os.path.join(settings.getLocalBackupsDir(), filename)
    if os.path.isfile(localDest):
        try:
            local_backup_size()[backupID] += os.path.getsize(localDest)
        except:
            dhnio.DprintException()
    RepaintBackup(backupID)


def LocalBlockReport(newblock, num_suppliers):
    """
    This updates "local" matrix - a several pieces corresponding to given block of data.
    """
    if suppliers_set().supplierCount != num_suppliers:
        dhnio.Dprint(6, 'backup_matrix.LocalBlockReport %s skipped, because number of suppliers were changed' % str(newblock))
        return
    try:
        backupID = newblock.BackupID
        blockNum = int(newblock.BlockNumber)
    except:
        dhnio.DprintException()
        return
    for supplierNum in xrange(num_suppliers):
        for dataORparity in ('Data', 'Parity'):
            packetID = packetid.MakePacketID(backupID, blockNum, supplierNum, dataORparity)
            if not local_files().has_key(backupID):
                local_files()[backupID] = {}
                # dhnio.Dprint(14, 'backup_matrix.LocalFileReport new local entry for %s created in the memory' % backupID)
            if not local_files()[backupID].has_key(blockNum):
                local_files()[backupID][blockNum] = {
                    'D': [0] * suppliers_set().supplierCount,
                    'P': [0] * suppliers_set().supplierCount}
            local_files()[backupID][blockNum][dataORparity[0]][supplierNum] = 1
            # dhnio.Dprint(6, 'backup_matrix.LocalFileReport %s max block num is %d' % (backupID, local_max_block_numbers()[backupID]))
            if not local_backup_size().has_key(backupID):
                local_backup_size()[backupID] = 0
            try:
                local_backup_size()[backupID] += os.path.getsize(os.path.join(settings.getLocalBackupsDir(), packetID))
            except:
                dhnio.DprintException()
    if not local_max_block_numbers().has_key(backupID):
        local_max_block_numbers()[backupID] = -1
    if local_max_block_numbers()[backupID] < blockNum:
        local_max_block_numbers()[backupID] = blockNum
    RepaintBackup(backupID)

#------------------------------------------------------------------------------ 

def ScanMissingBlocks(backupID):
    """
    Finally here is some real logic.
    This will compare both matrixes to find missing pieces on remote suppliers.
    Should return a list of numbers of missed blocks for given backup. 
    """
    missingBlocks = set()
    localMaxBlockNum = local_max_block_numbers().get(backupID, -1)
    remoteMaxBlockNum = remote_max_block_numbers().get(backupID, -1)
    supplierActiveArray = suppliers_set().GetActiveArray()

    if not remote_files().has_key(backupID):
        if not local_files().has_key(backupID):
            # we have no local and no remote info for this backup
            # no chance to do some rebuilds...
            # TODO but how we get here ?! 
            dhnio.Dprint(4, 'backup_matrix.ScanMissingBlocks no local and no remote info for %s' % backupID)
        else:
            # we have no remote info, but some local files exists
            # so let's try to sent all of them
            # need to scan all block numbers 
            for blockNum in xrange(localMaxBlockNum):
                # we check for Data and Parity packets
                localData = GetLocalDataArray(backupID, blockNum)
                localParity = GetLocalParityArray(backupID, blockNum)  
                for supplierNum in xrange(len(supplierActiveArray)):
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
        # dhnio.Dprint(6, 'backup_matrix.ScanMissingBlocks maxBlockNum=%d' % maxBlockNum)
        # and increase by one because range(3) give us [0, 1, 2], but we want [0, 1, 2, 3]
        for blockNum in xrange(maxBlockNum + 1):
            # if we have few remote files, but many locals - we want to send all missed 
            if not remote_files()[backupID].has_key(blockNum):
                missingBlocks.add(blockNum)
                continue
            # take remote info for this block
            remoteData = GetRemoteDataArray(backupID, blockNum)
            remoteParity = GetRemoteParityArray(backupID, blockNum)  
            # now check every our supplier for every block
            for supplierNum in xrange(len(supplierActiveArray)):
                # if supplier is not alive we can not send to him
                # so no need to scan for missing blocks 
                if supplierActiveArray[supplierNum] != 1:
                    continue
                if remoteData[supplierNum] != 1:    # -1 means missing
                    missingBlocks.add(blockNum)     # 0 - no info yet
                if remoteParity[supplierNum] != 1:  # 1 - file exist on remote supplier 
                    missingBlocks.add(blockNum)
                
    # dhnio.Dprint(6, 'backup_matrix.ScanMissingBlocks %s' % missingBlocks)
    return list(missingBlocks)

def ScanBlocksToRemove(backupID, check_all_suppliers=True):
    """
    This method compare both matrixes and found pieces which is present on both sides.
    If remote supplier got that file it can be removed from the local HDD.  
    """
    dhnio.Dprint(10, 'backup_matrix.ScanBlocksToRemove for %s' % backupID)
    packets = []
    localMaxBlockNum = local_max_block_numbers().get(backupID, -1)
    if not remote_files().has_key(backupID) or not local_files().has_key(backupID):
        # no info about this backup yet - skip
        return packets
    for blockNum in xrange(localMaxBlockNum + 1):
        localArray = {'Data': GetLocalDataArray(backupID, blockNum),
                      'Parity': GetLocalParityArray(backupID, blockNum)}  
        remoteArray = {'Data': GetRemoteDataArray(backupID, blockNum),
                       'Parity': GetRemoteParityArray(backupID, blockNum)}  
        if ( 0 in remoteArray['Data'] ) or ( 0 in remoteArray['Parity'] ):
            # if some supplier do not have some data for that block - do not remove any local files for that block!
            # we do remove the local files only when we sure all suppliers got the all data pieces
            continue
        if ( -1 in remoteArray['Data'] ) or ( -1 in remoteArray['Parity'] ):
            # also if we do not have any info about this block for some supplier do not remove other local pieces
            continue
        for supplierNum in xrange(suppliers_set().supplierCount):
            supplierIDURL = suppliers_set().suppliers[supplierNum]
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
                    dhnio.Dprint(10, '    mark to remove %s, blockNum:%d remote:%s local:%s' % (packetID, blockNum, str(remoteArray), str(localArray)))
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
    if '' in suppliers_set().suppliers:
        return {} 
    localMaxBlockNum = local_max_block_numbers().get(backupID, -1)
    supplierActiveArray = suppliers_set().GetActiveArray()
    bySupplier = {}
    for supplierNum in xrange(len(supplierActiveArray)):
        bySupplier[supplierNum] = set()
    if not remote_files().has_key(backupID):
        for blockNum in xrange(localMaxBlockNum + 1):
            localData = GetLocalDataArray(backupID, blockNum)
            localParity = GetLocalParityArray(backupID, blockNum)  
            for supplierNum in xrange(len(supplierActiveArray)):
                if supplierActiveArray[supplierNum] != 1:
                    continue
                if localData[supplierNum] == 1:
                    bySupplier[supplierNum].add(packetid.MakePacketID(backupID, blockNum, supplierNum, 'Data'))
                if localParity[supplierNum] == 1:
                    bySupplier[supplierNum].add(packetid.MakePacketID(backupID, blockNum, supplierNum, 'Parity'))
    else:
        for blockNum in xrange(localMaxBlockNum + 1):
            remoteData = GetRemoteDataArray(backupID, blockNum)
            remoteParity = GetRemoteParityArray(backupID, blockNum)  
            localData = GetLocalDataArray(backupID, blockNum)
            localParity = GetLocalParityArray(backupID, blockNum)  
            for supplierNum in xrange(len(supplierActiveArray)):
                if supplierActiveArray[supplierNum] != 1:
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
    if backup_control.HasRunningBackup():
        minDelay = 8.0
    _RepaintingTaskDelay = misc.LoopAttenuation(_RepaintingTaskDelay, len(_UpdatedBackupIDs) > 0, minDelay, 8.0)
    _UpdatedBackupIDs.clear()
    _RepaintingTask = reactor.callLater(_RepaintingTaskDelay, RepaintingProcess, True)

#------------------------------------------------------------------------------ 

def EraseBackupRemoteInfo(backupID): 
    """
    Clear info only for given backup from "remote" matrix.
    """
    if remote_files().has_key(backupID):
        del remote_files()[backupID] # remote_files().pop(backupID)
    if remote_max_block_numbers().has_key(backupID):
        del remote_max_block_numbers()[backupID]
        
def EraseBackupLocalInfo(backupID):
    """
    Clear info only for given backup from "local" matrix.
    """
    if local_files().has_key(backupID):
        del local_files()[backupID] # local_files().pop(backupID)
    if local_max_block_numbers().has_key(backupID):
        del local_max_block_numbers()[backupID]
    if local_backup_size().has_key(backupID):
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
    
def ClearSupplierRemoteInfo(supplierNum):
    """
    Clear only "single column" in the "remote" matrix corresponding to given supplier. 
    """
    files = 0
    for backupID in remote_files().keys():
        for blockNum in remote_files()[backupID].keys():
            if remote_files()[backupID][blockNum]['D'][supplierNum] == 1:
                files += 1 
            if remote_files()[backupID][blockNum]['P'][supplierNum] == 1:
                files += 1
            remote_files()[backupID][blockNum]['D'][supplierNum] = 0
            remote_files()[backupID][blockNum]['P'][supplierNum] = 0
    return files

#------------------------------------------------------------------------------ 

def GetBackupStats(backupID):
    """
    Collect needed info from "remote" matrix and create a detailed report about given backup.
    """
    if not remote_files().has_key(backupID):
        return 0, 0, [(0, 0)] * suppliers_set().supplierCount
    percentPerSupplier = 100.0 / suppliers_set().supplierCount
    # ??? maxBlockNum = remote_max_block_numbers().get(backupID, -1)
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    fileNumbers = [0] * suppliers_set().supplierCount
    totalNumberOfFiles = 0
    for blockNum in remote_files()[backupID].keys():
        for supplierNum in xrange(len(fileNumbers)):
            if supplierNum < suppliers_set().supplierCount:
                if remote_files()[backupID][blockNum]['D'][supplierNum] == 1:
                    fileNumbers[supplierNum] += 1
                    totalNumberOfFiles += 1
                if remote_files()[backupID][blockNum]['P'][supplierNum] == 1:
                    fileNumbers[supplierNum] += 1
                    totalNumberOfFiles += 1
    statsArray = []
    for supplierNum in xrange(suppliers_set().supplierCount):
        if maxBlockNum > -1:
            # 0.5 because we count both Parity and Data.
            percent = percentPerSupplier * 0.5 * fileNumbers[supplierNum] / ( maxBlockNum + 1 )
        else:
            percent = 0.0
        statsArray.append(( percent, fileNumbers[supplierNum] ))
    del fileNumbers 
    return totalNumberOfFiles, maxBlockNum, statsArray


def GetBackupLocalStats(backupID):
    """
    Provide detailed info about local files for that backup.
    Return a tuple::
    
      (totalPercent, totalNumberOfFiles, totalSize, maxBlockNum, statsArray)
    """
    # ??? maxBlockNum = local_max_block_numbers().get(backupID, -1)
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    if not local_files().has_key(backupID):
        return 0, 0, 0, maxBlockNum, [(0, 0)] * suppliers_set().supplierCount
    percentPerSupplier = 100.0 / suppliers_set().supplierCount
    totalNumberOfFiles = 0
    fileNumbers = [0] * suppliers_set().supplierCount
    for blockNum in xrange(maxBlockNum + 1):
        if blockNum not in local_files()[backupID].keys():
            continue
#    for blockNum in local_files()[backupID].keys():
        for supplierNum in xrange(len(fileNumbers)):
            if supplierNum < suppliers_set().supplierCount:
                if local_files()[backupID][blockNum]['D'][supplierNum] == 1:
                    fileNumbers[supplierNum] += 1
                    totalNumberOfFiles += 1
                if local_files()[backupID][blockNum]['P'][supplierNum] == 1:
                    fileNumbers[supplierNum] += 1
                    totalNumberOfFiles += 1
    statsArray = []
    for supplierNum in xrange(suppliers_set().supplierCount):
        if maxBlockNum > -1:
            # 0.5 because we count both Parity and Data.
            percent = percentPerSupplier * 0.5 * fileNumbers[supplierNum] / ( maxBlockNum + 1 )
        else:
            percent = 0.0
        statsArray.append(( percent, fileNumbers[supplierNum] ))
    del fileNumbers 
    totalPercent = 100.0 * 0.5 * totalNumberOfFiles / ((maxBlockNum + 1) * suppliers_set().supplierCount)
    return totalPercent, totalNumberOfFiles, local_backup_size().get(backupID, 0), maxBlockNum, statsArray


def GetBackupBlocksAndPercent(backupID):
    """
    Another method to get details about a backup.
    """
    if not remote_files().has_key(backupID):
        return 0, 0
    # get max block number
    # ??? maxBlockNum = remote_max_block_numbers().get(backupID, -1)
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    if maxBlockNum == -1:
        return 0, 0
    # we count all remote files for this backup
    fileCounter = 0
    for blockNum in remote_files()[backupID].keys():
        for supplierNum in xrange(suppliers_set().supplierCount):
            if remote_files()[backupID][blockNum]['D'][supplierNum] == 1:
                fileCounter += 1
            if remote_files()[backupID][blockNum]['P'][supplierNum] == 1:
                fileCounter += 1
    # +1 since zero based and *0.5 because Data and Parity
    return maxBlockNum + 1, 100.0 * 0.5 * fileCounter / ((maxBlockNum + 1) * suppliers_set().supplierCount)


def GetBackupRemoteStats(backupID, only_available_files=True):
    """
    This method found a most "weak" block of that backup, 
    this is a block which pieces is kept by less suppliers from all other blocks.
    
    This is needed to detect the whole backup availability.
    Because if you loose at least one block of the backup - you will loose the whole backup.!
    
    The backup condition is equal to the "worst" block condition.
    Return a tuple::
      
      (blocks, percent, weakBlock, weakBlockPercent)
    """
    if not remote_files().has_key(backupID):
        return 0, 0, 0, 0
    # get max block number
    # ??? maxBlockNum = remote_max_block_numbers().get(backupID, -1)
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    if maxBlockNum == -1:
        return 0, 0, 0, 0
    supplierCount = suppliers_set().supplierCount
    fileCounter = 0
    weakBlockNum = -1
    lessSuppliers = supplierCount
    activeArray = suppliers_set().GetActiveArray()
    # we count all remote files for this backup - scan all blocks
    for blockNum in xrange(maxBlockNum + 1):
        if blockNum not in remote_files()[backupID].keys():
            lessSuppliers = 0
            weakBlockNum = blockNum
            continue
        goodSuppliers = supplierCount
        for supplierNum in xrange(supplierCount):
            if activeArray[supplierNum] != 1 and only_available_files:
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
    return (maxBlockNum + 1, 100.0 * 0.5 * fileCounter / ((maxBlockNum + 1) * supplierCount),
            weakBlockNum, 100.0 * float(lessSuppliers) / float(supplierCount))


def GetBackupRemoteArray(backupID):
    """
    Get info for given backup from "remote" matrix. 
    """
    if not remote_files().has_key(backupID):
        return None
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    if maxBlockNum == -1:
        return None
    return remote_files()[backupID]


def GetBackupLocalArray(backupID):
    """
    Get info for given backup from "local" matrix. 
    """
    if not local_files().has_key(backupID):
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
        s.update(remote_files().keys())
    if local:
        s.update(local_files().keys())
    if sorted_ids:
        return misc.sorted_backup_ids(list(s))
    return list(s)


def GetKnownMaxBlockNum(backupID):
    """
    Return a maximum "known" block number for given backup.
    """
    return max(remote_max_block_numbers().get(backupID, -1), 
               local_max_block_numbers().get(backupID, -1))


def GetLocalDataArray(backupID, blockNum):
    """
    Get "local" info for a single block of given backup, this is for "Data" surface.  
    """
    if not local_files().has_key(backupID):
        return [0] * suppliers_set().supplierCount
    if not local_files()[backupID].has_key(blockNum):
        return [0] * suppliers_set().supplierCount
    return local_files()[backupID][blockNum]['D']


def GetLocalParityArray(backupID, blockNum):
    """
    Get "local" info for a single block of given backup, this is for "Parity" surface.  
    """
    if not local_files().has_key(backupID):
        return [0] * suppliers_set().supplierCount
    if not local_files()[backupID].has_key(blockNum):
        return [0] * suppliers_set().supplierCount
    return local_files()[backupID][blockNum]['P']
    

def GetRemoteDataArray(backupID, blockNum):
    """
    Get "remote" info for a single block of given backup, this is for "Data" surface.  
    """
    if not remote_files().has_key(backupID):
        return [0] * suppliers_set().supplierCount
    if not remote_files()[backupID].has_key(blockNum):
        return [0] * suppliers_set().supplierCount
    return remote_files()[backupID][blockNum]['D']

    
def GetRemoteParityArray(backupID, blockNum):
    """
    Get "remote" info for a single block of given backup, this is for "Parity" surface.  
    """
    if not remote_files().has_key(backupID):
        return [0] * suppliers_set().supplierCount
    if not remote_files()[backupID].has_key(blockNum):
        return [0] * suppliers_set().supplierCount
    return remote_files()[backupID][blockNum]['P']


def GetSupplierStats(supplierNum):
    """
    Collect info from "remote" matrix about given supplier.
    """
    result = {}
    files = total = 0
    for backupID in remote_files().keys():
        result[backupID] = [0, 0]
        for blockNum in remote_files()[backupID].keys():
            if remote_files()[backupID][blockNum]['D'][supplierNum] == 1:
                result[backupID][0] += 1
                files += 1 
            if remote_files()[backupID][blockNum]['P'][supplierNum] == 1:
                result[backupID][0] += 1
                files += 1
            result[backupID][1] += 2
            total += 2
    return files, total, result


def GetWeakLocalBlock(backupID):
    """
    Scan all "local" blocks for given backup and find the most "weak" block. 
    """
    supplierCount = suppliers_set().supplierCount
    if not local_files().has_key(backupID):
        return -1, 0, supplierCount
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    weakBlockNum = -1
    lessSuppliers = supplierCount
    for blockNum in xrange(maxBlockNum+1):
        if blockNum not in local_files()[backupID].keys():
            return blockNum, 0, supplierCount
        goodSuppliers = supplierCount
        for supplierNum in xrange(supplierCount):
            if  local_files()[backupID][blockNum]['D'][supplierNum] != 1 or local_files()[backupID][blockNum]['P'][supplierNum] != 1:
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
    supplierCount = suppliers_set().supplierCount
    if not remote_files().has_key(backupID):
        return -1, 0, supplierCount
    maxBlockNum = GetKnownMaxBlockNum(backupID)
    weakBlockNum = -1
    lessSuppliers = supplierCount
    activeArray = suppliers_set().GetActiveArray()
    for blockNum in xrange(maxBlockNum+1):
        if blockNum not in remote_files()[backupID].keys():
            return blockNum, 0, supplierCount
        goodSuppliers = supplierCount
        for supplierNum in xrange(supplierCount):
            if activeArray[supplierNum] != 1:
                goodSuppliers -= 1
                continue
            if  remote_files()[backupID][blockNum]['D'][supplierNum] != 1 or remote_files()[backupID][blockNum]['P'][supplierNum] != 1:
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
    import pprint
    # pprint.pprint(GetBackupIds())











