#!/usr/bin/python
#service_gateway.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_gateway

"""

from services.local_service import LocalService

def create_service():
    return GatewayService()
    
class GatewayService(LocalService):
    
    service_name = 'service_gateway'
    config_path = 'services/gateway/enabled'
    
    def dependent_on(self):
        return ['service_network',
                ]
    
    def start(self):
        from transport import gateway
        from transport import callback
        from transport import bandwidth
        gateway.init()
        bandwidth.init()
        callback.insert_inbox_callback(0, bandwidth.INfile)
        callback.add_finish_file_sending_callback(bandwidth.OUTfile)
        return True
    
    def stop(self):
        from transport import bandwidth
        from transport import gateway
        from transport import callback
        callback.remove_inbox_callback(bandwidth.INfile)
        callback.remove_finish_file_sending_callback(bandwidth.OUTfile)
        d = gateway.stop()
        bandwidth.shutdown()
        gateway.shutdown()
        return d
    
    

    