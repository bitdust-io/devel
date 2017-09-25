#!/usr/bin/python
# dht_relations.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (dht_relations.py) is part of BitDust Software.
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
.. module:: dht_relations.

"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

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

class RelationsLookup(object):

    def __init__(self, customer_idurl, new_data=None, publish=False, limit_lookups=100):
        self.customer_idurl = customer_idurl
        self._new_data = new_data
        self._publish = publish
        self._limit_lookups = limit_lookups
        self._index = 0
        self._missed = 0
        self._result = []

    def cb_get_value(self, value):
#         if _Debug:
#             lg.out(_DebugLevel + 10, 'dht_relations.cb_get_value %s: %s' % (self._index, value))
        if not isinstance(value, dict):
            if self._publish:
                return self.do_write()
            else:
                self._index += 1
                self._missed += 1
                return self.do_read()
        try:
            value = value[dht_service.key_to_hash(make_dht_key(self.customer_idurl, self._index))]
        except:
            lg.warn('dht key not found or bad value: %s' % value)
            if self._publish:
                return self.do_write()
            else:
                self._index += 1
                self._missed += 1
                return self.do_read()
        return self.do_verify(value)

    def eb_get_value(self, err, customer_idurl, index, new_data, publish):
#         if _Debug:
#             lg.out(_DebugLevel + 10, 'dht_relations.eb_get_value %s: %s' % (index, err))
        return err
    #     if not new_data:
    #         return do_read(customer_idurl, index + 1, new_data)
    #     return do_write(customer_idurl, index, new_data)

    def cb_set_value(self, value):
#         if _Debug:
#             lg.out(_DebugLevel + 10, 'dht_relations.cb_set_value %s: %s' % (self._index, value))
        return value

    def eb_set_value(self, err):
#         if _Debug:
#             lg.out(_DebugLevel + 10, 'dht_relations.eb_set_value %s: %s' % (self._index, err))
        return err

    #------------------------------------------------------------------------------

    def do_write(self):
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.do_write %s' % self._index)
        if not self._new_data:
            d = dht_service.delete_key(make_dht_key(self.customer_idurl, self._index))
            d.addCallback(self.cb_set_value)
            d.addErrback(self.eb_set_value)
            return d
        new_payload = json.dumps(self._new_data)
        d = dht_service.set_value(make_dht_key(self.customer_idurl, self._index), new_payload, age=int(time.time()))
        d.addCallback(self.cb_set_value)
        d.addErrback(self.eb_set_value)
        return d

    def do_read(self):
        if _Debug:
            lg.out(_DebugLevel + 6, 'dht_relations.do_read index:%d missed:%d' % (self._index, self._missed))
        if self._index >= self._limit_lookups:  # TODO: more smart and fault sensitive method
            return None
        if self._index >= 3 and self._missed >= 3:
            if float(self._missed) / float(self._index) > 0.5:
                return None
        d = dht_service.get_value(make_dht_key(self.customer_idurl, self._index))
        d.addCallback(self.cb_get_value)
        d.addErrback(self.eb_get_value)
        return d

    def do_verify(self, value):
        if _Debug:
            lg.out(_DebugLevel + 6, 'dht_relations.do_verify %s' % self._index)
        try:
            old_data = json.loads(value)
            old_data['customer_idurl']
            old_data['supplier_idurl']
            int(old_data['time'])
            old_data['signature']
        except:
            lg.exc()
            if self._publish:
                return self.do_write()
            else:
                self._index += 1
                return self.do_read()
        if old_data['customer_idurl'] != self.customer_idurl:
            if _Debug:
                lg.out(_DebugLevel - 4, 'dht_relations.do_verify ERROR, found invalid data %s at %s' % (
                    self.customer_idurl, self._index))
            if self._publish:
                return self.do_write()
            else:
                self._index += 1
                return self.do_read()
        if old_data['supplier_idurl'] != my_id.getLocalID():
            if _Debug:
                lg.out(_DebugLevel + 6, 'dht_relations.do_verify SKIP %s, found another supplier %s at %s' % (
                    old_data['supplier_idurl'], self.customer_idurl, self._index))
            self._index += 1
            return self.do_read()
        return self.do_process(value)

    def do_process(self, value):
        if not self._new_data:
            if _Debug:
                lg.out(_DebugLevel, 'dht_relations.do_process will REMOVE data for %s at %s' % (
                    self.customer_idurl, self._index))
            if self._publish:
                return self.do_write()
            else:
                self._index += 1
                return self.do_read()
        # TODO: verify signature
        # TODO: check expiration time
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.do_process SUCCESS, found valid data %s at %s' % (
                self.customer_idurl, self._index))
        return value

#------------------------------------------------------------------------------

def publish_customer_supplier_relation(customer_idurl, supplier_idurl=None):
    if not supplier_idurl:
        supplier_idurl = my_id.getLocalID()
    new_data = {
        'customer_idurl': customer_idurl,
        'supplier_idurl': supplier_idurl,
        'time': utime.utcnow_to_sec1970(),
        'signature': '',  # TODO: add signature and verification
    }
    ll = RelationsLookup(customer_idurl, new_data=new_data, publish=True)
    ll.do_read()


def close_customer_supplier_relation(customer_idurl):
    RelationsLookup(customer_idurl, new_data=None, publish=True).do_read()


def scan_customer_supplier_relations(customer_idurl):
    RelationsLookup(customer_idurl, new_data=None, publish=False).do_read()
