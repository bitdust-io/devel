#!/usr/bin/python
#backup_control.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: backup_control

A high level functions to manage backups.
Keeps track of current ``Jobs`` and ``Tasks``.
The "Jobs" dictionary keeps already started backups ( by backupID ) objects, see ``p2p.backup`` module.
"Tasks" is a list of path IDs to start backups in the future, as soon as some "Jobs" gets finished.
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 14

#------------------------------------------------------------------------------ 

import os
import sys
import time
import cStringIO

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor backup_db.py')

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio
from lib import misc
from system import tmpfile
from system import dirsize

from contacts import contactsdb

from lib import packetid
from lib import nameurl

from main import settings

from transport import callback

from raid import eccmap

from crypt import encrypted
from crypt import key

from web import control

import backup_fs
import backup_matrix

#------------------------------------------------------------------------------ 

MAXIMUM_JOBS_STARTED = 1 # let's do only one backup at once for now

_Jobs = {}   # here are already started backups ( by backupID )
_Tasks = []  # here are tasks to start backups in the future ( pathID )
_LastTaskNumber = 0   
_RevisionNumber = 0
_LoadingFlag = False  
_TaskStartedCallbacks = {}
_TaskFinishedCallbacks = {}

#------------------------------------------------------------------------------ 

def jobs():
    """
    Mutator method to access ``Jobs`` dictionary.
    """
    global _Jobs
    return _Jobs

def tasks():
    """
    Mutator method to access ``Tasks`` list.
    """
    global _Tasks
    return _Tasks

def revision():
    """
    Mutator method to access current software revision number.
    """
    global _RevisionNumber
    return _RevisionNumber

def commit(new_revision_number=None):
    """
    Need to be called after any changes in the index database.
    This increase revision number by 1 or set ``new_revision_number``. 
    """
    global _RevisionNumber
    if new_revision_number:
        _RevisionNumber = new_revision_number
    else:
        _RevisionNumber += 1

#------------------------------------------------------------------------------ 

def init():
    """
    Must be called before other methods here.
    Load index database from file .bitdust/metadata/index.
    """
    lg.out(4, 'backup_control.init')
    Load()

def shutdown():
    """
    Called for the correct completion of all things.
    """
    lg.out(4, 'backup_control.shutdown')
    
#------------------------------------------------------------------------------ 

def WriteIndex(filepath=None):
    """
    Write index data base to the local file .bitdust/metadata/index.
    """
    global _LoadingFlag
    if _LoadingFlag:
        return
    if filepath is None:
        filepath = settings.BackupIndexFilePath()
    src = '%d\n' % revision()
    src += backup_fs.Serialize()
    return bpio.AtomicWriteFile(filepath, src)

def ReadIndex(inpt):
    """
    Read index data base, ``input`` is a ``cStringIO.StringIO`` object which keeps the data.
    This is a simple text format, see ``p2p.backup_fs.Serialize()`` method.
    The first line keeps revision number. 
    """
    global _LoadingFlag
    if _LoadingFlag:
        return False
    _LoadingFlag = True
    try:
        new_revision = int(inpt.readline().rstrip('\n'))
    except:
        _LoadingFlag = False
        lg.exc()
        return False
    backup_fs.Clear()
    count = backup_fs.Unserialize(inpt)
    # local_site.update_backup_fs(backup_fs.ListAllBackupIDsSQL())
    commit(new_revision)
    _LoadingFlag = False
    return True

def Load(filepath=None):
    """
    This load the data from local file and call ``ReadIndex()`` method. 
    """
    global _LoadingFlag
    if _LoadingFlag:
        return False
    if filepath is None:
        filepath = settings.BackupIndexFilePath()
    if not os.path.isfile(filepath):
        lg.warn('file %s not exist' % filepath)
        WriteIndex(filepath)
        # return False
    src = bpio.ReadTextFile(filepath)
    if not src:
        lg.out(2, 'backup_control.Load ERROR reading file %s' % filepath)
        return False
    inpt = cStringIO.StringIO(src)
    ret = ReadIndex(inpt)
    inpt.close()
    backup_fs.Scan()
    backup_fs.Calculate()
    return ret

