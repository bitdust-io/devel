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
    * :red:`contracts-verified`
    * :red:`customers-rejected`
    * :red:`found-idle-customers`
    * :red:`found-unpaid-customers`
    * :red:`no-idle-customers`
    * :red:`restart`
    * :red:`space-enough`
    * :red:`space-overflow`
    * :red:`start`
    * :red:`timer-1hour`
"""

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 8

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.system import bpio

from bitdust.main import settings
from bitdust.main import config

from bitdust.interface import api

from bitdust.contacts import contactsdb

from bitdust.lib import utime

from bitdust.services import driver

from bitdust.p2p import ratings

from bitdust.storage import accounting

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
        _CustomersRejector = CustomersRejector(
            name='customers_rejector',
            state='READY',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
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
        'timer-1hour': (3600, ['READY']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """

    def A(self, event, *args, **kwargs):
        #---READY---
        if self.state == 'READY':
            if event == 'timer-1hour' or event == 'start' or event == 'restart':
                self.state = 'CAPACITY?'
                self.doTestMyCapacity(*args, **kwargs)
        #---CAPACITY?---
        elif self.state == 'CAPACITY?':
            if event == 'space-overflow':
                self.state = 'REJECT!'
                self.doRemoveCustomers(*args, **kwargs)
            elif event == 'space-enough':
                self.state = 'CONTRACTS?'
                self.doVerifyStorageContracts(*args, **kwargs)
        #---REJECT!---
        elif self.state == 'REJECT!':
            if event == 'restart':
                self.state = 'CAPACITY?'
                self.doTestMyCapacity(*args, **kwargs)
            elif event == 'customers-rejected':
                self.state = 'READY'
                self.doRestartLocalTester(*args, **kwargs)
                self.doRestartLater(*args, **kwargs)
        #---IDLE?---
        elif self.state == 'IDLE?':
            if event == 'found-idle-customers':
                self.state = 'REJECT!'
                self.doRemoveCustomers(*args, **kwargs)
            elif event == 'restart':
                self.state = 'CAPACITY?'
                self.doTestMyCapacity(*args, **kwargs)
            elif event == 'no-idle-customers':
                self.state = 'READY'
                self.doCountStatistics(*args, **kwargs)
        #---CONTRACTS?---
        elif self.state == 'CONTRACTS?':
            if event == 'found-unpaid-customers':
                self.state = 'REJECT!'
                self.doRemoveCustomers(*args, **kwargs)
            elif event == 'contracts-verified':
                self.state = 'IDLE?'
                self.doTestIdleDays(*args, **kwargs)
        return None

    def doTestMyCapacity(self, *args, **kwargs):
        """
        Here are some values.

        + donated_bytes : you set this in the settings
        + consumed_bytes : how many space was taken from you by other users
        + free_bytes = donated_bytes - consumed_bytes : not yet allocated space
        + used_bytes : size of all files, which you store on your disk for your customers
        + ratio : currently used space compared to consumed space
        """
        if _Debug:
            lg.out(_DebugLevel, 'customers_rejector.doTestMyCapacity')
        if bpio.Android():
            #TODO:
            self.automat('space-enough')
            return
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
            lg.info('storage quota checks succeed, all customers are verified')
            self.automat('space-enough')
            return
        if failed_customers:
            for idurl in failed_customers:
                lg.warn('customer %r failed storage quota verification' % idurl)
                current_customers.remove(idurl)
            self.automat('space-overflow', failed_customers)
            return
        used_space_ratio_dict = accounting.calculate_customers_usage_ratio(space_dict, used_dict)
        customers_sorted = sorted(
            current_customers,
            key=lambda idurl: used_space_ratio_dict[idurl],
        )
        while len(customers_sorted) > 0 and consumed_bytes > donated_bytes:
            idurl = customers_sorted.pop()
            allocated_bytes = int(space_dict[idurl])
            consumed_bytes -= allocated_bytes
            space_dict.pop(idurl)
            failed_customers.add(idurl)
            current_customers.remove(idurl)
            lg.warn('customer %r will be removed because of storage quota overflow' % idurl)
        free_space = donated_bytes - consumed_bytes
        self.automat('space-overflow', failed_customers)

    def doTestIdleDays(self, *args, **kwargs):
        """
        Action method.
        """
        dead_customers = []
        customer_idle_days = config.conf().getInt('services/customer-patrol/customer-idle-days', 0)
        if not customer_idle_days:
            self.automat('no-idle-customers')
            return
        for customer_idurl in contactsdb.customers():
            if driver.is_on('service_supplier_contracts'):
                from bitdust.supplier import storage_contract
                if storage_contract.is_current_customer_contract_active(customer_idurl):
                    continue
            connected_time = ratings.connected_time(customer_idurl.to_bin())
            if connected_time is None:
                lg.warn('last connected_time for customer %r is unknown, rejecting customer' % customer_idurl)
                dead_customers.append(customer_idurl)
                continue
            if utime.utcnow_to_sec1970() - connected_time > customer_idle_days*24*60*60:
                lg.warn('customer %r connected last time %r seconds ago, rejecting customer' % (customer_idurl, utime.utcnow_to_sec1970() - connected_time))
                dead_customers.append(customer_idurl)
        if dead_customers:
            lg.warn('found idle customers: %r' % dead_customers)
            self.automat('found-idle-customers', dead_customers)
        else:
            lg.info('all customers has some activity recently, no idle customers found')
            self.automat('no-idle-customers')

    def doRestartLocalTester(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.supplier import local_tester
        local_tester.TestSpaceTime()

    def doRestartLater(self, *args, **kwargs):
        """
        Action method.
        """
        self.automat('restart', delay=5)

    def doVerifyStorageContracts(self, *args, **kwargs):
        """
        Action method.
        """
        rejected_customers = []
        if driver.is_on('service_supplier_contracts'):
            from bitdust.supplier import storage_contract
            rejected_customers = storage_contract.verify_all_current_customers_contracts()
        if rejected_customers:
            lg.warn('found unpaid customers: %r' % rejected_customers)
            # TODO: disabled for now...
            # self.automat('found-unpaid-customers', rejected_customers)
            self.automat('contracts-verified')
        else:
            lg.info('all customers have valid contracts')
            self.automat('contracts-verified')

    def doCountStatistics(self, *args, **kwargs):
        """
        Action method.
        """

    def doRemoveCustomers(self, *args, **kwargs):
        """
        Action method.
        """
        removed_customers = args[0]
        for customer_idurl in removed_customers:
            api.customer_reject(customer_id=customer_idurl, erase_customer_key=True)
        self.automat('customers-rejected', removed_customers)
