#!/usr/bin/python
#accouning.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: accouning

Various methods to keep track of:

    + donated space
    + needed space
    + used space
    + free space
    + consumed space

"""

#------------------------------------------------------------------------------ 

_DebugLevel = 4

#------------------------------------------------------------------------------ 

import os
import math

from logs import lg

from system import bpio

from lib import diskspace
from lib import misc 

from main import settings

from contacts import contactsdb

from storage import backup_fs

#------------------------------------------------------------------------------ 

def init():
    lg.out(_DebugLevel, 'accounting.init')
    
#------------------------------------------------------------------------------ 

def check_create_customers_quotas():
    if not os.path.isfile(settings.CustomersSpaceFile()):
        bpio._write_dict(settings.CustomersSpaceFile(),
            {'free': settings.getDonatedBytes()})
        return True
    return False
    
def read_customers_quotas():
    return bpio._read_dict(settings.CustomersSpaceFile(), {})

def write_customers_quotas(new_space_dict):
    return bpio._write_dict(settings.CustomersSpaceFile(), new_space_dict)      

def count_consumed_space(space_dict=None):
    if space_dict is None:
        space_dict = read_customers_quotas()
    consumed_bytes = 0
    for idurl, customer_consumed in space_dict.items():
        if idurl != 'free':
            consumed_bytes += int(customer_consumed)
    return consumed_bytes

def validate_customers_quotas(space_dict=None):
    unknown_customers = set()
    unused_quotas = set()
    if space_dict is None:
        space_dict = bpio._read_dict(settings.CustomersSpaceFile(), {})
    for idurl in list(space_dict.keys()):
        try:
            space_dict[idurl] = int(space_dict[idurl])
        except:
            if idurl != 'free':
                unknown_customers.add(idurl)
            continue
        if idurl != 'free' and space_dict[idurl] <= 0:
            unknown_customers.add(idurl)
            continue            
    for idurl in contactsdb.customers():
        if idurl not in space_dict.keys():
            unknown_customers.add(idurl)
    for idurl in space_dict.keys():
        if idurl != 'free':
            if idurl not in contactsdb.customers():
                unused_quotas.add(idurl)
    return unknown_customers, unused_quotas

#------------------------------------------------------------------------------ 

def read_customers_usage(): 
    return bpio._read_dict(settings.CustomersUsedSpaceFile(), {})

def update_customers_usage(new_space_usage_dict):
    return bpio._write_dict(settings.CustomersUsedSpaceFile(), new_space_usage_dict)    

def calculate_customers_usage_ratio(space_dict=None, used_dict=None):
    if space_dict is None:
        space_dict = read_customers_quotas()
    if used_dict is None:
        used_dict = read_customers_usage()        
    current_customers = contactsdb.customers()
    used_space_ratio_dict = {}
    for idurl in current_customers:
        allocated_bytes = int(space_dict[idurl])
        try:
            files_size = int(used_dict.get(idurl, 0))
        except:
            files_size = 0
        try:
            ratio = float(files_size) / float(allocated_bytes)
        except:
            continue
        used_space_ratio_dict[idurl] = ratio
    return used_space_ratio_dict

#------------------------------------------------------------------------------ 

def report_donated_storage():
    space_dict = read_customers_quotas()
    used_space_dict = read_customers_usage()
    r = {}
    r['customers_num'] = contactsdb.num_customers()
    r['customers'] = []
    r['oldcustomers'] = []
    r['errors'] = []
    r['consumed'] = 0
    r['used'] = 0
    r['real'] = bpio.getDirectorySize(settings.getCustomersFilesDir())
    r['real_str'] = diskspace.MakeStringFromBytes(r['real'])
    r['donated'] = settings.getDonatedBytes()
    r['donated_str'] = diskspace.MakeStringFromBytes(r['donated'])
    try:
        r['free'] = int(space_dict.pop('free'))
    except:
        r['free'] = 0
    for idurl in contactsdb.customers():
        consumed_by_customer = 0
        used_by_customer = 0
        if idurl not in space_dict.keys():
            r['errors'].append('space consumed by customer %s is unknown' % idurl)
        else:
            try:
                consumed_by_customer = int(space_dict.pop(idurl))
                r['consumed'] += consumed_by_customer
            except:
                r['errors'].append('incorrect value of consumed space for customer %s' % idurl)
        if idurl in used_space_dict.keys():
            try:
                used_by_customer = int(used_space_dict.pop(idurl))
                r['used'] += used_by_customer
            except:
                r['errors'].append('incorrect value of used space for customer %s' % idurl)
        if consumed_by_customer < used_by_customer:
            r['errors'].append('customer %s currently using more space than requested' % idurl)
        c = {}
        c['idurl'] = idurl
        c['used'] = used_by_customer
        c['used_str'] = diskspace.MakeStringFromBytes(c['used'])
        c['consumed'] = consumed_by_customer
        c['consumed_str'] = diskspace.MakeStringFromBytes(c['consumed'])
        c['real'] = bpio.getDirectorySize(settings.getCustomerFilesDir(idurl))
        c['real_str'] = diskspace.MakeStringFromBytes(c['real'])
        r['customers'].append(c)
    r['used_str'] = diskspace.MakeStringFromBytes(r['used'])
    r['consumed_str'] = diskspace.MakeStringFromBytes(r['consumed'])
    if r['donated'] != r['free'] + r['consumed']:
        r['errors'].append('total consumed %d and known free %d (%d total) bytes not match with donated %d bytes' % (
            r['consumed'], r['free'], 
            r['consumed'] + r['free'], r['donated']))
    if r['used'] > r['donated']:
        r['errors'].append('total space used by customers exceed the donated limit')
    if len(space_dict) > 0:
        r['errors'].append('found %d incorrect records of consumed space' % len(space_dict))
    if r['real'] != r['used']:
        r['errors'].append('current info needs update, known size is %d bytes but real is %d bytes' % (
            r['used'], r['real']))
    for idurl in used_space_dict.keys():
        real = bpio.getDirectorySize(settings.getCustomerFilesDir(idurl))
        r['oldcustomers'].append({
            'idurl': idurl,
            'used': used_space_dict['idurl'],
            'used_str': diskspace.MakeStringFromBytes(used_space_dict['idurl']),
            'real': real,
            'real_str': diskspace.MakeStringFromBytes(real),
            })
    try:
        r['used_percent'] = misc.percent2string(r['used'] / r['donated'])
    except:
        r['used_percent'] = '0%'
    try:
        r['real_percent'] = misc.percent2string(r['real'] / r['donated'])
    except:
        r['real_percent'] = '0%'
    try:
        r['consumed_percent'] = misc.percent2string(r['consumed'] / r['donated'])
    except:
        r['consumed_percent'] = '0%'        
    return r


def report_consumed_storage():
    result = {}
    result['suppliers_num'] = contactsdb.num_suppliers()
    result['needed'] = settings.getNeededBytes()
    result['needed_str'] = diskspace.MakeStringFromBytes(result['needed'])
    result['used'] = int(backup_fs.sizebackups() / 2)
    result['used_str'] = diskspace.MakeStringFromBytes(result['used'])
    result['available'] = result['needed'] - result['used']
    result['available_str'] = diskspace.MakeStringFromBytes(result['available'])
    result['needed_per_supplier'] = 0
    result['used_per_supplier'] = 0
    result['available_per_supplier'] = 0
    if result['suppliers_num'] > 0: 
        result['needed_per_supplier'] = int(math.ceil(2.0 * result['needed'] / result['suppliers_num'])) 
        result['used_per_supplier'] = int(math.ceil(2.0 * result['used'] / result['suppliers_num']))
        result['available_per_supplier'] = result['needed_per_supplier'] - result['used_per_supplier']
    result['needed_per_supplier_str'] = diskspace.MakeStringFromBytes(result['needed_per_supplier'])
    result['used_per_supplier_str'] = diskspace.MakeStringFromBytes(result['used_per_supplier'])
    result['available_per_supplier_str'] = diskspace.MakeStringFromBytes(result['available_per_supplier'])
    try:
        result['used_percent'] = misc.percent2string(result['used'] / result['needed'])
    except:
        result['used_percent'] = '0%'
    return result

