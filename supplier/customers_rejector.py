

"""
.. module:: customers_rejector
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

import os

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat

from system import bpio

from main import settings

from contacts import contactsdb

from lib import packetid

from p2p import p2p_service

#------------------------------------------------------------------------------ 

_CustomersRejector = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _CustomersRejector
    if _CustomersRejector is None:
        # set automat name and starting state here
        _CustomersRejector = CustomersRejector('customers_rejector', 'READY', 4)
    if event is not None:
        _CustomersRejector.automat(event, arg)
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
    This class implements all the functionality of the ``customers_rejector()`` state machine.

    """

    timers = {
        'timer-10sec': (10.0, ['REJECT_GUYS']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """

    def A(self, event, arg):
        #---READY---
        if self.state == 'READY':
            if event == 'restart' :
                self.state = 'CAPACITY?'
                self.doTestMyCapacity(arg)
        #---CAPACITY?---
        elif self.state == 'CAPACITY?':
            if event == 'space-enough' :
                self.state = 'READY'
            elif event == 'space-overflow' :
                self.state = 'REJECT_GUYS'
                self.doRemoveCustomers(arg)
                self.doSendRejectService(arg)
        #---REJECT_GUYS---
        elif self.state == 'REJECT_GUYS':
            if event == 'restart' :
                self.state = 'CAPACITY?'
                self.doTestMyCapacity(arg)
            elif event == 'packets-sent' :
                self.state = 'READY'
                self.doRestartLocalTester(arg)

    def doTestMyCapacity(self, arg):
        """
        Action method.
            - donated_bytes : you set this in the config
            - spent_bytes : how many space is taken from you by other users right now
            - free_bytes = donated_bytes - spent_bytes : not yet allocated space
            - used_bytes : size of all files, which you store on your disk for your customers    
        """
        current_customers = contactsdb.customers()
        removed_customers = []
        spent_bytes = 0
        donated_bytes = settings.getDonatedBytes()
        if os.path.isfile(settings.CustomersSpaceFile()):
            space_dict = bpio._read_dict(settings.CustomersSpaceFile(), {})
        else:
            space_dict = {'free': donated_bytes}
        used_dict = bpio._read_dict(settings.CustomersUsedSpaceFile(), {})
        lg.out(8, 'customers_rejector.doTestMyCapacity donated=%d' % donated_bytes)
        try: 
            int(space_dict['free'])
            for idurl, customer_bytes in space_dict.items():
                if idurl != 'free':
                    spent_bytes += int(customer_bytes)
        except:
            lg.exc()
            space_dict = {'free': donated_bytes}
            spent_bytes = 0
            removed_customers = list(current_customers)
            current_customers = []
            self.automat('space-overflow', (space_dict, spent_bytes, current_customers, removed_customers))
            return
        lg.out(8, '        spent=%d' % spent_bytes)
        if spent_bytes < donated_bytes:
            space_dict['free'] = donated_bytes - spent_bytes
            bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
            lg.out(8, '        space is OK !!!!!!!!')
            self.automat('space-enough')
            return
        used_space_ratio_dict = {}
        for customer_pos in xrange(contactsdb.num_customers()):
            customer_idurl = contactsdb.customer(customer_pos)
            try:
                allocated_bytes = int(space_dict[customer_idurl])
            except:
                if customer_idurl in current_customers:
                    current_customers.remove(customer_idurl)
                    removed_customers.append(customer_idurl)
                else:
                    lg.warn('%s not customers' % customer_idurl)
                lg.warn('%s allocated space unknown' % customer_idurl)
                continue 
            if allocated_bytes <= 0:
                if customer_idurl in current_customers:
                    current_customers.remove(customer_idurl)
                    removed_customers.append(customer_idurl)
                else:
                    lg.warn('%s not customers' % customer_idurl)
                lg.warn('%s allocated_bytes==0' % customer_idurl)
                continue
            try:
                files_size = int(used_dict.get(customer_idurl, 0))
                ratio = float(files_size) / float(allocated_bytes)
            except:
                if customer_idurl in current_customers:
                    current_customers.remove(customer_idurl)
                    removed_customers.append(customer_idurl)
                else:
                    lg.warn('%s not customers' % customer_idurl)
                lg.warn('%s used_dict have wrong value' % customer_idurl)
                continue
            if ratio > 1.0:
                if customer_idurl in current_customers:
                    current_customers.remove(customer_idurl)
                    removed_customers.append(customer_idurl)
                else:
                    lg.warn('%s not customers' % customer_idurl)
                spent_bytes -= allocated_bytes
                lg.warn('%s space overflow, where is bptester?' % customer_idurl)
                continue
            used_space_ratio_dict[customer_idurl] = ratio
        customers_sorted = sorted(current_customers, 
            key=lambda i: used_space_ratio_dict[i],)
        while len(customers_sorted) > 0:
            customer_idurl = customers_sorted.pop()
            allocated_bytes = int(space_dict[customer_idurl])
            spent_bytes -= allocated_bytes
            space_dict.pop(customer_idurl)
            current_customers.remove(customer_idurl)
            removed_customers.append(customer_idurl)
            lg.out(8, '        customer %s REMOVED' % customer_idurl)
            if spent_bytes < donated_bytes:
                break
        space_dict['free'] = donated_bytes - spent_bytes
        lg.out(8, '        SPACE NOT ENOUGH !!!!!!!!!!')
        self.automat('space-overflow', (space_dict, spent_bytes, current_customers, removed_customers))
        
    def doRemoveCustomers(self, arg):
        """
        Action method.
        """
        space_dict, spent_bytes, current_customers, removed_customers = arg
        contactsdb.update_customers(current_customers)
        contactsdb.save_customers()
        bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
        
    def doSendRejectService(self, arg):
        """
        Action method.
        """
        space_dict, spent_bytes, current_customers, removed_customers = arg
        for customer_idurl in removed_customers:
            p2p_service.SendFailNoRequest(customer_idurl, packetid.UniqueID(), 'service rejected')
        
    def doRestartLocalTester(self, arg):
        """
        Action method.
        """
        from supplier import local_tester
        local_tester.TestSpaceTime()


