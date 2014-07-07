#!/usr/bin/python
#fire_hire.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: fire_hire
.. role:: red

.. raw:: html

    <a href="http://bitpie.net/automats/fire_hire/fire_hire.png" target="_blank">
    <img src="http://bitpie.net/automats/fire_hire/fire_hire.png" style="max-width:100%;">
    </a>
    
We contact BitPie.NET for list of nodes we have hired
and we can also replace any node (fire & hire someone else at once)
by contacting DHN and asking for replacement.

If at some point we are not getting good answers from a node
for too long we need to replace him and reconstruct the data
he was holding. This is fire_hire and then scrubbing.

Probably if we try to contact someone for 48 hours and can not,
we want to give up on them.

User can use GUI to fire_hire at any time.

Automatically fire if right after we ask a supplier for a BigPacket,
he turns around and asks us for it (like he does not have it).

Our regular code would not do this, but an evil modified version might
try to get away with not holding any data by just getting it from us
anytime we asked for it. So we can not allow this cheat to work.

We ask for lists of files they have for us and keep these in settings.SuppliersDir()/supplieridurl
These should be updated at least every night.
If a supplier has not given us a list for several days he is a candidate for firing.

Transport_control should keep statistics on how fast different nodes are.
We could fire a slow node.

Restore can keep track of who did not answer in time to be part of raidread, and they can
be a candidate for firing.

The fire packet needs to use IDURL so that if there is a retransmission of the "fire" request
we just send new "list suppliers" again.

Task list
1) fire inactive suppliers (default is 48 hours)
2) fire suppliers with low rating (less than 25% by default)
3) test if supplier is "evil modifed"
4) test ListFiles peridoically
5) fire slow nodes

The ``fire_hire()`` automat is our "human resources department".
The objective is to discharge the outsiders among suppliers - 
those who are offline for too long or who holds the least of our data.

Each time the machine is started, 
it chooses the weakest supplier and sends a request to the Central server 
to the dismissal of that supplier.
In response, the Central server sends a new list 
in which there is a new supplier instead dismissed.

If all providers are reliable enough - machine will not work and will reset.


EVENTS:
    * :red:`fire-him-now`
    * :red:`init`
    * :red:`made-decision`
    * :red:`restart`
    * :red:`search-failed`
    * :red:`supplier-connected`
    * :red:`supplier-disconnected`
    * :red:`timer-15sec`
