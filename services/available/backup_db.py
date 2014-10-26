#!/usr/bin/python
#backup_db.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: backup_db

"""

from services.local_service import LocalService

def create_service():
    return BackupDBService()
    
class BackupDBService(LocalService):
    
    service_name = 'backup_db'
    
    def dependent_on(self):
        return ['gateway',
                ]
    
    def start(self):
        from p2p import backup_db_keeper
        backup_db_keeper.A('init')
        return True
    
    def stop(self):
        return True
    
    
    

    