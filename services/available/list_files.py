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
    
    name = 'list_files'
    
    def dependent_on(self):
        return ['gateway',
                'customer',
                ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    