"""

import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in fire_hire.py')

import lib.dhnio as dhnio
import lib.misc as misc
import lib.settings as settings
import lib.contacts as contacts
import lib.automats as automats

import lib.automat as automat

import backup_monitor
import supplier_finder
import supplier_connector

#-------------------------------------------------------------------------------

_FireHire = None

#-------------------------------------------------------------------------------

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _FireHire
    if _FireHire is None:
        _FireHire = FireHire('fire_hire', 'READY', 4)
    if event is not None:
        _FireHire.automat(event, arg)
    return _FireHire

class FireHire(automat.Automat):
    """
    This class implements all the functionality of the ``fire_hire()`` state machine.
    """

    timers = {
        'timer-15sec': (15.0, ['FIRE_MANY']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.lastFireTime = 0 # time.time()
        self.dismiss_list = []
        self.dismiss_results = []
        self.new_suppliers = []

    def state_changed(self, oldstate, newstate):
        """
        Method to to catch the moment when automat's state were changed.
        """
        automats.set_global_state('FIREHIRE ' + newstate)

    def A(self, event, arg):
        #---READY---
        if self.state == 'READY':
            if event == 'restart' and not self.isTimePassed(arg) and not self.isMoreNeeded(arg) :
                backup_monitor.A('fire-hire-finished')
            elif event == 'fire-him-now' :
                self.state = 'HIRE_ONE'
                self.doRememberDismissSuppliers(arg)
                supplier_finder.A('start')
            elif event == 'restart' and self.isMoreNeeded(arg) :
                self.state = 'HIRE_ONE'
                supplier_finder.A('start')
            elif event == 'restart' :
                self.state = 'DECISION?'
                self.doDecideToDismissSuppliers(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'READY'
                self.doInit(arg)
        #---DECISION?---
        elif self.state == 'DECISION?':
            if event == 'made-decision' and not self.isSomeoneToDismiss(arg) :
                self.state = 'READY'
                backup_monitor.A('fire-hire-finished')
            elif event == 'made-decision' and self.isSomeoneToDismiss(arg) and self.isMoreNeeded(arg) :
                self.state = 'HIRE_ONE'
                self.doRememberDismissSuppliers(arg)
                supplier_finder.A('start')
            elif event == 'made-decision' and self.isSomeoneToDismiss(arg) and not self.isMoreNeeded(arg) :
                self.state = 'FIRE_MANY'
                self.doRememberDismissSuppliers(arg)
                self.doRemoveSuppliers(arg)
                self.doDisconnectSuppliers(arg)
        #---HIRE_ONE---
        elif self.state == 'HIRE_ONE':
            if event == 'supplier-connected' and self.isMoreNeeded(arg) :
                self.doSubstituteSupplier(arg)
                supplier_finder.A('start')
            elif event == 'search-failed' :
                self.state = 'READY'
                self.doClearDismissList(arg)
                backup_monitor.A('fire-hire-finished')
                self.doRestartLater(arg)
            elif event == 'supplier-connected' and not self.isMoreNeeded(arg) and not self.isSomeoneToDismiss(arg) :
                self.state = 'READY'
                self.doSubstituteSupplier(arg)
                backup_monitor.A('hire-new-supplier')
            elif event == 'supplier-connected' and not self.isMoreNeeded(arg) and self.isSomeoneToDismiss(arg) :
                self.state = 'FIRE_MANY'
                self.doSubstituteSupplier(arg)
                self.doDisconnectSuppliers(arg)
        #---FIRE_MANY---
        elif self.state == 'FIRE_MANY':
            if event == 'supplier-disconnected' and self.isAllDismissed(arg) :
                self.state = 'READY'
                self.doCloseSupplierConnector(arg)
                self.doClearDismissList(arg)
                backup_monitor.A('hire-new-supplier')
            elif event == 'supplier-disconnected' and not self.isAllDismissed(arg) :
                self.doCloseSupplierConnector(arg)
            elif event == 'timer-15sec' :
                self.state = 'READY'
                self.doCloseConnectors(arg)
                self.doClearDismissList(arg)

    def isTimePassed(self, arg):
        # dhnio.Dprint(6, 'fire_hire.isTimePassed last "fire" was %d minutes ago' % ((time.time() - self.lastFireTime) / 60.0))
        return time.time() - self.lastFireTime > settings.FireHireMinimumDelay()

    def isMoreNeeded(self, arg):
        """
        Condition method.
        """
        # dhnio.Dprint(10, 'fire_hire.isMoreNeeded current=%d dismiss=%d needed=%d' % (
        #     contacts.numSuppliers(), len(self.dismiss_list), settings.getCentralNumSuppliers()))
        if '' in contacts.getSupplierIDs():
            dhnio.Dprint(4, 'fire_hire.isMoreNeeded WARNING found empty suppliers!!!')
            return True
        return contacts.numSuppliers() - len(self.dismiss_list) < settings.getCentralNumSuppliers()
        
    def isAllDismissed(self, arg):
        """
        Condition method.
        """
        return len(self.dismiss_list) == len(self.dismiss_results)

    def isSomeoneToDismiss(self, arg):
        """
        Condition method.
        """
        return len(arg) > 0

    def doInit(self, arg):
        """
        Action method.
        """

    def doDecideToDismissSuppliers(self, arg):
        """
        Action method.
        """
        result = set()
        for supplier_idurl in contacts.getSupplierIDs():
            sc = supplier_connector.by_idurl(supplier_idurl)
            if not sc:
                continue
            if sc.state == 'NO_SERVICE':
                result.add(supplier_idurl)
        if contacts.numSuppliers() > settings.getCentralNumSuppliers():
            for supplier_index in range(settings.getCentralNumSuppliers(), contacts.numSuppliers()):
                result.add(contacts.getSupplierID(supplier_index))
        result = list(result) 
        dhnio.Dprint(10, 'fire_hire.doDecideToDismissSuppliers %s' % result)
        self.automat('made-decision', result)

    def doRememberDismissSuppliers(self, arg):
        """
        Action method.
        """
        self.dismiss_list = arg

    def doSubstituteSupplier(self, arg):
        """
        Action method.
        """
        new_idurl = arg
        current_suppliers = list(contacts.getSupplierIDs())
        if new_idurl in current_suppliers:
            raise  Exception('%s is already supplier' % new_idurl)
        position = -1
        old_idurl = None
        for i in range(len(current_suppliers)):
            if current_suppliers[i] in self.dismiss_list:
                # self.dismiss_list.remove(current_suppliers[i])
                position = i
                old_idurl = current_suppliers[i]
                break
            if current_suppliers[i].strip() == '':
                position = i
                break
        if position < 0:
            current_suppliers.append(new_idurl)
        else:
            current_suppliers[position] = new_idurl
        contacts.setSupplierIDs(current_suppliers)
        contacts.saveSupplierIDs()
        misc.writeSupplierData(new_idurl, 'connected', time.strftime('%d%m%y %H:%M:%S'))
        import backup_control
        backup_control.SetSupplierList(current_suppliers)
        import webcontrol
        webcontrol.OnListSuppliers()
        if position < 0:
            dhnio.Dprint(2, '!!!!!!!!!!! ADD SUPPLIER : %s' % (new_idurl))
        else:
            if old_idurl:
                dhnio.Dprint(2, '!!!!!!!!!!! SUBSTITUTE SUPPLIER %d : %s->%s' % (position, old_idurl, new_idurl))
            else:
                dhnio.Dprint(2, '!!!!!!!!!!! REPLACE EMPTY SUPPLIER %d : %s' % (position, new_idurl))

    def doRemoveSuppliers(self, arg):
        """
        Action method.
        """
        current_suppliers = contacts.getSupplierIDs()
        desired_suppliers = settings.getCentralNumSuppliers()
        if len(current_suppliers) <= desired_suppliers:
            dhnio.Dprint(4, 'fire_hire.doRemoveSuppliers WARNING must have more suppliers')
            return
        for supplier_idurl in self.dismiss_list:
            current_suppliers.remove(supplier_idurl)
            misc.writeSupplierData(supplier_idurl, 'disconnected', time.strftime('%d%m%y %H:%M:%S'))
        contacts.setSupplierIDs(current_suppliers)
        contacts.saveSupplierIDs()
        import backup_control
        backup_control.SetSupplierList(current_suppliers)
        import webcontrol
        webcontrol.OnListSuppliers()
        dhnio.Dprint(2, '!!!!!!!!!!! REMOVE SUPPLIERS : %d' % len(self.dismiss_list))

    def doDisconnectSuppliers(self, arg):
        """
        Action method.
        """
        # dhnio.Dprint(10, 'fire_hire.doDismissSuppliers %r' % self.dismiss_list)
        for supplier_idurl in self.dismiss_list:
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc:
                sc.automat('disconnect')
            else:
                raise Exception('supplier_connector must exist')        

    def doCloseSupplierConnector(self, arg):
        """
        Action method.
        """
        supplier_idurl = arg
        sc = supplier_connector.by_idurl(supplier_idurl)
        if sc:
            sc.automat('shutdown')
        else:
            raise Exception('supplier_connector must exist')

    def doCloseConnectors(self, arg):
        """
        Action method.
        """
        for supplier_idurl in self.dismiss_list:
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc:
                sc.automat('shutdown')
            else:
                raise Exception('supplier_connector must exist')        
        
    def doClearDismissList(self, arg):
        """
        Action method.
        """
        self.dismiss_list = []
        self.dismiss_results = []
        
    def doRestartLater(self, arg):
        """
        Action method.
        """
        reactor.callLater(10, self.automat, 'restart')




#def WhoIsLost():
#    """
#    If we have more than 50% data packets lost to someone and it was a long story - fire this guy.
#    We check this first, because this is more important than other things.
#    Well, many things can be a reason:
#    * refuse storage service,
#    * disconnected,
#    * slow connection, 
#    * old code, 
#    * too many network errors, 
#    * timeout during sending
#    If we can not send him our data or retreive it back - how can we do a backups to him even if he is online?
#    """
#
#    for supplier_idurl in contacts.getSupplierIDs():
#    # for sc in supplier_connector.connectors().values():
#        sc = supplier_connector.by_idurl(supplier_idurl)
#        if sc and sc.state == 'NO_SERVICE':
#            dhnio.Dprint(6, 'fire_hire.WhoIsLost !!!!!!!! %s : no service' % sc.idurl)
#            return 'found-one-lost-supplier', sc.idurl 
#    unreliable_supplier = None
#    most_fails = 0.0
#    for supplierNum in range(contacts.numSuppliers()):
#        idurl = contacts.getSupplierID(supplierNum)
#        if not idurl:
#            continue 
#        if not data_sender.statistic().has_key(idurl):
#            continue
#        stats = data_sender.statistic()[idurl]
#        total = stats[0] + stats[1]
#        failed = stats[1]
#        if total > 10:
#            failed_percent = failed / total
#            if failed_percent > 0.5:
#                if most_fails < failed_percent:
#                    most_fails = failed_percent
#                    unreliable_supplier = idurl
#    if unreliable_supplier:
#        return 'found-one-lost-supplier', unreliable_supplier
        
