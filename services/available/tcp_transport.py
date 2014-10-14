#!/usr/bin/python
#tcp_transport.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: tcp_transport

"""

from services.local_service import LocalService

def create_service():
    return TCPTransportService()
    
class TCPTransportService(LocalService):
    
    name = 'tcp_transport'
    
    def dependent_on(self):
        return ['tcp_connections',
                ]
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    

    