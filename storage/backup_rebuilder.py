#!/usr/bin/python
# backup_rebuilder.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (backup_rebuilder.py) is part of BitDust Software.
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
.. module:: backup_rebuilder.

.. raw:: html

    <a href="https://bitdust.io/automats/backup_rebuilder/backup_rebuilder.png" target="_blank">
    <img src="https://bitdust.io/automats/backup_rebuilder/backup_rebuilder.png" style="max-width:100%;">
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
    * :red:`found-missing`
    * :red:`inbox-data-packet`
    * :red:`init`
    * :red:`instant`
    * :red:`no-requests`
    * :red:`rebuilding-finished`
    * :red:`requests-sent`
    * :red:`start`
    * :red:`timer-1sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
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
from userid import global_id

from raid import eccmap
from raid import raid_worker

from services import driver

#------------------------------------------------------------------------------

_BackupRebuilder = None
_StoppedFlag = True
_BackupIDsQueue = []
_BlockRebuildersQueue = []

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _BackupRebuilder
    if _BackupRebuilder is None:
        _BackupRebuilder = BackupRebuilder(
            name='backup_rebuilder',
            state='STOPPED',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _BackupRebuilder.automat(event, *args, **kwargs)
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
        'timer-1sec': (1.0, ['REQUEST']),
    }

    def init(self):
        """
        Initialize needed variables.
        """
        self.currentBackupID = None             # currently working on this backup
        self.currentCustomerIDURL = None        # stored by this customer
        # list of missing blocks we work on for current backup
        self.workingBlocksQueue = []
        self.backupsWasRebuilt = []
        self.missingPackets = 0
        self.log_transitions = _Debug

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        This method is called every time when my state is changed.

        Need to notify backup_monitor() machine about my new state.
        """
        # global_state.set_global_state('REBUILD ' + newstate)
        if newstate in ['NEXT_BACKUP', 'REQUEST', 'REBUILDING', ]:
            self.automat('instant')
        elif newstate == 'DONE' or newstate == 'STOPPED':
            if driver.is_on('service_backups'):
                from storage import backup_monitor
                backup_monitor.A('backup_rebuilder.state', newstate)

    def A(self, event, *args, **kwargs):
        #---REQUEST---
        if self.state == 'REQUEST':
            if ( event == 'timer-1sec' or event == 'inbox-data-packet' or event == 'requests-sent' or event == 'found-missing' ) and self.isChanceToRebuild(*args, **kwargs) and not self.isStopped(*args, **kwargs):
                self.state = 'REBUILDING'
                self.doAttemptRebuild(*args, **kwargs)
            elif ( ( event == 'found-missing' and not self.isChanceToRebuild(*args, **kwargs) ) or ( event == 'no-requests' or ( ( event == 'timer-1sec' or event == 'inbox-data-packet' ) and self.isRequestQueueEmpty(*args, **kwargs) and not self.isMissingPackets(*args, **kwargs) ) ) ) and not self.isStopped(*args, **kwargs):
                self.state = 'DONE'
                self.doCloseThisBackup(*args, **kwargs)
            elif ( event == 'instant' or event == 'timer-1sec' or event == 'requests-sent' or event == 'no-requests' or event == 'found-missing' ) and self.isStopped(*args, **kwargs):
                self.state = 'STOPPED'
                self.doCloseThisBackup(*args, **kwargs)
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'init':
                self.doClearStoppedFlag(*args, **kwargs)
            elif event == 'start':
                self.state = 'NEXT_BACKUP'
                self.doClearStoppedFlag(*args, **kwargs)
        #---NEXT_BACKUP---
        elif self.state == 'NEXT_BACKUP':
            if event == 'instant' and not self.isMoreBackups(*args, **kwargs) and not self.isStopped(*args, **kwargs):
                self.state = 'DONE'
            elif event == 'instant' and self.isStopped(*args, **kwargs):
                self.state = 'STOPPED'
            elif event == 'instant' and not self.isStopped(*args, **kwargs) and self.isMoreBackups(*args, **kwargs):
                self.state = 'PREPARE'
                self.doOpenNextBackup(*args, **kwargs)
                self.doScanBrokenBlocks(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            if event == 'start' or ( event == 'instant' and self.isSomeRebuilts(*args, **kwargs) ):
                self.state = 'NEXT_BACKUP'
                self.doClearStoppedFlag(*args, **kwargs)
        #---PREPARE---
        elif self.state == 'PREPARE':
            if event == 'backup-ready' and ( not self.isMoreBackups(*args, **kwargs) and not self.isMoreBlocks(*args, **kwargs) ):
                self.state = 'DONE'
                self.doCloseThisBackup(*args, **kwargs)
            elif ( event == 'instant' or event == 'backup-ready' ) and self.isStopped(*args, **kwargs):
                self.state = 'STOPPED'
                self.doCloseThisBackup(*args, **kwargs)
            elif ( event == 'instant' or event == 'backup-ready' ) and not self.isStopped(*args, **kwargs) and self.isMoreBlocks(*args, **kwargs):
                self.state = 'REQUEST'
                self.doRequestAvailablePieces(*args, **kwargs)
            elif event == 'backup-ready' and not self.isStopped(*args, **kwargs) and not self.isMoreBlocks(*args, **kwargs) and self.isMoreBackups(*args, **kwargs):
                self.state = 'NEXT_BACKUP'
                self.doCloseThisBackup(*args, **kwargs)
        #---REBUILDING---
        elif self.state == 'REBUILDING':
            if event == 'rebuilding-finished' and not self.isStopped(*args, **kwargs) and not self.isMoreBlocks(*args, **kwargs):
                self.state = 'PREPARE'
                self.doScanBrokenBlocks(*args, **kwargs)
            elif ( event == 'instant' or event == 'rebuilding-finished' ) and self.isStopped(*args, **kwargs):
                self.state = 'STOPPED'
                self.doCloseThisBackup(*args, **kwargs)
                self.doKillRebuilders(*args, **kwargs)
            elif event == 'rebuilding-finished' and not self.isStopped(*args, **kwargs) and self.isMoreBlocks(*args, **kwargs):
                self.state = 'REQUEST'
                self.doRequestAvailablePieces(*args, **kwargs)
        return None

    def isSomeRebuilts(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.backupsWasRebuilt) > 0

    def isMoreBackups(self, *args, **kwargs):
        """
        Condition method.
        """
        global _BackupIDsQueue
        return len(_BackupIDsQueue) > 0

    def isMoreBlocks(self, *args, **kwargs):
        """
        Condition method.
        """
        # because started from 0,  -1 means not found
        return len(self.workingBlocksQueue) > 0

    def isMissingPackets(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.missingPackets > 0

    def isStopped(self, *args, **kwargs):
        """
        Condition method.
        """
        return ReadStoppedFlag()  # :-)

    def isChanceToRebuild(self, *args, **kwargs):
        """
        Condition method.
        """
        from storage import backup_matrix
        # supplierSet = backup_matrix.suppliers_set()
        # start checking in reverse order, see below for explanation
        for blockIndex in range(len(self.workingBlocksQueue) - 1, -1, -1):
            blockNumber = self.workingBlocksQueue[blockIndex]
            if eccmap.Current().CanMakeProgress(
                backup_matrix.GetLocalDataArray(
                    self.currentBackupID,
                    blockNumber),
                backup_matrix.GetLocalParityArray(
                    self.currentBackupID,
                    blockNumber)):
                return True
        return False

    def isRequestQueueEmpty(self, *args, **kwargs):
        """
        Condition method.
        """
        from customer import io_throttle
        # supplierSet = backup_matrix.suppliers_set()
        for supplierNum in range(contactsdb.num_suppliers()):
            supplierID = contactsdb.supplier(supplierNum)
            if io_throttle.HasBackupIDInRequestQueue(
                    supplierID, self.currentBackupID):
                return False
        return True

#     def isAnyDataReceiving(self, *args, **kwargs):
#         """
#         Condition method.
#         """
#         from transport import gateway
#         wanted_protos = gateway.list_active_transports()
#         for proto in wanted_protos:
#             for stream in gateway.list_active_streams(proto):
#                 if proto == 'tcp' and hasattr(stream, 'bytes_received'):
#                     return True
#                 elif proto == 'udp' and hasattr(stream.consumer, 'bytes_received'):
#                     return True
#         return False

    def doOpenNextBackup(self, *args, **kwargs):
        """
        Action method.
        """
        global _BackupIDsQueue
        # check it, may be we already fixed all things
        if len(_BackupIDsQueue) == 0:
            self.automat('backup-ready')
            if _Debug:
                lg.out(_DebugLevel, 'backup_rebuilder.doOpenNextBackup SKIP, queue is empty')
            return
        # take a first backup from queue to work on it
        self.currentBackupID = _BackupIDsQueue.pop(0)
        self.currentCustomerIDURL = packetid.CustomerIDURL(self.currentBackupID)
        if _Debug:
            lg.out(_DebugLevel, 'backup_rebuilder.doOpenNextBackup %s started, queue length: %d' % (
                self.currentBackupID, len(_BackupIDsQueue)))

    def doCloseThisBackup(self, *args, **kwargs):
        """
        Action method.
        """
        self.workingBlocksQueue = []
        if _Debug:
            lg.out(_DebugLevel, 'backup_rebuilder.doCloseThisBackup %s about to finish, queue length: %d' % (
                self.currentBackupID, len(_BackupIDsQueue)))
        if self.currentBackupID:
            # clear requesting queue from previous task
            from customer import io_throttle
            io_throttle.DeleteBackupRequests(self.currentBackupID)
        self.currentBackupID = None
        self.currentCustomerIDURL = None

    def doScanBrokenBlocks(self, *args, **kwargs):
        """
        Action method.
        """
        # if remote data structure is not exist for this backup - create it
        # this mean this is only local backup!
        from storage import backup_matrix
        if self.currentBackupID not in backup_matrix.remote_files():
            backup_matrix.remote_files()[self.currentBackupID] = {}
            # we create empty remote info for every local block
            # range(0) should return []
            for blockNum in range(
                backup_matrix.local_max_block_numbers().get(
                    self.currentBackupID, -1) + 1):
                backup_matrix.remote_files()[
                    self.currentBackupID][blockNum] = {
                    'D': [0] * contactsdb.num_suppliers(),
                    'P': [0] * contactsdb.num_suppliers()}
        # detect missing blocks from remote info
        self.workingBlocksQueue = backup_matrix.ScanMissingBlocks(self.currentBackupID)
        # find the correct max block number for this backup
        # we can have remote and local files
        # will take biggest block number from both
        backupMaxBlock = max(
            backup_matrix.remote_max_block_numbers().get(
                self.currentBackupID, -1), backup_matrix.local_max_block_numbers().get(
                self.currentBackupID, -1))
        # now need to remember this biggest block number
        # remote info may have less blocks - need to create empty info for
        # missing blocks
        for blockNum in range(backupMaxBlock + 1):
            if blockNum in backup_matrix.remote_files()[self.currentBackupID]:
                continue
            backup_matrix.remote_files()[self.currentBackupID][blockNum] = {
                'D': [0] * contactsdb.num_suppliers(),
                'P': [0] * contactsdb.num_suppliers()}
        # clear requesting queue, remove old packets for this backup, we will
        # send them again
        from customer import io_throttle
        io_throttle.DeleteBackupRequests(self.currentBackupID)
        lg.out(8, 'backup_rebuilder.doScanBrokenBlocks for %s : %s' % (
            self.currentBackupID, str(self.workingBlocksQueue)))
        self.automat('backup-ready')

    def doRequestAvailablePieces(self, *args, **kwargs):
        """
        Action method.
        """
        self._request_files()

    def doAttemptRebuild(self, *args, **kwargs):
        """
        Action method.
        """
        self.blocksSucceed = []
        if len(self.workingBlocksQueue) == 0:
            self.automat('rebuilding-finished')
            return
        # let's rebuild the backup blocks in reverse order, take last blocks first ...
        # in such way we can propagate how big is the whole backup as soon as possible!
        # remote machine can multiply [file size] * [block number]
        # and calculate the whole size to be received ... smart!
        # ... remote supplier should not use last file to calculate
        self.blockIndex = len(self.workingBlocksQueue) - 1
        reactor.callLater(0, self._start_one_block)  # @UndefinedVariable

    def doKillRebuilders(self, *args, **kwargs):
        """
        Action method.
        """
        # TODO: make sure to not kill workers for backup jobs....
        raid_worker.A('shutdown')

    def doClearStoppedFlag(self, *args, **kwargs):
        """
        Action method.
        """
        self.backupsWasRebuilt = []
        ClearStoppedFlag()

    #-------------------------------------------------------------------------

    def _request_files(self):
        from storage import backup_matrix
        from customer import io_throttle
        from customer import data_sender
        self.missingPackets = 0
        # here we want to request some packets before we start working to
        # rebuild the missed blocks
        availableSuppliers = backup_matrix.GetActiveArray(customer_idurl=self.currentCustomerIDURL)
        # remember how many requests we did on this iteration
        total_requests_count = 0
        # at the moment I do download everything I have available and needed
        if '' in contactsdb.suppliers(customer_idurl=self.currentCustomerIDURL) or b'' in contactsdb.suppliers(customer_idurl=self.currentCustomerIDURL):
            lg.out(8, 'backup_rebuilder._request_files SKIP - empty supplier')
            self.automat('no-requests')
            return
        for supplierNum in range(contactsdb.num_suppliers(customer_idurl=self.currentCustomerIDURL)):
            supplierID = contactsdb.supplier(supplierNum, customer_idurl=self.currentCustomerIDURL)
            if not supplierID:
                continue
            requests_count = 0
            # we do requests in reverse order because we start rebuilding from
            # the last block
            for blockIndex in range(len(self.workingBlocksQueue) - 1, -1, -1):
                blockNum = self.workingBlocksQueue[blockIndex]
                # do not keep too many requests in the queue
                if io_throttle.GetRequestQueueLength(supplierID) >= 16:
                    break
                # also don't do too many requests at once
                if requests_count > 16:
                    break
                remoteData = backup_matrix.GetRemoteDataArray(
                    self.currentBackupID, blockNum)
                remoteParity = backup_matrix.GetRemoteParityArray(
                    self.currentBackupID, blockNum)
                localData = backup_matrix.GetLocalDataArray(
                    self.currentBackupID, blockNum)
                localParity = backup_matrix.GetLocalParityArray(
                    self.currentBackupID, blockNum)
                if supplierNum >= len(remoteData) or supplierNum >= len(remoteParity):
                    break
                if supplierNum >= len(localData) or supplierNum >= len(localParity):
                    break
                # if remote Data exist and is available because supplier is on-line,
                # but we do not have it on hand - do request
                if localData[supplierNum] == 0:
                    PacketID = packetid.MakePacketID(
                        self.currentBackupID, blockNum, supplierNum, 'Data')
                    if remoteData[supplierNum] == 1:
                        if availableSuppliers[supplierNum]:
                            # if supplier is not alive - we can't request from him
                            if not io_throttle.HasPacketInRequestQueue(supplierID, PacketID):
                                customer, remotePath = packetid.SplitPacketID(PacketID)
                                filename = os.path.join(
                                    settings.getLocalBackupsDir(),
                                    customer,
                                    remotePath,
                                )
                                if not os.path.exists(filename):
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
                else:
                    # but if local Data already exists, but was not sent - do it now
                    if remoteData[supplierNum] != 1:
                        data_sender.A('new-data')
                # same for Parity
                if localParity[supplierNum] == 0:
                    PacketID = packetid.MakePacketID(
                        self.currentBackupID, blockNum, supplierNum, 'Parity')
                    if remoteParity[supplierNum] == 1:
                        if availableSuppliers[supplierNum]:
                            if not io_throttle.HasPacketInRequestQueue(
                                    supplierID, PacketID):
                                customer, remotePath = packetid.SplitPacketID(PacketID)
                                filename = os.path.join(
                                    settings.getLocalBackupsDir(),
                                    customer,
                                    remotePath,
                                )
                                if not os.path.exists(filename):
                                    if io_throttle.QueueRequestFile(
                                        self._file_received,
                                        my_id.getLocalID(),
                                        PacketID,
                                        my_id.getLocalID(),
                                        supplierID,
                                    ):
                                        requests_count += 1
                    else:
                        self.missingPackets += 1
                else:
                    # but if local Parity already exists, but was not sent - do it now
                    if remoteParity[supplierNum] != 1:
                        data_sender.A('new-data')
            total_requests_count += requests_count
        if total_requests_count > 0:
            lg.out(8, 'backup_rebuilder._request_files : %d chunks requested' % total_requests_count)
            self.automat('requests-sent', total_requests_count)
        else:
            if self.missingPackets:
                lg.out(8, 'backup_rebuilder._request_files : found %d missing packets' % self.missingPackets)
                self.automat('found-missing')
            else:
                lg.out(8, 'backup_rebuilder._request_files : nothing was requested')
                self.automat('no-requests')

    def _file_received(self, newpacket, state):
        if state in ['in queue', 'shutdown', 'exist', 'failed']:
            return
        if state != 'received':
            lg.warn("incorrect state [%s] for packet %s" % (str(state), str(newpacket)))
            return
        if not newpacket.Valid():
            # TODO: if we didn't get a valid packet ... re-request it or delete
            # it?
            lg.warn("%s is not a valid packet: %r" % (newpacket.PacketID, newpacket))
            return
        # packetID = newpacket.PacketID
        packetID = global_id.CanonicalID(newpacket.PacketID)
        customer, remotePath = packetid.SplitPacketID(packetID)
        filename = os.path.join(settings.getLocalBackupsDir(), customer, remotePath)
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
                lg.out(2, "backup_rebuilder._file_received ERROR can not create sub dir: " + dirname)
                return
        if not bpio.WriteBinaryFile(filename, newpacket.Payload):
            lg.out(2, "backup_rebuilder._file_received ERROR writing " + filename)
            return
        from storage import backup_matrix
        backup_matrix.LocalFileReport(packetID)
        lg.out(10, "backup_rebuilder._file_received and wrote to " + filename)
        self.automat('inbox-data-packet', packetID)

    def _start_one_block(self):
        from storage import backup_matrix
        if self.blockIndex < 0:
            lg.out(10, 'backup_rebuilder._start_one_block finish all blocks blockIndex=%d' % self.blockIndex)
            reactor.callLater(0, self._finish_rebuilding)  # @UndefinedVariable
            return
        BlockNumber = self.workingBlocksQueue[self.blockIndex]
        lg.out(10, 'backup_rebuilder._start_one_block %d to rebuild, blockIndex=%d, other blocks: %s' % (
            (BlockNumber, self.blockIndex, str(self.workingBlocksQueue))))
        task_params = (
            self.currentBackupID,
            BlockNumber,
            eccmap.Current().name,
            backup_matrix.GetActiveArray(),
            backup_matrix.GetRemoteMatrix(self.currentBackupID, BlockNumber),
            backup_matrix.GetLocalMatrix(self.currentBackupID, BlockNumber),
            settings.getLocalBackupsDir(),
        )
        raid_worker.add_task('rebuild', task_params, lambda cmd, params, result: self._block_finished(result, params))

    def _block_finished(self, result, params):
        if not result:
            lg.out(10, 'backup_rebuilder._block_finished FAILED, blockIndex=%d' % self.blockIndex)
            reactor.callLater(0, self._finish_rebuilding)  # @UndefinedVariable
            return
        try:
            newData, localData, localParity, reconstructedData, reconstructedParity = result
            _backupID = params[0]
            _blockNumber = params[1]
        except:
            lg.exc()
            reactor.callLater(0, self._finish_rebuilding)  # @UndefinedVariable
            return
        lg.out(10, 'backup_rebuilder._block_finished   backupID=%r  blockNumber=%r  newData=%r' % (
            _backupID, _blockNumber, newData))
        lg.out(10, '        localData=%r  localParity=%r' % (localData, localParity))
        err = False
        if newData:
            from storage import backup_matrix
            from customer import data_sender
            count = 0
            customer_idurl = packetid.CustomerIDURL(_backupID)
            for supplierNum in range(contactsdb.num_suppliers(customer_idurl=customer_idurl)):
                try:
                    localData[supplierNum]
                    localParity[supplierNum]
                    reconstructedData[supplierNum]
                    reconstructedParity[supplierNum]
                except:
                    err = True
                    lg.err('invalid result from the task: %s' % repr(params))
                    lg.out(10, 'result is %s' % repr(result))
                    break
                if localData[supplierNum] == 1 and reconstructedData[supplierNum] == 1:
                    backup_matrix.LocalFileReport(None, _backupID, _blockNumber, supplierNum, 'Data')
                    count += 1
                if localParity[supplierNum] == 1 and reconstructedParity[supplierNum] == 1:
                    backup_matrix.LocalFileReport(None, _backupID, _blockNumber, supplierNum, 'Parity')
                    count += 1
            if err:
                lg.out(10, 'found ERROR! seems suppliers were changed, stop rebuilding')
                reactor.callLater(0, self._finish_rebuilding)  # @UndefinedVariable
                return
            self.blocksSucceed.append(_blockNumber)
            data_sender.A('new-data')
            lg.out(10, '        !!!!!! %d NEW DATA segments reconstructed, blockIndex=%d' % (
                count, self.blockIndex))
        else:
            lg.out(10, '        NO CHANGES, blockIndex=%d' % self.blockIndex)
        self.blockIndex -= 1
        reactor.callLater(0, self._start_one_block)  # @UndefinedVariable

    def _finish_rebuilding(self):
        for blockNum in self.blocksSucceed:
            if blockNum in self.workingBlocksQueue:
                self.workingBlocksQueue.remove(blockNum)
            else:
                lg.warn('block %d not present in workingBlocksQueue')
        lg.out(10, 'backup_rebuilder._finish_rebuilding succeed:%s working:%s' % (
            str(self.blocksSucceed), str(self.workingBlocksQueue)))
        if len(self.blocksSucceed):
            self.backupsWasRebuilt.append(self.currentBackupID)
        self.blocksSucceed = []
        self.automat('rebuilding-finished')


#------------------------------------------------------------------------------

def AddBackupsToWork(backupIDs):
    """
    Put backups to the working queue, ``backupIDs`` is a list of backup IDs.

    They will be reconstructed one by one.
    """
    global _BackupIDsQueue
    _BackupIDsQueue.extend(backupIDs)
    if _Debug:
        lg.out(_DebugLevel, 'backup_rebuilder.AddBackupsToWork %s added, queue length: %d' % (backupIDs, len(_BackupIDsQueue)))


def RemoveBackupToWork(backupID):
    """
    Remove single backup from the working queue.
    """
    global _BackupIDsQueue
    if backupID in _BackupIDsQueue:
        _BackupIDsQueue.remove(backupID)
        if _Debug:
            lg.out(_DebugLevel, 'backup_rebuilder.RemoveBackupToWork %s removed, queue length: %d' % (
                backupID, len(_BackupIDsQueue)))
    else:
        if _Debug:
            lg.out(_DebugLevel, 'backup_rebuilder.RemoveBackupToWork %s not in the queue' % backupID)


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
    current_queue_length = len(_BackupIDsQueue)
    _BackupIDsQueue = []
    if _Debug:
        lg.out(_DebugLevel, 'RemoveAllBackupsToWork %d items cleaned' % current_queue_length)


def SetStoppedFlag():
    """
    To stop backup_rebuilder() you need to call this method, it will set
    ``_StoppedFlag`` to True.
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
