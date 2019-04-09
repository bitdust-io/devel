#!/usr/bin/env python
# rebuild.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (rebuild.py) is part of BitDust Software.
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


#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

import os
import traceback

#------------------------------------------------------------------------------

import raid.read
import raid.eccmap

#------------------------------------------------------------------------------

_Debug = False

#------------------------------------------------------------------------------

def rebuild(backupID, blockNum, eccMap, availableSuppliers, remoteMatrix, localMatrix, localBackupsDir):
    try:
        customer, _, localPath = backupID.rpartition(':')
        if '$' not in customer:
            customer = 'master$' + customer
        myeccmap = raid.eccmap.eccmap(eccMap)
        supplierCount = len(availableSuppliers)
        missingData = [0] * supplierCount
        missingParity = [0] * supplierCount
        reconstructedData = [0] * supplierCount
        reconstructedParity = [0] * supplierCount
        remoteData = list(remoteMatrix['D'])
        remoteParity = list(remoteMatrix['P'])
        localData = list(localMatrix['D'])
        localParity = list(localMatrix['P'])
    
        def _build_raid_file_name(supplierNumber, dataOrParity):
            return os.path.join(
                localBackupsDir,
                customer,
                localPath,
                str(blockNum) + '-' + str(supplierNumber) + '-' + dataOrParity)
    
        # This builds a list of missing pieces.
        # The file is missing if value in the corresponding cell
        # in the "remote" matrix (see ``p2p.backup_matrix``) is -1 or 0
        # but the supplier who must keep that file is online.
        # In other words, if supplier is online but do not have that piece - this piece is missing.
        for supplierNum in range(supplierCount):
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

        if _Debug:
            open('/tmp/raid.log', 'a').write(u'missingData=%r missingParity=%r\n' % (missingData, missingParity))
            open('/tmp/raid.log', 'a').write(u'localData=%r localParity=%r\n' % (localData, localParity))

        # This made an attempt to rebuild the missing pieces
        # from pieces we have on hands.
        # lg.out(14, 'block_rebuilder.AttemptRebuild %s %d BEGIN' % (self.backupID, self.blockNum))
        newData = False
        madeProgress = True
        while madeProgress:
            madeProgress = False
            # will check all data packets we have
            for supplierNum in range(supplierCount):
                dataFileName = _build_raid_file_name(supplierNum, 'Data')
                # if we do not have this item on hands - we will reconstruct it from other items
                if localData[supplierNum] == 0:
                    parityNum, parityMap = myeccmap.GetDataFixPath(localData, localParity, supplierNum)
                    if parityNum != -1:
                        rebuildFileList = []
                        rebuildFileList.append(_build_raid_file_name(parityNum, 'Parity'))
                        for supplierParity in parityMap:
                            if supplierParity != supplierNum:
                                filename = _build_raid_file_name(supplierParity, 'Data')
                                if os.path.isfile(filename):
                                    rebuildFileList.append(filename)
                        # lg.out(10, '    rebuilding file %s from %d files' % (os.path.basename(dataFileName), len(rebuildFileList)))
                        raid.read.RebuildOne(rebuildFileList, len(rebuildFileList), dataFileName)
                    if os.path.exists(dataFileName):
                        localData[supplierNum] = 1
                        madeProgress = True
                        # lg.out(10, '        Data file %s found after rebuilding for supplier %d' % (os.path.basename(dataFileName), supplierNum))
                # now we check again if we have the data on hand after rebuild at it is missing - send it
                # but also check to not duplicate sending to this man
                # now sending is separated, see the file data_sender.py
                if localData[supplierNum] == 1 and missingData[supplierNum] == 1:  # and self.dataSent[supplierNum] == 0:
                    # lg.out(10, '            rebuilt a new Data for supplier %d' % supplierNum)
                    newData = True
                    reconstructedData[supplierNum] = 1
                    # self.outstandingFilesList.append((dataFileName, self.BuildFileName(supplierNum, 'Data'), supplierNum))
                    # self.dataSent[supplierNum] = 1
        # now with parities ...
        for supplierNum in range(supplierCount):
            parityFileName = _build_raid_file_name(supplierNum, 'Parity')
            if localParity[supplierNum] == 0:
                parityMap = myeccmap.ParityToData[supplierNum]
                HaveAllData = True
                for segment in parityMap:
                    if localData[segment] == 0:
                        HaveAllData = False
                        break
                if HaveAllData:
                    rebuildFileList = []
                    for supplierParity in parityMap:
                        filename = _build_raid_file_name(supplierParity, 'Data')  # ??? why not 'Parity'
                        if os.path.isfile(filename):
                            rebuildFileList.append(filename)
                    # lg.out(10, '    rebuilding file %s from %d files' % (os.path.basename(parityFileName), len(rebuildFileList)))
                    raid.read.RebuildOne(rebuildFileList, len(rebuildFileList), parityFileName)
                    if os.path.exists(parityFileName):
                        # lg.out(10, '        Parity file %s found after rebuilding for supplier %d' % (os.path.basename(parityFileName), supplierNum))
                        localParity[supplierNum] = 1
            # so we have the parity on hand and it is missing - send it
            if localParity[supplierNum] == 1 and missingParity[supplierNum] == 1:  # and self.paritySent[supplierNum] == 0:
                # lg.out(10, '            rebuilt a new Parity for supplier %d' % supplierNum)
                newData = True
                reconstructedParity[supplierNum] = 1
                # self.outstandingFilesList.append((parityFileName, self.BuildFileName(supplierNum, 'Parity'), supplierNum))
                # self.paritySent[supplierNum] = 1
        # lg.out(14, 'block_rebuilder.AttemptRebuild END')
        return (newData, localData, localParity, reconstructedData, reconstructedParity, )

    except:
        # lg.exc()
        traceback.print_exc()
        return None
