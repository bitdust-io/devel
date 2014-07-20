

import os

import lib.bpio
import lib.packetid
import lib.settings

import raid.read


def BuildFileName(backupID, blockNum, supplierNumber, dataOrParity):
    """
    Build a file name for that piece depend on given supplier.
    """
    return lib.packetid.MakePacketID(backupID, blockNum, supplierNumber, dataOrParity)

def BuildRaidFileName(backupID, blockNum, supplierNumber, dataOrParity):
    """
    Same but return an absolute path of that file.
    """
    return os.path.join(lib.settings.getLocalBackupsDir(), 
        BuildFileName(backupID, blockNum, supplierNumber, dataOrParity))

def rebuild(backupID, blockNum, eccMap, availableSuppliers, remoteMatrix, localMatrix):
    supplierCount = len(availableSuppliers)
    missingData = [0] * supplierCount
    missingParity = [0] * supplierCount
    reconstructedData = [0] * supplierCount
    reconstructedParity = [0] * supplierCount
    remoteData = list(remoteMatrix['D'])
    remoteParity = list(remoteMatrix['P'])
    localData = list(localMatrix['D'])
    localParity = list(localMatrix['P'])
    # This builds a list of missing pieces.
    # The file is missing if value in the corresponding cell 
    # in the "remote" matrix (see ``p2p.backup_matrix``) is -1 or 0 
    # but the supplier who must keep that file is online.
    # In other words, if supplier is online but do not have that piece - this piece is missing.
    for supplierNum in xrange(supplierCount):
        if availableSuppliers[supplierNum] == 0:
            continue
        # if remote Data file not exist and supplier is online
        # we mark it as missing and will try to rebuild this file and send to him
        if remoteData[supplierNum] != 1:
            # mark file as missing  
            missingData[supplierNum] = 1
        # same for Parity file
        if remoteParity[supplierNum] != 1:
            missingParity[supplierNum] = 1
    # This made an attempt to rebuild the missing pieces 
    # from pieces we have on hands. 
    # bpio.log(14, 'block_rebuilder.AttemptRebuild %s %d BEGIN' % (self.backupID, self.blockNum))
    newData = False
    madeProgress = True
    while madeProgress:
        madeProgress = False
        # will check all data packets we have 
        for supplierNum in xrange(supplierCount):
            dataFileName = BuildRaidFileName(backupID, blockNum, supplierNum, 'Data')
            # if we do not have this item on hands - we will reconstruct it from other items 
            if localData[supplierNum] == 0:
                parityNum, parityMap = eccMap.GetDataFixPath(localData, localParity, supplierNum)
                if parityNum != -1:
                    rebuildFileList = []
                    rebuildFileList.append(BuildRaidFileName(backupID, blockNum, parityNum, 'Parity'))
                    for supplierParity in parityMap:
                        if supplierParity != supplierNum:
                            filename = BuildRaidFileName(supplierParity, 'Data')
                            if os.path.isfile(filename):
                                rebuildFileList.append(filename)
                    # bpio.log(10, '    rebuilding file %s from %d files' % (os.path.basename(dataFileName), len(rebuildFileList)))
                    raid.read.RebuildOne(rebuildFileList, len(rebuildFileList), dataFileName)
                if os.path.exists(dataFileName):
                    localData[supplierNum] = 1
                    madeProgress = True
                    # bpio.log(10, '        Data file %s found after rebuilding for supplier %d' % (os.path.basename(dataFileName), supplierNum))
            # now we check again if we have the data on hand after rebuild at it is missing - send it
            # but also check to not duplicate sending to this man   
            # now sending is separated, see the file data_sender.py          
            if localData[supplierNum] == 1 and missingData[supplierNum] == 1: # and self.dataSent[supplierNum] == 0:
                # bpio.log(10, '            rebuilt a new Data for supplier %d' % supplierNum)
                newData = True
                reconstructedData[supplierNum] = 1
                # self.outstandingFilesList.append((dataFileName, self.BuildFileName(supplierNum, 'Data'), supplierNum))
                # self.dataSent[supplierNum] = 1
    # now with parities ...            
    for supplierNum in xrange(supplierCount):
        parityFileName = BuildRaidFileName(backupID, blockNum, supplierNum, 'Parity')
        if localParity[supplierNum] == 0:
            parityMap = eccMap.ParityToData[supplierNum]
            HaveAllData = True
            for segment in parityMap:
                if localData[segment] == 0:
                    HaveAllData = False
                    break
            if HaveAllData:
                rebuildFileList = []
                for supplierParity in parityMap:
                    filename = BuildRaidFileName(supplierParity, 'Data')  # ??? why not 'Parity'
                    if os.path.isfile(filename): 
                        rebuildFileList.append(filename)
                # bpio.log(10, '    rebuilding file %s from %d files' % (os.path.basename(parityFileName), len(rebuildFileList)))
                raid.read.RebuildOne(rebuildFileList, len(rebuildFileList), parityFileName)
                if os.path.exists(parityFileName):
                    # bpio.log(10, '        Parity file %s found after rebuilding for supplier %d' % (os.path.basename(parityFileName), supplierNum))
                    localParity[supplierNum] = 1
        # so we have the parity on hand and it is missing - send it
        if localParity[supplierNum] == 1 and missingParity[supplierNum] == 1: # and self.paritySent[supplierNum] == 0:
            # bpio.log(10, '            rebuilt a new Parity for supplier %d' % supplierNum)
            newData = True
            reconstructedParity[supplierNum] = 1
            # self.outstandingFilesList.append((parityFileName, self.BuildFileName(supplierNum, 'Parity'), supplierNum))
            # self.paritySent[supplierNum] = 1
    # bpio.log(14, 'block_rebuilder.AttemptRebuild END')
    return (newData, localData, localParity, reconstructedData, reconstructedParity)


