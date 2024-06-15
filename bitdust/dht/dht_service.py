#!/usr/bin/python
# dht_service.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (dht_service.py) is part of BitDust Software.
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
"""
..

module:: dht_service
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import sys
import hashlib
import random
import optparse
import pprint
import json

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.task import LoopingCall  #@UnresolvedImport
from twisted.internet.defer import Deferred, DeferredList, fail  # @UnresolvedImport

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.system import bpio
from bitdust.system import local_fs

from bitdust.main import settings
from bitdust.main import events

from bitdust.lib import strng
from bitdust.lib import utime
from bitdust.lib import jsn

from bitdust.userid import id_url

from bitdust.dht import known_nodes

#------------------------------------------------------------------------------

from bitdust_forks.entangled.kademlia import constants  # @UnresolvedImport
from bitdust_forks.entangled.kademlia.datastore import SQLiteVersionedJsonDataStore  # @UnresolvedImport
from bitdust_forks.entangled.kademlia.node import rpcmethod, MultiLayerNode  # @UnresolvedImport
from bitdust_forks.entangled.kademlia.protocol import KademliaMultiLayerProtocol, encoding, msgformat  # @UnresolvedImport
from bitdust_forks.entangled.kademlia.routingtable import TreeRoutingTable  # @UnresolvedImport
from bitdust_forks.entangled.kademlia.contact import Contact  # @UnresolvedImport

#------------------------------------------------------------------------------

KEY_EXPIRE_MIN_SECONDS = 60*2
KEY_EXPIRE_MAX_SECONDS = constants.dataExpireSecondsDefaut
RECEIVING_FREQUENCY_SEC = 0.01
SENDING_FREQUENCY_SEC = 0.02  # must be always slower than receiving frequency!
RECEIVING_QUEUE_LENGTH_CRITICAL = 100
SENDING_QUEUE_LENGTH_CRITICAL = 50
DEFAULT_CACHE_TTL = 60*60*3

#------------------------------------------------------------------------------

_MyNode = None
_ActiveLookup = None
_ActiveLookupLayerID = None
_Counters = {}
_ProtocolVersion = 7
_Cache = {}

#------------------------------------------------------------------------------


def init(udp_port, dht_dir_path=None, open_layers=[]):
    global _MyNode
    if _MyNode is not None:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.init SKIP, DHTNode already exist')
        return
    nw_info = known_nodes.network_info()
    if 'bucket_size' in nw_info:
        constants.k = nw_info['bucket_size']
    if 'parallel_calls' in nw_info:
        constants.alpha = nw_info['parallel_calls']
    if 'rpc_timeout' in nw_info:
        constants.rpcTimeout = nw_info['rpc_timeout']
    if 'refresh_timeout' in nw_info:
        constants.refreshTimeout = nw_info['refresh_timeout']
    if 'max_age' in nw_info:
        constants.dataExpireTimeout = nw_info['max_age']
    if 'default_age' in nw_info:
        constants.dataExpireSecondsDefaut = nw_info['default_age']
    if dht_dir_path is None:
        dht_dir_path = settings.ServiceDir('service_entangled_dht')
    if not os.path.isdir(dht_dir_path):
        os.makedirs(dht_dir_path)
    list_layers = []
    if os.path.isdir(dht_dir_path):
        list_layers = os.listdir(dht_dir_path)
    cache_dir_path = os.path.join(dht_dir_path, 'cache')
    if not os.path.isdir(cache_dir_path):
        os.makedirs(cache_dir_path)
    load_cache(cache_dir_path)
    if _Debug:
        lg.dbg(_DebugLevel, 'dht_dir_path=%r list_layers=%r network_info=%r' % (dht_dir_path, list_layers, nw_info))
    layerStores = {}
    for layer_filename in list_layers:
        if not layer_filename.startswith('db_'):
            continue
        try:
            layer_name = layer_filename.replace('db_', '')
            layer_id = int(layer_name)
        except:
            continue
        db_file_path = os.path.join(dht_dir_path, 'db_%d' % layer_id)
        dbPath = bpio.portablePath(db_file_path)
        if _Debug:
            lg.dbg(_DebugLevel, 'found existing db layer: %r at %r' % (layer_id, dbPath))
        try:
            dataStore = SQLiteVersionedJsonDataStore(dbFile=dbPath)
        except:
            lg.warn('failed reading DHT records, removing %s and starting clean DB' % dbPath)
            lg.exc()
            try:
                os.remove(dbPath)
            except:
                pass
            dataStore = SQLiteVersionedJsonDataStore(dbFile=dbPath)
        layerStores[layer_id] = dataStore
    if not layerStores:
        db_file_path = os.path.join(dht_dir_path, 'db_0')
        dbPath = bpio.portablePath(db_file_path)
        layerStores[0] = SQLiteVersionedJsonDataStore(dbFile=dbPath)
    _MyNode = DHTNode(
        udpPort=udp_port,
        dataStores=layerStores,
        networkProtocol=DHTProtocol,
    )
    for layer_id in open_layers:
        open_layer(layer_id=layer_id, dht_dir_path=dht_dir_path, connect_now=False)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.init UDP port is %d, DB file path is %s, my DHT ID is %s' % (udp_port, dht_dir_path, _MyNode.layers[0]))


def shutdown():
    global _MyNode
    if _MyNode is not None:
        for ds in _MyNode._dataStores.values():
            ds._db.close()
        _MyNode._protocol.node = None
        del _MyNode
        _MyNode = None
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.shutdown')
    else:
        lg.warn('DHTNode not exist')


#------------------------------------------------------------------------------


def node():
    global _MyNode
    return _MyNode


def connect(seed_nodes=[], layer_id=0, attach=False):
    global _MyNode
    result = Deferred()

    if _Debug:
        lg.args(_DebugLevel, layer_id=layer_id, attach=attach, seed_nodes=seed_nodes)

    if not node():
        lg.err('node is not initialized')
        result.errback(Exception('node is not initialized'))
        return result

    joinDeferred = node().connectingTask(layer_id)
    if joinDeferred:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect SKIP, already joining layer %d' % layer_id)
        if joinDeferred.called:
            lg.warn('joinDeferred already called')
            reactor.callLater(0, result.callback, True)  # @UndefinedVariable
        else:
            joinDeferred.addBoth(lambda x: result.callback(True))
        return result

    if node().refreshers.get(layer_id, None) and node().refreshers[layer_id].active():
        node().refreshers[layer_id].reset(0)
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect SKIP seems like DHT already active, RESET current refresher task')
        reactor.callLater(0, result.callback, True)  # @UndefinedVariable
        return result

    if not node().listener:
        node().listenUDP()
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect opened a new listener : %r' % node().listener)

    if _Debug:
        lg.out(_DebugLevel, 'dht_service.connect STARTING with %d known nodes in layer %d:' % (len(seed_nodes), layer_id))
        for onenode in seed_nodes:
            lg.out(_DebugLevel, '    %s:%s' % onenode)

    if not seed_nodes:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect  SKIP : no seed nodes provided')
        reactor.callLater(0, result.callback, True)  # @UndefinedVariable
        events.send('dht-layer-connected', data=dict(layer_id=layer_id))
        return result

    def _on_connected(ok):
        if _Debug:
            lg.args(_DebugLevel, ok=ok, layer_id=layer_id)
        events.send('dht-layer-connected', data=dict(layer_id=layer_id))
        return ok

    result.addCallback(_on_connected)

    def _on_join_success(live_contacts, resolved_seed_nodes, _layer_id):
        ok = live_contacts and len(live_contacts) > 0 and live_contacts[0]
        if isinstance(live_contacts, dict):
            lg.err('Unexpected result from joinNetwork: %s' % pprint.pformat(live_contacts))
        else:
            if ok:
                if _Debug:
                    lg.out(_DebugLevel, 'dht_service.connect DHT JOIN SUCCESS   layer_id=%d attach=%r' % (_layer_id, attach))
            else:
                lg.warn('No live DHT contacts found...  your node is NOT CONNECTED TO DHT NETWORK at layer %d' % _layer_id)
        if _Debug:
            lg.out(_DebugLevel, 'for layer %d found DHT nodes: %s' % (_layer_id, live_contacts))
            lg.out(_DebugLevel, 'resolved SEED nodes: %r' % resolved_seed_nodes)
            lg.out(_DebugLevel, 'DHT node is active, ID%d=[%s]' % (_layer_id, node().layers[_layer_id]))
        reactor.callLater(0, result.callback, ok)  # @UndefinedVariable
        return live_contacts

    def _on_join_failed(x):
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect DHT JOIN FAILED : %s' % x)
        result.errback(x)
        return None

    def _on_hosts_resolved(resolved_seed_nodes, _layer_id):
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect RESOLVED %d live nodes' % (len(resolved_seed_nodes)))
            for onenode in resolved_seed_nodes:
                lg.out(_DebugLevel, '    %s:%s' % onenode)
        if not resolved_seed_nodes:
            resolved_seed_nodes = []
        d = node().joinNetwork(resolved_seed_nodes, layerID=_layer_id, attach=attach)
        d.addCallback(_on_join_success, resolved_seed_nodes, _layer_id=_layer_id)
        d.addErrback(_on_join_failed)
        if not node().expire_task.running:
            # reactor.callLater(random.randint(0, 60), node().expire_task.start, int(KEY_EXPIRE_MIN_SECONDS / 2), now=True)  # @UndefinedVariable
            node().expire_task.start(int(KEY_EXPIRE_MIN_SECONDS/2), now=True)  # @UndefinedVariable
        return resolved_seed_nodes

    def _on_hosts_resolve_failed(x):
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect ERROR : hosts not resolved: %s' % x)
        result.errback(x)
        return None

    d = resolve_hosts(seed_nodes)
    d.addCallback(_on_hosts_resolved, _layer_id=layer_id)
    d.addErrback(_on_hosts_resolve_failed)
    return result


def suspend(layer_id):
    if not node():
        return False
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.suspend    layer %d' % layer_id)
    node().leaveNetwork(layer_id)
    return True


def disconnect():
    global _MyNode
    if not node():
        return False
    if node().expire_task and node().expire_task.running:
        node().expire_task.stop()
    for refresher in node().refreshers.values():
        if refresher and refresher.active():
            refresher.cancel()
    node().refreshers.clear()
    if node().listener:
        node().listener.stopListening()
    return True


def reconnect():
    global _MyNode
    if not node():
        return None
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.reconnect')
    return node().reconnect()


#------------------------------------------------------------------------------


def is_layer_active(layer_id):
    if not node():
        return False
    return layer_id in node().active_layers


def open_layer(layer_id, seed_nodes=[], dht_dir_path=None, connect_now=False, attach=False):
    global _MyNode
    if not node():
        result = Deferred()
        result.callback(False)
        return result
    if not layer_id in node().layers:
        if dht_dir_path is None:
            dht_dir_path = settings.ServiceDir('service_entangled_dht')
        if not os.path.isdir(dht_dir_path):
            os.makedirs(dht_dir_path)
        layer_file_path = os.path.join(dht_dir_path, 'db_%d' % layer_id)
        dbPath = bpio.portablePath(layer_file_path)
        if not node().createLayer(layer_id, dataStore=SQLiteVersionedJsonDataStore(dbFile=dbPath)):
            lg.warn('failed to create DHT layer %d' % layer_id)
            result = Deferred()
            result.callback(False)
            return result
    if not connect_now:
        result = Deferred()
        result.callback(True)
        return result
    result = connect(seed_nodes=seed_nodes, layer_id=layer_id, attach=attach)
    lg.info('DHT layer %d opened and connecting to the seed nodes: %r' % (layer_id, seed_nodes))
    return result


def close_layer(layer_id):
    global _MyNode
    if not node():
        return False
    lg.info('destroying DHT layer %d' % layer_id)
    return node().destroyLayer(layer_id)


#------------------------------------------------------------------------------


def count(name):
    global _Counters
    if name not in _Counters:
        _Counters[name] = 0
    _Counters[name] += 1
    return True


def counter(name):
    global _Counters
    return _Counters.get(name, 0)


def drop_counters():
    global _Counters
    ret = _Counters.copy()
    _Counters.clear()
    return ret


#------------------------------------------------------------------------------


def on_host_resolved(ip, port, host, result_list, total_hosts, result_defer):
    if not strng.is_string(ip) or port is None:
        result_list.append(None)
        lg.warn('%r failed to resolve' % host)
    else:
        result_list.append((
            ip,
            port,
        ))
    if len(result_list) != total_hosts:
        return None
    return result_defer.callback([_f for _f in result_list if _f])


def on_host_failed(err, host, result_list, total_hosts, result_defer):
    lg.warn('%r failed to resolve: %r' % (host, err))
    result_list.append(None)
    if len(result_list) != total_hosts:
        return None
    return result_defer.callback([_f for _f in result_list if _f])


def resolve_hosts(nodes_list):
    result_defer = Deferred()
    if not nodes_list:
        result_defer.callback([])
        return result_defer
    result_list = []
    for node_tuple in nodes_list:
        d = reactor.resolve(strng.to_text(node_tuple[0]))  #@UndefinedVariable
        d.addCallback(on_host_resolved, node_tuple[1], node_tuple[0], result_list, len(nodes_list), result_defer)
        d.addErrback(on_host_failed, node_tuple[0], result_list, len(nodes_list), result_defer)
    return result_defer


#------------------------------------------------------------------------------


def random_key():
    return key_to_hash(strng.to_text(random.getrandbits(255)).encode())


def key_to_hash(key):
    key = strng.to_bin(key)
    h = hashlib.sha1()
    h.update(key)
    return h.hexdigest()


#------------------------------------------------------------------------------


def make_key(key, prefix, index=0, version=None):
    global _ProtocolVersion
    if not version:
        version = _ProtocolVersion
    return '{}:{}:{}:{}'.format(prefix, key, index, version)


def split_key(key_str):
    key_str = strng.to_text(key_str)
    prefix, key, index, version = key_str.split(':')
    return dict(
        key=key,
        prefix=prefix,
        index=index,
        version=version,
    )


#------------------------------------------------------------------------------


def on_success(result, method, key, *args, **kwargs):
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.on_success   %s(%r)    result is %s' % (method, key, type(result)))
    return result


def on_error(x, method, key):
    try:
        errmsg = x.value.subFailure.getErrorMessage()
    except:
        try:
            errmsg = x.getErrorMessage()
        except:
            try:
                errmsg = x.value
            except:
                try:
                    errmsg = str(x)
                except:
                    errmsg = 'Unknown Error'
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.on_error   %s(%s)   returned an ERROR:\n%r' % (method, key, errmsg))
    return x


#------------------------------------------------------------------------------


def get_value(key, layer_id=0, parallel_calls=None):
    if not node():
        return fail(Exception('DHT service is off'))
    count('get_value_%s' % key)
    key_hash = key_to_hash(key)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.get_value key=[%r] key_hash=%s' % (key, key_hash))
    d = node().iterativeFindValue(
        key=key_hash,
        rpc='findValue',
        layerID=layer_id,
        parallel_calls=parallel_calls,
    )
    d.addCallback(on_success, 'get_value', key)
    d.addErrback(on_error, 'get_value', key)
    return d


def set_value(key, value, age=0, expire=KEY_EXPIRE_MAX_SECONDS, collect_results=True, layer_id=0, parallel_calls=None):
    if not node():
        return fail(Exception('DHT service is off'))
    count('set_value_%s' % key)
    sz_bytes = len(value)
    key_hash = key_to_hash(key)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.set_value key=[%s] key_hash=%s with %d bytes for %d seconds' % (key, key_hash, sz_bytes, expire))
    if expire < KEY_EXPIRE_MIN_SECONDS:
        expire = KEY_EXPIRE_MIN_SECONDS
    if expire > KEY_EXPIRE_MAX_SECONDS:
        expire = KEY_EXPIRE_MAX_SECONDS
    d = node().iterativeStore(
        key=key_hash,
        value=value,
        age=age,
        expireSeconds=expire,
        collect_results=collect_results,
        layerID=layer_id,
        parallel_calls=parallel_calls,
    )
    d.addCallback(on_success, 'set_value', key, value)
    d.addErrback(on_error, 'set_value', key)
    return d


def delete_key(key, layer_id=0, parallel_calls=None):
    if not node():
        return fail(Exception('DHT service is off'))
    count('delete_key_%s' % key)
    key_hash = key_to_hash(key)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.delete_key [%s] key_hash=%s' % (key, key_hash))
    d = node().iterativeDelete(key_hash, layerID=layer_id, parallel_calls=parallel_calls)
    d.addCallback(on_success, 'delete_value', key)
    d.addErrback(on_error, 'delete_key', key)
    return d


#------------------------------------------------------------------------------


def on_read_json_response(response, key, result_defer=None):
    if _Debug:
        lg.out(_DebugLevel + 6, 'dht_service.on_read_json_response [%r] : %s' % (key, type(response)))
    json_value = None
    if isinstance(response, list):
        if _Debug:
            lg.out(_DebugLevel, '        response is a list, value not found')
        if result_defer:
            result_defer.callback(response)
        return None
    if isinstance(response, dict):
        if response.get('values'):
            try:
                latest_revision = 0
                latest = 0
                json_value = jsn.loads_text(response['values'][0][0])
                for v in response['values']:
                    j = jsn.loads_text(v[0])
                    rev = j.get('revision', -1)
                    if rev >= 0:
                        if rev > latest_revision:
                            latest = v[1]
                            latest_revision = rev
                            json_value = j
                    else:
                        if v[1] > latest:
                            latest = v[1]
                            latest_revision = rev
                            json_value = j
            except:
                lg.exc()
                if _Debug:
                    lg.out(_DebugLevel, '        invalid json value found in DHT, return None')
                if result_defer:
                    result_defer.errback(Exception('invalid json value found in DHT'))
                return None
        else:
            if _Debug:
                lg.out(_DebugLevel, '        response is a dict, "values" field is empty, value not found')
            if result_defer:
                result_defer.callback(response.get('activeContacts', []))
            return None
    if _Debug:
        lg.out(_DebugLevel, '        response is a dict, value is OK')
    if result_defer:
        result_defer.callback(json_value)
    return json_value


def get_json_value(key, layer_id=0, update_cache=True):
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.get_json_value key=[%r] layer_id=%d update_cache=%s' % (key, layer_id, update_cache))
    ret = Deferred()
    d = get_value(key, layer_id=layer_id)
    d.addCallback(on_read_json_response, key, ret)
    d.addErrback(ret.errback)
    if update_cache:
        d.addCallback(on_json_response_to_be_cached, key=key, layer_id=layer_id)
    return ret


def set_json_value(key, json_data, age=0, expire=KEY_EXPIRE_MAX_SECONDS, collect_results=True, layer_id=0):
    if not node():
        return fail(Exception('DHT service is off'))
    try:
        value = jsn.dumps(json_data, indent=0, sort_keys=True, separators=(',', ':'))
    except:
        return fail(Exception('bad input json data'))
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.set_json_value key=[%r] layer_id=%d with %d bytes' % (key, layer_id, len(repr(value))))
    return set_value(key=key, value=value, age=age, expire=expire, collect_results=collect_results, layer_id=layer_id)


#------------------------------------------------------------------------------


def validate_rules(value, key, rules, result_defer=None, raise_for_result=False, populate_meta_fields=False):
    """
    Will be executed on both sides: sender and receiver for each (key,value) get / set request on DHT.
    Can return in `result_defer` : errback, callback with list (closest nodes), callback with dict
    """
    if not rules:
        lg.err('DHT record must have validation rules applied')
        if result_defer:
            result_defer.errback(Exception('data must have validation rules applied'))
        return None

    if not isinstance(value, dict):
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.validate_rules    key=[%s] not found : %s' % (key, type(value)))
        if not result_defer:
            return value if populate_meta_fields else None
        if raise_for_result:
            result_defer.errback(Exception('value not found'))
            return None
        if not populate_meta_fields:
            result_defer.callback(None)
            return None
        result_defer.callback(value)
        return None

    try:
        expected_record_type = rules['type'][0]['arg']
    except:
        lg.exc()
        if result_defer:
            result_defer.errback(Exception('invalid validation rules can not be applied'))
        return None

    passed = True
    errors = []
    try:
        if populate_meta_fields:
            # Otherwise those records will not pass validation
            if value.get('type') != expected_record_type:
                value['type'] = expected_record_type
            if value.get('key') != key:
                value['key'] = key

        for field, field_rules in rules.items():
            if _Debug:
                lg.out(_DebugLevel, '    %r : %r' % (field, field_rules))
            for rule in field_rules:
                if 'op' not in rule:
                    lg.warn('incorrect validation rule found: %r' % rule)
                    continue
                if rule['op'] == 'equal' and rule.get('arg') != strng.to_text(value.get(field)):
                    passed = False
                    errors.append((
                        field,
                        rule,
                    ))
                    break
                if rule['op'] == 'exist' and field not in value:
                    passed = False
                    errors.append((
                        field,
                        rule,
                    ))
                    break
            if not passed:
                break
    except Exception as exc:
        lg.exc()
        passed = False
        errors = [(
            'unknown',
            exc,
        )]
    if not passed:
        lg.exc(exc_value=Exception('DHT record validation failed, errors: %s' % errors))
        if result_defer:
            result_defer.errback(Exception('DHT record validation failed: %r' % errors))
        return None
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.validate_rules   key=[%s] : value is OK' % key)
    if result_defer:
        result_defer.callback(value)
    return value


def validate_before_store(key, value, originalPublisherID, age, expireSeconds, **kwargs):
    """
    Will be executed on receiver side for each (key,value) set request on DHT
    """
    try:
        json_new_value = jsn.loads(value)
    except:
        # not a json data to be written - this is not valid
        lg.exc()
        raise ValueError('input data is not a json value: %r' % value)
    if _Debug:
        lg.out(_DebugLevel + 8, 'dht_service.validate_before_store key=[%s] with %d bytes value' % (key, len(value)))
    new_record_type = json_new_value.get('type')
    if not new_record_type:
        if _Debug:
            lg.out(_DebugLevel, '        new json data do not have "type" field present, store operation FAILED')
        raise ValueError('input data do not have "type" field present: %r' % json_new_value)
    layer_id = kwargs.get('layerID', 0)
    if key not in node()._dataStores[layer_id]:
        if _Debug:
            lg.out(_DebugLevel, '        previous value not exists yet, store OK')
        return True
    prev_value = node()._dataStores[layer_id][key]
    try:
        json_prev_value = jsn.loads(prev_value)
    except:
        if _Debug:
            lg.out(_DebugLevel, '        current value in DHT is not a json data, will be overwritten, store OK')
        return True
    prev_record_type = json_prev_value.get('type')
    if prev_record_type and prev_record_type != new_record_type:
        if _Debug:
            lg.out(_DebugLevel, '        new json data type did not match to existing record type, store operation FAILED')
        raise ValueError('new json data type do not match to existing record type: %r' % json_prev_value)
    # TODO: need to include "key" field into DHT record and validate it as well
    # new_record_key = json_new_value.get('key')
    # if not new_record_key:
    #     if _Debug:
    #         lg.out(_DebugLevel, '        new json data do not have "key" field present, store operation FAILED')
    #     return False
    # if new_record_key != key:
    #     if _Debug:
    #         lg.out(_DebugLevel, '        new json data do not have "key" field set properly, store operation FAILED')
    #     return False
    # prev_record_key = json_prev_value.get('key')
    # if prev_record_key and prev_record_key != new_record_key:
    #     if _Debug:
    #         lg.out(_DebugLevel, '        new json data "key" field do not match to existing record "key", store operation FAILED')
    #     return False
    try:
        prev_revision = int(json_prev_value['revision'])
    except:
        prev_revision = -1
    try:
        new_revision = int(json_new_value['revision'])
    except:
        new_revision = -1
    if prev_revision >= 0:
        if new_revision < 0:
            if _Debug:
                lg.out(_DebugLevel, '        new json data must have a revision, store operation FAILED')
            raise ValueError('new json data must have a revision')
        if new_revision < prev_revision:
            if _Debug:
                lg.out(_DebugLevel, '        new json data must increment revision number, store operation FAILED')
            raise ValueError('new json data must increment revision number, current revision is %d ' % prev_revision)
        if new_revision == prev_revision:
            if prev_record_type == 'suppliers':
                prev_ecc_map = json_prev_value.get('ecc_map')
                new_ecc_map = json_new_value.get('ecc_map')
                if prev_ecc_map and new_ecc_map != prev_ecc_map:
                    if _Debug:
                        lg.out(_DebugLevel, '        new json data have same revision but different ecc_map, store operation FAILED')
                    raise ValueError('new json data have same revision but different ecc_map, current revision is %d ' % prev_revision)
                prev_suppliers = id_url.to_bin_list(json_prev_value.get('suppliers', []))
                new_suppliers = id_url.to_bin_list(json_new_value.get('suppliers', []))
                if prev_suppliers != new_suppliers:
                    if _Debug:
                        lg.out(_DebugLevel, '        new json data have same revision but different suppliers list, store operation FAILED')
                    raise ValueError('new json data have same revision but different suppliers list, current revision is %d ' % prev_revision)
            if prev_record_type == 'message_broker':
                prev_broker_idurl = json_prev_value.get('broker_idurl')
                new_broker_idurl = json_new_value.get('broker_idurl')
                prev_position = json_prev_value.get('position')
                new_position = json_new_value.get('position')
                if prev_broker_idurl is not None and prev_position is not None:
                    if prev_broker_idurl != new_broker_idurl or prev_position != new_position:
                        if _Debug:
                            lg.out(_DebugLevel, '        new json data have same revision but different broker info, store operation FAILED')
                        raise ValueError('new json data have same revision but different broker info, current revision is %d ' % prev_revision)
    if _Debug:
        lg.out(_DebugLevel, '        new json data is valid and matching existing DHT record, store OK')
    return True


def validate_before_request(key, **kwargs):
    """
    Will be executed on receiver side for each "direct" key request on DHT
    """
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.validate_before_request key=[%s]' % key)
    return True


def validate_data_written(store_results, key, json_data, result_defer):
    """
    Will be executed on sender side for each (key,value) set request on DHT
    """
    nodes = store_results
    results_collected = False
    if isinstance(store_results, tuple):
        results_collected = True
        nodes = store_results[0]
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.validate_data_written key=[%s]  %s  collected=%s  nodes=%r' % (key, type(store_results), results_collected, nodes))
    if results_collected:
        for result in store_results[1]:
            try:
                success = strng.to_text(result[0])
                response = result[1]
                success_str = repr(success)
                response_str = repr(response)
            except Exception as exc:
                lg.exc()
                result_defer.errback(exc)
                return None
            if success_str.count('TimeoutError') or response_str.count('TimeoutError'):
                continue
            if not success:
                if _Debug:
                    lg.out(_DebugLevel, '    store operation failed: %r' % response)
                result_defer.errback(ValueError(response))
                return None
            if response != 'OK':
                if _Debug:
                    lg.out(_DebugLevel, '    store operation failed, unexpected response received: %r' % response)
                result_defer.errback(ValueError(response))
                return None
        result_defer.callback(nodes)
        return None
    if isinstance(store_results, list):
        result_defer.callback(nodes)
    else:
        result_defer.errback(Exception('store operation failed, result is %s' % type(store_results)))
    return None


def validate_before_send(value, key, rules, populate_meta_fields):
    """
    Will be executed on sender side before every (key,value) set request towards DHT
    """
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.validate_before_send for key [%s]' % key)
    if populate_meta_fields:
        if value.get('key') != key:
            value['key'] = key
        if value.get('type') != rules['type'][0]['arg']:
            value['type'] = rules['type'][0]['arg']
    return validate_rules(value, key, rules, raise_for_result=False, populate_meta_fields=populate_meta_fields)


def validate_after_receive(value, key, rules, result_defer, raise_for_result, populate_meta_fields):
    """
    Will be executed on sender side for each (key,value) get response from DHT
    """
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.validate_after_receive for key [%s]' % key)
    response = validate_rules(value, key, rules, result_defer=result_defer, raise_for_result=raise_for_result, populate_meta_fields=populate_meta_fields)
    if not isinstance(response, dict):
        if populate_meta_fields:
            ret = {
                'key': key,
                'type': rules['type'][0]['arg'],
                'closest': response,
            }
            return ret
    if populate_meta_fields:
        if response.get('key') != key:
            response['key'] = key
        if response.get('type') != rules['type'][0]['arg']:
            response['type'] = rules['type'][0]['arg']
    return response


#------------------------------------------------------------------------------


def get_valid_data(key, rules={}, raise_for_result=False, return_details=False, layer_id=0, use_cache_ttl=None, update_cache=True):
    ret = Deferred()
    if use_cache_ttl is not None:
        d = get_cached_json_value(key, layer_id=layer_id, cache_ttl=use_cache_ttl)
    else:
        d = get_json_value(key, layer_id=layer_id, update_cache=update_cache)
    d.addCallback(validate_after_receive, key=key, rules=rules, result_defer=ret, raise_for_result=raise_for_result, populate_meta_fields=return_details)
    d.addErrback(ret.errback)
    return ret


def set_valid_data(key, json_data, age=0, expire=KEY_EXPIRE_MAX_SECONDS, rules={}, collect_results=False, layer_id=0):
    valid_json_data = validate_before_send(value=json_data, key=key, rules=rules, populate_meta_fields=True)
    if valid_json_data is None or not isinstance(valid_json_data, dict):
        return fail(Exception('invalid data going to be written, validation failed'))
    ret = Deferred()
    d = set_json_value(key, json_data=json_data, age=age, expire=expire, collect_results=collect_results, layer_id=layer_id)
    d.addCallback(validate_data_written, key, json_data, ret)
    d.addErrback(ret.errback)
    return ret


#------------------------------------------------------------------------------


def write_verify_republish_data(key, json_data, age=0, expire=KEY_EXPIRE_MAX_SECONDS, rules={}, layer_id=0):
    try:
        raw_value = jsn.dumps(json_data, indent=0, sort_keys=True, separators=(',', ':'))
    except:
        return fail(Exception('bad input json data'))

    ret = Deferred()
    _found_nodes = None
    _write_response = None
    _join = Deferred()
    _join.addCallback(_do_verify)
    _join.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='write_verify_republish_data')

    def _some_nodes_found(nodes):
        global _write_response
        global _found_nodes
        global _join
        if _Debug:
            lg.out(_DebugLevel, 'dht_service._some_nodes_found : %r' % nodes)
        if len(nodes) > 0:
            _found_nodes = nodes
        else:
            _found_nodes = []
        if _write_response:
            _join.callback(_write_response, _found_nodes)
        return nodes

    def _nodes_not_found(err):
        global _found_nodes
        global _join
        if _Debug:
            lg.out(_DebugLevel, 'dht_service._nodes_not_found err=%s' % str(err))
        _found_nodes = []
        _join.cancel()
        del _join
        ret.errback(err)
        return err

    def _write_ok(write_result):
        global _write_response
        global _found_nodes
        global _join
        if _Debug:
            lg.out(_DebugLevel, 'dht_service._write_ok : %r' % write_result)
        _write_response = write_result
        if _found_nodes is not None:
            _join.callback(_write_response, _found_nodes)
        return write_result

    def _write_failed(err):
        global _join
        if _Debug:
            lg.out(_DebugLevel, 'dht_service._write_failed  err=%r' % err)
        _join.cancel()
        del _join
        ret.errback(err)
        return err

    def _do_verify(write_response, found_nodes):
        if _Debug:
            lg.out(_DebugLevel, 'dht_service._do_verify  %r via nodes: %r' % (write_response, found_nodes))
        for node in found_nodes:
            node.request(b'verify_update', key, raw_value, age, expire)
        ret.callback(write_response, found_nodes)
        return None

    new_key = random_key()
    d_observer = find_node(new_key, layer_id=layer_id)
    d_observer.addCallback(_some_nodes_found)
    d_observer.addErrback(_nodes_not_found)

    d_write = set_valid_data(key=key, json_data=json_data, age=age, expire=expire, rules=rules, layer_id=layer_id)
    d_write.addCallback(_write_ok)
    d_write.addErrback(_write_failed)

    return ret


#------------------------------------------------------------------------------


def on_nodes_found(result, node_id64):
    global _ActiveLookup
    global _ActiveLookupLayerID
    on_success(result, 'find_node', node_id64)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.on_nodes_found   node_id=[%s], %d nodes found' % (node_id64, len(result)))
    # _ActiveLookupLayerID = None
    # _ActiveLookup = None
    return result


def on_lookup_failed(result, node_id64):
    global _ActiveLookup
    global _ActiveLookupLayerID
    on_error(result, 'find_node', node_id64)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.on_lookup_failed   node_id=[%s], result=%s' % (node_id64, result))
    # _ActiveLookupLayerID = None
    # _ActiveLookup = None
    return result


def find_node(node_id, layer_id=0):
    global _ActiveLookup
    global _ActiveLookupLayerID
    if _ActiveLookup and not _ActiveLookup.called and _ActiveLookupLayerID == layer_id:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.find_node SKIP, already started')
        return _ActiveLookup
    count('find_node')
    if not node():
        return fail(Exception('DHT service is off'))
    if layer_id not in node().active_layers:
        return fail(Exception('DHT layer %d is not active' % layer_id))
    node_id64 = node_id
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.find_node   node_id=[%s]  layer_id=%d' % (node_id64, layer_id))
    _ActiveLookupLayerID = layer_id
    _ActiveLookup = node().iterativeFindNode(node_id, layerID=layer_id)
    _ActiveLookup.addErrback(on_lookup_failed, node_id64)
    _ActiveLookup.addCallback(on_nodes_found, node_id64)
    return _ActiveLookup


#------------------------------------------------------------------------------


def get_node_data(key, layer_id=0):
    if not node():
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.get_node_data local node is not ready')
        return None
    count('get_node_data')
    if layer_id not in node().data:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.get_node_data   layer_id=%d   is not exist' % layer_id)
        return None
    key = strng.to_text(key)
    if key not in node().data[layer_id]:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.get_node_data   key=[%s] not exist   layer_id=%d' % (key, layer_id))
        return None
    value = node().data[layer_id][key]
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.get_node_data key=[%s] read %d bytes   layer_id=%d' % (key, len(strng.to_text(value) or ''), layer_id))
    return value


def set_node_data(key, value, layer_id=0):
    if not node():
        lg.warn('DHT node is not ready yet, not able to store key %r for layer_id=%d locally' % (key, layer_id))
        return False
    count('set_node_data')
    if layer_id not in node().data:
        node().data[layer_id] = {}
    key = strng.to_text(key)
    node().data[layer_id][key] = value
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.set_node_data key=[%s] wrote %d bytes  layer_id=%d' % (key, len(strng.to_text(value) or ''), layer_id))
    return True


def delete_node_data(key, layer_id=0):
    if not node():
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.delete_node_data local node is not ready')
        return False
    count('delete_node_data')
    if layer_id not in node().data:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.delete_node_data layer_id=%d  is not exist' % layer_id)
        return False
    key = strng.to_text(key)
    if key not in node().data[layer_id]:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.delete_node_data key=[%s] not exist' % key)
        return False
    node().data[layer_id].pop(key)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.delete_node_data key=[%s]   layer_id=%d' % (key, layer_id))
    return True


def dump_local_db(value_as_json=False):
    if not node():
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.dump_local_db local node is not ready')
        return None
    result = {}
    try:
        for layerID in node()._dataStores.keys():
            l = []
            for itm in node()._dataStores[layerID].getAllItems():
                if value_as_json:
                    if isinstance(itm['value'], dict):
                        _j = jsn.dumps(itm['value'], keys_to_text=True, errors='ignore')
                        itm['value'] = jsn.loads_text(_j, errors='ignore')
                    else:
                        try:
                            itm['value'] = jsn.loads_text(itm['value'], errors='ignore')
                        except:
                            itm['value'] = strng.to_text(itm['value'])
                itm['scope'] = 'global'
                l.append(itm)
            for k, v in node().data[layerID].items():
                l.append({
                    'key': k,
                    'value': v,
                    'scope': 'node',
                })
            result[layerID] = l
    except:
        lg.exc()
    return result


#------------------------------------------------------------------------------


def cache():
    global _Cache
    return _Cache


def load_cache(cache_dir_path):
    global _Cache
    _Cache.clear()
    total_records = 0
    records_per_layer = {}
    for layer_id_str in os.listdir(cache_dir_path):
        layer_id = int(layer_id_str)
        if layer_id not in _Cache:
            _Cache[layer_id] = {}
        records_per_layer[layer_id] = 0
        for hash_key in os.listdir(cache_dir_path):
            _Cache[layer_id][hash_key] = jsn.loads_text(local_fs.ReadTextFile(os.path.join(cache_dir_path, hash_key)))
            total_records += 1
            records_per_layer[layer_id] += 1
    if _Debug:
        lg.args(_DebugLevel, total_records=total_records, records_per_layer=records_per_layer)
    return total_records


def store_cached_key(hash_key, json_value, layer_id=0, timestamp=None):
    global _Cache
    if not timestamp:
        timestamp = utime.utcnow_to_sec1970()
    if layer_id not in _Cache:
        _Cache[layer_id] = {}
    cached_json_record = {
        'v': json_value,
        't': timestamp,
    }
    dht_dir_path = settings.ServiceDir('service_entangled_dht')
    layer_cache_dir_path = os.path.join(dht_dir_path, 'cache', strng.to_text(layer_id))
    if not os.path.isdir(layer_cache_dir_path):
        os.makedirs(layer_cache_dir_path)
    cached_record_file_path = os.path.join(layer_cache_dir_path, hash_key)
    if not local_fs.WriteTextFile(cached_record_file_path, jsn.dumps(cached_json_record)):
        lg.err('failed to store cached dht key %r in layer %d' % (hash_key, layer_id))
        return False
    _Cache[layer_id][hash_key] = cached_json_record
    if _Debug:
        lg.args(_DebugLevel, hash_key=hash_key, layer_id=layer_id, timestamp=timestamp, cached_records=len(_Cache[layer_id]))
    return True


def get_cached_value(hash_key, layer_id=0):
    global _Cache
    value = _Cache.get(layer_id, {}).get(hash_key)
    if _Debug:
        lg.args(_DebugLevel, layer_id=layer_id, hash_key=hash_key, value_exist=(value is not None))
    return value


def on_json_response_to_be_cached(json_value, key, layer_id):
    if not json_value:
        return json_value
    hash_key = key_to_hash(key)
    store_cached_key(hash_key, json_value, layer_id)
    return json_value


def get_cached_json_value(key, layer_id=0, cache_ttl=DEFAULT_CACHE_TTL):
    hash_key = key_to_hash(key)
    cached_record = get_cached_value(hash_key)
    if not cached_record:
        return get_json_value(key, layer_id=layer_id, update_cache=True)
    if utime.utcnow_to_sec1970() - int(cached_record['t']) > cache_ttl:
        return get_json_value(key, layer_id=layer_id, update_cache=True)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.get_cached_json_value key=[%r] layer_id=%d cache_ttl=%d' % (key, layer_id, cache_ttl))
    ret = Deferred()
    ret.callback(cached_record['v'])
    return ret


#------------------------------------------------------------------------------


class DHTNode(MultiLayerNode):
    def __init__(self, udpPort=4000, dataStores=None, routingTables=None, networkProtocol=None, nodeID=None):
        super(DHTNode, self).__init__(
            udpPort=udpPort,
            dataStores=dataStores,
            routingTables=routingTables,
            networkProtocol=networkProtocol,
            id=nodeID,
        )
        self._counter = count
        self.data = {
            0: {},
        }
        if dataStores:
            for layer_id in dataStores.keys():
                self.data[layer_id] = {}
        self.expire_task = LoopingCall(self.expire)
        self.rpc_callbacks = {}

    def add_rpc_callback(self, rpc_method_name, cb):
        self.rpc_callbacks[rpc_method_name] = cb

    def remove_rpc_callback(self, rpc_method_name):
        self.rpc_callbacks.pop(rpc_method_name, None)

    def reset_my_dht_id(self, new_id=None):
        self._routingTable = TreeRoutingTable(self.id)
        h = hashlib.sha1()
        h.update(b'nodeState')
        nodeStateKey = h.hexdigest()
        if nodeStateKey in self._dataStore:
            json_state = self._dataStore[nodeStateKey]
            state = json.loads(json_state)
            self.id = state['id']
            self._routingTable = TreeRoutingTable(self.id)
            for contactTriple in state['closestNodes']:
                contact = Contact(encoding.to_text(contactTriple[0]), contactTriple[1], contactTriple[2], self._protocol)
                self._routingTable.addContact(contact)
            if _Debug:
                print('[DHT NODE]    found "nodeState" key in local db and added %d contacts to routing table' % len(state['closestNodes']))
        else:
            self.id = self._generateID()
            self._routingTable = TreeRoutingTable(self.id)
        self._counter = None

    def expire(self):
        now = utime.utcnow_to_sec1970()
        for layer_id in self._dataStores.keys():
            expired_keys = []
            for key in self._dataStores[layer_id].keys():
                if key == self.nodeStateKey:
                    continue
                item_data = self._dataStores[layer_id].getItem(key)
                if item_data:
                    originaly_published = item_data.get('originallyPublished')
                    expireSeconds = item_data.get('expireSeconds')
                    if expireSeconds and originaly_published:
                        age = now - originaly_published
                        if age > expireSeconds:
                            expired_keys.append(key)
            for key in expired_keys:
                if _Debug:
                    lg.out(_DebugLevel, 'dht_service.expire   [%s] removed from layer %d' % (key, layer_id))
                del self._dataStores[layer_id][key]

    @rpcmethod
    def store(self, key, value, originalPublisherID=None, age=0, expireSeconds=KEY_EXPIRE_MAX_SECONDS, **kwargs):
        count('store_dht_service')
        layerID = kwargs.pop('layerID', 0)
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.DHTNode.store key=[%s] for %d seconds layerID=%d' % (key, expireSeconds, layerID))

        if 'store' in self.rpc_callbacks and layerID in self.active_layers:
            # TODO: add signature validation to be sure this is the owner of that key:value pair
            self.rpc_callbacks['store'](key=key, value=value, originalPublisherID=originalPublisherID, age=age, expireSeconds=expireSeconds, layerID=layerID, **kwargs)

        return super(DHTNode, self).store(key=key, value=value, originalPublisherID=originalPublisherID, age=age, expireSeconds=expireSeconds, layerID=layerID, **kwargs)

    @rpcmethod
    def request(self, key, **kwargs):
        count('request')
        layerID = kwargs.get('layerID', 0)
        if layerID not in self.active_layers:
            if _Debug:
                lg.out(_DebugLevel, 'dht_service.DHTNode.request key=[%r] SKIP because layer %d is not active' % (key, layerID))
            return {
                key: 0,
                layerID: layerID,
            }
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.DHTNode.request key=[%r] layerID=%d' % (key, layerID))
        if 'request' in self.rpc_callbacks:
            self.rpc_callbacks['request'](key=key, layerID=layerID)
        value = get_node_data(key, layer_id=layerID)
        if value is None:
            value = 0
        if _Debug:
            lg.out(_DebugLevel, '    read internal value: %r' % value)
        return {
            key: value,
            layerID: layerID,
        }

    @rpcmethod
    def verify_update(self, key, value, originalPublisherID=None, age=0, expireSeconds=KEY_EXPIRE_MAX_SECONDS, **kwargs):
        count('verify_update')
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.DHTNode.verify_update key=[%s]' % strng.to_text(key, errors='ignore')[:10])
        return True

    @rpcmethod
    def findNode(self, key, **kwargs):
        count('findNode')
        layerID = kwargs.get('layerID', 0)
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.DHTNode.findNode key=[%s] layerID=%d' % (key, layerID))
        return super(DHTNode, self).findNode(key, **kwargs)

    @rpcmethod
    def findValue(self, key, **kwargs):
        count('findValue')
        layerID = kwargs.get('layerID', 0)
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.DHTNode.findValue key=[%s] layerID=%d' % (key, layerID))
        return super(DHTNode, self).findValue(key, **kwargs)

    @rpcmethod
    def ping(self):
        count('ping')
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.DHTNode.ping')
        return super(DHTNode, self).ping()

    def reconnect(self, knownNodeAddresses=None):
        """
        TODO: need to restart _scheduleNextNodeRefresh.
        """
        d = Deferred()
        if not self.listener:
            d.errback(Exception('Listener is not started yet'))
            return d
        d.callback(1)
        return d


#------------------------------------------------------------------------------


class DHTProtocol(KademliaMultiLayerProtocol):
    def __init__(self, node, msgEncoder=encoding.Bencode(), msgTranslator=msgformat.MultiLayerFormat()):
        KademliaMultiLayerProtocol.__init__(self, node, msgEncoder=msgEncoder, msgTranslator=msgTranslator)
        self._counter = count


#         self.receiving_queue = []
#         self.receiving_worker = None
#         self.sending_queue = []
#         self.sending_worker = None

#     def datagramReceived(self, datagram, address):
#         count('dht_datagramReceived')
#         if len(self.receiving_queue) > RECEIVING_QUEUE_LENGTH_CRITICAL:
#             lg.warn('incoming DHT traffic too high, items to process: %d' % len(self.receiving_queue))
#         self.receiving_queue.append((datagram, address, ))
#         if self.receiving_worker is None:
#             self._process_incoming()  # self.receiving_worker = reactor.callLater(0, self._process_incoming)

#     def _process_incoming(self):
#         if len(self.receiving_queue) == 0:
#             self.receiving_worker = None
#             return
#         datagram, address = self.receiving_queue.pop(0)
#         KademliaMultiLayerProtocol.datagramReceived(self, datagram, address)
#         t = 0
#         if len(self.receiving_queue) > RECEIVING_QUEUE_LENGTH_CRITICAL / 2:
#             t = RECEIVING_FREQUENCY_SEC
#         self.receiving_worker = reactor.callLater(t, self._process_incoming)  #@UndefinedVariable

#     def _send(self, data, rpcID, address):
#         count('dht_send')
#         if _Debug:
#             if len(self.sending_queue) > 50:
#                 lg.warn('outgoing DHT traffic too high, items to send: %d' % len(self.sending_queue))
#         self.sending_queue.append((data, rpcID, address, ))
#         if self.receiving_worker is None:
#             self._process_outgoing() # self.receiving_worker = reactor.callLater(0, self._process_outgoing)

#     def _process_outgoing(self):
#         if len(self.sending_queue) == 0:
#             self.sending_worker = None
#             return
#         data, rpcID, address = self.sending_queue.pop(0)
#         KademliaMultiLayerProtocol._send(self, data, rpcID, address)
#         t = 0
#         if len(self.sending_queue) > SENDING_QUEUE_LENGTH_CRITICAL:
#             t = SENDING_FREQUENCY_SEC
#         self.sending_worker = reactor.callLater(t, self._process_outgoing)  #@UndefinedVariable

#------------------------------------------------------------------------------


def parseCommandLine():
    oparser = optparse.OptionParser()
    oparser.add_option('-p', '--udpport', dest='udpport', type='int', help='specify UDP port for DHT network')
    oparser.set_default('udpport', settings.DefaultDHTPort())
    oparser.add_option('-d', '--dhtdb', dest='dhtdb', help='specify DHT folder location')
    oparser.set_default('dhtdb', settings.ServiceDir('service_entangled_dht'))
    oparser.add_option('-s', '--seeds', dest='seeds', help='specify list of DHT seed nodes')
    oparser.set_default('seeds', '')
    oparser.add_option('-l', '--layers', dest='layers', help='specify list of layers to be created')
    oparser.set_default('layers', '')
    oparser.add_option('-a', '--attach_layer', dest='attach_layer', help='specify which layer to be attached at start')
    oparser.set_default('attach_layer', '')
    oparser.add_option('-j', '--join_layer', dest='join_layer', help='specify which layer to be joined at start')
    oparser.set_default('join_layer', '')
    oparser.add_option('-w', '--wait', dest='delayed', type='int', help='wait N seconds before join the network')
    oparser.set_default('delayed', 0)
    (options, args) = oparser.parse_args()
    return options, args


def main(options=None, args=None):
    from bitdust.dht import dht_relations

    if options is None and args is None:
        (options, args) = parseCommandLine()

    else:
        (_options, _args) = parseCommandLine()
        if options is None:
            options = _options
        if args is None:
            args = _args

    if not os.path.exists(options.dhtdb):
        os.makedirs(options.dhtdb)

    connect_layers = [int(l) for l in options.layers.split(',') if l]
    init(udp_port=options.udpport, dht_dir_path=options.dhtdb, open_layers=connect_layers)
    lg.out(_DebugLevel, 'Init   udpport=%d   dhtdb=%s   node=%r   connect_layers=%r' % (options.udpport, options.dhtdb, node(), connect_layers))

    seeds = []

    def _go():
        lg.out(_DebugLevel, 'DHT node is active, layers: %r' % node().layers)

        try:
            if len(args) == 0:
                pass

            elif len(args) > 0:

                cmd = args[0]

                lg.info('COMMAND: %r' % cmd)

                def _r(x):
                    lg.info('RESULT "%s": %r' % (cmd, x))
                    reactor.stop()  #@UndefinedVariable

                if cmd == 'get':
                    get_value(args[1], layer_id=0 if len(args) < 3 else int(args[2])).addBoth(_r)
                elif cmd == 'set':
                    set_value(args[1], args[2], expire=int(args[3]), layer_id=0 if len(args) < 5 else int(args[4])).addBoth(_r)
                elif cmd == 'get_json':
                    get_json_value(args[1], layer_id=0 if len(args) < 3 else int(args[2])).addBoth(_r)
                elif cmd == 'set_json':
                    set_json_value(args[1], jsn.loads(args[2]), expire=int(args[3]), layer_id=0 if len(args) < 3 else int(args[2])).addBoth(_r)
                elif cmd == 'get_valid_data':
                    get_valid_data(args[1], rules=jsn.loads(args[2]), return_details=True, layer_id=0 if len(args) < 4 else int(args[3])).addBoth(_r)
                elif cmd == 'set_valid_data':
                    set_valid_data(args[1], jsn.loads(args[2]), expire=int(args[3]), rules=jsn.loads(args[4]), layer_id=0 if len(args) < 6 else int(args[5])).addBoth(_r)
                elif cmd == 'read_customer_suppliers':
                    dht_relations.read_customer_suppliers(args[1]).addBoth(_r)
                elif cmd == 'write_customer_suppliers':
                    dht_relations.write_customer_suppliers(args[1], args[2].split(',')).addBoth(_r)
                elif cmd == 'write_verify_republish':
                    write_verify_republish_data(args[1], args[2], expire=int(args[3])).addBoth(_r)
                elif cmd == 'find':
                    find_node(key_to_hash(args[1])).addBoth(_r)
                elif cmd == 'ping':
                    find_node(random_key()).addBoth(_r)
                elif cmd == 'get_node_data':
                    pprint.pprint(get_node_data(args[1]))
                elif cmd == 'observe_data':

                    def _p(val, n):
                        print('observed', n, val)

                    def _o(result):
                        for n in result:
                            d = n.request(args[2])
                            d.addCallback(_p, n)

                    d = find_node(key_to_hash(args[1]))
                    d.addErrback(_r)
                    d.addCallback(_o)
                elif cmd == 'discover':

                    def _l(x):
                        lg.info(x)
                        find_node(random_key()).addBoth(_l)

                    _l('')
                elif cmd == 'dump_db':
                    pprint.pprint(dump_local_db(value_as_json=True))
                elif cmd == 'create_layer':
                    open_layer(
                        layer_id=int(args[1]),
                        seed_nodes=[(s[0], int(s[1])) for s in args[2].split(',') if s],
                        dht_dir_path=options.dhtdb,
                        connect_now=True,
                    ).addBoth(_r)
        except:
            lg.exc()

    possible_seeds = options.seeds
    if possible_seeds in [
        'genesis',
        'root',
        b'genesis',
        b'root',
    ]:
        # "genesis" node must not connect anywhere
        possible_seeds = []

    lg.out(_DebugLevel, 'options.seeds=%r' % options.seeds)
    lg.out(_DebugLevel, 'possible_seeds=%r' % possible_seeds)

    if options.seeds in [
        'genesis',
        'root',
        b'genesis',
        b'root',
    ]:
        lg.out(_DebugLevel, 'Starting genesis node!!!!!!!!!!!!!!!!!!!!')

    else:
        for dht_node_str in options.seeds.split(','):
            if dht_node_str.strip():
                try:
                    dht_node = dht_node_str.strip().split(':')
                    dht_node_host = dht_node[0].strip()
                    dht_node_port = int(dht_node[1].strip())
                except:
                    continue
                seeds.append((
                    dht_node_host,
                    dht_node_port,
                ))

        if not seeds:
            seeds = known_nodes.nodes()

        lg.out(_DebugLevel, 'Seed nodes: %s' % seeds)

    if options.delayed:
        lg.out(_DebugLevel, 'Wait %d seconds before join the network' % options.delayed)
        import time
        time.sleep(options.delayed)

    def _layers_connected(allresults):
        lg.out(_DebugLevel, 'Layers are connected: %r' % allresults)
        _go()

    def _connected(nodes):
        lg.out(_DebugLevel, 'Connected, known contacts: %r' % nodes)
        l = []
        if options.attach_layer:
            layer_id = int(options.attach_layer)
            l.append(connect(seeds, layer_id=layer_id, attach=True))
        if options.join_layer:
            layer_id = int(options.join_layer)
            l.append(connect(seeds, layer_id=layer_id, attach=False))
        d = DeferredList(l)
        d.addBoth(_layers_connected)

    def _start():
        connect(seeds).addBoth(_connected)

    reactor.callWhenRunning(_start)  # @UndefinedVariable
    reactor.run()  #@UndefinedVariable


#------------------------------------------------------------------------------

if __name__ == '__main__':
    from bitdust.dht import dht_service
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
    dht_service.main()
    settings.shutdown()
