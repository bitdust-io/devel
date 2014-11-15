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
        from p2p import backup_fs
        from p2p import backup_monitor
        from p2p import backup_control
        from p2p import backup_matrix
        from p2p import webcontrol
        backup_fs.init()
        backup_control.init()
        backup_matrix.init()
        backup_matrix.SetBackupStatusNotifyCallback(webcontrol.OnBackupStats)
        backup_matrix.SetLocalFilesNotifyCallback(webcontrol.OnReadLocalFiles)
        backup_monitor.A('init')
        from twisted.internet import reactor
        reactor.callLater(1, backup_monitor.A, 'restart')
        return True
    
    def stop(self):
        from p2p import backup_fs
        from p2p import backup_monitor
        from p2p import backup_control
        backup_monitor.Destroy()
        backup_fs.shutdown()
        backup_control.shutdown()
        return True
    
    

    