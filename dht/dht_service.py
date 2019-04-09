#!/usr/bin/python
# dht_service.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
import six

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import sys
import hashlib
import random
import optparse
import pprint

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.task import LoopingCall  #@UnresolvedImport
from twisted.internet.defer import Deferred, fail  # @UnresolvedImport

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from dht.entangled.kademlia.datastore import SQLiteVersionedJsonDataStore  # @UnresolvedImport
from dht.entangled.kademlia.node import rpcmethod  # @UnresolvedImport
from dht.entangled.kademlia.protocol import KademliaProtocol, encoding, msgformat  # @UnresolvedImport
from dht.entangled.kademlia import constants  # @UnresolvedImport
from dht.entangled.node import EntangledNode  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

from lib import strng
from lib import utime
from lib import jsn

#------------------------------------------------------------------------------

KEY_EXPIRE_MIN_SECONDS = 60 * 2
KEY_EXPIRE_MAX_SECONDS = constants.dataExpireSecondsDefaut
RECEIVING_FREQUENCY_SEC = 0.01
SENDING_FREQUENCY_SEC = 0.02  # must be always slower than receiving frequency!
RECEIVING_QUEUE_LENGTH_CRITICAL = 100
SENDING_QUEUE_LENGTH_CRITICAL = 50

#------------------------------------------------------------------------------

_MyNode = None
_ActiveLookup = None
_Counters = {}
_ProtocolVersion = 7

#------------------------------------------------------------------------------


def init(udp_port, db_file_path=None):
    global _MyNode
    if _MyNode is not None:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.init SKIP, DHTNode already exist')
        return
    if db_file_path is None:
        db_file_path = settings.DHTDBFile()
    dbPath = bpio.portablePath(db_file_path)
    try:
        dataStore = SQLiteVersionedJsonDataStore(dbFile=dbPath)
    except:
        lg.warn('failed reading DHT records, removing %s and starting clean DB' % dbPath)
        lg.exc()
        os.remove(dbPath)
        dataStore = SQLiteVersionedJsonDataStore(dbFile=dbPath)
    networkProtocol = KademliaProtocolConveyor
    _MyNode = DHTNode(udp_port, dataStore, networkProtocol=networkProtocol)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.init UDP port is %d, DB file path: %s' % (udp_port, dbPath))


def shutdown():
    global _MyNode
    if _MyNode is not None:
        _MyNode._dataStore._db.close()
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


