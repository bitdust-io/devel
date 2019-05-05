#!/usr/bin/python
# backup_control.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (backup_control.py) is part of BitDust Software.
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

"""
.. module:: backup_control.

A high level functions to manage backups. Keeps track of current
``Jobs`` and ``Tasks``. The "Jobs" dictionary keeps already started
backups ( by backupID ) objects, see ``p2p.backup`` module. "Tasks" is a
list of path IDs to start backups in the future, as soon as some "Jobs"
gets finished.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
from io import StringIO

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 12

#------------------------------------------------------------------------------

import os
import sys
import time
import pprint


try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor backup_control.py')

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from system import bpio
from system import tmpfile
from system import dirsize

from contacts import contactsdb

from lib import misc
from lib import packetid
from lib import nameurl
from lib import strng
from lib import jsn

from main import settings
from main import events
from main import control

from raid import eccmap

from crypt import encrypted
from crypt import key
from crypt import my_keys

from userid import global_id
from userid import my_id

from services import driver

from storage import backup_fs
from storage import backup_matrix
from storage import backup_tar
from storage import backup

#------------------------------------------------------------------------------

MAXIMUM_JOBS_STARTED = 1  # let's do only one backup at once for now

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


def WriteIndex(filepath=None, encoding='utf-8'):
    """
    Write index data base to the local file .bitdust/metadata/index.
    """
    global _LoadingFlag
    if _LoadingFlag:
        return
    if filepath is None:
        filepath = settings.BackupIndexFilePath()
    json_data = {}
    # json_data = backup_fs.Serialize(to_json=True, encoding=encoding)
    for customer_idurl in backup_fs.known_customers():
        customer_id = global_id.UrlToGlobalID(customer_idurl)
        json_data[customer_id] = backup_fs.Serialize(
            iterID=backup_fs.fsID(customer_idurl),
            to_json=True,
            encoding=encoding,
        )
    src = '%d\n' % revision()
    src += jsn.dumps(
        json_data,
        indent=1,
        separators=(',', ':'),
        encoding=encoding,
    )
    if _Debug:
        lg.out(_DebugLevel, pprint.pformat(json_data))
    return bpio.WriteTextFile(filepath, src)


def ReadIndex(text_data, encoding='utf-8'):
    """
    Read index data base, ``input`` is a ``StringIO.StringIO`` object which
    keeps the data.

    This is a simple text format, see ``p2p.backup_fs.Serialize()``
    method. The first line keeps revision number.
    """
    global _LoadingFlag
    if _LoadingFlag:
        return False
    _LoadingFlag = True
    backup_fs.Clear()
    count = 0
    try:
        json_data = jsn.loads(
            text_data,
            encoding=encoding,
        )
    except:
        lg.exc()
        json_data = text_data
    if _Debug:
        lg.out(_DebugLevel, pprint.pformat(json_data))
    for customer_id in json_data.keys():
        if customer_id == 'items':
            try:
                count = backup_fs.Unserialize(json_data, from_json=True, decoding=encoding)
            except:
                lg.exc()
                return False
        else:
            customer_idurl = global_id.GlobalUserToIDURL(customer_id)
            try:
                count = backup_fs.Unserialize(
                    json_data[customer_id],
                    iter=backup_fs.fs(customer_idurl),
                    iterID=backup_fs.fsID(customer_idurl),
                    from_json=True,
                    decoding=encoding,
                )
            except:
                lg.exc()
                return False
    if _Debug:
        lg.out(_DebugLevel, 'backup_control.ReadIndex %d items loaded' % count)
    # local_site.update_backup_fs(backup_fs.ListAllBackupIDsSQL())
    # commit(new_revision)
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
    src = bpio.ReadTextFile(filepath)
    if not src:
        lg.out(2, 'backup_control.Load ERROR reading file %s' % filepath)
        return False
    inpt = StringIO(src)
    try:
        known_revision = int(inpt.readline().rstrip('\n'))
    except:
        lg.exc()
        return False
    raw_data = inpt.read()
    inpt.close()
    ret = ReadIndex(raw_data)
    if ret:
        commit(known_revision)
        backup_fs.Scan()
        backup_fs.Calculate()
    else:
        lg.warn('catalog index reading failed')
    return ret


def Save(filepath=None):
    """
    Save index data base to local file ( call ``WriteIndex()`` ) and notify
    "index_synchronizer()" state machine.
    """
    global _LoadingFlag
    if _LoadingFlag:
        return False
    commit()
    WriteIndex(filepath)
    if driver.is_on('service_backup_db'):
        from storage import index_synchronizer
        index_synchronizer.A('push')

#------------------------------------------------------------------------------

def IncomingSupplierListFiles(newpacket, list_files_global_id):
    """
    Called when command "Files" were received from one of my suppliers.
    This is an answer from given supplier (after my request) to get a
    list of our files stored on his machine.
    """
    from p2p import p2p_service
    supplier_idurl = newpacket.OwnerID
    # incoming_key_id = newpacket.PacketID.strip().split(':')[0]
    customer_idurl = list_files_global_id['idurl']
    num = contactsdb.supplier_position(supplier_idurl, customer_idurl=customer_idurl)
    if num < -1:
        lg.warn('unknown supplier: %s' % supplier_idurl)
        return False
    from supplier import list_files
    from customer import list_files_orator
    try:
        block = encrypted.Unserialize(
            newpacket.Payload,
            decrypt_key=my_keys.make_key_id(alias='customer', creator_idurl=my_id.getLocalIDURL(), ),
        )
        input_data = block.Data()
    except:
        lg.exc()
        lg.out(2, 'backup_control.IncomingSupplierListFiles ERROR decrypting data from %s' % newpacket)
        return False
    src = list_files.UnpackListFiles(input_data, settings.ListFilesFormat())
    backups2remove, paths2remove, missed_backups = backup_matrix.ReadRawListFiles(num, src)
    list_files_orator.IncomingListFiles(newpacket)
    backup_matrix.SaveLatestRawListFiles(supplier_idurl, src)
    if _Debug:
        lg.out(_DebugLevel, 'backup_control.IncomingSupplierListFiles from [%s]: paths2remove=%d, backups2remove=%d missed_backups=%d' % (
            nameurl.GetName(supplier_idurl), len(paths2remove), len(backups2remove), len(missed_backups)))
    if len(backups2remove) > 0:
        p2p_service.RequestDeleteListBackups(backups2remove)
        if _Debug:
            lg.out(_DebugLevel, '    also sent requests to remove %d backups' % len(backups2remove))
    if len(paths2remove) > 0:
        p2p_service.RequestDeleteListPaths(paths2remove)
        if _Debug:
            lg.out(_DebugLevel, '    also sent requests to remove %d paths' % len(paths2remove))
    if len(missed_backups) > 0:
        from storage import backup_rebuilder
        backup_rebuilder.AddBackupsToWork(missed_backups)
        backup_rebuilder.A('start')
        if _Debug:
            lg.out(_DebugLevel, '    also triggered service_rebuilding with %d missed backups' % len(missed_backups))
    del backups2remove
    del paths2remove
    del missed_backups
    return True


def IncomingSupplierBackupIndex(newpacket):
    """
    Called by ``p2p.p2p_service`` when a remote copy of our local index data
    base ( in the "Data" packet ) is received from one of our suppliers.

    The index is also stored on suppliers to be able to restore it.
    """
    b = encrypted.Unserialize(newpacket.Payload)
    if b is None:
        lg.out(2, 'backup_control.IncomingSupplierBackupIndex ERROR reading data from %s' % newpacket.RemoteID)
        return
    try:
        session_key = key.DecryptLocalPrivateKey(b.EncryptedSessionKey)
        padded_data = key.DecryptWithSessionKey(session_key, b.EncryptedData)
        inpt = StringIO(strng.to_text(padded_data[:int(b.Length)]))
        supplier_revision = inpt.readline().rstrip('\n')
        if supplier_revision:
            supplier_revision = int(supplier_revision)
        else:
            supplier_revision = -1
    except:
        lg.out(2, 'backup_control.IncomingSupplierBackupIndex ERROR reading data from %s' % newpacket.RemoteID)
        lg.exc()
        try:
            inpt.close()
        except:
            pass
        return
    if driver.is_on('service_backup_db'):
        from storage import index_synchronizer
        index_synchronizer.A('index-file-received', (newpacket, supplier_revision))
    if revision() >= supplier_revision:
        inpt.close()
        lg.out(4, 'backup_control.IncomingSupplierBackupIndex SKIP, supplier %s revision=%d, local revision=%d' % (
            newpacket.RemoteID, supplier_revision, revision(), ))
        return
    text_data = inpt.read()
    inpt.close()
    if ReadIndex(text_data):
        commit(supplier_revision)
        backup_fs.Scan()
        backup_fs.Calculate()
        WriteIndex()
        control.request_update()
        lg.out(4, 'backup_control.IncomingSupplierBackupIndex updated to revision %d from %s' % (
            revision(), newpacket.RemoteID))
    else:
        lg.warn('failed to read catalog index from supplier')

#------------------------------------------------------------------------------


def DeleteAllBackups():
    """
    Remove all backup IDs from index data base, see ``DeleteBackup()`` method.
    """
    # prepare a list of all known backup IDs
    all_ids = set(backup_fs.ListAllBackupIDs())
    all_ids.update(backup_matrix.GetBackupIDs(remote=True, local=True))
    lg.out(4, 'backup_control.DeleteAllBackups %d ID\'s to kill' % len(all_ids))
    # delete one by one
    for backupID in all_ids:
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
    10) save the modified index data base, soon it will be synchronized with "index_synchronizer()" state machine
    """
    backupID = global_id.CanonicalID(backupID)
    # if the user deletes a backup, make sure we remove any work we're doing on it
    # abort backup if it just started and is running at the moment
    if AbortRunningBackup(backupID):
        lg.out(8, 'backup_control.DeleteBackup %s is in process, stopping' % backupID)
        return True
    from customer import io_throttle
    from . import backup_rebuilder
    lg.out(8, 'backup_control.DeleteBackup ' + backupID)
    # if we requested for files for this backup - we do not need it anymore
    io_throttle.DeleteBackupRequests(backupID)
    io_throttle.DeleteBackupSendings(backupID)
    # remove interests in transport_control
    # callback.delete_backup_interest(backupID)
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
        control.request_update([('backupID', backupID), ])
    return True


