#!/usr/bin/python
# contactsdb.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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
from six.moves import range
_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from logs import lg

from lib import nameurl

from system import bpio

from main import settings

from userid import my_id
from userid import global_id

from contacts import identitycache

#-------------------------------------------------------------------------------

_CustomersList = []      # comes from settings.CustomerIDsFilename()
_SuppliersList = {}      # comes from settings.SupplierIDsFilename()
_CorrespondentsList = []   # comes from settings.CorrespondentIDsFilename()
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
    lg.out(4, "contactsdb.init")
    load_suppliers()
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


def shutdown():
    """
    """
    global _SuppliersChangedCallback
    global _CustomersChangedCallback
    lg.out(4, "contactsdb.shutdown")
    RemoveContactsChangedCallback(on_contacts_changed)
    if _SuppliersChangedCallback is not None:
        _SuppliersChangedCallback = None
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback = None

#------------------------------------------------------------------------------

def suppliers(customer_idurl=None):
    """
    Return list of suppliers ID's for given customer.
    """
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _SuppliersList:
        _SuppliersList[customer_idurl] = []
    return _SuppliersList[customer_idurl]


def supplier(index, customer_idurl=None):
    """
    Return supplier ID on given position or empty string.
    """
    num = int(index)
    if num >= 0 and num < len(suppliers(customer_idurl=customer_idurl)):
        return suppliers(customer_idurl=customer_idurl)[num]
    return ''


def all_suppliers():
    """
    """
    global _SuppliersList
    result = []
    for suppliers_list in _SuppliersList.values():
        for supplier_idurl in suppliers_list:
            if supplier_idurl not in result:
                result.append(supplier_idurl)
    return result


def set_suppliers(idlist, customer_idurl=None):
    """
    Set suppliers ID's list.
    """
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _SuppliersList:
        _SuppliersList[customer_idurl] = []
    _SuppliersList[customer_idurl] = [idurl.strip() for idurl in idlist]


def update_suppliers(idslist, customer_idurl=None):
    """
    High-level method to set suppliers ID's list.
    Executes required callbacks.
    """
    global _SuppliersChangedCallback
    global _ContactsChangedCallbacks
    oldsuppliers = suppliers(customer_idurl=customer_idurl)
    oldcontacts = contacts()
    set_suppliers(idslist, customer_idurl=customer_idurl)
    if _SuppliersChangedCallback is not None:
        _SuppliersChangedCallback(oldsuppliers, suppliers(customer_idurl=customer_idurl))
    for cb in _ContactsChangedCallbacks:
        cb(oldcontacts, contacts())


def add_supplier(idurl, position=None, customer_idurl=None):
    """
    Add supplier in my list of suppliers or to the list stored for another customer.
    If parameter `position` is provided, supplier will be inserted instead of added.
    If position is greater than current list - empty strings will be filled in between.
    """
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _SuppliersList:
        _SuppliersList[customer_idurl] = []
    if position is None:
        _SuppliersList[customer_idurl].append(idurl)
        return len(_SuppliersList[customer_idurl]) - 1
    current_suppliers = _SuppliersList[customer_idurl]
    if position >= len(current_suppliers):
        current_suppliers += ['', ] * (1 + position - len(current_suppliers))
    if current_suppliers[position] and current_suppliers[position] != idurl:
        lg.warn('replacing known supplier %s by %s at position %d for customer %s' % (
            current_suppliers[position], idurl, position, customer_idurl))
    current_suppliers[position] = idurl
    _SuppliersList[customer_idurl] = current_suppliers
    return position


def erase_supplier(idurl=None, position=None, customer_idurl=None):
    """
    """
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _SuppliersList:
        return False
    current_suppliers = _SuppliersList[customer_idurl]
    if idurl:
        if idurl not in current_suppliers:
            return False
        current_suppliers[current_suppliers.index(idurl)] = ''
    elif position is not None:
        if position >= len(current_suppliers):
            return False
        current_suppliers[position] = ''
    else:
        return False
    _SuppliersList[customer_idurl] = current_suppliers
    return True