def Save(filepath=None):
    """
    Save index data base to local file ( call ``WriteIndex()`` ) and restart "backup_db_keeper()" state machine.
    """
    global _LoadingFlag
    if _LoadingFlag:
        return False
    commit()
    WriteIndex(filepath)
    import backup_db_keeper
    backup_db_keeper.A('restart')

#------------------------------------------------------------------------------ 

def IncomingSupplierListFiles(newpacket):
    """
    Called by ``p2p.p2p_service`` when command "Files" were received from one of our suppliers.
    This is an answer from given supplier (after our request) to get a list of our files stored on his machine.
    """
    from p2p import p2p_service
    supplier_idurl = newpacket.OwnerID
    num = contactsdb.supplier_position(supplier_idurl)
    if num < -1:
        lg.out(2, 'backup_control.IncomingSupplierListFiles ERROR unknown supplier: %s' % supplier_idurl)
        return
    src = p2p_service.UnpackListFiles(newpacket.Payload, settings.ListFilesFormat())
    backups2remove, paths2remove = backup_matrix.ReadRawListFiles(num, src)
    from customer import list_files_orator
    list_files_orator.IncomingListFiles(newpacket)
    backup_matrix.SaveLatestRawListFiles(supplier_idurl, src)
    if len(backups2remove) > 0:
        p2p_service.RequestDeleteListBackups(backups2remove)
    if len(paths2remove) > 0:
        p2p_service.RequestDeleteListPaths(paths2remove)
    del backups2remove
    del paths2remove
    lg.out(8, 'backup_control.IncomingSupplierListFiles from [%s] %s bytes long' % (
        nameurl.GetName(supplier_idurl), len(newpacket.Payload)))
 
def IncomingSupplierBackupIndex(newpacket):
    """
    Called by ``p2p.p2p_service`` when a remote copy of our local index data base ( in the "Data" packet )
    is received from one of our suppliers. The index is also stored on suppliers to be able to restore it.   
    """
    b = encrypted.Unserialize(newpacket.Payload)
    if b is None:
        lg.out(2, 'backup_control.IncomingSupplierBackupIndex ERROR reading data from %s' % newpacket.RemoteID)
        return
    try:
        session_key = key.DecryptLocalPK(b.EncryptedSessionKey)
        padded_data = key.DecryptWithSessionKey(session_key, b.EncryptedData)
        input = cStringIO.StringIO(padded_data[:int(b.Length)])
        supplier_revision = input.readline().rstrip('\n')
        if supplier_revision:
            supplier_revision = int(supplier_revision)
        else:
            supplier_revision = -1
        input.seek(0)
    except:
        lg.out(2, 'backup_control.IncomingSupplierBackupIndex ERROR reading data from %s' % newpacket.RemoteID)
        lg.out(2, '\n' + padded_data)
        lg.exc()
        try:
            input.close()
        except:
            pass
        return
    if revision() < supplier_revision:
        ReadIndex(input)
        backup_fs.Scan()
        backup_fs.Calculate()
        WriteIndex()
        control.request_update()
        lg.out(2, 'backup_control.IncomingSupplierBackupIndex updated to revision %d from %s' % (
            revision(), newpacket.RemoteID))
    input.close()
    # backup_db_keeper.A('incoming-db-info', newpacket)
        
#------------------------------------------------------------------------------ 

def DeleteAllBackups():
    """
    Remove all backup IDs from index data base, see ``DeleteBackup()`` method.
    """
    # prepare a list of all known backup IDs
    all = set(backup_fs.ListAllBackupIDs())
    all.update(backup_matrix.GetBackupIDs(remote=True, local=True))
    lg.out(4, 'backup_control.DeleteAllBackups %d ID\'s to kill' % len(all))
    # delete one by one
    for backupID in all:
        DeleteBackup(backupID, saveDB=False, calculate=False)
    # scan all files
    backup_fs.Scan()
    # check and calculate used space
    backup_fs.Calculate()
    # save the index
    Save()
    # refresh the GUI
    control.request_update()

