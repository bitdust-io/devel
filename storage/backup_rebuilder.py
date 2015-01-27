#!/usr/bin/python
#backup_rebuilder.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: backup_rebuilder

.. raw:: html

    <a href="http://bitdust.io/automats/backup_rebuilder/backup_rebuilder.png" target="_blank">
    <img src="http://bitdust.io/automats/backup_rebuilder/backup_rebuilder.png" style="max-width:100%;">
    </a>
    
This is a state machine to run the rebuilding process.
If some pieces is missing, need to reconstruct them asap.

To do that you need to know needed number of pieces on hands, 
so need to request the missing segments.

The ``backup_rebuilder()`` machine works on backups one by one (keep them in queue) 
and can be stopped and started at any time. 

The whole process here may be stopped from ``backup_monitor()`` by 
setting a flag in the ``isStopped()`` condition.
This is need to be able to stop the rebuilding process - 
to do rebuilding of a single block we need start a blocking code. 

EVENTS:
    * :red:`backup-ready`
    * :red:`inbox-data-packet`
    * :red:`init`
    * :red:`instant`
    * :red:`rebuilding-finished`
    * :red:`requests-sent`
    * :red:`start`
    * :red:`timer-10sec`
    * :red:`timer-1min`
    * :red:`timer-1sec`

