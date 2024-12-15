#!/usr/bin/python
# backup_control.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

_Debug = False
_DebugLevel = 20

#------------------------------------------------------------------------------

import os
import sys
import time
import zlib
import pprint

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor backup_control.py')

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.system import bpio
from bitdust.system import tmpfile
from bitdust.system import dirsize

from bitdust.lib import misc
from bitdust.lib import packetid
from bitdust.lib import nameurl
from bitdust.lib import strng

from bitdust.main import settings
from bitdust.main import events

from bitdust.raid import eccmap

from bitdust.crypt import encrypted
from bitdust.crypt import key
from bitdust.crypt import my_keys

from bitdust.userid import global_id
from bitdust.userid import id_url

from bitdust.services import driver

from bitdust.contacts import contactsdb

from bitdust.p2p import p2p_service

from bitdust.stream import data_sender

from bitdust.storage import backup_fs
from bitdust.storage import backup_matrix
from bitdust.storage import backup

from bitdust.userid import my_id

#------------------------------------------------------------------------------

MAXIMUM_JOBS_STARTED = 1  # let's do only one backup at once for now

_Jobs = {}  # here are already started backups ( by backupID )
_Tasks = []  # here are tasks to start backups in the future ( pathID )
_LastTaskNumber = 0
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


#------------------------------------------------------------------------------


def init():
    """
    Must be called before other methods here.

    Load index database from file `~/.bitdust/[network name]/metadata/index`.
    """
    if _Debug:
        lg.out(_DebugLevel, 'backup_control.init')


def shutdown():
    """
    Called for the correct completion of all things.
    """
    if _Debug:
        lg.out(_DebugLevel, 'backup_control.shutdown')


#------------------------------------------------------------------------------


def SaveFSIndex(customer_idurl=None, key_alias='master', increase_revision=True):
    """
    Save index data base to local file and notify "index_synchronizer()" or "shared_access_coordinator()" state machines.
    """
    if _Debug:
        lg.args(_DebugLevel, c=customer_idurl, k=key_alias, increase_revision=increase_revision)
    global _LoadingFlag
    if _LoadingFlag:
        return False
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if increase_revision:
        backup_fs.commit(
            customer_idurl=customer_idurl,
            key_alias=key_alias,
        )
    backup_fs.SaveIndex(customer_idurl, key_alias)
    if increase_revision:
        if key_alias == 'master':
            if driver.is_on('service_backup_db'):
                from bitdust.storage import index_synchronizer
                index_synchronizer.A('push')
        else:
            if driver.is_on('service_shared_data'):
                from bitdust.access import shared_access_coordinator
                shared_access_coordinator.on_index_file_updated(customer_idurl, key_alias)


#------------------------------------------------------------------------------


def on_files_received(newpacket, info):
    list_files_global_id = global_id.ParseGlobalID(newpacket.PacketID)
    if not list_files_global_id['idurl']:
        lg.warn('invalid PacketID: %s' % newpacket.PacketID)
        return False
    if list_files_global_id['key_alias'] != 'master':
        # ignore Files() if this is a shared data
        if _Debug:
            lg.dbg(_DebugLevel, 'ignore incoming %r, this is not a private data' % newpacket)
        return False
    if not id_url.is_the_same(list_files_global_id['idurl'], my_id.getIDURL()):
        # ignore Files() if this is another customer
        if _Debug:
            lg.dbg(_DebugLevel, 'ignore incoming %r which is owned by another customer' % newpacket)
        return False
    if not contactsdb.is_supplier(newpacket.OwnerID):
        # ignore Files() if this is not my supplier
        if _Debug:
            lg.dbg(_DebugLevel, 'incoming %r received, but %r is not my supplier' % (newpacket, newpacket.OwnerID))
        return False
    if _Debug:
        lg.dbg(_DebugLevel, '%r for us from %s' % (newpacket, newpacket.CreatorID))
    if IncomingSupplierListFiles(newpacket, list_files_global_id):
        p2p_service.SendAck(newpacket)
    else:
        p2p_service.SendFail(newpacket)
    return True


#------------------------------------------------------------------------------


def UnpackListFiles(payload, method):
    if method == 'Text':
        return payload
    elif method == 'Compressed':
        return strng.to_text(zlib.decompress(strng.to_bin(payload)))
    return payload