#    # we only fire offline suppliers
#    offline_suppliers = {}

#    # ask backup_monitor about current situation
#    # check every offline supplier and see how many files he keep at the moment
#    for supplierNum in range(contacts.numSuppliers()):
#        idurl = contacts.getSupplierID(supplierNum)
#        if not idurl:
#            continue
#        if contact_status.isOnline(idurl):
#            continue
#        blocks, total, stats = backup_matrix.GetSupplierStats(supplierNum)
#        rating = 0 if total == 0 else blocks / total 
#        offline_suppliers[idurl] = rating

#    # if all suppliers are online - we are very happy - no need to fire anybody! 
#    if len(offline_suppliers) == 0:
#        dhnio.Dprint(4, 'fire_hire.WhoIsLost no offline suppliers, Cool!')
#        return 'not-found-lost-suppliers', ''
    
#    # sort users - we always fire worst supplier 
#    rating = offline_suppliers.keys()
#    rating.sort(key=lambda idurl: offline_suppliers[idurl])
#    lost_supplier_idurl = rating[0]

#    # we do not want to fire this man if he store at least 50% of our files
#    # the fact that he is offline is not enough to fire him!
#    if offline_suppliers[lost_supplier_idurl] < 0.5 and backup_fs.sizebackups() > 0:
#        dhnio.Dprint(4, 'fire_hire.WhoIsLost !!!!!!!! %s is offline and keeps only %d%% of our data' % (
#            nameurl.GetName(lost_supplier_idurl), 
#            int(offline_suppliers[lost_supplier_idurl] * 100.0)))
#        return 'found-one-lost-supplier', lost_supplier_idurl
    
#    # but if we did not saw him for a long time - we do not want him for sure
#    if time.time() - ratings.connected_time(lost_supplier_idurl) > 60 * 60 * 24 * 2:
#        dhnio.Dprint(2, 'fire_hire.WhoIsLost !!!!!!!! %s is offline and keeps %d%% of our data, but he was online %d hours ago' % (
#            nameurl.GetName(lost_supplier_idurl), 
#            int(offline_suppliers[lost_supplier_idurl] * 100.0),
#            int((time.time() - ratings.connected_time(lost_supplier_idurl)) * 60 * 60),))
#        return 'found-one-lost-supplier', lost_supplier_idurl
    
#    dhnio.Dprint(2, 'fire_hire.WhoIsLost some people is not here, but we did not found the bad guy at this time')
#    return 'not-found-lost-suppliers', ''


def GetLastFireTime():
    """
    This method returns a time moment when last time some supplier was replaced. 
    """
    return A().lastFireTime


def ClearLastFireTime():
    """
    """
    A().lastFireTime = 0