def clear_suppliers(customer_idurl=None):
    """
    Remove all suppliers for given customer, if customer_idurl is None will erase all my suppliers.
    """
    global _SuppliersList
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    _SuppliersList.pop(customer_idurl)


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
    return ''


def set_customers(idlist):
    """
    Set customers list.
    """
    global _CustomersList
    _CustomersList = [idurl.strip() for idurl in idlist]


def update_customers(idslist):
    """
    Hight-level method to set customers ID's list.
    Executes required callbacks.
    """
    global _CustomersChangedCallback
    global _ContactsChangedCallbacks
    oldcustomers = customers()
    oldcontacts = contacts()
    set_customers(idslist)
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback(oldcustomers, customers())
    for cb in _ContactsChangedCallbacks:
        cb(oldcontacts, contacts())


def add_customer(idurl):
    """
    Add customer and return its position in the list.
    """
    global _CustomersList
    _CustomersList.append(idurl)
    return len(_CustomersList) - 1


def clear_customers():
    """
    Remove all customers.
    """
    global _CustomersList
    _CustomersList = []


#------------------------------------------------------------------------------

def contacts(include_all=False):
    """
    Return a union of suppliers and customers ID's.
    """
    result = set(suppliers() + customers())
    if include_all:
        result.intersection_update(correspondents())
    return list(result)


def contacts_list():
    """
    Return a list of suppliers and customers ID's.
    """
    return list(suppliers() + customers())


def contacts_full():
    """
    Return a union of suppliers, customers and correspondents.
    """
    return list(set(contacts() + correspondents_ids()))


def contacts_remote():
    """
    Return ID's list of all known peers.
    """
    allcontactslist = contacts_full()
    if my_id.getLocalID() in allcontactslist:
        allcontactslist.remove(my_id.getLocalID())
    return allcontactslist

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
    _CorrespondentsList = list(idlist)


def clear_correspondents():
    """
    Remove all correspondents without notification.
    """
    global _CorrespondentsList
    _CorrespondentsList = []


def add_correspondent(idurl, nickname=''):
    """
    Add correspondent, execute notification callback and return its position in
    the list.
    """
    global _CorrespondentsList
    global _CorrespondentsChangedCallback
    curlist = _CorrespondentsList
    _CorrespondentsList.append((idurl, nickname))
    if _CorrespondentsChangedCallback is not None:
        _CorrespondentsChangedCallback(curlist, _CorrespondentsList)
    return len(curlist)


def remove_correspondent(idurl):
    """
    Remove correspondent with given IDURL, execute notification callback and
    return True if success.
    """
    global _CorrespondentsList
    global _CorrespondentsChangedCallback
    curlist = _CorrespondentsList
    for tupl in _CorrespondentsList:
        if idurl == tupl[0]:
            _CorrespondentsList.remove(tupl)
            if _CorrespondentsChangedCallback is not None:
                _CorrespondentsChangedCallback(curlist, _CorrespondentsList)
            return True
    return False


def update_correspondents(idslist):
    """
    Set correspondents ID's list.
    """
    global _CorrespondentsChangedCallback
    oldcorrespondents = correspondents()
    set_correspondents(idslist)
    if _CorrespondentsChangedCallback is not None:
        _CorrespondentsChangedCallback(oldcorrespondents, correspondents())

#-------------------------------------------------------------------------------


def is_customer(idurl):
    """
    Return True if given ID is found in customers list.
    """
    return idurl in customers()


def is_supplier(idurl, customer_idurl=None):
    """
    Return True if given ID is found in suppliers list.
    """
    return idurl and idurl in suppliers(customer_idurl=customer_idurl)


def is_correspondent(idurl):
    """
    Return True if given ID is found in correspondents list.
    """
    return idurl in correspondents_ids()

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
    """
    """
    global _SuppliersList
    result = set()
    for suppliers_list in _SuppliersList.values():
        result.update(set(suppliers_list))
    return len(result)