def IncomingSupplierListFiles(newpacket, list_files_global_id):
    """
    Called when command "Files" were received from one of my suppliers.
    This is an answer from given supplier (after my request) to get a
    list of our files stored on his machine.
    """
    supplier_idurl = newpacket.OwnerID
    customer_idurl = list_files_global_id['idurl']
    num = contactsdb.supplier_position(supplier_idurl, customer_idurl=customer_idurl)
    if num < -1:
        lg.warn('unknown supplier: %s' % supplier_idurl)
        return False
    from bitdust.customer import list_files_orator
    target_key_id = my_keys.latest_key_id(list_files_global_id['key_id'])
    if not my_keys.is_key_private(target_key_id):
        lg.warn('key %r not registered, not possible to decrypt ListFiles() packet from %r' % (target_key_id, supplier_idurl))
        return False
    try:
        block = encrypted.Unserialize(
            newpacket.Payload,
            decrypt_key=target_key_id,
        )
        input_data = block.Data()
    except:
        lg.err('failed decrypting data from packet %r received from %r' % (newpacket, supplier_idurl))
        return False
    from bitdust.storage import index_synchronizer
    is_in_sync = index_synchronizer.is_synchronized() and backup_fs.revision() > 0
    list_files_raw = UnpackListFiles(input_data, settings.ListFilesFormat())
    remote_files_changed, backups2remove, paths2remove, missed_backups = backup_matrix.process_raw_list_files(
        supplier_num=num,
        list_files_text_body=list_files_raw,
        customer_idurl=None,
        is_in_sync=is_in_sync,
    )
    list_files_orator.IncomingListFiles(newpacket)
    if remote_files_changed:
        backup_matrix.SaveLatestRawListFiles(supplier_idurl, list_files_raw)
    if _Debug:
        lg.args(_DebugLevel, s=nameurl.GetName(supplier_idurl), c=nameurl.GetName(customer_idurl), backups2remove=len(backups2remove), paths2remove=len(paths2remove), files_changed=remote_files_changed, missed_backups=len(missed_backups))
    if len(backups2remove) > 0:
        p2p_service.RequestDeleteListBackups(backups2remove)
        backup_matrix.populate_remote_versions_deleted(backups2remove)
        if _Debug:
            lg.out(_DebugLevel, '    also sent requests to remove %d backups' % len(backups2remove))
    if len(paths2remove) > 0:
        p2p_service.RequestDeleteListPaths(paths2remove)
        if _Debug:
            lg.out(_DebugLevel, '    also sent requests to remove %d paths' % len(paths2remove))
    if len(missed_backups) > 0:
        from bitdust.storage import backup_rebuilder
        backup_rebuilder.AddBackupsToWork(missed_backups)
        backup_rebuilder.A('start')
        if _Debug:
            lg.out(_DebugLevel, '    also triggered service_rebuilding with %d missed backups' % len(missed_backups))
    del backups2remove
    del paths2remove
    del missed_backups
    return True


def IncomingSupplierBackupIndex(newpacket, key_id=None, deleted_path_ids=[]):
    """
    Called by ``p2p.p2p_service`` when a remote copy of our local index data
    base ( in the "Data" packet ) is received from one of our suppliers.

    The index is also stored on suppliers to be able to restore it.
    """
    block = encrypted.Unserialize(newpacket.Payload, decrypt_key=key_id)
    if not block:
        lg.err('failed reading data from %s' % newpacket.RemoteID)
        return None
    try:
        data = block.Data()
        inpt = StringIO(strng.to_text(data))
        supplier_revision = inpt.readline().rstrip('\n')
        if supplier_revision:
            supplier_revision = int(supplier_revision)
        else:
            supplier_revision = None
        text_data = inpt.read()
    except:
        lg.exc()
        try:
            inpt.close()
        except:
            pass
        return None
    inpt.close()
    if _Debug:
        lg.args(_DebugLevel, k=key_id, p=newpacket.PacketID, c=newpacket.CreatorID, sz=len(text_data), inp=len(newpacket.Payload), deleted=len(deleted_path_ids))
    count, updated_customers_keys = backup_fs.ReadIndex(text_data, new_revision=supplier_revision, deleted_path_ids=deleted_path_ids)
    if updated_customers_keys:
        for customer_idurl, key_alias in updated_customers_keys:
            backup_fs.SaveIndex(customer_idurl, key_alias)
            if _Debug:
                lg.out(_DebugLevel, 'backup_control.IncomingSupplierBackupIndex updated to revision %d for %s of %s from %s' % (backup_fs.revision(customer_idurl, key_alias), customer_idurl, key_alias, newpacket.RemoteID))
    return supplier_revision


