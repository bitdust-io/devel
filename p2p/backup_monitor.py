#!/usr/bin/python
#backup_monitor.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: backup_monitor

.. raw:: html

    <a href="http://bitpie.net/automats/backup_monitor/backup_monitor.png" target="_blank">
    <img src="http://bitpie.net/automats/backup_monitor/backup_monitor.png" style="max-width:100%;">
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

from logs import lg

from lib import bpio
from lib import misc
from lib import settings
from lib import contacts
from lib import diskspace
from lib import automat
from lib import automats
from lib import nameurl

import backup_rebuilder
import fire_hire
import list_files_orator 
import backup_matrix
import backup_fs
import backup_control
import supplier_connector
import backup_db_keeper
import data_sender
import io_throttle

#------------------------------------------------------------------------------ 

_BackupMonitor = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _BackupMonitor
    if _BackupMonitor is None:
        _BackupMonitor = BackupMonitor('backup_monitor', 'READY', 4)
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
        automats.set_global_state('MONITOR ' + newstate)
        if newstate == 'RESTART':
            self.automat('instant')

    def A(self, event, arg):
        #---READY---
        if self.state == 'READY':
            if event == 'init' :
                self.RestartAgain=False
                self.doSuppliersInit(arg)
                backup_rebuilder.A('init')
            elif event == 'restart' or ( event == 'instant' and self.RestartAgain ) :
                self.state = 'FIRE_HIRE'
                self.RestartAgain=False
                self.doRememberSuppliers(arg)
                fire_hire.A('restart')
            elif event == 'timer-5sec' :
                self.doOverallCheckUp(arg)
        #---LIST_FILES---
        elif self.state == 'LIST_FILES':
            if ( event == 'list_files_orator.state' and arg == 'NO_FILES' ) :
                self.state = 'READY'
            elif ( event == 'list_files_orator.state' and arg == 'SAW_FILES' ) :
                self.state = 'LIST_BACKUPS'
                backup_db_keeper.A('restart')
                data_sender.A('restart')
                self.doPrepareListBackups(arg)
            elif event == 'restart' :
                self.RestartAgain=True
        #---LIST_BACKUPS---
        elif self.state == 'LIST_BACKUPS':
            if event == 'list-backups-done' :
                self.state = 'REBUILDING'
                backup_rebuilder.A('start')
            elif event == 'restart' :
                self.state = 'FIRE_HIRE'
                fire_hire.A('restart')
            elif event == 'restart' :
                self.RestartAgain=True
        #---REBUILDING---
        elif self.state == 'REBUILDING':
            if event == 'restart' :
                self.state = 'FIRE_HIRE'
                backup_rebuilder.SetStoppedFlag()
                fire_hire.A('restart')
            elif ( event == 'backup_rebuilder.state' and arg in [ 'DONE' , 'STOPPED' ] ) :
                self.state = 'READY'
                self.doCleanUpBackups(arg)
        #---FIRE_HIRE---
        elif self.state == 'FIRE_HIRE':
            if event == 'suppliers-changed' and self.isSuppliersNumberChanged(arg) :
                self.state = 'LIST_FILES'
                self.doDeleteAllBackups(arg)
                self.doRememberSuppliers(arg)
                list_files_orator.A('need-files')
            elif event == 'fire-hire-finished' :
                self.state = 'LIST_FILES'
                list_files_orator.A('need-files')
            elif event == 'suppliers-changed' and not self.isSuppliersNumberChanged(arg) :
                self.state = 'LIST_FILES'
                self.doUpdateSuppliers(arg)
                self.doRememberSuppliers(arg)
                list_files_orator.A('need-files')
            elif event == 'restart' :
                self.RestartAgain=True
        return None

    def isSuppliersNumberChanged(self, arg):
        """
        Condition method.
        """
        return contacts.numSuppliers() != len(self.current_suppliers)

    def doSuppliersInit(self, arg):
        """
        Action method.
        """
        for supplier_idurl in contacts.getSupplierIDs():
            if supplier_idurl:
                sc = supplier_connector.by_idurl(supplier_idurl)
                if sc is None:
                    sc = supplier_connector.create(supplier_idurl)

    def doRememberSuppliers(self, arg):
        """
        Action method.
        """
        self.current_suppliers = list(contacts.getSupplierIDs())
        
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
        # backup_matrix.suppliers_set().UpdateSuppliers(contacts.getSupplierIDs())
        io_throttle.DeleteAllSuppliers()
        
    def doUpdateSuppliers(self, arg):
        """
        Action method.
        """
        # supplierList = contacts.getSupplierIDs()
        # take a list of suppliers positions that was changed
        changedSupplierNums = backup_matrix.SuppliersChangedNumbers(self.current_suppliers)
        # notify io_throttle that we do not neeed already this suppliers
        for supplierNum in changedSupplierNums:
            lg.out(2, "backup_monitor.doUpdateSuppliers supplier %d changed: [%s]->[%s]" % (
                supplierNum, 
                nameurl.GetName(self.current_suppliers[supplierNum]),
                nameurl.GetName(contacts.getSupplierIDs()[supplierNum]),))
            suplier_idurl = self.current_suppliers[supplierNum] 
            io_throttle.DeleteSuppliers([suplier_idurl,])
            # erase (set to 0) remote info for this guys
            backup_matrix.ClearSupplierRemoteInfo(supplierNum)
        # finally save the list of current suppliers and clear all stats 
        # backup_matrix.suppliers_set().UpdateSuppliers(supplierList)
        
    def doPrepareListBackups(self, arg):
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
        lg.out(6, 'backup_monitor.doPrepareListBackups %d items' % len(allBackupIDs))
        self.automat('list-backups-done')

    def doCleanUpBackups(self, arg):
        # here we check all backups we have and remove the old one
        # user can set how many versions of that file or folder to keep 
        # other versions (older) will be removed here  
        versionsToKeep = settings.getGeneralBackupsToKeep()
        bytesUsed = backup_fs.sizebackups()/contacts.numSuppliers()
        bytesNeeded = diskspace.GetBytesFromString(settings.getNeededString(), 0) 
        lg.out(6, 'backup_monitor.doCleanUpBackups backupsToKeep=%d used=%d needed=%d' % (versionsToKeep, bytesUsed, bytesNeeded))
        delete_count = 0
        if versionsToKeep > 0:
            for pathID, localPath, itemInfo in backup_fs.IterateIDs():
                if backup_control.IsPathInProcess(pathID):
                    continue
                versions = itemInfo.list_versions()
                # TODO do we need to sort the list? it comes from a set, so must be sorted may be
                while len(versions) > versionsToKeep:
                    backupID = pathID + '/' + versions.pop(0)
                    lg.out(6, 'backup_monitor.doCleanUpBackups %d of %d backups for %s, so remove older %s' % (len(versions), versionsToKeep, localPath, backupID))
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
                versions = itemInfo.list_versions(True, False)
                if len(versions) <= 1:
                    continue
                for version in versions[1:]:
                    backupID = pathID+'/'+version
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
        collected = gc.collect()
        lg.out(6, 'backup_monitor.doCleanUpBackups collected %d objects' % collected)

    def doOverallCheckUp(self, arg):
        """
        Action method.
        """
        if '' in contacts.getSupplierIDs():
            lg.out(6, 'backup_monitor.doOverallCheckUp found empty supplier')
            Restart()
            return
        # TODO 
        
#------------------------------------------------------------------------------ 


def Restart():
    """
    Just sends a "restart" event to the state machine.
    """
    lg.out(4, 'backup_monitor.Restart')
    A('restart')


def shutdown():
    """
    Called from high level modules to finish all things correctly.
    """
    lg.out(4, 'backup_monitor.shutdown')
    A().destroy()

        


