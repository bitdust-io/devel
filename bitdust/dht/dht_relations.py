#!/usr/bin/python
# dht_relations.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred, DeferredList  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import strng

from bitdust.dht import dht_records

from bitdust.contacts import contactsdb

from bitdust.userid import my_id
from bitdust.userid import id_url

from bitdust.contacts import identitycache

#------------------------------------------------------------------------------


def read_customer_suppliers(customer_idurl, as_fields=True, use_cache=True):
    if as_fields:
        customer_idurl = id_url.field(customer_idurl)
    else:
        customer_idurl = id_url.to_bin(customer_idurl)

    rotated_idurls = id_url.list_known_idurls(customer_idurl, num_revisions=3)

    if _Debug:
        lg.args(_DebugLevel, customer_idurl=customer_idurl, rotated_idurls=rotated_idurls, as_fields=as_fields, use_cache=use_cache)

    result = Deferred()

    def _do_identity_cache(ret):
        all_stories = []
        for _supplier_idurl in ret['suppliers']:
            if _supplier_idurl:
                _supplier_idurl = id_url.to_bin(_supplier_idurl)
                if not id_url.is_cached(_supplier_idurl) or not identitycache.HasFile(_supplier_idurl):
                    one_supplier_story = identitycache.immediatelyCaching(_supplier_idurl)
                    one_supplier_story.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='read_customer_suppliers._do_identity_cache')
                    all_stories.append(one_supplier_story)
        _customer_idurl = id_url.to_bin(ret['customer_idurl'])
        if _customer_idurl and (not id_url.is_cached(_customer_idurl) or not identitycache.HasFile(_customer_idurl)):
            one_customer_story = identitycache.immediatelyCaching(_customer_idurl)
            one_customer_story.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='read_customer_suppliers._do_identity_cache')
            all_stories.append(one_customer_story)
        if _Debug:
            lg.args(_DebugLevel, all_stories=len(all_stories), ret=ret)
        id_cache_story = DeferredList(all_stories, consumeErrors=True)
        id_cache_story.addCallback(_do_save_customer_suppliers, ret)
        id_cache_story.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='read_customer_suppliers._do_identity_cache')
        id_cache_story.addErrback(result.errback)
        return id_cache_story

    def _do_verify(dht_value, customer_idurl_bin):
        if customer_idurl_bin in rotated_idurls:
            rotated_idurls.remove(customer_idurl_bin)
        ret = {
            'suppliers': [],
            'ecc_map': None,
            'customer_idurl': customer_idurl,
            'revision': 0,
            'publisher_idurl': None,
            'timestamp': None,
        }
        if not dht_value or not isinstance(dht_value, dict):
            if not rotated_idurls:
                result.callback(ret)
                return ret
            another_customer_idurl_bin = rotated_idurls.pop(0)
            lg.warn('found another rotated idurl %r and re-try reading customer suppliers' % another_customer_idurl_bin)
            d = dht_records.get_suppliers(another_customer_idurl_bin, return_details=True, use_cache=False)
            d.addCallback(_do_verify, another_customer_idurl_bin)
            d.addErrback(_on_error)
            return ret
        try:
            _ecc_map = strng.to_text(dht_value['ecc_map'])
            if as_fields:
                _customer_idurl = id_url.field(dht_value['customer_idurl'])
                _publisher_idurl = id_url.field(dht_value.get('publisher_idurl'))
                _suppliers_list = id_url.fields_list(dht_value['suppliers'])
            else:
                _customer_idurl = id_url.to_bin(dht_value['customer_idurl'])
                _publisher_idurl = id_url.to_bin(dht_value.get('publisher_idurl'))
                _suppliers_list = id_url.to_bin_list(dht_value['suppliers'])
            _revision = int(dht_value.get('revision'))
            _timestamp = int(dht_value.get('timestamp'))
        except:
            lg.exc()
            result.callback(ret)
            return ret
        ret.update({
            'suppliers': _suppliers_list,
            'ecc_map': _ecc_map,
            'customer_idurl': _customer_idurl,
            'revision': _revision,
            'publisher_idurl': _publisher_idurl,
            'timestamp': _timestamp,
        })
        return _do_identity_cache(ret)

    def _do_save_customer_suppliers(id_cached_result, ret):
        if my_id.getIDURL() != id_url.field(ret['customer_idurl']):
            contactsdb.set_suppliers(ret['suppliers'], customer_idurl=ret['customer_idurl'])
            contactsdb.save_suppliers(customer_idurl=ret['customer_idurl'])
            if ret.get('ecc_map'):
                for supplier_idurl in ret['suppliers']:
                    if supplier_idurl and id_url.is_cached(supplier_idurl):
                        contactsdb.add_supplier_meta_info(
                            supplier_idurl=supplier_idurl,
                            info={
                                'ecc_map': ret['ecc_map'],
                            },
                            customer_idurl=ret['customer_idurl'],
                        )
        else:
            if _Debug:
                lg.out(_DebugLevel, 'dht_relations._do_save_customer_suppliers SKIP processing my own suppliers')
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations._do_save_customer_suppliers  OK  for %r  returned %d suppliers' % (ret['customer_idurl'], len(ret['suppliers'])))
        result.callback(ret)
        return ret

    def _on_error(err):
        try:
            msg = err.getErrorMessage()
        except:
            msg = str(err).replace('Exception:', '')
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.read_customer_suppliers ERROR %r  failed with %r' % (customer_idurl, msg))
        result.errback(err)
        return None

    customer_idurl_bin = id_url.to_bin(customer_idurl)
    d = dht_records.get_suppliers(customer_idurl_bin, return_details=True, use_cache=use_cache)
    d.addCallback(_do_verify, customer_idurl_bin)
    d.addErrback(_on_error)
    return result


