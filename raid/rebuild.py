

import lib.io


def BuildRaidFileName():
    pass

def attempt_rebuild_block(supplierCount):
    try:
        """
        This made an attempt to rebuild the missing pieces from pieces we have on hands. 
        """
        # io.log(14, 'block_rebuilder.AttemptRebuild %s %d BEGIN' % (self.backupID, self.blockNum))
        newData = False
        madeProgress = True
        while madeProgress:
            madeProgress = False
#            # if number of suppliers were changed - stop immediately 
#            if contacts.numSuppliers() != self.supplierCount:
#                io.log(10, 'block_rebuilder.AttemptRebuild END - number of suppliers were changed')
#                return False
            # will check all data packets we have 
            for supplierNum in xrange(supplierCount):
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
                        io.log(10, '    rebuilding file %s from %d files' % (os.path.basename(dataFileName), len(rebuildFileList)))
                        
                        
                        # TODO - send to raid_worker
                        # need to make block_rebuilder state machine here
                        raid.read.RebuildOne(rebuildFileList, len(rebuildFileList), dataFileName)
                        
                        
                        
        
                    if os.path.exists(dataFileName):
                        self.localData[supplierNum] = 1
                        madeProgress = True
                        io.log(10, '        Data file %s found after rebuilding for supplier %d' % (os.path.basename(dataFileName), supplierNum))
                # now we check again if we have the data on hand after rebuild at it is missing - send it
                # but also check to not duplicate sending to this man   
                # now sending is separated, see the file data_sender.py          
                if self.localData[supplierNum] == 1 and self.missingData[supplierNum] == 1: # and self.dataSent[supplierNum] == 0:
                    io.log(10, '            rebuilt a new Data for supplier %d' % supplierNum)
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
                    io.log(10, '    rebuilding file %s from %d files' % (os.path.basename(parityFileName), len(rebuildFileList)))
                    
                    
                    
                    raid.read.RebuildOne(rebuildFileList, len(rebuildFileList), parityFileName)
                    
                    
                    
                    if os.path.exists(parityFileName):
                        io.log(10, '        Parity file %s found after rebuilding for supplier %d' % (os.path.basename(parityFileName), supplierNum))
                        self.localParity[supplierNum] = 1
            # so we have the parity on hand and it is missing - send it
            if self.localParity[supplierNum] == 1 and self.missingParity[supplierNum] == 1: # and self.paritySent[supplierNum] == 0:
                io.log(10, '            rebuilt a new Parity for supplier %d' % supplierNum)
                newData = True
                self.reconstructedParity[supplierNum] = 1
                # self.outstandingFilesList.append((parityFileName, self.BuildFileName(supplierNum, 'Parity'), supplierNum))
                # self.paritySent[supplierNum] = 1
        io.log(14, 'block_rebuilder.AttemptRebuild END')
        return newData
    except:
        lib.io.exception()
        return None
