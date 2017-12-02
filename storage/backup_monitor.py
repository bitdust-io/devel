#!/usr/bin/python
# backup_monitor.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (backup_monitor.py) is part of BitDust Software.
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
.. module:: backup_monitor.

.. raw:: html

    <a href="https://bitdust.io/automats/backup_monitor/backup_monitor.png" target="_blank">
    <img src="https://bitdust.io/automats/backup_monitor/backup_monitor.png" style="max-width:100%;">
    </a>

This is a state machine to manage rebuilding process of all backups.

Do several operations periodically:
    1) ping all suppliers
    2) request ListFiles from all suppliers
    3) prepare a list of backups to put some work to rebuild
    4) run rebuilding process and wait to finish
    5) make decision to replace one unreliable supplier with fresh one

The ``backup_monitor()`` automat starts the process of rebuilding the backups.

Control is passed to the ``list_files_orator()`` machine,
which will update the list of user's files already stored on remote machines.

Next would be a perform a list of backups that need to be rebuilt.

In the next step, control is passed to the state machine ``backup_rebuilder()``,
which control of the rebuilding process.

The last step is run ``fire_hire()`` automat, which monitors remote suppliers.


EVENTS:
    * :red:`backup_rebuilder.state`
    * :red:`fire-hire-finished`
    * :red:`init`
    * :red:`instant`
    * :red:`list-backups-done`
    * :red:`list_files_orator.state`
    * :red:`restart`
    * :red:`suppliers-changed`
    * :red:`timer-5sec`
