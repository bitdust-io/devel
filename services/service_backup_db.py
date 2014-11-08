#!/usr/bin/python
#service_backup_db.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_backup_db

"""

from services.local_service import LocalService

def create_service():
    return BackupDBService()
    
class BackupDBService(LocalService):
    
    service_name = 'service_backup_db'
    
    def dependent_on(self):
        return ['service_list_files',
                'service_data_sender', 
                ]
    
    def start(self):
        from p2p import backup_db_keeper
        backup_db_keeper.A('init')
        return True
    
    def stop(self):
        from p2p import backup_db_keeper
        backup_db_keeper.Destroy()
        return True
    
    
    

    