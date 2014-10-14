#!/usr/bin/python
#udp_datagrams.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: udp_datagrams

"""

from services.local_service import LocalService

def create_service():
    return UDPDatagramsService()
    
class UDPDatagramsService(LocalService):
    
    name = 'udp_datagrams'
    
    def dependent_on(self):
        return []
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    