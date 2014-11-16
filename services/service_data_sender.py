#!/usr/bin/python
#service_data_sender.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_data_sender

"""

from services.local_service import LocalService

def create_service():
    return DataSenderService()
    
class DataSenderService(LocalService):
    
    service_name = 'service_data_sender'
    config_path = 'services/data-sender/enabled'
    
    def dependent_on(self):
        return ['service_customer',
                ]
    
    def start(self):
        from p2p import io_throttle
        from p2p import data_sender
        io_throttle.init()
        data_sender.A('init')
        return True
    
    def stop(self):
        from p2p import io_throttle
        from p2p import data_sender
        io_throttle.shutdown()
        data_sender.SetShutdownFlag()
        data_sender.Destroy()
        return True
    
    

    