def DeletePathBackups(pathID, removeLocalFilesToo=True, saveDB=True, calculate=True):
    """
    This removes all backups of given path ID
    Doing same operations as ``DeleteBackup()``.
    """
    from . import backup_rebuilder
    from customer import io_throttle
    pathID = global_id.CanonicalID(pathID)
    # get the working item
    customer, remotePath = packetid.SplitPacketID(pathID)
    customer_idurl = global_id.GlobalUserToIDURL(customer)
    item = backup_fs.GetByID(remotePath, iterID=backup_fs.fsID(customer_idurl))
    if item is None:
        return False
    lg.out(8, 'backup_control.DeletePathBackups ' + pathID)
    # this is a list of all known backups of this path
    versions = item.list_versions()
    for version in versions:
        backupID = packetid.MakeBackupID(customer, remotePath, version)
        lg.out(8, '        removing %s' % backupID)
        # abort backup if it just started and is running at the moment
        AbortRunningBackup(backupID)
        # if we requested for files for this backup - we do not need it anymore
        io_throttle.DeleteBackupRequests(backupID)
        io_throttle.DeleteBackupSendings(backupID)
        # remove interests in transport_control
        # callback.delete_backup_interest(backupID)
        # remove local files for this backupID
        if removeLocalFilesToo:
            backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), backupID)
        # remove remote info for this backup from the memory
        backup_matrix.EraseBackupRemoteInfo(backupID)
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
    As soon as task get executed it fires the result call back and removed from the list.
    When task executes a new backup job gets created.
    """

    def __init__(self, pathID, localPath=None, keyID=None):
        self.number = NewTaskNumber()                   # index number for the task
        self.created = time.time()
        self.backupID = None
        self.pathID = None
        self.fullGlobPath = None
        self.fullCustomerID = None
        self.customerGlobID = None
        self.customerIDURL = None
        self.remotePath = None
        self.keyID = None
        self.keyAlias = None
        self.result_defer = Deferred()
        self.result_defer.addCallback(OnTaskExecutedCallback)
        self.result_defer.addErrback(OnTaskFailedCallback)
        parts = self.set_path_id(pathID)
        self.set_key_id(keyID or my_keys.make_key_id(alias=parts['key_alias'], creator_glob_id=parts['customer']))
        self.set_local_path(localPath)
        if _Debug:
            lg.out(_DebugLevel, 'new Task created: %r' % self)
        events.send('backup-task-created', data=dict(
            number=self.number,
            created=self.created,
            backup_id=self.backupID,
            key_id=self.keyID,
            path_id=self.pathID,
            customer_id=self.customerGlobID,
            path=self.remotePath,
            local_path=self.localPath,
            remote_path=self.fullGlobPath,
        ))

    def destroy(self, message=None):
        lg.out(4, 'backup_control.Task-%d.destroy %s -> %s' % (
            self.number, self.localPath, self.backupID))
        if self.result_defer and not self.result_defer.called:
            self.result_defer.cancel()
            self.result_defer = None
        events.send('backup-task-finished', data=dict(
            number=self.number,
            created=self.created,
            backup_id=self.backupID,
            key_id=self.keyID,
            path_id=self.pathID,
            customer_id=self.customerGlobID,
            path=self.remotePath,
            local_path=self.localPath,
            remote_path=self.fullGlobPath,
            message=message,
        ))

    def set_path_id(self, pathID):
        parts = global_id.ParseGlobalID(pathID)
        self.pathID = pathID  # source path to backup
        self.customerGlobID = parts['customer']
        self.customerIDURL = parts['idurl']
        self.remotePath = parts['path']  # here it must be in 0/1/2 form
        if parts['key_alias']:
            self.set_key_id(my_keys.make_key_id(alias=parts['key_alias'], creator_glob_id=self.customerGlobID))
        return parts

    def set_key_id(self, key_id):
        self.keyID = key_id
        self.keyAlias = packetid.KeyAlias(self.keyID)
        self.fullGlobPath = global_id.MakeGlobalID(
            customer=self.customerGlobID, key_alias=self.keyAlias, path=self.remotePath)
        self.fullCustomerID = global_id.MakeGlobalID(
            customer=self.customerGlobID, key_alias=self.keyAlias)

    def set_local_path(self, localPath):
        self.localPath = localPath

    def __repr__(self):
        """
        Return a string like:

            "Task-5: 0/1/2/3 from /home/veselin/Documents/myfile.txt"
        """
        return 'Task-%d(%s from %s)' % (self.number, self.pathID, self.localPath)

#     def _on_job_done(self, backupID, result):
#         reactor.callLater(0, OnJobDone, backupID, result)
#         if self.result_defer is not None:
#             self.result_defer.callback((backupID, result))
#             self.result_defer = None

#     def _on_job_failed(self, backupID, err=None):
#         if self.result_defer is not None:
#             self.result_defer.errback((backupID, err))
#             self.result_defer = None
#         return err

    def run(self):
        """
        Runs a new ``Job`` from that ``Task``.
        """
        iter_and_path = backup_fs.WalkByID(self.remotePath, iterID=backup_fs.fsID(self.customerIDURL))
        if iter_and_path is None:
            lg.out(4, 'backup_control.Task.run ERROR %s not found in the index' % self.remotePath)
            # self.defer.callback('error', self.pathID)
            # self._on_job_failed(self.pathID)
            err = 'remote path "%s" not found in the catalog' % self.remotePath
            OnTaskFailed(self.pathID, err)
            return err
        itemInfo, sourcePath = iter_and_path
        if isinstance(itemInfo, dict):
            try:
                itemInfo = itemInfo[backup_fs.INFO_KEY]
            except:
                lg.exc()
                # self._on_job_failed(self.pathID)
                err = 'catalog item related to "%s" is broken' % self.remotePath
                OnTaskFailed(self.pathID, err)
                return err
        if not self.localPath:
            self.localPath = sourcePath
            lg.out('backup_control.Task.run local path was populated from catalog: %s' % self.localPath)
        if self.localPath != sourcePath:
            lg.warn('local path is differ from catalog: %s != %s' % (self.localPath, sourcePath))
        if not bpio.pathExist(self.localPath):
            lg.warn('path not exist: %s' % self.localPath)
            # self._on_job_failed(self.pathID)
            err = 'local path "%s" not exist' % self.localPath
            OnTaskFailed(self.pathID, err)
            return err
#         if os.path.isfile(self.localPath) and self.localPath != sourcePath:
#             tmpfile.make(name, extension, prefix)
        dataID = misc.NewBackupID()
        if itemInfo.has_version(dataID):
            # ups - we already have same version
            # let's add 1,2,3... to the end to make absolutely unique version ID
            i = 1
            while itemInfo.has_version(dataID + str(i)):
                i += 1
            dataID += str(i)
        self.backupID = packetid.MakeBackupID(
            customer=self.fullCustomerID,
            path_id=self.remotePath,
            version=dataID,
        )
        if self.backupID in jobs():
            lg.warn('backup job %s already started' % self.backupID)
            return 'backup job %s already started' % self.backupID
        try:
            backup_fs.MakeLocalDir(settings.getLocalBackupsDir(), self.backupID)
        except:
            lg.exc()
            lg.out(4, 'backup_control.Task.run ERROR creating destination folder for %s' % self.pathID)
            # self.defer.callback('error', self.pathID)
            # self._on_job_failed(self.backupID)
            err = 'failed creating destination folder for "%s"' % self.backupID
            return OnTaskFailed(self.backupID, err)
        compress_mode = 'bz2'  # 'none' # 'gz'
        arcname = os.path.basename(sourcePath)
        if bpio.pathIsDir(self.localPath):
            backupPipe = backup_tar.backuptardir(self.localPath, arcname=arcname, compress=compress_mode)
        else:
            backupPipe = backup_tar.backuptarfile(self.localPath, arcname=arcname, compress=compress_mode)
        backupPipe.make_nonblocking()
        job = backup.backup(
            self.backupID,
            backupPipe,
            finishCallback=OnJobDone,
            blockResultCallback=OnBackupBlockReport,
            blockSize=settings.getBackupBlockSize(),
            sourcePath=self.localPath,
            keyID=self.keyID or itemInfo.key_id,
        )
        jobs()[self.backupID] = job
        itemInfo.add_version(dataID)
        if itemInfo.type == backup_fs.DIR:
            dirsize.ask(self.localPath, OnFoundFolderSize, (self.pathID, dataID))
        else:
            sz = os.path.getsize(self.localPath)
            jobs()[self.backupID].totalSize = sz
            itemInfo.set_size(sz)
            backup_fs.Calculate()
            Save()
        jobs()[self.backupID].automat('start')
        reactor.callLater(0, FireTaskStartedCallbacks, self.pathID, dataID)  # @UndefinedVariable
        lg.out(4, 'backup_control.Task-%d.run [%s/%s], size=%d, %s' % (
            self.number, self.pathID, dataID, itemInfo.size, self.localPath))
        return None

#------------------------------------------------------------------------------


def PutTask(pathID, localPath=None, keyID=None):
    """
    Creates a new backup ``Task`` and append it to the list of tasks.
    """
    pathID = global_id.CanonicalID(pathID)
    current_task = GetPendingTask(pathID)
    if current_task:
        current_task.set_path_id(pathID)
        if localPath:
            current_task.set_local_path(localPath)
        if keyID:
            current_task.set_key_id(keyID)
        return current_task
    t = Task(pathID=pathID, localPath=localPath, keyID=keyID)
    tasks().append(t)
    return t


def DeleteAllTasks():
    """
    Clear the tasks list.
    """
    global _Tasks
    _Tasks = []


def RunTask():
    """
    Checks current jobs and run a one task if it is possible.
    Verifies if it is possible to start a new task,
    the maximum number of simultaneously running ``Jobs`` is limited.
    """
    if len(tasks()) == 0:
        return False
    if len(jobs()) >= MAXIMUM_JOBS_STARTED:
        return False
    if b'' in contactsdb.suppliers() or '' in contactsdb.suppliers():
        if _Debug:
            lg.out(_DebugLevel, 'backup_control.RunTask found empty supplier, retry after 5 sec')
        reactor.callLater(5, RunTask)  # @UndefinedVariable
        return False
    T = tasks().pop(0)
    message = T.run()
    if message:
        events.send('backup-task-failed', data=dict(path_id=T.pathID, message=message, ))
        T.result_defer.errback((T.pathID, message))
    else:
    #     events.send('backup-task-executed', data=dict(path_id=T.pathID, backup_id=T.backupID, ))
        T.result_defer.callback((T.backupID, None))
    T.destroy(message)
    return True


def HasTask(pathID):
    """
    Looks for path ID in the tasks list.
    """
    pathID = global_id.CanonicalID(pathID)
    for task in tasks():
        if task.pathID == pathID:
            return True
    return False


def GetPendingTask(pathID):
    """
    """
    pathID = global_id.CanonicalID(pathID)
    for t in tasks():
        if t.pathID == pathID:
            return t
    return None


def ListPendingTasks():
    """
    """
    return tasks()


def AbortPendingTask(pathID):
    """
    """
    pathID = global_id.CanonicalID(pathID)
    for t in tasks():
        if t.pathID == pathID:
            tasks().remove(t)
            return True
    return False

#------------------------------------------------------------------------------

def OnFoundFolderSize(pth, sz, arg):
    """
    This is a callback, fired from ``lib.dirsize.ask()`` method after finish
    calculating of folder size.
    """
    try:
        pathID, version = arg
        customerGlobID, pathID = packetid.SplitPacketID(pathID)
        customerIDURL = global_id.GlobalUserToIDURL(customerGlobID)
        item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(customerIDURL))
        if item:
            item.set_size(sz)
            backup_fs.Calculate()
            Save()
        if version:
            backupID = packetid.MakeBackupID(customerGlobID, pathID, version)
            job = GetRunningBackupObject(backupID)
            if job:
                job.totalSize = sz
        if _Debug:
            lg.out(_DebugLevel, 'backup_control.OnFoundFolderSize %s %d' % (backupID, sz))
    except:
        lg.exc()


def OnJobDone(backupID, result):
    """
    A callback method fired when backup is finished.

    Here we need to save the index data base.
    """
    from . import backup_rebuilder
    from customer import io_throttle
    lg.out(4, '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    lg.out(4, 'backup_control.OnJobDone [%s] %s, %d more tasks' % (backupID, result, len(tasks())))
    jobs().pop(backupID)
    customerGlobalID, remotePath, version = packetid.SplitBackupID(backupID)
    customer_idurl = global_id.GlobalUserToIDURL(customerGlobalID)
    if result == 'done':
        maxBackupsNum = settings.getBackupsMaxCopies()
        if maxBackupsNum:
            item = backup_fs.GetByID(remotePath, iterID=backup_fs.fsID(customer_idurl))
            if item:
                versions = item.list_versions(sorted=True, reverse=True)
                if len(versions) > maxBackupsNum:
                    for version in versions[maxBackupsNum:]:
                        item.delete_version(version)
                        backupID = packetid.MakeBackupID(customerGlobalID, remotePath, version)
                        backup_rebuilder.RemoveBackupToWork(backupID)
                        io_throttle.DeleteBackupRequests(backupID)
                        io_throttle.DeleteBackupSendings(backupID)
                        # callback.delete_backup_interest(backupID)
                        backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), backupID)
                        backup_matrix.EraseBackupLocalInfo(backupID)
                        backup_matrix.EraseBackupLocalInfo(backupID)
        backup_fs.ScanID(remotePath)
        backup_fs.Calculate()
        Save()
        control.request_update([('pathID', remotePath), ])
        # TODO: check used space, if we have over use - stop all tasks immediately
        backup_matrix.RepaintBackup(backupID)
    elif result == 'abort':
        DeleteBackup(backupID)
    if len(tasks()) == 0:
        # do we really need to restart backup_monitor after each backup?
        # if we have a lot tasks started this will produce a lot unneeded actions
        # will be smarter to restart it once we finish all tasks
        # because user will probably leave BitDust working after starting a long running operations
        from storage import backup_monitor
        lg.warn('restarting backup_monitor() machine because no tasks left')
        backup_monitor.A('restart')
    reactor.callLater(0, RunTask)  # @UndefinedVariable
    reactor.callLater(0, FireTaskFinishedCallbacks, remotePath, version, result)  # @UndefinedVariable


def OnJobFailed(backupID, err):
    """
    """
    lg.out(4, '!!!!!!!!!!!!!!! ERROR !!!!!!!!!!!!!!!!')
    lg.out(4, 'backup_control.OnJobFailed [%s] : %s' % (backupID, err))
    jobs().pop(backupID)


def OnTaskFailed(pathID, result):
    """
    Called when backup process get failed somehow.
    """
    lg.out(4, 'backup_control.OnTaskFailed [%s] %s, %d more tasks' % (pathID, result, len(tasks())))
    reactor.callLater(0, RunTask)  # @UndefinedVariable
    reactor.callLater(0, FireTaskFinishedCallbacks, pathID, None, result)  # @UndefinedVariable


def OnBackupBlockReport(backupID, blockNum, result):
    """
    Called for every finished block during backup process.

    :param newblock: this is a ``p2p.encrypted_block.encrypted_block`` instance
    :param num_suppliers: number of suppliers which is used for that backup
    """
    backup_matrix.LocalBlockReport(backupID, blockNum, result)


def OnTaskExecutedCallback(result):
    """
    """
    lg.out(_DebugLevel, 'backup_control.OnTaskExecuted %s : %s' % (result[0], result[1]))
    return result

def OnTaskFailedCallback(result):
    """
    """
    lg.err('pathID: %s, error: %s' % (result[0], result[1]))
    return result

#------------------------------------------------------------------------------


def AddTaskStartedCallback(pathID, callback):
    """
    You can catch a moment when given ``Task`` were started.

    Call this method to provide a callback method to handle.
    """
    global _TaskStartedCallbacks
    pathID = global_id.CanonicalID(pathID)
    if pathID not in _TaskStartedCallbacks:
        _TaskStartedCallbacks[pathID] = []
    _TaskStartedCallbacks[pathID].append(callback)


def AddTaskFinishedCallback(pathID, callback):
    """
    You can also catch a moment when the whole ``Job`` is done and backup
    process were finished or failed.
    """
    global _TaskFinishedCallbacks
    pathID = global_id.CanonicalID(pathID)
    if pathID not in _TaskFinishedCallbacks:
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


def FireTaskFinishedCallbacks(remotePath, version, result):
    """
    This runs callbacks for given path ID when that ``Job`` is done or failed.
    """
    global _TaskFinishedCallbacks
    for cb in _TaskFinishedCallbacks.get(remotePath, []):
        cb(remotePath, version, result)
    _TaskFinishedCallbacks.pop(remotePath, None)

#------------------------------------------------------------------------------


def StartSingle(pathID, localPath=None, keyID=None):
    """
    A high level method to start a backup of single file or folder.
    """
    from storage import backup_monitor
    t = PutTask(pathID=pathID, localPath=localPath, keyID=keyID)
    reactor.callLater(0, RunTask)  # @UndefinedVariable
    reactor.callLater(0, backup_monitor.A, 'restart')  # @UndefinedVariable
    return t


def StartRecursive(pathID, keyID=None):
    """
    A high level method to start recursive backup of given path.

    This is will traverse all paths below this ID in the 'tree' and add
    tasks for them.
    """
    pathID = global_id.CanonicalID(pathID)
    from storage import backup_monitor
    startedtasks = []

    def visitor(_pathID, path, info):
        if info.type == backup_fs.FILE:
            if _pathID.startswith(pathID):
                t = PutTask(pathID=pathID, localPath=path, keyID=keyID)
                startedtasks.append(t)

    backup_fs.TraverseByID(visitor)
    reactor.callLater(0, RunTask)  # @UndefinedVariable
    reactor.callLater(0, backup_monitor.A, 'restart')  # @UndefinedVariable
    lg.out(6, 'backup_control.StartRecursive %s  :  %d tasks started' % (pathID, len(startedtasks)))
    return startedtasks

#------------------------------------------------------------------------------


def IsBackupInProcess(backupID):
    """
    Return True if given backup ID is running and that "job" exists.
    """
    backupID = global_id.CanonicalID(backupID)
    return backupID in jobs()


def IsPathInProcess(pathID):
    """
    Return True if some backups is running at the moment of given path.
    """
    pathID = global_id.CanonicalID(pathID)
    for backupID in jobs().keys():
        if backupID.startswith(pathID):
            return True
    return False


def FindRunningBackup(pathID=None, customer=None):
    """
    """
    if pathID:
        pathID = global_id.CanonicalID(pathID)
    result = set()
    for backupID in jobs().keys():
        if pathID:
            if backupID.count(pathID):
                result.add(backupID)
                continue
        if customer:
            if backupID.count(customer + ':'):
                result.add(backupID)
                continue
    return list(result)


def HasRunningBackup():
    """
    Return True if at least one backup is running right now.
    """
    return len(jobs()) > 0


def AbortRunningBackup(backupID):
    """
    Call ``abort()`` method of ``p2p.backup.backup`` object - abort the running backup.
    """
    backupID = global_id.CanonicalID(backupID)
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
    return list(jobs().keys())


def GetRunningBackupObject(backupID):
    """
    Return an instance of ``p2p.backup.backup`` class - a running backup object,
    or None if that ID is not exist in the jobs dictionary.
    """
    backupID = global_id.CanonicalID(backupID)
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
    pprint.pprint(backup_fs.fsID())
    pprint.pprint(backup_fs.fs())
    print(backup_fs.GetByID('0'))
    # pprint.pprint(backup_fs.WalkByID('0/0/2/19/F20140106100849AM'))
    # for pathID, localPath, item in backup_fs.IterateIDs():
    #     print pathID, misc.unicode_to_str_safe(localPath)
    # backup_fs.TraverseByIDSorted(lambda x, y, z: sys.stdout.write('%s %s\n' % (x,misc.unicode_to_str_safe(y))))


def test2():
    """
    For tests.
    """
    # reactor.callLater(1, StartDirRecursive, 'c:/temp')
    reactor.run()  # @UndefinedVariable

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
