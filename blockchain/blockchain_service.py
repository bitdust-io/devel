#!/usr/bin/python
#blockchain_service.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: blockchain_service

"""

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------ 

import random
import string

from twisted.internet import reactor

from logs import lg
from main import settings

from blockchain import zcoin as zc

#------------------------------------------------------------------------------ 

def namespaces():
    return {
        'this':
        'last',
    }

#------------------------------------------------------------------------------ 

def init():
    zc.namespace.set_base_dir(settings.BlockChainDir())
    zc.namespace.new('')


def shutdown():
    pass


def db():
    return zc.config.db


def wallet():
    return zc.config.wallet


def nodes():
    return zc.config.nodes

#------------------------------------------------------------------------------ 

class BitDustCoins(zc.zcoin.zCoin):

    def firstrun(self):
        if _Debug:
            lg.out(_DebugLevel, 'BitDustCoins.firstrun')
        pub, priv = zc.zcoin.rsa.newkeys(1024)
        address = "Z"+''.join([random.choice(string.uppercase+string.lowercase+string.digits) for x in range(50)])
        # print "Your address is: "+address
        # print "Getting nodes..."
        zc.get_nodes.send(True)
        check = zc.config.nodes.find("nodes", "all")
        if not check:
            # print "It looks like you are the first node on this network."
            ip = raw_input("What is your IP address? ")
            zc.config.nodes.insert("nodes", {"public":str(pub), "address":address, "ip":ip, "relay":config.relay, "port":config.port})
            zc.config.nodes.save()
            zc.config.db.insert("difficulty", {"difficulty": config.base_difficulty})
            zc.config.db.save()
        zc.config.wallet.insert("data", {"public":str(pub), "address":address, "private":str(priv)})
        zc.config.wallet.save()
        print "Registering..."
        zc.register.send()
        print "Getting coins db..."
        zc.get_db.send()
        print "Done!"
    
