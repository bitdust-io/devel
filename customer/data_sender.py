#!/usr/bin/python
# data_sender.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

    <a href="https://bitdust.io/automats/data_sender/data_sender.png" target="_blank">
    <img src="https://bitdust.io/automats/data_sender/data_sender.png" style="max-width:100%;">
    </a>

A state machine to manage data sending process, acts very simple:
    1) when new local data is created it tries to send it to the correct supplier
    2) wait while ``p2p.io_throttle`` is doing some data transmission to remote suppliers
    3) calls ``p2p.backup_matrix.ScanBlocksToSend()`` to get a list of pieces needs to be send
    4) this machine is restarted every minute to check if some more data needs to be send
    5) also can be restarted at any time when it is needed

EVENTS:
    * :red:`block-acked`
    * :red:`block-failed`
    * :red:`init`
    * :red:`new-data`
    * :red:`restart`
    * :red:`scan-done`
    * :red:`shutdown`
    * :red:`timer-1min`
    * :red:`timer-1sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

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

from main import settings

from p2p import online_status

from customer import io_throttle

#------------------------------------------------------------------------------

_DataSender = None
_ShutdownFlag = False

#------------------------------------------------------------------------------

def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _DataSender
    if _DataSender is None:
        _DataSender = DataSender(
            name='data_sender',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _DataSender.automat(event, *args, **kwargs)
    return _DataSender


class DataSender(automat.Automat):
    """
    A class to manage process of sending data packets to remote suppliers.
    """
    timers = {
        'timer-1min': (60, ['READY']),
        'timer-1sec': (1.0, ['SENDING']),
    }


    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        global_state.set_global_state('DATASEND ' + newstate)

    def A(self, event, *args, **kwargs):
        #---READY---
        if self.state == 'READY':
            if event == 'new-data' or event == 'timer-1min':
                self.state = 'SCAN_BLOCKS'
                self.doScanAndQueue(*args, **kwargs)
            elif event == 'restart':
                self.state = 'SCAN_BLOCKS'
                self.doCleanUpSendingQueue(*args, **kwargs)
                self.doScanAndQueue(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---SCAN_BLOCKS---
        elif self.state == 'SCAN_BLOCKS':
            if event == 'scan-done' and self.isQueueEmpty(*args, **kwargs):
                self.state = 'READY'
                self.doRemoveUnusedFiles(*args, **kwargs)
            elif event == 'scan-done' and not self.isQueueEmpty(*args, **kwargs):
                self.state = 'SENDING'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doCleanUpSendingQueue(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'restart':
                self.doCleanUpSendingQueue(*args, **kwargs)
                self.doScanAndQueue(*args, **kwargs)
        #---SENDING---
        elif self.state == 'SENDING':
            if event == 'restart':
                self.state = 'SCAN_BLOCKS'
                self.doCleanUpSendingQueue(*args, **kwargs)
                self.doScanAndQueue(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doCleanUpSendingQueue(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif ( event == 'timer-1sec' or event == 'block-acked' or event == 'block-failed' or event == 'new-data' ) and self.isQueueEmpty(*args, **kwargs):
                self.state = 'SCAN_BLOCKS'
                self.doScanAndQueue(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READY'
                self.doInit(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isQueueEmpty(self, *args, **kwargs):
        if not args or not args[0]:
            is_empty = io_throttle.IsSendingQueueEmpty()
            if _Debug:
                lg.out(_DebugLevel, 'data_sender.isQueueEmpty is_empty=%s' % is_empty)
            return is_empty
        remoteID, _ = args[0]
        can_send_to = io_throttle.OkToSend(remoteID)
        if _Debug:
            lg.out(_DebugLevel, 'data_sender.isQueueEmpty can_send_to=%s remoteID=%r' % (can_send_to, remoteID, ))
        return can_send_to

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.statistic = {}

    def doScanAndQueue(self, *args, **kwargs):
        """
        Action method.
        """
        global _ShutdownFlag
        if _Debug:
            lg.out(_DebugLevel, 'data_sender.doScanAndQueue _ShutdownFlag=%r' % _ShutdownFlag)
        if _ShutdownFlag:
            if _Debug:
                lg.out(_DebugLevel, '        _ShutdownFlag is True\n')
            self.automat('scan-done')
            return
        from storage import backup_matrix
        backup_matrix.ReadLocalFiles()
        progress = 0
        for customer_idurl in contactsdb.known_customers():
            if customer_idurl != my_id.getLocalIDURL():
                # TODO: check that later
                if _Debug:
                    lg.out(_DebugLevel + 6, '    skip sending to another customer: %r' % customer_idurl)
                continue
            known_suppliers = contactsdb.suppliers(customer_idurl)
            if b'' in known_suppliers or '' in known_suppliers:
                if _Debug:
                    lg.out(_DebugLevel, '        found empty supplier for customer %r, SKIP' % customer_idurl)
                continue
            known_backups = misc.sorted_backup_ids(list(backup_matrix.local_files().keys()), True)
            if _Debug:
                lg.out(_DebugLevel, '        found %d known suppliers for customer %r with %d backups' % (
                    len(known_suppliers), customer_idurl, len(known_backups)))
            for backupID in known_backups:
                this_customer_idurl = packetid.CustomerIDURL(backupID)
                if this_customer_idurl != customer_idurl:
                    continue
                packetsBySupplier = backup_matrix.ScanBlocksToSend(backupID)
                if _Debug:
                    lg.out(_DebugLevel, '        packets for customer %r : %s' % (customer_idurl, packetsBySupplier))
                for supplierNum in packetsBySupplier.keys():
                    # supplier_idurl = contactsdb.supplier(supplierNum, customer_idurl=customer_idurl)
                    try:
                        supplier_idurl = known_suppliers[supplierNum]
                    except:
                        lg.exc()
                        continue
                    if not supplier_idurl:
                        lg.warn('unknown supplier_idurl supplierNum=%s for %s, customer_idurl=%r' % (
                            supplierNum, backupID, customer_idurl))
                        continue
                    for packetID in packetsBySupplier[supplierNum]:
                        backupID_, _, supplierNum_, _ = packetid.BidBnSnDp(packetID)
                        if backupID_ != backupID:
                            lg.warn('unexpected backupID supplierNum=%s for %s, customer_idurl=%r' % (
                                packetID, backupID, customer_idurl))
                            continue
                        if supplierNum_ != supplierNum:
                            lg.warn('unexpected supplierNum %s for %s, customer_idurl=%r' % (
                                packetID, backupID, customer_idurl))
                            continue
                        if io_throttle.HasPacketInSendQueue(supplier_idurl, packetID):
                            if _Debug:
                                lg.out(_DebugLevel, '        %s already in sending queue for %r' % (packetID, supplier_idurl))
                            continue
                        if not io_throttle.OkToSend(supplier_idurl):
                            if _Debug:
                                lg.out(_DebugLevel + 6, '        skip, not ok to send %s\n' % supplier_idurl)
                            continue
                        customerGlobalID, pathID = packetid.SplitPacketID(packetID)
                        # tranByID = gate.transfers_out_by_idurl().get(supplier_idurl, [])
                        # if len(tranByID) > 3:
                        #     log.write(u'transfers by %s: %d\n' % (supplier_idurl, len(tranByID)))
                        #     continue
                        customerGlobalID, pathID = packetid.SplitPacketID(packetID)
                        filename = os.path.join(
                            settings.getLocalBackupsDir(),
                            customerGlobalID,
                            pathID,
                        )
                        if not os.path.isfile(filename):
                            if _Debug:
                                lg.out(_DebugLevel, '        %s is not a file\n' % filename)
                            continue
                        if io_throttle.QueueSendFile(
                            filename,
                            packetID,
                            supplier_idurl,
                            my_id.getLocalID(),
                            self._packetAcked,
                            self._packetFailed,
                        ):
                            progress += 1
                            if _Debug:
                                lg.out(_DebugLevel, '        io_throttle.QueueSendFile %s' % packetID)
                        else:
                            if _Debug:
                                lg.out(_DebugLevel, '        io_throttle.QueueSendFile FAILED %s' % packetID)
        if _Debug:
            lg.out(_DebugLevel, 'data_sender.doScanAndQueue progress=%s' % progress)
        self.automat('scan-done')

#     def doPrintStats(self, *args, **kwargs):
#         """
#         """
#        if lg.is_debug(18):
#            transfers = transport_control.current_transfers()
#            bytes_stats = transport_control.current_bytes_transferred()
#            s = ''
#            for info in transfers:
#                s += '%s ' % (diskspace.MakeStringFromBytes(bytes_stats[info.transfer_id]).replace(' ', '').replace('bytes', 'b'))
#            lg.out(0, 'transfers: ' + s[:120])

    def doRemoveUnusedFiles(self, *args, **kwargs):
        """
        Action method.
        """
        # we want to remove files for this block
        # because we only need them during rebuilding
        if settings.getBackupsKeepLocalCopies() is True:
            # if user set this in settings - he want to keep the local files
            return
        # ... user do not want to keep local backups
        if settings.getGeneralWaitSuppliers() is True:
            from customer import fire_hire
            # but he want to be sure - all suppliers are green for a long time
            if len(online_status.listOfflineSuppliers()) > 0 or (time.time() - fire_hire.GetLastFireTime() < 24 * 60 * 60):
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
                list(backup_matrix.local_files().keys())):
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

    def doCleanUpSendingQueue(self, *args, **kwargs):
        """
        Action method.
        """
        io_throttle.DeleteAllSuppliers()

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.statistic = {}

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
