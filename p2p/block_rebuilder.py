#!/usr/bin/python
#block_rebuilder.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: block_rebuilder

A low level code to rebuild a single block of data for particular backup.

The data block is divided into pieces using a RAID array, 
and the pieces are distributed and transmitted to the suppliers.

Due to redundancy when creating backup you can recover lost blocks from the existing - 
this is called rebuilding data.

Rebuilding each block of data is as follows:
    * Determination of the lost pieces of data
    * Request the missing pieces from suppliers
    * Start the process of rebuilding the data block
    * Newly created pieces are sent to suppliers
    * Waiting for the delivery notification from each supplier
"""

import os

import lib.bpio as bpio
import lib.misc as misc
import lib.settings as settings
import lib.contacts as contacts
import lib.packetid as packetid

# import raid.raid_worker as raid_worker
import raid.read

import backup_matrix
# import raidread

#------------------------------------------------------------------------------ 

class BlockRebuilder():
    """
    This object is created in the backup_rebuilder() to work on single block of given backup.
    """
    def __init__(self,  
                 eccMap, 
                 backupID, 
                 blockNum,  
                 remoteData, 
                 remoteParity,
                 localData, 
                 localParity, 
                 creatorId = None, 
                 ownerId = None):
        self.eccMap = eccMap
        self.backupID = backupID
        self.blockNum = blockNum
        self.supplierCount = contacts.numSuppliers()
        self.remoteData = remoteData
        self.remoteParity = remoteParity
        self.localData = localData
        self.localParity = localParity
        self.creatorId = creatorId
        self.ownerId = ownerId
        # at some point we may be dealing with when we're scrubbers
        if self.creatorId == None:
            self.creatorId = misc.getLocalID()
        if self.ownerId == None:
            self.ownerId = misc.getLocalID()
        # this files we want to rebuild
        # need to identify which files to work on
        self.missingData = [0] * self.supplierCount
        self.missingParity = [0] * self.supplierCount
        # array to remember requested files
        self.reconstructedData = [0] * self.supplierCount
        self.reconstructedParity = [0] * self.supplierCount

    def IdentifyMissing(self):
        """
        This builds a list of missing pieces.
        The file is missing if value in the corresponding cell 
        in the "remote" matrix (see ``p2p.backup_matrix``) is -1 or 0 
        but the supplier who must keep that file is online.
        In other words, if supplier is online but do not have that piece - this piece is missing.
        """
        self.availableSuppliers = backup_matrix.GetActiveArray()
        for supplierNum in xrange(self.supplierCount):
            if self.availableSuppliers[supplierNum] == 0:
                continue
            # if remote Data file not exist and supplier is online
            # we mark it as missing and will try to rebuild this file and send to him
            if self.remoteData[supplierNum] != 1:
                # mark file as missing  
                self.missingData[supplierNum] = 1
            # same for Parity file
            if self.remoteParity[supplierNum] != 1:
                self.missingParity[supplierNum] = 1

    def IsMissingFilesOnHand(self):
        """
        If we have all missing pieces on hands - just need to transfer them, not need to rebuild anything.
        """
        for supplierNum in xrange(self.supplierCount):
            # if supplier do not have the Data but is on line 
            if self.missingData[supplierNum] == 1:
                # ... and we also do not have the Data 
                if self.localData[supplierNum] != 1:
                    # return False - will need request the file   
                    return False
            # same for Parity                
            if self.missingParity[supplierNum] == 1:
                if self.localParity[supplierNum] != 1:
                    return False
        return True

    def BuildFileName(self, supplierNumber, dataOrParity):
        """
        Build a file name for that piece depend on given supplier.
        """
        return packetid.MakePacketID(self.backupID, self.blockNum, supplierNumber, dataOrParity)

    def BuildRaidFileName(self, supplierNumber, dataOrParity):
        """
        Same but return an absolute path of that file.
        """
        return os.path.join(settings.getLocalBackupsDir(), self.BuildFileName(supplierNumber, dataOrParity))

    def HaveAllData(self, parityMap):
        """
        Return True if you have on hands all needed pieces to rebuild the block.
        """
        for segment in parityMap:
            if self.localData[segment] == 0:
                return False
        return True

    def AttemptRebuild(self):
        return False
    

        """
        This made an attempt to rebuild the missing pieces from pieces we have on hands. 
        """
        bpio.log(14, 'block_rebuilder.AttemptRebuild %s %d BEGIN' % (self.backupID, self.blockNum))
        newData = False
        madeProgress = True
        while madeProgress:
            madeProgress = False
            # if number of suppliers were changed - stop immediately 
            if contacts.numSuppliers() != self.supplierCount:
                bpio.log(10, 'block_rebuilder.AttemptRebuild END - number of suppliers were changed')
                return False
            # will check all data packets we have 
            for supplierNum in xrange(self.supplierCount):
                dataFileName = self.BuildRaidFileName(supplierNum, 'Data')
                # if we do not have this item on hands - we will reconstruct it from other items 
                if self.localData[supplierNum] == 0:
                    parityNum, parityMap = self.eccMap.GetDataFixPath(self.localData, self.localParity, supplierNum)
                    if parityNum != -1:
                        rebuildFileList = []
                        rebuildFileList.append(self.BuildRaidFileName(parityNum, 'Parity'))
                        for supplierParity in parityMap:
                            if supplierParity != supplierNum:
                                filename = self.BuildRaidFileName(supplierParity, 'Data')
                                if os.path.isfile(filename):
                                    rebuildFileList.append(filename)
                        bpio.log(10, '    rebuilding file %s from %d files' % (os.path.basename(dataFileName), len(rebuildFileList)))
                        
                        
                        # TODO - send to raid_worker
                        # need to make block_rebuilder state machine here
                        raid.read.RebuildOne(rebuildFileList, len(rebuildFileList), dataFileName)
                        
                        
                        
        
                    if os.path.exists(dataFileName):
                        self.localData[supplierNum] = 1
                        madeProgress = True
                        bpio.log(10, '        Data file %s found after rebuilding for supplier %d' % (os.path.basename(dataFileName), supplierNum))
                # now we check again if we have the data on hand after rebuild at it is missing - send it
                # but also check to not duplicate sending to this man   
                # now sending is separated, see the file data_sender.py          
                if self.localData[supplierNum] == 1 and self.missingData[supplierNum] == 1: # and self.dataSent[supplierNum] == 0:
                    bpio.log(10, '            rebuilt a new Data for supplier %d' % supplierNum)
                    newData = True
                    self.reconstructedData[supplierNum] = 1
                    # self.outstandingFilesList.append((dataFileName, self.BuildFileName(supplierNum, 'Data'), supplierNum))
                    # self.dataSent[supplierNum] = 1
        # now with parities ...            
        for supplierNum in xrange(self.supplierCount):
            parityFileName = self.BuildRaidFileName(supplierNum, 'Parity')
            if self.localParity[supplierNum] == 0:
                parityMap = self.eccMap.ParityToData[supplierNum]
                if self.HaveAllData(parityMap):
                    rebuildFileList = []
                    for supplierParity in parityMap:
                        filename = self.BuildRaidFileName(supplierParity, 'Data')  # ??? why not 'Parity'
                        if os.path.isfile(filename): 
                            rebuildFileList.append(filename)
                    bpio.log(10, '    rebuilding file %s from %d files' % (os.path.basename(parityFileName), len(rebuildFileList)))
                    
                    
                    
                    raid.read.RebuildOne(rebuildFileList, len(rebuildFileList), parityFileName)
                    
                    
                    
                    if os.path.exists(parityFileName):
                        bpio.log(10, '        Parity file %s found after rebuilding for supplier %d' % (os.path.basename(parityFileName), supplierNum))
                        self.localParity[supplierNum] = 1
            # so we have the parity on hand and it is missing - send it
            if self.localParity[supplierNum] == 1 and self.missingParity[supplierNum] == 1: # and self.paritySent[supplierNum] == 0:
                bpio.log(10, '            rebuilt a new Parity for supplier %d' % supplierNum)
                newData = True
                self.reconstructedParity[supplierNum] = 1
                # self.outstandingFilesList.append((parityFileName, self.BuildFileName(supplierNum, 'Parity'), supplierNum))
                # self.paritySent[supplierNum] = 1
        bpio.log(14, 'block_rebuilder.AttemptRebuild END')
        return newData

    def WorkDoneReport(self):
        """
        Notify to ``backup_matrix`` module about rebuilding results.
        """
        for supplierNum in xrange(self.supplierCount):
            if self.localData[supplierNum] == 1 and self.reconstructedData[supplierNum] == 1:
                backup_matrix.LocalFileReport(None, self.backupID, self.blockNum, supplierNum, 'Data')
            if self.localParity[supplierNum] == 1 and self.reconstructedParity[supplierNum] == 1:
                backup_matrix.LocalFileReport(None, self.backupID, self.blockNum, supplierNum, 'Parity')
                    
                    
