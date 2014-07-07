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
    * :red:`hire-new-supplier`
    * :red:`init`
    * :red:`instant`
    * :red:`list-backups-done`
    * :red:`list_files_orator.state`
    * :red:`restart`
    * :red:`timer-1sec`
    * :red:`timer-20sec`
"""


import sys
import gc


try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in backup_monitor.py')

import lib.dhnio as dhnio
import lib.misc as misc
import lib.settings as settings
import lib.contacts as contacts
import lib.diskspace as diskspace
import lib.automat as automat
import lib.automats as automats

import backup_rebuilder
import fire_hire
import list_files_orator 
import backup_matrix
import backup_fs
import backup_control
import supplier_connector
import backup_db_keeper
import data_sender

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


class BackupMonitor(automat.Automat):
    """
    A class to monitor backups and manage rebuilding process.
    """
    
    timers = {
        'timer-1sec': (1.0, ['RESTART','SUPPLIERS?']),
        'timer-20sec': (20.0, ['SUPPLIERS?']),
        }
    ackCounter = 0
    pingTime = 0
    lastRequestSuppliersTime = 0

    def state_changed(self, oldstate, newstate):
        """
        This method is called every time when my state is changed. 
        """
        automats.set_global_state('MONITOR ' + newstate)

    def A(self, event, arg):
        #---READY---
        if self.state == 'READY':
            if event == 'init' :
                self.doSuppliersInit(arg)
                backup_rebuilder.A('init')
            elif event == 'restart' :
                self.state = 'RESTART'
        #---RESTART---
        elif self.state == 'RESTART':
            if ( event == 'instant' or event == 'timer-1sec' ) and not self.isAnyBackupRunning(arg) and backup_rebuilder.A().state in [ 'STOPPED', 'DONE', ] :
                self.state = 'SUPPLIERS?'
                self.doSuppliersConnect(arg)
        #---LIST_FILES---
        elif self.state == 'LIST_FILES':
            if event == 'restart' :
                self.state = 'RESTART'
            elif ( event == 'list_files_orator.state' and arg == 'NO_FILES' ) :
                self.state = 'READY'
            elif ( event == 'list_files_orator.state' and arg == 'SAW_FILES' ) :
                self.state = 'LIST_BACKUPS'
                backup_db_keeper.A('restart')
                data_sender.A('restart')
                self.doPrepareListBackups(arg)
        #---LIST_BACKUPS---
        elif self.state == 'LIST_BACKUPS':
            if event == 'list-backups-done' :
                self.state = 'REBUILDING'
                backup_rebuilder.A('start')
            elif event == 'restart' :
                self.state = 'RESTART'
        #---REBUILDING---
        elif self.state == 'REBUILDING':
            if event == 'restart' :
                self.state = 'RESTART'
                backup_rebuilder.SetStoppedFlag()
            elif ( event == 'backup_rebuilder.state' and arg == 'STOPPED' ) :
                self.state = 'READY'
            elif ( event == 'backup_rebuilder.state' and arg == 'DONE' ) :
                self.state = 'FIRE_HIRE'
                fire_hire.A('restart')
        #---FIRE_HIRE---
        elif self.state == 'FIRE_HIRE':
            if event == 'fire-hire-finished' :
                self.state = 'READY'
                self.doCleanUpBackups(arg)
            elif event == 'restart' or event == 'hire-new-supplier' :
                self.state = 'RESTART'
        #---SUPPLIERS?---
        elif self.state == 'SUPPLIERS?':
            if event == 'timer-1sec' and self.isAllSuppliersReady(arg) :
                self.state = 'LIST_FILES'
                list_files_orator.A('need-files')
            elif event == 'restart' :
                self.state = 'RESTART'
            elif event == 'timer-20sec' :
                self.state = 'FIRE_HIRE'
                fire_hire.A('restart')

    def isAllSuppliersReady(self, arg):
        """
        Condition method.
        """
        states = set(map(lambda c: c.state, supplier_connector.connectors().values()))
        return 'REQUEST' not in states

    def isAnyBackupRunning(self, arg):
        return backup_control.HasRunningBackup()

    def doSuppliersInit(self, arg):
        """
        Action method.
        """
        for supplier_idurl in contacts.getSupplierIDs():
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc is None:
                sc = supplier_connector.create(supplier_idurl)

    def doSuppliersConnect(self, arg):
        """
        Action method.
        """
        for supplier_idurl in contacts.getSupplierIDs():
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc is None: 
                sc = supplier_connector.create(supplier_idurl)
            sc.automat('connect')

    def doPrepareListBackups(self, arg):
        if backup_control.HasRunningBackup():
            # if some backups are running right now no need to rebuild something - too much use of CPU
            backup_rebuilder.RemoveAllBackupsToWork()
            dhnio.Dprint(6, 'backup_monitor.doPrepareListBackups skip all rebuilds')
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
        dhnio.Dprint(6, 'backup_monitor.doPrepareListBackups %d items' % len(allBackupIDs))
        self.automat('list-backups-done')

    def doCleanUpBackups(self, arg):
        # here we check all backups we have and remove the old one
        # user can set how many versions of that file of folder to keep 
        # other versions (older) will be removed here  
        versionsToKeep = settings.getGeneralBackupsToKeep()
        bytesUsed = backup_fs.sizebackups()/contacts.numSuppliers()
        bytesNeeded = diskspace.GetBytesFromString(settings.getCentralMegabytesNeeded(), 0) 
        dhnio.Dprint(6, 'backup_monitor.doCleanUpBackups backupsToKeep=%d used=%d needed=%d' % (versionsToKeep, bytesUsed, bytesNeeded))
        delete_count = 0
        if versionsToKeep > 0:
            for pathID, localPath, itemInfo in backup_fs.IterateIDs():
                versions = itemInfo.list_versions()
                # TODO do we need to sort the list? it comes from a set, so must be sorted may be
                while len(versions) > versionsToKeep:
                    backupID = pathID + '/' + versions.pop(0)
                    dhnio.Dprint(6, 'backup_monitor.doCleanUpBackups %d of %d backups for %s, so remove older %s' % (len(versions), versionsToKeep, localPath, backupID))
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
                        dhnio.Dprint(6, 'backup_monitor.doCleanUpBackups over use %d of %d, so remove %s of %s' % (
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
        dhnio.Dprint(6, 'backup_monitor.doCleanUpBackups collected %d objects' % collected)



def Restart():
    """
    Just sends a "restart" event to the state machine.
    """
    dhnio.Dprint(4, 'backup_monitor.Restart')
    A('restart')


def shutdown():
    """
    Called from high level modules to finish all things correctly.
    """
    dhnio.Dprint(4, 'backup_monitor.shutdown')
    automat.clear_object(A().index)

        


