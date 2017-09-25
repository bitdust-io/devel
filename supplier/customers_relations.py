#!/usr/bin/python
# customers_relations.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (customers_relations.py) is part of BitDust Software.
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
.. module:: customers_relations.

"""
#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import time
import json

#------------------------------------------------------------------------------

from logs import lg

from lib import utime

from system import bpio

from main import settings

from userid import my_id

from dht import dht_service

#------------------------------------------------------------------------------

def make_dht_key(key, index):
    return '{}:{}'.format(key, index)

#------------------------------------------------------------------------------

def cb_get_value(value, customer_idurl, index, new_data):
    if _Debug:
        lg.out(_DebugLevel + 10, 'customers_relations.cb_get_value %s: %s' % (index, value))
    if not isinstance(value, dict):
        return do_write(customer_idurl, index, new_data)
    try:
        value = value[dht_service.key_to_hash(make_dht_key(customer_idurl, index))]
    except:
        lg.exc()
        return do_write(customer_idurl, index, new_data)
    return do_verify(value, customer_idurl, index, new_data)


def eb_get_value(err, customer_idurl, index, new_data):
    if _Debug:
        lg.out(_DebugLevel + 10, 'customers_relations.eb_get_value %s: %s' % (index, err))
    return err
#     if not new_data:
#         return do_read(customer_idurl, index + 1, new_data)
#     return do_write(customer_idurl, index, new_data)


def cb_set_value(value, customer_idurl, index, new_data):
    if _Debug:
        lg.out(_DebugLevel + 10, 'customers_relations.cb_set_value %s: %s' % (index, value))
    return value


def eb_set_value(err, customer_idurl, index, new_data):
    if _Debug:
        lg.out(_DebugLevel + 10, 'customers_relations.eb_set_value %s: %s' % (index, err))
    return err

#------------------------------------------------------------------------------

def do_write(customer_idurl, index, new_data):
    if _Debug:
        lg.out(_DebugLevel + 10, 'customers_relations.do_write %s' % index)
    if not new_data:
        d = dht_service.delete_key(make_dht_key(customer_idurl, index))
        d.addCallback(cb_set_value, customer_idurl, index, new_data)
        d.addErrback(eb_set_value, customer_idurl, index, new_data)
        return d
    new_payload = json.dumps(new_data)
    d = dht_service.set_value(make_dht_key(customer_idurl, index), new_payload, age=int(time.time()))
    d.addCallback(cb_set_value, customer_idurl, index, new_data)
    d.addErrback(eb_set_value, customer_idurl, index, new_data)
    return d


def do_read(customer_idurl, index, new_data):
    if _Debug:
        lg.out(_DebugLevel + 10, 'customers_relations.do_read %s' % index)
    d = dht_service.get_value(make_dht_key(customer_idurl, index))
    d.addCallback(cb_get_value, customer_idurl, index, new_data)
    d.addErrback(eb_get_value, customer_idurl, index, new_data)
    return d


def do_verify(value, customer_idurl, index, new_data):
    if _Debug:
        lg.out(_DebugLevel + 10, 'customers_relations.do_verify %s' % index)
    try:
        old_data = json.loads(value)
        old_data['customer_idurl']
        old_data['supplier_idurl']
        int(old_data['time'])
        old_data['signature']
    except:
        lg.exc()
        return do_write(customer_idurl, index, new_data)
    if old_data['customer_idurl'] != customer_idurl:
        if _Debug:
            lg.out(_DebugLevel - 4, 'customers_relations.do_verify ERROR, found invalid data %s at %s' % (
                customer_idurl, index))
        return do_write(customer_idurl, index, new_data)
    if old_data['supplier_idurl'] != my_id.getLocalID():
        if _Debug:
            lg.out(_DebugLevel + 10, 'customers_relations.do_verify SKIP %s, found another supplier %s at %s' % (
                old_data['supplier_idurl'], customer_idurl, index))
        return do_read(customer_idurl, index + 1, new_data)
    if not new_data:
        if _Debug:
            lg.out(_DebugLevel, 'customers_relations.do_verify will REMOVE data for %s at %s' % (
                customer_idurl, index))
        return do_write(customer_idurl, index, new_data)
    # TODO: verify signature
    # TODO: check expiration time
    if _Debug:
        lg.out(_DebugLevel, 'customers_relations.do_verify SUCCESS, found valid data %s at %s' % (
            customer_idurl, index))
    return value

#------------------------------------------------------------------------------

def publish_customer_relation(customer_idurl):
    new_data = {
        'customer_idurl': customer_idurl,
        'supplier_idurl': my_id.getLocalID(),
        'time': utime.utcnow_to_sec1970(),
        'signature': '',  # TODO: add signature and verification
    }
    do_read(customer_idurl, 0, new_data)


def close_customer_relation(customer_idurl):
    do_read(customer_idurl, 0, None)
