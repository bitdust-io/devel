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
        return ['customer',
                ]
    
    def start(self):
        from p2p import data_sender
        data_sender.A('init')
        return True
    
    def stop(self):
        from p2p import data_sender
        data_sender.SetShutdownFlag()
        data_sender.Destroy()
        return True
    
    

    