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
    
    service_name = 'service_accountant'
    config_path = 'services/accountant/enabled'
    
    def dependent_on(self):
        return ['service_p2p_hookups', 
                ]
    
    def start(self):
        from coins import accountant_node
        accountant_node.A('init')
        accountant_node.A('start')
        return True
    
    def stop(self):
        from coins import accountant_node
        accountant_node.A('stop')
        accountant_node.A('shutdown')
        return True
    
    def request(self, request, info):
        from logs import lg
        from p2p import p2p_service
        words = request.Payload.split(' ')
        try:
            mode = words[1][:10]
        except:
            lg.exc()
            return None
        if mode != 'join' and mode != 'write' and mode != 'read':
            lg.out(8, "service_accountant.request DENIED, wrong mode provided : %s" % mode)
            return None
        from coins import accountant_node
        if not accountant_node.A():
            lg.out(8, "service_accountant.request DENIED, accountant_node() state machine not exist")
            return p2p_service.SendFail(request, "accountant_node service not started")
        if accountant_node.A().state not in ['ACCOUNTANTS?', "READY", "VALID_COIN?", "WRITE_COIN!", ]:
            lg.out(8, "service_accountant.request DENIED, accountant_node() state is : %s" % accountant_node.A().state)
            return p2p_service.SendFail(request, "accountant_node service currently unavailable")
        if mode == 'join':
            accountant_node.A().join_accountant(request.OwnerID)
        return p2p_service.SendAck(request, 'accepted')
    