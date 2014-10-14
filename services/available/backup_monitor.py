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

"""

from services.local_service import LocalService

def create_service():
    return BackupMonitorService()
    
class BackupMonitorService(LocalService):
    
    name = 'backup_monitor'
    
    def dependent_on(self):
        return ['gateway',
                'list_files',
                'fire_hire',
                'rebuilding',
                ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    