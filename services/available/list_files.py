#!/usr/bin/python
#list_files.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: list_files

"""

from services.local_service import LocalService

def create_service():
    return ListFilesService()
    
class ListFilesService(LocalService):
    
    service_name = 'list_files'
    
    def dependent_on(self):
        return ['customer',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    