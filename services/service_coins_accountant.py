#!/usr/bin/python
#service_coins_accountant.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_coins_accountant

"""

from services.local_service import LocalService

def create_service():
    return CoinsAccountantService()
    
class CoinsAccountantService(LocalService):
    
    service_name = 'service_coins_accountant'
    config_path = 'services/coins-accountant/enabled'
    
    def dependent_on(self):
        return ['service_p2p_hookups', 
                ]
    
    def start(self):
        from transport import callback
        from coins import accountant
        accountant.init()
        callback.append_inbox_callback(accountant.inbox_packet)
        return True
    
    def stop(self):
        from transport import callback
        from coins import accountant
        callback.remove_inbox_callback(accountant.inbox_packet)
        accountant.shutdown()
        return True
