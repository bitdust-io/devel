#!/usr/bin/python
#accountant.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: accountant

"""

_Debug = True
_DebugLevel = 14

#------------------------------------------------------------------------------ 

import json

#------------------------------------------------------------------------------ 

from p2p import commands
from p2p import p2p_service

#------------------------------------------------------------------------------ 

_AccountantNode = None

#------------------------------------------------------------------------------ 

def node():
    global _AccountantNode
    return _AccountantNode

#------------------------------------------------------------------------------ 

def init():
    global _AccountantNode
    if _AccountantNode:
        return
    _AccountantNode = AccountantNode()

def shutdown():
    global _AccountantNode
    if not _AccountantNode:
        return
    del _AccountantNode
    _AccountantNode = None

#------------------------------------------------------------------------------ 

def inbox_packet(newpacket, info, status, error_message):
    if status != 'finished':
        return False
    if newpacket.Command != commands.Coin():
        return False
    if not node():
        return False
    try:
        coins = json.loads(newpacket.Payload)['coins']
    except:
        return False
    results = []
    for coin in coins:
        results.append(node().validate_coin(coin))
    p2p_service.SendAck(newpacket, ','.join(results))
    return True
    
#------------------------------------------------------------------------------ 

class AccountantNode(object):
    
    def validate_coin(self, coin):
        return ''
    
    def inbox_packet(self, data):
        pass
    
    
    
