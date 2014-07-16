#!/usr/bin/python
#contactsdb.py
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
Suppliers and customers comes from Central server,
list of correspondents are managed by user and also can be stored on Central server (not done yet). 
"""

import bpio

#-------------------------------------------------------------------------------

_customerids = []      # comes from settings.CustomerIDsFilename() 
_supplierids = []      # comes from settings.SupplierIDsFilename()  
_correspondentids = [] # comes from settings.CorrespondentIDsFilename()

#-------------------------------------------------------------------------------

def suppliers():
    """
    Return list of suppliers ID's.
    """
    global _supplierids
    return _supplierids

def customers():
    """
    Return list of customers ID's.
    """
    global _customerids
    return _customerids

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

def correspondents():
    """
    Return list of correspondent ID's.
    """
    global _correspondentids
    return _correspondentids

def contacts_full():
    """
    Return a union of suppliers, customers and correspondents. 
    """
    return list(set(contacts() + correspondents()))

def set_suppliers(idlist):
    """
    Set suppliers ID's list.
    """
    global _supplierids
    _supplierids = []
    for idurl in idlist:
        _supplierids.append(idurl.strip())

def set_customers(idlist):
    """
    Set customers list.
    """
    global _customerids
    _customerids = []
    for idurl in idlist:
        _customerids.append(idurl.strip())

def set_correspondents(idlist):
    """
    Set correspondents list.
    """
    global _correspondentids
    _correspondentids = list(idlist)

def add_customer(idurl):
    """
    Add customer and return its position in the list.
    """
    global _customerids
    _customerids.append(idurl)
    return len(_customerids) - 1

def add_supplier(idurl):
    """
    Add supplier and return its position in the list.
    """
    global _supplierids
    _supplierids.append(idurl)
    return len(_supplierids) - 1

def add_correspondent(idurl):
    """
    Add correspondent and return its position in the list.
    """
    global _correspondentids
    _correspondentids.append(idurl)
    return len(_correspondentids) - 1

def remove_correspondent(idurl):
    """
    Remove correspondent with given ID and return True if success.
    """
    global _correspondentids
    if idurl in _correspondentids:
        _correspondentids.remove(idurl)
        return True
    return False

def clear_suppliers():
    """
    Remove all suppliers.
    """
    global _supplierids
    _supplierids = [] 

def clear_customers():
    """
    Remove all customers.
    """
    global _customerids
    _customerids = []
    
def clear_correspondents():
    """
    Remove all correspondents.
    """
    global _correspondentids
    _correspondentids = []

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
    return idurl in correspondents()

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

def supplier_index(idurl):
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

def customer_index(idurl):
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

def contact_index(idurl):
    """
    Return position of given contact in the list of suppliers and customers with given ID or -1.
    """
    if not idurl:
        return -1
    try:
        index = contacts_list().index(idurl)
    except:
        index = -1
    return index

#-------------------------------------------------------------------------------

def save_suppliers(path):
    """
    Write current suppliers list on the disk, ``path`` is a file path to save.
    """
    bpio._write_list(path, suppliers())

def save_customers(path):
    """
    Write current customers list on the disk, ``path`` is a file path to save.
    """
    bpio._write_list(path, customers())
    
def save_correspondents(path):
    """
    Write current correspondents list on the disk, ``path`` is a file path to save.
    """
    bpio._write_list(path, correspondents())

def load_suppliers(path):
    """
    Load suppliers list from disk.
    """
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    set_suppliers(lst)

def load_customers(path):
    """
    Load customers list from disk.
    """
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    set_customers(lst)

def load_correspondents(path):
    """
    Load correspondents list from disk.
    """
    lst = bpio._read_list(path)
    if lst is None:
        lst = list()
    set_correspondents(lst)






