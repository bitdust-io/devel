#!/usr/bin/env python
# customers_rejector.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (customers_rejector.py) is part of BitDust Software.
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
.. module:: customers_rejector.

.. role:: red

BitDust customers_rejector() Automat

.. raw:: html

    <a href="customers_rejector.png" target="_blank">
    <img src="customers_rejector.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`packets-sent`
    * :red:`restart`
    * :red:`space-enough`
    * :red:`space-overflow`
"""

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from system import bpio

from main import settings
from main import events

from contacts import contactsdb

from lib import packetid

from userid import id_url

from p2p import p2p_service

from storage import accounting

#------------------------------------------------------------------------------

_CustomersRejector = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _CustomersRejector
    if _CustomersRejector is None:
        # set automat name and starting state here
        _CustomersRejector = CustomersRejector('customers_rejector', 'READY', 4)
    if event is not None:
        _CustomersRejector.automat(event, *args, **kwargs)
    return _CustomersRejector


def Destroy():
    """
    Destroy customers_rejector() automat and remove its instance from memory.
    """
    global _CustomersRejector
    if _CustomersRejector is None:
        return
    _CustomersRejector.destroy()
    del _CustomersRejector
    _CustomersRejector = None


class CustomersRejector(automat.Automat):
    """
    This class implements all the functionality of the ``customers_rejector()``
    state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['REJECT_GUYS']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """

    def A(self, event, *args, **kwargs):
        #---READY---
        if self.state == 'READY':
            if event == 'restart':
                self.state = 'CAPACITY?'
                self.doTestMyCapacity(*args, **kwargs)
        #---CAPACITY?---
        elif self.state == 'CAPACITY?':
            if event == 'space-enough':
                self.state = 'READY'
            elif event == 'space-overflow':
                self.state = 'REJECT_GUYS'
                self.doRemoveCustomers(*args, **kwargs)
                self.doSendRejectService(*args, **kwargs)
        #---REJECT_GUYS---
        elif self.state == 'REJECT_GUYS':
            if event == 'restart':
                self.state = 'CAPACITY?'
                self.doTestMyCapacity(*args, **kwargs)
            elif event == 'packets-sent':
                self.state = 'READY'
                self.doRestartLocalTester(*args, **kwargs)

    def doTestMyCapacity(self, *args, **kwargs):
        """
        Here are some values.

        + donated_bytes : you set this in the configs
        + consumed_bytes : how many space was taken from you by other users
        + free_bytes = donated_bytes - consumed_bytes : not yet allocated space
        + used_bytes : size of all files, which you store on your disk for your customers
        + ratio : currently used space compared to consumed space
        """
        lg.out(8, 'customers_rejector.doTestMyCapacity')
        failed_customers = set()
        current_customers = contactsdb.customers()
        donated_bytes = settings.getDonatedBytes()
        space_dict, free_space = accounting.read_customers_quotas()
        used_dict = accounting.read_customers_usage()
        unknown_customers, unused_quotas = accounting.validate_customers_quotas(space_dict, free_space)
        failed_customers.update(unknown_customers)
        for idurl in unknown_customers:
            space_dict.pop(idurl, None)
        for idurl in unused_quotas:
            space_dict.pop(idurl, None)
        consumed_bytes = accounting.count_consumed_space(space_dict)
        free_space = donated_bytes - consumed_bytes
        if consumed_bytes < donated_bytes and len(failed_customers) == 0:
            accounting.write_customers_quotas(space_dict, free_space)
            lg.out(8, '        space is OK !!!!!!!!')
            self.automat('space-enough')
            return
        if failed_customers:
            lg.out(8, '        found FAILED Customers: %d')
            for idurl in failed_customers:
                current_customers.remove(idurl)
                lg.out(8, '            %r' % idurl)
            self.automat('space-overflow', (
                space_dict, free_space, consumed_bytes, current_customers, failed_customers))
            return
        used_space_ratio_dict = accounting.calculate_customers_usage_ratio(space_dict, used_dict)
        customers_sorted = sorted(current_customers,
                                  key=lambda idurl: used_space_ratio_dict[idurl],)
        while len(customers_sorted) > 0 and consumed_bytes > donated_bytes:
            idurl = customers_sorted.pop()
            allocated_bytes = int(space_dict[idurl])
            consumed_bytes -= allocated_bytes
            space_dict.pop(idurl)
            failed_customers.add(idurl)
            current_customers.remove(idurl)
            lg.out(8, '        customer %s will be REMOVED' % idurl)
        free_space = donated_bytes - consumed_bytes
        lg.out(8, '        SPACE NOT ENOUGH !!!!!!!!!!')
        self.automat('space-overflow', (
            space_dict, free_space, consumed_bytes, current_customers, failed_customers))

    def doRemoveCustomers(self, *args, **kwargs):
        """
        Action method.
        """
        space_dict, free_space, spent_bytes, current_customers, removed_customers = args[0]
        for customer_idurl in removed_customers:
            contactsdb.remove_customer_meta_info(customer_idurl)
        accounting.write_customers_quotas(space_dict, free_space)
        contactsdb.update_customers(current_customers)
        contactsdb.save_customers()

    def doSendRejectService(self, *args, **kwargs):
        """
        Action method.
        """
        space_dict, free_space, spent_bytes, current_customers, removed_customers = args[0]
        for customer_idurl in removed_customers:
            p2p_service.SendFailNoRequest(customer_idurl, packetid.UniqueID(), 'service rejected')
            events.send('existing-customer-terminated', dict(idurl=customer_idurl))
        self.automat('packets-sent')

    def doRestartLocalTester(self, *args, **kwargs):
        """
        Action method.
        """
        from supplier import local_tester
        local_tester.TestSpaceTime()
