#!/usr/bin/python
#service_zcoin_blockchain.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_zcoin_blockchain

"""

from services.local_service import LocalService

def create_service():
    return ZCoinBlockChainService()
    
class ZCoinBlockChainService(LocalService):
    
    service_name = 'service_zcoin_blockchain'
    config_path = 'services/zcoin-blockchain/enabled'
    
    def dependent_on(self):
        return ['service_tcp_connections', 
                ]
    
    def start(self):
        from blockchain import zcoin_service
        zcoin_service.init()
        return True
    
    def stop(self):
        from blockchain import zcoin_service
        zcoin_service.shutdown()
        return True
