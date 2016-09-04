#!/usr/bin/python
#service_coins_miner.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_coins_miner

"""

from services.local_service import LocalService

def create_service():
    return CoinsMinerService()
    
class CoinsMinerService(LocalService):
    
    service_name = 'service_coins_miner'
    config_path = 'services/coins-miner/enabled'
    
    def dependent_on(self):
        return ['service_p2p_hookups', 
                ]
    
    def start(self):
        from transport import callback
        from coins import miner
        miner.init()
        callback.append_inbox_callback(miner.inbox_packet)
        return True
    
    def stop(self):
        from transport import callback
        from coins import miner
        callback.remove_inbox_callback(miner.inbox_packet)
        miner.shutdown()
        return True
