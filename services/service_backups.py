#!/usr/bin/python
#service_backups.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_backups

"""

from services.local_service import LocalService

def create_service():
    return BackupMonitorService()
    
class BackupMonitorService(LocalService):
    
    service_name = 'service_backups'
    config_path = 'services/backups/enabled'
    
    def dependent_on(self):
        return ['service_list_files',
                'service_fire_hire',
                'service_rebuilding',
                ]
    
    def start(self):
        from twisted.internet import reactor
        from storage import backup_fs
        from storage import backup_monitor
        from storage import backup_control
        from storage import backup_matrix
        from web import webcontrol
        from main.config import conf
        backup_fs.init()
        backup_control.init()
        backup_matrix.init()
        backup_matrix.SetBackupStatusNotifyCallback(webcontrol.OnBackupStats)
        backup_matrix.SetLocalFilesNotifyCallback(webcontrol.OnReadLocalFiles)
        backup_monitor.A('init')
        backup_monitor.A('restart')
        conf().addCallback('services/backups/keep-local-copies-enabled', 
            self._on_keep_local_copies_modified)
        conf().addCallback('services/backups/wait-suppliers-enabled',
            self._on_wait_suppliers_modified)
        return True
    
    def stop(self):
        from storage import backup_fs
        from storage import backup_monitor
        from storage import backup_control
        from main.config import conf
        backup_monitor.Destroy()
        backup_fs.shutdown()
        backup_control.shutdown()
        conf().removeCallback('services/backups/keep-local-copies-enabled')
        return True
    
    def _on_keep_local_copies_modified(self, path, value, oldvalue, result):
        from storage import backup_monitor
        backup_monitor.A('restart')
    
    def _on_wait_suppliers_modified(self, path, value, oldvalue, result):
        from storage import backup_monitor
        backup_monitor.A('restart')
    