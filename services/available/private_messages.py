#!/usr/bin/python
#private_messages.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: private_messages

"""

from services.local_service import LocalService

def create_service():
    return PrivateMessagesService()
    
class PrivateMessagesService(LocalService):
    
    name = 'private_messages'
    
    def dependent_on(self):
        return ['gateway',
                'distributed_hash_table',
                ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    