def connect(seed_nodes=[]):
    result = Deferred()

    if node().refresher and node().refresher.active():
        node().refresher.reset(0)
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect DHT already active : SKIP but RESET refresher task')
        if node()._joinDeferred and node()._joinDeferred.called:
            result.callback(True)
        else:
            node()._joinDeferred.addBoth(lambda x: result.callback(True))
        return result

    if not node().listener:
        node().listenUDP()
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect opened a new listener : %r' % node().listener)

    if _Debug:
        lg.out(_DebugLevel, 'dht_service.connect STARTING with %d known nodes:' % (len(seed_nodes)))
        for onenode in seed_nodes:
            lg.out(_DebugLevel, '    %s:%s' % onenode)

    def _on_join_success(live_contacts, resolved_seed_nodes):
        if _Debug:
            if isinstance(live_contacts, dict):
                lg.warn('Unexpected result from joinNetwork: %s' % pprint.pformat(live_contacts))
            else: 
                if live_contacts and len(live_contacts) > 0 and live_contacts[0]:
                    lg.out(_DebugLevel, 'dht_service.connect DHT JOIN SUCCESS !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                else:
                    lg.out(_DebugLevel, 'dht_service.connect DHT JOINED, but still OFFLINE !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                    lg.warn('No live DHT contacts found...  your node is NOT CONNECTED TO DHT NETWORK')
            lg.out(_DebugLevel, 'alive DHT nodes: %s' % pprint.pformat(live_contacts))
            lg.out(_DebugLevel, 'resolved SEED nodes: %r' % resolved_seed_nodes)
            lg.out(_DebugLevel, 'DHT node is active, ID=[%s]' % node().id)
        result.callback(resolved_seed_nodes)
        return live_contacts

    def _on_join_failed(x):
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect DHT JOIN FAILED : %s' % x)
        result.callback(False)
        return None

    def _on_hosts_resolved(resolved_seed_nodes):
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect RESOLVED %d live nodes' % (len(resolved_seed_nodes)))
            for onenode in resolved_seed_nodes:
                lg.out(_DebugLevel, '    %s:%s' % onenode)
        if not resolved_seed_nodes:
            resolved_seed_nodes = None 
        d = node().joinNetwork(resolved_seed_nodes)
        d.addCallback(_on_join_success, resolved_seed_nodes)
        d.addErrback(_on_join_failed)
        node().expire_task.start(int(KEY_EXPIRE_MIN_SECONDS / 2), now=True)
        return resolved_seed_nodes

    def _on_hosts_resolve_failed(x):
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.connect ERROR : hosts not resolved: %s' % x)
        result.callback(False)
        return x

    d = resolve_hosts(seed_nodes)
    d.addCallback(_on_hosts_resolved)
    d.addErrback(_on_hosts_resolve_failed)
    return result


def disconnect():
    global _MyNode
    if not node():
        return False
    if node().expire_task and node().expire_task.running:
        node().expire_task.stop()
    if node().refresher and node().refresher.active():
        node().refresher.cancel()
    if node().listener:
        node().listener.stopListening()
    return True


def reconnect():
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.reconnect')
    return node().reconnect()

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
        result_list.append((ip, port, ))
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
    return key_to_hash(str(random.getrandbits(255)).encode())


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
        lg.out(_DebugLevel, 'dht_service.on_success   %s(%r)    result is %s' % (method, key, type(result), ))
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

def get_value(key):
    if not node():
        return fail(Exception('DHT service is off'))
    count('get_value_%s' % key)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.get_value key=[%r]' % key)
    d = node().iterativeFindValue(key_to_hash(key), rpc='findValue')
    d.addCallback(on_success, 'get_value', key)
    d.addErrback(on_error, 'get_value', key)
    return d


def set_value(key, value, age=0, expire=KEY_EXPIRE_MAX_SECONDS, collect_results=True):
    if not node():
        return fail(Exception('DHT service is off'))
    count('set_value_%s' % key)
    sz_bytes = len(value)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.set_value key=[%s] with %d bytes for %d seconds' % (key, sz_bytes, expire, ))
    if expire < KEY_EXPIRE_MIN_SECONDS:
        expire = KEY_EXPIRE_MIN_SECONDS
    if expire > KEY_EXPIRE_MAX_SECONDS:
        expire = KEY_EXPIRE_MAX_SECONDS
    d = node().iterativeStore(key_to_hash(key), value, age=age, expireSeconds=expire, collect_results=collect_results)
    d.addCallback(on_success, 'set_value', key, value)
    d.addErrback(on_error, 'set_value', key)
    return d


def delete_key(key):
    if not node():
        return fail(Exception('DHT service is off'))
    count('delete_key_%s' % key)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.delete_key [%s]' % key)
    d = node().iterativeDelete(key_to_hash(key))
    d.addCallback(on_success, 'delete_value', key)
    d.addErrback(on_error, 'delete_key', key)
    return d

#------------------------------------------------------------------------------

def read_json_response(response, key, result_defer=None, as_bytes=False):
    if _Debug:
        lg.out(_DebugLevel + 6, 'dht_service.read_json_response [%r] : %r' % (key, response))
    value = None
    if isinstance(response, list):
        if _Debug:
            lg.out(_DebugLevel, '        response is a list, value not found')
        if result_defer:
            result_defer.callback(response)
        return None
    if isinstance(response, dict):
        if response.get('values'):
            try:
                latest = 0
                if as_bytes:
                    value = jsn.loads(response['values'][0][0])
                else:
                    value = jsn.loads_text(response['values'][0][0])
                for v in response['values']:
                    if v[1] > latest:
                        latest = v[1]
                        value = jsn.loads(v[0])
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
        result_defer.callback(value)
    return value


def get_json_value(key, as_bytes=False):
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.get_json_value key=[%r]' % key)
    ret = Deferred()
    d = get_value(key)
    d.addCallback(read_json_response, key, ret, as_bytes)
    d.addErrback(ret.errback)
    return ret


def set_json_value(key, json_data, age=0, expire=KEY_EXPIRE_MAX_SECONDS, collect_results=True):
    if not node():
        return fail(Exception('DHT service is off'))
    try:
        value = jsn.dumps(json_data, indent=0, sort_keys=True, separators=(',', ':'))
    except:
        return fail(Exception('bad input json data'))
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.set_json_value key=[%s] with %d bytes' % (key, len(str(value))))
    return set_value(key=key, value=value, age=age, expire=expire, collect_results=collect_results)

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
            lg.out(_DebugLevel, 'dht_service.validate_data_received    key=[%s] not found : %s' % (key, type(value)))
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

    if populate_meta_fields:
        # Otherwise those records will not pass validation
        if value.get('type') != expected_record_type:
            value['type'] = expected_record_type
        if value.get('key') != key:
            value['key'] = key

    passed = True
    errors = []
    for field, field_rules in rules.items():
        for rule in field_rules:
            if 'op' not in rule:
                lg.warn('incorrect validation rule found: %r' % rule)
                continue
            if rule['op'] == 'equal' and rule.get('arg') != strng.to_text(value.get(field)):
                passed = False
                errors.append((field, rule, ))
                break
            if rule['op'] == 'exist' and field not in value:
                passed = False
                errors.append((field, rule, ))
                break
        if not passed:
            break
    if not passed:
        lg.err('DHT record validation failed, errors: %s' % errors)
        if result_defer:
            result_defer.errback(Exception('DHT record validation failed'))
        return None
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.validate_data_received   key=[%s] : value is OK' % key)
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
        lg.out(_DebugLevel + 8, 'dht_service.validate_before_store key=[%s] json=%r' % (key, json_new_value, ))
    new_record_type = json_new_value.get('type')
    if not new_record_type:
        if _Debug:
            lg.out(_DebugLevel, '        new json data do not have "type" field present, store operation FAILED')
        raise ValueError('input data do not have "type" field present: %r' % json_new_value)
    if key not in node()._dataStore:
        if _Debug:
            lg.out(_DebugLevel, '        previous value not exists yet, store OK')
        return True
    prev_value = node()._dataStore[key]
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
                prev_suppliers = [strng.to_bin(idurl.strip()) for idurl in json_prev_value.get('suppliers', [])]
                new_suppliers = [strng.to_bin(idurl.strip()) for idurl in json_new_value.get('suppliers', [])]
                if prev_suppliers != new_suppliers:
                    if _Debug:
                        lg.out(_DebugLevel, '        new json data have same revision but different suppliers list, store operation FAILED')
                    raise ValueError('new json data have same revision but different suppliers list, current revision is %d ' % prev_revision)
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
        lg.out(_DebugLevel, 'dht_service.validate_data_written key=[%s]  %s  collected=%s  nodes=%r' % (
            key, type(store_results), results_collected, nodes, ))
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
        lg.out(_DebugLevel, 'dht_service.validate_data_before_send for key [%s]' % key)
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
        lg.out(_DebugLevel, 'dht_service.validate_data_after_receive for key [%s]' % key)
    response = validate_rules(value, key, rules, result_defer=result_defer,
                            raise_for_result=raise_for_result,
                            populate_meta_fields=populate_meta_fields)
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


def get_valid_data(key, rules={}, raise_for_result=False, return_details=False):
    ret = Deferred()
    d = get_json_value(key)
    d.addCallback(validate_after_receive, key=key, rules=rules, result_defer=ret,
                  raise_for_result=raise_for_result, populate_meta_fields=return_details)
    d.addErrback(ret.errback)
    return ret


def set_valid_data(key, json_data, age=0, expire=KEY_EXPIRE_MAX_SECONDS, rules={}, collect_results=False):
    valid_json_data = validate_before_send(value=json_data, key=key, rules=rules, populate_meta_fields=True)
    if valid_json_data is None or not isinstance(valid_json_data, dict):
        return fail(Exception('invalid data going to be written, validation failed'))
    ret = Deferred()
    d = set_json_value(key, json_data=json_data, age=age, expire=expire, collect_results=collect_results)
    d.addCallback(validate_data_written, key, json_data, ret)
    d.addErrback(ret.errback)
    return ret


def write_verify_republish_data(key, json_data, age=0, expire=KEY_EXPIRE_MAX_SECONDS, rules={}):
    """
    """
    try:
        raw_value = jsn.dumps(json_data, indent=0, sort_keys=True, separators=(',', ':'))
    except:
        return fail(Exception('bad input json data'))

    ret = Deferred()
    _found_nodes = None
    _write_response = None
    _join = Deferred()
    _join.addCallback(_do_verify)
    _join.addErrback(lg.errback)

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
            lg.out(_DebugLevel, 'dht_service._do_verify  %r via nodes: %r' % (write_response, found_nodes, ))
        for node in found_nodes:
            node.request(b'verify_update', key, raw_value, age, expire)
        ret.callback(write_response, found_nodes)
        return None

    new_key = random_key()
    d_observer = find_node(new_key)
    d_observer.addCallback(_some_nodes_found)
    d_observer.addErrback(_nodes_not_found)

    d_write = set_valid_data(key=key, json_data=json_data, age=age, expire=expire, rules=rules)
    d_write.addCallback(_write_ok)
    d_write.addErrback(_write_failed)

    return ret

#------------------------------------------------------------------------------

def on_nodes_found(result, node_id64):
    on_success(result, 'find_node', node_id64)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.on_nodes_found   node_id=[%s], %d nodes found' % (node_id64, len(result)))
    return result


def on_lookup_failed(result, node_id64):
    on_error(result, 'find_node', node_id64)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.on_lookup_failed   node_id=[%s], result=%s' % (node_id64, result))
    return result


def find_node(node_id):
    global _ActiveLookup
    if _ActiveLookup and not _ActiveLookup.called:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.find_node SKIP, already started')
        return _ActiveLookup
    count('find_node')
    node_id64 = node_id
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.find_node   node_id=[%s]  counter=%d' % (node_id64, counter('find_node')))
    if not node():
        return fail(Exception('DHT service is off'))
    _ActiveLookup = node().iterativeFindNode(node_id)
    _ActiveLookup.addCallback(on_nodes_found, node_id64)
    _ActiveLookup.addErrback(on_lookup_failed, node_id64)
    return _ActiveLookup

#------------------------------------------------------------------------------

def get_node_data(key):
    if not node():
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.get_node_data local node is not ready')
        return None
    count('get_node_data')
    key = strng.to_text(key)
    if key not in node().data:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.get_node_data key=[%s] not exist' % key)
        return None
    value = node().data[key]
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.get_node_data key=[%s] read %d bytes, counter=%d' % (
            key, len(str(value)), counter('get_node_data')))
    return value