#------------------------------------------------------------------------------


def DeleteAllBackups():
    """
    Remove all backup IDs from index data base, see ``DeleteBackup()`` method.
    """
    # prepare a list of all known backup IDs
    all_ids = set(backup_fs.ListAllBackupIDs(customer_idurl=my_id.getIDURL()))
    all_ids.update(backup_matrix.GetBackupIDs(remote=True, local=True))
    if _Debug:
        lg.out(_DebugLevel, 'backup_control.DeleteAllBackups %d ID\'s to kill' % len(all_ids))
    # delete one by one
    for backupID in all_ids:
        DeleteBackup(backupID, saveDB=False, calculate=False)
    # scan all files
    backup_fs.Scan()
    # check and calculate used space
    backup_fs.Calculate()
    # save the index
    SaveFSIndex()


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
    key_alias, customer, _, _ = packetid.SplitBackupIDFull(backupID)
    customer_idurl = global_id.GlobalUserToIDURL(customer)
    # if the user deletes a backup, make sure we remove any work we're doing on it
    # abort backup if it just started and is running at the moment
    if AbortRunningBackup(backupID):
        if _Debug:
            lg.out(_DebugLevel, 'backup_control.DeleteBackup %s is in process, stopping' % backupID)
        return True
    from bitdust.stream import io_throttle
    from bitdust.storage import backup_rebuilder
    if _Debug:
        lg.out(_DebugLevel, 'backup_control.DeleteBackup %r' % backupID)
    # if we requested for files for this backup - we do not need it anymore
    io_throttle.DeleteBackupRequests(backupID)
    io_throttle.DeleteBackupSendings(backupID)
    # remove interests in transport_control
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
    if calculate or key_alias != 'master':
        backup_fs.Scan(customer_idurl=customer_idurl, key_alias=key_alias)
        backup_fs.Calculate(customer_idurl=customer_idurl, key_alias=key_alias)
    # in some cases we want to save the DB later
    if saveDB or key_alias != 'master':
        SaveFSIndex(customer_idurl, key_alias)
    return True