def write_customer_suppliers(
    customer_idurl,
    suppliers_list,
    ecc_map=None,
    revision=None,
    publisher_idurl=None,
):
    customer_idurl = id_url.field(customer_idurl)
    publisher_idurl = id_url.field(publisher_idurl)
    if customer_idurl == my_id.getIDURL():
        lg.warn('skip writing my own suppliers list which suppose to be written to DHT')
    else:
        contactsdb.set_suppliers(suppliers_list, customer_idurl=customer_idurl)
        contactsdb.save_suppliers(customer_idurl=customer_idurl)
    return dht_records.set_suppliers(
        customer_idurl=customer_idurl,
        suppliers_list=id_url.fields_list(suppliers_list),
        ecc_map=ecc_map,
        revision=revision,
        publisher_idurl=publisher_idurl,
    )


#------------------------------------------------------------------------------


def read_customer_message_brokers(customer_idurl, positions=[
    0,
], return_details=True, as_fields=True, use_cache=True):
    if _Debug:
        lg.args(_DebugLevel, customer_idurl=customer_idurl, use_cache=use_cache, positions=positions)
    if as_fields:
        customer_idurl = id_url.field(customer_idurl)
    else:
        customer_idurl = id_url.to_bin(customer_idurl)
    result = Deferred()

    def _on_borker_identity_cache_failed(err, position, broker_result):
        if _Debug:
            lg.args(_DebugLevel, position=position, err=err)
        broker_result.callback({
            'timestamp': None,
            'revision': 0,
            'customer_idurl': customer_idurl,
            'broker_idurl': None,
            'position': position,
        })
        return None

    def _do_broker_identity_cache(dht_record, position, broker_result):
        one_broker_task = identitycache.GetLatest(id_url.to_bin(dht_record['broker_idurl']))
        one_broker_task.addCallback(lambda xmlsrc: broker_result.callback(dht_record))
        one_broker_task.addErrback(_on_borker_identity_cache_failed, position, broker_result)
        # if _Debug:
        #     lg.args(_DebugLevel, position=position, broker_idurl=dht_record['broker_idurl'])
        return None

    def _do_verify(dht_value, position, broker_result):
        ret = {
            'timestamp': None,
            'revision': 0,
            'customer_idurl': customer_idurl,
            'broker_idurl': None,
            'position': position,
        }
        if not dht_value or not isinstance(dht_value, dict):
            if _Debug:
                lg.args(_DebugLevel, c=customer_idurl, p=position, dht_value=type(dht_value))
            broker_result.callback(ret)
            return ret
        try:
            if as_fields:
                _customer_idurl = id_url.field(dht_value['customer_idurl'])
                _broker_idurl = id_url.field(dht_value['broker_idurl'])
            else:
                _customer_idurl = id_url.to_bin(dht_value['customer_idurl'])
                _broker_idurl = id_url.to_bin(dht_value['broker_idurl'])
            _position = int(dht_value['position'])
            _revision = int(dht_value.get('revision'))
            _timestamp = int(dht_value.get('timestamp'))
        except:
            lg.exc()
            broker_result.callback(ret)
            return ret
        if _Debug:
            lg.args(_DebugLevel, p=position, b=_broker_idurl, r=_revision)
        if as_fields:
            if _customer_idurl != customer_idurl:
                lg.err('wrong customer idurl %r in message broker DHT record for %r at position %d' % (_customer_idurl, customer_idurl, position))
                broker_result.callback(ret)
                return ret
        if position != _position:
            lg.err('wrong position value %d in message broker DHT record for %r at position %d' % (_position, customer_idurl, position))
            broker_result.callback(ret)
            return ret
        ret.update({
            'customer_idurl': _customer_idurl,
            'broker_idurl': _broker_idurl,
            'position': _position,
            'revision': _revision,
            'timestamp': _timestamp,
        })
        _do_broker_identity_cache(ret, position, broker_result)
        return None

    def _on_error(err, position, broker_result):
        try:
            msg = err.getErrorMessage()
        except:
            msg = str(err).replace('Exception:', '')
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.read_customer_message_brokers ERROR %r at position %d failed with %r' % (customer_idurl, position, msg))
        broker_result.errback(err)
        return None

    def _do_collect_results(all_results):
        # if _Debug:
        #     lg.args(_DebugLevel, all_results=len(all_results))
        final_result = []
        for one_success, one_result in all_results:
            if one_success and one_result['broker_idurl']:
                final_result.append(one_result)
        final_result.sort(key=lambda i: i.get('position'))
        if _Debug:
            lg.args(_DebugLevel, results=len(final_result))
        result.callback(final_result)
        return None

    def _do_read_brokers():
        all_brokers_results = []
        for position in positions:
            one_broker_result = Deferred()
            all_brokers_results.append(one_broker_result)
            d = dht_records.get_message_broker(
                customer_idurl=customer_idurl,
                position=position,
                return_details=return_details,
                use_cache=use_cache,
            )
            d.addCallback(_do_verify, position, one_broker_result)
            d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='read_customer_message_brokers._do_read_brokers')
            d.addErrback(_on_error, position, one_broker_result)
        join_all_brokers = DeferredList(all_brokers_results, consumeErrors=False)
        join_all_brokers.addCallback(_do_collect_results)
        join_all_brokers.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='read_customer_message_brokers._do_read_brokers')
        join_all_brokers.addErrback(result.errback)
        return None

    d = identitycache.GetLatest(customer_idurl)
    d.addCallback(lambda _: _do_read_brokers())
    d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='read_customer_message_brokers')
    d.addErrback(result.errback)
    return result


def write_customer_message_broker(customer_idurl, broker_idurl, position=0, revision=None):
    if _Debug:
        lg.args(_DebugLevel, c=customer_idurl, b=broker_idurl, p=position, r=revision)
    customer_idurl = id_url.field(customer_idurl)
    broker_idurl = id_url.field(broker_idurl)
    return dht_records.set_message_broker(
        customer_idurl=customer_idurl,
        broker_idurl=broker_idurl,
        position=position,
        revision=revision,
    )
