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

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys
import time
import random

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in lookup.py')

from twisted.internet.defer import DeferredList, Deferred

#------------------------------------------------------------------------------

from bitdust.lib import strng

from bitdust.logs import lg

from bitdust.dht import dht_service

from bitdust.contacts import identitycache

from bitdust.userid import id_url

#------------------------------------------------------------------------------

_KnownIDURLsDict = {}
_DiscoveredIDURLsList = {}
_LookupTasks = []
_LatestLookupID = 0
_CurrentLookupTask = None
_LookupMethod = None  # method to get a list of random nodes
_ObserveMethod = None  # method to get IDURL from given node
_ProcessMethod = None  # method to do some stuff with discovered IDURL

#------------------------------------------------------------------------------


def init(lookup_method=None, observe_method=None, process_method=None):
    global _LookupMethod
    global _ObserveMethod
    global _ProcessMethod
    _LookupMethod = lookup_method
    _ObserveMethod = observe_method
    _ProcessMethod = process_method
    if _Debug:
        lg.out(_DebugLevel, 'lookup.init')


def shutdown():
    global _LookupMethod
    global _ObserveMethod
    global _ProcessMethod
    _LookupMethod = None
    _ObserveMethod = None
    _ProcessMethod = None
    if _Debug:
        lg.out(_DebugLevel, 'lookup.shutdown')


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
        # random_pos = random.randint(0, len(discovered_idurls(layer_id=layer_id)) - 1)
        # results.append(id_url.to_bin(discovered_idurls(layer_id=layer_id).pop(random_pos)))
        results.append(id_url.to_bin(discovered_idurls(layer_id=layer_id).pop(0)))
    if _Debug:
        lg.out(_DebugLevel, 'lookup.consume_discovered_idurls : %s' % results)
    return results


def extract_discovered_idurls(count=1, layer_id=0):
    if not discovered_idurls(layer_id=layer_id):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.extract_discovered_idurls returns empty list')
        return []
    discovered = list(discovered_idurls(layer_id=layer_id))
    # random.shuffle(discovered)
    results = id_url.to_bin_list(discovered[:count])
    if _Debug:
        lg.out(_DebugLevel, 'lookup.extract_discovered_idurls : %s' % results)
    return results


#------------------------------------------------------------------------------


def random_proxy_router(**kwargs):
    from bitdust.dht import dht_records
    kwargs['layer_id'] = dht_records.LAYER_PROXY_ROUTERS
    return start(**kwargs)


def random_supplier(**kwargs):
    from bitdust.dht import dht_records
    kwargs['layer_id'] = dht_records.LAYER_SUPPLIERS
    return start(**kwargs)


def random_message_broker(**kwargs):
    from bitdust.dht import dht_records
    kwargs['layer_id'] = dht_records.LAYER_MESSAGE_BROKERS
    return start(**kwargs)


def random_merchant(**kwargs):
    from bitdust.dht import dht_records
    kwargs['layer_id'] = dht_records.LAYER_MERCHANTS
    return start(**kwargs)


def random_customer(**kwargs):
    from bitdust.dht import dht_records
    kwargs['layer_id'] = dht_records.LAYER_CUSTOMERS
    return start(**kwargs)


def random_web_socket_router(**kwargs):
    from bitdust.dht import dht_records
    kwargs['layer_id'] = dht_records.LAYER_WEB_SOCKET_ROUTERS
    return start(**kwargs)


#------------------------------------------------------------------------------


def start(
    count=1,
    consume=True,
    lookup_method=None,
    observe_method=None,
    process_method=None,
    force_discovery=False,
    ignore_idurls=[],
    is_idurl=True,
    layer_id=0,
):
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
        ignore_idurls=ignore_idurls,
        is_idurl=is_idurl,
        layer_id=layer_id,
    )
    if is_idurl and not force_discovery and len(discovered_idurls(layer_id=layer_id)) > count:
        if _Debug:
            lg.out(_DebugLevel - 4, 'lookup.start  knows %d discovered nodes, SKIP and return %d nodes' % (len(discovered_idurls(layer_id=layer_id)), count))
        if consume:
            idurls = consume_discovered_idurls(count, layer_id=layer_id)
        else:
            idurls = extract_discovered_idurls(count, layer_id=layer_id)
        reactor.callLater(0, t.result_defer.callback, idurls)  # @UndefinedVariable
        return t
    # if force_discovery:
    #     discovered_idurls(layer_id=layer_id).clear()
    _LookupTasks.append(t)
    reactor.callLater(0, work)  # @UndefinedVariable
    if _Debug:
        lg.out(_DebugLevel - 4, 'lookup.start  new DiscoveryTask created for %d nodes at layer %d' % (count, layer_id))
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
    if _CurrentLookupTask.stopped or not _CurrentLookupTask.result_defer or not _CurrentLookupTask.lookup_method:
        lg.warn('task %s is closed' % _CurrentLookupTask)
        _CurrentLookupTask = None
        return
    _CurrentLookupTask.start()
    if _CurrentLookupTask.result_defer:
        _CurrentLookupTask.result_defer.addCallback(on_lookup_task_success)
        _CurrentLookupTask.result_defer.addErrback(on_lookup_task_failed)
    else:
        lg.warn('task %s was closed immediately' % _CurrentLookupTask)
        _CurrentLookupTask = None