def DeleteBackup(backupID, removeLocalFilesToo=True, saveDB=True, calculate=True):
    """
    This removes a single backup ID completely. Perform several operations:
    
        1) abort backup if it just started and is running at the moment
        2) if we requested for files for this backup we do not need it anymore - remove 'Data' requests
        3) remove interests in transport_control, see ``lib.transport_control.DeleteBackupInterest()``
        4) remove that ID from the index data base
        5) remove local files for this backup ID
        6) remove all remote info for this backup from the memory, see ``p2p.backup_matrix.EraseBackupRemoteInfo()``
        7) also remove local info from memory, see ``p2p.backup_matrix.EraseBackupLocalInfo()``
        8) stop any rebuilding, we will restart it soon 
        9) check and calculate used space
        10) save the modified index data base, soon it will be synchronized with "backup_db_keeper()" state machine  
    """
    from customer import io_throttle
    import backup_rebuilder
    lg.out(8, 'backup_control.DeleteBackup ' + backupID)
    # if the user deletes a backup, make sure we remove any work we're doing on it
    # abort backup if it just started and is running at the moment
    AbortRunningBackup(backupID)
    # if we requested for files for this backup - we do not need it anymore
    io_throttle.DeleteBackupRequests(backupID)
    io_throttle.DeleteBackupSendings(backupID)
    # remove interests in transport_control
    callback.delete_backup_interest(backupID)
    # mark it as being deleted in the db, well... just remove it from the index now
    if not backup_fs.DeleteBackupID(backupID):
        return False
    # finally remove local files for this backupID
    if removeLocalFilesToo:
        backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), backupID)
    # remove all remote info for this backup from the memory 
    backup_matrix.EraseBackupRemoteInfo(backupID)
    # also remove local info
    backup_matrix.EraseBackupLocalInfo(backupID)
    # stop any rebuilding, we will restart it soon
    backup_rebuilder.RemoveAllBackupsToWork()
    backup_rebuilder.SetStoppedFlag()
    # check and calculate used space
    if calculate:
        backup_fs.Scan()
        backup_fs.Calculate()
    # in some cases we want to save the DB later 
    if saveDB:
        Save()
        control.request_update()
    return True
    
def DeletePathBackups(pathID, removeLocalFilesToo=True, saveDB=True, calculate=True):
    """
    This removes all backups of given path ID.
    Doing same operations as ``DeleteBackup()``.
    """
    import backup_rebuilder
    from customer import io_throttle
    # get the working item
    item = backup_fs.GetByID(pathID)
    if item is None:
        return False
    # this is a list of all known backups of this path 
    versions = item.list_versions()
    for version in versions:
        backupID = pathID + '/' + version
        # abort backup if it just started and is running at the moment
        AbortRunningBackup(backupID)
        # if we requested for files for this backup - we do not need it anymore
        io_throttle.DeleteBackupRequests(backupID)
        io_throttle.DeleteBackupSendings(backupID)
        # remove interests in transport_control
        callback.delete_backup_interest(backupID)
        # remove local files for this backupID
        if removeLocalFilesToo:
            backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), backupID)
        # remove remote info for this backup from the memory 
        backup_matrix.EraseBackupLocalInfo(backupID)
        # also remove local info
        backup_matrix.EraseBackupLocalInfo(backupID)
        # finally remove this backup from the index
        item.delete_version(version)
        # lg.out(8, 'backup_control.DeletePathBackups ' + backupID)
    # stop any rebuilding, we will restart it soon
    backup_rebuilder.RemoveAllBackupsToWork()
    backup_rebuilder.SetStoppedFlag()
    # check and calculate used space
    if calculate:
        backup_fs.Scan()
        backup_fs.Calculate()
    # save the index if needed
    if saveDB:
        Save()
        control.request_update()
    return True

#------------------------------------------------------------------------------ 

def NewTaskNumber():
    """
    A method to create a unique number for new task.
    It just increments a variable in memory and returns it.
    """
    global _LastTaskNumber
    _LastTaskNumber += 1
    return _LastTaskNumber

