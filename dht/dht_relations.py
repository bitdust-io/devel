#!/usr/bin/python
# dht_relations.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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
.. module:: dht_relations

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

from twisted.internet import reactor
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from lib import utime
from lib import strng

from userid import my_id
from userid import global_id

from contacts import contactsdb

from dht import dht_service
from dht import dht_records

#------------------------------------------------------------------------------

class RelationsLookup(object):

    def __init__(self, customer_idurl, new_data=None, publish=False,
                 limit_lookups=100, max_misses_in_row=3, prefix='customer_supplier'):
        self.customer_idurl = customer_idurl
        self.customer_id = global_id.UrlToGlobalID(self.customer_idurl)
        self._result_defer = Deferred()
        self._new_data = new_data
        self._publish = publish
        self._limit_lookups = limit_lookups
        self._index = 0
        self._last_success_index = -1
        self._last_missed_index = -1
        self._max_misses_in_row = max_misses_in_row
        self._prefix = prefix
        self._misses_in_row = 0
        self._missed = 0
        self._result = {}
        self._meta = {}

    def start(self):
        reactor.callLater(0, self.do_read)
        return self._result_defer

    #------------------------------------------------------------------------------

    def do_read(self):
        # TODO: build more smart and fault sensitive method
        if self._index >= self._limit_lookups:
            if _Debug:
                lg.out(_DebugLevel, 'dht_relations.do_read STOP %s, limit lookups riched' % self.customer_id)
            self.do_report_success()
            return None
        if self._last_missed_index >= 0 and self._index - self._last_missed_index > self._max_misses_in_row:
            if _Debug:
                lg.out(_DebugLevel, 'dht_relations.do_read STOP %s, last missed index is %d' % (
                    self.customer_id, self._last_missed_index))
            self.do_report_success()
            return None
        target_dht_key = dht_service.make_key(
            key=self.customer_id,
            index=self._index,
            prefix=self._prefix,
        )
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.do_read %s:%d missed:%d' % (
                self.customer_id, self._index, self._missed))
        d = dht_records.get_relation(target_dht_key)
        d.addCallback(self.do_verify)
        d.addErrback(self.do_verify)
        return d

    def do_erase(self):
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.do_erase %s:%s' % (
                self.customer_id, self._index, ))
        target_dht_key = dht_service.make_key(
            key=self.customer_id,
            index=self._index,
            prefix=self._prefix,
        )
        d = dht_service.delete_key(target_dht_key)
        d.addCallback(self.do_report_success)
        d.addErrback(self.do_report_failed)
        return 3

    def do_write(self):
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.do_write %s:%s' % (
                self.customer_id, self._index, ))
        new_dht_key = dht_service.make_key(
            key=self.customer_id,
            index=self._index,
            prefix=self._prefix,
        )
        d = dht_records.set_relation(
            new_dht_key, self.customer_idurl, self._new_data, self._prefix, self._index, )
        d.addCallback(self.do_report_success)
        d.addErrback(self.do_report_failed)
        return 2

    def do_next(self, verified):
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.do_next %s:%s, last_missed:%d' % (
                self.customer_id, self._index, self._last_missed_index))
        if verified == -1:
            self._missed += 1
            if self._last_missed_index == -1:
                self._last_missed_index = self._index
        self._index += 1

    def do_verify(self, dht_value):
        record = None
        if isinstance(dht_value, dict):
            try:
                record = dht_value['data']
                record['customer_idurl'] = strng.to_bin(record['customer_idurl'])
                record['supplier_idurl'] = strng.to_bin(record['supplier_idurl'])
                record['time'] = int(record['time'])
                record['signature'] = str(record['signature'])
            except:
                lg.exc()

        if not record:
            if _Debug:
                lg.out(_DebugLevel, 'dht_relations.do_verify MISSED %s: broken/empty record found at pos %s' % (
                    self.customer_id, self._index))
            # record not exist or invalid
            return self.do_process(record, -1)

        if record['customer_idurl'] != self.customer_idurl:
            if _Debug:
                lg.out(_DebugLevel, 'dht_relations.do_verify ERROR, found invalid record %s at %s' % (
                    self.customer_id, self._index))
            # record exist but stored for another customer - can be overwritten
            return self.do_process(record, -1)

        if record['supplier_idurl'] == my_id.getLocalID():
            # TODO: verify signature
            if _Debug:
                lg.out(_DebugLevel, 'dht_relations.do_verify SUCCESS, found own data %s at %s' % (
                    self.customer_id, self._index))
            # record exist and store relation to me
            return self.do_process(record, 1)

        if record['supplier_idurl'] in list(self._result.values()):
            lg.out(_DebugLevel, 'dht_relations.do_verify DUPLICATED %s, found second record for supplier %s at %s' % (
                self.customer_id, record['supplier_idurl'], self._index))
            # this record from another supplier is duplicated - we can overwrite it
            return self.do_process(record, -1)

        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.do_verify NEXT %s, found another supplier record %s at %s' % (
                record['supplier_idurl'], self.customer_id, self._index))
        # this is a correct record from another supplier
        return self.do_process(record, 0)

    def do_process(self, record, verified):
        if verified == -1:
            # record #N is not exist, might be invalid or duplicated
            if self._publish:
                if self._new_data:
                    return self.do_write()
                return self.do_erase()
            self.do_next(verified)
            self.do_read()
            return verified

        if verified == 0:
            # record #N from another supplier
            self._last_success_index = self._index
            self._result[self._index] = record['supplier_idurl']
            self._meta[self._index] = {'ecc_map': record.get('ecc_map'), }
            self.do_next(verified)
            self.do_read()
            return verified

        if verified == 1:
            # record #N from me
            self._last_success_index = self._index
            self._result[self._index] = record['supplier_idurl']
            self._meta[self._index] = {'ecc_map': record.get('ecc_map'), }
            if self._publish:
                if self._new_data:
                    return self.do_write()
                return self.do_erase()
            # still want to continue further to get all list
            self.do_next(verified)
            self.do_read()
            return verified

        raise Exception()

    def do_close(self):
        self._result_defer = None
        self._new_data = None
        self._publish = False
        self._index = 0
        self._last_success_index = -1
        self._last_missed_index = -1
        self._max_misses_in_row = 0
        self._misses_in_row = 0
        self._missed = 0
        self._result = {}
        self._meta = {}

    def do_report_success(self, x=None):
        result_list = []
        for i in range(self._last_success_index + 1):
            idurl = self._result.get(i, '')
            if idurl:
                result_list.append(self._result.get(i, ''))
                meta_info = self._meta.get(i, {})
                if meta_info:
                    contactsdb.add_supplier_meta_info(
                        idurl, meta_info, customer_idurl=self.customer_idurl)
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.do_report_success customer_id=%s:' % (
                self.customer_id))
            lg.out(_DebugLevel, '    %s' % result_list)
        self._result_defer.callback(result_list)
        self.do_close()
        return None

    def do_report_failed(self, err):
        lg.warn(err)
        self._result_defer.errback(err)
        self.do_close()
        return None

