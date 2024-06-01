#!/usr/bin/env python
# payment.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (payment.py) is part of BitDust Software.
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
.. module:: payment.

"""

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import utime
from bitdust.lib import strng
from bitdust.lib import jsn

from bitdust.system import bpio
from bitdust.system import local_fs

from bitdust.main import settings

from bitdust.crypt import key

from bitdust.blockchain import bismuth_wallet

from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------


def get_supplier_contracts_dir(supplier_idurl):
    supplier_idurl = id_url.field(supplier_idurl)
    supplier_contracts_prefix = '{}_{}'.format(
        supplier_idurl.username,
        strng.to_text(key.HashSHA(supplier_idurl.to_public_key(), hexdigest=True)),
    )
    return os.path.join(settings.ServiceDir('service_customer_contracts'), supplier_contracts_prefix)


def save_storage_contract(supplier_idurl, json_data):
    supplier_contracts_dir = get_supplier_contracts_dir(supplier_idurl)
    if not os.path.isdir(supplier_contracts_dir):
        bpio._dirs_make(supplier_contracts_dir)
    contract_path = os.path.join(supplier_contracts_dir, str(utime.unpack_time(json_data['started'])))
    json_data['supplier'] = supplier_idurl
    local_fs.WriteTextFile(contract_path, jsn.dumps(json_data))
    return contract_path


def list_storage_contracts(supplier_idurl):
    supplier_contracts_dir = get_supplier_contracts_dir(supplier_idurl)
    if not os.path.isdir(supplier_contracts_dir):
        return []
    l = []
    for contract_filename in os.listdir(supplier_contracts_dir):
        contract_path = os.path.join(supplier_contracts_dir, contract_filename)
        json_data = jsn.loads_text(local_fs.ReadTextFile(contract_path))
        l.append(json_data)
    l.sort(key=lambda json_data: utime.unpack_time(json_data['started']))
    return l


def list_contracted_suppliers():
    supplier_idurls = []
    for supplier_contracts_prefix in os.listdir(settings.ServiceDir('service_customer_contracts')):
        supplier_contracts_dir = os.path.join(settings.ServiceDir('service_customer_contracts'), supplier_contracts_prefix)
        for contract_filename in os.listdir(supplier_contracts_dir):
            contract_path = os.path.join(supplier_contracts_dir, contract_filename)
            json_data = jsn.loads_text(local_fs.ReadTextFile(contract_path))
            supplier_idurl = json_data.get('supplier', None)
            if supplier_idurl:
                if not id_url.is_in(supplier_idurl, supplier_idurls):
                    supplier_idurls.append(supplier_idurl)
                break
    return supplier_idurls


#------------------------------------------------------------------------------


def pay_for_storage():
    cur_balance = bismuth_wallet.my_balance()
    if cur_balance == 'N/A':
        lg.err('my current balance is not available, payments are not possible at the moment')
        return False
    now = utime.utcnow_to_sec1970()
    my_customer_prefix = my_id.getIDURL().unique_name()
    for supplier_idurl in list_contracted_suppliers():
        supplier_contracts = list_storage_contracts(supplier_idurl)
        unpaid_contracts = []
        unpaid_sequence_numbers = set()
        for pos, json_data in enumerate(supplier_contracts):
            if json_data.get('paid'):
                continue
            if now < utime.unpack_time(json_data['complete_after']):
                continue
            unpaid_contracts.append(json_data)
            sequence_number = json_data.get('sequence_number', -1)
            if sequence_number < 0:
                sequence_number = pos + 1
            unpaid_sequence_numbers.add(sequence_number)
        sum_to_pay = 0
        pay_before_earliest = None
        pay_before_latest = None
        supplier_wallet_address = None
        started = None
        complete_after = None
        if unpaid_contracts:
            unpaid_contracts.sort(key=lambda i: utime.unpack_time(i['started']))
            started = unpaid_contracts[0]['started']
            complete_after = unpaid_contracts[-1]['complete_after']
            pay_before_earliest = utime.unpack_time(unpaid_contracts[0]['pay_before'])
            pay_before_latest = utime.unpack_time(unpaid_contracts[-1]['pay_before'])
            supplier_wallet_address = unpaid_contracts[-1]['wallet_address']
            for unpaid_contract in unpaid_contracts:
                sum_to_pay += unpaid_contract['value']
        if _Debug:
            lg.args(
                _DebugLevel,
                s=supplier_idurl,
                unpaid=len(unpaid_contracts),
                debt=sum_to_pay,
                pay_earliest=utime.pack_time(pay_before_earliest),
                pay_latest=utime.pack_time(pay_before_latest),
                started=started,
                complete_after=complete_after,
            )
        if sum_to_pay:
            if now > pay_before_earliest:
                if sum_to_pay >= cur_balance:
                    lg.warn('my current balance %r is not enough to pay %r to %r' % (cur_balance, sum_to_pay, supplier_idurl))
                    continue
                try:
                    ret = bismuth_wallet.send_transaction(
                        recipient=supplier_wallet_address,
                        amount=sum_to_pay,
                        operation='storage',
                        data='{} {}'.format(my_customer_prefix, ','.join(map(str, sorted(unpaid_sequence_numbers)))),
                        raise_errors=True,
                    )
                except:
                    lg.exc()
                    return False
                if _Debug:
                    lg.args(_DebugLevel, recipient=supplier_wallet_address, ret=ret)
                cur_balance = bismuth_wallet.my_balance()
                if cur_balance == 'N/A':
                    lg.err('my current balance is not available, payments are not possible at the moment')
                    return False
    return True