class Task():
    """
    A class to represent a ``Task`` - a path to be backed up as soon as other backups will be finished.
    All tasks are stored in the list, see ``tasks()`` method. 
    """
    def __init__(self, pathID, localPath=None):
        self.number = NewTaskNumber()                   # index number for the task
        self.pathID = pathID                            # source path to backup
        self.localPath = localPath 
        self.created = time.time()
        
    def __repr__(self):
        """
        Return a string like "Task-5: 0/1/2/3".
        """
        return 'Task-%d: %s' % (self.number, self.pathID)
       
    #--- !!! STARTING BACKUP HERE !!! --- 
    def run(self):
        """
        Runs a new ``Job`` from that ``Task``.
        Called from ``RunTasks()`` method if it is possible to start a new task -
        the maximum number of simultaneously running ``Jobs`` is limited.  
        """
        import backup_tar
        import backup
        iter_and_path = backup_fs.WalkByID(self.pathID)
        if iter_and_path is None:
            lg.out(4, 'backup_control.Task.run ERROR %s not found in the index' % self.pathID)
            # self.defer.callback('error', self.pathID)
            return
        itemInfo, sourcePath = iter_and_path
        if isinstance(itemInfo, dict):
            try:
                itemInfo = itemInfo[backup_fs.INFO_KEY]
            except:
                lg.exc()
                return
        if self.localPath and self.localPath != sourcePath:
            lg.warn('local path were changed: %s -> %s' % (self.localPath, sourcePath))
        self.localPath = sourcePath
        if not bpio.pathExist(sourcePath):
            lg.warn('path not exist: %s' % sourcePath)
            reactor.callLater(0, OnTaskFailed, self.pathID, 'not exist')
            return
        dataID = misc.NewBackupID()
        if itemInfo.has_version(dataID):
            # ups - we already have same version
            # let's add 1,2,3... to the end to make absolutely unique version ID
            i = 1
            while itemInfo.has_version(dataID+str(i)):
                i += 1
            dataID += str(i)
        backupID = self.pathID + '/' + dataID
        try:
            backupPath = backup_fs.MakeLocalDir(settings.getLocalBackupsDir(), backupID)
        except:
            lg.exc()
            lg.out(4, 'backup_control.Task.run ERROR creating destination folder for %s' % self.pathID)
            # self.defer.callback('error', self.pathID)
            return 
        compress_mode = 'bz2' # 'none' # 'gz'
        if bpio.pathIsDir(sourcePath):
            backupPipe = backup_tar.backuptar(sourcePath, compress=compress_mode)
        else:    
            backupPipe = backup_tar.backuptarfile(sourcePath, compress=compress_mode)
        backupPipe.make_nonblocking()
        job = backup.backup(
            backupID, backupPipe, 
            OnJobDone, OnBackupBlockReport, 
            settings.getBackupBlockSize(),
            sourcePath)
        jobs()[backupID] = job
        itemInfo.add_version(dataID)
        if itemInfo.type in [ backup_fs.PARENT, backup_fs.DIR ]:
            dirsize.ask(sourcePath, OnFoundFolderSize, (self.pathID, dataID))
        else:
            jobs()[backupID].totalSize = os.path.getsize(sourcePath)
        jobs()[backupID].automat('start')
        reactor.callLater(0, FireTaskStartedCallbacks, self.pathID, dataID)
        lg.out(4, 'backup_control.Task.run %s [%s], size=%d, %s' % (
            self.pathID, dataID, itemInfo.size, sourcePath))
    
#------------------------------------------------------------------------------ 
        
def PutTask(pathID, localPath=None):
    """
    Creates a new ``Task`` and append it to the list of tasks.  
    """
    t = Task(pathID, localPath)
    tasks().append(t)
    return t.number

def HasTask(pathID):
    """
    Looks for path ID in the tasks list.
    """
    for task in tasks():
        if task.pathID == pathID:
            return True
    return False 

def DeleteAllTasks():
    """
    Clear the tasks list.
    """
    global _Tasks
    _Tasks = []
    
def RunTasks():
    """
    Checks current jobs and run a one task if it is possible.
    """
    if len(tasks()) == 0:
        return
    if len(jobs()) >= MAXIMUM_JOBS_STARTED:
        return
    T = tasks().pop(0)
    T.run()

#------------------------------------------------------------------------------ 

