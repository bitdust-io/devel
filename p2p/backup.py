#!/usr/bin/python
#backup.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: backup

.. raw:: html

    <a href="http://bitpie.net/automats/backup/backup.png" target="_blank">
    <img src="http://bitpie.net/automats/backup/backup.png" style="max-width:100%;">
    </a>

The core module.
The ``backup()`` state machine is doing a bunch of things to create a single backup.

Here is an interfaces between a pipe from something like tar 
and the twisted code for rest of BitPie.NET.

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
    * :red:`read-success`
    * :red:`start`
    * :red:`timer-001sec`
    * :red:`timer-01sec`

"""

import os
import sys
import time
import cStringIO
import gc


try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in backup.py')

from twisted.internet.defer import maybeDeferred

if __name__ == "__main__":
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

from logs import lg

from lib import misc
from lib import settings
from lib import nonblocking
from lib import tmpfile
from lib import automat

from raid import eccmap
from raid import raid_worker

from crypt import encrypted
from crypt import key

import data_sender
import events


#-------------------------------------------------------------------------------

class backup(automat.Automat):
    """
    A class to run the backup process, data is read from pipe. 
    """

    timers = {
        'timer-01sec': (0.1, ['RAID']),
        'timer-001sec': (0.01, ['READ']),
        }
    
    def __init__(self, backupID, pipe, finishCallback=None, blockResultCallback=None, blockSize=None,): #  resultDeferred=None
        self.backupID = backupID
        self.eccmap = eccmap.Current()
        self.pipe = pipe
        self.blockSize = blockSize
        if self.blockSize is None:
            self.blockSize = settings.getBackupBlockSize()
        self.ask4abort = False
        self.stateEOF = False
        self.stateReading = False
        self.closed = False
        self.currentBlockData = cStringIO.StringIO()
        self.currentBlockSize = 0
        self.workBlocks = {}
        self.blockNumber = 0
        self.dataSent = 0
        self.blocksSent = 0
        self.finishCallback = finishCallback
        self.blockResultCallback = blockResultCallback
        automat.Automat.__init__(self, 'backup_%s' % self.backupID, 'AT_STARTUP', 14)
        # lg.out(6, 'backup.__init__ %s %s %d' % (self.backupID, self.eccmap, self.blockSize,))

    def abort(self):
        """
        This method should stop this backup by killing the pipe process.
        """
        lg.out(4, 'backup.abort id='+str(self.backupID))
        self.ask4abort = True
        try:
            self.pipe.kill()
        except:
            pass
        
    #------------------------------------------------------------------------------ 
        
    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start' :
                self.state = 'READ'
                self.doInit(arg)
                self.doFirstBlock(arg)
        #---READ---
        elif self.state == 'READ':
            if event == 'read-success' and not self.isReadingNow(arg) and ( self.isBlockReady(arg) or self.isEOF(arg) ) :
                self.state = 'ENCRYPT'
                self.doEncryptBlock(arg)
            elif event == 'block-raid-done' :
                self.doPopBlock(arg)
                self.doBlockReport(arg)
                data_sender.A('new-data')
            elif ( event == 'read-success' or event == 'timer-001sec' ) and self.isAborted(arg) :
                self.state = 'ABORTED'
                self.doClose(arg)
                self.doReport(arg)
                self.doDestroyMe(arg)
            elif ( event == 'read-success' or event == 'timer-001sec' ) and not self.isAborted(arg) and self.isPipeReady(arg) and not self.isEOF(arg) and not self.isReadingNow(arg) and not self.isBlockReady(arg) :
                self.doRead(arg)
        #---RAID---
        elif self.state == 'RAID':
            if ( event == 'timer-01sec' or event == 'block-raid-done' or event == 'block-raid-started' ) and self.isAborted(arg) :
                self.state = 'ABORTED'
                self.doClose(arg)
                self.doReport(arg)
                self.doDestroyMe(arg)
            elif event == 'block-raid-done' and not self.isMoreBlocks(arg) and not self.isAborted(arg) :
                self.state = 'DONE'
                self.doPopBlock(arg)
                self.doBlockReport(arg)
                data_sender.A('new-data')
                self.doClose(arg)
                self.doReport(arg)
                self.doDestroyMe(arg)
            elif event == 'block-raid-started' and not self.isEOF(arg) and not self.isAborted(arg) :
                self.state = 'READ'
                self.doNextBlock(arg)
                self.doRead(arg)
            elif event == 'block-raid-done' and self.isMoreBlocks(arg) and not self.isAborted(arg) :
                self.doPopBlock(arg)
                self.doBlockReport(arg)
                data_sender.A('new-data')
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---ABORTED---
        elif self.state == 'ABORTED':
            pass
        #---ENCRYPT---
        elif self.state == 'ENCRYPT':
            if event == 'block-raid-done' :
                self.doPopBlock(arg)
                self.doBlockReport(arg)
                data_sender.A('new-data')
            elif event == 'block-encrypted' :
                self.state = 'RAID'
                self.doBlockPushAndRaid(arg)

    def isAborted(self, arg):
        """
        Return current value of ``ask4abort`` flag.
        """
        return self.ask4abort
         
    def isPipeReady(self, arg):
        """
        Return True if ``pipe`` object exist and is ready for reading a the new chunk of data. 
        """
        return self.pipe is not None and self.pipe.state() in [nonblocking.PIPE_CLOSED, nonblocking.PIPE_READY2READ]
    
    def isBlockReady(self, arg):
        return self.currentBlockSize >= self.blockSize
    
    def isEOF(self, arg):
        return self.stateEOF
    
    def isReadingNow(self, arg):
        return self.stateReading

    def isMoreBlocks(self, arg):
        """
        Condition method.
        """
        return len(self.workBlocks) > 1

    def doInit(self, arg):
        """
        Action method.
        """
        events.info('backup', '%s started' % self.backupID)

    def doRead(self, arg):
        def readChunk():
            size = self.blockSize - self.currentBlockSize
            if size < 0:
                lg.out(1, "backup.readChunk ERROR eccmap.nodes=" + str(self.eccmap.nodes()))
                lg.out(1, "backup.readChunk ERROR blockSize=" + str(self.blockSize))
                lg.out(1, "backup.readChunk ERROR currentBlockSize=" + str(self.currentBlockSize))
                raise Exception('size < 0, blockSize=%s, currentBlockSize=%s' % (self.blockSize, self.currentBlockSize))
                return ''
            elif size == 0:
                return ''
            if self.pipe is None:
                raise Exception('backup.pipe is None')
                return ''
            if self.pipe.state() == nonblocking.PIPE_CLOSED:
                lg.out(10, 'backup.readChunk the state is PIPE_CLOSED !!!!!!!!!!!!!!!!!!!!!!!!')
                return ''
            if self.pipe.state() == nonblocking.PIPE_READY2READ:
                newchunk = self.pipe.recv(size)
                if newchunk == '':
                    lg.out(10, 'backup.readChunk pipe.recv() returned empty string')
                return newchunk
            lg.out(1, "backup.readChunk ERROR pipe.state=" + str(self.pipe.state()))
            raise Exception('backup.pipe.state is ' + str(self.pipe.state()))
            return ''
        def readDone(data):
            self.currentBlockData.write(data)
            self.currentBlockSize += len(data)
            self.stateReading = False
            if data == '':
                self.stateEOF = True
            reactor.callLater(0, self.automat, 'read-success')
            #out(12, 'backup.readDone %d bytes' % len(data))
        self.stateReading = True
        maybeDeferred(readChunk).addCallback(readDone)

    def doEncryptBlock(self, arg):
        def _doBlock():
            dt = time.time()
            src = self.currentBlockData.getvalue()
            block = encrypted.Block(
                misc.getLocalID(),
                self.backupID,
                self.blockNumber,
                key.NewSessionKey(),
                key.SessionKeyType(),
                self.stateEOF,
                src,)
            del src
            lg.out(12, 'backup.doEncryptBlock blockNumber=%d size=%d atEOF=%s dt=%s' % (
                self.blockNumber, self.currentBlockSize, self.stateEOF, str(time.time()-dt)))
            return block
        maybeDeferred(_doBlock).addCallback(
            lambda block: self.automat('block-encrypted', block),)

    def doBlockPushAndRaid(self, arg):
        """
        Action method.
        """
        newblock = arg
        fileno, filename = tmpfile.make('raid')
        serializedblock = newblock.Serialize()
        blocklen = len(serializedblock)
        os.write(fileno, str(blocklen) + ":" + serializedblock)
        os.close(fileno)
        self.workBlocks[newblock.BlockNumber] = filename
        dt = time.time()
        task_params = (filename, self.eccmap.name, self.backupID, newblock.BlockNumber, 
                       os.path.join(settings.getLocalBackupsDir(), self.backupID)) 
        raid_worker.add_task('make', task_params, 
            lambda cmd, params, result: self._raidmakeCallback(params, result, dt),)
        self.automat('block-raid-started', newblock)
        lg.out(12, 'backup.doBlockPushAndRaid %s' % newblock.BlockNumber)
        del serializedblock

    def doPopBlock(self, arg):
        """
        Action method.
        """
        blockNumber, result = arg
        filename = self.workBlocks.pop(blockNumber)
        tmpfile.throw_out(filename, 'block raid done')

    def doFirstBlock(self, arg):
        """
        Action method.
        """
        self.dataSent = 0
        self.blocksSent = 0
        self.blockNumber = 0
        self.currentBlockSize = 0
        self.currentBlockData = cStringIO.StringIO()
        
    def doNextBlock(self, arg):
        """
        Action method.
        """
        self.dataSent += self.currentBlockSize
        self.blocksSent += 1
        self.blockNumber += 1
        self.currentBlockData.close() 
        self.currentBlockSize = 0
        self.currentBlockData = cStringIO.StringIO()

    def doBlockReport(self, arg):
        BlockNumber, result = arg
        if self.blockResultCallback:
            self.blockResultCallback(self.backupID, BlockNumber, result)
  
    def doClose(self, arg):
        self.closed = True
        for filename in self.workBlocks.values():
            tmpfile.throw_out(filename, 'backup aborted')

    def doReport(self, arg):
        if self.ask4abort:
            if self.finishCallback:
                self.finishCallback(self.backupID, 'abort')
            events.info('backup', '%s aborted' % self.backupID)
        else:  
            if self.finishCallback:
                self.finishCallback(self.backupID, 'done')
            events.info('backup', '%s done successfully' % self.backupID)

    def doDestroyMe(self, arg):
        self.currentBlockData.close()
        del self.currentBlockData
        self.destroy()
        collected = gc.collect()
        lg.out(10, 'backup.doDestroyMe [%s] collected %d objects' % (self.backupID, collected))

    def _raidmakeCallback(self, params, result, dt):
        filename, eccmapname, backupID, blockNumber, targetDir = params
        if result is None:
            lg.out(12, 'backup._raidmakeCallback ERROR - result is None :  %r eof=%s dt=%s' % (
                blockNumber, str(self.stateEOF), str(time.time()-dt)))
            events.info('backup', '%s ERROR' % self.backupID)
            self.abort()
        else:
            lg.out(12, 'backup._raidmakeCallback %r %r eof=%s dt=%s' % (
                blockNumber, result, str(self.stateEOF), str(time.time()-dt)))
            self.automat('block-raid-done', (blockNumber, result))

#------------------------------------------------------------------------------ 

def main():
    lg.set_debug_level(24)
    sourcePath = sys.argv[1]
    compress_mode = 'none' # 'gz' 
    backupID = sys.argv[2]
    import backup_tar
    from lib import bpio
    raid_worker.A('init')
    from p2p import backup_fs
    backupPath = backup_fs.MakeLocalDir(settings.getLocalBackupsDir(), backupID)
    if bpio.pathIsDir(sourcePath):
        backupPipe = backup_tar.backuptar(sourcePath, compress=compress_mode)
    else:    
        backupPipe = backup_tar.backuptarfile(sourcePath, compress=compress_mode)
    backupPipe.make_nonblocking()
    def _bk_done(bid, result):
        from crypt import signed
        try:
            os.mkdir(os.path.join(settings.getLocalBackupsDir(), bid+'.out'))
        except:
            pass
        for filename in os.listdir(os.path.join(settings.getLocalBackupsDir(), bid)):
            filepath = os.path.join(settings.getLocalBackupsDir(), bid, filename)
            payld = str(bpio.ReadBinaryFile(filepath))
            newpacket = signed.Packet(
                'Data', 
                misc.getLocalID(), 
                misc.getLocalID(), 
                filename, 
                payld, 
                'http://megafaq.ru/cvps1010.xml')
            newfilepath = os.path.join(settings.getLocalBackupsDir(), bid+'.out', filename)
            bpio.AtomicWriteFile(newfilepath, newpacket.Serialize())
        reactor.stop()
    job = backup(backupID, backupPipe, _bk_done)
    reactor.callLater(1, job.automat, 'start')
    reactor.run()
    
if __name__ == "__main__":
    main()

