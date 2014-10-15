#!/usr/bin/python
#restore_monitor.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: restore_monitor

"""

from services.local_service import LocalService

def create_service():
    return RestoreMonitorService()
    
class RestoreMonitorService(LocalService):
    
    service_name = 'restore_monitor'
    
    def dependent_on(self):
        return ['gateway',
                ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    