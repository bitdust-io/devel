#!/usr/bin/python
#service_private_messages.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_private_messages

"""

from services.local_service import LocalService

def create_service():
    return PrivateMessagesService()
    
class PrivateMessagesService(LocalService):
    
    service_name = 'service_private_messages'
    config_path = 'services/private-messages/enabled'
    
    def dependent_on(self):
        return ['service_gateway',
                'service_entangled_dht',
                ]
    
    def start(self):
        from chat import message
        from web import webcontrol
        message.init()
        message.OnIncomingMessageFunc = webcontrol.OnIncomingMessage
        from userid import nickname_holder
        nickname_holder.A('set', None)
        return True
    
    def stop(self):
        from userid import nickname_holder
        nickname_holder.Destroy()
        return True
    
    

    