#------------------------------------------------------------------------------

def publish_customer_supplier_relation(customer_idurl, supplier_idurl=None):
    if not supplier_idurl:
        supplier_idurl = my_id.getLocalID()
    meta_info = contactsdb.get_customer_meta_info(customer_idurl)
    if _Debug:
        lg.out(_DebugLevel, 'dht_relations.publish_customer_supplier_relation: customer:%s supplier:%s meta:%s' % (
            customer_idurl, supplier_idurl, meta_info, ))
    new_data = {
        'customer_idurl': customer_idurl,
        'supplier_idurl': supplier_idurl,
        'ecc_map': meta_info.get('ecc_map', None),
        'time': utime.utcnow_to_sec1970(),
        'signature': '',
        # TODO: add signature and verification methods
    }
    return RelationsLookup(customer_idurl, new_data=new_data, publish=True).start()


def close_customer_supplier_relation(customer_idurl):
    if _Debug:
        lg.out(_DebugLevel, 'dht_relations.close_customer_supplier_relation: customer:%s' % (
            customer_idurl, ))
    return RelationsLookup(customer_idurl, new_data=None, publish=True).start()


def scan_customer_supplier_relations(customer_idurl):
    if _Debug:
        lg.out(_DebugLevel, 'dht_relations.scan_customer_supplier_relations: customer:%s' % (
            customer_idurl, ))
    return RelationsLookup(customer_idurl, new_data=None, publish=False).start()