def DeletePathBackups(pathID, removeLocalFilesToo=True, saveDB=True, calculate=True):
    """
    This removes all backups of given path ID
    Doing same operations as ``DeleteBackup()``.
    """
    from bitdust.storage import backup_rebuilder
    from bitdust.stream import io_throttle
    pathID = global_id.CanonicalID(pathID)
    # get the working item
    customer, remotePath = packetid.SplitPacketID(pathID)
    key_alias = packetid.KeyAlias(customer)
    customer_idurl = global_id.GlobalUserToIDURL(customer)
    item = backup_fs.GetByID(remotePath, iterID=backup_fs.fsID(customer_idurl, key_alias))
    if item is None:
        return False
    if _Debug:
        lg.out(_DebugLevel, 'backup_control.DeletePathBackups ' + pathID)
    # this is a list of all known backups of this path
    versions = item.list_versions()
    for version in versions:
        backupID = packetid.MakeBackupID(customer, remotePath, version, key_alias=key_alias)
        if _Debug:
            lg.out(_DebugLevel, '        removing %s' % backupID)
        # abort backup if it just started and is running at the moment
        AbortRunningBackup(backupID)
        # if we requested for files for this backup - we do not need it anymore
        io_throttle.DeleteBackupRequests(backupID)
        io_throttle.DeleteBackupSendings(backupID)
        # remove interests in transport_control
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
    if calculate or key_alias != 'master':
        backup_fs.Scan(customer_idurl=customer_idurl, key_alias=key_alias)
        backup_fs.Calculate(customer_idurl=customer_idurl, key_alias=key_alias)
    # save the index if needed
    if saveDB or key_alias != 'master':
        SaveFSIndex(customer_idurl, key_alias)
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
        self.number = NewTaskNumber()  # index number for the task
        self.created = time.time()
        self.backupID = None
        self.pathID = None
        self.dataID = None
        self.totalSize = None
        self.fullGlobPath = None
        self.fullCustomerID = None
        self.customerGlobID = None
        self.customerIDURL = None
        self.remotePath = None
        self.localPath = None
        self.sourcePath = None
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
        data = dict(
            number=self.number,
            created=self.created,
            backup_id=self.backupID,
            key_id=self.keyID,
            path_id=self.pathID,
            customer_id=self.customerGlobID,
            path=self.remotePath,
            local_path=self.localPath,
            remote_path=self.fullGlobPath,
        )
        events.send('backup-task-created', data=data)

    def __repr__(self):
        """
        Return a string like:

            "Task-5: 0/1/2/3 from /home/veselin/Documents/myfile.txt"
        """
        return 'Task-%d(%s from %s)' % (self.number, self.pathID, self.localPath)

    def destroy(self, message=None):
        if _Debug:
            lg.out(_DebugLevel, 'backup_control.Task-%d.destroy %s -> %s' % (self.number, self.localPath, self.backupID))
        if self.result_defer and not self.result_defer.called:
            self.result_defer.cancel()
            self.result_defer = None
        # yapf: disable
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
        # yapf: enable

    def set_path_id(self, pathID):
        parts = global_id.NormalizeGlobalID(pathID)
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
        self.fullGlobPath = global_id.MakeGlobalID(customer=self.customerGlobID, key_alias=self.keyAlias, path=self.remotePath)
        self.fullCustomerID = global_id.MakeGlobalID(customer=self.customerGlobID, key_alias=self.keyAlias)

    def set_local_path(self, localPath):
        self.localPath = localPath

    def run(self):
        """
        Runs a new ``Job`` from that ``Task``.
        """
        iter_and_path = backup_fs.WalkByID(self.remotePath, iterID=backup_fs.fsID(self.customerIDURL, self.keyAlias))
        if iter_and_path is None:
            if _Debug:
                lg.out(_DebugLevel, 'backup_control.Task.run ERROR %s not found in the index' % self.remotePath)
            err = 'remote path "%s" not found in the catalog' % self.remotePath
            OnTaskFailed(self.pathID, err)
            return err
        itemInfo, sourcePath = iter_and_path
        self.sourcePath = sourcePath
        if isinstance(itemInfo, dict):
            try:
                itemInfo = itemInfo[backup_fs.INFO_KEY]
            except:
                lg.exc()
                err = 'catalog item related to "%s" is broken' % self.remotePath
                OnTaskFailed(self.pathID, err)
                return err
        if not self.localPath:
            self.localPath = sourcePath
            lg.out('backup_control.Task.run local path was populated from catalog: %s' % self.localPath)
        if self.localPath != sourcePath:
            if _Debug:
                lg.out(_DebugLevel, '    local path different in the catalog: %s != %s' % (self.localPath, sourcePath))
        if not bpio.pathExist(self.localPath):
            lg.warn('path not exist: %s' % self.localPath)
            err = 'local path "%s" not exist' % self.localPath
            OnTaskFailed(self.pathID, err)
            return err
        dataID = misc.NewBackupID()
        if itemInfo.has_version(dataID):
            # ups - we already have same version
            # let's add 1,2,3... to the end to make absolutely unique version ID
            i = 1
            while itemInfo.has_version(dataID + str(i)):
                i += 1
            dataID += str(i)
        self.dataID = dataID
        self.backupID = packetid.MakeBackupID(
            customer=self.fullCustomerID,
            path_id=self.remotePath,
            version=self.dataID,
        )
        if self.backupID in jobs():
            lg.warn('backup job %s already started' % self.backupID)
            return 'backup job %s already started' % self.backupID
        if itemInfo.type == backup_fs.DIR:
            dirsize.ask(self.localPath, self.on_folder_size_counted, itemInfo)
        else:
            sz = os.path.getsize(self.localPath)
            reactor.callLater(0, self.on_folder_size_counted, self.localPath, sz, itemInfo)  # @UndefinedVariable
        return None

    def on_folder_size_counted(self, pth, sz, itemInfo):
        """
        This is a callback, fired from ``lib.dirsize.ask()`` method after finish
        calculating of folder size.
        """
        self.totalSize = sz
        if id_url.is_the_same(self.customerIDURL, my_id.getIDURL()):
            # TODO: need to rethink that approach
            # here not taking in account compressing rate of the local files
            # but taking in account remote version size - it is always doubled
            if backup_fs.total_stats()['size_backups'] + self.totalSize*2 > settings.getNeededBytes():
                err_str = 'insufficient storage space expected'
                pth_id = self.pathID
                self.result_defer.errback(Exception(err_str))
                reactor.callLater(0, OnTaskFailed, pth_id, err_str)  # @UndefinedVariable
                self.destroy(err_str)
                return None
        try:
            backup_fs.MakeLocalDir(settings.getLocalBackupsDir(), self.backupID)
        except:
            lg.exc()
            if _Debug:
                lg.out(_DebugLevel, 'backup_control.Task.on_folder_size_counted ERROR creating destination folder for %s' % self.pathID)
            err_str = 'failed creating destination folder for "%s"' % self.backupID
            pth_id = self.pathID
            self.result_defer.errback(Exception(err_str))
            reactor.callLater(0, OnTaskFailed, pth_id, err_str)  # @UndefinedVariable
            self.destroy(err_str)
            return None

        itemInfo.set_size(self.totalSize)
        itemInfo.add_version(self.dataID)

        if _Debug:
            lg.out(_DebugLevel, 'backup_control.Task.on_folder_size_counted %s %d for %r' % (pth, sz, itemInfo))

        compress_mode = 'bz2'
        arcname = os.path.basename(self.sourcePath)

        from bitdust.storage import backup_tar
        if bpio.pathIsDir(self.localPath):
            backupPipe = backup_tar.backuptardir_thread(self.localPath, arcname=arcname, compress=compress_mode)
        else:
            backupPipe = backup_tar.backuptarfile_thread(self.localPath, arcname=arcname, compress=compress_mode)

        job = backup.backup(
            self.backupID,
            backupPipe,
            finishCallback=OnJobDone,
            blockResultCallback=OnBackupBlockReport,
            notifyNewDataCallback=OnNewDataPrepared,
            blockSize=settings.getBackupBlockSize(),
            sourcePath=self.localPath,
            keyID=self.keyID or itemInfo.key_id,
        )
        job.totalSize = self.totalSize
        jobs()[self.backupID] = job

        backup_fs.Calculate(customer_idurl=self.customerIDURL, key_alias=self.keyAlias)
        SaveFSIndex(customer_idurl=self.customerIDURL, key_alias=self.keyAlias)

        jobs()[self.backupID].automat('start')
        reactor.callLater(0, FireTaskStartedCallbacks, self.pathID, self.dataID)  # @UndefinedVariable

        if self.keyAlias == 'master':
            if driver.is_on('service_backup_db'):
                from bitdust.storage import index_synchronizer
                index_synchronizer.A('push')

        if _Debug:
            lg.out(_DebugLevel, 'backup_control.Task-%d.run [%s/%s], size=%d, %s' % (self.number, self.pathID, self.dataID, itemInfo.size, self.localPath))

        self.result_defer.callback((self.backupID, None))
        self.destroy(None)
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
    from bitdust.customer import fire_hire
    if not fire_hire.IsAllHired():
        if _Debug:
            lg.out(_DebugLevel, 'backup_control.RunTask some suppliers not hired yet, retry after 5 sec')
        reactor.callLater(5, RunTask)  # @UndefinedVariable
        return False
    T = tasks().pop(0)
    message = T.run()
    if message:
        events.send('backup-task-failed', data=dict(
            path_id=T.pathID,
            message=message,
        ))
        T.result_defer.errback(Exception(message))
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
    pathID = global_id.CanonicalID(pathID)
    for t in tasks():
        if t.pathID == pathID:
            return t
    return None


