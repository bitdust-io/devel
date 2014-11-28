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

    <a href="http://bitpie.net/automats/backup_rebuilder/backup_rebuilder.png" target="_blank">
    <img src="http://bitpie.net/automats/backup_rebuilder/backup_rebuilder.png" style="max-width:100%;">
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
        self.currentBlockNumber = -1            # currently working on this block
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
            if event == 'timer-1sec' and self.isStopped(arg) :
                self.state = 'STOPPED'
            elif ( event == 'timer-10sec' or event == 'inbox-data-packet' or event == 'requests-sent' ) and self.isChanceToRebuild(arg) :
                self.state = 'REBUILDING'
                self.doAttemptRebuild(arg)
            elif event == 'timer-1min' or ( event == 'requests-sent' and self.isRequestQueueEmpty(arg) and not self.isMissingPackets(arg) ) :
                self.state = 'DONE'
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'init' :
                pass
            elif event == 'start' :
                self.state = 'NEXT_BACKUP'
                self.doClearStoppedFlag(arg)
        #---NEXT_BACKUP---
        elif self.state == 'NEXT_BACKUP':
            if event == 'instant' and not self.isStopped(arg) and self.isMoreBackups(arg) :
                self.state = 'PREPARE'
                self.doPrepareNextBackup(arg)
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
            if event == 'backup-ready' and self.isStopped(arg) :
                self.state = 'STOPPED'
            elif event == 'backup-ready' and not self.isStopped(arg) and self.isMoreBlocks(arg) :
                self.state = 'REQUEST'
                self.doRequestAvailableBlocks(arg)
            elif event == 'backup-ready' and not self.isStopped(arg) and not self.isMoreBlocks(arg) and self.isMoreBackups(arg) :
                self.state = 'NEXT_BACKUP'
            elif event == 'backup-ready' and ( not self.isMoreBackups(arg) and not self.isMoreBlocks(arg) ) :
                self.state = 'DONE'
        #---REBUILDING---
        elif self.state == 'REBUILDING':
            if event == 'rebuilding-finished' and self.isStopped(arg) :
                self.state = 'STOPPED'
            elif event == 'rebuilding-finished' and not self.isStopped(arg) and self.isMoreBlocks(arg) :
                self.state = 'REQUEST'
                self.doRequestAvailableBlocks(arg)
            elif event == 'rebuilding-finished' and not self.isStopped(arg) and not self.isMoreBlocks(arg) :
                self.state = 'PREPARE'
                self.doPrepareNextBackup(arg)
        return None

    def isMoreBackups(self, arg):
        global _BackupIDsQueue
        return len(_BackupIDsQueue) > 0
    
    def isMoreBlocks(self, arg):
        # because started from 0,  -1 means not found
        return len(self.workingBlocksQueue) > 0 
        # return self.currentBlockNumber > -1
        
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

    def doPrepareNextBackup(self, arg):
        from customer import io_throttle
        import backup_matrix
        global _BackupIDsQueue
        # clear block number from previous iteration
        self.currentBlockNumber = -1
        # check it, may be we already fixed all things
        if len(_BackupIDsQueue) == 0:
            self.workingBlocksQueue = []
            self.automat('backup-ready')
            return
        # take a first backup from queue to work on it
        backupID = _BackupIDsQueue.pop(0)
        # if remote data structure is not exist for this backup - create it
        # this mean this is only local backup!
        if not backup_matrix.remote_files().has_key(backupID):
            backup_matrix.remote_files()[backupID] = {}
            # we create empty remote info for every local block
            # range(0) should return []
            for blockNum in range(backup_matrix.local_max_block_numbers().get(backupID, -1) + 1):
                backup_matrix.remote_files()[backupID][blockNum] = {
                    'D': [0] * contactsdb.num_suppliers(),
                    'P': [0] * contactsdb.num_suppliers() }
        # detect missing blocks from remote info
        self.workingBlocksQueue = backup_matrix.ScanMissingBlocks(backupID)
        lg.out(8, 'backup_rebuilder.doPrepareNextBackup [%s] working blocks: %s' % (backupID, str(self.workingBlocksQueue)))
        # find the correct max block number for this backup
        # we can have remote and local files
        # will take biggest block number from both 
        backupMaxBlock = max(backup_matrix.remote_max_block_numbers().get(backupID, -1),
                             backup_matrix.local_max_block_numbers().get(backupID, -1))
        # now need to remember this biggest block number
        # remote info may have less blocks - need to create empty info for missing blocks
        for blockNum in range(backupMaxBlock + 1):
            if backup_matrix.remote_files()[backupID].has_key(blockNum):
                continue
            backup_matrix.remote_files()[backupID][blockNum] = {
                'D': [0] * contactsdb.num_suppliers(),
                'P': [0] * contactsdb.num_suppliers() }
        if self.currentBackupID:
            # clear requesting queue from previous task
            io_throttle.DeleteBackupRequests(self.currentBackupID)
        # really take the next backup
        self.currentBackupID = backupID
        # clear requesting queue, remove old packets for this backup, we will send them again
        io_throttle.DeleteBackupRequests(self.currentBackupID)
        # lg.out(6, 'backup_rebuilder.doTakeNextBackup currentBackupID=%s workingBlocksQueue=%d' % (self.currentBackupID, len(self.workingBlocksQueue)))
        self.automat('backup-ready')

    def doRequestAvailableBlocks(self, arg):
        from customer import io_throttle
        import backup_matrix
        self.missingPackets = 0
        # self.missingSuppliers.clear()
        # here we want to request some packets before we start working to rebuild the missed blocks
        # supplierSet = backup_matrix.suppliers_set()
        availableSuppliers = backup_matrix.GetActiveArray()
        # remember how many requests we did on this iteration
        total_requests_count = 0
        # at the moment I do download everything I have available and needed
        if '' in contactsdb.suppliers():
            self.automat('requests-sent', total_requests_count)
            return
        for supplierNum in range(contactsdb.num_suppliers()):
            supplierID = contactsdb.supplier(supplierNum)
            requests_count = 0
            # we do requests in reverse order because we start rebuilding from the last block 
            # for blockNum in range(self.currentBlockNumber, -1, -1):
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
        self.automat('requests-sent', total_requests_count)
            
    def doAttemptRebuild(self, arg):
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
        lg.out(8, 'backup_rebuilder.doAttemptRebuild %d more blocks' % (self.blockIndex+1))
        def _prepare_one_block(): 
            import backup_matrix
            if self.blockIndex < 0:
                lg.out(8, '        _prepare_one_block finish all blocks')
                reactor.callLater(0, _finish_all_blocks)
                return
            self.currentBlockNumber = self.workingBlocksQueue[self.blockIndex]
            lg.out(8, '        _prepare_one_block %d to rebuild' % self.currentBlockNumber)
            task_params = (
                self.currentBackupID, self.currentBlockNumber, eccmap.Current(),
                backup_matrix.GetActiveArray(),
                backup_matrix.remote_files()[self.currentBackupID][self.currentBlockNumber],
                backup_matrix.local_files()[self.currentBackupID][self.currentBlockNumber],)
            raid_worker.add_task('rebuild', task_params,
                lambda cmd, params, result: _rebuild_finished(result))
        def _rebuild_finished(result):
            import backup_matrix
            self.blockIndex -= 1
            if result:
                try:
                    newData, localData, localParity, reconstructedData, reconstructedParity = result
                except:
                    lg.exc()
                    self.automat('rebuilding-finished', False)
                    return
                lg.out(8, '        _rebuild_finished on block %d, result is %s' % (self.currentBlockNumber, str(newData)))
                if newData:
                    for supplierNum in xrange(contactsdb.num_suppliers()):
                        if localData[supplierNum] == 1 and reconstructedData[supplierNum] == 1:
                            backup_matrix.LocalFileReport(None, self.currentBackupID, self.currentBlockNumber, supplierNum, 'Data')
                        if localParity[supplierNum] == 1 and reconstructedParity[supplierNum] == 1:
                            backup_matrix.LocalFileReport(None, self.currentBackupID, self.currentBlockNumber, supplierNum, 'Parity')
                    self.blocksSucceed.append(self.currentBlockNumber)
                    from customer import data_sender
                    data_sender.A('new-data')
            else:
                lg.out(8, '        _rebuild_finished on block %d, result is %s' % (self.currentBlockNumber, result))
                self.automat('rebuilding-finished', False)
                return
            reactor.callLater(0, _prepare_one_block)
        def _finish_all_blocks():
            for blockNum in self.blocksSucceed:
                self.workingBlocksQueue.remove(blockNum)
            lg.out(8, 'backup_rebuilder.doAttemptRebuild._finish_all_blocks succeed:%s working:%s' % (str(self.blocksSucceed), str(self.workingBlocksQueue)))
            result = len(self.blocksSucceed) > 0
            self.blocksSucceed = []
            self.automat('rebuilding-finished', result)         
        reactor.callLater(0, _prepare_one_block)
        
                
