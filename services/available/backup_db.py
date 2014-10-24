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
        return ['gateway']
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    
    

    