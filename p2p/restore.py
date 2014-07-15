#!/usr/bin/python
#restore.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: restore

.. raw:: html

    <a href="http://bitpie.net/automats/restore/restore.png" target="_blank">
    <img src="http://bitpie.net/automats/restore/restore.png" style="max-width:100%;">
    </a>
    

At least for now we will work one block at a time, though packets in parallel.
We ask transport_control for all the data packets for a block then see if we
get them all or need to ask for some parity packets.  We do this till we have
gotten a block with the "LastBlock" flag set.  If we have tried several times
and not gotten data packets from a supplier we can flag him as suspect-bad
and start requesting a parity packet to cover him right away.

When we are missing a data packet we pick a parity packet where we have all the
other data packets for that parity so we can recover the missing data packet .
This network cost for this is just as low as if we read the data packet .
But most of the time we won't bother reading the parities.  Just uses up bandwidth.

We don't want to fire someone till
after we have finished a restore in case we have other problems and they might come
back to life and save us.  However, we might keep packets for a node we plan to fire.
This would make replacing them very easy.

At the "tar" level a user will have choice of full restore (to new empty system probably)
or to restore to another location on disk, or to just recover certain files.  However,
in this module we have to read block by block all of the blocks.


How do we restore if we lost everything?
Our ( public/private-key and eccmap) could be:

    1)  at BitPie.NET  (encrypted with pass phrase)
    2)  on USB in safe or deposit box   (encrypted with passphrase or clear text)
    3)  with friends or scrubbers (encrypted with passphrase)
                
The other thing we need is the backupIDs which we can get from our suppliers with the ListFiles command.
The ID is something like ``F200801161206`` or ``I200801170401`` indicating full or incremental.


EVENTS:
    * :red:`block-restored`
    * :red:`init`
    * :red:`packet-came-in`
    * :red:`raid-done`
    * :red:`request-done`
    * :red:`timer-01sec`
    * :red:`timer-1sec`
    * :red:`timer-5sec`