def set_node_data(key, value):
    if not node():
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.set_node_data local node is not ready')
        return False
    count('set_node_data')
    key = strng.to_text(key)
    node().data[key] = value
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.set_node_data key=[%s] wrote %d bytes, counter=%d' % (
            key, len(str(value)), counter('set_node_data')))
    return True


def delete_node_data(key):
    if not node():
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.delete_node_data local node is not ready')
        return False
    count('delete_node_data')
    key = strng.to_text(key)
    if key not in node().data:
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.delete_node_data key=[%s] not exist' % key)
        return False
    node().data.pop(key)
    if _Debug:
        lg.out(_DebugLevel, 'dht_service.delete_node_data key=[%s], counter=%d' % (key, counter('delete_node_data')))
    return True


def dump_local_db(value_as_json=False):
    if not node():
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.dump_local_db local node is not ready')
        return None
    l = []
    for itm in node()._dataStore.getAllItems():
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
    for k, v in node().data.items():
        l.append({'key': k, 'value': v, 'scope': 'node', })
    return l

#------------------------------------------------------------------------------


class DHTNode(EntangledNode):

    def __init__(self, udpPort=4000, dataStore=None, routingTable=None, networkProtocol=None):
        super(DHTNode, self).__init__(udpPort=udpPort, dataStore=dataStore, routingTable=routingTable, networkProtocol=networkProtocol, id=None, )
        self._counter = count
        self.data = {}
        self.expire_task = LoopingCall(self.expire)
        self.rpc_callbacks = {}

    def add_rpc_callback(self, rpc_method_name, cb):
        self.rpc_callbacks[rpc_method_name] = cb

    def remove_rpc_callback(self, rpc_method_name):
        self.rpc_callbacks.pop(rpc_method_name, None)

    def expire(self):
        now = utime.get_sec1970()
        expired_keys = []
        h = hashlib.sha1()
        h.update(b'nodeState')
        nodeStateKey = h.hexdigest()
        for key in self._dataStore.keys():
            if key == nodeStateKey:
                continue
            item_data = self._dataStore.getItem(key)
            if item_data:
                originaly_published = item_data.get('originallyPublished')
                expireSeconds = item_data.get('expireSeconds')
                if expireSeconds and originaly_published:
                    age = now - originaly_published
                    if age > expireSeconds:
                        expired_keys.append(key)
        for key in expired_keys:
            if _Debug:
                lg.out(_DebugLevel, 'dht_service.expire   [%s] removed' % key)
            del self._dataStore[key]

    @rpcmethod
    def store(self, key, value, originalPublisherID=None,
              age=0, expireSeconds=KEY_EXPIRE_MAX_SECONDS, **kwargs):
        count('store_dht_service')
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.DHTNode.store key=[%s] for %d seconds, counter=%d' % (
                key, expireSeconds, counter('store')))

        if 'store' in self.rpc_callbacks:
            # TODO: add signature validation to be sure this is the owner of that key:value pair
            self.rpc_callbacks['store'](
                key=key,
                value=value,
                originalPublisherID=originalPublisherID,
                age=age,
                expireSeconds=expireSeconds,
                **kwargs
            )

        return super(DHTNode, self).store(
            key=key,
            value=value,
            originalPublisherID=originalPublisherID,
            age=age,
            expireSeconds=expireSeconds,
            **kwargs
        )

    @rpcmethod
    def request(self, key):
        count('request')
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.DHTNode.request key=[%r]' % key)
        if 'request' in self.rpc_callbacks:
            self.rpc_callbacks['request'](
                key=key,
            )
        value = get_node_data(key)
        if value is None:
            value = 0
        if _Debug:
            lg.out(_DebugLevel, '    read internal value: %r' % value)
        return {key: value, }

    @rpcmethod
    def verify_update(self, key, value, originalPublisherID=None,
                            age=0, expireSeconds=KEY_EXPIRE_MAX_SECONDS, **kwargs):
        count('request')
        if _Debug:
            lg.out(_DebugLevel, 'dht_service.DHTNode.verify_update key=[%s]' % strng.to_text(key, errors='ignore')[:10])

    def reconnect(self, knownNodeAddresses=None):
        """
        TODO: need to restart _scheduleNextNodeRefresh.
        """
        d = Deferred()
        if not self.listener:
            d.errback(Exception('Listener is not started yet'))
            return d
        if self.refresher and self.refresher.active():
            self.refresher.reset(0)
        d.callback(1)
        return d

