

"""
.. module:: customers_rejector
.. role:: red

BitPie.NET customers_rejector() Automat

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

import lib.automat as automat
import lib.bpio as bpio
import lib.settings as settings
import lib.diskspace as diskspace
import lib.contacts as contacts

import p2p_service
import local_tester

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

    def state_changed(self, oldstate, newstate):
        """
        Method to to catch the moment when automat's state were changed.
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
        current_customers = contacts.getCustomerIDs()
        removed_customers = []
        spent_bytes = 0
        donated_bytes = settings.getDonatedBytes()
        space_dict = bpio._read_dict(settings.CustomersSpaceFile(), {})
        used_dict = bpio._read_dict(settings.CustomersUsedSpaceFile(), {})
        bpio.log(8, 'customers_rejector.doTestMyCapacity donated=%d' % donated_bytes)
        try: 
            int(space_dict['free'])
            for idurl, customer_bytes in space_dict.items():
                if idurl != 'free':
                    spent_bytes += int(customer_bytes)
        except:
            bpio.exception()
            space_dict = {'free': donated_bytes}
            spent_bytes = 0
            removed_customers = list(current_customers)
            current_customers = []
            self.automat('space-overflow', (space_dict, spent_bytes, current_customers, removed_customers))
            return
        bpio.log(8, '        spent=%d' % spent_bytes)
        if spent_bytes < donated_bytes:
            space_dict['free'] = donated_bytes - spent_bytes
            bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
            bpio.log(8, '        space is OK !!!!!!!!')
            self.automat('space-enough')
            return
        used_space_ratio_dict = {}
        for customer_pos in xrange(contacts.numCustomers()):
            customer_idurl = contacts.getCustomerID(customer_pos)
            try:
                allocated_bytes = int(space_dict[customer_idurl])
            except:
                if customer_idurl in current_customers:
                    current_customers.remove(customer_idurl)
                    removed_customers.append(customer_idurl)
                else:
                    bpio.log(4, 'customers_rejector.doTestMyCapacity WARNING %s not customers' % customer_idurl)
                bpio.log(4, 'customers_rejector.doTestMyCapacity WARNING %s allocated space unknown' % customer_idurl)
                continue 
            if allocated_bytes <= 0:
                if customer_idurl in current_customers:
                    current_customers.remove(customer_idurl)
                    removed_customers.append(customer_idurl)
                else:
                    bpio.log(4, 'customers_rejector.doTestMyCapacity WARNING %s not customers' % customer_idurl)
                bpio.log(4, 'customers_rejector.doTestMyCapacity WARNING %s allocated_bytes==0' % customer_idurl)
                continue
            try:
                files_size = int(used_dict.get(customer_idurl, 0))
                ratio = float(files_size) / float(allocated_bytes)
            except:
                if customer_idurl in current_customers:
                    current_customers.remove(customer_idurl)
                    removed_customers.append(customer_idurl)
                else:
                    bpio.log(4, 'customers_rejector.doTestMyCapacity WARNING %s not customers' % customer_idurl)
                bpio.log(4, 'customers_rejector.doTestMyCapacity WARNING %s used_dict have wrong value' % customer_idurl)
                continue
            if ratio > 1.0:
                if customer_idurl in current_customers:
                    current_customers.remove(customer_idurl)
                    removed_customers.append(customer_idurl)
                else:
                    bpio.log(4, 'customers_rejector.doTestMyCapacity WARNING %s not customers' % customer_idurl)
                spent_bytes -= allocated_bytes
                bpio.log(4, 'customers_rejector.doTestMyCapacity WARNING %s space overflow, where is bptester?' % customer_idurl)
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
            bpio.log(8, '        customer %s REMOVED' % customer_idurl)
            if spent_bytes >= donated_bytes:
                break
        space_dict['free'] = donated_bytes - spent_bytes
        bpio.log(8, '        SPACE NOT ENOUGH !!!!!!!!!!')
        self.automat('space-overflow', (space_dict, spent_bytes, current_customers, removed_customers))
        
    def doRemoveCustomers(self, arg):
        """
        Action method.
        """
        space_dict, spent_bytes, current_customers, removed_customers = arg
        contacts.setCustomerIDs(current_customers)
        contacts.saveCustomerIDs()
        bpio._write_dict(settings.CustomersSpaceFile(), space_dict)
        
    def doSendRejectService(self, arg):
        """
        Action method.
        """
        space_dict, spent_bytes, current_customers, removed_customers = arg
        for customer_idurl in removed_customers:
            p2p_service.SendFail(customer_idurl, 'customer removed')
        
    def doRestartLocalTester(self, arg):
        """
        Action method.
        """
        local_tester.TestSpaceTime()


