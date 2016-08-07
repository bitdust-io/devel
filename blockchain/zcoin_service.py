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

_Debug = False
_DebugLevel = 4

#------------------------------------------------------------------------------ 

import datetime
import dateutil.relativedelta

from twisted.internet import reactor, threads

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    import sys, os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------ 

from logs import lg

from blockchain.z_coin import namespace
from blockchain.z_coin import zcoin

#------------------------------------------------------------------------------ 

_BlockchainServices = {}

#------------------------------------------------------------------------------ 

def services():
    global _BlockchainServices
    return _BlockchainServices

#------------------------------------------------------------------------------ 

def namespaces(now=None):
    if now is None:
        now = datetime.datetime.utcnow()
    last = now - dateutil.relativedelta.relativedelta(months=1)
    return [
        now.strftime('%Y%b').upper(), 
        last.strftime('%Y%b').upper(),
    ]

def namespace_current():
    return datetime.datetime.utcnow().strftime('%Y%b').upper()

def namespace_last():
    now = datetime.datetime.utcnow()
    last = now - dateutil.relativedelta.relativedelta(months=1)
    return last.strftime('%Y%b').upper()

#------------------------------------------------------------------------------ 

def init():
    if _Debug:
        lg.out(_DebugLevel, 'blockchain_service.init')
    try:
        from lib import misc
        from main import settings
        external_ip = misc.readExternalIP()
        namespace.set_base_dir(settings.BlockChainDir())
    except:
        external_ip = None
        namespace.set_base_dir('.')

    port_num = 6800 # TODO: take from settings
    for ns in namespaces():
        port_num += 11
        namespace.new(ns, port_num)
    for ns in namespaces():
        zservice = zcoin.run_with_twisted_reactor(ns, ip=external_ip)
        services()[ns] = zservice
    

def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'blockchain_service.shutdown')
    for ns in services().keys():
        services()[ns].stop()
        services().pop(ns)
    for ns in namespace.list_all():
        namespace.erase(ns)


def db(ns=None):
    if not ns:
        ns = namespace_current()
    return namespace.ns(ns).db


def wallet(ns=None):
    if not ns:
        ns = namespace_current()
    return namespace.ns(ns).wallet


def nodes(ns=None):
    if not ns:
        ns = namespace_current()
    return namespace.ns(ns).nodes


def create_new_record(json_data, ns=None):
    if not ns:
        ns = namespace_current()
    svc = services().get(ns)
    if not svc:
        return False
    return threads.deferToThread(svc.mine_one_coin, json_data)

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    lg.set_debug_level(30)
    init()
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)
    reactor.callLater(1, create_new_record, dict(ok=dict(idurl='isurl1'), test='seems working', num=2))
    reactor.run()
    
