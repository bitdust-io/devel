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
    * :red:`raid-done`
    * :red:`raid-failed`
    * :red:`request-failed`


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

_Debug = True
_DebugLevel = 12

#------------------------------------------------------------------------------

import os
import sys
import time

try:
    from twisted.internet import reactor
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

from raid import raid_worker
from raid import eccmap

from crypt import encrypted

from p2p import contact_status

#------------------------------------------------------------------------------

class RestoreWorker(automat.Automat):
    """
    This class implements all the functionality of ``restore_worker()`` state machine.
    """

    def __init__(self,
                 BackupID,
                 OutputFile,
                 KeyID=None,
                 debug_level=0,
                 log_events=False,
                 log_transitions=False,
                 publish_events=False,
                 **kwargs):
        """
        Builds `restore_worker()` state machine.
        """
        self.CreatorID = my_id.getLocalID()
        self.BackupID = BackupID
        _parts = packetid.SplitBackupID(self.BackupID)
        self.CustomerGlobalID = _parts[0]
        self.CustomerIDURL = global_id.GlobalUserToIDURL(self.CustomerGlobalID)
        self.PathID = _parts[1]
        self.Version = _parts[2]
        self.File = OutputFile
        self.KeyID = KeyID
        # is current active block - so when add 1 we get to first, which is 0
        self.BlockNumber = -1
        self.BytesWritten = 0
        self.OnHandData = []
        self.OnHandParity = []
        self.AbortState = False
        self.Done = False
        self.EccMap = eccmap.Current()
        self.Started = time.time()
        self.LastAction = time.time()
        self.RequestFails = []
        # For anyone who wants to know when we finish
        self.MyDeferred = Deferred()
        self.packetInCallback = None
        self.blockRestoredCallback = None

        super(RestoreWorker, self).__init__(
            name='restore_%s' % self.Version,
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )
        events.send('restore-started', dict(backup_id=self.BackupID))

    def set_packet_in_callback(self, cb):
        self.packetInCallback = cb

    def set_block_restored_callback(self, cb):
        self.blockRestoredCallback = cb

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'REQUESTED'
                self.doInit(arg)
                self.doStartNewBlock(arg)
                self.doScanExistingPackets(arg)
                self.doRequestPackets(arg)
                self.Attempt=1
        #---REQUESTED---
        elif self.state == 'REQUESTED':
            if event == 'request-failed' and self.isStillCorrectable(arg):
                self.doScanExistingPackets(arg)
                self.doRequestPackets(arg)
                self.Attempt+=1
            elif event == 'abort' or ( event == 'request-failed' and ( not self.isStillCorrectable(arg) or self.Attempts>=3 ) ):
                self.state = 'FAILED'
                self.doDeleteAllRequests(arg)
                self.doRemoveTempFile(arg)
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'data-receiving-started':
                self.state = 'RECEIVING'
        #---RECEIVING---
        elif self.state == 'RECEIVING':
            if event == 'data-received' and self.isBlockFixable(arg):
                self.state = 'RAID'
                self.doSavePacket(arg)
                self.doReadRaid(arg)
            elif event == 'data-received' and not self.isBlockFixable(arg):
                self.doSavePacket(arg)
            elif event == 'abort' or ( ( event == 'request-failed' or event == 'data-receiving-stopped' ) and not self.isStillCorrectable(arg) ):
                self.state = 'FAILED'
                self.doDeleteAllRequests(arg)
                self.doRemoveTempFile(arg)
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'data-receiving-stopped' and self.isStillCorrectable(arg):
                self.state = 'REQUESTED'
        #---RAID---
        elif self.state == 'RAID':
            if event == 'raid-done':
                self.state = 'BLOCK'
                self.doRestoreBlock(arg)
            elif event == 'data-received':
                pass
            elif event == 'raid-failed' or event == 'abort':
                self.state = 'FAILED'
                self.doDeleteAllRequests(arg)
                self.doRemoveTempFile(arg)
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---BLOCK---
        elif self.state == 'BLOCK':
            if event == 'block-restored' and not self.isLastBlock(arg):
                self.state = 'REQUESTED'
                self.doWriteRestoredData(arg)
                self.doRemoveTempFile(arg)
                self.doStartNewBlock(arg)
                self.doScanExistingPackets(arg)
                self.doRequestPackets(arg)
                self.Attempt=1
            elif event == 'block-restored' and self.isLastBlock(arg):
                self.state = 'DONE'
                self.doWriteRestoredData(arg)
                self.doDeleteAllRequests(arg)
                self.doRemoveTempFile(arg)
                self.doReportDone(arg)
                self.doDestroyMe(arg)
            elif event == 'data-received':
                pass
            elif event == 'block-failed' or event == 'abort':
                self.state = 'FAILED'
                self.doDeleteAllRequests(arg)
                self.doRemoveTempFile(arg)
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def isLastBlock(self, arg):
        """
        Condition method.
        """
        NewBlock = arg[0]
        return NewBlock.LastBlock

    def isStillCorrectable(self, arg):
        """
        Condition method.
        """
        return len(self.RequestFails) <= eccmap.GetCorrectableErrors(self.EccMap.NumSuppliers())

    def isBlockFixable(self, arg):
        """
        Condition method.
        """
        return self.EccMap.Fixable(self.OnHandData, self.OnHandParity)

    def doInit(self, arg):
        """
        Action method.
        """
        data_receiver_lookup = automat.find('data_receiver')
        if data_receiver_lookup:
            data_receiver_lookup[0].addStateChangedCallback()

    def doStartNewBlock(self, arg):
        """
        Action method.
        """
        self.LastAction = time.time()
        self.BlockNumber += 1
        if _Debug:
            lg.out(_DebugLevel, "restore_worker.doStartNewBlock " + str(self.BlockNumber))
        self.OnHandData = [False, ] * self.EccMap.datasegments
        self.OnHandParity = [False, ] * self.EccMap.paritysegments
        self.RequestFails = []

    def doScanExistingPackets(self, arg):
        """
        Action method.
        """
        for SupplierNumber in range(self.EccMap.datasegments):
            PacketID = packetid.MakePacketID(self.BackupID, self.BlockNumber, SupplierNumber, 'Data')
            customer, remotePath = packetid.SplitPacketID(PacketID)
            self.OnHandData[SupplierNumber] = os.path.exists(os.path.join(
                settings.getLocalBackupsDir(), customer, remotePath))
        for SupplierNumber in range(self.EccMap.paritysegments):
            PacketID = packetid.MakePacketID(self.BackupID, self.BlockNumber, SupplierNumber, 'Parity')
            customer, remotePath = packetid.SplitPacketID(PacketID)
            self.OnHandParity[SupplierNumber] = os.path.exists(os.path.join(
                settings.getLocalBackupsDir(), customer, remotePath))

    def doRestoreBlock(self, arg):
        """
        Action method.
        """
        filename = arg
        blockbits = bpio.ReadBinaryFile(filename)
        if not blockbits:
            self.automat('block-failed')
            return
        splitindex = blockbits.index(":")
        lengthstring = blockbits[0:splitindex]
        try:
            datalength = int(lengthstring)                                        # real length before raidmake/ECC
            blockdata = blockbits[splitindex + 1:splitindex + 1 + datalength]     # remove padding from raidmake/ECC
            newblock = encrypted.Unserialize(blockdata, decrypt_key=self.KeyID)   # convert to object
        except:
            lg.exc()
            self.automat('block-failed')
            return
        self.automat('block-restored', (newblock, filename, ))

    def doRequestPackets(self, arg):
        """
        Action method.
        """
        from customer import io_throttle
        packetsToRequest = []
        for SupplierNumber in range(self.EccMap.datasegments):
            SupplierID = contactsdb.supplier(SupplierNumber, customer_idurl=self.CustomerIDURL)
            if not SupplierID:
                continue
            if not self.OnHandData[SupplierNumber] and contact_status.isOnline(SupplierID):
                packetsToRequest.append((SupplierID, packetid.MakePacketID(self.BackupID, self.BlockNumber, SupplierNumber, 'Data')))
        for SupplierNumber in range(self.EccMap.paritysegments):
            SupplierID = contactsdb.supplier(SupplierNumber, customer_idurl=self.CustomerIDURL)
            if not SupplierID:
                continue
            if not self.OnHandParity[SupplierNumber] and contact_status.isOnline(SupplierID):
                packetsToRequest.append((SupplierID, packetid.MakePacketID(self.BackupID, self.BlockNumber, SupplierNumber, 'Parity')))
        requests_made = 0
        for SupplierID, packetID in packetsToRequest:
            if not io_throttle.HasPacketInRequestQueue(SupplierID, packetID):
                io_throttle.QueueRequestFile(
                    self._on_packet_request_result,
                    self.CreatorID,
                    packetID,
                    self.CreatorID,
                    SupplierID)
                requests_made += 1
        del packetsToRequest
        if requests_made:
            if _Debug:
                lg.out(_DebugLevel, "restore_worker.doRequestPackets requested %d packets for block %d" % (
                    requests_made, self.BlockNumber))
        else:
            lg.warn('no requests made for block %d')
            self.automat('request-failed')

    def doSavePacket(self, arg):
        """
        Action method.
        """
        NewPacket, PacketID = arg
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
            if not bpio.WriteFile(filename, NewPacket.Payload):
                lg.warn("unable to write to %s" % filename)
                return
            if self.packetInCallback is not None:
                self.packetInCallback(self.BackupID, NewPacket)
            if _Debug:
                lg.out(_DebugLevel, "restore_worker.doSavePacket %s saved to %s" % (packetID, filename))
        else:
            lg.warn('new packet is None, probably already exists locally')

    def doReadRaid(self, arg):
        """
        Action method.
        """
        fd, outfilename = tmpfile.make(
            'restore',
            prefix=self.BackupID.replace(':', '_').replace('@', '_').replace('/', '_') + '_' + str(self.BlockNumber) + '_',
        )
        os.close(fd)
        inputpath = os.path.join(settings.getLocalBackupsDir(), self.CustomerGlobalID, self.PathID)
        task_params = (outfilename, eccmap.CurrentName(), self.Version, self.BlockNumber, inputpath)
        raid_worker.add_task('read', task_params,
                             lambda cmd, params, result: self._on_block_restored(result, outfilename))

    def doRemoveTempFile(self, arg):
        """
        Action method.
        """
        try:
            filename = arg[1]
        except:
            return
        tmpfile.throw_out(filename, 'block restored')
        if settings.getBackupsKeepLocalCopies():
            return
        import backup_rebuilder
        import backup_matrix
        if not backup_rebuilder.ReadStoppedFlag():
            if backup_rebuilder.A().currentBackupID is not None:
                if backup_rebuilder.A().currentBackupID == self.BackupID:
                    if _Debug:
                        lg.out(_DebugLevel, 'restore_worker.doRemoveTempFile SKIP because rebuilding in process')
                    return
        count = 0
        for supplierNum in xrange(contactsdb.num_suppliers(customer_idurl=self.CustomerIDURL)):
            supplierIDURL = contactsdb.supplier(supplierNum, customer_idurl=self.CustomerIDURL)
            if not supplierIDURL:
                continue
            for dataORparity in ['Data', 'Parity', ]:
                packetID = packetid.MakePacketID(self.BackupID, self.BlockNumber,
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
        backup_matrix.LocalBlockReport(self.BackupID, self.BlockNumber, arg)
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doRemoveTempFile %d files were removed' % count)

    def doWriteRestoredData(self, arg):
        """
        Action method.
        """
        NewBlock = arg[0]
        data = NewBlock.Data()
        # Add to the file where all the data is going
        try:
            os.write(self.File, data)
            self.BytesWritten += len(data)
        except:
            lg.exc()
            # TODO Error handling...
            return
        if self.blockRestoredCallback is not None:
            self.blockRestoredCallback(self.BackupID, NewBlock)

    def doDeleteAllRequests(self, arg):
        """
        Action method.
        """
        from customer import io_throttle
        io_throttle.DeleteBackupRequests(self.BackupID)

    def doReportDone(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doReportDone')
        self.Done = True
        self.MyDeferred.callback('done')
        events.send('restore-done', dict(backup_id=self.BackupID))

    def doReportFailed(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'restore_worker.doReportFailed')
        self.Done = True
        self.MyDeferred.callback('failed')
        events.send('restore-failed', dict(backup_id=self.BackupID, block_number=self.BlockNumber, reason=arg))

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.OnHandData = None
        self.OnHandParity = None
        self.EccMap = None
        self.LastAction = None
        self.RequestFails = None
        self.MyDeferred = None
        self.File = None
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
            self.RequestFails.append(NewPacketOrPacketID)
            self.automat('request-failed', NewPacketOrPacketID.PacketID)
        else:
            lg.warn('packet %s got not recognized result: %s' % (NewPacketOrPacketID, result, ))
            self.automat('request-failed', NewPacketOrPacketID)

    def _on_data_receiver_state_changed(self, oldstate, newstate, event_string, args):
        if newstate == 'RECEIVING' and oldstate != 'RECEIVING':
            self.automat('data-receiving-started', newstate)
        elif oldstate == 'RECEIVING' and newstate != 'RECEIVING':
            self.automat('data-receiving-stopped', newstate)
