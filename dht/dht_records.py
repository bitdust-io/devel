#!/usr/bin/python
# dht_records.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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
_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

from logs import lg

from dht import dht_service

from lib import utime

#------------------------------------------------------------------------------

_Rules = {
    'nickname': {
        'type': [{'op': 'equal', 'arg': 'nickname', }, ],
        'timestamp': [{'op': 'exist', }, ],
        'idurl': [{'op': 'exist', }, ],
        'nickname': [{'op': 'exist', }, ],
        'position': [{'op': 'exist', }, ],
    },
    'identity': {
        'type': [{'op': 'equal', 'arg': 'identity', }, ],
        'timestamp': [{'op': 'exist', }, ],
        'idurl': [{'op': 'exist', }, ],
        'identity': [{'op': 'exist', }, ],
    },
    'relation': {
        'type': [{'op': 'equal', 'arg': 'relation', }, ],
        'timestamp': [{'op': 'exist', }, ],
        'idurl': [{'op': 'exist', }, ],
        'index': [{'op': 'exist', }, ],
        'prefix': [{'op': 'exist', }, ],
        'data': [{'op': 'exist', }, ],
    },
}

def get_rules(record_type):
    global _Rules
    return _Rules.get(record_type, {})

#------------------------------------------------------------------------------

def get_nickname(key):
    if _Debug:
        lg.args(_DebugLevel, key)
    return dht_service.get_valid_data(key, rules=get_rules('nickname'))

def set_nickname(key, idurl):
    if _Debug:
        lg.args(_DebugLevel, key, idurl)
    nickname, _, pos = key.partition(':')
    return dht_service.set_valid_data(
        key=key,
        json_data={
            'type': 'nickname',
            'timestamp': utime.get_sec1970(),
            'idurl': idurl,
            'nickname': nickname,
            'position': pos,
        },
        rules=get_rules('nickname'),
    )

#------------------------------------------------------------------------------

def get_identity(idurl):
    if _Debug:
        lg.args(_DebugLevel, idurl)
    return dht_service.get_valid_data(idurl, rules=get_rules('identity'))

def set_identity(idurl, raw_xml_data):
    if _Debug:
        lg.args(_DebugLevel, idurl)
    return dht_service.set_valid_data(
        key=idurl,
        json_data={
            'type': 'identity',
            'timestamp': utime.get_sec1970(),
            'idurl': idurl,
            'identity': raw_xml_data,
        },
        rules=get_rules('identity'),
    )

#------------------------------------------------------------------------------

def get_udp_incoming():
    return

def set_udp_incoming():
    return

#------------------------------------------------------------------------------

def get_relation(key):
    if _Debug:
        lg.args(_DebugLevel, key)
    return dht_service.get_valid_data(key, rules=get_rules('relation'))

def set_relation(key, idurl, data, prefix, index):
    if _Debug:
        lg.args(_DebugLevel, key, idurl, prefix, index)
    return dht_service.set_valid_data(
        key=key,
        json_data={
            'type': 'relation',
            'timestamp': utime.get_sec1970(),
            'idurl': idurl,
            'index': index,
            'prefix': prefix,
            'data': data,
        },
        rules=get_rules('relation'),
        expire=60 * 5,
    )

#------------------------------------------------------------------------------