"""

import os
import sys
import time
import gc

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in restore.py')


from twisted.internet import threads
from twisted.internet.defer import Deferred


import lib.misc as misc
import lib.io as io
import lib.eccmap as eccmap
import lib.settings as settings
import lib.packetid as packetid
import lib.contacts as contacts
import lib.tmpfile as tmpfile
import lib.automat as automat

import raid.raid_worker as raid_worker

# import raidread
import encrypted_block
import io_throttle
import events
import contact_status


#------------------------------------------------------------------------------ 


class restore(automat.Automat):
    timers = {
        'timer-1sec': (1.0, ['REQUEST']),
        'timer-01sec': (0.1, ['RUN']),
        'timer-5sec': (5.0, ['REQUEST']),
        }

    def __init__(self, BackupID, OutputFile): # OutputFileName 
        self.CreatorID = misc.getLocalID()
        self.BackupID = BackupID
        self.PathID, self.Version = packetid.SplitBackupID(self.BackupID)
        self.File = OutputFile
        # is current active block - so when add 1 we get to first, which is 0
        self.BlockNumber = -1              
        self.OnHandData = []
        self.OnHandParity = []
        self.AbortState = False
        self.Done = False
        self.EccMap = eccmap.Current()
        self.LastAction = time.time()
        self.InboxPacketsQueue = []
        self.InboxQueueWorker = None
        self.InboxQueueDelay = 1
        # For anyone who wants to know when we finish
        self.MyDeferred = Deferred()       
        self.packetInCallback = None
        self.blockRestoredCallback = None
        
        automat.Automat.__init__(self, 'restore', 'AT_STARTUP', 4)
        self.automat('init')
        events.info('restore', '%s start restoring' % self.BackupID)
        # io.log(6, "restore.__init__ %s, ecc=%s" % (self.BackupID, str(self.EccMap)))

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'RUN'
        #---RUN---
        elif self.state == 'RUN':
            if event == 'timer-01sec' and not self.isAborted(arg) :
                self.state = 'REQUEST'
                self.doStartNewBlock(arg)
                self.doReadPacketsQueue(arg)
                self.doScanExistingPackets(arg)
                self.doRequestPackets(arg)
            elif event == 'timer-01sec' and self.isAborted(arg) :
                self.state = 'ABORTED'
                self.doDeleteAllRequests(arg)
                self.doCloseFile(arg)
                self.doReportAborted(arg)
                self.doDestroyMe(arg)
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'packet-came-in' and self.isPacketValid(arg) and self.isCurrentBlock(arg) :
                self.doSavePacket(arg)
            elif event == 'timer-1sec' and self.isAborted(arg) :
                self.state = 'ABORTED'
                self.doPausePacketsQueue(arg)
                self.doDeleteAllRequests(arg)
                self.doCloseFile(arg)
                self.doReportAborted(arg)
                self.doDestroyMe(arg)
            elif ( event == 'timer-1sec' or event == 'request-done' ) and not self.isAborted(arg) and self.isBlockFixable(arg) :
                self.state = 'RAID'
                self.doPausePacketsQueue(arg)
                self.doReadRaid(arg)
            elif event == 'timer-5sec' and not self.isAborted(arg) and self.isTimePassed(arg) :
                self.doScanExistingPackets(arg)
                self.doRequestPackets(arg)
        #---RAID---
        elif self.state == 'RAID':
            if event == 'raid-done' :
                self.state = 'BLOCK'
                self.doRestoreBlock(arg)
        #---BLOCK---
        elif self.state == 'BLOCK':
            if event == 'block-restored' and self.isBlockValid(arg) and not self.isLastBlock(arg) :
                self.state = 'RUN'
                self.doWriteRestoredData(arg)
                self.doDeleteBlockRequests(arg)
                self.doRemoveTempFile(arg)
            elif event == 'block-restored' and self.isBlockValid(arg) and self.isLastBlock(arg) :
                self.state = 'DONE'
                self.doWriteRestoredData(arg)
                self.doDeleteAllRequests(arg)
                self.doRemoveTempFile(arg)
                self.doCloseFile(arg)
                self.doReportDone(arg)
                self.doDestroyMe(arg)
            elif event == 'block-restored' and not self.isBlockValid(arg) :
                self.state = 'FAILED'
                self.doDeleteAllRequests(arg)
                self.doRemoveTempFile(arg)
                self.doCloseFile(arg)
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---ABORTED---
        elif self.state == 'ABORTED':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---DONE---
        elif self.state == 'DONE':
            pass

    def isAborted(self, arg):
        return self.AbortState

    def isTimePassed(self, arg):
        return time.time() - self.LastAction > 60
    
    def isPacketValid(self, NewPacket):
        if not NewPacket.Valid():
            return False
        if NewPacket.DataOrParity() not in ['Data', 'Parity']:
            return False
        return True
    
    def isCurrentBlock(self, NewPacket):
        return NewPacket.BlockNumber() == self.BlockNumber
    
    def isBlockFixable(self, arg):
        return self.EccMap.Fixable(self.OnHandData, self.OnHandParity)
    
    def isBlockValid(self, arg):
        NewBlock = arg[0]
        if NewBlock is None:
            return False
        return NewBlock.Valid()
    
    def isLastBlock(self, arg):
        NewBlock = arg[0]
        return NewBlock.LastBlock
    
    def doStartNewBlock(self, arg):
        self.LastAction = time.time()
        self.BlockNumber += 1    
        io.log(6, "restore.doStartNewBlock " + str(self.BlockNumber))
        self.OnHandData = [False] * self.EccMap.datasegments
        self.OnHandParity = [False] * self.EccMap.paritysegments

    def doScanExistingPackets(self, arg):
        for SupplierNumber in range(self.EccMap.datasegments):
            PacketID = packetid.MakePacketID(self.BackupID, self.BlockNumber, SupplierNumber, 'Data')
            self.OnHandData[SupplierNumber] = os.path.exists(os.path.join(settings.getLocalBackupsDir(), PacketID))
        for SupplierNumber in range(self.EccMap.paritysegments):
            PacketID = packetid.MakePacketID(self.BackupID, self.BlockNumber, SupplierNumber, 'Parity')
            self.OnHandParity[SupplierNumber] = os.path.exists(os.path.join(settings.getLocalBackupsDir(), PacketID))
        
    def doRequestPackets(self, arg):
        packetsToRequest = []
        for SupplierNumber in range(self.EccMap.datasegments):
            SupplierID = contacts.getSupplierID(SupplierNumber) 
            if not SupplierID:
                continue
            if not self.OnHandData[SupplierNumber] and contact_status.isOnline(SupplierID):
                packetsToRequest.append((SupplierID, packetid.MakePacketID(self.BackupID, self.BlockNumber, SupplierNumber, 'Data')))
        for SupplierNumber in range(self.EccMap.paritysegments):
            SupplierID = contacts.getSupplierID(SupplierNumber) 
            if not SupplierID:
                continue
            if not self.OnHandParity[SupplierNumber] and contact_status.isOnline(SupplierID):
                packetsToRequest.append((SupplierID, packetid.MakePacketID(self.BackupID, self.BlockNumber, SupplierNumber, 'Parity')))
        for SupplierID, packetID in packetsToRequest:
            io_throttle.QueueRequestFile(
                self.PacketCameIn, 
                self.CreatorID, 
                packetID, 
                self.CreatorID, 
                SupplierID)
        io.log(6, "restore.doRequestPackets requested %d packets for block %d" % (len(packetsToRequest), self.BlockNumber))
        del packetsToRequest
        self.automat('request-done')
    
    def doReadRaid(self, arg):
        fd, filename = tmpfile.make('restore', 
            prefix=self.BackupID.replace('/','_')+'_'+str(self.BlockNumber)+'_')
        os.close(fd)
        raid_worker.A('new-task', ('read', 
            (filename, eccmap.CurrentName(), self.Version, self.BlockNumber, 
            os.path.join(settings.getLocalBackupsDir(), self.PathID)),
            lambda cmd, params, result: self._blockRestoreResult(result, filename)))
        
#        threads.deferToThread(
#            raidread.raidread,
#                filename, 
#                eccmap.CurrentName(), 
#                self.Version, 
#                self.BlockNumber, 
#                os.path.join(settings.getLocalBackupsDir(), self.PathID) ).addBoth(
#                    lambda restored_blocks: self.automat('raid-done', filename))
         
    def doReadPacketsQueue(self, arg):
        reactor.callLater(0, self.ProcessInboxQueue)
    
    def doPausePacketsQueue(self, arg):
        if self.InboxQueueWorker is not None:
            if self.InboxQueueWorker.active():
                self.InboxQueueWorker.cancel()
            self.InboxQueueWorker = None
    
    def doSavePacket(self, NewPacket):
        packetID = NewPacket.PacketID
        pathID, version, packetBlockNum, SupplierNumber, dataORparity = packetid.SplitFull(packetID)
        if dataORparity == 'Data':
            self.OnHandData[SupplierNumber] = True
        elif NewPacket.DataOrParity() == 'Parity':
            self.OnHandParity[SupplierNumber] = True
        filename = os.path.join(settings.getLocalBackupsDir(), packetID)
        dirpath = os.path.dirname(filename)
        if not os.path.exists(dirpath):
            try:
                io._dirs_make(dirpath)
            except:
                io.exception()
        # either way the payload of packet is saved
        if not io.WriteFile(filename, NewPacket.Payload):
            io.log(6, "restore.doSavePacket WARNING unable to write to %s" % filename)
            return
        io.log(6, "restore.doSavePacket %s saved" % packetID)
        if self.packetInCallback is not None:
            self.packetInCallback(self.BackupID, NewPacket)
    
    def doRestoreBlock(self, arg):
        filename = arg
        blockbits = io.ReadBinaryFile(filename)
        if not blockbits:
            self.automat('block-restored', (None, filename))
            return 
        splitindex = blockbits.index(":")
        lengthstring = blockbits[0:splitindex]
        try:
            datalength = int(lengthstring)                                  # real length before raidmake/ECC
            blockdata = blockbits[splitindex+1:splitindex+1+datalength]     # remove padding from raidmake/ECC
            newblock = encrypted_block.Unserialize(blockdata)                      # convert to object
        except:
            datalength = 0
            blockdata = ''
            newblock = None
        self.automat('block-restored', (newblock, filename))
    
    def doWriteRestoredData(self, arg):
        NewBlock = arg[0]
        # SessionKey = crypto.DecryptLocalPK(NewBlock.EncryptedSessionKey)
        # paddeddata = crypto.DecryptWithSessionKey(SessionKey, NewBlock.EncryptedData)
        # newlen = int(NewBlock.Length)
        # data = paddeddata[:newlen]
        data = NewBlock.Data()
        # Add to the file where all the data is going
        try:
            # self.File.write(data)
            os.write(self.File, data)
        except:
            io.exception()
        if self.blockRestoredCallback is not None:
            self.blockRestoredCallback(self.BackupID, NewBlock)
    
    def doDeleteAllRequests(self, arg):
        io_throttle.DeleteBackupRequests(self.BackupID)
                                         
    def doDeleteBlockRequests(self, arg):
        io_throttle.DeleteBackupRequests(self.BackupID + "-" + str(self.BlockNumber))

    def doRemoveTempFile(self, arg):
        tmpfile.throw_out(arg[1], 'block restored')

    def doCloseFile(self, arg):
        # self.File.close()
        os.close(self.File)
    
    def doReportAborted(self, arg):
        io.log(6, "restore.doReportAborted " + self.BackupID)
        self.Done = True
        self.MyDeferred.callback(self.BackupID+' aborted')
        events.info('restore', '%s restoring were aborted' % self.BackupID)
    
    def doReportFailed(self, arg):
        io.log(6, "restore.doReportFailed ERROR - the block does not look good")
        self.Done = True
        self.MyDeferred.errback(Exception(self.BackupID+' failed'))
        events.notify('restore', '%s failed to restore block number %d' % (self.BackupID, self.BlockNumber))
    
    def doReportDone(self, arg):
        # io.log(6, "restore.doReportDone - restore has finished. All is well that ends well !!!")
        self.Done = True
        self.MyDeferred.callback(self.BackupID+' done')
        events.info('restore', '%s restored successfully' % self.BackupID)
    
    def doDestroyMe(self, arg):
        automat.objects().pop(self.index)
        collected = gc.collect()
        # io.log(6, 'restore.doDestroyMe collected %d objects' % collected)

    def _blockRestoreResult(self, restored_blocks, filename):
        self.automat('raid-done', filename)

    def PacketCameIn(self, NewPacket, state):
        if state == 'received':
            self.InboxPacketsQueue.append(NewPacket)

    def ProcessInboxQueue(self):
        if len(self.InboxPacketsQueue) > 0:
            NewPacket = self.InboxPacketsQueue.pop(0)
            self.automat('packet-came-in', NewPacket)
        self.InboxQueueWorker = reactor.callLater(self.InboxQueueDelay, self.ProcessInboxQueue)
    
    def SetPacketInCallback(self, cb):
        self.packetInCallback = cb

    def SetBlockRestoredCallback(self, cb):
        self.blockRestoredCallback = cb

    def Abort(self): # for when user clicks the Abort restore button on the gui
        io.log(4, "restore.Abort " + self.BackupID)
        self.AbortState = True

