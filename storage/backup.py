#!/usr/bin/python
# backup.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (backup.py) is part of BitDust Software.
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
.. module:: backup.

.. raw:: html

    <a href="https://bitdust.io/automats/backup/backup.png" target="_blank">
    <img src="https://bitdust.io/automats/backup/backup.png" style="max-width:100%;">
    </a>

The core module.
The ``backup()`` state machine is doing a bunch of things to create a single backup.

Here is an interfaces between a pipe from something like tar
and the twisted code for rest of BitDust.

Main idea:
   1) when a backup is started a backup object is created
   2) get a file descriptor for the process creating the tar archive
   3) always use select/poll before reading, so never block the main process
   4) also poll to see if more data is needed to create a block
   5) number/name blocks so can be sure what is what when we read back later
   6) encrypt the block data into ``encrypted_blocks``
   7) call ``p2p.raidmake`` to split block and make "Parity" packets (pieces of block)
   8) notify the top level code about new pieces of data to send on suppliers

This state machine controls the data read from the folder,
partition the data into blocks,
block encryption using the private key and the transfer of units to the suppliers.

Reading is performed from the opened ".tar" pipe and must be finished
as soon as empty chunk of data were read from the pipe.
The encrypted data blocks are stored in a temporary folder on the HDD
and deleted (user configurable) as soon as the suppliers have them.

For each block must be received delivery report: positive or negative.

Process will be completed as soon as all data will be read from the folder
and all blocks will receive a delivery report.

