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

import datetime
import dateutil.relativedelta
import random
import string

from twisted.internet import reactor

from logs import lg
from main import settings

from blockchain import zcoin as zc

#------------------------------------------------------------------------------ 

_BlockchainServices = {}

#------------------------------------------------------------------------------ 

def services():
    global _BlockchainServices
    return _BlockchainServices

#------------------------------------------------------------------------------ 

def namespaces(now=None):
    if not now:
        now = datetime.datetime.utcnow()
    last = now - dateutil.relativedelta.relativedelta(months=1)
    return [
        now.strftime('%Y%b'), 
        last.strftime('%Y%b'),
    ]

def namespace_current():
    return datetime.datetime.utcnow().strftime('%Y%b')

def namespace_last():
    now = datetime.datetime.utcnow()
    last = now - dateutil.relativedelta.relativedelta(months=1)
    return last.strftime('%Y%b')

#------------------------------------------------------------------------------ 

def init():
    zc.namespace.set_base_dir(settings.BlockChainDir())
    for ns in namespaces():
        zc.namespace.new(ns)


def shutdown():
    pass


def db(ns=None):
    if not ns:
        ns = namespace_current()
    return zc.namespace.ns(ns).db


def wallet(ns=None):
    if not ns:
        ns = namespace_current()
    return zc.namespace.ns(ns).wallet


def nodes(ns=None):
    if not ns:
        ns = namespace_current()
    return zc.namespace.ns(ns).nodes

#------------------------------------------------------------------------------ 

def start_services():
    port_num = 6800 # TODO: take from settings
    for ns in namespaces():
        zservice = zc.zcoin.run(ns, port_num)
        port_num += 10
        services()[ns] = zservice


def stop_services():
    for svc in services():
        pass

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
    