#------------------------------------------------------------------------------

def supplier_position(idurl, customer_idurl=None):
    """
    Return position of supplier with given ID or -1.
    """
    if not idurl:
        return -1
    try:
        index = suppliers(customer_idurl=customer_idurl).index(idurl)
    except:
        index = -1
    return index


def customer_position(idurl):
    """
    Return position of supplier with given ID or -1.
    """
    if not idurl:
        return -1
    try:
        index = customers().index(idurl)
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
    try:
        index = contacts_list().index(idurl)
    except:
        index = -1
    return index

#-------------------------------------------------------------------------------

def save_suppliers(path=None, customer_idurl=None):
    """
    Write current suppliers list on the disk, ``path`` is a file path to save.
    """
    if path is None:
        if customer_idurl is None:
            path = settings.SupplierIDsFilename()
        else:
            path = os.path.join(
                settings.SuppliersDir(),
                global_id.UrlToGlobalID(customer_idurl),
                'supplierids',
            )
    bpio._write_list(path, suppliers(customer_idurl=customer_idurl))
    return True

def load_suppliers(path=None, customer_idurl=None, all_customers=False):
    """
    Load suppliers list from disk.
    """
    if all_customers:
        for customer_id in os.listdir(settings.SuppliersDir()):
            if not global_id.IsValidGlobalUser(customer_id):
                lg.warn('invalid customer record %s found in %s' % (customer_id, settings.SuppliersDir()))
                continue
            path = os.path.join(settings.SuppliersDir(), customer_id, 'supplierids')
            lst = bpio._read_list(path)
            if lst is None:
                lst = list()
            set_suppliers(lst, customer_idurl=global_id.GlobalUserToIDURL(customer_id))
            lg.out(4, 'contactsdb.load_suppliers %d items from %s' % (len(lst), path))
        return True
    if path is None:
        if customer_idurl is None:
            path = settings.SupplierIDsFilename()
        else:
            path = os.path.join(settings.SuppliersDir(), global_id.UrlToGlobalID(customer_idurl), 'supplierids')
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    set_suppliers(lst)
    lg.out(4, 'contactsdb.load_suppliers %d items from %s' % (len(lst), path))
    return True
                

#------------------------------------------------------------------------------

def save_customers(path=None):
    """
    Write current customers list on the disk, ``path`` is a file path to save.
    """
    if path is None:
        path = settings.CustomerIDsFilename()
    bpio._write_list(path, customers())


def load_customers(path=None):
    """
    Load customers list from disk.
    """
    if path is None:
        path = settings.CustomerIDsFilename()
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    set_customers(lst)
    lg.out(4, 'contactsdb.load_customers %d items' % len(lst))

#------------------------------------------------------------------------------

def save_correspondents(path=None):
    """
    Write current correspondents list on the disk, ``path`` is a file path to
    save.
    """
    if path is None:
        path = settings.CorrespondentIDsFilename()
    bpio._write_list(path, ["%s %s" % t for t in correspondents()])


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
        if lst[i][1].strip() == '':
            lst[i] = (lst[i][0], nameurl.GetName(lst[i][0]))
    set_correspondents(lst)
    lg.out(4, 'contactsdb.load_correspondents %d items' % len(lst))

#------------------------------------------------------------------------------


def get_contact_identity(idurl):
    """
    The Main Method Here - return identity object for given ID or None if not found.
    Only valid contacts for packets will be signed by local identity, suppliers, customers.
    """
    if idurl is None:
        return None
    if idurl == my_id.getLocalID():
        return my_id.getLocalIdentity()
    if is_supplier(idurl):
        return identitycache.FromCache(idurl)
    if is_customer(idurl):
        return identitycache.FromCache(idurl)
    if is_correspondent(idurl):
        return identitycache.FromCache(idurl)
    if identitycache.HasKey(idurl):
        # lg.warn("who is %s ?" % nameurl.GetName(idurl))
        return identitycache.FromCache(idurl)
    lg.warn("%s is NOT FOUND IN CACHE" % idurl)
    # TODO:
    # this is not correct:
    # need to check if other contacts is fine - if internet is turned off we can get lots fails ...
    return None