#    def doAttemptRebuild(self, arg):
#        self.workBlock = None
#        self.blocksSucceed = []
#        if len(self.workingBlocksQueue) == 0:
#            self.automat('rebuilding-finished', False)
#            return            
#        # let's rebuild the backup blocks in reverse order, take last blocks first ... 
#        # in such way we can propagate how big is the whole backup as soon as possible!
#        # remote machine can multiply [file size] * [block number] 
#        # and calculate the whole size to be received ... smart!
#        # ... remote supplier should not use last file to calculate
#        self.blockIndex = len(self.workingBlocksQueue) - 1
#        lg.out(8, 'backup_rebuilder.doAttemptRebuild %d more blocks' % (self.blockIndex+1))
#        def _prepare_one_block(): 
#            if self.blockIndex < 0:
#                # lg.out(8, '        _prepare_one_block finish all blocks')
#                reactor.callLater(0, _finish_all_blocks)
#                return
#            self.currentBlockNumber = self.workingBlocksQueue[self.blockIndex]
#            # lg.out(8, '        _prepare_one_block %d to rebuild' % self.currentBlockNumber)
#            self.workBlock = block_rebuilder.BlockRebuilder(
#                eccmap.Current(), #self.eccMap,
#                self.currentBackupID,
#                self.currentBlockNumber,
#                backup_matrix.suppliers_set(),
#                backup_matrix.GetRemoteDataArray(self.currentBackupID, self.currentBlockNumber),
#                backup_matrix.GetRemoteParityArray(self.currentBackupID, self.currentBlockNumber),
#                backup_matrix.GetLocalDataArray(self.currentBackupID, self.currentBlockNumber),
#                backup_matrix.GetLocalParityArray(self.currentBackupID, self.currentBlockNumber),)
#            reactor.callLater(0, _identify_block_packets)
#        def _identify_block_packets():
#            self.workBlock.IdentifyMissing()
##            if not self.workBlock.IsMissingFilesOnHand():
##                lg.out(8, '        _identify_block_packets some missing files is not come yet')
##                reactor.callLater(0, self.automat, 'rebuilding-finished', False)
##                return
#            reactor.callLater(0, _work_on_block)
#        def _work_on_block():
#            # self.workBlock.AttemptRebuild().addBoth(_rebuild_finished)
#            maybeDeferred(self.workBlock.AttemptRebuild).addCallback(_rebuild_finished)
#        def _rebuild_finished(someNewData):
#            # lg.out(8, '        _rebuild_finished on block %d, result is %s' % (self.currentBlockNumber, str(someNewData)))
#            if someNewData:
#                self.workBlock.WorkDoneReport()
#                self.blocksSucceed.append(self.currentBlockNumber)
#                data_sender.A('new-data')
#            self.workBlock = None
#            self.blockIndex -= 1
#            delay = 0
#            if someNewData:
#                delay = 0.5
#            reactor.callLater(delay, _prepare_one_block)
#        def _finish_all_blocks():
#            for blockNum in self.blocksSucceed:
#                self.workingBlocksQueue.remove(blockNum)
#            lg.out(8, 'backup_rebuilder.doAttemptRebuild._finish_all_blocks succeed:%s working:%s' % (str(self.blocksSucceed), str(self.workingBlocksQueue)))
#            result = len(self.blocksSucceed) > 0
#            self.blocksSucceed = []
#            self.automat('rebuilding-finished', result)  
#        reactor.callLater(0, _prepare_one_block)

    def doClearStoppedFlag(self, arg):
        ClearStoppedFlag()

    def _file_received(self, newpacket, state):
        import backup_matrix
        if state in ['in queue', 'shutdown', 'exist']:
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
        if os.path.exists(filename):
            lg.warn("rewriting existed file" + filename)
            try: 
                os.remove(filename)
            except:
                lg.exc()
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            try:
                bpio._dirs_make(dirname)
            except:
                lg.out(2, "backup_rebuilder._file_received ERROR can not create sub dir " + dirname)
                return 
        if not bpio.WriteFile(filename, newpacket.Payload):
            return
        backup_matrix.LocalFileReport(packetID)
        self.automat('inbox-data-packet', packetID)
        
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
    
    
