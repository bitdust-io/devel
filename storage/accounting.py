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
    result = {
        'customers': [],
        'oldcustomers': [],
        'errors': [],
        'consumed': 0,
        'used': 0,
        'real': bpio.getDirectorySize(settings.getCustomersFilesDir()),
        'donated': settings.getDonatedBytes()
        }
    try:
        result['free'] = int(space_dict.pop('free'))
    except:
        result['free'] = 0
    for idurl in contactsdb.customers():
        consumed_by_customer = 0
        used_by_customer = 0
        if idurl not in space_dict.keys():
            result['errors'].append('space consumed by customer %s is unknown' % idurl)
        else:
            try:
                consumed_by_customer = int(space_dict.pop(idurl))
                result['consumed'] += consumed_by_customer
            except:
                result['errors'].append('incorrect value of consumed space for customer %s' % idurl)
        if idurl in used_space_dict.keys():
            try:
                used_by_customer = int(used_space_dict.pop(idurl))
                result['used'] += used_by_customer
            except:
                result['errors'].append('incorrect value of used space for customer %s' % idurl)
        if consumed_by_customer < used_by_customer:
            result['errors'].append('customer %s currently using more space than requested' % idurl)
        result['customers'].append({
            'idurl': idurl,
            'used': used_by_customer,
            'consumed': consumed_by_customer,
            })
    if result['donated'] != result['free'] + result['consumed']:
        result['errors'].append('total consumed %d and known free %d (%d total) bytes not match with donated %d bytes' % (
            result['consumed'], result['free'], 
            result['consumed'] + result['free'], result['donated']))
    if result['used'] > result['donated']:
        result['errors'].append('total space used by customers exceed the donated limit')
    if len(space_dict) > 0:
        result['errors'].append('found %d incorrect records of consumed space' % len(space_dict))
    if result['real'] != result['used']:
        result['errors'].append('current info is not correct, known size is %d bytes but real is %d bytes' % (
            result['used'], result['real']))
    for idurl in used_space_dict.keys():
        result['oldcustomers'].append({
            'idurl': idurl,
            'used': used_space_dict['idurl'],
            })
    return result


def report_consumed_storage():
    result = {
        'needed': settings.getNeededBytes(),
        'used': int(backup_fs.sizebackups() / 2),
        'suppliers': contactsdb.num_suppliers(),
        'needed_per_supplier': 0,
        'used_per_supplier': 0,
        'available_per_supplier': 0,
        }
    result['free'] = result['needed'] - result['used']
    if result['suppliers'] > 0: 
        result['needed_per_supplier'] = int(math.ceil(2.0 * result['needed'] / result['suppliers'])) 
        result['used_per_supplier'] = int(math.ceil(2.0 * result['used'] / result['suppliers']))
        result['available_per_supplier'] = result['needed_per_supplier'] - result['used_per_supplier']
    return result

