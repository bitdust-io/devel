#!/usr/bin/env python
# storage_contract.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (storage_contract.py) is part of BitDust Software.
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
"""
.. module:: storage_contract.

"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import utime
from bitdust.lib import strng
from bitdust.lib import jsn

from bitdust.system import local_fs
from bitdust.system import bpio

from bitdust.main import config
from bitdust.main import settings
from bitdust.main import events

from bitdust.crypt import key

from bitdust.contacts import contactsdb

from bitdust.storage import accounting

from bitdust.blockchain import bismuth_wallet

from bitdust.userid import id_url

#------------------------------------------------------------------------------


def get_customer_contracts_dir(customer_idurl):
    customer_idurl = id_url.field(customer_idurl)
    customer_contracts_prefix = '{}_{}'.format(
        customer_idurl.username,
        strng.to_text(key.HashSHA(customer_idurl.to_public_key(), hexdigest=True)),
    )
    return os.path.join(settings.ServiceDir('service_supplier_contracts'), customer_contracts_prefix)


def get_current_customer_contract(customer_idurl):
    customer_contracts_dir = get_customer_contracts_dir(customer_idurl)
    if _Debug:
        lg.args(_DebugLevel, c=customer_idurl, path=customer_contracts_dir)
    if not os.path.isdir(customer_contracts_dir):
        bpio._dirs_make(customer_contracts_dir)
    current_customer_contract_path = os.path.join(customer_contracts_dir, 'current')
    if not os.path.isfile(current_customer_contract_path):
        return None
    json_data = jsn.loads_text(local_fs.ReadTextFile(current_customer_contract_path))
    if not json_data:
        return None
    if not accounting.verify_storage_contract(json_data):
        lg.err('current storage contract with %r is not valid' % customer_idurl)
        return None
    if 'my_position' in json_data:
        # TODO: remove later...
        json_data['ecc_position'] = json_data.pop('my_position')
    return json_data


def is_current_customer_contract_active(customer_idurl):
    current_contract = get_current_customer_contract(customer_idurl)
    if not current_contract:
        return False
    now = utime.utcnow_to_sec1970()
    if now > utime.unpack_time(current_contract['complete_after']):
        return False
    return True


def list_customer_contracts(customer_idurl):
    customer_contracts_dir = get_customer_contracts_dir(customer_idurl)
    if not os.path.isdir(customer_contracts_dir):
        bpio._dirs_make(customer_contracts_dir)
    customer_contracts = {}
    current_contract = None
    latest_contract = None
    latest_contract_state = None
    latest_contract_started_time = -1
    latest_completed_contract = None
    latest_completed_contract_time = -1
    latest_paid_contract = None
    latest_paid_contract_time = -1
    completed_contracts_total_GBH_value = 0
    paid_contracts_total_GBH_value = 0
    for fname in os.listdir(customer_contracts_dir):
        if fname == 'current':
            current_contract = jsn.loads_text(local_fs.ReadTextFile(os.path.join(customer_contracts_dir, 'current')))
            if not accounting.verify_storage_contract(current_contract):
                current_contract = None
                lg.err('current storage contract is invalid')
            if 'my_position' in current_contract:
                # TODO: remove later...
                current_contract['ecc_position'] = current_contract.pop('my_position')
            continue
        try:
            started_time = int(fname.split('.')[0])
            contract_state = fname.split('.')[1]
        except:
            lg.exc()
            continue
        contract_path = os.path.join(customer_contracts_dir, fname)
        json_data = jsn.loads_text(local_fs.ReadTextFile(contract_path))
        if not accounting.verify_storage_contract(json_data):
            lg.err('invalid storage contract found: %r' % fname)
            continue
        if 'my_position' in json_data:
            # TODO: remove later...
            json_data['ecc_position'] = json_data.pop('my_position')
        json_data['filename'] = fname
        customer_contracts[started_time] = json_data
        if started_time > latest_contract_started_time:
            latest_contract_started_time = started_time
            latest_contract = json_data
            latest_contract_state = contract_state
        if contract_state == 'completed':
            completed_contracts_total_GBH_value += json_data['value']
            if started_time > latest_completed_contract_time:
                latest_completed_contract = json_data
        elif contract_state == 'cancelled':
            completed_contracts_total_GBH_value += json_data['completed_value']
        elif contract_state == 'paid':
            paid_contracts_total_GBH_value += json_data['value']
            if started_time > latest_paid_contract_time:
                latest_paid_contract = json_data
        else:
            raise Exception('unknown state of the contract')
    customer_contracts['current'] = current_contract
    customer_contracts['latest'] = latest_contract
    customer_contracts['latest_state'] = latest_contract_state
    customer_contracts['latest_paid_contract'] = latest_paid_contract
    customer_contracts['latest_completed_contract'] = latest_completed_contract
    customer_contracts['completed_value'] = completed_contracts_total_GBH_value
    customer_contracts['paid_value'] = paid_contracts_total_GBH_value
    if _Debug:
        lg.args(_DebugLevel, completed_value=completed_contracts_total_GBH_value, paid_value=paid_contracts_total_GBH_value)
    return customer_contracts


def prepare_customer_contract(customer_idurl, details):
    customer_contracts_dir = get_customer_contracts_dir(customer_idurl)
    if _Debug:
        lg.args(_DebugLevel, c=customer_idurl, path=customer_contracts_dir)
    now = utime.utcnow_to_sec1970()
    started_time = now
    if not os.path.isdir(customer_contracts_dir):
        bpio._dirs_make(customer_contracts_dir)
    current_customer_contract_path = os.path.join(customer_contracts_dir, 'current')
    if os.path.isfile(current_customer_contract_path):
        current_contract = jsn.loads_text(local_fs.ReadTextFile(current_customer_contract_path))
        if current_contract:
            if not accounting.verify_storage_contract(current_contract):
                current_contract = None
                lg.err('current storage contract with %r is not valid' % customer_idurl)
            else:
                if now < utime.unpack_time(current_contract['complete_after']):
                    # SCENARIO 2: there is already a contract started with this customer and not yet completed
                    if _Debug:
                        lg.dbg(_DebugLevel, 'valid customer contract with %r already exists' % customer_idurl)
                    return change_current_customer_contract(customer_idurl, details)
                # SCENARIO 3,4,6: found that previous contract was active but finished now
                lg.warn('current storage contract with %r already ended' % customer_idurl)
                complete_current_customer_contract(customer_idurl)
    customer_contracts_list_and_details = list_customer_contracts(customer_idurl)
    latest_contract = customer_contracts_list_and_details['latest']
    latest_contract_state = customer_contracts_list_and_details['latest_state']
    latest_paid_contract = customer_contracts_list_and_details['latest_paid_contract']
    latest_completed_contract = customer_contracts_list_and_details['latest_completed_contract']
    completed_value = customer_contracts_list_and_details['completed_value']
    billing_period_seconds = settings.SupplierContractBillingPeriodDays()*24*60*60
    initial_duration_hours = config.conf().getInt('services/supplier-contracts/initial-duration-hours')
    new_raise_factor = config.conf().getFloat('services/supplier-contracts/duration-raise-factor')
    new_duration_hours = None
    if not latest_contract:
        # SCENARIO 1: this is a new customer - there were no contracts signed yet
        started_time = now
        new_duration_hours = initial_duration_hours
        new_pay_before_time = started_time + int(billing_period_seconds/2.0)
    else:
        if latest_contract_state == 'cancelled':
            cancelled_contract_filename = latest_contract.pop('filename', None)
            if now < utime.unpack_time(latest_contract['complete_after']):
                # SCENARIO 15,16,17: latest contract was cancelled, but customer wants to restart it
                try:
                    os.remove(os.path.join(customer_contracts_dir, cancelled_contract_filename))
                except:
                    lg.exc()
                return start_current_customer_contract(
                    customer_idurl=customer_idurl,
                    details=details,
                    started_time=utime.unpack_time(latest_contract['started']),
                    complete_after_time=utime.unpack_time(latest_contract['complete_after']),
                    pay_before_time=utime.unpack_time(latest_contract['pay_before']),
                    duration_hours=latest_contract['duration_hours'],
                    raise_factor=latest_contract['raise_factor'],
                )
            if latest_completed_contract:
                if now - initial_duration_hours*60*60 > utime.unpack_time(latest_completed_contract['pay_before']):
                    # SCENARIO 18, 19: latest contract was cancelled and already expired, customer wants to start a new contract
                    # other contract was completed, but was not paid
                    lg.warn('customer %r yet did not pay for previously completed contract' % customer_idurl)
                    return {
                        'deny': True,
                        'reason': 'unpaid',
                        'value': completed_value,
                    }
                # SCENARIO 11,13: latest contract was cancelled and already expired, other contracts was completed already
                try:
                    os.remove(os.path.join(customer_contracts_dir, cancelled_contract_filename))
                except:
                    lg.exc()
                # rename cancelled contract file to "<started_time>.completed"
                contract_path_new = os.path.join(customer_contracts_dir, '{}.completed'.format(utime.unpack_time(latest_contract['started'])))
                local_fs.WriteTextFile(contract_path_new, jsn.dumps(latest_contract))
                started_time = now
                new_duration_hours = initial_duration_hours
                new_pay_before_time = utime.unpack_time(latest_completed_contract['pay_before'])
            else:
                if latest_paid_contract:
                    # SCENARIO 12: latest contract was cancelled and already expired, other contracts was paid
                    try:
                        os.remove(os.path.join(customer_contracts_dir, cancelled_contract_filename))
                    except:
                        lg.exc()
                    # rename cancelled contract file to "<started_time>.completed"
                    contract_path_new = os.path.join(customer_contracts_dir, '{}.completed'.format(utime.unpack_time(latest_contract['started'])))
                    local_fs.WriteTextFile(contract_path_new, jsn.dumps(latest_contract))
                    started_time = now
                    new_duration_hours = initial_duration_hours
                    new_pay_before_time = started_time + int(billing_period_seconds/2.0)
                else:
                    # SCENARIO 10: latest contract was cancelled and already expired, no other contracts found
                    # rename cancelled contract file to "<started_time>.completed"
                    contract_path_new = os.path.join(customer_contracts_dir, '{}.completed'.format(utime.unpack_time(latest_contract['started'])))
                    local_fs.WriteTextFile(contract_path_new, jsn.dumps(latest_contract))
                    started_time = now
                    new_duration_hours = initial_duration_hours
                    new_pay_before_time = started_time + int(billing_period_seconds/2.0)
        else:
            started_time = utime.unpack_time(latest_contract['complete_after'])
            new_duration_hours = int(latest_contract['duration_hours']*latest_contract['raise_factor'])
            if latest_contract_state == 'completed':
                if latest_paid_contract:
                    new_pay_before_time = utime.unpack_time(latest_paid_contract['started']) + latest_paid_contract['duration_hours']*60*60 + billing_period_seconds
                    if new_pay_before_time < started_time + new_duration_hours*60*60:
                        # SCENARIO 9: the previous contract is completed and some contracts already paid, but there is still no trust to this customer
                        lg.warn('customer %r paid before, but yet did not pay for previously completed contracts' % customer_idurl)
                        return {
                            'deny': True,
                            'reason': 'unpaid',
                            'value': completed_value,
                        }
                    else:
                        # SCENARIO 7: no active contract, the previos contract is completed and there is also a paid contract before
                        pass
                else:
                    new_pay_before_time = utime.unpack_time(latest_contract['pay_before'])
                    if new_pay_before_time < now + new_duration_hours*60*60:
                        # SCENARIO 8: the previous contract is completed, but there is no trust to this customer
                        lg.warn('customer %r yet did not pay for previously completed contract' % customer_idurl)
                        return {
                            'deny': True,
                            'reason': 'unpaid',
                            'value': completed_value,
                        }
                    else:
                        # SCENARIO 5: no active contract, the previos contract is completed but there were no payments yet done
                        pass
            elif latest_contract_state == 'paid':
                # SCENARIO 14: currently there is no active contract, but the previos contract is completed and paid
                new_duration_hours = initial_duration_hours
                new_pay_before_time = started_time + billing_period_seconds
            else:
                raise Exception('unexpected contract state: %r' % latest_contract_state)
    return start_current_customer_contract(
        customer_idurl=customer_idurl,
        details=details,
        started_time=started_time,
        complete_after_time=started_time + new_duration_hours*60*60,
        pay_before_time=new_pay_before_time,
        duration_hours=new_duration_hours,
        raise_factor=new_raise_factor,
    )


def start_current_customer_contract(customer_idurl, details, started_time, complete_after_time, pay_before_time, duration_hours, raise_factor):
    json_data = {
        'started': utime.pack_time(started_time),
        'complete_after': utime.pack_time(complete_after_time),
        'pay_before': utime.pack_time(pay_before_time),
        'value': float(duration_hours)*(details['allocated_bytes']/(1024.0*1024.0*1024.0)),
        'allocated_bytes': details['allocated_bytes'],
        'duration_hours': duration_hours,
        'ecc_position': details['ecc_position'],
        'ecc_map': details['ecc_map'],
        'raise_factor': raise_factor,
        'wallet_address': bismuth_wallet.my_wallet_address(),
    }
    local_fs.WriteTextFile(os.path.join(get_customer_contracts_dir(customer_idurl), 'current'), jsn.dumps(json_data))
    json_data['customer'] = customer_idurl
    if _Debug:
        lg.args(_DebugLevel, c=json_data)
    events.send('storage-contract-started', data=dict(contract=json_data))
    return json_data


def cancel_customer_contract(customer_idurl):
    customer_contracts_dir = get_customer_contracts_dir(customer_idurl)
    if _Debug:
        lg.args(_DebugLevel, c=customer_idurl, path=customer_contracts_dir)
    if not os.path.isdir(customer_contracts_dir):
        return False
    current_customer_contract_path = os.path.join(customer_contracts_dir, 'current')
    if not os.path.isfile(current_customer_contract_path):
        return False
    current_contract = jsn.loads_text(local_fs.ReadTextFile(current_customer_contract_path))
    if not current_contract:
        return False
    if not accounting.verify_storage_contract(current_contract):
        lg.err('current contract with %r is not valid' % customer_idurl)
        return False
    cancelled_time = utime.utcnow_to_sec1970()
    completed_duration_hours = (cancelled_time - utime.unpack_time(current_contract['started']))/(60.0*60.0)
    completed_value = float(completed_duration_hours)*(current_contract['allocated_bytes']/(1024.0*1024.0*1024.0))
    current_contract['completed_value'] = completed_value
    current_contract['cancelled'] = utime.pack_time(cancelled_time)
    # rename "current" file to "<started_time>.cancelled"
    try:
        os.remove(current_customer_contract_path)
    except:
        lg.exc()
    contract_path_new = os.path.join(customer_contracts_dir, '{}.cancelled'.format(utime.unpack_time(current_contract['started'])))
    local_fs.WriteTextFile(contract_path_new, jsn.dumps(current_contract))
    if _Debug:
        lg.args(_DebugLevel, old_path=current_customer_contract_path, new_path=contract_path_new)
    current_contract['customer'] = customer_idurl
    events.send('storage-contract-cancelled', data=dict(contract=current_contract))
    return True


def change_current_customer_contract(customer_idurl, details):
    customer_contracts_dir = get_customer_contracts_dir(customer_idurl)
    if _Debug:
        lg.args(_DebugLevel, c=customer_idurl, path=customer_contracts_dir)
    if not os.path.isdir(customer_contracts_dir):
        bpio._dirs_make(customer_contracts_dir)
    current_customer_contract_path = os.path.join(customer_contracts_dir, 'current')
    if not os.path.isfile(current_customer_contract_path):
        lg.err('current storage contract with %r not found' % customer_idurl)
        return {
            'deny': True,
            'reason': 'current storage contract not found',
        }
    current_contract = jsn.loads_text(local_fs.ReadTextFile(current_customer_contract_path))
    if not current_contract:
        lg.err('current storage contract with %r read failed' % customer_idurl)
        return {
            'deny': True,
            'reason': 'current storage contract not found',
        }
    if details.get('ecc_map'):
        current_contract['ecc_map'] = details['ecc_map']
    if details.get('ecc_position') is not None:
        current_contract['ecc_position'] = details['ecc_position']
    if details['allocated_bytes'] != current_contract['allocated_bytes']:
        current_value = current_contract['value']
        new_duration_hours = int(current_value/(details['allocated_bytes']/(1024.0*1024.0*1024.0)))
        new_complete_after_time = utime.unpack_time(current_contract['started']) + new_duration_hours*60*60
        if new_complete_after_time > utime.unpack_time(current_contract['pay_before']):
            return {
                'deny': True,
                'reason': 'contract duration change limit exceeded',
            }
        current_contract['allocated_bytes'] = details['allocated_bytes']
        current_contract['duration_hours'] = new_duration_hours
        current_contract['complete_after'] = utime.pack_time(new_complete_after_time)
    if _Debug:
        lg.args(_DebugLevel, c=current_contract)
    local_fs.WriteTextFile(current_customer_contract_path, jsn.dumps(current_contract))
    current_contract['customer'] = customer_idurl
    events.send('storage-contract-changed', data=dict(contract=current_contract))
    return current_contract


def complete_current_customer_contract(customer_idurl):
    customer_contracts_dir = get_customer_contracts_dir(customer_idurl)
    if _Debug:
        lg.args(_DebugLevel, c=customer_idurl, path=customer_contracts_dir)
    if not os.path.isdir(customer_contracts_dir):
        bpio._dirs_make(customer_contracts_dir)
    current_customer_contract_path = os.path.join(customer_contracts_dir, 'current')
    if not os.path.isfile(current_customer_contract_path):
        return False
    current_contract = jsn.loads_text(local_fs.ReadTextFile(current_customer_contract_path))
    if not current_contract:
        return False
    if not accounting.verify_storage_contract(current_contract):
        lg.err('current contract with %r is not valid' % customer_idurl)
        return False
    # rename "current" file to "<started_time>.completed"
    contract_path_new = os.path.join(customer_contracts_dir, '{}.completed'.format(utime.unpack_time(current_contract['started'])))
    if _Debug:
        lg.args(_DebugLevel, old_path=current_customer_contract_path, new_path=contract_path_new)
    os.rename(current_customer_contract_path, contract_path_new)
    current_contract['customer'] = customer_idurl
    events.send('storage-contract-completed', data=dict(contract=current_contract))
    return True


def verify_all_current_customers_contracts():
    rejected_customers = []
    now = utime.utcnow_to_sec1970()
    for customer_idurl in contactsdb.customers():
        contracts_list = list_customer_contracts(customer_idurl)
        latest_contract = contracts_list['latest']
        if contracts_list['current']:
            if now > utime.unpack_time(contracts_list['current']['complete_after']):
                lg.warn('current storage contract with %r already ended' % customer_idurl)
                complete_current_customer_contract(customer_idurl)
                latest_contract = contracts_list['current']
        if not latest_contract:
            rejected_customers.append(customer_idurl)
            lg.warn('rejecting customer %r because of missing contract' % customer_idurl)
        else:
            if latest_contract.get('cancelled'):
                lg.warn('rejecting customer %r because of cancelled contract' % customer_idurl)
                rejected_customers.append(customer_idurl)
            else:
                next_complete_after_time = utime.unpack_time(latest_contract['complete_after']) + latest_contract['raise_factor']*latest_contract['duration_hours']*60*60
                if now > next_complete_after_time:
                    lg.warn('rejecting customer %r because of finished contract' % customer_idurl)
                    rejected_customers.append(customer_idurl)
    return rejected_customers
