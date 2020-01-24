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

_Debug = False
_DebugLevel = 8

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred, DeferredList  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from lib import strng

from dht import dht_records

from contacts import contactsdb

from userid import my_id
from userid import id_url

from contacts import identitycache

#------------------------------------------------------------------------------

def read_customer_suppliers(customer_idurl, as_fields=True):
    if as_fields:
        customer_idurl = id_url.field(customer_idurl)
    else:
        customer_idurl = id_url.to_bin(customer_idurl)
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
        if _customer_idurl and ( not id_url.is_cached(_customer_idurl) or not identitycache.HasFile(_customer_idurl) ):
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

    def _do_verify(dht_value):
        ret = {
            'suppliers': [],
            'ecc_map': None,
            'customer_idurl': customer_idurl,
            'revision': 0,
            'publisher_idurl': None,
            'timestamp': None,
        }
        if not dht_value or not isinstance(dht_value, dict):
            result.callback(ret)
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
        if my_id.getLocalID() != id_url.field(ret['customer_idurl']):
            contactsdb.set_suppliers(ret['suppliers'], customer_idurl=ret['customer_idurl'])
            contactsdb.save_suppliers(customer_idurl=ret['customer_idurl'])
        else:
            if _Debug:
                lg.out(_DebugLevel, 'dht_relations._do_save_customer_suppliers SKIP processing my own suppliers')
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.read_customer_suppliers  OK  for %r  returned %d suppliers' % (
                ret['customer_idurl'], len(ret['suppliers']), ))
        result.callback(ret)
        return ret

    def _on_error(err):
        try:
            msg = err.getErrorMessage()
        except:
            msg = str(err).replace('Exception:', '')
        if _Debug:
            lg.out(_DebugLevel, 'dht_relations.read_customer_suppliers ERROR %r  failed with %r' % (
                customer_idurl, msg, ))
        result.errback(err)
        return None

    d = dht_records.get_suppliers(id_url.to_bin(customer_idurl), return_details=True)
    d.addCallback(_do_verify)
    d.addErrback(_on_error)
    return result


def write_customer_suppliers(customer_idurl, suppliers_list, ecc_map=None, revision=None, publisher_idurl=None, ):
    customer_idurl = id_url.field(customer_idurl)
    publisher_idurl = id_url.field(publisher_idurl)
    if customer_idurl == my_id.getLocalID():
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
