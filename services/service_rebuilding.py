#!/usr/bin/python
#service_rebuilding.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_rebuilding

"""

from services.local_service import LocalService

def create_service():
    return RebuildingService()
    
class RebuildingService(LocalService):
    
    service_name = 'service_rebuilding'
    config_path = 'services/rebuilding/enabled'
    
    def dependent_on(self):
        return ['service_data_sender',
                ]
    
    def start(self):
        from raid import raid_worker
        from storage import backup_rebuilder
        raid_worker.A('init')
        backup_rebuilder.A('init')
        return True
    
    def stop(self):
        from raid import raid_worker
        from storage import backup_rebuilder
        backup_rebuilder.Destroy()
        raid_worker.A('shutdown')
        return True
    
    

    