import os
import sys

from twisted.internet import reactor

if __name__ == "__main__":
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

from logs import lg

from lib import misc
from lib import settings
from lib import bpio
from lib import tmpfile

from p2p import backup_tar
from p2p import backup_fs
from p2p import backup
from p2p import restore

from raid import raid_worker

#------------------------------------------------------------------------------ 

def backup_done(bid, result):
    from crypt import signed
    try:
        os.mkdir(os.path.join(settings.getLocalBackupsDir(), bid+'.out'))
    except:
        pass
    for filename in os.listdir(os.path.join(settings.getLocalBackupsDir(), bid)):
        filepath = os.path.join(settings.getLocalBackupsDir(), bid, filename)
        payld = str(bpio.ReadBinaryFile(filepath))
        outpacket = signed.Packet(
            'Data', 
            misc.getLocalID(), 
            misc.getLocalID(), 
            filename, 
            payld, 
            'http://megafaq.ru/cvps1010.xml')
        newfilepath = os.path.join(settings.getLocalBackupsDir(), 
                                   bid+'.out', filename)
        bpio.AtomicWriteFile(newfilepath, outpacket.Serialize())
    # Assume we delivered all pieces from ".out" to suppliers and lost original data
    # Then we requested the data back and got it into ".inp"
    try:
        os.mkdir(os.path.join(settings.getLocalBackupsDir(), bid+'.inp'))
    except:
        pass
    for filename in os.listdir(os.path.join(settings.getLocalBackupsDir(), bid+'.out')):
        filepath = os.path.join(settings.getLocalBackupsDir(), bid+'.out', filename)
        data = bpio.ReadBinaryFile(filepath)
        inppacket = signed.Unserialize(data)
        assert inppacket.Valid()
        newfilepath = os.path.join(settings.getLocalBackupsDir(), 
                                   bid+'.inp', filename)
        bpio.AtomicWriteFile(newfilepath, inppacket.Payload)
    # Now do restore from input data
    backupID = bid+'.inp'
    outfd, tarfilename = tmpfile.make('restore', '.tar.gz', backupID.replace('/','_')+'_')
    r = restore.restore(backupID, outfd)
    r.MyDeferred.addBoth(restore_done, tarfilename)
    reactor.callLater(1, r.automat, 'init')
        
def restore_done(x, tarfilename):
    backupID, result = x.split(' ')
    print backupID, result
    print tarfilename
    reactor.stop()

def main():
    sourcePath = sys.argv[1]
    backupID = sys.argv[2]
    lg.set_debug_level(24)
    compress_mode = 'none' # 'gz' 
    raid_worker.A('init')
    backupPath = backup_fs.MakeLocalDir(settings.getLocalBackupsDir(), backupID)
    if bpio.pathIsDir(sourcePath):
        backupPipe = backup_tar.backuptar(sourcePath, compress=compress_mode)
    else:    
        backupPipe = backup_tar.backuptarfile(sourcePath, compress=compress_mode)
    backupPipe.make_nonblocking()

    job = backup.backup(backupID, backupPipe, backup_done)
    reactor.callLater(1, job.automat, 'start')
    reactor.run()
    
    
if __name__ == "__main__":
    main()
    
    
    