def get_customer_identity(idurl):
    """
    If ``idurl`` is in customers list, return its identity object.
    """
    if is_customer(idurl):
        return identitycache.FromCache(idurl)
    return None


def get_supplier_identity(idurl):
    """
    Return peer's identity if he is in suppliers list.
    """
    if is_supplier(idurl):
        return identitycache.FromCache(idurl)
    return None


def get_correspondent_identity(idurl):
    """
    Return peer's identity if he is in the correspondents list.
    """
    if is_correspondent(idurl):
        return identitycache.FromCache(idurl)
    return ''


def get_correspondent_nickname(correspondent_idurl):
    """
    """
    for idurl, nickname in correspondents():
        if idurl == correspondent_idurl:
            return nickname
    return ''


def find_correspondent_by_nickname(nickname):
    for idurl, corr_nickname in correspondents_dict().items():
        if nickname == corr_nickname:
            return idurl
    return ''

#------------------------------------------------------------------------------

def on_contacts_changed(old_contacts_list, new_contacts_list):
    from main import events
    events.send('contacts-changed', data=dict(old_contacts=old_contacts_list, new_contacts=new_contacts_list))

#------------------------------------------------------------------------------

def add_customer_meta_info(customer_idurl, info):
    """
    """
    global _CustomersMetaInfo
    if customer_idurl not in _CustomersMetaInfo:
        _CustomersMetaInfo[customer_idurl] = {}
    _CustomersMetaInfo[customer_idurl].update(info)


def remove_customer_meta_info(customer_idurl):
    """
    """
    global _CustomersMetaInfo
    if customer_idurl not in _CustomersMetaInfo:
        return False
    _CustomersMetaInfo.pop(customer_idurl)
    return True


def get_customer_meta_info(customer_idurl):
    """
    """
    global _CustomersMetaInfo
    return _CustomersMetaInfo.get(customer_idurl, {})

#------------------------------------------------------------------------------

def add_supplier_meta_info(supplier_idurl, info, customer_idurl=None):
    """
    """
    global _SuppliersMetaInfo
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _SuppliersMetaInfo:
        _SuppliersMetaInfo[customer_idurl] = {}
    if supplier_idurl not in _SuppliersMetaInfo[customer_idurl]:
        _SuppliersMetaInfo[customer_idurl][supplier_idurl] = {}
    _SuppliersMetaInfo[customer_idurl][supplier_idurl].update(info)
    if _Debug:
        lg.out(_DebugLevel, 'contactsdb.add_supplier_meta_info   for supplier %s of customer %s: %s' % (
            supplier_idurl, customer_idurl, _SuppliersMetaInfo[customer_idurl][supplier_idurl]))


def remove_supplier_meta_info(supplier_idurl, customer_idurl=None):
    """
    """
    global _SuppliersMetaInfo
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _SuppliersMetaInfo:
        return False
    if supplier_idurl not in _SuppliersMetaInfo[customer_idurl]:
        return False
    _SuppliersMetaInfo[customer_idurl].pop(customer_idurl)
    if len(_SuppliersMetaInfo[customer_idurl]) == 0:
        _SuppliersMetaInfo.pop(customer_idurl)
    return True


def get_supplier_meta_info(supplier_idurl, customer_idurl=None):
    """
    """
    global _SuppliersMetaInfo
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    return _SuppliersMetaInfo.get(customer_idurl, {}).get(supplier_idurl, {})

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

    on_contacts_changed(old_contacts_list, new_contacts_list)
    """
    global _ContactsChangedCallbacks
    _ContactsChangedCallbacks.append(cb)


def RemoveContactsChangedCallback(cb):
    """
    Set callback to fire when any contact were changed.
    """
    global _ContactsChangedCallbacks
    _ContactsChangedCallbacks.remove(cb)
