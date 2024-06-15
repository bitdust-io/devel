#!/usr/bin/python
# dht_records.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (dht_records.py) is part of BitDust Software.
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
..

module:: dht_records
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import utime
from bitdust.lib import strng

from bitdust.dht import dht_service

#------------------------------------------------------------------------------

LAYER_ID_SERVERS = 1
LAYER_PROXY_ROUTERS = 2
LAYER_SUPPLIERS = 3
LAYER_REBUILDERS = 4
LAYER_BROADCASTERS = 5
LAYER_MERCHANTS = 6
LAYER_MESSAGE_BROKERS = 7
LAYER_CUSTOMERS = 8

LAYERS_REGISTRY = {
    LAYER_ID_SERVERS: 'ID_SERVERS',
    LAYER_PROXY_ROUTERS: 'PROXY_ROUTERS',
    LAYER_SUPPLIERS: 'SUPPLIERS',
    LAYER_REBUILDERS: 'REBUILDERS',
    LAYER_BROADCASTERS: 'BROADCASTERS',
    LAYER_MERCHANTS: 'MERCHANTS',
    LAYER_MESSAGE_BROKERS: 'MESSAGE_BROKERS',
    LAYER_CUSTOMERS: 'CUSTOMERS',
}

#------------------------------------------------------------------------------

RELATION_RECORD_CACHE_TTL = {
    'nickname': 60*60*24,
    'identity': 60*60,
    'suppliers': 60*60*12,
    'message_broker': 60*60*12,
    'bismuth_identity_request': 60*60,
}

_Rules = {
    'nickname': {
        'key': [
            {
                'op': 'exist',
            },
        ],
        'type': [
            {
                'op': 'equal',
                'arg': 'nickname',
            },
        ],
        'timestamp': [
            {
                'op': 'exist',
            },
        ],
        'idurl': [
            {
                'op': 'exist',
            },
        ],
        'nickname': [
            {
                'op': 'exist',
            },
        ],
        'position': [
            {
                'op': 'exist',
            },
        ],
    },
    'identity': {
        'key': [
            {
                'op': 'exist',
            },
        ],
        'type': [
            {
                'op': 'equal',
                'arg': 'identity',
            },
        ],
        'timestamp': [
            {
                'op': 'exist',
            },
        ],
        'idurl': [
            {
                'op': 'exist',
            },
        ],
        'identity': [
            {
                'op': 'exist',
            },
        ],
    },
    'suppliers': {
        'key': [
            {
                'op': 'exist',
            },
        ],
        'type': [
            {
                'op': 'equal',
                'arg': 'suppliers',
            },
        ],
        'timestamp': [
            {
                'op': 'exist',
            },
        ],
        'customer_idurl': [
            {
                'op': 'exist',
            },
        ],
        'ecc_map': [
            {
                'op': 'exist',
            },
        ],
        'suppliers': [
            {
                'op': 'exist',
            },
        ],
        'revision': [
            {
                'op': 'exist',
            },
        ],
    },
    'message_broker': {
        'key': [
            {
                'op': 'exist',
            },
        ],
        'type': [
            {
                'op': 'equal',
                'arg': 'message_broker',
            },
        ],
        'timestamp': [
            {
                'op': 'exist',
            },
        ],
        'customer_idurl': [
            {
                'op': 'exist',
            },
        ],
        'broker_idurl': [
            {
                'op': 'exist',
            },
        ],
        'position': [
            {
                'op': 'exist',
            },
        ],
    },
    'bismuth_identity_request': {
        'type': [
            {
                'op': 'equal',
                'arg': 'bismuth_identity_request',
            },
        ],
        'timestamp': [
            {
                'op': 'exist',
            },
        ],
        'idurl': [
            {
                'op': 'exist',
            },
        ],
        'public_key': [
            {
                'op': 'exist',
            },
        ],
        'position': [
            {
                'op': 'exist',
            },
        ],
    },
    # customers relations are not stored, so this is actually not needed, but decided to leave it here just in case:
    # 'customers': {
    #     'key': [{'op': 'exist', }, ],
    #     'type': [{'op': 'equal', 'arg': 'customers', }, ],
    #     'timestamp': [{'op': 'exist', }, ],
    #     'customer_idurl': [{'op': 'exist', }, ],
    #     'revision': [{'op': 'exist', }, ],
    # },
    'skip_validation': {
        'type': [
            {
                'op': 'equal',
                'arg': 'skip_validation',
            },
        ],
    },
}

#------------------------------------------------------------------------------


def get_rules(record_type):
    global _Rules
    return _Rules.get(record_type, {})


def layer_name(layer_id):
    global LAYERS_REGISTRY
    return LAYERS_REGISTRY.get(layer_id, 'UNKNOWN')


#------------------------------------------------------------------------------


def get_nickname(key, use_cache=True):
    if _Debug:
        lg.args(_DebugLevel, key)
    return dht_service.get_valid_data(
        key=key,
        rules=get_rules('nickname'),
        use_cache_ttl=RELATION_RECORD_CACHE_TTL['nickname'] if use_cache else None,
    )


def set_nickname(key, idurl):
    if _Debug:
        lg.args(_DebugLevel, key, idurl)
    nickname, _, pos = key.partition(':')
    json_data = {
        'type': 'nickname',
        'timestamp': utime.utcnow_to_sec1970(),
        'idurl': idurl.to_bin(),
        'nickname': nickname,
        'position': pos,
    }
    return dht_service.set_valid_data(
        key=key,
        json_data=json_data,
        rules=get_rules('nickname'),
    )


#------------------------------------------------------------------------------