EVENTS:
    * :red:`block-encrypted`
    * :red:`block-raid-done`
    * :red:`block-raid-started`
    * :red:`fail`
    * :red:`read-success`
    * :red:`start`
    * :red:`timer-001sec`
    * :red:`timer-01sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import BytesIO

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import sys
import time
import gc

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in backup.py')

from twisted.internet.defer import maybeDeferred

#------------------------------------------------------------------------------

if __name__ == "__main__":
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

#------------------------------------------------------------------------------

from logs import lg

from lib import packetid
from lib import strng

from userid import my_id
from userid import global_id

from system import nonblocking
from system import tmpfile

from main import settings
from main import events

from automats import automat

from raid import eccmap
from raid import raid_worker

from crypt import encrypted
from crypt import key

#-------------------------------------------------------------------------------


class backup(automat.Automat):
    """
    A class to run the backup process, data is read from pipe.
    """

    timers = {
        'timer-01sec': (0.1, ['RAID']),
        'timer-001sec': (0.01, ['READ']),
    }

    def __init__(self,
                 backupID,
                 pipe,
                 finishCallback=None,
                 blockResultCallback=None,
                 blockSize=None,
                 sourcePath=None,
                 keyID=None, ):
        self.backupID = backupID
        _parts = packetid.SplitBackupID(self.backupID)
        self.customerGlobalID = _parts[0]
        self.pathID = _parts[1]
        self.version = _parts[2]
        self.customerIDURL = global_id.GlobalUserToIDURL(self.customerGlobalID)
        self.sourcePath = sourcePath
        self.keyID = keyID
        self.eccmap = eccmap.Current()
        self.pipe = pipe
        self.blockSize = blockSize
        if self.blockSize is None:
            self.blockSize = settings.getBackupBlockSize()
        self.ask4abort = False
        self.terminating = False
        self.stateEOF = False
        self.stateReading = False
        self.closed = False
        self.currentBlockData = BytesIO()
        self.currentBlockSize = 0
        self.workBlocks = {}
        self.blockNumber = 0
        self.dataSent = 0
        self.blocksSent = 0
        self.totalSize = -1
        self.finishCallback = finishCallback
        self.blockResultCallback = blockResultCallback
        automat.Automat.__init__(self, 'backup_%s' % self.version, 'AT_STARTUP', _DebugLevel)

    def init(self):
        """
        """
        self.log_transitions = _Debug

    def A(self, event, *args, **kwargs):
        from customer import data_sender
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'READ'
                self.doInit(*args, **kwargs)
                self.doFirstBlock(*args, **kwargs)
        #---READ---
        elif self.state == 'READ':
            if event == 'read-success' and not self.isReadingNow(*args, **kwargs) and ( self.isBlockReady(*args, **kwargs) or self.isEOF(*args, **kwargs) ):
                self.state = 'ENCRYPT'
                self.doEncryptBlock(*args, **kwargs)
            elif event == 'fail' or ( ( event == 'read-success' or event == 'timer-001sec' ) and self.isAborted(*args, **kwargs) ):
                self.state = 'ABORTED'
                self.doClose(*args, **kwargs)
                self.doReport(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif ( event == 'read-success' or event == 'timer-001sec' ) and not self.isAborted(*args, **kwargs) and self.isPipeReady(*args, **kwargs) and not self.isEOF(*args, **kwargs) and not self.isReadingNow(*args, **kwargs) and not self.isBlockReady(*args, **kwargs):
                self.doRead(*args, **kwargs)
            elif event == 'block-raid-done' and not self.isAborted(*args, **kwargs):
                self.doPopBlock(*args, **kwargs)
                self.doBlockReport(*args, **kwargs)
                data_sender.A('new-data')
        #---RAID---
        elif self.state == 'RAID':
            if event == 'block-raid-done' and not self.isMoreBlocks(*args, **kwargs) and not self.isAborted(*args, **kwargs):
                self.state = 'DONE'
                self.doPopBlock(*args, **kwargs)
                self.doBlockReport(*args, **kwargs)
                data_sender.A('new-data')
                self.doClose(*args, **kwargs)
                self.doReport(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'block-raid-started' and not self.isEOF(*args, **kwargs) and not self.isAborted(*args, **kwargs):
                self.state = 'READ'
                self.doNextBlock(*args, **kwargs)
                self.doRead(*args, **kwargs)
            elif event == 'block-raid-done' and self.isMoreBlocks(*args, **kwargs) and not self.isAborted(*args, **kwargs):
                self.doPopBlock(*args, **kwargs)
                self.doBlockReport(*args, **kwargs)
                data_sender.A('new-data')
            elif event == 'fail' or ( ( event == 'timer-01sec' or event == 'block-raid-done' or event == 'block-raid-started' ) and self.isAborted(*args, **kwargs) ):
                self.state = 'ABORTED'
                self.doClose(*args, **kwargs)
                self.doReport(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---ABORTED---
        elif self.state == 'ABORTED':
            pass
        #---ENCRYPT---
        elif self.state == 'ENCRYPT':
            if event == 'block-encrypted':
                self.state = 'RAID'
                self.doBlockPushAndRaid(*args, **kwargs)
            elif event == 'fail':
                self.state = 'ABORTED'
                self.doClose(*args, **kwargs)
                self.doReport(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'block-raid-done' and not self.isAborted(*args, **kwargs):
                self.doPopBlock(*args, **kwargs)
                self.doBlockReport(*args, **kwargs)
                data_sender.A('new-data')
        return None

    def isAborted(self, *args, **kwargs):
        """
        Return current value of ``ask4abort`` flag.
        """
        return self.ask4abort

    def isPipeReady(self, *args, **kwargs):
        """
        Return True if ``pipe`` object exist and is ready for reading a the new
        chunk of data.
        """
        return self.pipe is not None and self.pipe.state() in [nonblocking.PIPE_CLOSED, nonblocking.PIPE_READY2READ]

    def isBlockReady(self, *args, **kwargs):
        return self.currentBlockSize >= self.blockSize

    def isEOF(self, *args, **kwargs):
        return self.stateEOF

    def isReadingNow(self, *args, **kwargs):
        return self.stateReading

    def isMoreBlocks(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.workBlocks) > 1

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        events.send('backup-started', dict(backup_id=self.backupID))

    def doRead(self, *args, **kwargs):
        """
        Action method.
        """

        def readChunk():
            size = self.blockSize - self.currentBlockSize
            if size < 0:
                lg.out(1, "backup.readChunk ERROR eccmap.nodes=" + str(self.eccmap.nodes()))
                lg.out(1, "backup.readChunk ERROR blockSize=" + str(self.blockSize))
                lg.out(1, "backup.readChunk ERROR currentBlockSize=" + str(self.currentBlockSize))
                raise Exception('size < 0, blockSize=%s, currentBlockSize=%s' % (self.blockSize, self.currentBlockSize))
            elif size == 0:
                return b''
            if self.pipe is None:
                raise Exception('backup.pipe is None')
            if self.pipe.state() == nonblocking.PIPE_CLOSED:
                if _Debug:
                    lg.out(_DebugLevel, 'backup.readChunk the state is PIPE_CLOSED')
                return b''
            if self.pipe.state() == nonblocking.PIPE_EMPTY:
                if _Debug:
                    lg.out(_DebugLevel, 'backup.readChunk the state is PIPE_EMPTY !!!!!!!!!!!!!!!!!!!!!!!!')
                return b''
            if self.pipe.state() == nonblocking.PIPE_READY2READ:
                try:
                    inputtext = self.pipe.recv(size)
                    newchunk = strng.to_bin(inputtext)
                except:
                    lg.err('pipe.recv() failed')
                    lg.exc()
                if newchunk:
                    if _Debug:
                        lg.out(_DebugLevel, 'backup.readChunk pipe.recv() returned %d bytes' % len(newchunk))
                else:
                    if _Debug:
                        lg.out(_DebugLevel, 'backup.readChunk pipe.recv() returned empty string')
                return newchunk
            lg.out(1, "backup.readChunk ERROR pipe.state=" + str(self.pipe.state()))
            raise Exception('backup.pipe.state is ' + str(self.pipe.state()))

        def readDone(data):
            try:
                self.currentBlockData.write(data)
                self.currentBlockSize += len(data)
                self.stateReading = False
            except:
                lg.exc()
                self.automat('fail', None)
                return None
            if not data:
                self.stateEOF = True
            if _Debug:
                lg.out(_DebugLevel + 4, 'backup.readDone %d bytes' % len(data))
            reactor.callLater(0, self.automat, 'read-success')  # @UndefinedVariable
            return data

        def readFailed(err):
            lg.err(err)
            self.automat('fail', err)
            return None

        self.stateReading = True
        d = maybeDeferred(readChunk)
        d.addCallback(readDone)
        d.addErrback(readFailed)

    def doEncryptBlock(self, *args, **kwargs):
        """
        Action method.
        """
        def _doBlock():
            dt = time.time()
            raw_bytes = self.currentBlockData.getvalue()
#             if not raw_bytes:
#                 lg.err('current block data is empty')
#                 raise ValueError('current block data is empty')
            block = encrypted.Block(
                CreatorID=my_id.getLocalID(),
                BackupID=self.backupID,
                BlockNumber=self.blockNumber,
                SessionKey=key.NewSessionKey(),
                SessionKeyType=key.SessionKeyType(),
                LastBlock=self.stateEOF,
                Data=raw_bytes,
                EncryptKey=self.keyID,
            )
            del raw_bytes
            if _Debug:
                lg.out(_DebugLevel, 'backup.doEncryptBlock blockNumber=%d size=%d atEOF=%s dt=%s EncryptKey=%s' % (
                    self.blockNumber, self.currentBlockSize, self.stateEOF, str(time.time() - dt), self.keyID))
            return block

        d = maybeDeferred(_doBlock)
        d.addCallback(lambda block: self.automat('block-encrypted', block))
        d.addErrback(lambda err: self.automat('fail', err))

    def doBlockPushAndRaid(self, *args, **kwargs):
        """
        Action method.
        """
        newblock = args[0]
        if newblock is None:
            self.abort()
            self.automat('fail')
            lg.out(_DebugLevel, 'backup.doBlockPushAndRaid ERROR newblock is empty, terminating=%s' % self.terminating)
            lg.warn('failed to encrypt block, ABORTING')
            return
        if self.terminating:
            self.automat('block-raid-done', (newblock.BlockNumber, None))
            lg.out(_DebugLevel, 'backup.doBlockPushAndRaid SKIP, terminating=True')
            return
        fileno, filename = tmpfile.make('raid', extension='.raid')
        serializedblock = newblock.Serialize()
        blocklen = len(serializedblock)
        os.write(fileno, strng.to_bin(blocklen) + b":" + serializedblock)
        os.close(fileno)
        self.workBlocks[newblock.BlockNumber] = filename
        dt = time.time()
        outputpath = os.path.join(
            settings.getLocalBackupsDir(), self.customerGlobalID, self.pathID, self.version)
        task_params = (filename, self.eccmap.name, self.version, newblock.BlockNumber, outputpath)
        raid_worker.add_task('make', task_params, lambda cmd, params, result: self._raidmakeCallback(params, result, dt))
        self.automat('block-raid-started', newblock)
        del serializedblock
        if _Debug:
            lg.out(_DebugLevel, 'backup.doBlockPushAndRaid %s : start process data from %s to %s, %d' % (
                newblock.BlockNumber, filename, outputpath, id(self.terminating)))

    def doPopBlock(self, *args, **kwargs):
        """
        Action method.
        """
        blockNumber, _ = args[0]
        filename = self.workBlocks.pop(blockNumber)
        tmpfile.throw_out(filename, 'block raid done')

    def doFirstBlock(self, *args, **kwargs):
        """
        Action method.
        """
        self.dataSent = 0
        self.blocksSent = 0
        self.blockNumber = 0
        self.currentBlockSize = 0
        self.currentBlockData = BytesIO()

    def doNextBlock(self, *args, **kwargs):
        """
        Action method.
        """
        self.dataSent += self.currentBlockSize
        self.blocksSent += 1
        self.blockNumber += 1
        self.currentBlockSize = 0
        self.currentBlockData.close()
        self.currentBlockData = BytesIO()

    def doBlockReport(self, *args, **kwargs):
        """
        Action method.
        """
        BlockNumber, result = args[0]
        if self.blockResultCallback:
            self.blockResultCallback(self.backupID, BlockNumber, result)

    def doClose(self, *args, **kwargs):
        """
        Action method.
        """
        self.closed = True
        for filename in self.workBlocks.values():
            tmpfile.throw_out(filename, 'backup aborted')

    def doReport(self, *args, **kwargs):
        """
        Action method.
        """
        if self.ask4abort:
            if self.finishCallback:
                self.finishCallback(self.backupID, 'abort')
            events.send('backup-aborted', dict(backup_id=self.backupID))
        else:
            if self.finishCallback:
                self.finishCallback(self.backupID, 'done')
            events.send('backup-done', dict(backup_id=self.backupID))

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.currentBlockData.close()
        del self.currentBlockData
        self.destroy()
        collected = gc.collect()
        if _Debug:
            lg.out(_DebugLevel, 'backup.doDestroyMe [%s] collected %d objects' % (self.backupID, collected))

    def abort(self):
        """
        This method should stop this backup by killing the pipe process.
        """
        if _Debug:
            lg.out(_DebugLevel, 'backup.abort id %s, %d' % (str(self.backupID), id(self.ask4abort)))
        self.terminating = True
        for blockNumber, filename in self.workBlocks.items():
            lg.warn('aborting raid make worker for block %d in %s' % (blockNumber, filename))
            raid_worker.cancel_task('make', filename)
        lg.warn('killing backup pipe')
        self._kill_pipe()

    def progress(self):
        """
        """
        if self.totalSize <= 0:
            return 0.0
        percent = min(100.0, 100.0 * self.dataSent / self.totalSize)
        return percent

    def _raidmakeCallback(self, params, result, dt):
        filename, eccmapname, backupID, blockNumber, targetDir = params
        if result is None:
            if _Debug:
                lg.out(_DebugLevel, 'backup._raidmakeCallback WARNING - result is None :  %r eof=%s dt=%s' % (
                    blockNumber, str(self.stateEOF), str(time.time() - dt)))
            events.send('backup-aborted', dict(backup_id=self.backupID))
            self._kill_pipe()
        else:
            if _Debug:
                lg.out(_DebugLevel, 'backup._raidmakeCallback %r %r eof=%s dt=%s' % (
                    blockNumber, result, str(self.stateEOF), str(time.time() - dt)))
            self.automat('block-raid-done', (blockNumber, result))

    def _kill_pipe(self):
        if _Debug:
            lg.out(_DebugLevel, 'backup._kill_pipe for %s' % self.backupID)
        self.ask4abort = True
        try:
            self.pipe.kill()
        except:
            pass

#------------------------------------------------------------------------------


def main():
    from system import bpio
    from . import backup_tar
    from . import backup_fs
    lg.set_debug_level(24)
    sourcePath = sys.argv[1]
    compress_mode = 'none'  # 'gz'
    backupID = sys.argv[2]
    raid_worker.A('init')
    backupPath = backup_fs.MakeLocalDir(settings.getLocalBackupsDir(), backupID)
    if bpio.pathIsDir(sourcePath):
        backupPipe = backup_tar.backuptardir(sourcePath, compress=compress_mode)
    else:
        backupPipe = backup_tar.backuptarfile(sourcePath, compress=compress_mode)
    backupPipe.make_nonblocking()

    def _bk_done(bid, result):
        from crypt import signed
        customer, remotePath = packetid.SplitPacketID(bid)
        try:
            os.mkdir(os.path.join(settings.getLocalBackupsDir(), customer, remotePath + '.out'))
        except:
            pass
        for filename in os.listdir(os.path.join(settings.getLocalBackupsDir(), customer, remotePath)):
            filepath = os.path.join(settings.getLocalBackupsDir(), customer, remotePath, filename)
            payld = bpio.ReadBinaryFile(filepath)
            newpacket = signed.Packet(
                'Data',
                my_id.getLocalID(),
                my_id.getLocalID(),
                filename,
                payld,
                'http://megafaq.ru/cvps1010.xml')
            newfilepath = os.path.join(settings.getLocalBackupsDir(), customer, remotePath + '.out', filename)
            bpio.WriteBinaryFile(newfilepath, newpacket.Serialize())
        reactor.stop()  # @UndefinedVariable
    job = backup(backupID, backupPipe, _bk_done)
    reactor.callLater(1, job.automat, 'start')  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable


if __name__ == "__main__":
    main()