#------------------------------------------------------------------------------


class KademliaProtocolConveyor(KademliaProtocol):

    def __init__(self, node, msgEncoder=encoding.Bencode(), msgTranslator=msgformat.DefaultFormat()):
        KademliaProtocol.__init__(self, node, msgEncoder, msgTranslator)
        self.receiving_queue = []
        self.receiving_worker = None
        self.sending_queue = []
        self.sending_worker = None
        self._counter = count

#     def datagramReceived(self, datagram, address):
#         count('dht_datagramReceived')
#         if len(self.receiving_queue) > RECEIVING_QUEUE_LENGTH_CRITICAL:
#             lg.warn('incoming DHT traffic too high, items to process: %d' % len(self.receiving_queue))
#         self.receiving_queue.append((datagram, address, ))
#         if self.receiving_worker is None:
#             self._process_incoming()  # self.receiving_worker = reactor.callLater(0, self._process_incoming)

    def _process_incoming(self):
        if len(self.receiving_queue) == 0:
            self.receiving_worker = None
            return
        datagram, address = self.receiving_queue.pop(0)
        KademliaProtocol.datagramReceived(self, datagram, address)
        t = 0
        if len(self.receiving_queue) > RECEIVING_QUEUE_LENGTH_CRITICAL / 2:
            t = RECEIVING_FREQUENCY_SEC
        self.receiving_worker = reactor.callLater(t, self._process_incoming)  #@UndefinedVariable