def get_identity(idurl, use_cache=True):
    if _Debug:
        lg.args(_DebugLevel, idurl)
    return dht_service.get_valid_data(
        idurl=idurl,
        rules=get_rules('identity'),
        return_details=True,
        use_cache_ttl=RELATION_RECORD_CACHE_TTL['identity'] if use_cache else None,
    )


def set_identity(idurl, raw_xml_data):
    if _Debug:
        lg.args(_DebugLevel, idurl)
    return dht_service.set_valid_data(
        key=idurl,
        json_data={
            'type': 'identity',
            'timestamp': utime.utcnow_to_sec1970(),
            'idurl': strng.to_text(idurl),
            'identity': strng.to_text(raw_xml_data),
        },
        rules=get_rules('identity'),
    )


#------------------------------------------------------------------------------


def get_udp_incoming():
    return


def set_udp_incoming():
    return


#------------------------------------------------------------------------------


def get_suppliers(customer_idurl, return_details=True, use_cache=True):
    if _Debug:
        lg.args(_DebugLevel, customer_idurl=customer_idurl, use_cache=use_cache)
    return dht_service.get_valid_data(
        key=dht_service.make_key(
            key=strng.to_text(customer_idurl),
            prefix='suppliers',
        ),
        rules=get_rules('suppliers'),
        return_details=return_details,
        use_cache_ttl=RELATION_RECORD_CACHE_TTL['suppliers'] if use_cache else None,
    )


def set_suppliers(customer_idurl, ecc_map, suppliers_list, revision=None, publisher_idurl=None, expire=60*60):
    if _Debug:
        lg.args(_DebugLevel, customer_idurl=customer_idurl, ecc_map=ecc_map, suppliers_list=suppliers_list, revision=revision)
    return dht_service.set_valid_data(
        key=dht_service.make_key(
            key=strng.to_text(customer_idurl),
            prefix='suppliers',
        ),
        json_data={
            'type': 'suppliers',
            'timestamp': utime.utcnow_to_sec1970(),
            'revision': 0 if revision is None else revision,
            'publisher_idurl': publisher_idurl.to_text() if publisher_idurl else None,
            'customer_idurl': customer_idurl.to_text(),
            'ecc_map': ecc_map,
            'suppliers': list(map(lambda i: i.to_text(), suppliers_list)),
        },
        rules=get_rules('suppliers'),
        expire=expire,
        collect_results=True,
    )


#------------------------------------------------------------------------------


def get_message_broker(customer_idurl, position=0, return_details=True, use_cache=True):
    if _Debug:
        lg.args(_DebugLevel, customer_idurl=customer_idurl, position=position)
    return dht_service.get_valid_data(
        key=dht_service.make_key(
            key='%s%d' % (strng.to_text(customer_idurl), position),
            prefix='message_broker',
        ),
        rules=get_rules('message_broker'),
        return_details=return_details,
        use_cache_ttl=RELATION_RECORD_CACHE_TTL['message_broker'] if use_cache else None,
    )


def set_message_broker(customer_idurl, broker_idurl, position=0, revision=None, expire=60*60):
    if _Debug:
        lg.args(_DebugLevel, customer=customer_idurl, pos=position, broker=broker_idurl, rev=revision)
    return dht_service.set_valid_data(
        key=dht_service.make_key(
            key='%s%d' % (strng.to_text(customer_idurl), position),
            prefix='message_broker',
        ),
        json_data={
            'type': 'message_broker',
            'timestamp': utime.utcnow_to_sec1970(),
            'revision': 0 if revision is None else revision,
            'customer_idurl': customer_idurl.to_text(),
            'broker_idurl': broker_idurl.to_text(),
            'position': position,
        },
        rules=get_rules('message_broker'),
        expire=expire,
        collect_results=True,
    )


#------------------------------------------------------------------------------


def get_bismuth_identity_request(position, use_cache=False):
    time_shift = int(utime.utcnow_to_sec1970()/(60*60))
    dht_key = dht_service.make_key(
        key=time_shift,
        index=position,
        prefix='blockchain_identity',
    )
    ret = dht_service.get_valid_data(
        key=dht_key,
        rules=get_rules('bismuth_identity_request'),
        use_cache_ttl=RELATION_RECORD_CACHE_TTL['bismuth_identity_request'] if use_cache else None,
    )
    if _Debug:
        lg.args(_DebugLevel, dht_key=dht_key, ret=ret)
    return ret


def set_bismuth_identity_request(position, idurl, public_key, wallet_address):
    json_data = {
        'type': 'bismuth_identity_request',
        'timestamp': utime.utcnow_to_sec1970(),
        'idurl': idurl.to_bin(),
        'public_key': public_key,
        'wallet_address': wallet_address,
        'position': position,
    }
    time_shift = int(utime.utcnow_to_sec1970()/(60*60))
    dht_key = dht_service.make_key(
        key=time_shift,
        index=position,
        prefix='blockchain_identity',
    )
    ret = dht_service.set_valid_data(
        key=dht_key,
        json_data=json_data,
        rules=get_rules('bismuth_identity_request'),
    )
    if _Debug:
        lg.args(_DebugLevel, dht_key=dht_key, idurl=idurl, wallet_address=wallet_address, ret=ret)
    return ret


def erase_bismuth_identity_request(position):
    time_shift = int(utime.utcnow_to_sec1970()/(60*60))
    dht_key = dht_service.make_key(
        key=time_shift,
        index=position,
        prefix='blockchain_identity',
    )
    ret = dht_service.delete_key(key=dht_key)
    if _Debug:
        lg.args(_DebugLevel, dht_key=dht_key, ret=ret)
    return ret
