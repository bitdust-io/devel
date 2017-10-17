#!/usr/bin/python
# fire_hire.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (fire_hire.py) is part of BitDust Software.
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
#

"""
.. module:: fire_hire

.. role:: red

.. raw:: html

    <a href="http://bitdust.io/automats/fire_hire/fire_hire.png" target="_blank">
    <img src="http://bitdust.io/automats/fire_hire/fire_hire.png" style="max-width:100%;">
    </a>

If at some point we are not getting good answers from a node
for too long we need to replace him and reconstruct the data
he was holding. This is fire & hire and then rebuilding and scrubbing.

Probably if we try to contact someone for 48 hours and can not,
we want to give up on them.

User can use GUI to fire & hire at any time.

Automatically fire if right after we ask a supplier for a BigPacket,
he turns around and asks us for it (like he does not have it).

Our regular code would not do this, but an evil modified version might
try to get away with not holding any data by just getting it from us
any time we asked for it. So we can not allow this cheat to work.

We ask for lists of files they have for us and keep these in
``settings.SuppliersDir()/[supplier idurl]``
These should be updated at least every night.
If a supplier has not given us a list for several days
he is a candidate for firing.

Gateway code keeps statistics on how fast different nodes are.
We could fire a slowest node periodically.

Restore can keep track of who did not answer in time to be part of raidread,
and they can be a candidate for firing.

The fire packet needs to use IDURL so that if there is a retransmission of the "fire" request
we just send new "list suppliers" again.

Task list
1) fire inactive suppliers (default is 48 hours)
2) fire suppliers with low rating (less than 25% by default)
3) test if supplier is "evil modified"
4) test ListFiles periodically
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
    * :red:`init`
    * :red:`instant`
    * :red:`made-decision`
    * :red:`restart`
    * :red:`search-failed`
    * :red:`supplier-connected`
    * :red:`supplier-state-changed`
    * :red:`timer-15sec`
"""

#------------------------------------------------------------------------------

import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in fire_hire.py')

#------------------------------------------------------------------------------

from logs import lg

from automats import global_state
from automats import automat

from lib import misc

from lib import diskspace

from main import settings
from main import events

from contacts import contactsdb

from services import driver

from customer import supplier_finder
from customer import supplier_connector

from userid import my_id

#-------------------------------------------------------------------------

_FireHire = None
_LastFireTime = 0
_SuppliersToFire = []

#-------------------------------------------------------------------------


def GetLastFireTime():
    """
    This method returns a time moment when last time some supplier was
    replaced.
    """
    global _LastFireTime
    return _LastFireTime


def ClearLastFireTime():
    """
    """
    _LastFireTime = 0


def AddSupplierToFire(idurl):
    """
    """
    global _SuppliersToFire
    _SuppliersToFire.append(idurl)

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _FireHire
    if _FireHire is None:
        _FireHire = FireHire('fire_hire', 'READY', 8)
    if event is not None:
        _FireHire.automat(event, arg)
    return _FireHire


def Destroy():
    """
    Destroy the state machine and remove the instance from memory.
    """
    global _FireHire
    if _FireHire is None:
        return
    _FireHire.destroy()
    del _FireHire
    _FireHire = None

#------------------------------------------------------------------------------