#     def _send(self, data, rpcID, address):
#         count('dht_send')
#         if _Debug:
#             if len(self.sending_queue) > 50:
#                 lg.warn('outgoing DHT traffic too high, items to send: %d' % len(self.sending_queue))
#         self.sending_queue.append((data, rpcID, address, ))
#         if self.receiving_worker is None:
#             self._process_outgoing() # self.receiving_worker = reactor.callLater(0, self._process_outgoing)

    def _process_outgoing(self):
        if len(self.sending_queue) == 0:
            self.sending_worker = None
            return
        data, rpcID, address = self.sending_queue.pop(0)
        KademliaProtocol._send(self, data, rpcID, address)
        t = 0
        if len(self.sending_queue) > SENDING_QUEUE_LENGTH_CRITICAL:
            t = SENDING_FREQUENCY_SEC
        self.sending_worker = reactor.callLater(t, self._process_outgoing)  #@UndefinedVariable

#------------------------------------------------------------------------------


def parseCommandLine():
    oparser = optparse.OptionParser()
    oparser.add_option("-p", "--udpport", dest="udpport", type="int", help="specify UDP port for DHT network")
    oparser.set_default('udpport', settings.DefaultDHTPort())
    oparser.add_option("-d", "--dhtdb", dest="dhtdb", help="specify DHT database file location")
    oparser.set_default('dhtdb', settings.DHTDBFile())
    oparser.add_option("-s", "--seeds", dest="seeds", help="specify list of DHT seed nodes")
    oparser.set_default('seeds', '')
    oparser.add_option("-w", "--wait", dest="delayed", type="int", help="wait N seconds before join the network")
    oparser.set_default('delayed', 0)
    
    (options, args) = oparser.parse_args()
    return options, args


