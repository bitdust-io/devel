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
    
    service_name = 'udp_datagrams'
    
    def dependent_on(self):
        return []
    
    def start(self):
        from lib import udp
        from lib import settings
        udp_port = int(settings.getUDPPort())
        if not udp.proto(udp_port):
            udp.listen(udp_port)
        return True
    
    def stop(self):
        from lib import udp
        from lib import settings
        udp_port = int(settings.getUDPPort())
        if udp.proto(udp_port):
            udp.close(udp_port)
        return True
    
    

    