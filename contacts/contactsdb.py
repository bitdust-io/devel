#!/usr/bin/python
#py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: contactsdb

A low level methods to store list of contacts locally.:
    - suppliers
    - customers
    - correspondents
"""

from logs import lg

from lib import nameurl

from system import bpio

from main import settings

from userid import my_id

import identitycache

#-------------------------------------------------------------------------------

_CustomersList = []      # comes from settings.CustomerIDsFilename() 
_SuppliersList = []      # comes from settings.SupplierIDsFilename()  
_CorrespondentsList = []   # comes from settings.CorrespondentIDsFilename()
_CorrespondentsDict = {}

_SuppliersChangedCallback = None
_CustomersChangedCallback = None
_ContactsChangedCallback = None
_CorrespondentsChangedCallback = None

#-------------------------------------------------------------------------------

def init():
    """
    We read from disk and if we have all the info we are set.
    If we don't have enough, then we have to ask BitDust to list contacts and use
    that list to get and then store all the identities for our contacts.
    """
    global _SuppliersChangedCallback
    global _CustomersChangedCallback
    global _CorrespondentsChangedCallback
    lg.out(4, "contactsdb.init")
    load_suppliers(settings.SupplierIDsFilename())
    if _SuppliersChangedCallback is not None:
        _SuppliersChangedCallback([], suppliers())
    load_customers(settings.CustomerIDsFilename())
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback([], customers())
    load_correspondents(settings.CorrespondentIDsFilename())
    if _CorrespondentsChangedCallback is not None:
        _CorrespondentsChangedCallback([], correspondents())
        

def shutdown():
    """
    """
    global _SuppliersChangedCallback
    global _CustomersChangedCallback
    lg.out(4, "contactsdb.shutdown")
    if _SuppliersChangedCallback is not None:
        _SuppliersChangedCallback = None
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback = None
    
#------------------------------------------------------------------------------ 

def suppliers():
    """
    Return list of suppliers ID's.
    """
    global _SuppliersList
    return _SuppliersList

def customers():
    """
    Return list of customers ID's.
    """
    global _CustomersList
    return _CustomersList

def contacts():
    """
    Return a union of suppliers and customers ID's. 
    """
    return list(set(suppliers()+customers()))

def contacts_list():
    """
    Return a list of suppliers and customers ID's. 
    """
    return list(suppliers()+customers())

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

def set_suppliers(idlist):
    """
    Set suppliers ID's list.
    """
    global _SuppliersList
    _SuppliersList = map(lambda idurl: idurl.strip(), idlist)

def set_customers(idlist):
    """
    Set customers list.
    """
    global _CustomersList
    _CustomersList = map(lambda idurl: idurl.strip(), idlist)

def add_customer(idurl):
    """
    Add customer and return its position in the list.
    """
    global _CustomersList
    _CustomersList.append(idurl)
    return len(_CustomersList) - 1

def add_supplier(idurl):
    """
    Add supplier and return its position in the list.
    """
    global _SuppliersList
    _SuppliersList.append(idurl)
    return len(_SuppliersList) - 1

def clear_suppliers():
    """
    Remove all suppliers.
    """
    global _SuppliersList
    _SuppliersList = [] 

def clear_customers():
    """
    Remove all customers.
    """
    global _CustomersList
    _CustomersList = []

#------------------------------------------------------------------------------ 

def update_suppliers(idslist):
    """
    Set suppliers ID's list, called from fire_hire() machine basically.
    """
    global _SuppliersChangedCallback
    global _ContactsChangedCallback
    oldsuppliers = suppliers()
    oldcontacts = contacts()
    set_suppliers(idslist)
    if _SuppliersChangedCallback is not None:
        _SuppliersChangedCallback(oldsuppliers, suppliers())
    if _ContactsChangedCallback is not None:
        _ContactsChangedCallback(oldcontacts, contacts())

def update_customers(idslist):
    """
    Set customers ID's list.
    """
    global _CustomersChangedCallback
    global _ContactsChangedCallback
    oldcustomers = customers()
    oldcontacts = contacts()
    set_customers(idslist)
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback(oldcustomers, customers())
    if _ContactsChangedCallback is not None:
        _ContactsChangedCallback(oldcontacts, contacts())


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
    return map(lambda tupl: tupl[0], _CorrespondentsList) 


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
    Add correspondent,
    execute notification callback
    and return its position in the list.
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
    Remove correspondent with given IDURL,
    execute notification callback
    and return True if success.
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

def is_supplier(idurl):
    """
    Return True if given ID is found in suppliers list. 
    """
    return idurl and idurl in suppliers()

def is_correspondent(idurl):
    """
    Return True if given ID is found in correspondents list. 
    """
    return idurl in correspondents_ids()

def num_customers():
    """
    Return current number of customers.
    """
    return len(customers())

def num_suppliers():
    """
    Return current number of suppliers.
    """
    return len(suppliers())

def supplier(index):
    """
    Return supplier ID on given position or empty string.
    """
    num = int(index)
    if num>=0 and num < len(suppliers()):
        return suppliers()[num]
    return ''

def customer(index):
    """
    Return customer ID on given position or empty string.
    """
    num = int(index)
    if num>=0 and num < len(customers()):
        return customers()[num]
    return ''

def supplier_position(idurl):
    """
    Return position of supplier with given ID or -1.
    """
    if not idurl:
        return -1
    try:
        index = suppliers().index(idurl)
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
    Return position for given contact ID in the total list combined from suppliers, customers.
    Suppliers should be numbered 0 to 63 with customers after that not sure we can count on numbers staying.
    """
    if not idurl:
        return -1
    try:
        index = contacts_list().index(idurl)
    except:
        index = -1
    return index