def OnFoundFolderSize(pth, sz, arg):
    """
    This is a callback, fired from ``lib.dirsize.ask()`` method after finish calculating of folder size. 
    """
    try:
        pathID, version = arg
        backupID = pathID + '/' + version
        item = backup_fs.GetByID(pathID)
        if item:
            item.set_size(sz)
        job = GetRunningBackupObject(backupID)
        if job:
            job.totalSize = sz
        if _Debug:
            lg.out(_DebugLevel, 'backup_control.OnFoundFolderSize %s %d' % (backupID, sz))
    except:
        lg.exc()
        
#------------------------------------------------------------------------------ 

def OnJobDone(backupID, result):
    """
    A callback method fired when backup is finished.
    Here we need to save the index data base. 
    """
    import backup_rebuilder
    from customer import io_throttle
    lg.out(4, '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    lg.out(4, 'backup_control.OnJobDone [%s] %s, %d more tasks' % (backupID, result, len(tasks())))
    jobs().pop(backupID)
    pathID, version = packetid.SplitBackupID(backupID)
    if result == 'done':
        maxBackupsNum = settings.getBackupsMaxCopies()
        if maxBackupsNum:
            item = backup_fs.GetByID(pathID)
            if item: 
                versions = item.list_versions(sorted=True, reverse=True)
                if len(versions) > maxBackupsNum: 
                    for version in versions[maxBackupsNum:]:
                        item.delete_version(version)
                        backupID = pathID+'/'+version
                        backup_rebuilder.RemoveBackupToWork(backupID)
                        io_throttle.DeleteBackupRequests(backupID)
                        io_throttle.DeleteBackupSendings(backupID)
                        callback.delete_backup_interest(backupID)
                        backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), backupID)
                        backup_matrix.EraseBackupLocalInfo(backupID)
                        backup_matrix.EraseBackupLocalInfo(backupID)
        backup_fs.ScanID(pathID)
        backup_fs.Calculate()
        Save()
        control.request_update()
        #TODO: check used space, if we have over use - stop all tasks immediately
        backup_matrix.RepaintBackup(backupID)
    elif result == 'abort':
        DeleteBackup(backupID)
    if len(tasks()) == 0:   
        # do we really need to restart backup_monitor after each backup?
        # if we have a lot tasks started this will produce a lot unneeded actions
        # will be smarter to restart it once we finish all tasks
        # because user will probable leave BitDust working after starting a long running operation
        import backup_monitor
        backup_monitor.A('restart') 
    RunTasks()
    reactor.callLater(0, FireTaskFinishedCallbacks, pathID, version, result)
    
def OnTaskFailed(pathID, result):
    """
    Called when backup process get failed somehow.
    """
    lg.out(4, 'backup_control.OnTaskFailed [%s] %s, %d more tasks' % (pathID, result, len(tasks())))
    RunTasks()
    reactor.callLater(0, FireTaskFinishedCallbacks, pathID, None, result)
    
def OnBackupBlockReport(backupID, blockNum, result):
    """
    Called for every finished block during backup process.
        :param newblock: this is a ``p2p.encrypted_block.encrypted_block`` instance
        :param num_suppliers: number of suppliers which is used for that backup
        
    """
    backup_matrix.LocalBlockReport(backupID, blockNum, result)

#------------------------------------------------------------------------------ 

def AddTaskStartedCallback(pathID, callback):
    """
    You can catch a moment when given ``Task`` were started.
    Call this method to provide a callback method to handle.
    """
    global _TaskStartedCallbacks
    if not _TaskStartedCallbacks.has_key(pathID):
        _TaskStartedCallbacks[pathID] = []
    _TaskStartedCallbacks[pathID].append(callback)
   
def AddTaskFinishedCallback(pathID, callback):
    """
    You can also catch a moment when the whole ``Job`` is done and backup process were finished or failed.
    """
    global _TaskFinishedCallbacks
    if not _TaskFinishedCallbacks.has_key(pathID):
        _TaskFinishedCallbacks[pathID] = []
    _TaskFinishedCallbacks[pathID].append(callback)
    
def FireTaskStartedCallbacks(pathID, version):
    """
    This runs callbacks for given path ID when that ``Job`` is started.
    """
    global _TaskStartedCallbacks
    for cb in _TaskStartedCallbacks.get(pathID, []):
        cb(pathID, version)
    _TaskStartedCallbacks.pop(pathID, None)

