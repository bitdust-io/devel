#!/usr/bin/env python
# restore_worker.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
Our ( public/private-key and eccmap) needs to be stored previously
on USB, in safe or deposit box (encrypted with passphrase or clear text).

The other thing we need is the backupIDs which we can get from our suppliers with the ListFiles command.

"""


#------------------------------------------------------------------------------

from __future__ import absolute_import
import six
from six.moves import range

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import sys
import time

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in restore.py')

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from automats import automat

from logs import lg

from system import bpio
from system import tmpfile

from main import settings
from main import events

from lib import packetid

from contacts import contactsdb

from userid import my_id
from userid import global_id

from crypt import encrypted

from p2p import online_status
from p2p import propagate

from customer import data_receiver

from raid import raid_worker
from raid import eccmap

from services import driver

#------------------------------------------------------------------------------

class RestoreWorker(automat.Automat):
    """
    This class implements all the functionality of ``restore_worker()`` state machine.
    """

    timers = {
        'timer-5sec': (5.0, ['REQUESTED']),
    }

    def __init__(self,
                 BackupID,
                 OutputFile,
                 KeyID=None,
                 debug_level=_DebugLevel,
                 log_events=False,
                 log_transitions=_Debug,
                 publish_events=False,
                 **kwargs):
        """
        Builds `restore_worker()` state machine.
        """
        self.creator_id = my_id.getLocalID()
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
        self.EccMap = None
        self.Started = time.time()
        self.LastAction = time.time()
        self.RequestFails = []
        self.AlreadyRequestedCounts = {}
        # For anyone who wants to know when we finish
        self.MyDeferred = Deferred()
        self.packetInCallback = None
        self.blockRestoredCallback = None

        super(RestoreWorker, self).__init__(
            name='restore_worker_%s' % self.version,
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )
        events.send('restore-started', dict(backup_id=self.backup_id))

    def set_packet_in_callback(self, cb):
        self.packetInCallback = cb

    def set_block_restored_callback(self, cb):
        self.blockRestoredCallback = cb

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `restore_worker()` state were changed.
        """
        if newstate == 'REQUESTED':
            self.automat('instant')

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
                self.Attempts=1
        #---REQUESTED---
        elif self.state == 'REQUESTED':
            if event == 'data-receiving-started':
                self.state = 'RECEIVING'
            elif event == 'data-received' and not self.isBlockFixable(*args, **kwargs):
                self.doSavePacket(*args, **kwargs)
            elif event == 'timer-5sec' and self.Attempts==1:
                self.doPingSuppliers(*args, **kwargs)
            elif ( event == 'instant' or event == 'data-received' ) and self.isBlockFixable(*args, **kwargs):
                self.state = 'RAID'
                self.doSavePacket(*args, **kwargs)
                self.doReadRaid(*args, **kwargs)
            elif event == 'abort' or ( ( event == 'request-failed' ) and ( not self.isStillCorrectable(*args, **kwargs) or self.Attempts>=3 ) ):
                self.state = 'FAILED'
                self.doDeleteAllRequests(*args, **kwargs)
                self.doRemoveTempFile(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif ( event == 'request-failed' ) and self.isStillCorrectable(*args, **kwargs) and self.Attempts<3:
                self.doScanExistingPackets(*args, **kwargs)
                self.doRequestPackets(*args, **kwargs)
                self.Attempts+=1
        #---RECEIVING---
        elif self.state == 'RECEIVING':
            if event == 'data-received' and self.isBlockFixable(*args, **kwargs):
                self.state = 'RAID'
                self.doSavePacket(*args, **kwargs)
                self.doReadRaid(*args, **kwargs)
            elif event == 'data-received' and not self.isBlockFixable(*args, **kwargs):
                self.doSavePacket(*args, **kwargs)
            elif event == 'abort' or ( ( event == 'request-failed' or event == 'data-receiving-stopped' ) and not self.isStillCorrectable(*args, **kwargs) ):
                self.state = 'FAILED'
                self.doDeleteAllRequests(*args, **kwargs)
                self.doRemoveTempFile(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'data-receiving-stopped' and self.isStillCorrectable(*args, **kwargs):
                self.state = 'REQUESTED'
                self.doScanExistingPackets(*args, **kwargs)
                self.doRequestPackets(*args, **kwargs)
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
                self.Attempts=1
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
        max_errors = eccmap.GetCorrectableErrors(self.EccMap.NumSuppliers())
        result = bool(len(self.RequestFails) <= max_errors)
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.isStillCorrectable max_errors=%d, fails=%d' % (
                max_errors, len(self.RequestFails), ))
        return result

    def isBlockFixable(self, *args, **kwargs):
        """
        Condition method.
        """
        result = self.EccMap.Fixable(self.OnHandData, self.OnHandParity)
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.isBlockFixable returns %s for block %d' % (result, self.block_number, ))
            lg.out(_DebugLevel, '    OnHandData: %s' % self.OnHandData)
            lg.out(_DebugLevel, '    OnHandParity: %s' % self.OnHandParity)
        return result

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.known_suppliers = [_f for _f in contactsdb.suppliers(customer_idurl=self.customer_idurl) if _f]
        known_eccmap_dict = {}
        for supplier_idurl in self.known_suppliers:
            known_ecc_map = contactsdb.get_supplier_meta_info(
                supplier_idurl=supplier_idurl, customer_idurl=self.customer_idurl,
            ).get('ecc_map', None)
            if known_ecc_map:
                if known_ecc_map not in known_eccmap_dict:
                    known_eccmap_dict[known_ecc_map] = 0
                known_eccmap_dict[known_ecc_map] += 1
        if known_eccmap_dict:
            all_known_eccmaps = list(known_eccmap_dict.items())
            all_known_eccmaps.sort(key=lambda i: i[1], reverse=True)
            self.EccMap = eccmap.eccmap(all_known_eccmaps[0][0])
            lg.info('eccmap %r recognized from suppliers meta info' % self.EccMap)
        else:
            known_ecc_map = None
            if driver.is_on('service_shared_data'):
                from access import shared_access_coordinator
                active_share = shared_access_coordinator.get_active_share(self.key_id)
                if active_share:
                    known_ecc_map = active_share.known_ecc_map
            if known_ecc_map:
                self.EccMap = eccmap.eccmap(known_ecc_map)
                lg.info('eccmap %r recognized from active share %r' % (self.EccMap, active_share, ))
            else:
                num_suppliers = len(self.known_suppliers)
                if num_suppliers not in eccmap.GetPossibleSuppliersCount():
                    num_suppliers = settings.DefaultDesiredSuppliers()
                self.EccMap = eccmap.eccmap(eccmap.GetEccMapName(num_suppliers))
                lg.warn('no meta info found, guessed eccmap %r from %d known suppliers' % (
                    self.EccMap, len(self.known_suppliers)))
        if data_receiver.A():
            data_receiver.A().addStateChangedCallback(self._on_data_receiver_state_changed)

    def doStartNewBlock(self, *args, **kwargs):
        """
        Action method.
        """
        self.LastAction = time.time()
        self.block_number += 1
        if _Debug:
            lg.out(_DebugLevel, "restore_worker.doStartNewBlock " + str(self.block_number))
        self.OnHandData = [False, ] * self.EccMap.datasegments
        self.OnHandParity = [False, ] * self.EccMap.paritysegments
        self.RequestFails = []
        self.AlreadyRequestedCounts = {}

    def doPingSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        propagate.SendSuppliers()

    def doScanExistingPackets(self, *args, **kwargs):
        """
        Action method.
        """
        for SupplierNumber in range(self.EccMap.datasegments):
            PacketID = packetid.MakePacketID(self.backup_id, self.block_number, SupplierNumber, 'Data')
            customerID, remotePath = packetid.SplitPacketID(PacketID)
            self.OnHandData[SupplierNumber] = bool(os.path.exists(os.path.join(
                settings.getLocalBackupsDir(), customerID, remotePath)))
        for SupplierNumber in range(self.EccMap.paritysegments):
            PacketID = packetid.MakePacketID(self.backup_id, self.block_number, SupplierNumber, 'Parity')
            customerID, remotePath = packetid.SplitPacketID(PacketID)
            self.OnHandParity[SupplierNumber] = bool(os.path.exists(os.path.join(
                settings.getLocalBackupsDir(), customerID, remotePath)))

    def doRestoreBlock(self, *args, **kwargs):
        """
        Action method.
        """
        filename = args[0]
        blockbits = bpio.ReadBinaryFile(filename)
        if not blockbits:
            self.automat('block-failed')
            return
        splitindex = blockbits.index(b":")
        lengthstring = blockbits[0:splitindex]
        try:
            datalength = int(lengthstring)                                        # real length before raidmake/ECC
            blockdata = blockbits[splitindex + 1:splitindex + 1 + datalength]     # remove padding from raidmake/ECC
            newblock = encrypted.Unserialize(blockdata, decrypt_key=self.key_id)  # convert to object
        except:
            lg.exc()
            self.automat('block-failed')
            return
        if not newblock:
            self.automat('block-failed')
            return
        self.automat('block-restored', (newblock, filename, ))

    def doRequestPackets(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doRequestPackets for %s at block %d' % (self.backup_id, self.block_number, ))
        from customer import io_throttle
        packetsToRequest = []
        for SupplierNumber in range(self.EccMap.datasegments):
            SupplierID = contactsdb.supplier(SupplierNumber, customer_idurl=self.customer_idurl)
            if not SupplierID:
                lg.warn('unknown supplier at position %s' % SupplierNumber)
                continue
            if online_status.isOffline(SupplierID):
                lg.warn('offline supplier: %s' % SupplierID)
                continue
            if self.OnHandData[SupplierNumber]:
                if _Debug:
                    lg.out(_DebugLevel, '        OnHandData is True for supplier %d' % SupplierNumber)
                continue
            packetsToRequest.append((SupplierID, packetid.MakePacketID(self.backup_id, self.block_number, SupplierNumber, 'Data')))
        for SupplierNumber in range(self.EccMap.paritysegments):
            SupplierID = contactsdb.supplier(SupplierNumber, customer_idurl=self.customer_idurl)
            if not SupplierID:
                lg.warn('unknown supplier at position %s' % SupplierNumber)
                continue
            if online_status.isOffline(SupplierID):
                lg.warn('offline supplier: %s' % SupplierID)
                continue
            if self.OnHandParity[SupplierNumber]:
                if _Debug:
                    lg.out(_DebugLevel, '        OnHandParity is True for supplier %d' % SupplierNumber)
                continue
            packetsToRequest.append((SupplierID, packetid.MakePacketID(self.backup_id, self.block_number, SupplierNumber, 'Parity')))
        if _Debug:
            lg.out(_DebugLevel, '        packets to request: %s' % packetsToRequest)
        requests_made = 0
        already_requested = 0
        for SupplierID, packetID in packetsToRequest:
            if io_throttle.HasPacketInRequestQueue(SupplierID, packetID):
                already_requested += 1
                if packetID not in self.AlreadyRequestedCounts:
                    self.AlreadyRequestedCounts[packetID] = 0
                self.AlreadyRequestedCounts[packetID] += 1
                if _Debug:
                    lg.out(_DebugLevel, '        packet already in request queue: %s %s' % (SupplierID, packetID, ))
                continue
            io_throttle.QueueRequestFile(
                self._on_packet_request_result,
                self.creator_id,
                packetID,
                self.creator_id,
                SupplierID)
            requests_made += 1
        del packetsToRequest
        if requests_made:
            if _Debug:
                lg.out(_DebugLevel, "        requested %d packets for block %d" % (
                    requests_made, self.block_number))
        else:
            if not already_requested:
                lg.warn('no requests made for block %d' % self.block_number)
                self.automat('request-failed', None)
            else:
                if _Debug:
                    lg.out(_DebugLevel, "        found %d already requested packets for block %d" % (
                        already_requested, self.block_number))
                if self.AlreadyRequestedCounts:
                    all_counts = sorted(self.AlreadyRequestedCounts.values())
                    if all_counts[0] > 100:
                        lg.warn('too much requests made for block %d' % self.block_number)
                        self.automat('request-failed', None)

    def doSavePacket(self, *args, **kwargs):
        """
        Action method.
        """
        if not args or not args[0]:
            return
        NewPacket, PacketID = args[0]
        glob_path = global_id.ParseGlobalID(PacketID, detect_version=True)
        packetID = global_id.CanonicalID(PacketID)
        customer_id, _, _, _, SupplierNumber, dataORparity = packetid.SplitFull(packetID)
        if dataORparity == 'Data':
            self.OnHandData[SupplierNumber] = True
        elif dataORparity == 'Parity':
            self.OnHandParity[SupplierNumber] = True
        if NewPacket:
            filename = os.path.join(settings.getLocalBackupsDir(), customer_id, glob_path['path'])
            dirpath = os.path.dirname(filename)
            if not os.path.exists(dirpath):
                try:
                    bpio._dirs_make(dirpath)
                except:
                    lg.exc()
            # either way the payload of packet is saved
            if not bpio.WriteBinaryFile(filename, NewPacket.Payload):
                lg.warn("unable to write to %s" % filename)
                return
            if self.packetInCallback is not None:
                self.packetInCallback(self.backup_id, NewPacket)
            if _Debug:
                lg.out(_DebugLevel, "restore_worker.doSavePacket %s saved to %s" % (packetID, filename))
        else:
            lg.warn('new packet is None, probably already exists locally')

    def doReadRaid(self, *args, **kwargs):
        """
        Action method.
        """
        fd, outfilename = tmpfile.make(
            'restore',
            extension='.raid',
            prefix=self.backup_id.replace(':', '_').replace('@', '_').replace('/', '_') + '_' + str(self.block_number) + '_',
        )
        os.close(fd)
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
        from . import backup_rebuilder
        from . import backup_matrix
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
            for dataORparity in ['Data', 'Parity', ]:
                packetID = packetid.MakePacketID(self.backup_id, self.block_number,
                                                 supplierNum, dataORparity)
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
        from customer import io_throttle
        io_throttle.DeleteBackupRequests(self.backup_id)

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doReportDone')
        self.done_flag = True
        self.MyDeferred.callback('done')
        events.send('restore-done', dict(backup_id=self.backup_id))

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
        events.send('restore-failed', dict(
            backup_id=self.backup_id,
            block_number=self.block_number,
            args=args,
            reason=reason,
        ))

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        if data_receiver.A():
            data_receiver.A().removeStateChangedCallback(self._on_data_receiver_state_changed)
        self.OnHandData = None
        self.OnHandParity = None
        self.EccMap = None
        self.LastAction = None
        self.RequestFails = []
        self.AlreadyRequestedCounts = {}
        self.MyDeferred = None
        self.output_stream = None
        self.destroy()

    def _on_block_restored(self, restored_blocks, filename):
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker._on_block_restored at %s with result: %s' % (filename, restored_blocks))
        if restored_blocks is None:
            self.automat('raid-failed', (None, filename))
        else:
            self.automat('raid-done', filename)

    def _on_packet_request_result(self, NewPacketOrPacketID, result):
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker._on_packet_request_result %s : %s' % (result, NewPacketOrPacketID))
        if result == 'received':
            self.automat('data-received', (NewPacketOrPacketID, NewPacketOrPacketID.PacketID, ))
        elif result == 'exist':
            self.automat('data-received', (None, NewPacketOrPacketID, ))
        elif result == 'in queue':
            lg.warn('packet already in the request queue')
        elif result == 'failed':
            if isinstance(NewPacketOrPacketID, six.string_types):
                self.RequestFails.append(NewPacketOrPacketID)
                self.automat('request-failed', NewPacketOrPacketID)
            else:
                self.RequestFails.append(getattr(NewPacketOrPacketID, 'PacketID', None))
                self.automat('request-failed', getattr(NewPacketOrPacketID, 'PacketID', None))
        else:
            lg.warn('packet %s got not recognized result: %s' % (NewPacketOrPacketID, result, ))
            if isinstance(NewPacketOrPacketID, six.string_types):
                self.RequestFails.append(NewPacketOrPacketID)
                self.automat('request-failed', NewPacketOrPacketID)
            else:
                self.RequestFails.append(getattr(NewPacketOrPacketID, 'PacketID', None))
                self.automat('request-failed', getattr(NewPacketOrPacketID, 'PacketID', None))

    def _on_data_receiver_state_changed(self, oldstate, newstate, event_string, *args, **kwargs):
        if newstate == 'RECEIVING' and oldstate != 'RECEIVING':
            self.automat('data-receiving-started', newstate)
        elif oldstate == 'RECEIVING' and newstate != 'RECEIVING':
            self.automat('data-receiving-stopped', newstate)
