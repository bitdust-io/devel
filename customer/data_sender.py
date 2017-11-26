#!/usr/bin/python
# data_sender.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (data_sender.py) is part of BitDust Software.
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
.. module:: data_sender.

.. raw:: html

    <a href="http://bitdust.io/automats/data_sender/data_sender.png" target="_blank">
    <img src="http://bitdust.io/automats/data_sender/data_sender.png" style="max-width:100%;">
    </a>

A state machine to manage data sending process, acts very simple:
    1) when new local data is created it tries to send it to needed supplier
    2) wait while ``p2p.io_throttle`` is doing some data transmission to remote suppliers
    3) calls ``p2p.backup_matrix.ScanBlocksToSend()`` to get a list of pieces needs to be send
    4) this machine is restarted every minute to try to send the data ASAP
    5) also can be restarted at any time when other code decides that

EVENTS:
    * :red:`block-acked`
    * :red:`block-failed`
    * :red:`init`
    * :red:`new-data`
    * :red:`restart`
    * :red:`scan-done`
    * :red:`timer-1min`
    * :red:`timer-1sec`
"""

import os
import time

#------------------------------------------------------------------------------

from logs import lg

from automats import automat
from automats import global_state

from lib import misc

from lib import packetid

from contacts import contactsdb

from userid import my_id
from userid import global_id

from main import settings

from p2p import contact_status

import io_throttle

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 18

#------------------------------------------------------------------------------

_DataSender = None
_ShutdownFlag = False

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _DataSender
    if _DataSender is None:
        _DataSender = DataSender('data_sender', 'READY', _DebugLevel, _Debug)
    if event is not None:
        _DataSender.automat(event, arg)
    return _DataSender


def Destroy():
    """
    Destroy the state machine and remove the instance from memory.
    """
    global _DataSender
    if _DataSender is None:
        return
    _DataSender.destroy()
    del _DataSender
    _DataSender = None


class DataSender(automat.Automat):
    """
    A class to manage process of sending data packets to remote suppliers.
    """
    timers = {
        'timer-1min': (60, ['READY']),
        'timer-1min': (60, ['READY']),
        'timer-1sec': (1.0, ['SENDING']),
    }
    statistic = {}

    def state_changed(self, oldstate, newstate, event, arg):
        global_state.set_global_state('DATASEND ' + newstate)

    def A(self, event, arg):
        #---READY---
        if self.state == 'READY':
            if event == 'new-data' or event == 'timer-1min' or event == 'restart':
                self.state = 'SCAN_BLOCKS'
                self.doScanAndQueue(arg)
            elif event == 'init':
                pass
        #---SCAN_BLOCKS---
        elif self.state == 'SCAN_BLOCKS':
            if event == 'scan-done' and self.isQueueEmpty(arg):
                self.state = 'READY'
                self.doRemoveUnusedFiles(arg)
            elif event == 'scan-done' and not self.isQueueEmpty(arg):
                self.state = 'SENDING'
        #---SENDING---
        elif self.state == 'SENDING':
            if event == 'restart' or ( ( event == 'timer-1sec' or event == 'block-acked' or event == 'block-failed' or event == 'new-data' ) and self.isQueueEmpty(arg) ):
                self.state = 'SCAN_BLOCKS'
                self.doScanAndQueue(arg)
        return None

    def isQueueEmpty(self, arg):
        if not arg:
            return io_throttle.IsSendingQueueEmpty()
        remoteID, _ = arg
        return io_throttle.OkToSend(remoteID)

    def doScanAndQueue(self, arg):
        global _ShutdownFlag
        if _Debug:
            lg.out(_DebugLevel, 'data_sender.doScanAndQueue _ShutdownFlag=%r' % _ShutdownFlag)
        if _Debug:
            log = open(os.path.join(settings.LogsDir(), 'data_sender.log'), 'w')
            log.write('doScanAndQueue %s\n' % time.asctime())
        if _ShutdownFlag:
            if _Debug:
                log.write('doScanAndQueue _ShutdownFlag is True\n')
            self.automat('scan-done')
            if _Debug:
                log.flush()
                log.close()
            return
        for customer_idurl in contactsdb.known_customers():
            if '' not in contactsdb.suppliers(customer_idurl):
                from storage import backup_matrix
                for backupID in misc.sorted_backup_ids(
                        backup_matrix.local_files().keys(), True):
                    packetsBySupplier = backup_matrix.ScanBlocksToSend(backupID)
                    if _Debug:
                        log.write('%s\n' % packetsBySupplier)
                    for supplierNum in packetsBySupplier.keys():
                        supplier_idurl = contactsdb.supplier(supplierNum, customer_idurl=customer_idurl)
                        if not supplier_idurl:
                            lg.warn('?supplierNum? %s for %s' % (supplierNum, backupID))
                            continue
                        for packetID in packetsBySupplier[supplierNum]:
                            backupID_, _, supplierNum_, _ = packetid.BidBnSnDp(packetID)
                            if backupID_ != backupID:
                                lg.warn('?backupID? %s for %s' % (packetID, backupID))
                                continue
                            if supplierNum_ != supplierNum:
                                lg.warn('?supplierNum? %s for %s' % (packetID, backupID))
                                continue
                            if io_throttle.HasPacketInSendQueue(
                                    supplier_idurl, packetID):
                                if _Debug:
                                    log.write('%s already in sending queue for %s\n' % (packetID, supplier_idurl))
                                continue
                            if not io_throttle.OkToSend(supplier_idurl):
                                if _Debug:
                                    log.write('ok to send %s ? - NO!\n' % supplier_idurl)
                                continue
                            # tranByID = gate.transfers_out_by_idurl().get(supplier_idurl, [])
                            # if len(tranByID) > 3:
                            #     log.write('transfers by %s: %d\n' % (supplier_idurl, len(tranByID)))
                            #     continue
                            filename = os.path.join(
                                settings.getLocalBackupsDir(),
                                global_id.UrlToGlobalID(customer_idurl),
                                packetid.RemotePath(packetID),
                            )
                            if not os.path.isfile(filename):
                                if _Debug:
                                    log.write('%s is not a file\n' % filename)
                                continue
                            if io_throttle.QueueSendFile(
                                filename,
                                packetID,
                                supplier_idurl,
                                my_id.getLocalID(),
                                self._packetAcked,
                                self._packetFailed,
                            ):
                                if _Debug:
                                    log.write('io_throttle.QueueSendFile %s\n' % packetID)
                            else:
                                if _Debug:
                                    log.write('io_throttle.QueueSendFile FAILED %s\n' % packetID)
                            # lg.out(6, '  %s for %s' % (packetID, backupID))
                            # DEBUG
                            # break

        self.automat('scan-done')
        if _Debug:
            log.flush()
            log.close()

#     def doPrintStats(self, arg):
#         """
#         """
#        if lg.is_debug(18):
#            transfers = transport_control.current_transfers()
#            bytes_stats = transport_control.current_bytes_transferred()
#            s = ''
#            for info in transfers:
#                s += '%s ' % (diskspace.MakeStringFromBytes(bytes_stats[info.transfer_id]).replace(' ', '').replace('bytes', 'b'))
#            lg.out(0, 'transfers: ' + s[:120])

    def doRemoveUnusedFiles(self, arg):
        # we want to remove files for this block
        # because we only need them during rebuilding
        if settings.getBackupsKeepLocalCopies() is True:
            # if user set this in settings - he want to keep the local files
            return
        # ... user do not want to keep local backups
        if settings.getGeneralWaitSuppliers() is True:
            from customer import fire_hire
            # but he want to be sure - all suppliers are green for a long time
            if len(contact_status.listOfflineSuppliers()) > 0 or time.time(
            ) - fire_hire.GetLastFireTime() < 24 * 60 * 60:
                # some people are not there or we do not have stable team yet
                # do not remove the files because we need it to rebuild
                return
        count = 0
        from storage import backup_matrix
        from storage import restore_monitor
        from storage import backup_rebuilder
        if _Debug:
            lg.out(_DebugLevel, 'data_sender.doRemoveUnusedFiles')
        for backupID in misc.sorted_backup_ids(
                backup_matrix.local_files().keys()):
            if restore_monitor.IsWorking(backupID):
                if _Debug:
                    lg.out(
                        _DebugLevel,
                        '        %s : SKIP, because restoring' %
                        backupID)
                continue
            if backup_rebuilder.IsBackupNeedsWork(backupID):
                if _Debug:
                    lg.out(
                        _DebugLevel,
                        '        %s : SKIP, because needs rebuilding' %
                        backupID)
                continue
            if not backup_rebuilder.ReadStoppedFlag():
                if backup_rebuilder.A().currentBackupID is not None:
                    if backup_rebuilder.A().currentBackupID == backupID:
                        if _Debug:
                            lg.out(
                                _DebugLevel,
                                '        %s : SKIP, because rebuilding is in process' %
                                backupID)
                        continue
            packets = backup_matrix.ScanBlocksToRemove(
                backupID, settings.getGeneralWaitSuppliers())
            for packetID in packets:
                customer, pathID = packetid.SplitPacketID(packetID)
                filename = os.path.join(settings.getLocalBackupsDir(), customer, pathID)
                if os.path.isfile(filename):
                    try:
                        os.remove(filename)
                        # lg.out(6, '    ' + os.path.basename(filename))
                    except:
                        lg.exc()
                        continue
                    count += 1
        if _Debug:
            lg.out(_DebugLevel, '    %d files were removed' % count)
        backup_matrix.ReadLocalFiles()

    def _packetAcked(self, packet, ownerID, packetID):
        from storage import backup_matrix
        backupID, blockNum, supplierNum, dataORparity = packetid.BidBnSnDp(packetID)
        backup_matrix.RemoteFileReport(
            backupID, blockNum, supplierNum, dataORparity, True)
        if ownerID not in self.statistic:
            self.statistic[ownerID] = [0, 0]
        self.statistic[ownerID][0] += 1
        self.automat('block-acked', (ownerID, packetID))

    def _packetFailed(self, remoteID, packetID, why):
        from storage import backup_matrix
        backupID, blockNum, supplierNum, dataORparity = packetid.BidBnSnDp(
            packetID)
        backup_matrix.RemoteFileReport(
            backupID, blockNum, supplierNum, dataORparity, False)
        if remoteID not in self.statistic:
            self.statistic[remoteID] = [0, 0]
        self.statistic[remoteID][1] += 1
        self.automat('block-failed', (remoteID, packetID))


def statistic():
    """
    The ``data_sender()`` keeps track of sending results with every supplier.

    This is used by ``fire_hire()`` to decide how reliable is given
    supplier.
    """
    global _DataSender
    if _DataSender is None:
        return {}
    return _DataSender.statistic


def SetShutdownFlag():
    """
    Set flag to indicate that no need to send anything anymore.
    """
    global _ShutdownFlag
    _ShutdownFlag = True
