#!/usr/bin/python
#service_miner.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_miner

"""

from services.local_service import LocalService

def create_service():
    return MinerService()
    
class MinerService(LocalService):
    
    service_name = 'service_miner'
    config_path = 'services/miner/enabled'
    
    def dependent_on(self):
        return ['service_p2p_hookups',
                'service_nodes_lookup',
                ]
    
    def start(self):
        from coins import coins_miner
        coins_miner.A('init')
        coins_miner.A('start')
        return True
    
    def stop(self):
        from coins import coins_miner
        coins_miner.A('stop')
        coins_miner.Destroy()
        return True
