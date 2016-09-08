#!/usr/bin/python
#lookup.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: lookup
.. role:: red

"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------ 


import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in lookup.py')

from twisted.internet.defer import DeferredList, Deferred

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio

from lib import nameurl

from contacts import contactsdb
from contacts import identitycache

from userid import known_servers
from userid import my_id

from p2p import commands

from main import settings

from system import tmpfile

from crypt import signed
from crypt import key

from transport import gateway
from transport import stats
from transport import packet_out
from transport.tcp import tcp_node

from dht import dht_service

#------------------------------------------------------------------------------ 

_KnownIDURLsDict = {}
_DiscoveredIDURLsList = []
_NextLookupTask = None
_LookupMethod = None # method to get a list of random nodes
_ObserveMethod = None # method to get IDURL from given node

#------------------------------------------------------------------------------

def init(lookup_method=None, observe_method=None, process_method=None):
    """
    """
    global _LookupMethod
    global _ObserveMethod
    global _ProcessMethod
    _LookupMethod = lookup_method
    _ObserveMethod = observe_method
    _ProcessMethod = process_method
    lg.out(4, "lookup.init %s, %s, %s" % (_LookupMethod, _ObserveMethod, _ProcessMethod))


def shutdown():
    """
    """
    global _LookupMethod
    global _ObserveMethod
    global _ProcessMethod
    _LookupMethod = None
    _ObserveMethod = None
    _ProcessMethod = None
    lg.out(4, "lookup.shutdown")

#------------------------------------------------------------------------------ 

def known_idurls():
    global _KnownIDURLsDict
    return _KnownIDURLsDict.keys()

def discovered_idurls():
    global _DiscoveredIDURLsList
    return _DiscoveredIDURLsList

#------------------------------------------------------------------------------ 

def consume_discovered_idurls(count=1):
    if not discovered_idurls():
        if _Debug:
            lg.out(_DebugLevel, 'lookup.consume_discovered_idurls return None')
        return []
    results = []
    while len(results) < count and discovered_idurls():
        results.append(discovered_idurls().pop(0))
    if _Debug:
        lg.out(_DebugLevel, 'lookup.consume_discovered_idurls returns: %s' % results)
    return results


def schedule_next_lookup(current_lookup_task):
    global _NextLookupTask
    if _NextLookupTask:
        return
    _NextLookupTask = reactor.callLater(60, start,
        count = current_lookup_task.count,
        key = current_lookup_task.key,
        lookup_method = current_lookup_task.lookup_method,
        observe_method = current_lookup_task.observe_method,
        process_method = current_lookup_task.process_method
    )

def reset_next_lookup():
    global _NextLookupTask
    if _NextLookupTask and not _NextLookupTask.called and not _NextLookupTask.cancelled:
        _NextLookupTask.cancel()
        _NextLookupTask = None 

#------------------------------------------------------------------------------ 

def start(count=1, key='idurl', **kwargs):
    result = Deferred()
    if key=='idurl' and len(discovered_idurls()) > count:
        result.callback(consume_discovered_idurls(count))
        return result
    reset_next_lookup()
    t = LookupTask(count=count, key=key, **kwargs)
    t.start()
    return t.result

#------------------------------------------------------------------------------ 

class LookupTask(object):
    def __init__(self, count, key, lookup_method=None, observe_method=None, process_method=None,):
        global _LookupMethod
        global _ObserveMethod
        global _ProcessMethod
        self.lookup_method = lookup_method or _LookupMethod
        self.observe_method = observe_method or _ObserveMethod
        self.process_method = process_method or _ProcessMethod
        self.result = Deferred()
        self.started = time.time()
        self.count = count
        self.succeed = 0
        self.failed = 0
        self.key = key
        self.found_nodes = []

    def start(self):
        d = self.lookup_method()
        d.addCallback(self.on_nodes_discovered)
        d.addErrback(lambda err: schedule_next_lookup(self))
        if self.result:
            d.addErrback(lambda err: self.report_result([]))
        return d

    def observe_nodes(self, nodes):
        l = []
        for node in nodes:
            d = self.observe_method(node, self.key)
            d.addCallback(self.on_node_observed, node)
            d.addErrback(self.on_failed)
            l.append(d)
        dl = DeferredList(l, consumeErrors=True)
        dl.addCallback(self.on_all_nodes_observed)
        return nodes

    def report_result(self, results):
        if self.result:
            self.result.callback(results)
            self.result = None

    def on_succeed(self, node, info):
        self.succeed += 1
        if _Debug:
            lg.out(_DebugLevel, 'lookup.on_succeed %s info: %s' % (node, info))
        
    def on_failed(self, err):
        self.failed += 1
        if _Debug:
            lg.warn('ERROR: %r' % err)

    def on_nodes_discovered(self, nodes):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.on_nodes_discovered : %s' % nodes)
        if not nodes or len(discovered_idurls()) < 5:
            schedule_next_lookup(self.count,
                                 lookup_method=self.lookup_method,
                                 observe_method=self.observe_method,
                                 process_method=self.process_method)
        if len(nodes) == 0:
            self.report_result([])
            return []
        return self.observe_nodes(nodes)
    
    def on_node_observed(self, response, node):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.on_node_observed %s' % response)
        d = self.process_method(response, self.key)
        d.addErrback(self.on_failed)
        if self.key == 'idurl':
            d.addCallback(self.on_identity_cached, node)
        return d

    def on_all_nodes_observed(self, results):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.on_all_nodes_observed %s' % results)

    def on_node_processed(self, node, idurl):
        if self.count > len(discovered_idurls()):
            if _Debug:
                lg.out(_DebugLevel, 'lookup.on_node_processed %s, need more' % idurl)
            return
        self.report_result(consume_discovered_idurls(self.count))

    def on_identity_cached(self, idurl, src, node):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.on_identity_cached %s' % idurl)
        discovered_idurls().append(idurl)
        known_idurls()[idurl] = time.time()
        self.on_succeed(node, idurl)
        reactor.callLater(0, self.on_node_processed, node, idurl)
        return idurl

#------------------------------------------------------------------------------ 