def ListPendingTasks():
    return tasks()


def AbortPendingTask(pathID):
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
        keyAlias = packetid.KeyAlias(customerGlobID)
        item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(customerIDURL, keyAlias))
        if item:
            item.set_size(sz)
            backup_fs.Calculate(customer_idurl=customerIDURL, key_alias=keyAlias)
            SaveFSIndex(customer_idurl=customerIDURL, key_alias=keyAlias)
        if version:
            backupID = packetid.MakeBackupID(customerGlobID, pathID, version, key_alias=keyAlias)
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
    from bitdust.storage import backup_rebuilder
    lg.info('job done [%s] with result "%s", %d more tasks' % (backupID, result, len(tasks())))
    jobs().pop(backupID)
    keyAlias, customerGlobalID, remotePath, version = packetid.SplitBackupIDFull(backupID)
    customer_idurl = global_id.GlobalUserToIDURL(customerGlobalID)
    if result == 'done':
        maxBackupsNum = settings.getBackupsMaxCopies()
        if maxBackupsNum:
            item = backup_fs.GetByID(remotePath, iterID=backup_fs.fsID(customer_idurl, keyAlias))
            if item:
                versions = item.list_versions(sorted=True, reverse=True)
                if len(versions) > maxBackupsNum:
                    for version in versions[maxBackupsNum:]:
                        item.delete_version(version)
                        backupID = packetid.MakeBackupID(customerGlobalID, remotePath, version, key_alias=keyAlias)
                        backup_rebuilder.RemoveBackupToWork(backupID)
                        backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), backupID)
                        backup_matrix.EraseBackupLocalInfo(backupID)
                        backup_matrix.EraseBackupLocalInfo(backupID)
        backup_fs.ScanID(remotePath, customer_idurl=customer_idurl, key_alias=keyAlias)
        backup_fs.Calculate(customer_idurl=customer_idurl, key_alias=keyAlias)
        SaveFSIndex(customer_idurl=customer_idurl, key_alias=keyAlias)
        # TODO: check used space, if we have over use - stop all tasks immediately
    elif result == 'abort':
        DeleteBackup(backupID)
    if len(tasks()) == 0:
        # do we really need to restart backup_monitor after each backup?
        # if we have a lot tasks started this will produce a lot unneeded actions
        # will be smarter to restart it once we finish all tasks
        # because user will probably leave BitDust working after starting a long running operations
        from bitdust.storage import backup_monitor
        if _Debug:
            lg.out(_DebugLevel, 'backup_control.OnJobDone restarting backup_monitor() machine because no tasks left')
        backup_monitor.A('restart')
    reactor.callLater(0, RunTask)  # @UndefinedVariable
    reactor.callLater(0, FireTaskFinishedCallbacks, remotePath, version, result)  # @UndefinedVariable


