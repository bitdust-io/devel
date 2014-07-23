#!/usr/bin/python
#contacts.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: contacts

This module to store and work with user IDs.

User ID has the following form:
    
    http://example.server.org/subfolder/user.xml
    
See userid/identity.py for more details about user identities. 

We only talk with limited sets of people and in limited ways for each type:
 1)  suppliers        - ID's for nodes who supply us with storage services 
 2)  customer         - ID's for nodes we provide our storage
 3)  scrubber         - only activated for customers who are offline more than 30 hours (or something)
                           Rights the same as that customer number they scrub for
 4)  correspondent    - ID's for people we accept messages from

We keep around URLIDs and Identities for each.
We have to get an identity record for each of these contacts.
We have to record bandwidth between us and each contact for each 24 hour period.
We have to report bandwidth sometime in the following 24 hour period.
From User/GUI or backup_monitor.py we might replace one contact at a time.

A low level methods used here are placed in the contactsdb.py.
TODO:  contacts and contactsdb can be merged probably. 

"""


import os
import string
import sys

from logs import lg

from userid import identitycache 

import bpio
import settings
import misc
import contactsdb
import nameurl


#-------------------------------------------------------------------------------

_SuppliersChangedCallback = None
_CustomersChangedCallback = None
_ContactsChangedCallback = None
_CorrespondentsChangedCallback = None
#_RequestFailsDict = {}

#------------------------------------------------------------------------------ 

def init():
    """
    We read from disk and if we have all the info we are set.
    If we don't have enough, then we have to ask BitPie.NET to list contacts and use
    that list to get and then store all the identities for our contacts.
    """
    lg.out(4, "contacts.init ")
    contactsdb.load_suppliers(settings.SupplierIDsFilename())
    contactsdb.load_customers(settings.CustomerIDsFilename())
    contactsdb.load_correspondents(settings.CorrespondentIDsFilename())

#------------------------------------------------------------------------------ 

def getContact(idurl):
    """
    The Main Method Here - return identity object for given ID or None if not found. 
    Only valid contacts for packets will be signed by local identity, suppliers, customers.
    """
    if idurl is None:
        return None
    if idurl == misc.getLocalID():
        return misc.getLocalIdentity()
    if contactsdb.is_supplier(idurl):
        return identitycache.FromCache(idurl)
    if contactsdb.is_customer(idurl):
        return identitycache.FromCache(idurl)
    if contactsdb.is_correspondent(idurl):
        return identitycache.FromCache(idurl)
    if identitycache.HasKey(idurl):
        # lg.out(2, "contacts.getContact WARNING who is %s ?" % nameurl.GetName(idurl))
        return identitycache.FromCache(idurl)
    lg.out(6, "contacts.getContact %s is not found" % nameurl.GetName(idurl))
    # TODO
    # this is not correct: 
    # need to check if other contacts is fine - if internet is turned off we can get lots fails ...  
    return None

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

#-------------------------------------------------------------------------------

def getContactIDs():
    """
    Return a list of all contacts - a union of suppliers, customers and correspondents.
    Sometimes we want to loop through all the IDs we make contact with.
    """
    return contactsdb.contacts()

def IsCustomer(custid):
    """
    Verify that ``custid`` is included in customers list.
    """
    return contactsdb.is_customer(custid)

def IsSupplier(supid):
    """
    Verify that ``supid`` is included in suppliers list.
    """
    return contactsdb.is_supplier(supid)

def IsCorrespondent(idurl):
    """
    Verify that ``idurl`` is included in correspondents list.
    """
    return contactsdb.is_correspondent(idurl)

def numSuppliers():
    """
    Return number of suppliers.
    """
    return contactsdb.num_suppliers()

def numCustomers():
    """
    Return number of customers.
    """
    return contactsdb.num_customers()

def getSupplierIDs():
    """
    Return list of suppliers ID's.
    """
    return contactsdb.suppliers()

def getCustomerIDs():
    """
    Return list of customers ID's.
    """
    return contactsdb.customers()

def getCustomer(ID):
    """
    If ``ID`` is in customers list, return its identity object.
    """
    if contactsdb.is_customer(ID):
        return identitycache.FromCache(ID)
    return None

def getCustomerNames():
    """
    Return a list of customers names: ['veselin', 'bob', 'alice', ...]
    """
    return map(nameurl.GetName, contactsdb.customers())

def setSupplierIDs(idslist):
    """
    Set suppliers ID's list, called when ListContacts packet received from Central server.
    """
    global _SuppliersChangedCallback
    global _ContactsChangedCallback
    oldsuppliers = contactsdb.suppliers()
    oldcontacts = contactsdb.contacts()
    contactsdb.set_suppliers(idslist)
    if _SuppliersChangedCallback is not None:
        _SuppliersChangedCallback(oldsuppliers, contactsdb.suppliers())
    if _ContactsChangedCallback is not None:
        _ContactsChangedCallback(oldcontacts, contactsdb.contacts())

def setCustomerIDs(idslist):
    """
    Set customers ID's list, called when ListContacts packet received from Central server.
    """
    global _CustomersChangedCallback
    global _ContactsChangedCallback
    oldcustomers = contactsdb.customers()
    oldcontacts = contactsdb.contacts()
    contactsdb.set_customers(idslist)
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback(oldcustomers, contactsdb.customers())
    if _ContactsChangedCallback is not None:
        _ContactsChangedCallback(oldcontacts, contactsdb.contacts())

def getCorrespondentIDs():
    """
    Return a list of correspondents ID's.
    """
    return contactsdb.correspondents()

def getContactsAndCorrespondents():
    """
    Return a union on contacts and correspondents ID's.
    """
    return contactsdb.contacts_full()

def getRemoteContacts():
    """
    Return ID's list of all known peers. 
    """
    allcontacts = getContactsAndCorrespondents()
    if misc.getLocalID() in allcontacts:
        allcontacts.remove(misc.getLocalID())
    return allcontacts

def getSupplierID(N):
    """
    Return ID of supplier who position is ``N``.
    """
    return contactsdb.supplier(N)

def getSupplierN(N):
    """
    Return identity of supplier who position is ``N``.
    """
    return identitycache.FromCache(getSupplierID(N))

def getSupplier(ID):
    """
    Return peer's identity if he is in suppliers list.
    """
    if contactsdb.is_supplier(ID):
        return identitycache.FromCache(ID)
    return None

def getCorrespondent(ID):
    """
    Return peer's identity if he is in the correspondents list.
    """
    if contactsdb.is_correspondent(ID):
        return identitycache.FromCache(ID)
    return ''

def isKnown(idurl):
    """
    Return True if this is a known ID.
    """
    if contactsdb.is_supplier(idurl):
        return True
    if contactsdb.is_customer(idurl):
        return True
    if contactsdb.is_correspondent(idurl):
        return True
    return False
    
def numberForContact(idurl):
    """
    Return position for given contact ID in the total list combined from suppliers, customers.
    Suppliers should be numbered 0 to 63 with customers after that not sure we can count on numbers staying.
    """
    return contactsdb.contact_index(idurl)

def numberForCustomer(idurl):
    """
    Return position for given customer ID in the customers list.
    """
    return contactsdb.customer_index(idurl)

def numberForSupplier(idurl):
    """
    Return position for given supplier ID in the suppliers list.
    """
    return contactsdb.supplier_index(idurl)

def getCustomerID(N):
    """
    Get customer ID at given position.
    """
    return contactsdb.customer(N)

def getCustomerN(N):
    """
    Get customer at given position.
    """
    return identitycache.FromCache(contactsdb.customer(N))

def addCustomer(idurl):
    """
    Add a new customer, call event handlers.
    """
    global _CustomersChangedCallback
    global _ContactsChangedCallback
    oldcustomers = contactsdb.customers()
    oldcontacts = contactsdb.contacts()
    res = contactsdb.add_customer(idurl)
    if _CustomersChangedCallback is not None:
        _CustomersChangedCallback(oldcustomers, contactsdb.customers())
    if _ContactsChangedCallback is not None:
        _ContactsChangedCallback(oldcontacts, contactsdb.contacts())
    return res

#------------------------------------------------------------------------------ 

def getIDByAddress(address):
    """
    This will return a user ID by given contact address or None.
    """
    idurls = identitycache.GetIDURLsByContact(address)
    if len(idurls) == 0:
        return None
    return idurls[0]
    
#------------------------------------------------------------------------------ 

def saveCustomerIDs():
    """
    Save current customers list to local file.
    """
    contactsdb.save_customers(settings.CustomerIDsFilename())

def saveSupplierIDs():
    """
    Save current suppleirs list to local file.
    """
    contactsdb.save_suppliers(settings.SupplierIDsFilename())
    
def saveCorrespondentIDs():
    """
    Save correspondents list to local file.
    """
    contactsdb.save_correspondents(settings.CorrespondentIDsFilename())

#-------------------------------------------------------------------------------

def addCorrespondent(idurl):
    """
    Add a new correspondent.
    """
    return contactsdb.add_correspondent(idurl)
    
def removeCorrespondent(idurl):
    """
    Remove a correspondent.
    """
    return contactsdb.remove_correspondent(idurl)

#-------------------------------------------------------------------------------

if __name__ == '__main__':
    init()