class FireHire(automat.Automat):
    """
    This class implements all the functionality of the ``fire_hire()`` state
    machine.
    """

    timers = {
        'timer-15sec': (15.0, ['FIRE_MANY', 'SUPPLIERS?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        # self.lastFireTime = 0 # time.time()
        self.connect_list = []
        self.dismiss_list = []
        self.dismiss_results = []
        self.new_suppliers = []
        self.configs = (None, None)
        self.restart_interval = 1.0
        self.restart_task = None

    def state_changed(self, oldstate, newstate, event, arg):
        """
        This method intended to catch the moment when automat's state were
        changed.
        """
        global_state.set_global_state('FIREHIRE ' + newstate)
        if newstate == 'READY':
            self.automat('instant')

    def A(self, event, arg):
        #---READY---
        if self.state == 'READY':
            if (event == 'restart' or (event == 'instant' and self.NeedRestart)) and not (
                    self.isConfigChanged(arg) and self.isExistSomeSuppliers(arg)):
                self.state = 'DECISION?'
                self.NeedRestart = False
                self.doDecideToDismiss(arg)
            elif (event == 'restart' or (event == 'instant' and self.NeedRestart)) and self.isConfigChanged(arg) and self.isExistSomeSuppliers(arg):
                self.state = 'SUPPLIERS?'
                self.NeedRestart = False
                self.doSaveConfig(arg)
                self.doConnectSuppliers(arg)
        #---DECISION?---
        elif self.state == 'DECISION?':
            if event == 'made-decision' and self.isSomeoneToDismiss(arg) and not self.isMoreNeeded(arg):
                self.state = 'FIRE_MANY'
                self.doRememberSuppliers(arg)
                self.doRemoveSuppliers(arg)
                self.doDisconnectSuppliers(arg)
            elif event == 'restart':
                self.NeedRestart = True
            elif event == 'made-decision' and not self.isMoreNeeded(arg) and not self.isSomeoneToDismiss(arg):
                self.state = 'READY'
                self.doNotifyFinished(arg)
            elif event == 'made-decision' and self.isMoreNeeded(arg):
                self.state = 'HIRE_ONE'
                self.doRememberSuppliers(arg)
                supplier_finder.A('start')
        #---HIRE_ONE---
        elif self.state == 'HIRE_ONE':
            if event == 'restart':
                self.NeedRestart = True
            elif event == 'supplier-connected' and not self.isStillNeeded(arg) and self.isSomeoneToDismiss(arg):
                self.state = 'FIRE_MANY'
                self.doSubstituteSupplier(arg)
                self.doDisconnectSuppliers(arg)
            elif event == 'supplier-connected' and not self.isStillNeeded(arg) and not self.isSomeoneToDismiss(arg):
                self.state = 'READY'
                self.doSubstituteSupplier(arg)
                self.doNotifySuppliersChanged(arg)
            elif event == 'supplier-connected' and self.isStillNeeded(arg):
                self.doSubstituteSupplier(arg)
                supplier_finder.A('start')
            elif event == 'search-failed' and not self.isSomeoneToDismiss(arg):
                self.state = 'READY'
                self.doScheduleNextRestart(arg)
            elif event == 'search-failed' and self.isSomeoneToDismiss(arg):
                self.state = 'FIRE_MANY'
                self.doDisconnectSuppliers(arg)
                self.doRemoveSuppliers(arg)
                self.doScheduleNextRestart(arg)
        #---FIRE_MANY---
        elif self.state == 'FIRE_MANY':
            if event == 'timer-15sec':
                self.state = 'READY'
                self.doCloseConnectors(arg)
                self.doClearDismissList(arg)
                self.doNotifySuppliersChanged(arg)
            elif event == 'supplier-state-changed' and not self.isAllDismissed(arg):
                self.doCloseConnector(arg)
            elif event == 'restart':
                self.NeedRestart = True
            elif event == 'supplier-state-changed' and self.isAllDismissed(arg):
                self.state = 'READY'
                self.doCloseConnector(arg)
                self.doClearDismissList(arg)
                self.doNotifySuppliersChanged(arg)
        #---SUPPLIERS?---
        elif self.state == 'SUPPLIERS?':
            if event == 'restart':
                self.NeedRestart = True
            elif (event == 'supplier-state-changed' and self.isAllReady(arg)) or event == 'timer-15sec':
                self.state = 'DECISION?'
                self.doDecideToDismiss(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READY'
                self.NeedRestart = False
        return None

    def isMoreNeeded(self, arg):
        """
        Condition method.
        """
        # lg.out(10, 'fire_hire.isMoreNeeded current=%d dismiss=%d needed=%d' % (
        # contactsdb.num_suppliers(), len(self.dismiss_list),
        # settings.getSuppliersNumberDesired()))
        if '' in contactsdb.suppliers():
            lg.out(4, 'fire_hire.isMoreNeeded found empty suppliers!!!')
            return True
        if isinstance(arg, list):
            dismissed = arg
        else:
            dismissed = self.dismiss_list
        s = set(contactsdb.suppliers())
        s.difference_update(set(dismissed))
        result = len(s) < settings.getSuppliersNumberDesired()
        lg.out(14, 'fire_hire.isMoreNeeded %d %d %d %d, result=%s' % (
            contactsdb.num_suppliers(), len(dismissed), len(s),
            settings.getSuppliersNumberDesired(), result))
        return result

    def isAllReady(self, arg):
        """
        Condition method.
        """
        lg.out(14, 'fire_hire.isAllReady %d %d' % (
            len(self.connect_list), contactsdb.num_suppliers()))
        return len(self.connect_list) == 0  # contactsdb.num_suppliers()

    def isAllDismissed(self, arg):
        """
        Condition method.
        """
        return len(self.dismiss_list) == len(self.dismiss_results)

    def isSomeoneToDismiss(self, arg):
        """
        Condition method.
        """
        if isinstance(arg, list):
            dismissed = arg
        else:
            dismissed = self.dismiss_list
        return len(dismissed) > 0

    def isStillNeeded(self, arg):
        """
        Condition method.
        """
        supplier_idurl = arg
        current_suppliers = contactsdb.suppliers()
        if supplier_idurl in current_suppliers:
            # this guy is already a supplier, we still need more then
            return True
        desired_number = settings.getSuppliersNumberDesired()
        needed_suppliers = current_suppliers[:desired_number]
        empty_suppliers = needed_suppliers.count('')
        # if '' in needed_suppliers:
        # lg.warn('found empty suppliers!!!')
        # return True
        s = set(needed_suppliers)
        s.add(supplier_idurl)
        s.difference_update(set(self.dismiss_list))
        result = len(s) - \
            empty_suppliers < settings.getSuppliersNumberDesired()
        # lg.out(14, 'fire_hire.isStillNeeded %d %d %d %d %d, result=%s' % (
        #     contactsdb.num_suppliers(), len(needed_suppliers), len(self.dismiss_list),
        #     len(s), settings.getSuppliersNumberDesired(), result))
        return result

    def isConfigChanged(self, arg):
        """
        Condition method.
        """
        curconfigs = (settings.getSuppliersNumberDesired(),
                      diskspace.GetBytesFromString(settings.getNeededString()))
        if None in self.configs:
            return True
        return self.configs[0] != curconfigs[
            0] or self.configs[1] != curconfigs[1]

    def isExistSomeSuppliers(self, arg):
        """
        Condition method.
        """
        return contactsdb.num_suppliers() > 0 and contactsdb.suppliers().count(
            '') < contactsdb.num_suppliers()

    def doSaveConfig(self, arg):
        """
        Action method.
        """
        self.configs = (
            settings.getSuppliersNumberDesired(),
            diskspace.GetBytesFromString(
                settings.getNeededString()))

    def doConnectSuppliers(self, arg):
        """
        Action method.
        """
        self.connect_list = []
        for supplier_idurl in contactsdb.suppliers():
            if supplier_idurl == '':
                continue
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc is None:
                sc = supplier_connector.create(supplier_idurl)
            sc.set_callback('fire_hire', self._supplier_connector_state_changed)
            self.connect_list.append(supplier_idurl)
            sc.automat('connect')

    def doDecideToDismiss(self, arg):
        """
        Action method.
        """
        global _SuppliersToFire
        result = set(_SuppliersToFire)
        _SuppliersToFire = []
        # if you have some empty suppliers need to get rid of them,
        # but no need to dismiss anyone at the moment.
        if '' in contactsdb.suppliers():
            lg.out(10, 'fire_hire.doDecideToDismiss found empty supplier, SKIP')
            self.automat('made-decision', [])
            return
        for supplier_idurl in contactsdb.suppliers():
            if not supplier_idurl:
                continue
            sc = supplier_connector.by_idurl(supplier_idurl)
            if not sc:
                continue
            if sc.state == 'NO_SERVICE':
                result.add(supplier_idurl)
        if contactsdb.num_suppliers() > settings.getSuppliersNumberDesired():
            for supplier_index in range(
                    settings.getSuppliersNumberDesired(),
                    contactsdb.num_suppliers()):
                idurl = contactsdb.supplier(supplier_index)
                if idurl:
                    result.add(idurl)
        result = list(result)
        lg.out(10, 'fire_hire.doDecideToDismiss %s' % result)
        self.automat('made-decision', result)

    def doRememberSuppliers(self, arg):
        """
        Action method.
        """
        self.dismiss_list = arg

    def doSubstituteSupplier(self, arg):
        """
        Action method.
        """
        new_idurl = arg
        current_suppliers = list(contactsdb.suppliers())
        if new_idurl in current_suppliers:
            raise Exception('%s is already supplier' % new_idurl)
        position = -1
        old_idurl = None
        for i in range(len(current_suppliers)):
            if current_suppliers[i].strip() == '':
                position = i
                break
            if current_suppliers[i] in self.dismiss_list:
                # self.dismiss_list.remove(current_suppliers[i])
                position = i
                old_idurl = current_suppliers[i]
                break
        lg.out(10, 'fire_hire.doSubstituteSupplier position=%d' % position)
        if position < 0:
            current_suppliers.append(new_idurl)
        else:
            current_suppliers[position] = new_idurl
        contactsdb.update_suppliers(current_suppliers)
        contactsdb.save_suppliers()
        misc.writeSupplierData(
            new_idurl,
            'connected',
            time.strftime('%d-%m-%Y %H:%M:%S'),
            my_id.getLocalID(),
        )
        if settings.NewWebGUI():
            from web import control
            control.on_suppliers_changed(current_suppliers)
        else:
            from web import webcontrol
            webcontrol.OnListSuppliers()
        if position < 0:
            lg.out(2, '!!!!!!!!!!! ADDED NEW SUPPLIER : %s' % (new_idurl))
            events.send('supplier-modified', dict(
                new_idurl=new_idurl, old_idurl=None, position=(len(current_suppliers) - 1),
            ))
        else:
            if old_idurl:
                lg.out(2, '!!!!!!!!!!! SUBSTITUTE EXISTING SUPPLIER %d : %s->%s' % (position, old_idurl, new_idurl))
                events.send('supplier-modified', dict(
                    new_idurl=new_idurl, old_idurl=old_idurl, position=position,
                ))
            else:
                lg.out(2, '!!!!!!!!!!! REPLACE EMPTY SUPPLIER %d : %s' % (position, new_idurl))
                events.send('supplier-modified', dict(
                    new_idurl=new_idurl, old_idurl=None, position=position,
                ))
        self.restart_interval = 1.0

    def doRemoveSuppliers(self, arg):
        """
        Action method.
        """
        current_suppliers = contactsdb.suppliers()
        desired_suppliers = settings.getSuppliersNumberDesired()
        if len(current_suppliers) < desired_suppliers:
            lg.warn('must have more suppliers %d<%d' % (
                len(current_suppliers), desired_suppliers))
        removed_suppliers = []
        for supplier_idurl in self.dismiss_list:
            if supplier_idurl not in current_suppliers:
                lg.warn('%s not a supplier' % supplier_idurl)
                continue
            pos = current_suppliers.index(supplier_idurl)
            # current_suppliers.remove(supplier_idurl)
            current_suppliers[pos] = ''
            removed_suppliers.append((pos, supplier_idurl,))
            misc.writeSupplierData(
                supplier_idurl,
                'disconnected',
                time.strftime('%d-%m-%Y %H:%M:%S'),
                my_id.getLocalID(),
            )
        current_suppliers = current_suppliers[:desired_suppliers]
        contactsdb.update_suppliers(current_suppliers)
        contactsdb.save_suppliers()
        if settings.NewWebGUI():
            from web import control
            control.on_suppliers_changed(current_suppliers)
        else:
            from web import webcontrol
            webcontrol.OnListSuppliers()
        for position, supplier_idurl in removed_suppliers:
            events.send('supplier-modified', dict(
                new_idurl=None, old_idurl=supplier_idurl, position=position,
            ))
        lg.out(2, '!!!!!!!!!!! REMOVE SUPPLIERS : %d' % len(self.dismiss_list))

    def doDisconnectSuppliers(self, arg):
        """
        Action method.
        """
        lg.out(10, 'fire_hire.doDisconnectSuppliers %r' % self.dismiss_list)
        self.dismiss_results = []
        for supplier_idurl in self.dismiss_list:
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc:
                sc.set_callback('fire_hire',
                                self._supplier_connector_state_changed)
                sc.automat('disconnect')
            else:
                lg.warn(
                    'supplier_connector must exist, but not found %s' %
                    supplier_idurl)

    def doCloseConnector(self, arg):
        """
        Action method.
        """
        supplier_idurl, _ = arg
        sc = supplier_connector.by_idurl(supplier_idurl)
        if supplier_idurl in self.dismiss_list:
            self.dismiss_list.remove(supplier_idurl)
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
            if supplier_idurl in self.dismiss_list:
                self.dismiss_list.remove(supplier_idurl)
            if sc:
                sc.automat('shutdown')

    def doClearDismissList(self, arg):
        """
        Action method.
        """
        self.dismiss_list = []

    def doScheduleNextRestart(self, arg):
        """
        Action method.
        """
        if not self.restart_task:
            self.restart_task = reactor.callLater(
                self.restart_interval, self._scheduled_restart)
            lg.out(
                10, 'fire_hire.doScheduleNextRestart after %r sec.' %
                self.restart_interval)
            self.restart_interval *= 1.1
        else:
            lg.out(
                10, 'fire_hire.doScheduleNextRestart already scheduled - %r sec. left' %
                (time.time() - self.restart_task.getTime()))

    def doNotifySuppliersChanged(self, arg):
        if driver.is_started('service_backups'):
            from storage import backup_monitor
            backup_monitor.A('suppliers-changed')

    def doNotifyFinished(self, arg):
        if driver.is_started('service_backups'):
            from storage import backup_monitor
            backup_monitor.A('fire-hire-finished')

    def _scheduled_restart(self):
        self.restart_task = None
        self.automat('restart')

    def _supplier_connector_state_changed(self, idurl, newstate):
        lg.out(14, 'fire_hire._supplier_connector_state_changed %s to %s, own state is %s' % (
            idurl, newstate, self.state))
        supplier_connector.by_idurl(idurl).remove_callback('fire_hire')
        if self.state == 'SUPPLIERS?':
            self.connect_list.remove(idurl)
        elif self.state == 'FIRE_MANY':
            self.dismiss_results.append(idurl)
        else:
            return
        self.automat('supplier-state-changed', (idurl, newstate))


# def WhoIsLost():
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
#    for supplier_idurl in contactsdb.suppliers():
#    # for sc in supplier_connector.connectors().values():
#        sc = supplier_connector.by_idurl(supplier_idurl)
#        if sc and sc.state == 'NO_SERVICE':
#            lg.out(6, 'fire_hire.WhoIsLost !!!!!!!! %s : no service' % sc.idurl)
#            return 'found-one-lost-supplier', sc.idurl
#    unreliable_supplier = None
#    most_fails = 0.0
#    for supplierNum in range(contactsdb.num_suppliers()):
#        idurl = contactsdb.supplier(supplierNum)
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
#    for supplierNum in range(contactsdb.num_suppliers()):
#        idurl = contactsdb.supplier(supplierNum)
#        if not idurl:
#            continue
#        if contact_status.isOnline(idurl):
#            continue
#        blocks, total, stats = backup_matrix.GetSupplierStats(supplierNum)
#        rating = 0 if total == 0 else blocks / total
#        offline_suppliers[idurl] = rating

#    # if all suppliers are online - we are very happy - no need to fire anybody!
#    if len(offline_suppliers) == 0:
#        lg.out(4, 'fire_hire.WhoIsLost no offline suppliers, Cool!')
#        return 'not-found-lost-suppliers', ''

#    # sort users - we always fire worst supplier
#    rating = offline_suppliers.keys()
#    rating.sort(key=lambda idurl: offline_suppliers[idurl])
#    lost_supplier_idurl = rating[0]

#    # we do not want to fire this man if he store at least 50% of our files
#    # the fact that he is offline is not enough to fire him!
#    if offline_suppliers[lost_supplier_idurl] < 0.5 and backup_fs.sizebackups() > 0:
#        lg.out(4, 'fire_hire.WhoIsLost !!!!!!!! %s is offline and keeps only %d%% of our data' % (
#            nameurl.GetName(lost_supplier_idurl),
#            int(offline_suppliers[lost_supplier_idurl] * 100.0)))
#        return 'found-one-lost-supplier', lost_supplier_idurl

#    # but if we did not saw him for a long time - we do not want him for sure
#    if time.time() - ratings.connected_time(lost_supplier_idurl) > 60 * 60 * 24 * 2:
#        lg.out(2, 'fire_hire.WhoIsLost !!!!!!!! %s is offline and keeps %d%% of our data, but he was online %d hours ago' % (
#            nameurl.GetName(lost_supplier_idurl),
#            int(offline_suppliers[lost_supplier_idurl] * 100.0),
#            int((time.time() - ratings.connected_time(lost_supplier_idurl)) * 60 * 60),))
#        return 'found-one-lost-supplier', lost_supplier_idurl

#    lg.out(2, 'fire_hire.WhoIsLost some people is not here, but we did not found the bad guy at this time')
#    return 'not-found-lost-suppliers', ''
