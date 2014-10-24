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
    
    service_name = 'tcp_transport'
    
    def dependent_on(self):
        return ['tcp_connections',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    