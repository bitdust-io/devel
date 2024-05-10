#!/usr/bin/python
# contactsdb.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (contactsdb.py) is part of BitDust Software.
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
"""
.. module:: contactsdb.

A low level methods to store list of contacts locally.:
    + suppliers
    + customers
    + correspondents
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range  # @UnresolvedImport

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

from twisted.internet.defer import DeferredList

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import nameurl
from bitdust.lib import strng
from bitdust.lib import jsn

from bitdust.system import bpio
from bitdust.system import local_fs

from bitdust.main import settings
from bitdust.main import listeners

from bitdust.services import driver

from bitdust.userid import id_url
from bitdust.userid import my_id
from bitdust.userid import global_id

from bitdust.contacts import identitycache

#-------------------------------------------------------------------------------

_CustomersList = []  # comes from settings.CustomerIDsFilename()
_SuppliersList = {}  # comes from settings.SuppliersDir()
_CorrespondentsList = []  # comes from settings.CorrespondentIDsFilename()
_CorrespondentsDict = {}

_SuppliersChangedCallback = None
_CustomersChangedCallback = None
_CorrespondentsChangedCallback = None
_ContactsChangedCallbacks = []

_CustomersMetaInfo = {}
_SuppliersMetaInfo = {}
_CorrespondentsMetaInfo = {}

#-------------------------------------------------------------------------------


def init():
    """
    We read from disk and if we have all the info we are set.

    If we don't have enough, then we have to ask BitDust to list
    contacts and use that list to get and then store all the identities
    for our contacts.
    """
    global _SuppliersChangedCallback
    global _CustomersChangedCallback
    global _CorrespondentsChangedCallback
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.init')
    d = cache_contacts()
    d.addCallback(lambda _: load_contacts())
    d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='contactsdb.init')
    return d


def shutdown():
    global _SuppliersChangedCallback
    global _CustomersChangedCallback
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.shutdown')
    RemoveContactsChangedCallback(on_contacts_changed)
    if _SuppliersChangedCallback is not None:
        _SuppliersChangedCallback = None
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback = None


#------------------------------------------------------------------------------


def suppliers(customer_idurl=None):
    """
    Return list of suppliers ID's for given customer - me or another user.
    """
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _SuppliersList:
        _SuppliersList[customer_idurl] = []
        lg.info('created new suppliers list in memory for customer %r' % customer_idurl)
    return _SuppliersList[customer_idurl]


def supplier(index, customer_idurl=None):
    """
    Return supplier ID on given position or empty string.
    """
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    num = int(index)
    if num >= 0 and num < len(suppliers(customer_idurl=customer_idurl)):
        return suppliers(customer_idurl=customer_idurl)[num]
    return id_url.field(b'')


def all_suppliers(as_dict=False):
    global _SuppliersList
    if as_dict:
        return _SuppliersList
    result = []
    for suppliers_list in _SuppliersList.values():
        for supplier_idurl in suppliers_list:
            if id_url.is_cached(supplier_idurl) and supplier_idurl not in result:
                result.append(supplier_idurl)
    return result


def set_suppliers(idlist, customer_idurl=None):
    """
    Set suppliers ID's list.
    """
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _SuppliersList:
        _SuppliersList[customer_idurl] = []
        lg.info('created new suppliers list in memory for customer %r' % customer_idurl)
    try:
        _SuppliersList[customer_idurl] = id_url.fields_list(idlist)
    except:
        pass
    if _Debug:
        lg.args(_DebugLevel, suppliers=_SuppliersList[customer_idurl], customer_idurl=customer_idurl)


def update_suppliers(idlist, customer_idurl=None):
    """
    High-level method to set suppliers ID's list.
    Executes required callbacks.
    """
    global _SuppliersChangedCallback
    global _ContactsChangedCallbacks
    oldsuppliers = list(suppliers(customer_idurl=customer_idurl))
    oldcontacts = list(contacts())
    idlist = list(map(lambda i: i if id_url.is_cached(i) else b'', idlist))
    set_suppliers(idlist, customer_idurl=customer_idurl)
    if _SuppliersChangedCallback is not None:
        _SuppliersChangedCallback(oldsuppliers, suppliers(customer_idurl=customer_idurl))
    if id_url.to_original_list(oldcontacts) != id_url.to_original_list(contacts()):
        for cb in _ContactsChangedCallbacks:
            cb(id_url.to_original_list(oldcontacts), id_url.to_original_list(contacts()))


def add_supplier(idurl, position=None, customer_idurl=None):
    """
    Add supplier in my list of suppliers or to the list stored for another customer.
    If parameter `position` is provided, supplier will be inserted instead of added.
    If position is greater than current list - empty strings will be filled in between.
    """
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _SuppliersList:
        _SuppliersList[customer_idurl] = []
        lg.info('created new suppliers list in memory for customer %r' % customer_idurl)
    idurl = id_url.field(idurl)
    if _Debug:
        lg.args(_DebugLevel, idurl=idurl, position=position, customer_idurl=customer_idurl)
    if position is None or position == -1:
        lg.warn('position unknown, added supplier "%s" to the end of the list for customer %s' % (idurl, customer_idurl))
        _SuppliersList[customer_idurl].append(idurl)
        return len(_SuppliersList[customer_idurl]) - 1
    current_suppliers = _SuppliersList[customer_idurl]
    if position >= len(current_suppliers):
        empty_suppliers = [
            id_url.field(b''),
        ]*(1 + position - len(current_suppliers))
        current_suppliers.extend(empty_suppliers)
        if _Debug:
            lg.out(_DebugLevel, 'contactsdb.add_supplier   %d empty suppliers added for customer %r' % (len(empty_suppliers), customer_idurl))
    if current_suppliers[position] and current_suppliers[position] != idurl:
        lg.info('replacing known supplier "%s" by "%s" at position %d for customer %s' % (current_suppliers[position], idurl, position, customer_idurl))
    else:
        lg.info('added supplier "%s" at position %d for customer %s' % (idurl, position, customer_idurl))
    current_suppliers[position] = idurl
    update_suppliers(idlist=current_suppliers, customer_idurl=customer_idurl)
    return position


def erase_supplier(idurl=None, position=None, customer_idurl=None):
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _SuppliersList:
        return False
    current_suppliers = _SuppliersList[customer_idurl]
    if _Debug:
        lg.args(_DebugLevel, idurl=idurl, position=position, customer_idurl=customer_idurl)
    if idurl:
        idurl = id_url.field(idurl)
        if idurl not in current_suppliers:
            return False
        current_suppliers[current_suppliers.index(idurl)] = id_url.field(b'')
    elif position is not None:
        if position >= len(current_suppliers):
            return False
        current_suppliers[position] = id_url.field(b'')
    else:
        return False
    update_suppliers(idlist=current_suppliers, customer_idurl=customer_idurl)
    return True


def clear_suppliers(customer_idurl=None):
    """
    Remove all suppliers for given customer, if customer_idurl is None will erase all my suppliers.
    """
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    _SuppliersList.pop(customer_idurl)
    lg.info('erased suppliers list from memory for customer %r' % customer_idurl)


def clear_all_suppliers():
    """
    Remove all suppliers.
    """
    global _SuppliersList
    _SuppliersList.clear()


#------------------------------------------------------------------------------


def known_customers():
    """
    Return list of all known customers : if I need to connect to their suppliers.
    """
    global _SuppliersList
    return list(_SuppliersList.keys())


def customers():
    """
    Return list of my customers ID's if I am a supplier.
    """
    global _CustomersList
    return _CustomersList


def customer(index):
    """
    Return customer IDURL at given position or empty string if I have no customers.
    """
    num = int(index)
    if num >= 0 and num < len(customers()):
        return customers()[num]
    return id_url.field(b'')


def set_customers(idlist):
    """
    Set customers list.
    """
    global _CustomersList
    try:
        _CustomersList = id_url.fields_list(idlist)
    except:
        pass


def update_customers(idslist):
    """
    High-level method to set customers ID's list.
    Executes required callbacks.
    """
    global _CustomersChangedCallback
    global _ContactsChangedCallbacks
    old_customers = list(customers())
    old_contacts = list(contacts())
    idslist = list(filter(id_url.is_cached, idslist))
    set_customers(idslist)
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback(old_customers, customers())
    for cb in _ContactsChangedCallbacks:
        cb(id_url.to_original_list(old_contacts), id_url.to_original_list(contacts()))
    if _Debug:
        lg.args(_DebugLevel, new_customers=idslist, old_customers=old_customers)


def clear_customers():
    """
    Remove all customers.
    """
    global _CustomersList
    _CustomersList = []


#------------------------------------------------------------------------------


def contacts(include_all=False, include_enabled=True):
    """
    Return a union of suppliers and customers ID's.
    """
    result = set()
    if include_all or (include_enabled and driver.is_enabled('service_customer')) or driver.is_on('service_customer'):
        result.update(set(all_suppliers()))
    if include_all or (include_enabled and driver.is_enabled('service_supplier')) or driver.is_on('service_supplier'):
        result.update(set(customers() + known_customers()))
    if include_all or (include_enabled and driver.is_enabled('service_private_messages')) or driver.is_on('service_private_messages'):
        result.update(set(correspondents_ids()))
    # if include_all or include_enabled:
    #     if driver.is_enabled('service_message_broker') or driver.is_on('service_message_broker'):
    #         from bitdust.stream import message_peddler
    #         result.update(set(message_peddler.list_customers()))
    #         result.update(set(message_peddler.list_consumers_producers(include_consumers=True, include_producers=True)))
    #         result.update(set(message_peddler.list_known_brokers()))
    return list(result)


def contacts_list():
    """
    Return a list of suppliers and customers ID's.
    """
    return list(suppliers() + customers())


def contacts_remote(include_all=False, include_enabled=True):
    """
    Return ID's list of all known peers.
    """
    l = id_url.to_bin_list(contacts(include_all=include_all, include_enabled=include_enabled))
    return [i for i in id_url.fields_list(l) if not id_url.is_the_same(i, my_id.getIDURL())]


#------------------------------------------------------------------------------


def correspondents():
    """
    Return list of tuples of correspondents: (IDURL, nickname).
    """
    global _CorrespondentsList
    return _CorrespondentsList


def correspondents_ids():
    """
    Return list of correspondents IDURLs.
    """
    global _CorrespondentsList
    return [tupl[0] for tupl in _CorrespondentsList]


def correspondents_dict():
    """
    Return dictionary of correspondents : IDURL->nickname.
    """
    global _CorrespondentsList
    return dict(_CorrespondentsList)


def set_correspondents(idlist):
    """
    Set correspondents from list of tuples without notification.
    """
    global _CorrespondentsList
    _CorrespondentsList = [(id_url.field(idurl_name[0]).to_bin(), idurl_name[1]) for idurl_name in idlist]


def add_correspondent(idurl, nickname=''):
    """
    Add correspondent, execute notification callback and return its position in
    the list.
    """
    global _CorrespondentsList
    global _CorrespondentsChangedCallback
    curlist = list(_CorrespondentsList)
    idurl = id_url.field(idurl)
    _CorrespondentsList.append((
        idurl.to_bin(),
        nickname,
    ))
    if _CorrespondentsChangedCallback is not None:
        _CorrespondentsChangedCallback(curlist, _CorrespondentsList)
    listeners.push_snapshot('correspondent', snap_id=idurl.to_bin(), data=dict(
        idurl=idurl.to_bin(),
        nickname=nickname,
    ))
    return len(curlist)


def remove_correspondent(idurl):
    """
    Remove correspondent with given IDURL, execute notification callback and
    return True if success.
    """
    global _CorrespondentsList
    global _CorrespondentsChangedCallback
    curlist = list(_CorrespondentsList)
    idurl = id_url.field(idurl)
    for tupl in _CorrespondentsList:
        if idurl.to_bin() == id_url.field(tupl[0]).to_bin():
            _CorrespondentsList.remove(tupl)
            if _CorrespondentsChangedCallback is not None:
                _CorrespondentsChangedCallback(curlist, _CorrespondentsList)
            listeners.push_snapshot('correspondent', snap_id=idurl.to_bin(), deleted=True, data=dict(
                idurl=idurl.to_bin(),
                nickname=tupl[1],
            ))
            return True
    return False


def populate_correspondents():
    for corr in correspondents():
        listeners.push_snapshot('correspondent', snap_id=corr[0], data=dict(
            idurl=corr[0],
            nickname=corr[1],
        ))


#-------------------------------------------------------------------------------


def is_customer(idurl):
    """
    Return True if given ID is found in customers list.
    """
    if id_url.is_empty(idurl):
        return False
    return id_url.field(idurl).to_bin() in id_url.to_bin_list(customers())


def is_supplier(idurl, customer_idurl=None):
    """
    Return True if given ID is found in suppliers list.
    """
    if id_url.is_empty(idurl):
        return False
    return id_url.field(idurl).to_bin() in id_url.to_bin_list(suppliers(customer_idurl=customer_idurl))


def is_correspondent(idurl):
    """
    Return True if given ID is found in correspondents list.
    """
    if id_url.is_empty(idurl):
        return False
    return id_url.field(idurl).to_bin() in id_url.to_bin_list(correspondents_ids())


#------------------------------------------------------------------------------


def num_customers():
    """
    Return current number of customers.
    """
    return len(customers())


def num_suppliers(customer_idurl=None):
    """
    Return current number of suppliers.
    """
    return len(suppliers(customer_idurl=customer_idurl))


def total_suppliers():
    global _SuppliersList
    result = set()
    for suppliers_list in _SuppliersList.values():
        result.update(set(id_url.to_bin_list(suppliers_list)))
    return len(result)


def num_correspondents():
    """
    Return current number of correspondents.
    """
    return len(correspondents())


#------------------------------------------------------------------------------


def supplier_position(idurl, customer_idurl=None):
    """
    Return position of supplier with given ID or -1.
    """
    if not idurl:
        return -1
    if not id_url.is_cached(idurl):
        return -1
    idurl = id_url.field(idurl)
    try:
        index = id_url.to_bin_list(suppliers(customer_idurl=customer_idurl)).index(idurl.to_bin())
    except:
        index = -1
    return index


def customer_position(idurl):
    """
    Return position of supplier with given ID or -1.
    """
    if not idurl:
        return -1
    if not id_url.is_cached(idurl):
        return -1
    idurl = id_url.field(idurl)
    try:
        index = id_url.to_bin_list(customers()).index(idurl.to_bin())
    except:
        index = -1
    return index


def contact_position(idurl):
    """
    Return position for given contact ID in the total list combined from
    suppliers, customers.

    Suppliers should be numbered 0 to 63 with customers after that not
    sure we can count on numbers staying.
    """
    if not idurl:
        return -1
    if not id_url.is_cached(idurl):
        return -1
    idurl = id_url.field(idurl)
    try:
        index = id_url.to_bin_list(contacts_list()).index(idurl.to_bin())
    except:
        index = -1
    return index


#-------------------------------------------------------------------------------


def save_suppliers(path=None, customer_idurl=None):
    """
    Write current suppliers list on the disk, ``path`` is a file path to save.
    """
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    customer_id = global_id.UrlToGlobalID(customer_idurl)
    if path is None:
        path = os.path.join(settings.SuppliersDir(), customer_id, 'supplierids')
    lst = suppliers(customer_idurl=customer_idurl)
    lst = list(map(strng.to_text, lst))
    if not os.path.exists(os.path.dirname(path)):
        bpio._dirs_make(os.path.dirname(path))
    bpio._write_list(path, lst)
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.save_suppliers for customer [%s]:\n%r' % (customer_id, lst))
    return True


def load_suppliers(path=None, customer_idurl=None, all_customers=False):
    """
    Load suppliers list from disk.
    """
    if all_customers:
        list_local_customers = list(os.listdir(settings.SuppliersDir()))
        if _Debug:
            lg.out(_DebugLevel, 'contactsdb.load_suppliers %d known customers' % len(list_local_customers))
        for customer_id in list_local_customers:
            if not global_id.IsValidGlobalUser(customer_id):
                lg.warn('invalid customer record %s found in %s' % (customer_id, settings.SuppliersDir()))
                continue
            path = os.path.join(settings.SuppliersDir(), customer_id, 'supplierids')
            lst = bpio._read_list(path)
            if lst is None:
                lg.warn('did not found suppliers ids at %s' % path)
                continue
            one_customer_idurl = global_id.GlobalUserToIDURL(customer_id)
            if not id_url.is_cached(one_customer_idurl):
                lg.warn('customer identity %r not cached yet' % one_customer_idurl)
                continue
            if not one_customer_idurl.is_latest():
                latest_customer_path = os.path.join(settings.SuppliersDir(), one_customer_idurl.to_id())
                old_customer_path = os.path.join(settings.SuppliersDir(), customer_id)
                if not os.path.exists(latest_customer_path):
                    os.rename(old_customer_path, latest_customer_path)
                    lg.info('detected and processed idurl rotate when loading suppliers for customer : %r -> %r' % (customer_id, one_customer_idurl.to_id()))
                else:
                    bpio._dir_remove(old_customer_path)
                    lg.warn('found old customer dir %r and removed' % old_customer_path)
                    continue
            lst = list(map(lambda i: i if id_url.is_cached(i) else b'', lst))
            set_suppliers(lst, customer_idurl=one_customer_idurl)
            if _Debug:
                lg.out(_DebugLevel, '    loaded %d known suppliers for customer %r' % (len(lst), one_customer_idurl))
        return True
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if path is None:
        path = os.path.join(settings.SuppliersDir(), global_id.UrlToGlobalID(customer_idurl), 'supplierids')
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    lst = list(map(lambda i: i if id_url.is_cached(i) else b'', lst))
    set_suppliers(lst, customer_idurl=customer_idurl)
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.load_suppliers %d items from %s' % (len(lst), path))
    return True


def cache_suppliers(path=None):
    """
    Make sure identities of all suppliers we know are cached.
    """
    dl = []
    list_local_customers = list(os.listdir(settings.SuppliersDir()))
    for customer_id in list_local_customers:
        if not global_id.IsValidGlobalUser(customer_id):
            lg.warn('invalid customer record %s found in %s' % (customer_id, settings.SuppliersDir()))
            continue
        try:
            one_customer_idurl = global_id.GlobalUserToIDURL(customer_id)
        except Exception as exc:
            lg.err('idurl caching failed: %r' % exc)
            continue
        if not id_url.is_cached(one_customer_idurl):
            dl.append(identitycache.immediatelyCaching(one_customer_idurl))
        path = os.path.join(settings.SuppliersDir(), customer_id, 'supplierids')
        lst = bpio._read_list(path)
        if lst is None:
            lg.warn('did not found suppliers ids at %s' % path)
            continue
        for one_supplier_idurl in lst:
            if one_supplier_idurl:
                if not id_url.is_cached(one_supplier_idurl):
                    dl.append(identitycache.immediatelyCaching(one_supplier_idurl))
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.cache_suppliers prepared %d idurls to be cached' % len(dl))
    return DeferredList(dl, consumeErrors=True)


#------------------------------------------------------------------------------


def save_customers(path=None, save_meta_info=False):
    """
    Write current customers list on the disk, ``path`` is a file path to save.
    """
    global _CustomersMetaInfo
    if path is None:
        path = settings.CustomerIDsFilename()
    lst = customers()
    lst = list(map(strng.to_text, lst))
    bpio._write_list(path, lst)
    if save_meta_info:
        json_info = id_url.to_bin_dict(_CustomersMetaInfo)
        local_fs.WriteTextFile(settings.CustomersMetaInfoFilename(), jsn.dumps(
            json_info,
            indent=2,
            sort_keys=True,
            keys_to_text=True,
        ))
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.save_customers save_meta_info=%r : %r' % (save_meta_info, lst))


def load_customers(path=None):
    """
    Load customers list from disk.
    """
    global _CustomersMetaInfo
    if path is None:
        path = settings.CustomerIDsFilename()
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    lst = list(filter(id_url.is_cached, lst))
    set_customers(lst)
    _CustomersMetaInfo = jsn.loads(
        local_fs.ReadTextFile(settings.CustomersMetaInfoFilename()) or '{}',
        keys_to_bin=True,
    )
    _CustomersMetaInfo = id_url.to_bin_dict(_CustomersMetaInfo)
    _CustomersMetaInfo = jsn.dict_values_to_text(_CustomersMetaInfo)
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.load_customers %d items' % len(lst))


def cache_customers(path=None):
    """
    Make sure identities of all customers we know are cached.
    """
    dl = []
    if path is None:
        path = settings.CustomerIDsFilename()
    lst = bpio._read_list(path) or []
    for one_customer_idurl in lst:
        if one_customer_idurl:
            if not id_url.is_cached(one_customer_idurl):
                dl.append(identitycache.immediatelyCaching(one_customer_idurl))
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.cache_customers prepared %d idurls to be cached' % len(dl))
    return DeferredList(dl, consumeErrors=True)


#------------------------------------------------------------------------------


def save_correspondents(path=None):
    """
    Write current correspondents list on the disk, ``path`` is a file path to
    save.
    """
    if path is None:
        path = settings.CorrespondentIDsFilename()
    lst = ['%s %s' % (
        strng.to_text(t[0]),
        strng.to_text(t[1]),
    ) for t in correspondents()]
    bpio._write_list(path, lst)


def load_correspondents(path=None):
    """
    Load correspondents list from disk.
    """
    if path is None:
        path = settings.CorrespondentIDsFilename()
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    for i in range(len(lst)):
        lst[i] = tuple(lst[i].strip().split(' ', 1))
        if len(lst[i]) < 2:
            lst[i] = (lst[i][0], '')
        if not lst[i][1].strip():
            lst[i] = (id_url.field(lst[i][0]), nameurl.GetName(lst[i][0]))
    lst = list(filter(lambda i: id_url.is_cached(i[0]), lst))
    set_correspondents(lst)
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.load_correspondents %d items' % len(lst))


def cache_correspondents(path=None):
    """
    Make sure identities of all correspondents we know are cached.
    """
    dl = []
    if path is None:
        path = settings.CorrespondentIDsFilename()
    lst = bpio._read_list(path) or []
    for i in range(len(lst)):
        try:
            one_correspondent_idurl = lst[i].strip().split(' ', 1)[0]
        except:
            lg.exc()
            continue
        if one_correspondent_idurl:
            if not id_url.is_cached(one_correspondent_idurl):
                dl.append(identitycache.immediatelyCaching(one_correspondent_idurl))
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.cache_correspondents prepared %d idurls to be cached' % len(dl))
    return DeferredList(dl, consumeErrors=True)


#------------------------------------------------------------------------------


def cache_contacts(
    suppliers_path=None,
    customers_path=None,
    correspondents_path=None,
):
    """
    Make sure identities of all my known contacts are cached.
    """
    dl = []
    dl.append(cache_suppliers(suppliers_path))
    dl.append(cache_customers(customers_path))
    dl.append(cache_correspondents(correspondents_path))
    return DeferredList(dl, consumeErrors=True)


def load_contacts():
    """
    Load all my contacts from disk.
    """
    load_suppliers(all_customers=True)
    if _SuppliersChangedCallback is not None:
        _SuppliersChangedCallback([], suppliers())
    load_customers()
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback([], customers())
    load_correspondents()
    if _CorrespondentsChangedCallback is not None:
        _CorrespondentsChangedCallback([], correspondents())
    AddContactsChangedCallback(on_contacts_changed)
    if listeners.is_populate_required('correspondent'):
        # listeners.populate_later().remove('correspondent')
        populate_correspondents()


#------------------------------------------------------------------------------


def get_contact_identity(idurl):
    """
    The Main Method Here - return identity object for given ID or None if not found.
    Only valid contacts for packets will be signed by local identity, suppliers, customers.
    """
    if idurl is None:
        return None
    idurl = id_url.field(idurl)
    if idurl.to_bin() == my_id.getIDURL().to_bin():
        return my_id.getLocalIdentity()


#     if is_supplier(idurl):
#         return identitycache.FromCache(idurl)
#     if is_customer(idurl):
#         return identitycache.FromCache(idurl)
#     if is_correspondent(idurl):
#         return identitycache.FromCache(idurl)
    if identitycache.HasKey(idurl):
        # lg.warn("who is %s ?" % nameurl.GetName(idurl))
        return identitycache.FromCache(idurl)
    lg.warn('%s is NOT FOUND IN CACHE' % idurl)
    # TODO:
    # this is not correct:
    # need to check if other contacts is fine - if internet is turned off we can get lots of fails ...
    return None


def get_customer_identity(idurl):
    """
    If ``idurl`` is in customers list, return its identity object.
    """
    if is_customer(idurl):
        idurl = id_url.field(idurl)
        return identitycache.FromCache(idurl)
    return None


def get_supplier_identity(idurl):
    """
    Return peer's identity if he is in suppliers list.
    """
    if is_supplier(idurl):
        idurl = id_url.field(idurl)
        return identitycache.FromCache(idurl)
    return None


def get_correspondent_identity(idurl):
    """
    Return peer's identity if he is in the correspondents list.
    """
    if is_correspondent(idurl):
        idurl = id_url.field(idurl)
        return identitycache.FromCache(idurl)
    return None


def get_correspondent_nickname(correspondent_idurl):
    for idurl, nickname in correspondents():
        if id_url.field(idurl).to_bin() == id_url.field(correspondent_idurl).to_bin():
            return nickname
    return None


def find_correspondent_by_nickname(nickname):
    for idurl, corr_nickname in correspondents_dict().items():
        if nickname == corr_nickname:
            return idurl
    return None


#------------------------------------------------------------------------------


def on_contacts_changed(old_contacts_list, new_contacts_list):
    from bitdust.main import events
    events.send('contacts-changed', data=dict(
        old_contacts=old_contacts_list,
        new_contacts=new_contacts_list,
    ))


#------------------------------------------------------------------------------


def read_customers_meta_info_all():
    global _CustomersMetaInfo
    return _CustomersMetaInfo


def write_customers_meta_info_all(new_customers_info):
    global _CustomersMetaInfo
    _CustomersMetaInfo = new_customers_info
    json_info = {k: jsn.dict_keys_to_text(v) for k, v in id_url.to_bin_dict(_CustomersMetaInfo).items()}
    try:
        raw_data = jsn.dumps(
            json_info,
            indent=2,
            sort_keys=True,
            keys_to_text=True,
            values_to_text=True,
        )
    except:
        lg.exc()
        return None
    local_fs.WriteTextFile(settings.CustomersMetaInfoFilename(), raw_data)
    return _CustomersMetaInfo


def add_customer_meta_info(customer_idurl, info):
    global _CustomersMetaInfo
    customer_idurl = id_url.field(customer_idurl)
    if not customer_idurl.is_latest():
        if customer_idurl.original() in _CustomersMetaInfo:
            if customer_idurl.to_bin() not in _CustomersMetaInfo:
                _CustomersMetaInfo[customer_idurl.to_bin()] = _CustomersMetaInfo.pop(customer_idurl.original())
                lg.info('detected and processed idurl rotate for customer meta info : %r -> %r' % (customer_idurl.original(), customer_idurl.to_bin()))
    customer_idurl = id_url.to_bin(customer_idurl)
    if 'family_snapshot' in info:
        info['family_snapshot'] = id_url.to_bin_list(info['family_snapshot'])
    if 'ecc_map' in info:
        info['ecc_map'] = strng.to_text(info['ecc_map'])
    if customer_idurl not in _CustomersMetaInfo:
        if _Debug:
            lg.out(_DebugLevel, 'contactsdb.add_customer_meta_info   store new meta info for customer %r: %r' % (customer_idurl, info))
        _CustomersMetaInfo[customer_idurl] = {}
    else:
        if _Debug:
            lg.out(_DebugLevel, 'contactsdb.add_customer_meta_info   update existing meta info for customer %r: %r' % (customer_idurl, info))
        _CustomersMetaInfo[customer_idurl].update(info)
    json_info = {k: jsn.dict_keys_to_text(v) for k, v in id_url.to_bin_dict(_CustomersMetaInfo).items()}
    try:
        raw_data = jsn.dumps(
            json_info,
            indent=2,
            sort_keys=True,
            keys_to_text=True,
            values_to_text=True,
        )
    except:
        lg.exc()
        return None
    local_fs.WriteTextFile(settings.CustomersMetaInfoFilename(), raw_data)
    return _CustomersMetaInfo


def remove_customer_meta_info(customer_idurl):
    global _CustomersMetaInfo
    customer_idurl = id_url.field(customer_idurl)
    if not customer_idurl.is_latest():
        if customer_idurl.original() in _CustomersMetaInfo:
            if customer_idurl.to_bin() not in _CustomersMetaInfo:
                _CustomersMetaInfo[customer_idurl.to_bin()] = _CustomersMetaInfo.pop(customer_idurl.original())
                lg.info('detected and processed idurl rotate for customer meta info : %r -> %r' % (customer_idurl.original(), customer_idurl.to_bin()))
    customer_idurl = id_url.to_bin(customer_idurl)
    if customer_idurl not in _CustomersMetaInfo:
        lg.warn('meta info for customer %r not exist' % customer_idurl)
        return False
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.remove_customer_meta_info   erase existing meta info for customer %r' % customer_idurl)
    _CustomersMetaInfo.pop(customer_idurl)
    json_info = {k: jsn.dict_keys_to_text(v) for k, v in id_url.to_bin_dict(_CustomersMetaInfo).items()}
    local_fs.WriteTextFile(settings.CustomersMetaInfoFilename(), jsn.dumps(
        json_info,
        indent=2,
        sort_keys=True,
        keys_to_text=True,
        values_to_text=True,
    ))
    return True


def get_customer_meta_info(customer_idurl):
    global _CustomersMetaInfo
    customer_idurl = id_url.field(customer_idurl)
    if not customer_idurl.is_latest():
        if customer_idurl.original() in _CustomersMetaInfo:
            if customer_idurl.to_bin() not in _CustomersMetaInfo:
                _CustomersMetaInfo[customer_idurl.to_bin()] = _CustomersMetaInfo.pop(customer_idurl.original())
                lg.info('detected and processed idurl rotate for customer meta info : %r -> %r' % (customer_idurl.original(), customer_idurl.to_bin()))
    customer_idurl = id_url.to_bin(customer_idurl)
    return jsn.dict_keys_to_text(jsn.dict_values_to_text(_CustomersMetaInfo.get(customer_idurl, {})))


#------------------------------------------------------------------------------


def add_supplier_meta_info(supplier_idurl, info, customer_idurl=None):
    global _SuppliersMetaInfo
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    supplier_idurl = id_url.field(supplier_idurl)
    if customer_idurl not in _SuppliersMetaInfo:
        _SuppliersMetaInfo[customer_idurl] = {}
    if supplier_idurl not in _SuppliersMetaInfo[customer_idurl]:
        _SuppliersMetaInfo[customer_idurl][supplier_idurl] = {}
    _SuppliersMetaInfo[customer_idurl][supplier_idurl].update(info)
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.add_supplier_meta_info   for supplier %s of customer %s: %s' % (supplier_idurl, customer_idurl, _SuppliersMetaInfo[customer_idurl][supplier_idurl]))


def remove_supplier_meta_info(supplier_idurl, customer_idurl=None):
    global _SuppliersMetaInfo
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    supplier_idurl = id_url.field(supplier_idurl)
    if customer_idurl not in _SuppliersMetaInfo:
        return False
    if supplier_idurl not in _SuppliersMetaInfo[customer_idurl]:
        return False
    _SuppliersMetaInfo[customer_idurl].pop(supplier_idurl)
    if len(_SuppliersMetaInfo[customer_idurl]) == 0:
        _SuppliersMetaInfo.pop(customer_idurl)
    return True


def get_supplier_meta_info(supplier_idurl, customer_idurl=None):
    global _SuppliersMetaInfo
    if not customer_idurl:
        customer_idurl = my_id.getIDURL()
    if not id_url.is_cached(customer_idurl) or not id_url.is_cached(supplier_idurl):
        return {}
    customer_idurl = id_url.field(customer_idurl)
    supplier_idurl = id_url.field(supplier_idurl)
    return jsn.dict_keys_to_text(jsn.dict_values_to_text(_SuppliersMetaInfo.get(customer_idurl, {}).get(supplier_idurl, {})))


#------------------------------------------------------------------------------


def SetSuppliersChangedCallback(cb):
    """
    Set callback to fire when suppliers is changed.
    """
    global _SuppliersChangedCallback
    _SuppliersChangedCallback = cb


def SetCustomersChangedCallback(cb):
    """
    Set callback to fire when customers is changed.
    """
    global _CustomersChangedCallback
    _CustomersChangedCallback = cb


def SetCorrespondentsChangedCallback(cb):
    """
    Set callback to fire when correspondents is changed.
    """
    global _CorrespondentsChangedCallback
    _CorrespondentsChangedCallback = cb


def AddContactsChangedCallback(cb):
    """
    Set callback to fire when any contact were changed.
    """
    global _ContactsChangedCallbacks
    _ContactsChangedCallbacks.append(cb)


def RemoveContactsChangedCallback(cb):
    """
    Set callback to fire when any contact were changed.
    """
    global _ContactsChangedCallbacks
    if cb in _ContactsChangedCallbacks:
        _ContactsChangedCallbacks.remove(cb)
