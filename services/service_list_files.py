#!/usr/bin/python
#service_list_files.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_list_files

"""

from services.local_service import LocalService

def create_service():
    return ListFilesService()
    
class ListFilesService(LocalService):
    
    service_name = 'service_list_files'
    config_path = 'services/list-files/enabled'
    
    def dependent_on(self):
        return ['service_customer',
                ]
    
    def start(self):
        from supplier import list_files_orator
        list_files_orator.A('init')
        return True
    
    def stop(self):
        from supplier import list_files_orator
        list_files_orator.Destroy()
        return True
    
    

    