def OnJobFailed(backupID, err):
    lg.err('job failed [%s] : %s' % (backupID, err))
    jobs().pop(backupID)


def OnTaskFailed(pathID, result):
    """
    Called when backup process get failed somehow.
    """
    lg.err('task failed [%s] with result "%s", %d more tasks' % (pathID, result, len(tasks())))
    reactor.callLater(0, RunTask)  # @UndefinedVariable
    reactor.callLater(0, FireTaskFinishedCallbacks, pathID, None, result)  # @UndefinedVariable


def OnBackupBlockReport(backupID, blockNum, result):
    """
    Called for every finished block during backup process.

    :param newblock: this is a ``p2p.encrypted_block.encrypted_block`` instance
    :param num_suppliers: number of suppliers which is used for that backup
    """
    backup_matrix.LocalBlockReport(backupID, blockNum, result)


def OnNewDataPrepared():
    data_sender.A('new-data')


def OnTaskExecutedCallback(result):
    if _Debug:
        lg.out(_DebugLevel, 'backup_control.OnTaskExecuted %s : %s' % (result[0], result[1]))
    return result


def OnTaskFailedCallback(result):
    lg.err(str(result))
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
    from bitdust.storage import backup_monitor
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
    from bitdust.storage import backup_monitor
    startedtasks = []

    def visitor(_pathID, path, info):
        if info.type == backup_fs.FILE:
            if _pathID.startswith(pathID):
                t = PutTask(pathID=pathID, localPath=path, keyID=keyID)
                startedtasks.append(t)

    backup_fs.TraverseByID(visitor)
    reactor.callLater(0, RunTask)  # @UndefinedVariable
    reactor.callLater(0, backup_monitor.A, 'restart')  # @UndefinedVariable
    if _Debug:
        lg.out(_DebugLevel, 'backup_control.StartRecursive %s  :  %d tasks started' % (pathID, len(startedtasks)))
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

if __name__ == '__main__':
    bpio.init()
    lg.set_debug_level(20)
    settings.init()
    tmpfile.init(settings.getTempDir())
    contactsdb.init()
    eccmap.init()
    key.InitMyKey()
    init()
    test()
    settings.shutdown()