"""


import sys
import gc

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in backup_monitor.py')

#------------------------------------------------------------------------------

from logs import lg

from automats import automat
from automats import global_state

from lib import diskspace
from lib import nameurl
from lib import packetid
from lib import misc

from main import settings

from contacts import contactsdb

from storage import backup_matrix
from storage import backup_fs
from storage import backup_control

from userid import global_id
from userid import my_id

#------------------------------------------------------------------------------

_BackupMonitor = None

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _BackupMonitor
    if _BackupMonitor is None:
        _BackupMonitor = BackupMonitor('backup_monitor', 'AT_STARTUP', 6, False)
    if event is not None:
        _BackupMonitor.automat(event, arg)
    return _BackupMonitor


def Destroy():
    """
    Destroy backup_monitor() automat and remove its instance from memory.
    """
    global _BackupMonitor
    if _BackupMonitor is None:
        return
    _BackupMonitor.destroy()
    del _BackupMonitor
    _BackupMonitor = None


class BackupMonitor(automat.Automat):
    """
    A class to monitor backups and manage rebuilding process.
    """

    timers = {
        'timer-5sec': (5.0, ['READY']),
    }

    def init(self):
        self.current_suppliers = []

    def state_changed(self, oldstate, newstate, event, arg):
        """
        This method is called every time when my state is changed.
        """
        global_state.set_global_state('MONITOR ' + newstate)
        if newstate == 'READY':
            self.automat('instant')

    def A(self, event, arg):
        from customer import fire_hire
        from customer import data_sender
        from customer import list_files_orator
        from storage import backup_rebuilder
        from storage import index_synchronizer
        #---READY---
        if self.state == 'READY':
            if event == 'timer-5sec':
                self.doOverallCheckUp(arg)
            elif event == 'restart' or event == 'suppliers-changed' or (event == 'instant' and self.RestartAgain):
                self.state = 'FIRE_HIRE'
                self.RestartAgain = False
                self.doRememberSuppliers(arg)
                fire_hire.A('restart')
        #---LIST_FILES---
        elif self.state == 'LIST_FILES':
            if (event == 'list_files_orator.state' and arg == 'NO_FILES'):
                self.state = 'READY'
            elif (event == 'list_files_orator.state' and arg == 'SAW_FILES'):
                self.state = 'LIST_BACKUPS'
                index_synchronizer.A('pull')
                data_sender.A('restart')
                self.doPrepareListBackups(arg)
            elif event == 'restart':
                self.RestartAgain = True
            elif event == 'suppliers-changed':
                self.state = 'READY'
                self.RestartAgain = True
        #---LIST_BACKUPS---
        elif self.state == 'LIST_BACKUPS':
            if event == 'list-backups-done':
                self.state = 'REBUILDING'
                backup_rebuilder.A('start')
            elif event == 'restart':
                self.RestartAgain = True
            elif event == 'suppliers-changed':
                self.state = 'READY'
                self.RestartAgain = True
            elif event == 'restart':
                self.state = 'FIRE_HIRE'
                fire_hire.A('restart')
        #---REBUILDING---
        elif self.state == 'REBUILDING':
            if (event == 'backup_rebuilder.state' and arg in ['DONE', 'STOPPED']):
                self.state = 'READY'
                self.doCleanUpBackups(arg)
                data_sender.A('restart')
            elif event == 'restart' or event == 'suppliers-changed':
                self.state = 'FIRE_HIRE'
                backup_rebuilder.SetStoppedFlag()
                fire_hire.A('restart')
        #---FIRE_HIRE---
        elif self.state == 'FIRE_HIRE':
            if event == 'suppliers-changed' and self.isSuppliersNumberChanged(arg):
                self.state = 'LIST_FILES'
                self.doDeleteAllBackups(arg)
                self.doRememberSuppliers(arg)
                list_files_orator.A('need-files')
            elif event == 'fire-hire-finished':
                self.state = 'LIST_FILES'
                list_files_orator.A('need-files')
            elif event == 'suppliers-changed' and not self.isSuppliersNumberChanged(arg):
                self.state = 'LIST_FILES'
                self.doUpdateSuppliers(arg)
                self.doRememberSuppliers(arg)
                list_files_orator.A('need-files')
            elif event == 'restart':
                self.RestartAgain = True
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READY'
                self.RestartAgain = False
        return None

    def isSuppliersNumberChanged(self, arg):
        """
        Condition method.
        """
        return contactsdb.num_suppliers() != len(self.current_suppliers)

    def doRememberSuppliers(self, arg):
        """
        Action method.
        """
        self.current_suppliers = list(contactsdb.suppliers())

    def doDeleteAllBackups(self, arg):
        """
        Action method.
        """
        lg.out(2, "backup_monitor.doDeleteAllBackups")
        # cancel all tasks and jobs
        backup_control.DeleteAllTasks()
        backup_control.AbortAllRunningBackups()
        # remove all local files and all backups
        backup_control.DeleteAllBackups()
        # erase all remote info
        backup_matrix.ClearRemoteInfo()
        # also erase local info
        backup_matrix.ClearLocalInfo()
        # finally save the list of current suppliers and clear all stats
        # backup_matrix.suppliers_set().UpdateSuppliers(contactsdb.suppliers())
        from customer import io_throttle
        io_throttle.DeleteAllSuppliers()

    def doUpdateSuppliers(self, arg):
        """
        Action method.
        """
        from customer import io_throttle
        # supplierList = contactsdb.suppliers()
        # take a list of suppliers positions that was changed
        changedSupplierNums = backup_matrix.SuppliersChangedNumbers(self.current_suppliers)
        # notify io_throttle that we do not neeed already this suppliers
        for supplierNum in changedSupplierNums:
            lg.out(2, "backup_monitor.doUpdateSuppliers supplier %d changed: [%s]->[%s]" % (
                supplierNum,
                nameurl.GetName(self.current_suppliers[supplierNum]),
                nameurl.GetName(contactsdb.suppliers()[supplierNum]),))
            suplier_idurl = self.current_suppliers[supplierNum]
            io_throttle.DeleteSuppliers([suplier_idurl, ])
            # erase (set to 0) remote info for this guys
            backup_matrix.ClearSupplierRemoteInfo(supplierNum)
        # finally save the list of current suppliers and clear all stats
        # backup_matrix.suppliers_set().UpdateSuppliers(supplierList)

    def doPrepareListBackups(self, arg):
        import backup_rebuilder
        if backup_control.HasRunningBackup():
            # if some backups are running right now no need to rebuild something - too much use of CPU
            backup_rebuilder.RemoveAllBackupsToWork()
            lg.out(6, 'backup_monitor.doPrepareListBackups skip all rebuilds')
            self.automat('list-backups-done')
            return
        # take remote and local backups and get union from it
        allBackupIDs = set(backup_matrix.local_files().keys() + backup_matrix.remote_files().keys())
        # take only backups from data base
        allBackupIDs.intersection_update(backup_fs.ListAllBackupIDs())
        # remove running backups
        allBackupIDs.difference_update(backup_control.ListRunningBackups())
        # sort it in reverse order - newer backups should be repaired first
        allBackupIDs = misc.sorted_backup_ids(list(allBackupIDs), True)
        # add backups to the queue
        backup_rebuilder.AddBackupsToWork(allBackupIDs)
        lg.out(6, 'backup_monitor.doPrepareListBackups %d items:' % len(allBackupIDs))
        lg.out(6, '    %s' % allBackupIDs)
        self.automat('list-backups-done', allBackupIDs)

    def doCleanUpBackups(self, arg):
        # here we check all backups we have and remove the old one
        # user can set how many versions of that file or folder to keep
        # other versions (older) will be removed here
        versionsToKeep = settings.getBackupsMaxCopies()
        bytesUsed = backup_fs.sizebackups() / contactsdb.num_suppliers()
        bytesNeeded = diskspace.GetBytesFromString(settings.getNeededString(), 0)
        customerGlobID = my_id.getGlobalID()
        lg.out(6, 'backup_monitor.doCleanUpBackups backupsToKeep=%d used=%d needed=%d' % (versionsToKeep, bytesUsed, bytesNeeded))
        delete_count = 0
        if versionsToKeep > 0:
            for pathID, localPath, itemInfo in backup_fs.IterateIDs():
                pathID = global_id.CanonicalID(pathID)
                if backup_control.IsPathInProcess(pathID):
                    continue
                versions = itemInfo.list_versions()
                # TODO: do we need to sort the list? it comes from a set, so must be sorted may be
                while len(versions) > versionsToKeep:
                    backupID = packetid.MakeBackupID(customerGlobID, pathID, versions.pop(0))
                    lg.out(6, 'backup_monitor.doCleanUpBackups %d of %d backups for %s, so remove older %s' % (
                        len(versions), versionsToKeep, localPath, backupID))
                    backup_control.DeleteBackup(backupID, saveDB=False, calculate=False)
                    delete_count += 1
        # we need also to fit used space into needed space (given from other users)
        # they trust us - do not need to take extra space from our friends
        # so remove oldest backups, but keep at least one for every folder - at least locally!
        # still our suppliers will remove our "extra" files by their "local_tester"
        if bytesNeeded <= bytesUsed:
            sizeOk = False
            for pathID, localPath, itemInfo in backup_fs.IterateIDs():
                if sizeOk:
                    break
                pathID = global_id.CanonicalID(pathID)
                versions = itemInfo.list_versions(True, False)
                if len(versions) <= 1:
                    continue
                for version in versions[1:]:
                    backupID = packetid.MakeBackupID(customerGlobID, pathID, version)
                    versionInfo = itemInfo.get_version_info(version)
                    if versionInfo[1] > 0:
                        lg.out(6, 'backup_monitor.doCleanUpBackups over use %d of %d, so remove %s of %s' % (
                            bytesUsed, bytesNeeded, backupID, localPath))
                        backup_control.DeleteBackup(backupID, saveDB=False, calculate=False)
                        delete_count += 1
                        bytesUsed -= versionInfo[1]
                        if bytesNeeded > bytesUsed:
                            sizeOk = True
                            break
        if delete_count > 0:
            backup_fs.Scan()
            backup_fs.Calculate()
            backup_control.Save()
            from web import control
            control.request_update()
        collected = gc.collect()
        lg.out(6, 'backup_monitor.doCleanUpBackups collected %d objects' % collected)

    def doOverallCheckUp(self, arg):
        """
        Action method.
        """
        if '' in contactsdb.suppliers():
            lg.out(6, 'backup_monitor.doOverallCheckUp found empty supplier, restart now')
            self.automat('restart')
            return
        # TODO: more tests here: low rating(), time offline, low ping, etc..
