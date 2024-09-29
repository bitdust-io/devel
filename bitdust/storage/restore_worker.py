#!/usr/bin/env python
# restore_worker.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
#
# This file (restore_worker.py) is part of BitDust Software.
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
"""
.. module:: restore_worker
.. role:: red

BitDust restore_worker() Automat

EVENTS:
    * :red:`abort`
    * :red:`block-failed`
    * :red:`block-restored`
    * :red:`data-received`
    * :red:`data-receiving-started`
    * :red:`data-receiving-stopped`
    * :red:`init`
    * :red:`instant`
    * :red:`raid-done`
    * :red:`raid-failed`
    * :red:`request-failed`
    * :red:`request-finished`
    * :red:`timer-5sec`


At least for now we will work one block at a time, though packets in parallel.
We ask transport_control for all the data packets for a block then see if we
get them all or need to ask for some parity packets.  We do this till we have
gotten a block with the "LastBlock" flag set.  If we have tried several times
and not gotten data packets from a supplier we can flag him as suspect-bad
and start requesting a parity packet to cover him right away.

When we are missing a data packet we pick a parity packet where we have all the
other data packets for that parity so we can recover the missing data packet.
This network cost for this is just as low as if we read the data packet.
But most of the time we won't bother reading the parities.  Just uses up bandwidth.

We don't want to fire someone till
after we have finished a restore in case we have other problems and they might come
back to life and save us.  However, we might keep packets for a node we plan to fire.
This would make replacing them very easy.

At the "tar" level a user will have choice of full restore (to new empty system probably)
or to restore to another location on disk, or to just recover certain files.  However,
in this module we have to read block by block all of the blocks.

How do we restore if we lost everything?
Our public/private-key needs to be stored previously
on USB, in safe or deposit box (encrypted with passphrase or clear text).

The other thing we need is the backupIDs which we can get from our suppliers with the ListFiles command.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

import os
import sys
import time

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in restore.py')

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust.automats import automat

from bitdust.logs import lg

from bitdust.system import bpio
from bitdust.system import tmpfile

from bitdust.main import settings
from bitdust.main import events

from bitdust.lib import packetid
from bitdust.lib import strng

from bitdust.contacts import contactsdb

from bitdust.crypt import encrypted

from bitdust.p2p import online_status
from bitdust.p2p import propagate

from bitdust.stream import data_receiver
from bitdust.stream import io_throttle

from bitdust.raid import raid_worker
from bitdust.raid import eccmap

from bitdust.services import driver

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------


class RestoreWorker(automat.Automat):

    """
    This class implements all the functionality of ``restore_worker()`` state machine.
    """

    timers = {
        'timer-5sec': (5.0, ['REQUESTED']),
    }

    def __init__(self, BackupID, OutputFile, KeyID=None, ecc_map=None, debug_level=_DebugLevel, log_events=False, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `restore_worker()` state machine.
        """
        self.creator_id = my_id.getIDURL()
        self.backup_id = BackupID
        _parts = packetid.SplitBackupID(self.backup_id)
        self.customer_id = _parts[0]
        self.customer_idurl = global_id.GlobalUserToIDURL(self.customer_id)
        self.known_suppliers = []
        self.path_id = _parts[1]
        self.version = _parts[2]
        self.output_stream = OutputFile
        self.key_id = KeyID
        # is current active block - so when add 1 we get to first, which is 0
        self.block_number = -1
        self.bytes_written = 0
        self.OnHandData = []
        self.OnHandParity = []
        self.abort_flag = False
        self.done_flag = False
        self.EccMap = ecc_map or None
        self.max_errors = 0
        self.Started = time.time()
        self.LastAction = time.time()
        self.RequestFails = []
        self.block_requests = {}
        self.AlreadyRequestedCounts = {}
        # For anyone who wants to know when we finish
        self.MyDeferred = Deferred()
        self.packetInCallback = None
        self.blockRestoredCallback = None
        self.Attempts = 0

        super(RestoreWorker, self).__init__(name='restore_%s' % self.version, state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)
        events.send('restore-started', data=dict(backup_id=self.backup_id))

    def set_packet_in_callback(self, cb):
        self.packetInCallback = cb

    def set_block_restored_callback(self, cb):
        self.blockRestoredCallback = cb

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `restore_worker()` state were changed.
        """
        if event != 'instant':
            if newstate in ['REQUESTED', 'RECEIVING'] and oldstate not in ['REQUESTED', 'RECEIVING']:
                reactor.callLater(0.01, self.automat, 'instant')  # @UndefinedVariable

    def state_not_changed(self, curstate, event, *args, **kwargs):
        if event == 'data-received' and curstate in ['REQUESTED', 'RECEIVING']:
            reactor.callLater(0.01, self.automat, 'instant')  # @UndefinedVariable

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'REQUESTED'
                self.doInit(*args, **kwargs)
                self.doStartNewBlock(*args, **kwargs)
                self.doScanExistingPackets(*args, **kwargs)
                self.doRequestPackets(*args, **kwargs)
                self.Attempts = 1
        #---REQUESTED---
        elif self.state == 'REQUESTED':
            if event == 'data-receiving-started':
                self.state = 'RECEIVING'
            elif event == 'timer-5sec' and self.Attempts == 2:
                self.doPingOfflineSuppliers(*args, **kwargs)
            elif event == 'data-received':
                self.doSavePacket(*args, **kwargs)
            elif event == 'request-failed' and self.isStillCorrectable(*args, **kwargs) and self.Attempts < 3:
                self.doScanExistingPackets(*args, **kwargs)
                self.doRequestPackets(*args, **kwargs)
                self.Attempts += 1
            elif (event == 'abort' or
                  (event == 'request-failed' and
                   (not self.isStillCorrectable(*args, **kwargs) or self.Attempts >= 3))) or ((event == 'instant' or event == 'request-finished') and not self.isBlockReceiving(*args, **kwargs) and not self.isBlockFixable(*args, **kwargs)):
                self.state = 'FAILED'
                self.doDeleteAllRequests(*args, **kwargs)
                self.doRemoveTempFile(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif (event == 'instant' or event == 'request-finished') and self.isBlockFixable(*args, **kwargs):
                self.state = 'RAID'
                self.doReadRaid(*args, **kwargs)
        #---RECEIVING---
        elif self.state == 'RECEIVING':
            if event == 'data-receiving-stopped' and self.isStillCorrectable(*args, **kwargs):
                self.state = 'REQUESTED'
                self.doScanExistingPackets(*args, **kwargs)
                self.doRequestPackets(*args, **kwargs)
            elif event == 'data-received':
                self.doSavePacket(*args, **kwargs)
            elif (event == 'abort' or ((event == 'request-failed' or event == 'data-receiving-stopped') and
                                       not self.isStillCorrectable(*args, **kwargs))) or ((event == 'instant' or event == 'request-finished') and not self.isBlockReceiving(*args, **kwargs) and not self.isBlockFixable(*args, **kwargs)):
                self.state = 'FAILED'
                self.doDeleteAllRequests(*args, **kwargs)
                self.doRemoveTempFile(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif (event == 'instant' or event == 'request-finished') and self.isBlockFixable(*args, **kwargs):
                self.state = 'RAID'
                self.doReadRaid(*args, **kwargs)
        #---RAID---
        elif self.state == 'RAID':
            if event == 'raid-done':
                self.state = 'BLOCK'
                self.doRestoreBlock(*args, **kwargs)
            elif event == 'data-received':
                pass
            elif event == 'raid-failed' or event == 'abort':
                self.state = 'FAILED'
                self.doDeleteAllRequests(*args, **kwargs)
                self.doRemoveTempFile(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---BLOCK---
        elif self.state == 'BLOCK':
            if event == 'block-restored' and not self.isLastBlock(*args, **kwargs):
                self.state = 'REQUESTED'
                self.doWriteRestoredData(*args, **kwargs)
                self.doRemoveTempFile(*args, **kwargs)
                self.doStartNewBlock(*args, **kwargs)
                self.doScanExistingPackets(*args, **kwargs)
                self.doRequestPackets(*args, **kwargs)
                self.Attempts = 1
            elif event == 'block-restored' and self.isLastBlock(*args, **kwargs):
                self.state = 'DONE'
                self.doWriteRestoredData(*args, **kwargs)
                self.doDeleteAllRequests(*args, **kwargs)
                self.doRemoveTempFile(*args, **kwargs)
                self.doReportDone(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'data-received':
                pass
            elif event == 'block-failed' or event == 'abort':
                self.state = 'FAILED'
                self.doDeleteAllRequests(*args, **kwargs)
                self.doRemoveTempFile(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def isLastBlock(self, *args, **kwargs):
        """
        Condition method.
        """
        NewBlock = args[0][0]
        return NewBlock.LastBlock

    def isStillCorrectable(self, *args, **kwargs):
        """
        Condition method.
        """
        if not self.EccMap:
            return False
        result = bool(len(self.RequestFails) <= self.max_errors)
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.isStillCorrectable max_errors=%d, fails=%d' % (self.max_errors, len(self.RequestFails)))
        return result

    def isBlockFixable(self, *args, **kwargs):
        """
        Condition method.
        """
        if not self.EccMap:
            return False
        result = self.EccMap.Fixable(self.OnHandData, self.OnHandParity)
        if _Debug:
            lg.args(_DebugLevel, block_number=self.block_number, result=result, OnHandData=self.OnHandData, OnHandParity=self.OnHandParity)
        return result

    def isBlockReceiving(self, *args, **kwargs):
        """
        Condition method.
        """
        block_results = list(self.block_requests.values())
        if _Debug:
            lg.args(_DebugLevel, block_results=block_results)
        return block_results.count(None) > 0

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_block_rebuilding()
        self.known_suppliers = [_f for _f in contactsdb.suppliers(customer_idurl=self.customer_idurl) if _f]
        if not self.EccMap:
            if self.customer_idurl == my_id.getIDURL():
                self.EccMap = eccmap.Current()
                lg.info('ECC map %r set from local for my own suppliers' % self.EccMap)
        if not self.EccMap:
            known_eccmap_dict = {}
            for supplier_idurl in self.known_suppliers:
                known_ecc_map = contactsdb.get_supplier_meta_info(
                    supplier_idurl=supplier_idurl,
                    customer_idurl=self.customer_idurl,
                ).get('ecc_map', None)
                if known_ecc_map:
                    if known_ecc_map not in known_eccmap_dict:
                        known_eccmap_dict[known_ecc_map] = 0
                    known_eccmap_dict[known_ecc_map] += 1
            if known_eccmap_dict:
                all_known_eccmaps = list(known_eccmap_dict.items())
                all_known_eccmaps.sort(key=lambda i: i[1], reverse=True)
                self.EccMap = eccmap.eccmap(all_known_eccmaps[0][0])
                lg.info('ECC map %r recognized from suppliers meta info' % self.EccMap)
            else:
                known_ecc_map = None
                if driver.is_on('service_shared_data'):
                    from bitdust.access import shared_access_coordinator
                    active_share = shared_access_coordinator.get_active_share(self.key_id)
                    if active_share:
                        known_ecc_map = active_share.known_ecc_map
                if known_ecc_map:
                    self.EccMap = eccmap.eccmap(known_ecc_map)
                    lg.info('ECC map %r recognized from active share %r' % (self.EccMap, active_share))
                else:
                    num_suppliers = len(self.known_suppliers)
                    if num_suppliers not in eccmap.GetPossibleSuppliersCount():
                        num_suppliers = settings.DefaultDesiredSuppliers()
                    self.EccMap = eccmap.eccmap(eccmap.GetEccMapName(num_suppliers))
                    lg.warn('no meta info found, guessed ECC map %r from %d known suppliers' % (self.EccMap, len(self.known_suppliers)))
        # TODO: here we multiply by two because we have always two packets for each fragment: Data and Parity
        # so number of possible errors can be two times larger
        # however we may also add another check here to identify dead suppliers as well
        # and dead suppliers number must be lower than "max_errors" in order restore to continue
        self.max_errors = eccmap.GetCorrectableErrors(self.EccMap.NumSuppliers())*2
        if data_receiver.A():
            data_receiver.A().addStateChangedCallback(self._on_data_receiver_state_changed)

    def doStartNewBlock(self, *args, **kwargs):
        """
        Action method.
        """
        self.LastAction = time.time()
        self.block_number += 1
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doStartNewBlock ' + str(self.block_number))
        self.OnHandData = [False]*self.EccMap.datasegments
        self.OnHandParity = [False]*self.EccMap.paritysegments
        self.RequestFails = []
        self.block_requests = {}
        self.AlreadyRequestedCounts = {}

    def doPingOfflineSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        l = []
        for supplier_idurl in contactsdb.suppliers(customer_idurl=self.customer_idurl):
            if online_status.isOnline(supplier_idurl):
                continue
            l.append(supplier_idurl)
        propagate.SendToIDs(l, wide=True)

    def doScanExistingPackets(self, *args, **kwargs):
        """
        Action method.
        """
        for SupplierNumber in range(self.EccMap.datasegments):
            PacketID = packetid.MakePacketID(self.backup_id, self.block_number, SupplierNumber, 'Data')
            customerID, remotePath = packetid.SplitPacketID(PacketID)
            self.OnHandData[SupplierNumber] = bool(os.path.exists(os.path.join(settings.getLocalBackupsDir(), customerID, remotePath)))
        for SupplierNumber in range(self.EccMap.paritysegments):
            PacketID = packetid.MakePacketID(self.backup_id, self.block_number, SupplierNumber, 'Parity')
            customerID, remotePath = packetid.SplitPacketID(PacketID)
            self.OnHandParity[SupplierNumber] = bool(os.path.exists(os.path.join(settings.getLocalBackupsDir(), customerID, remotePath)))

    def doRestoreBlock(self, *args, **kwargs):
        """
        Action method.
        """
        filename = args[0]
        blockbits = bpio.ReadBinaryFile(filename)
        if not blockbits:
            lg.warn('empty file %r' % filename)
            self.automat('block-failed')
            return
        try:
            splitindex = blockbits.index(b':')
            lengthstring = blockbits[0:splitindex]
            datalength = int(lengthstring)  # real length before raidmake/ECC
            blockdata = blockbits[splitindex + 1:splitindex + 1 + datalength]  # remove padding from raidmake/ECC
            newblock = encrypted.Unserialize(blockdata, decrypt_key=self.key_id)  # convert to object
        except:
            if _Debug:
                lg.exc('bad block: %r' % blockbits)
            else:
                lg.exc()
            self.automat('block-failed')
            return
        if not newblock:
            lg.warn('block read/unserialize failed from %d bytes of data' % len(blockbits))
            self.automat('block-failed')
            return
        self.automat('block-restored', (newblock, filename))

    def doRequestPackets(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_check_run_requests()

    def doSavePacket(self, *args, **kwargs):
        """
        Action method.
        """
        if not args or not args[0]:
            raise Exception('no input found')
        NewPacket, PacketID = args[0]
        glob_path = global_id.NormalizeGlobalID(PacketID, detect_version=True)
        packetID = global_id.CanonicalID(PacketID)
        customer_id, _, _, _, SupplierNumber, dataORparity = packetid.SplitFull(packetID)
        if dataORparity == 'Data':
            self.OnHandData[SupplierNumber] = True
        elif dataORparity == 'Parity':
            self.OnHandParity[SupplierNumber] = True
        if not NewPacket:
            lg.warn('packet %r already exists locally' % packetID)
            return
        filename = os.path.join(settings.getLocalBackupsDir(), customer_id, glob_path['path'])
        dirpath = os.path.dirname(filename)
        if not os.path.exists(dirpath):
            try:
                bpio._dirs_make(dirpath)
            except:
                lg.exc()
        # either way the payload of packet is saved
        if not bpio.WriteBinaryFile(filename, NewPacket.Payload):
            lg.err('unable to write to %s' % filename)
            return
        if self.packetInCallback is not None:
            self.packetInCallback(self.backup_id, NewPacket)
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doSavePacket %s saved to %s' % (packetID, filename))

    def doReadRaid(self, *args, **kwargs):
        """
        Action method.
        """
        alias = self.backup_id.split('$')[0]
        _, outfilename = tmpfile.make(
            'restore',
            extension='.raid',
            prefix=alias + '_' + str(self.block_number) + '_',
            close_fd=True,
        )
        inputpath = os.path.join(settings.getLocalBackupsDir(), self.customer_id, self.path_id)
        task_params = (outfilename, self.EccMap.name, self.version, self.block_number, inputpath)
        raid_worker.add_task('read', task_params, lambda cmd, params, result: self._on_block_restored(result, outfilename))

    def doRemoveTempFile(self, *args, **kwargs):
        """
        Action method.
        """
        if not args or not len(args) > 1:
            return
        filename = args[1]
        if filename:
            tmpfile.throw_out(filename, 'block restored')
        if settings.getBackupsKeepLocalCopies():
            return
        from bitdust.storage import backup_matrix
        from bitdust.storage import backup_rebuilder
        if not backup_rebuilder.ReadStoppedFlag():
            if backup_rebuilder.A().currentBackupID is not None:
                if backup_rebuilder.A().currentBackupID == self.backup_id:
                    if _Debug:
                        lg.out(_DebugLevel, 'restore_worker.doRemoveTempFile SKIP because rebuilding in process')
                    return
        count = 0
        for supplierNum in range(contactsdb.num_suppliers(customer_idurl=self.customer_idurl)):
            supplierIDURL = contactsdb.supplier(supplierNum, customer_idurl=self.customer_idurl)
            if not supplierIDURL:
                continue
            for dataORparity in ['Data', 'Parity']:
                packetID = packetid.MakePacketID(self.backup_id, self.block_number, supplierNum, dataORparity)
                customer, remotePath = packetid.SplitPacketID(packetID)
                filename = os.path.join(settings.getLocalBackupsDir(), customer, remotePath)
                if os.path.isfile(filename):
                    try:
                        os.remove(filename)
                    except:
                        lg.exc()
                        continue
                    count += 1
        backup_matrix.LocalBlockReport(self.backup_id, self.block_number, *args, **kwargs)
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doRemoveTempFile %d files were removed' % count)

    def doWriteRestoredData(self, *args, **kwargs):
        """
        Action method.
        """
        NewBlock = args[0][0]
        data = NewBlock.Data()
        # Add to the file where all the data is going
        try:
            os.write(self.output_stream, data)
            self.bytes_written += len(data)
        except:
            lg.exc()
            # TODO Error handling...
            return
        if self.blockRestoredCallback is not None:
            self.blockRestoredCallback(self.backup_id, NewBlock)

    def doDeleteAllRequests(self, *args, **kwargs):
        """
        Action method.
        """
        io_throttle.DeleteBackupRequests(self.backup_id)

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doReportDone')
        self.done_flag = True
        self.MyDeferred.callback('done')
        # events.send('restore-done', data=dict(backup_id=self.backup_id))

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        if args and len(args) > 0 and args[0] == 'abort':
            reason = 'abort'
        else:
            reason = 'failed'
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doReportFailed : %s' % reason)
        self.done_flag = True
        self.MyDeferred.callback(reason)
        events.send('restore-failed', data=dict(
            backup_id=self.backup_id,
            block_number=self.block_number,
            args=args,
            reason=reason,
        ))

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self._do_unblock_rebuilding()
        if data_receiver.A():
            data_receiver.A().removeStateChangedCallback(self._on_data_receiver_state_changed)
        self.OnHandData = None
        self.OnHandParity = None
        self.EccMap = None
        self.LastAction = None
        self.RequestFails = []
        self.AlreadyRequestedCounts = None
        self.block_requests = None
        self.MyDeferred = None
        self.output_stream = None
        self.destroy()

    def _do_block_rebuilding(self):
        from bitdust.storage import backup_rebuilder
        backup_rebuilder.BlockBackup(self.backup_id)
        io_throttle.DeleteBackupRequests(self.backup_id)

    def _do_unblock_rebuilding(self):
        from bitdust.storage import backup_rebuilder
        backup_rebuilder.UnBlockBackup(self.backup_id)

    def _do_check_run_requests(self):
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker._do_check_run_requests for %s at block %d' % (self.backup_id, self.block_number))
        packetsToRequest = []
        for SupplierNumber in range(self.EccMap.datasegments):
            request_packet_id = packetid.MakePacketID(self.backup_id, self.block_number, SupplierNumber, 'Data')
            if self.OnHandData[SupplierNumber]:
                if _Debug:
                    lg.out(_DebugLevel, '        SKIP, OnHandData is True for supplier %d' % SupplierNumber)
                if request_packet_id not in self.block_requests:
                    self.block_requests[request_packet_id] = True
                continue
            if request_packet_id in self.block_requests:
                if _Debug:
                    lg.out(_DebugLevel, '        SKIP, request for packet %r already sent to IO queue for supplier %d' % (request_packet_id, SupplierNumber))
                continue
            SupplierID = contactsdb.supplier(SupplierNumber, customer_idurl=self.customer_idurl)
            if not SupplierID:
                lg.warn('unknown supplier at position %s' % SupplierNumber)
                continue
            if online_status.isOffline(SupplierID):
                if _Debug:
                    lg.out(_DebugLevel, '        SKIP, offline supplier: %s' % SupplierID)
                continue
            packetsToRequest.append((SupplierID, request_packet_id))
        for SupplierNumber in range(self.EccMap.paritysegments):
            request_packet_id = packetid.MakePacketID(self.backup_id, self.block_number, SupplierNumber, 'Parity')
            if self.OnHandParity[SupplierNumber]:
                if _Debug:
                    lg.out(_DebugLevel, '        SKIP, OnHandParity is True for supplier %d' % SupplierNumber)
                if request_packet_id not in self.block_requests:
                    self.block_requests[request_packet_id] = True
                continue
            if request_packet_id in self.block_requests:
                if _Debug:
                    lg.out(_DebugLevel, '        SKIP, request for packet %r already sent to IO queue for supplier %d' % (request_packet_id, SupplierNumber))
                continue
            SupplierID = contactsdb.supplier(SupplierNumber, customer_idurl=self.customer_idurl)
            if not SupplierID:
                lg.warn('unknown supplier at position %s' % SupplierNumber)
                continue
            if online_status.isOffline(SupplierID):
                if _Debug:
                    lg.out(_DebugLevel, '        SKIP, offline supplier: %s' % SupplierID)
                continue
            packetsToRequest.append((SupplierID, request_packet_id))
        requests_made = 0
        # already_requested = 0
        for SupplierID, packetID in packetsToRequest:
            if io_throttle.HasPacketInRequestQueue(SupplierID, packetID):
                # already_requested += 1
                # if packetID not in self.AlreadyRequestedCounts:
                #     self.AlreadyRequestedCounts[packetID] = 0
                # self.AlreadyRequestedCounts[packetID] += 1
                lg.warn('packet already in IO queue for supplier %s : %s' % (SupplierID, packetID))
                continue
            self.block_requests[packetID] = None
            if io_throttle.QueueRequestFile(
                callOnReceived=self._on_packet_request_result,
                creatorID=self.creator_id,
                packetID=packetID,
                ownerID=self.creator_id,  # self.customer_idurl,
                remoteID=SupplierID,
            ):
                requests_made += 1
            else:
                self.block_requests[packetID] = False
            if _Debug:
                lg.dbg(_DebugLevel, 'sent request %r to %r, other requests: %r' % (packetID, SupplierID, list(self.block_requests.values())))
        del packetsToRequest
        if requests_made:
            if _Debug:
                lg.out(_DebugLevel, '        requested %d packets for block %d' % (requests_made, self.block_number))
            return
        current_block_requests_results = list(self.block_requests.values())
        if _Debug:
            lg.args(_DebugLevel, current_results=current_block_requests_results)
        pending_count = current_block_requests_results.count(None)
        if pending_count > 0:
            if _Debug:
                lg.out(_DebugLevel, '        nothing for request, currently %d pending packets for block %d' % (pending_count, self.block_number))
            return
        failed_count = current_block_requests_results.count(False)
        if failed_count > self.max_errors:
            lg.err('all requests finished and %d packets failed, not possible to read data for block %d' % (failed_count, self.block_number))
            reactor.callLater(0, self.automat, 'request-failed', None)  # @UndefinedVariable
            return
        if _Debug:
            lg.out(_DebugLevel, '        all requests finished for block %d : %r' % (self.block_number, current_block_requests_results))
        reactor.callLater(0, self.automat, 'request-finished', None)  # @UndefinedVariable

    def _on_block_restored(self, restored_blocks, filename):
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker._on_block_restored at %s with result: %s' % (filename, restored_blocks))
        if restored_blocks is None:
            self.automat('raid-failed', (None, filename))
        else:
            self.automat('raid-done', filename)

    def _on_packet_request_result(self, NewPacketOrPacketID, result):
        if self.block_requests is None:
            return
        if _Debug:
            lg.args(_DebugLevel, packet=NewPacketOrPacketID, result=result)
        packet_id = None
        if strng.is_string(NewPacketOrPacketID):
            packet_id = NewPacketOrPacketID
        else:
            packet_id = getattr(NewPacketOrPacketID, 'PacketID', None)
        if not packet_id:
            raise Exception('packet ID is unknown from %r' % NewPacketOrPacketID)
        if packet_id not in self.block_requests:
            resp = global_id.NormalizeGlobalID(packet_id)
            for req_packet_id in self.block_requests:
                req = global_id.NormalizeGlobalID(req_packet_id)
                if resp['version'] == req['version'] and resp['path'] == req['path']:
                    if resp['key_alias'] == req['key_alias'] and resp['user'] == req['user']:
                        if id_url.is_the_same(resp['idurl'], req['idurl']):
                            packet_id = req_packet_id
                            lg.warn('found matching packet request %r for rotated idurl %r' % (packet_id, resp['idurl']))
                            break
        if packet_id not in self.block_requests:
            if _Debug:
                lg.args(_DebugLevel, block_requests=self.block_requests)
            raise Exception('packet ID not registered')
        if result == 'in queue':
            if self.block_requests[packet_id] is not None:
                raise Exception('packet is still in IO queue, but already unregistered')
            lg.warn('packet already in the request queue: %r' % packet_id)
            return
        if result in ['received', 'exist']:
            self.block_requests[packet_id] = True
            if result == 'exist':
                # reactor.callLater(0, self.automat, 'data-received', (None, packet_id, ))  # @UndefinedVariable
                self.event('data-received', (None, packet_id))
            else:
                # reactor.callLater(0, self.automat, 'data-received', (NewPacketOrPacketID, packet_id, ))  # @UndefinedVariable
                self.event('data-received', (NewPacketOrPacketID, packet_id))
        else:
            self.block_requests[packet_id] = False
            self.RequestFails.append(packet_id)
            # reactor.callLater(0, self.automat, 'request-failed', packet_id)  # @UndefinedVariable
            self.event('request-failed', packet_id)

    def _on_data_receiver_state_changed(self, oldstate, newstate, event_string, *args, **kwargs):
        if newstate == 'RECEIVING' and oldstate != 'RECEIVING':
            self.automat('data-receiving-started', newstate)
        elif oldstate == 'RECEIVING' and newstate != 'RECEIVING':
            self.automat('data-receiving-stopped', newstate)
