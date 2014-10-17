#!/usr/bin/python
#data_sender.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: data_sender

.. raw:: html

    <a href="http://bitpie.net/automats/data_sender/data_sender.png" target="_blank">
    <img src="http://bitpie.net/automats/data_sender/data_sender.png" style="max-width:100%;">
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
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in data_sender.py')

from logs import lg

from lib import bpio
from lib import misc
from lib import packetid
from lib import contacts
from lib import settings
from lib import diskspace
from lib import nameurl
from lib import automat
from lib import automats

from transport import gate

import io_throttle
import backup_matrix
import fire_hire
import contact_status
import backup_monitor

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
        _DataSender = DataSender('data_sender', 'READY', 4)
    if event is not None:
        _DataSender.automat(event, arg)
    return _DataSender


class DataSender(automat.Automat):
    """
    A class to manage process of sending data packets to remote suppliers.
    """
    
    timers = {'timer-1min':     (60,     ['READY']),
        'timer-1min': (60, ['READY']),
        'timer-1sec': (1.0, ['SENDING']),
              }
    statistic = {}

    def state_changed(self, oldstate, newstate, event, arg):
        automats.set_global_state('DATASEND ' + newstate)

    def A(self, event, arg):
        #---READY---
        if self.state == 'READY':
            if event == 'new-data' or event == 'timer-1min' or event == 'restart' :
                self.state = 'SCAN_BLOCKS'
                self.doScanAndQueue(arg)
            elif event == 'init' :
                pass
        #---SCAN_BLOCKS---
        elif self.state == 'SCAN_BLOCKS':
            if event == 'scan-done' and self.isQueueEmpty(arg) :
                self.state = 'READY'
                self.doRemoveUnusedFiles(arg)
            elif event == 'scan-done' and not self.isQueueEmpty(arg) :
                self.state = 'SENDING'
        #---SENDING---
        elif self.state == 'SENDING':
            if event == 'restart' or ( ( event == 'timer-1sec' or event == 'block-acked' or event == 'block-failed' ) and self.isQueueEmpty(arg) ) :
                self.state = 'SCAN_BLOCKS'
                self.doScanAndQueue(arg)
            elif event == 'timer-1sec' :
                self.doPrintStats(arg)

    def isQueueEmpty(self, arg):
        if not arg:
            return io_throttle.IsSendingQueueEmpty()
        remoteID, packetID = arg
        return io_throttle.OkToSend(remoteID)
    
    def doScanAndQueue(self, arg):
        global _ShutdownFlag
        lg.out(10, 'data_sender.doScanAndQueue')
        log = open(os.path.join(settings.LogsDir(), 'data_sender.log'), 'w')
        log.write('doScanAndQueue %s\n' % time.asctime())
        if _ShutdownFlag:
            log.write('doScanAndQueue _ShutdownFlag is True\n')
            self.automat('scan-done')
            log.flush()
            log.close()
            return
        if '' not in contacts.getSupplierIDs():
            for backupID in misc.sorted_backup_ids(backup_matrix.local_files().keys(), True):
                packetsBySupplier = backup_matrix.ScanBlocksToSend(backupID)
                log.write('%s\n' % packetsBySupplier)
                for supplierNum in packetsBySupplier.keys():
                    supplier_idurl = contacts.getSupplierID(supplierNum)
                    if not supplier_idurl:
                        lg.warn('?supplierNum? %s for %s' % (supplierNum, backupID))
                        continue
                    for packetID in packetsBySupplier[supplierNum]:
                        backupID_, blockNum, supplierNum_, dataORparity = packetid.BidBnSnDp(packetID)
                        if backupID_ != backupID:
                            lg.warn('?backupID? %s for %s' % (packetID, backupID))
                            continue
                        if supplierNum_ != supplierNum:
                            lg.warn('?supplierNum? %s for %s' % (packetID, backupID))
                            continue
                        if io_throttle.HasPacketInSendQueue(supplier_idurl, packetID):
                            log.write('%s in the send queue to %s\n' % (packetID, supplier_idurl))
                            continue
                        if not io_throttle.OkToSend(supplier_idurl):
                            log.write('ok to send %s ? - NO!\n' % supplier_idurl)
                            continue
                        # tranByID = gate.transfers_out_by_idurl().get(supplier_idurl, [])
                        # if len(tranByID) > 3:
                        #     log.write('transfers by %s: %d\n' % (supplier_idurl, len(tranByID)))
                        #     continue
                        filename = os.path.join(settings.getLocalBackupsDir(), packetID)
                        if not os.path.isfile(filename):
                            log.write('%s is not file\n' % filename)
                            continue
                        if io_throttle.QueueSendFile(
                                filename, 
                                packetID, 
                                supplier_idurl, 
                                misc.getLocalID(), 
                                self._packetAcked, 
                                self._packetFailed):
                            log.write('io_throttle.QueueSendFile %s\n' % packetID)
                        else:
                            log.write('io_throttle.QueueSendFile FAILED %s\n' % packetID)
                        # lg.out(6, '  %s for %s' % (packetID, backupID))
        self.automat('scan-done')
        log.flush()
        log.close()
        
    def doPrintStats(self, arg):
        """
        """
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
        if settings.getGeneralLocalBackups() is True:
            # if user set this in settings - he want to keep the local files
            return
        # ... user do not want to keep local backups
        if settings.getGeneralWaitSuppliers() is True:
            # but he want to be sure - all suppliers are green for a long time
            if contact_status.hasOfflineSuppliers() or time.time() - fire_hire.GetLastFireTime() < 24*60*60:
                # some people are not there or we do not have stable team yet
                # do not remove the files because we need it to rebuild
                return
        count = 0 
        for backupID in misc.sorted_backup_ids(backup_matrix.local_files().keys()):
            packets = backup_matrix.ScanBlocksToRemove(backupID, settings.getGeneralWaitSuppliers())
            for packetID in packets:
                filename = os.path.join(settings.getLocalBackupsDir(), packetID)
                if os.path.isfile(filename):
                    try:
                        os.remove(filename)
                        # lg.out(6, '    ' + os.path.basename(filename))
                    except:
                        lg.exc()
                        continue
                    count += 1
        lg.out(8, 'data_sender.doRemoveUnusedFiles %d files were removed' % count)
        backup_matrix.ReadLocalFiles()
                         
    def _packetAcked(self, packet, ownerID, packetID):
        backupID, blockNum, supplierNum, dataORparity = packetid.BidBnSnDp(packetID)
        backup_matrix.RemoteFileReport(backupID, blockNum, supplierNum, dataORparity, True)
        if not self.statistic.has_key(ownerID):
            self.statistic[ownerID] = [0, 0]
        self.statistic[ownerID][0] += 1
        self.automat('block-acked', (ownerID, packetID))
    
    def _packetFailed(self, remoteID, packetID, why):
        backupID, blockNum, supplierNum, dataORparity = packetid.BidBnSnDp(packetID)
        backup_matrix.RemoteFileReport(backupID, blockNum, supplierNum, dataORparity, False)
        if not self.statistic.has_key(remoteID):
            self.statistic[remoteID] = [0, 0]
        self.statistic[remoteID][1] += 1
        self.automat('block-failed', (remoteID, packetID))


def statistic():
    """
    The ``data_sender()`` keeps track of sending results with every supplier.
    This is used by ``fire_hire()`` to decide how reliable is given supplier.
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
        
        
        
        
        
        
        