#------------------------------------------------------------------------------


def lookup_in_dht(layer_id=0):
    """
    Pick random node from Distributed Hash Table.
    Generates
    """
    if _Debug:
        lg.out(_DebugLevel, 'lookup.lookup_in_dht layer_id=%d' % (layer_id, ))
    d = dht_service.find_node(dht_service.random_key(), layer_id=layer_id)
    d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='lookup_in_dht')
    return d


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
        lg.out(_DebugLevel, 'lookup.observe_dht_node   %s  layer_id=%d' % (node, layer_id))
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
        lg.out(_DebugLevel, 'lookup.process_idurl %r from %r' % (idurl, node))
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
        ignore_idurls=[],
        is_idurl=True,
        layer_id=0,
    ):
        global _LookupMethod
        global _ObserveMethod
        global _ProcessMethod
        global _LatestLookupID
        _LatestLookupID += 1
        self.id = _LatestLookupID
        self.lookup_method = lookup_method or _LookupMethod
        self.observe_method = observe_method or _ObserveMethod
        self.process_method = process_method or _ProcessMethod
        self.ignore_idurls = ignore_idurls
        self.started = time.time()
        self.is_idurl = is_idurl
        self.layer_id = layer_id
        self.count = count
        self.consume = consume
        self.observed_count = 0
        self.cached_count = 0
        self.succeed = 0
        self.failed = 0
        self.lookup_now = False
        self.stopped = False
        self.observe_finished = False
        self.lookup_task = None
        self.result_defer = Deferred(canceller=lambda d: self._close())
        self.result_defer.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='DiscoveryTask')
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r].__init__   layer_id=%d' % (self.id, self.layer_id))

    def __del__(self):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r].__del__   layer_id=%d' % (self.id, self.layer_id))

    def start(self):
        if self.stopped:
            lg.warn('DiscoveryTask[%r] : task already stopped' % self.id)
            return None
        if self.lookup_task and not self.lookup_task.called:
            lg.warn('DiscoveryTask[%r] : lookup_nodes() method already called' % self.id)
            return self.lookup_task
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r].start  layer_id=%d' % (self.id, self.layer_id))
        return self._lookup_nodes()

    def stop(self):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r].stop' % self.id)
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
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r].close finished in %f seconds' % (self.id, round(time.time() - self.started, 3)))

    def _lookup_nodes(self):
        if self.lookup_task and not self.lookup_task.called:
            if _Debug:
                lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._lookup_nodes    SKIP, already started' % self.id)
            return self.lookup_task
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._lookup_nodes layer_id=%d' % (self.id, self.layer_id))
        self.lookup_now = True
        self.lookup_task = self.lookup_method(layer_id=self.layer_id)
        self.lookup_task.addCallback(self._on_nodes_discovered)
        self.lookup_task.addErrback(self._on_lookup_failed)
        return self.lookup_task

    def _observe_nodes(self, nodes):
        if self.stopped:
            lg.warn('DiscoveryTask[%r] : discovery process already stopped' % self.id)
            return
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._observe_nodes  started for %d items  layer_id=%d' % (self.id, len(nodes), self.layer_id))
        observe_list = []
        for node in nodes:
            d = self.observe_method(node, layer_id=self.layer_id)
            d.addCallback(self._on_node_observed, node)
            d.addErrback(self._on_node_observe_failed, node)
            observe_list.append(d)
        self.observed_count = len(nodes)
        dl = DeferredList(observe_list, consumeErrors=False)
        dl.addCallback(self._on_all_nodes_observed)
        dl.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='DiscoveryTask._observe_nodes')

    def _report_result(self, results=None):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]_report_result in %f seconds   %s,   result_defer=%s' % (self.id, round(time.time() - self.started, 3), str(results), self.result_defer))
        if results is None:
            if self.consume:
                results = consume_discovered_idurls(self.count, layer_id=self.layer_id)
                if _Debug:
                    lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]    %d results consumed, %d were requested' % (self.id, len(results), self.count))
            else:
                results = extract_discovered_idurls(self.count, layer_id=self.layer_id)
                if _Debug:
                    lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]    %d results extracted, %d were requested' % (self.id, len(results), self.count))
        if self.result_defer and not self.result_defer.called:
            self.result_defer.callback(results)
        self.result_defer = None

    def _report_fails(self, err):
        lg.err('DHT lookup %r failed: %r' % (self.id, err))
        if self.result_defer:
            self.result_defer.errback(err)
        self.result_defer = None

    def _on_node_succeed(self, node, idurl):
        self.succeed += 1
        if _Debug:
            lg.out(_DebugLevel, 'lookup.lookup.DiscoveryTask[%r]._on_node_succeed %r : %r' % (self.id, node, idurl))
        reactor.callLater(0, self._on_node_processed, node, idurl)  # @UndefinedVariable
        return node

    def _on_node_process_failed(self, err, node):
        self.failed += 1
        if _Debug:
            lg.warn('DiscoveryTask[%r] : node %r processing failed with  %r' % (self.id, node, err))
        reactor.callLater(0, self._on_node_processed, node, None)  # @UndefinedVariable
        return None

    def _on_node_observe_failed(self, err, node):
        try:
            self.failed += 1
            if _Debug:
                err = strng.to_text(err, errors='ignore')
                if err.count('idurl observe failed'):
                    err = 'idurl observe failed'
                lg.args(_DebugLevel, node=node, err=err, task_id=self.id)
        except:
            lg.exc()
        return None

    def _on_node_observed(self, value, node):
        if self.stopped:
            lg.warn('DiscoveryTask[%r] : node observed, but discovery process already stopped' % self.id)
            return None
        if not self.is_idurl:
            return value
        idurl = id_url.to_bin(value)
        if _Debug:
            lg.out(_DebugLevel + 4, 'lookup.DiscoveryTask[%r]._on_node_observed %r : %r' % (self.id, node, idurl))
        cached_time = known_idurls().get(idurl)
        if cached_time and time.time() - cached_time < 30.0:
            if _Debug:
                lg.out(_DebugLevel + 4, 'lookup.DiscoveryTask[%r]._on_node_observed   SKIP processing node %r because already observed recently' % (self.id, idurl))
            self._on_identity_cached(idurl, node)
            return idurl
        d = self.process_method(idurl, node)
        d.addCallback(self._on_identity_cached, node)
        d.addErrback(self._on_node_process_failed, node)
        return idurl

    def _on_node_processed(self, node, idurl):
        if self.stopped:
            if _Debug:
                lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._on_node_processed   node %s processed but task already finished' % (self.id, idurl))
            return None
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._on_node_processed  %r  discovered_idurls=%d count=%d  idurl=%s' % (self.id, node, len(discovered_idurls(layer_id=self.layer_id)), self.count, idurl))
        if self.succeed + self.failed >= self.count:
            if _Debug:
                lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._on_node_processed   enough node processed : succeed=%d  failed=%d' % (self.id, self.succeed, self.failed))
            self._report_result()
            # self._close()
            return node
        if self.succeed + self.failed >= self.observed_count:
            if _Debug:
                lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._on_node_processed   all observed nodes are processed : succeed=%d  failed=%d observed_count=%d' % (self.id, self.succeed, self.failed, self.observed_count))
            self._report_result()
            self._close()
            return node
        if self.observe_finished:
            lg.warn('observe process already finished')
            self._report_result()
            self._close()
        return node

    def _on_all_nodes_observed(self, observe_results):
        if self.stopped:
            lg.warn('DiscoveryTask[%r] : observe finished, but discovery process already stopped' % self.id)
            return
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._on_all_nodes_observed results: %r, discovered nodes: %d' % (self.id, observe_results, len(discovered_idurls(layer_id=self.layer_id))))
        self.observe_finished = True
        found_any_nodes = False
        results = []
        for one_result in observe_results:
            if one_result[0] and one_result[1]:
                found_any_nodes = True
                results.append(one_result[1])
        if not self.is_idurl:
            self._report_result(results=results)
            self._close()
            return
        if not found_any_nodes:
            lg.warn('DiscoveryTask[%r] : did not observed any nodes' % self.id)
            self._report_result()
            self._close()

    def _on_identity_cached(self, idurl, node):
        if self.stopped:
            return None
        if not idurl:
            self._on_node_process_failed(None, node)
            return None
        if id_url.is_in(idurl, self.ignore_idurls):
            if _Debug:
                lg.dbg(_DebugLevel, 'lookup.DiscoveryTask[%r]._on_identity_cached IGNORE %r' % (self.id, idurl))
            self._on_node_process_failed(None, node)
            return None
        self.cached_count += 1
        idurl = id_url.to_bin(idurl)
        if idurl not in discovered_idurls(layer_id=self.layer_id):
            discovered_idurls(layer_id=self.layer_id).append(idurl)
        known_idurls()[idurl] = time.time()
        self._on_node_succeed(node, idurl)
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._on_identity_cached : %s' % (self.id, idurl))
        return idurl

    def _on_nodes_discovered(self, nodes):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._on_nodes_discovered : %s, stopped=%s' % (self.id, str(nodes), self.stopped))
        self.lookup_now = False
        if self.stopped:
            lg.warn('DiscoveryTask[%r] : nodes are discovered, but the task was already stopped' % self.id)
            self._close()
            return None
        if not nodes:
            self._report_result()
            self._close()
            return None
        random.shuffle(nodes)
        self._observe_nodes(nodes)
        return None

    def _on_lookup_failed(self, err):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask[%r]._on_lookup_failed %s' % (self.id, err))
        self.lookup_now = False
        if self.stopped:
            lg.warn('DiscoveryTask[%r] : discovery process already stopped' % self.id)
            self._close()
            return
        self._report_fails(err)
        self._close()
        return err


#------------------------------------------------------------------------------