"""

import os
import sys


try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in backup_rebuilder.py')

#------------------------------------------------------------------------------ 

from logs import lg

from lib import packetid

from automats import automat

from system import bpio

from main import settings

from contacts import contactsdb
from userid import my_id

from raid import eccmap
from raid import raid_worker

import backup_monitor

#------------------------------------------------------------------------------ 

_BackupRebuilder = None
_StoppedFlag = True
_BackupIDsQueue = []  
_BlockRebuildersQueue = []

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _BackupRebuilder
    if _BackupRebuilder is None:
        _BackupRebuilder = BackupRebuilder('backup_rebuilder', 'STOPPED', 4, True)
    if event is not None:
        _BackupRebuilder.automat(event, arg)
    return _BackupRebuilder


def Destroy():
    """
    Destroy backup_rebuilder() automat and remove its instance from memory.
    """
    global _BackupRebuilder
    if _BackupRebuilder is None:
        return
    _BackupRebuilder.destroy()
    del _BackupRebuilder
    _BackupRebuilder = None
    

class BackupRebuilder(automat.Automat):
    """
    A class to prepare and run rebuilding operations. 
    """

    timers = {
        'timer-1min': (60, ['REQUEST']),
        'timer-1sec': (1.0, ['REQUEST']),
        'timer-10sec': (10.0, ['REQUEST']),
        }
    
    def init(self):
        """
        Initialize needed variables.
        """
        self.currentBackupID = None             # currently working on this backup
        self.workingBlocksQueue = []            # list of missing blocks we work on for current backup
        self.missingPackets = 0 
        self.missingSuppliers = set()

    def state_changed(self, oldstate, newstate, event, arg):
        """
        This method is called every time when my state is changed.
        Need to notify backup_monitor() machine about my new state. 
        """
        # global_state.set_global_state('REBUILD ' + newstate)
        if newstate == 'NEXT_BACKUP':
            self.automat('instant')
        elif newstate == 'DONE' or newstate == 'STOPPED':
            backup_monitor.A('backup_rebuilder.state', newstate)
        
    def A(self, event, arg):
        #---REQUEST---
        if self.state == 'REQUEST':
            if ( event == 'timer-10sec' or event == 'inbox-data-packet' or event == 'requests-sent' ) and self.isChanceToRebuild(arg) :
                self.state = 'REBUILDING'
                self.doAttemptRebuild(arg)
            elif event == 'timer-1min' or ( event == 'requests-sent' and self.isRequestQueueEmpty(arg) and not self.isMissingPackets(arg) ) :
                self.state = 'DONE'
                self.doCloseThisBackup(arg)
            elif ( event == 'instant' or event == 'timer-1sec' ) and self.isStopped(arg) :
                self.state = 'STOPPED'
                self.doCloseThisBackup(arg)
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'init' :
                self.doClearStoppedFlag(arg)
            elif event == 'start' :
                self.state = 'NEXT_BACKUP'
                self.doClearStoppedFlag(arg)
        #---NEXT_BACKUP---
        elif self.state == 'NEXT_BACKUP':
            if event == 'instant' and not self.isStopped(arg) and self.isMoreBackups(arg) :
                self.state = 'PREPARE'
                self.doOpenNextBackup(arg)
                self.doScanBrokenBlocks(arg)
            elif event == 'instant' and not self.isMoreBackups(arg) and not self.isStopped(arg) :
                self.state = 'DONE'
            elif event == 'instant' and self.isStopped(arg) :
                self.state = 'STOPPED'
        #---DONE---
        elif self.state == 'DONE':
            if event == 'start' :
                self.state = 'NEXT_BACKUP'
                self.doClearStoppedFlag(arg)
        #---PREPARE---
        elif self.state == 'PREPARE':
            if event == 'backup-ready' and not self.isStopped(arg) and self.isMoreBlocks(arg) :
                self.state = 'REQUEST'
                self.doRequestAvailablePieces(arg)
            elif event == 'backup-ready' and not self.isStopped(arg) and not self.isMoreBlocks(arg) and self.isMoreBackups(arg) :
                self.state = 'NEXT_BACKUP'
                self.doCloseThisBackup(arg)
            elif event == 'backup-ready' and ( not self.isMoreBackups(arg) and not self.isMoreBlocks(arg) ) :
                self.state = 'DONE'
                self.doCloseThisBackup(arg)
            elif ( event == 'instant' or event == 'backup-ready' ) and self.isStopped(arg) :
                self.state = 'STOPPED'
                self.doCloseThisBackup(arg)
        #---REBUILDING---
        elif self.state == 'REBUILDING':
            if event == 'rebuilding-finished' and not self.isStopped(arg) and self.isMoreBlocks(arg) :
                self.state = 'REQUEST'
                self.doRequestAvailablePieces(arg)
            elif ( event == 'instant' or event == 'rebuilding-finished' ) and self.isStopped(arg) :
                self.state = 'STOPPED'
                self.doCloseThisBackup(arg)
                self.doKillRebuilders(arg)
            elif event == 'rebuilding-finished' and not self.isStopped(arg) and not self.isMoreBlocks(arg) :
                self.state = 'PREPARE'
                self.doScanBrokenBlocks(arg)
        return None

    def isMoreBackups(self, arg):
        global _BackupIDsQueue
        return len(_BackupIDsQueue) > 0
    
    def isMoreBlocks(self, arg):
        # because started from 0,  -1 means not found
        return len(self.workingBlocksQueue) > 0 
        
    def isMissingPackets(self, arg):
        return self.missingPackets > 0 

    def isStopped(self, arg):
        return ReadStoppedFlag() == True # :-)
    
    def isChanceToRebuild(self, arg):
        import backup_matrix
#         return len(self.missingSuppliers) <= eccmap.Current().CorrectableErrors
        # supplierSet = backup_matrix.suppliers_set()
        # start checking in reverse order, see below for explanation
        for blockIndex in range(len(self.workingBlocksQueue)-1, -1, -1):
            blockNumber = self.workingBlocksQueue[blockIndex]
            if eccmap.Current().CanMakeProgress(
                    backup_matrix.GetLocalDataArray(self.currentBackupID, blockNumber),
                    backup_matrix.GetLocalParityArray(self.currentBackupID, blockNumber)):
                return True
        return False
    
    def isRequestQueueEmpty(self, arg):
        from customer import io_throttle
        # supplierSet = backup_matrix.suppliers_set()
        for supplierNum in range(contactsdb.num_suppliers()):
            supplierID = contactsdb.supplier(supplierNum)
            if io_throttle.HasBackupIDInRequestQueue(supplierID, self.currentBackupID):
                return False
        return True

    def doOpenNextBackup(self, arg):
        """
        """
        global _BackupIDsQueue
        # check it, may be we already fixed all things
        if len(_BackupIDsQueue) == 0:
            self.automat('backup-ready')
            return
        # take a first backup from queue to work on it
        self.currentBackupID = _BackupIDsQueue.pop(0)
         
    def doCloseThisBackup(self, arg):
        """
        Action method.
        """
        self.workingBlocksQueue = []
        if self.currentBackupID:
            # clear requesting queue from previous task
            from customer import io_throttle
            io_throttle.DeleteBackupRequests(self.currentBackupID)
        self.currentBackupID = None
        
    def doScanBrokenBlocks(self, arg):
        """
        Action method.
        """
        # if remote data structure is not exist for this backup - create it
        # this mean this is only local backup!
        import backup_matrix
        if not backup_matrix.remote_files().has_key(self.currentBackupID):
            backup_matrix.remote_files()[self.currentBackupID] = {}
            # we create empty remote info for every local block
            # range(0) should return []
            for blockNum in range(backup_matrix.local_max_block_numbers().get(self.currentBackupID, -1) + 1):
                backup_matrix.remote_files()[self.currentBackupID][blockNum] = {
                    'D': [0] * contactsdb.num_suppliers(),
                    'P': [0] * contactsdb.num_suppliers() }
        # detect missing blocks from remote info
        self.workingBlocksQueue = backup_matrix.ScanMissingBlocks(self.currentBackupID)
        # find the correct max block number for this backup
        # we can have remote and local files
        # will take biggest block number from both 
        backupMaxBlock = max(backup_matrix.remote_max_block_numbers().get(self.currentBackupID, -1),
                             backup_matrix.local_max_block_numbers().get(self.currentBackupID, -1))
        # now need to remember this biggest block number
        # remote info may have less blocks - need to create empty info for missing blocks
        for blockNum in range(backupMaxBlock + 1):
            if backup_matrix.remote_files()[self.currentBackupID].has_key(blockNum):
                continue
            backup_matrix.remote_files()[self.currentBackupID][blockNum] = {
                'D': [0] * contactsdb.num_suppliers(),
                'P': [0] * contactsdb.num_suppliers() }
        # clear requesting queue, remove old packets for this backup, we will send them again
        from customer import io_throttle
        io_throttle.DeleteBackupRequests(self.currentBackupID)
        lg.out(8, 'backup_rebuilder.doScanBrokenBlocks for %s : %s' % (
            self.currentBackupID, str(self.workingBlocksQueue)))
        self.automat('backup-ready')

    def doRequestAvailablePieces(self, arg):
        """
        Action method.
        """
        self._request_files()
            
    def doAttemptRebuild(self, arg):
        """
        Action method.
        """
        self.blocksSucceed = []
        if len(self.workingBlocksQueue) == 0:
            self.automat('rebuilding-finished', False)
            return            
        # let's rebuild the backup blocks in reverse order, take last blocks first ... 
        # in such way we can propagate how big is the whole backup as soon as possible!
        # remote machine can multiply [file size] * [block number] 
        # and calculate the whole size to be received ... smart!
        # ... remote supplier should not use last file to calculate
        self.blockIndex = len(self.workingBlocksQueue) - 1
        reactor.callLater(0, self._start_one_block)

    def doKillRebuilders(self, arg):
        """
        Action method.
        """
        raid_worker.A('shutdown')

    def doClearStoppedFlag(self, arg):
        ClearStoppedFlag()

    #------------------------------------------------------------------------------ 

    def _request_files(self):
        import backup_matrix
        from customer import io_throttle
        self.missingPackets = 0
        # here we want to request some packets before we start working to rebuild the missed blocks
        availableSuppliers = backup_matrix.GetActiveArray()
        # remember how many requests we did on this iteration
        total_requests_count = 0
        # at the moment I do download everything I have available and needed
        if '' in contactsdb.suppliers():
            lg.out(8, 'backup_rebuilder._request_files SKIP - empty supplier')
            self.automat('requests-sent', total_requests_count)
            return
        for supplierNum in range(contactsdb.num_suppliers()):
            supplierID = contactsdb.supplier(supplierNum)
            requests_count = 0
            # we do requests in reverse order because we start rebuilding from the last block 
            for blockIndex in range(len(self.workingBlocksQueue)-1, -1, -1):
                blockNum = self.workingBlocksQueue[blockIndex] 
                # do not keep too many requests in the queue
                if io_throttle.GetRequestQueueLength(supplierID) >= 16:
                    break
                # also don't do too many requests at once
                if requests_count > 16:
                    break
                remoteData = backup_matrix.GetRemoteDataArray(self.currentBackupID, blockNum)
                remoteParity = backup_matrix.GetRemoteParityArray(self.currentBackupID, blockNum)
                localData = backup_matrix.GetLocalDataArray(self.currentBackupID, blockNum)
                localParity = backup_matrix.GetLocalParityArray(self.currentBackupID, blockNum)
                # if the remote Data exist and is available because supplier is on line,
                # but we do not have it on hand - do request  
                if localData[supplierNum] == 0:
                    PacketID = packetid.MakePacketID(self.currentBackupID, blockNum, supplierNum, 'Data')
                    if remoteData[supplierNum] == 1:
                        if availableSuppliers[supplierNum]:
                            # if supplier is not alive - we can't request from him           
                            if not io_throttle.HasPacketInRequestQueue(supplierID, PacketID):
                                if io_throttle.QueueRequestFile(
                                        self._file_received, 
                                        my_id.getLocalID(), 
                                        PacketID, 
                                        my_id.getLocalID(), 
                                        supplierID):
                                    requests_count += 1
                    else:
                        # count this packet as missing
                        self.missingPackets += 1
                        # also mark this guy as one who dont have any data - nor local nor remote 
                        # self.missingSuppliers.add(supplierNum)
                # same for Parity
                if localParity[supplierNum] == 0:
                    PacketID = packetid.MakePacketID(self.currentBackupID, blockNum, supplierNum, 'Parity')
                    if remoteParity[supplierNum] == 1: 
                        if availableSuppliers[supplierNum]:
                            if not io_throttle.HasPacketInRequestQueue(supplierID, PacketID):
                                if io_throttle.QueueRequestFile(
                                        self._file_received, 
                                        my_id.getLocalID(), 
                                        PacketID, 
                                        my_id.getLocalID(), 
                                        supplierID):
                                    requests_count += 1
                    else:
                        self.missingPackets += 1
                        # self.missingSuppliers.add(supplierNum)
            total_requests_count += requests_count
        lg.out(8, 'backup_rebuilder._request_files : %d chunks requested')
        self.automat('requests-sent', total_requests_count)
        
    def _file_received(self, newpacket, state):
        if state in ['in queue', 'shutdown', 'exist', 'failed']:
            return
        if state != 'received':
            lg.warn("incorrect state [%s] for packet %s" % (str(state), str(newpacket)))
            return
        packetID = newpacket.PacketID
        filename = os.path.join(settings.getLocalBackupsDir(), packetID)
        if not newpacket.Valid():
            # TODO 
            # if we didn't get a valid packet ... re-request it or delete it?
            lg.warn("%s is not a valid packet: %r" % (packetID, newpacket))
            return
        if os.path.isfile(filename):
            lg.warn("found existed file" + filename)
            self.automat('inbox-data-packet', packetID)
            return
            # try: 
            #     os.remove(filename)
            # except:
            #     lg.exc()
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            try:
                bpio._dirs_make(dirname)
            except:
                lg.out(2, "backup_rebuilder._file_received ERROR can not create sub dir " + dirname)
                return 
        if not bpio.WriteFile(filename, newpacket.Payload):
            lg.out(2, "backup_rebuilder._file_received ERROR writing " + filename)
            return
        import backup_matrix
        backup_matrix.LocalFileReport(packetID)
        lg.out(10, "backup_rebuilder._file_received and wrote to " + filename)
        self.automat('inbox-data-packet', packetID)

    def _start_one_block(self): 
        import backup_matrix
        if self.blockIndex < 0:
            lg.out(10, 'backup_rebuilder._start_one_block finish all blocks blockIndex=%d' % self.blockIndex)
            reactor.callLater(0, self._finish_rebuilding)
            return
        BlockNumber = self.workingBlocksQueue[self.blockIndex]
        lg.out(10, 'backup_rebuilder._start_one_block %d to rebuild, blockIndex=%d, other blocks: %s' % (
            (BlockNumber, self.blockIndex, str(self.workingBlocksQueue))))
        task_params = ( 
            self.currentBackupID, BlockNumber, eccmap.Current(),
            backup_matrix.GetActiveArray(),
            backup_matrix.GetRemoteMatrix(self.currentBackupID, BlockNumber),
            backup_matrix.GetLocalMatrix(self.currentBackupID, BlockNumber),)
        raid_worker.add_task('rebuild', task_params,
            lambda cmd, params, result: self._block_finished(result, params))
        
    def _block_finished(self, result, params):
        if not result:
            lg.out(10, 'backup_rebuilder._block_finished FAILED, blockIndex=%d' % self.blockIndex)
            reactor.callLater(0, self._finish_rebuilding)
            return
        try:
            newData, localData, localParity, reconstructedData, reconstructedParity = result
            _backupID = params[0]
            _blockNumber = params[1]
        except:
            lg.exc()
            reactor.callLater(0, self._finish_rebuilding)
            return
        if newData: 
            import backup_matrix
            count = 0
            for supplierNum in xrange(contactsdb.num_suppliers()):
                if localData[supplierNum] == 1 and reconstructedData[supplierNum] == 1:
                    backup_matrix.LocalFileReport(None, _backupID, _blockNumber, supplierNum, 'Data')
                    count += 1
                if localParity[supplierNum] == 1 and reconstructedParity[supplierNum] == 1:
                    backup_matrix.LocalFileReport(None, _backupID, _blockNumber, supplierNum, 'Parity')
                    count += 1
            self.blocksSucceed.append(_blockNumber)
            from customer import data_sender
            data_sender.A('new-data')
            lg.out(10, 'backup_rebuilder._block_finished !!!!!! %d NEW DATA segments reconstructed, blockIndex=%d' % (
                count, self.blockIndex))
        else:
            lg.out(10, 'backup_rebuilder._block_finished NO CHANGES, blockIndex=%d' % self.blockIndex)
        self.blockIndex -= 1
        reactor.callLater(0, self._start_one_block)

    def _finish_rebuilding(self):
        for blockNum in self.blocksSucceed:
            self.workingBlocksQueue.remove(blockNum)
        lg.out(10, 'backup_rebuilder._finish_rebuilding succeed:%s working:%s' % (
            str(self.blocksSucceed), str(self.workingBlocksQueue)))
        result = len(self.blocksSucceed) > 0
        self.blocksSucceed = []
        self.automat('rebuilding-finished', result)         
                
#------------------------------------------------------------------------------ 

def AddBackupsToWork(backupIDs):
    """
    Put backups to the working queue, ``backupIDs`` is a list of backup IDs.
    They will be reconstructed one by one. 
    """
    global _BackupIDsQueue 
    _BackupIDsQueue.extend(backupIDs)


def RemoveBackupToWork(backupID):
    """
    Remove single backup from the working queue.
    """
    global _BackupIDsQueue
    if backupID in _BackupIDsQueue:
        _BackupIDsQueue.remove(backupID)


def IsBackupNeedsWork(backupID):
    """
    """
    global _BackupIDsQueue
    return backupID in _BackupIDsQueue


def RemoveAllBackupsToWork():
    """
    Clear the whole working queue.
    """
    global _BackupIDsQueue
    _BackupIDsQueue = []


def SetStoppedFlag():
    """
    To stop backup_rebuilder() you need to call this method, 
    it will set ``_StoppedFlag`` to True.
    """
    global _StoppedFlag
    _StoppedFlag = True
    A('instant')
    
    
def ClearStoppedFlag():
    """
    This set ``_StoppedFlag`` to False.
    """
    global _StoppedFlag
    _StoppedFlag = False
    

def ReadStoppedFlag():
    """
    Return current state of ``_StoppedFlag``.
    """
    global _StoppedFlag
    return _StoppedFlag
    
    