def FireTaskFinishedCallbacks(pathID, version, result):
    """
    This runs callbacks for given path ID when that ``Job`` is done or failed.
    """
    global _TaskFinishedCallbacks
    for cb in _TaskFinishedCallbacks.get(pathID, []):
        cb(pathID, version, result)
    _TaskFinishedCallbacks.pop(pathID, None)

#------------------------------------------------------------------------------ 

def StartSingle(pathID, localPath=None):
    """
    A high level method to start a backup of single file or folder.    
    """
    import backup_monitor
    PutTask(pathID, localPath)
    reactor.callLater(0, RunTasks)
    reactor.callLater(0, backup_monitor.A, 'restart')

def StartRecursive(pathID, localPath=None):
    """
    A high level method to start recursive backup of given path.
    This is will traverse all paths below this ID in the 'tree' and add tasks for them.  
    """
    import backup_monitor
    startedtasks = set()
    def visitor(path_id, path, info):
        if info.type == backup_fs.FILE:
            if path_id.startswith(pathID):
                PutTask(path_id, path)
                startedtasks.add(path_id)
    backup_fs.TraverseByID(visitor)
    reactor.callLater(0, RunTasks)
    reactor.callLater(0, backup_monitor.A, 'restart')
    lg.out(6, 'backup_control.StartRecursive %s  :  %d tasks started' % (pathID, len(startedtasks)))
    return startedtasks

#------------------------------------------------------------------------------ 

def IsTaskScheduled(pathID):
    """
    """
    return pathID in tasks()

def GetPendingTask(pathID):
    """
    """
    for t in tasks():
        if t.pathID == pathID:
            return t
    return None

def ListPendingTasks():
    """
    """
    return tasks()

#------------------------------------------------------------------------------ 

def IsBackupInProcess(backupID):
    """
    Return True if given backup ID is running and that "job" exists. 
    """
    return jobs().has_key(backupID)

def IsPathInProcess(pathID):
    """
    Return True if some backups is running at the moment of given path.
    """
    for backupID in jobs().keys():
        if backupID.startswith(pathID+'/'):
            return True
    return False 

def HasRunningBackup():
    """
    Return True if at least one backup is running right now.
    """
    return len(jobs()) > 0

def AbortRunningBackup(backupID):
    """
    Call ``abort()`` method of ``p2p.backup.backup`` object - abort the running backup.
    """
    if IsBackupInProcess(backupID):
        jobs()[backupID].abort()
        return True
    return False
        
def AbortAllRunningBackups():
    """
    Abort all running backups :-).
    """
    for backupObj in jobs().values():
        backupObj.abort()
        
def ListRunningBackups():
    """
    List backup IDs of currently running jobs. 
    """
    return jobs().keys()

def GetRunningBackupObject(backupID):
    """
    Return an instance of ``p2p.backup.backup`` class - a running backup object, 
    or None if that ID is not exist in the jobs dictionary.
    """
    return jobs().get(backupID, None)

#------------------------------------------------------------------------------ 
#------------------------------------------------------------------------------ 
#------------------------------------------------------------------------------ 

def test():
    """
    For tests.
    """
#    backup_fs.Calculate()
#    print backup_fs.counter()
#    print backup_fs.numberfiles()
#    print backup_fs.sizefiles()
#    print backup_fs.sizebackups()
    import pprint
    pprint.pprint(backup_fs.fsID())
    pprint.pprint(backup_fs.fs())
    print backup_fs.GetByID('0')
    # pprint.pprint(backup_fs.WalkByID('0/0/2/19/F20140106100849AM'))
    # for pathID, localPath, item in backup_fs.IterateIDs():
    #     print pathID, misc.unicode_to_str_safe(localPath)
    # backup_fs.TraverseByIDSorted(lambda x, y, z: sys.stdout.write('%s %s\n' % (x,misc.unicode_to_str_safe(y))))
    

    
    
def test2():
    """
    For tests.
    """
    # reactor.callLater(1, StartDirRecursive, 'c:/temp')
    reactor.run()
    
#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    bpio.init()
    lg.set_debug_level(20)
    settings.init()
    tmpfile.init(settings.getTempDir())
    contactsdb.init()
    eccmap.init()
    key.InitMyKey()
    init()
    test()





