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

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import utime

from bitdust.contacts import contactsdb

from bitdust.customer import supplier_connector

#------------------------------------------------------------------------------


def pay_for_storage():
    now = utime.utcnow_to_sec1970()
    for supplier_idurl in contactsdb.suppliers():
        supplier_contracts = supplier_connector.list_storage_contracts(supplier_idurl)
        unpaid_contracts = []
        for json_data in supplier_contracts:
            if json_data.get('paid'):
                continue
            if now < utime.unpack_time(json_data['complete_after']):
                continue
            unpaid_contracts.append(json_data)
        if unpaid_contracts:
            unpaid_contracts.sort(key=lambda i: utime.unpack_time(i['started']))
            pay_before_earliest = utime.unpack_time(unpaid_contracts[0]['pay_before'])
            pay_before_latest = utime.unpack_time(unpaid_contracts[-1]['pay_before'])
            sum_to_pay = 0
            for unpaid_contract in unpaid_contracts:
                sum_to_pay += unpaid_contract['value']
            if _Debug:
                lg.args(_DebugLevel, s=supplier_idurl, to_pay=sum_to_pay, pay_before_earliest=utime.pack_time(pay_before_earliest), pay_before_latest=utime.pack_time(pay_before_latest))
