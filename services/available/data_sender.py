#!/usr/bin/python
#data_sender.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: data_sender

"""

from services.local_service import LocalService

def create_service():
    return DataSenderService()
    
class DataSenderService(LocalService):
    
    service_name = 'data_sender'
    
    def dependent_on(self):
        return []
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    