#-------------------------------------------------------------------------------

def save_suppliers(path=None):
    """
    Write current suppliers list on the disk, ``path`` is a file path to save.
    """
    if path is None:
        path = settings.SupplierIDsFilename()
    bpio._write_list(path, suppliers())

def save_customers(path=None):
    """
    Write current customers list on the disk, ``path`` is a file path to save.
    """
    if path is None:
        path = settings.CustomerIDsFilename() 
    bpio._write_list(path, customers())
    
def save_correspondents(path=None):
    """
    Write current correspondents list on the disk, ``path`` is a file path to save.
    """
    if path is None:
        path = settings.CorrespondentIDsFilename()
    bpio._write_list(path, map(lambda t: "%s %s" % t, correspondents()))

def load_suppliers(path):
    """
    Load suppliers list from disk.
    """
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    set_suppliers(lst)
    lg.out(4, 'contactsdb.load_suppliers %d items' % len(lst))

def load_customers(path):
    """
    Load customers list from disk.
    """
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    set_customers(lst)
    lg.out(4, 'contactsdb.load_customers %d items' % len(lst))

def load_correspondents(path):
    """
    Load correspondents list from disk.
    """
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    for i in xrange(len(lst)):
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
    lg.out(6, "contactsdb.getContact %s is not found" % nameurl.GetName(idurl))
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

def SetSuppliersChangedCallback(cb):
    """
    Set callback to fire when suppliers is changed 
    """
    global _SuppliersChangedCallback
    _SuppliersChangedCallback = cb

def SetCustomersChangedCallback(cb):
    """
    Set callback to fire when customers is changed 
    """
    global _CustomersChangedCallback
    _CustomersChangedCallback = cb

def SetContactsChangedCallback(cb):
    """
    Set callback to fire when any contact were changed 
    """
    global _ContactsChangedCallback
    _ContactsChangedCallback = cb

def SetCorrespondentsChangedCallback(cb):
    """
    Set callback to fire when correspondents is changed 
    """
    global _CorrespondentsChangedCallback
    _CorrespondentsChangedCallback = cb