def main(options=None, args=None):
    from dht import dht_relations

    if options is None and args is None:
        (options, args) = parseCommandLine()

    else:
        (_options, _args) = parseCommandLine()
        if options is None:
            options = _options
        if args is None:
            args = _args

    init(udp_port=options.udpport, db_file_path=options.dhtdb)
    lg.out(_DebugLevel, 'Init   udpport=%d   dhtdb=%s   node=%r' % (options.udpport, options.dhtdb, node()))

    def _go(nodes):
#         lg.out(_DebugLevel, 'Connected nodes: %r' % nodes)
#         lg.out(_DebugLevel, 'DHT node is active, ID=[%s]' % base64.b64encode(node().id))
        try:
            if len(args) == 0:
                pass

            elif len(args) > 0:

                def _r(x):
                    lg.info(x)
                    # reactor.stop()  #@UndefinedVariable

                cmd = args[0]
                if cmd == 'get':
                    get_value(args[1]).addBoth(_r)
                elif cmd == 'set':
                    set_value(args[1], args[2], expire=int(args[3])).addBoth(_r)
                elif cmd == 'get_json':
                    get_json_value(args[1]).addBoth(_r)
                elif cmd == 'set_json':
                    set_json_value(args[1], jsn.loads(args[2]),
                                   expire=(int(args[3]) if len(args)>=4 else 9999)).addBoth(_r)
                elif cmd == 'get_valid_data':
                    get_valid_data(args[1], rules=jsn.loads(args[2]), return_details=True).addBoth(_r)
                elif cmd == 'set_valid_data':
                    set_valid_data(args[1], jsn.loads(args[2]),
                                   expire=(int(args[3]) if len(args)>=4 else 9999),
                                   rules=jsn.loads(args[4])).addBoth(_r)
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
        except:
            lg.exc()

    seeds = []

    if options.seeds in ['genesis', 'root', b'genesis', b'root', ]:
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
                seeds.append((dht_node_host, dht_node_port, ))
        
        if not seeds:
            from dht import known_nodes
            seeds = known_nodes.nodes()

        lg.out(_DebugLevel, 'Seed nodes: %s' % seeds)

    if options.delayed:
        lg.out(_DebugLevel, 'Wait %d seconds before join the network' % options.delayed)
        import time
        time.sleep(options.delayed)
    
    connect(seeds).addBoth(_go)
    reactor.run()  #@UndefinedVariable

#------------------------------------------------------------------------------


if __name__ == '__main__':
    from dht import dht_service
    bpio.init()
    settings.init()
    lg.set_debug_level(settings.getDebugLevel())
    dht_service._Debug = True
    dht_service.main()
