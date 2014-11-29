#!/usr/bin/python
#service_restores.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_restores

"""

from services.local_service import LocalService

def create_service():
    return RestoreMonitorService()
    
class RestoreMonitorService(LocalService):
    
    service_name = 'service_restores'
    config_path = 'services/restores/enabled'
    
    def dependent_on(self):
        return ['service_backups',
                ]
    
    def start(self):
        from storage import restore_monitor
        from web import webcontrol
        from main import settings
        restore_monitor.init()
        if not settings.NewWebGUI():
            restore_monitor.OnRestorePacketFunc = webcontrol.OnRestoreProcess
            restore_monitor.OnRestoreBlockFunc = webcontrol.OnRestoreSingleBlock
            restore_monitor.OnRestoreDoneFunc = webcontrol.OnRestoreDone
        return True
    
    def stop(self):
        from storage import restore_monitor
        restore_monitor.shutdown()
        return True
    
    

    