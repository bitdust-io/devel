#!/usr/bin/python
# lookup.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (lookup.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#

"""
.. module:: lookup.

.. role:: red
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys
import time

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in lookup.py')

from twisted.internet.defer import DeferredList, Deferred

#------------------------------------------------------------------------------

from lib import strng

from logs import lg

from dht import dht_service

from contacts import identitycache

from userid import id_url

#------------------------------------------------------------------------------

_KnownIDURLsDict = {}
_DiscoveredIDURLsList = {}
_LookupTasks = []
_CurrentLookupTask = None
# _NextLookupTask = None
_LookupMethod = None  # method to get a list of random nodes
_ObserveMethod = None  # method to get IDURL from given node
_ProcessMethod = None  # method to do some stuff with discovered IDURL

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
    if _Debug:
        lg.out(_DebugLevel, "lookup.init")


def shutdown():
    """
    """
    global _LookupMethod
    global _ObserveMethod
    global _ProcessMethod
    _LookupMethod = None
    _ObserveMethod = None
    _ProcessMethod = None
    if _Debug:
        lg.out(_DebugLevel, "lookup.shutdown")

#------------------------------------------------------------------------------


def known_idurls():
    global _KnownIDURLsDict
    return _KnownIDURLsDict


def discovered_idurls(layer_id=0):
    global _DiscoveredIDURLsList
    if layer_id not in _DiscoveredIDURLsList:
        _DiscoveredIDURLsList[layer_id] = []
    return _DiscoveredIDURLsList[layer_id]

#------------------------------------------------------------------------------


def consume_discovered_idurls(count=1, layer_id=0):
    if not discovered_idurls(layer_id=layer_id):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.consume_discovered_idurls returns empty list')
        return []
    results = []
    while len(results) < count and discovered_idurls(layer_id=layer_id):
        results.append(id_url.to_bin(discovered_idurls(layer_id=layer_id).pop(0)))
    if _Debug:
        lg.out(_DebugLevel, 'lookup.consume_discovered_idurls : %s' % results)
    return results


def extract_discovered_idurls(count=1, layer_id=0):
    if not discovered_idurls(layer_id=layer_id):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.extract_discovered_idurls returns empty list')
        return []
    results = id_url.to_bin_list(discovered_idurls(layer_id=layer_id)[:count])
    if _Debug:
        lg.out(_DebugLevel, 'lookup.extract_discovered_idurls : %s' % results)
    return results

#------------------------------------------------------------------------------

def random_proxy_router():
    from dht import dht_records
    return start(layer_id=dht_records.LAYER_PROXY_ROUTERS)


def random_supplier():
    from dht import dht_records
    return start(layer_id=dht_records.LAYER_SUPPLIERS)

#------------------------------------------------------------------------------

def start(count=1, consume=True, lookup_method=None, observe_method=None, process_method=None, layer_id=0):
    """
    NOTE: no parallel threads, DHT lookup can be started only one at time.
    """
    global _LookupTasks
    t = DiscoveryTask(
        count=count,
        consume=consume,
        lookup_method=lookup_method,
        observe_method=observe_method,
        process_method=process_method,
        layer_id=layer_id,
    )
    if len(discovered_idurls(layer_id=layer_id)) > count:
        if _Debug:
            lg.out(_DebugLevel - 4, 'lookup.start  knows %d discovered nodes, SKIP and return %d nodes' % (
                len(discovered_idurls(layer_id=layer_id)), count))
        if consume:
            idurls = consume_discovered_idurls(count, layer_id=layer_id)
        else:
            idurls = extract_discovered_idurls(count, layer_id=layer_id)
        reactor.callLater(0, t.result_defer.callback, idurls)  # @UndefinedVariable
        return t
    _LookupTasks.append(t)
    reactor.callLater(0, work)  # @UndefinedVariable
    if _Debug:
        lg.out(_DebugLevel - 4, 'lookup.start  new DiscoveryTask created for %d nodes at layer %d' % (count, layer_id, ))
    return t

#------------------------------------------------------------------------------

def on_lookup_task_success(result):
    global _CurrentLookupTask
    if _Debug:
        lg.out(_DebugLevel - 4, 'lookup.on_lookup_task_success %s' % result)
    _CurrentLookupTask = None
    reactor.callLater(0, work)  # @UndefinedVariable
    return result


def on_lookup_task_failed(err):
    global _CurrentLookupTask
    if _Debug:
        lg.out(_DebugLevel - 4, 'lookup.on_lookup_task_failed: %s' % err)
    _CurrentLookupTask = None
    reactor.callLater(0, work)  # @UndefinedVariable
    return err


def work():
    """
    """
    global _CurrentLookupTask
    global _LookupTasks
    if _CurrentLookupTask:
        if _Debug:
            lg.out(_DebugLevel - 4, 'lookup.work SKIP, %s is in progress' % _CurrentLookupTask)
        return
    if not _LookupTasks:
        if _Debug:
            lg.out(_DebugLevel - 4, 'lookup.work SKIP no lookup tasks in the queue')
        return
    if _Debug:
        lg.out(_DebugLevel - 4, 'lookup.work starting next task in the queue')
    _CurrentLookupTask = _LookupTasks.pop(0)
    if not _CurrentLookupTask.result_defer:
        lg.warn('task %s is closed' % _CurrentLookupTask)
        return
    _CurrentLookupTask.start()
    if _CurrentLookupTask.result_defer:
        _CurrentLookupTask.result_defer.addCallback(on_lookup_task_success)
    else:
        lg.warn('task %s was closed immediately' % _CurrentLookupTask)

#------------------------------------------------------------------------------

def lookup_in_dht(layer_id=0):
    """
    Pick random node from Distributed Hash Table.
    Generates
    """
    if _Debug:
        lg.out(_DebugLevel, 'lookup.lookup_in_dht layer_id=%d' % (layer_id, ))
    return dht_service.find_node(dht_service.random_key(), layer_id=layer_id)


def on_idurl_response(response, result):
    if _Debug:
        lg.out(_DebugLevel, 'lookup.on_idurl_response : %r' % response)
    responded_idurl = response.get('idurl')
    if not responded_idurl:
        result.errback(Exception('idurl observe failed'))
        return response
    try:
        idurl = id_url.to_bin(responded_idurl)
    except:
        lg.exc()
        result.errback(Exception('idurl observe failed'))
        return response
    result.callback(idurl)
    return response


def observe_dht_node(node, layer_id=0):
    if _Debug:
        lg.out(_DebugLevel, 'lookup.observe_dht_node   %s  layer_id=%d' % (
            node, layer_id, ))
    result = Deferred()
    d = node.request('idurl', layerID=layer_id)
    d.addCallback(on_idurl_response, result)
    d.addErrback(result.errback)
    return result


def on_identity_cached(src, idurl, result):
    if not src:
        if _Debug:
            lg.out(_DebugLevel, 'lookup.on_identity_cached FAILED with empty identity source for %r' % idurl)
        result.errback(Exception(idurl))
        return None
    if _Debug:
        lg.out(_DebugLevel, 'lookup.on_identity_cached %r with %d bytes' % (idurl, len(src)))
    result.callback(id_url.field(idurl))
    return src


def process_idurl(idurl, node):
    if _Debug:
        lg.out(_DebugLevel, 'lookup.process_idurl %r from %r' % (idurl, node, ))
    result = Deferred()
    if not idurl:
        result.errback(Exception(idurl))
        return result
    d = identitycache.immediatelyCaching(idurl)
    d.addCallback(on_identity_cached, idurl, result)
    d.addErrback(result.errback)
    return result

#------------------------------------------------------------------------------

class DiscoveryTask(object):

    def __init__(
        self,
        count,
        consume=True,
        lookup_method=None,
        observe_method=None,
        process_method=None,
        layer_id=0,
    ):
        global _LookupMethod
        global _ObserveMethod
        global _ProcessMethod
        self.lookup_method = lookup_method or _LookupMethod
        self.observe_method = observe_method or _ObserveMethod
        self.process_method = process_method or _ProcessMethod
        self.started = time.time()
        self.layer_id = layer_id
        self.count = count
        self.consume = consume
        self.succeed = 0
        self.failed = 0
        self.lookup_now = False
        self.stopped = False
        self.lookup_task = None
        self.result_defer = Deferred(canceller=lambda d: self._close())
        self.result_defer.addErrback(lg.errback)

    def __del__(self):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.__del__')

    def start(self):
        if self.stopped:
            lg.warn('DiscoveryTask already stopped')
            return None
        if self.lookup_task and not self.lookup_task.called:
            lg.warn('lookup_nodes() method already called')
            return self.lookup_task
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask.start  layer_id=%d' % self.layer_id)
        return self._lookup_nodes()

    def stop(self):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask.stop')
        self.stopped = True
        self._close()

    def _close(self):
        self.stopped = True
        if self.lookup_task and not self.lookup_task.called:
            self.lookup_task.cancel()
            self.lookup_task = None
        self.lookup_method = None
        self.observe_method = None
        self.process_method = None
        self.result_defer = None
        if _Debug:
            lg.out(_DebugLevel, 'lookup.close finished in %f seconds' % round(time.time() - self.started, 3))

    def _lookup_nodes(self):
        if self.lookup_task and not self.lookup_task.called:
            if _Debug:
                lg.out(_DebugLevel, 'lookup._lookup_nodes    SKIP, already started')
            return self.lookup_task
        if _Debug:
            lg.out(_DebugLevel, 'lookup._lookup_nodes layer_id=%d' % self.layer_id)
        self.lookup_now = True
        self.lookup_task = self.lookup_method(layer_id=self.layer_id)
        self.lookup_task.addCallback(self._on_nodes_discovered)
        self.lookup_task.addErrback(self._on_lookup_failed)
        return self.lookup_task

    def _observe_nodes(self, nodes):
        if self.stopped:
            if _Debug:
                lg.warn('discovery process already stopped')
            return
        if _Debug:
            lg.out(_DebugLevel, 'lookup._observe_nodes on %d items layer_id=%d' % (len(nodes), self.layer_id, ))
        observe_list = []
        for node in nodes:
            d = self.observe_method(node, layer_id=self.layer_id)
            d.addCallback(self._on_node_observed, node)
            d.addErrback(self._on_node_observe_failed, node)
            observe_list.append(d)
        dl = DeferredList(observe_list, consumeErrors=False)
        dl.addCallback(self._on_all_nodes_observed)

    def _report_result(self, results=None):
        if _Debug:
            lg.out(_DebugLevel, 'lookup._report_result %s, result_defer=%s' % (str(results), self.result_defer))
        if results is None:
            if self.consume:
                results = consume_discovered_idurls(self.count, layer_id=self.layer_id)
                if _Debug:
                    lg.out(_DebugLevel, '    %d results consumed, %d were requested' % (len(results), self.count))
            else:
                results = extract_discovered_idurls(self.count, layer_id=self.layer_id)
                if _Debug:
                    lg.out(_DebugLevel, '    %d results extracted, %d were requested' % (len(results), self.count))
        if self.result_defer:
            self.result_defer.callback(results)
        self.result_defer = None

    def _report_fails(self, err):
        if _Debug:
            lg.out(_DebugLevel, 'lookup._report_fails %s' % err)
        if self.result_defer:
            self.result_defer.errback(err)
        self.result_defer = None

    def _on_node_succeed(self, node, info):
        self.succeed += 1
        if _Debug:
            lg.out(_DebugLevel, 'lookup._on_succeed %s info: %s' % (node, info))
        return node

    def _on_node_proces_failed(self, err, node):
        self.failed += 1
        if _Debug:
            lg.warn('%r : %r' % (node, err))
        return None

    def _on_node_observe_failed(self, err, node):
        try:
            self.failed += 1
            if _Debug:
                err = strng.to_text(err, errors='ignore')
                if err.count('idurl observe failed'):
                    err = 'idurl observe failed'
                lg.args(_DebugLevel, node=node, err=err)
        except:
            lg.exc()
        return None

    def _on_node_observed(self, idurl, node):
        if self.stopped:
            lg.warn('node observed, but discovery process already stopped')
            return None
        idurl = id_url.to_bin(idurl)
        try:
            if _Debug:
                lg.out(_DebugLevel + 4, 'lookup._on_node_observed %r : %r' % (idurl, node))
            cached_time = known_idurls().get(idurl)
            if cached_time and time.time() - cached_time < 30.0:
                if _Debug:
                    lg.out(_DebugLevel + 4, 'lookup._on_node_observed SKIP node %r already observed recently' % idurl)
                return None
            if _Debug:
                lg.out(_DebugLevel + 4, 'lookup._on_node_observed %r : %r' % (node, idurl))
            d = self.process_method(idurl, node)
            d.addCallback(self._on_identity_cached, node)
            d.addErrback(self._on_node_proces_failed, node)
            return d
        except:
            lg.exc()
            return idurl

    def _on_node_processed(self, node, idurl):
        if _Debug:
            if len(discovered_idurls(layer_id=self.layer_id)) < self.count:
                lg.out(_DebugLevel, 'lookup._on_node_processed %s, but need more nodes' % idurl)
            else:
                lg.out(_DebugLevel, 'lookup._on_node_processed %s, have enough nodes now' % idurl)
        return node

    def _on_all_nodes_observed(self, observe_results):
        if self.stopped:
            lg.warn('_on_all_nodes_observed finished, but discovery process already stopped')
            return
        if _Debug:
            lg.out(_DebugLevel, 'lookup._on_all_nodes_observed results: %d, discovered nodes: %d' % (
                len(observe_results), len(discovered_idurls(layer_id=self.layer_id))))
        self._report_result()
        self._close()

    def _on_identity_cached(self, idurl, node):
        if self.stopped:
            return None
        if idurl is None:
            return None
        idurl = id_url.to_bin(idurl)
        discovered_idurls(layer_id=self.layer_id).append(idurl)
        known_idurls()[idurl] = time.time()
        self._on_node_succeed(node, idurl)
        reactor.callLater(0, self._on_node_processed, node, idurl)  # @UndefinedVariable
        if _Debug:
            lg.out(_DebugLevel, 'lookup._on_identity_cached : %s' % idurl)
        return idurl

    def _on_nodes_discovered(self, nodes):
        if _Debug:
            lg.out(_DebugLevel, 'lookup._on_nodes_discovered : %s, stopped=%s' % (str(nodes), self.stopped))
        self.lookup_now = False
        if self.stopped:
            lg.warn('on_nodes_discovered finished, but discovery process was already stopped')
            self._close()
            return None
        if not nodes:
            self._report_result()
            self._close()
            return None
        self._observe_nodes(nodes)
        return None

    def _on_lookup_failed(self, err):
        if _Debug:
            lg.out(_DebugLevel, 'lookup._on_lookup_failed %s' % err)
        self.lookup_now = False
        if self.stopped:
            lg.warn('discovery process already stopped')
            self._close()
            return
        self._report_fails(err)
        self._close()
        return err

#------------------------------------------------------------------------------
