#!/usr/bin/python
# fire_hire.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

    <a href="https://bitdust.io/automats/fire_hire/fire_hire.png" target="_blank">
    <img src="https://bitdust.io/automats/fire_hire/fire_hire.png" style="max-width:100%;">
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
    * :red:`timer-25sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys
import time

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in fire_hire.py')

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import misc
from bitdust.lib import diskspace
from bitdust.lib import strng
from bitdust.lib import utime

from bitdust.main import config
from bitdust.main import settings
from bitdust.main import events

from bitdust.contacts import contactsdb

from bitdust.services import driver

from bitdust.raid import eccmap

from bitdust.userid import my_id
from bitdust.userid import id_url

#-------------------------------------------------------------------------

_FireHire = None
_LastFireTime = 0
_SuppliersToFire = []
_ForceRestartState = False

#-------------------------------------------------------------------------


def GetLastFireTime():
    """
    This method returns a time moment when last time some supplier was
    replaced.
    """
    global _LastFireTime
    return _LastFireTime


def ClearLastFireTime():
    _LastFireTime = 0


def AddSupplierToFire(idurl):
    global _SuppliersToFire
    _SuppliersToFire.append(idurl)


def ForceRestart():
    global _ForceRestartState
    _ForceRestartState = True


def IsAllHired():
    if settings.getSuppliersNumberDesired() < 0:
        # I must know how many suppliers I want
        lg.warn('my desired number of suppliers not set')
        return False
    if contactsdb.num_suppliers() != settings.getSuppliersNumberDesired():
        # I must have exactly that amount of suppliers already
        if _Debug:
            lg.args(_DebugLevel, desiried_suppliers=settings.getSuppliersNumberDesired(), current_suppliers=contactsdb.num_suppliers())
        return False
    if id_url.is_some_empty(contactsdb.suppliers()):
        # I must know all of my suppliers
        if _Debug:
            lg.args(_DebugLevel, my_suppliers=contactsdb.suppliers())
        return False
    return True


#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _FireHire
    if _FireHire is None:
        _FireHire = FireHire(
            name='fire_hire',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _FireHire.automat(event, *args, **kwargs)
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

    fast = False

    timers = {
        'timer-25sec': (25.0, ['FIRE_MANY', 'SUPPLIERS?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.connect_list = []
        self.dismiss_list = []
        self.dismiss_results = []
        self.hire_list = []
        self.configs = (None, None)
        self.restart_interval = 1.0
        self.restart_task = None

    def shutdown(self):
        self.connect_list = []
        self.dismiss_list = []
        self.dismiss_results = []
        self.hire_list = []
        self.configs = (None, None)
        self.restart_interval = 1.0
        self.restart_task = None

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when automat's state was changed.
        """
        if newstate == 'READY' and event != 'instant':
            self.automat('instant')

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READY'
                self.NeedRestart = False
        #---READY---
        elif self.state == 'READY':
            if (event == 'restart' or (event == 'instant' and self.NeedRestart)) and (self.isConfigChanged(*args, **kwargs) or self.isContractExpiring(*args, **kwargs)) and self.isExistSomeSuppliers(*args, **kwargs):
                self.state = 'SUPPLIERS?'
                self.NeedRestart = False
                self.doSaveConfig(*args, **kwargs)
                self.doConnectSuppliers(*args, **kwargs)
            elif (event == 'restart' or (event == 'instant' and self.NeedRestart)) and not ((self.isConfigChanged(*args, **kwargs) or self.isContractExpiring(*args, **kwargs)) and self.isExistSomeSuppliers(*args, **kwargs)):
                self.state = 'DECISION?'
                self.NeedRestart = False
                self.doDecideToDismiss(*args, **kwargs)
        #---DECISION?---
        elif self.state == 'DECISION?':
            if event == 'made-decision' and self.isSomeoneToDismiss(*args, **kwargs) and not self.isMoreNeeded(*args, **kwargs):
                self.state = 'FIRE_MANY'
                self.doRememberSuppliers(*args, **kwargs)
                self.doRemoveSuppliers(*args, **kwargs)
                self.doDisconnectSuppliers(*args, **kwargs)
            elif event == 'restart':
                self.NeedRestart = True
            elif event == 'made-decision' and not self.isMoreNeeded(*args, **kwargs) and not self.isSomeoneToDismiss(*args, **kwargs):
                self.state = 'READY'
                self.doNotifyFinished(*args, **kwargs)
            elif event == 'made-decision' and self.isMoreNeeded(*args, **kwargs):
                self.state = 'HIRE_ONE'
                self.doRememberSuppliers(*args, **kwargs)
                self.doFindNewSupplier(*args, **kwargs)
        #---HIRE_ONE---
        elif self.state == 'HIRE_ONE':
            if event == 'restart':
                self.NeedRestart = True
            elif event == 'supplier-connected' and not self.isStillNeeded(*args, **kwargs) and self.isSomeoneToDismiss(*args, **kwargs):
                self.state = 'FIRE_MANY'
                self.doSubstituteSupplier(*args, **kwargs)
                self.doDisconnectSuppliers(*args, **kwargs)
            elif event == 'supplier-connected' and not self.isStillNeeded(*args, **kwargs) and not self.isSomeoneToDismiss(*args, **kwargs):
                self.state = 'READY'
                self.doSubstituteSupplier(*args, **kwargs)
                self.doNotifySuppliersChanged(*args, **kwargs)
            elif event == 'supplier-connected' and self.isStillNeeded(*args, **kwargs):
                self.doSubstituteSupplier(*args, **kwargs)
                self.doFindNewSupplier(*args, **kwargs)
            elif event == 'search-failed' and not self.isSomeoneToDismiss(*args, **kwargs):
                self.state = 'READY'
                self.doScheduleNextRestart(*args, **kwargs)
                self.doNotifySuppliersChanged(*args, **kwargs)
            elif event == 'search-failed' and self.isSomeoneToDismiss(*args, **kwargs):
                self.state = 'FIRE_MANY'
                self.doDisconnectSuppliers(*args, **kwargs)
                self.doRemoveSuppliers(*args, **kwargs)
                self.doScheduleNextRestart(*args, **kwargs)
        #---FIRE_MANY---
        elif self.state == 'FIRE_MANY':
            if event == 'supplier-state-changed' and not self.isAllDismissed(*args, **kwargs):
                self.doCloseConnector(*args, **kwargs)
            elif event == 'restart':
                self.NeedRestart = True
            elif event == 'supplier-state-changed' and self.isAllDismissed(*args, **kwargs):
                self.state = 'READY'
                self.doCloseConnector(*args, **kwargs)
                self.doClearDismissList(*args, **kwargs)
                self.doNotifySuppliersChanged(*args, **kwargs)
            elif event == 'timer-25sec':
                self.state = 'READY'
                self.doCloseConnectors(*args, **kwargs)
                self.doClearDismissList(*args, **kwargs)
                self.doNotifySuppliersChanged(*args, **kwargs)
        #---SUPPLIERS?---
        elif self.state == 'SUPPLIERS?':
            if event == 'restart':
                self.NeedRestart = True
            elif (event == 'supplier-state-changed' and self.isAllReady(*args, **kwargs)) or event == 'timer-25sec':
                self.state = 'DECISION?'
                self.doDecideToDismiss(*args, **kwargs)
        return None

    def isMoreNeeded(self, *args, **kwargs):
        """
        Condition method.
        """
        # if _Debug:
        #     lg.out(_DebugLevel, 'fire_hire.isMoreNeeded current=%d dismiss=%d needed=%d' % (
        #         contactsdb.num_suppliers(), len(self.dismiss_list),
        #         settings.getSuppliersNumberDesired()))
        if id_url.is_some_empty(contactsdb.suppliers()):
            if _Debug:
                lg.out(_DebugLevel, 'fire_hire.isMoreNeeded found empty supplier!!!')
            return True
        if isinstance(args[0], list):
            dismissed = args[0]
        else:
            dismissed = self.dismiss_list
        s = set(id_url.to_bin_list(contactsdb.suppliers()))
        s.difference_update(set(id_url.to_bin_list(dismissed)))
        result = len(s) < settings.getSuppliersNumberDesired()
        if _Debug:
            lg.out(_DebugLevel, 'fire_hire.isMoreNeeded %d %d %d %d, result=%s' % (contactsdb.num_suppliers(), len(dismissed), len(s), settings.getSuppliersNumberDesired(), result))
        return result

    def isAllReady(self, *args, **kwargs):
        """
        Condition method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'fire_hire.isAllReady %d %d' % (len(self.connect_list), contactsdb.num_suppliers()))
        return len(self.connect_list) == 0  # contactsdb.num_suppliers()

    def isAllDismissed(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.dismiss_list) == len(self.dismiss_results)

    def isSomeoneToDismiss(self, *args, **kwargs):
        """
        Condition method.
        """
        if args and isinstance(args[0], list):
            dismissed = args[0]
        else:
            dismissed = self.dismiss_list
        return len(dismissed) > 0

    def isStillNeeded(self, *args, **kwargs):
        """
        Condition method.
        """
        supplier_idurl = args[0]
        current_suppliers = contactsdb.suppliers()
        if supplier_idurl in current_suppliers:
            # this guy is already a supplier, we still need more then
            return True
        desired_number = settings.getSuppliersNumberDesired()
        needed_suppliers = current_suppliers[:desired_number]
        empty_suppliers = needed_suppliers.count(id_url.field(b''))
        # if '' in needed_suppliers:
        # lg.warn('found empty suppliers!!!')
        # return True
        s = set(id_url.to_bin_list(needed_suppliers))
        s.add(id_url.to_bin(supplier_idurl))
        s.difference_update(set(id_url.to_bin_list(self.dismiss_list)))
        result = len(s) - empty_suppliers < settings.getSuppliersNumberDesired()
        # if _Debug:
        #     lg.out(_DebugLevel, 'fire_hire.isStillNeeded %d %d %d %d %d, result=%s' % (
        #     contactsdb.num_suppliers(), len(needed_suppliers), len(self.dismiss_list),
        #     len(s), settings.getSuppliersNumberDesired(), result))
        return result

    def isConfigChanged(self, *args, **kwargs):
        """
        Condition method.
        """
        global _ForceRestartState
        if _ForceRestartState:
            return True
        return self._is_config_changed()

    def isContractExpiring(self, *args, **kwargs):
        """
        Condition method.
        """
        if not driver.is_on('service_customer_contracts'):
            return False
        return len(self._get_suppliers_with_expired_contracts()) > 0

    def isExistSomeSuppliers(self, *args, **kwargs):
        """
        Condition method.
        """
        sup_list = contactsdb.suppliers()
        return contactsdb.num_suppliers() > 0 and sup_list.count(id_url.field(b'')) < contactsdb.num_suppliers()

    def doSaveConfig(self, *args, **kwargs):
        """
        Action method.
        """
        self.configs = (
            settings.getSuppliersNumberDesired(),
            diskspace.GetBytesFromString(settings.getNeededString()),
        )

    def doConnectSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        global _ForceRestartState
        _ForceRestartState = False
        from bitdust.customer import supplier_connector
        from bitdust.p2p import online_status
        self.connect_list = []
        my_current_family = contactsdb.suppliers()
        target_suppliers = list(my_current_family)
        if not self._is_config_changed():
            if driver.is_on('service_customer_contracts'):
                # only select suppliers with expired contracts
                target_suppliers = self._get_suppliers_with_expired_contracts()
        if _Debug:
            lg.args(_DebugLevel, my_current_family=my_current_family, target_suppliers=target_suppliers, configs=self.configs)
        for pos, supplier_idurl in enumerate(my_current_family):
            if not supplier_idurl:
                continue
            if self.configs[0] and pos >= self.configs[0]:
                continue
            if not id_url.is_in(supplier_idurl, target_suppliers):
                continue
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc is None:
                sc = supplier_connector.create(
                    supplier_idurl=supplier_idurl,
                    customer_idurl=my_id.getIDURL(),
                )
            else:
                sc.needed_bytes = None
                sc.do_calculate_needed_bytes()
            sc.set_callback('fire_hire', self._on_supplier_connector_state_changed)
            self.connect_list.append(supplier_idurl)
            sc.automat(
                'connect',
                family_position=pos,
                ecc_map=eccmap.Current().name,
                family_snapshot=id_url.to_bin_list(my_current_family),
            )
            online_status.add_online_status_listener_callback(
                idurl=supplier_idurl,
                callback_method=self._on_supplier_online_status_state_changed,
            )

    def doDecideToDismiss(self, *args, **kwargs):
        """
        Action method.
        """
        global _SuppliersToFire
        from bitdust.p2p import p2p_connector
        from bitdust.p2p import network_connector
        from bitdust.customer import supplier_connector
        from bitdust.p2p import online_status
        # take any actions only if I am connected to the network
        if not p2p_connector.A() or not network_connector.A():
            if _Debug:
                lg.out(_DebugLevel, 'fire_hire.doDecideToDismiss    p2p_connector() is not ready yet, SKIP')
            self.automat('made-decision', [])
            return
        if not network_connector.A():
            if _Debug:
                lg.out(_DebugLevel, 'fire_hire.doDecideToDismiss    network_connector() is not ready yet, SKIP')
            self.automat('made-decision', [])
            return
        if p2p_connector.A().state != 'CONNECTED' or network_connector.A().state != 'CONNECTED':
            if _Debug:
                lg.out(_DebugLevel, 'fire_hire.doDecideToDismiss    p2p/network is not connected at the moment, SKIP')
            self.automat('made-decision', [])
            return
        # if certain suppliers needs to be removed by manual/external request just do that
        to_be_fired = id_url.to_list(set(_SuppliersToFire))
        _SuppliersToFire = []
        if to_be_fired:
            lg.info('going to fire %d suppliers from external request' % len(to_be_fired))
            self.automat('made-decision', to_be_fired)
            return
        # make sure to not go too far when i just want to decrease number of my suppliers
        number_desired = settings.getSuppliersNumberDesired()
        redundant_suppliers = set()
        if contactsdb.num_suppliers() > number_desired:
            for supplier_index in range(number_desired, contactsdb.num_suppliers()):
                idurl = contactsdb.supplier(supplier_index)
                if idurl:
                    lg.info('found REDUNDANT supplier %s at position %d' % (idurl, supplier_index))
                    redundant_suppliers.add(idurl)
        if redundant_suppliers:
            result = list(redundant_suppliers)
            lg.info('will replace redundant suppliers: %s' % result)
            self.automat('made-decision', result)
            return
        # now I need to look more careful at my suppliers
        potentialy_fired = set()
        connected_suppliers = set()
        disconnected_suppliers = set()
        requested_suppliers = set()
        online_suppliers = set()
        offline_suppliers = set()
        # if you have some empty suppliers need to get rid of them,
        # but no need to dismiss anyone at the moment.
        my_suppliers = contactsdb.suppliers()
        if _Debug:
            lg.args(_DebugLevel, my_suppliers=my_suppliers)
        if id_url.is_some_empty(my_suppliers):
            lg.warn('SKIP, found empty supplier')
            self.automat('made-decision', [])
            return
        for supplier_idurl in my_suppliers:
            sc = supplier_connector.by_idurl(supplier_idurl)
            if not sc:
                lg.warn('SKIP, supplier connector for supplier %s not exist' % supplier_idurl)
                continue
            if sc.state == 'NO_SERVICE':
                lg.warn('found "NO_SERVICE" supplier: %s' % supplier_idurl)
                disconnected_suppliers.add(supplier_idurl)
                potentialy_fired.add(supplier_idurl)
            elif sc.state == 'CONNECTED':
                connected_suppliers.add(supplier_idurl)
            elif sc.state in ['DISCONNECTED', 'REFUSE']:
                disconnected_suppliers.add(supplier_idurl)
#             elif sc.state in ['QUEUE?', 'REQUEST', ]:
#                 requested_suppliers.add(supplier_idurl)
            if online_status.isOffline(supplier_idurl):
                offline_suppliers.add(supplier_idurl)
            elif online_status.isOnline(supplier_idurl):
                online_suppliers.add(supplier_idurl)
            elif online_status.isCheckingNow(supplier_idurl):
                requested_suppliers.add(supplier_idurl)
        if not connected_suppliers or not online_suppliers:
            lg.warn('SKIP, no ONLINE suppliers found at the moment')
            self.automat('made-decision', [])
            return
        if requested_suppliers:
            lg.warn('SKIP, still waiting response from some of suppliers')
            self.automat('made-decision', [])
            return
        if not disconnected_suppliers:
            if _Debug:
                lg.out(_DebugLevel, 'fire_hire.doDecideToDismiss    SKIP, no OFFLINE suppliers found at the moment')
            # TODO: add more conditions to fire "slow" suppliers - they are still connected but useless
            self.automat('made-decision', [])
            return
        if len(offline_suppliers) + len(online_suppliers) != number_desired:
            lg.warn('SKIP, offline + online != total count: %s %s %s' % (offline_suppliers, online_suppliers, number_desired))
            self.automat('made-decision', [])
            return
        max_offline_suppliers_count = eccmap.GetCorrectableErrors(number_desired)
        if len(offline_suppliers) > max_offline_suppliers_count:
            lg.warn('SKIP, too many OFFLINE suppliers at the moment : %d > %d' % (len(offline_suppliers), max_offline_suppliers_count))
            self.automat('made-decision', [])
            return
        critical_offline_suppliers_count = eccmap.GetFireHireErrors(number_desired)
        if len(offline_suppliers) >= critical_offline_suppliers_count and len(offline_suppliers) > 0:
            if config.conf().getBool('services/employer/replace-critically-offline-enabled'):
                # TODO: check that issue
                # too aggressive replacing suppliers who still have the data is very dangerous !!!
                one_dead_supplier = offline_suppliers.pop()
                lg.warn('found "CRITICALLY_OFFLINE" supplier %s, max offline limit is %d' % (one_dead_supplier, critical_offline_suppliers_count))
                potentialy_fired.add(one_dead_supplier)
        if not potentialy_fired:
            if _Debug:
                lg.out(_DebugLevel, 'fire_hire.doDecideToDismiss   found no "bad" suppliers, all is good !!!!!')
            self.automat('made-decision', [])
            return
        # only replace suppliers one by one at the moment
        result = list(potentialy_fired)
        lg.info('will replace supplier %s' % result[0])
        self.automat('made-decision', [
            result[0],
        ])

    def doRememberSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        self.dismiss_list = id_url.to_list(args[0])

    def doFindNewSupplier(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'fire_hire.doFindNewSupplier desired_suppliers=%d current_suppliers=%r' % (settings.getSuppliersNumberDesired(), contactsdb.suppliers()))
        from bitdust.p2p import network_connector
        if network_connector.A().state != 'CONNECTED':
            if _Debug:
                lg.out(_DebugLevel, '        network_connector is not CONNECTED at the moment, SKIP')
            self.automat('search-failed')
            return
        position_for_new_supplier = None
        for pos in range(settings.getSuppliersNumberDesired()):
            if pos in self.hire_list:
                continue
            supplier_idurl = contactsdb.supplier(pos)
            if not supplier_idurl:
                lg.info('found empty supplier at position %d and going to find new supplier on that position' % pos)
                position_for_new_supplier = pos
                break
            if id_url.is_in(supplier_idurl, self.dismiss_list, as_field=False):
                lg.info('going to find new supplier on existing position %d to replace supplier %s' % (pos, supplier_idurl))
                position_for_new_supplier = pos
                break
        if position_for_new_supplier is None:
            lg.err('did not found position for new supplier')
            self.automat('search-failed')
            return
        from bitdust.customer import supplier_finder
        for idurl_txt in strng.to_text(config.conf().getString('services/employer/candidates')).split(','):
            if idurl_txt.strip():
                supplier_finder.AddSupplierToHire(idurl_txt)
        self.hire_list.append(position_for_new_supplier)
        supplier_finder.A(
            'start',
            family_position=position_for_new_supplier,
            ecc_map=eccmap.Current().name,
            family_snapshot=id_url.to_bin_list(contactsdb.suppliers()),
        )

    def doSubstituteSupplier(self, *args, **kwargs):
        """
        Action method.
        """
        new_idurl = id_url.field(args[0])
        family_position = kwargs.get('family_position')
        current_suppliers = list(contactsdb.suppliers())
        desired_suppliers = settings.getSuppliersNumberDesired()
        old_idurl = None
        if family_position in self.hire_list:
            self.hire_list.remove(family_position)
            lg.info('found position on which new supplier suppose to be hired: %d' % family_position)
        else:
            lg.warn('did not found position for new supplier to be hired on')
        if new_idurl in current_suppliers:
            raise Exception('%s is already supplier' % new_idurl)
        if family_position is None or family_position == -1:
            lg.warn('unknown family_position from supplier results, will pick first empty spot')
            position = -1
            old_idurl = None
            for i in range(len(current_suppliers)):
                if not current_suppliers[i].strip():
                    position = i
                    break
                if id_url.is_in(current_suppliers[i], self.dismiss_list, as_field=False):
                    position = i
                    old_idurl = current_suppliers[i]
                    break
            family_position = position
        if _Debug:
            lg.out(_DebugLevel, 'fire_hire.doSubstituteSupplier family_position=%d' % family_position)
        contactsdb.add_supplier(idurl=new_idurl, position=family_position)
        contactsdb.save_suppliers()
        misc.writeSupplierData(
            new_idurl,
            'connected',
            time.strftime('%d-%m-%Y %H:%M:%S'),
            my_id.getIDURL(),
        )
        if family_position < 0:
            lg.info('added new supplier, family position unknown: %s desired_suppliers=%d current_suppliers=%d' % (new_idurl, desired_suppliers, len(contactsdb.suppliers())))
            # yapf: disable
            events.send('supplier-modified', data=dict(
                new_idurl=new_idurl,
                old_idurl=None,
                position=family_position,
                ecc_map=eccmap.Current().name,
                family_snapshot=id_url.to_bin_list(contactsdb.suppliers()),
            ))
            # yapf: enable
        else:
            if old_idurl:
                lg.info('hired new supplier and substitute existing supplier on position %d : %s->%s desired_suppliers=%d current_suppliers=%d' % (family_position, old_idurl, new_idurl, desired_suppliers, len(contactsdb.suppliers())))
                # yapf: disable
                events.send('supplier-modified', data=dict(
                    new_idurl=new_idurl,
                    old_idurl=old_idurl,
                    position=family_position,
                    ecc_map=eccmap.Current().name,
                    family_snapshot=id_url.to_bin_list(contactsdb.suppliers()),
                ))
                # yapf: enable
            else:
                lg.info('hired new supplier on empty position %d : %s desired_suppliers=%d current_suppliers=%d' % (family_position, new_idurl, desired_suppliers, len(contactsdb.suppliers())))
                # yapf: disable
                events.send('supplier-modified', data=dict(
                    new_idurl=new_idurl,
                    old_idurl=None,
                    position=family_position,
                    ecc_map=eccmap.Current().name,
                    family_snapshot=id_url.to_bin_list(contactsdb.suppliers()),
                ))
                # yapf: enable
        self.restart_interval = 1.0
        if _Debug:
            lg.out(_DebugLevel, '    my current suppliers: %r' % contactsdb.suppliers())

    def doRemoveSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        current_suppliers = contactsdb.suppliers()
        desired_suppliers = settings.getSuppliersNumberDesired()
        if len(current_suppliers) < desired_suppliers:
            lg.warn('must have more suppliers %d<%d' % (len(current_suppliers), desired_suppliers))
        removed_suppliers = []
        for supplier_idurl in self.dismiss_list:
            if id_url.is_not_in(supplier_idurl, current_suppliers, as_field=False):
                lg.warn('%s not a supplier' % supplier_idurl)
                continue
            pos = current_suppliers.index(id_url.field(supplier_idurl))
            current_suppliers[pos] = ''
            removed_suppliers.append((
                pos,
                supplier_idurl,
            ))
            misc.writeSupplierData(
                supplier_idurl,
                'disconnected',
                time.strftime('%d-%m-%Y %H:%M:%S'),
                my_id.getIDURL(),
            )
        current_suppliers = current_suppliers[:desired_suppliers]
        contactsdb.update_suppliers(current_suppliers)
        contactsdb.save_suppliers()
        for position, supplier_idurl in removed_suppliers:
            events.send('supplier-modified', data=dict(
                new_idurl=None,
                old_idurl=supplier_idurl,
                position=position,
            ))
        lg.info('removed some suppliers : %d  desired_suppliers=%d current_suppliers=%d' % (len(self.dismiss_list), desired_suppliers, len(contactsdb.suppliers())))
        if _Debug:
            lg.out(_DebugLevel, '    my current suppliers: %r' % contactsdb.suppliers())

    def doDisconnectSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.customer import supplier_connector
        from bitdust.p2p import online_status
        if _Debug:
            lg.out(_DebugLevel, 'fire_hire.doDisconnectSuppliers %r' % self.dismiss_list)
        self.dismiss_results = []
        for supplier_idurl in self.dismiss_list:
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc:
                sc.set_callback('fire_hire', self._on_supplier_connector_state_changed)
                sc.automat('disconnect', ecc_map=eccmap.Current().name)
            else:
                lg.warn('supplier_connector must exist, but not found %s' % supplier_idurl)
                self.dismiss_results.append(supplier_idurl)
            online_status.remove_online_status_listener_callback(
                idurl=supplier_idurl,
                callback_method=self._on_supplier_online_status_state_changed,
            )

    def doCloseConnector(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.customer import supplier_connector
        supplier_idurl, _ = args[0]
        supplier_idurl = id_url.field(supplier_idurl)
        if _Debug:
            lg.args(_DebugLevel, supplier_idurl=supplier_idurl, dismiss_list=self.dismiss_list)
        sc = supplier_connector.by_idurl(supplier_idurl)
        if id_url.is_in(supplier_idurl.to_bin(), self.dismiss_list, as_field=False):
            self.dismiss_list.remove(supplier_idurl)
        if sc:
            sc.automat('shutdown')
        else:
            raise Exception('supplier_connector must exist')

    def doCloseConnectors(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.customer import supplier_connector
        for supplier_idurl in self.dismiss_list:
            sc = supplier_connector.by_idurl(supplier_idurl)
            if id_url.is_in(supplier_idurl, self.dismiss_list, as_field=False):
                self.dismiss_list.remove(supplier_idurl)
            if sc:
                sc.automat('shutdown')

    def doClearDismissList(self, *args, **kwargs):
        """
        Action method.
        """
        self.dismiss_list = []

    def doScheduleNextRestart(self, *args, **kwargs):
        """
        Action method.
        """
        self.hire_list = []
        if not self.restart_task:
            self.restart_task = reactor.callLater(  # @UndefinedVariable
                self.restart_interval,
                self._scheduled_restart,
            )
            if _Debug:
                lg.out(_DebugLevel, 'fire_hire.doScheduleNextRestart after %r sec.' % self.restart_interval)
            from bitdust.p2p import network_connector
            if network_connector.A().state != 'CONNECTED':
                self.restart_interval = 60*5
            else:
                self.restart_interval *= 1.1
        else:
            if _Debug:
                lg.out(_DebugLevel, 'fire_hire.doScheduleNextRestart already scheduled - %r sec. left' % (time.time() - self.restart_task.getTime()))

    def doNotifySuppliersChanged(self, *args, **kwargs):
        self.hire_list = []
        if driver.is_on('service_backups'):
            from bitdust.storage import backup_monitor
            backup_monitor.A('suppliers-changed')

    def doNotifyFinished(self, *args, **kwargs):
        self.hire_list = []
        if driver.is_on('service_backups'):
            from bitdust.storage import backup_monitor
            backup_monitor.A('fire-hire-finished')

    def _is_config_changed(self):
        if None in self.configs:
            return True
        curconfigs = (settings.getSuppliersNumberDesired(), diskspace.GetBytesFromString(settings.getNeededString()))
        return self.configs[0] != curconfigs[0] or self.configs[1] != curconfigs[1]

    def _get_suppliers_with_expired_contracts(self):
        from bitdust.customer import supplier_connector
        now = utime.utcnow_to_sec1970()
        ret = []
        for supplier_idurl in contactsdb.suppliers():
            if supplier_idurl:
                sc = supplier_connector.by_idurl(supplier_idurl)
                if sc:
                    if sc.state == 'CONNECTED':
                        if sc.storage_contract:
                            if now > utime.unpack_time(sc.storage_contract['complete_after']):
                                lg.warn('storage contract with %s is expired' % supplier_idurl)
                                ret.append(supplier_idurl)
        return ret

    def _scheduled_restart(self):
        self.restart_task = None
        self.automat('restart')

    def _on_supplier_connector_state_changed(self, idurl, newstate, **kwargs):
        from bitdust.customer import supplier_connector
        idurl = id_url.field(idurl)
        if _Debug:
            lg.out(_DebugLevel, 'fire_hire._on_supplier_connector_state_changed %s to %s, own state is %s ' % (idurl, newstate, self.state))
        if supplier_connector.by_idurl(idurl):
            supplier_connector.by_idurl(idurl).remove_callback('fire_hire', self._on_supplier_connector_state_changed)
        if self.state == 'SUPPLIERS?':
            if idurl in self.connect_list:
                self.connect_list.remove(idurl)
            else:
                lg.warn('did not found %r in connect_list' % idurl)
        elif self.state == 'FIRE_MANY':
            if idurl not in self.dismiss_results:
                self.dismiss_results.append(idurl)
            else:
                lg.warn('did not found %r in dismiss_results' % idurl)
        else:
            return
        self.automat('supplier-state-changed', (
            idurl,
            newstate,
        ))

    def _on_supplier_online_status_state_changed(self, oldstate, newstate, event_string, *args, **kwargs):
        if oldstate != newstate:
            if _Debug:
                lg.out(_DebugLevel, 'fire_hire._on_supplier_online_status_state_changed  %s -> %s, own state is %s' % (oldstate, newstate, self.state))
        if oldstate != newstate and newstate in [
            'CONNECTED',
            'OFFLINE',
        ]:
            self.automat('restart')


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
#    If we can not send him our data or retrieve it back - how can we do a backups to him even if he is online?
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
