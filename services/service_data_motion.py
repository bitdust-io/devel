#!/usr/bin/python
#service_data_motion.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_data_motion

"""

from services.local_service import LocalService

def create_service():
    return DataMotionService()
    
class DataMotionService(LocalService):
    
    service_name = 'service_data_motion'
    config_path = 'services/data-motion/enabled'
    
    def dependent_on(self):
        return ['service_customer',
                ]
    
    def start(self):
        from customer import io_throttle
        from customer import data_sender
        io_throttle.init()
        data_sender.A('init')
        return True
    
    def stop(self):
        from customer import io_throttle
        from customer import data_sender
        data_sender.SetShutdownFlag()
        data_sender.Destroy()
        io_throttle.shutdown()
        return True
    
    

    