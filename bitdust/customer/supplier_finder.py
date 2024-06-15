#!/usr/bin/env python
# supplier_finder.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (supplier_finder.py) is part of BitDust Software.
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
.. module:: supplier_finder.

.. role:: red
BitDust supplier_finder() Automat


EVENTS:
    * :red:`ack-received`
    * :red:`found-one-user`
    * :red:`ping-failed`
    * :red:`start`
    * :red:`supplier-connected`
    * :red:`supplier-not-connected`
    * :red:`timer-10sec`
    * :red:`timer-30sec`
    * :red:`users-not-found`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import strng

from bitdust.p2p import lookup
from bitdust.p2p import online_status

from bitdust.contacts import identitycache
from bitdust.contacts import contactsdb

from bitdust.userid import my_id
from bitdust.userid import id_url

#------------------------------------------------------------------------------

_SupplierFinder = None
_SuppliersToHire = []

#------------------------------------------------------------------------------


def AddSupplierToHire(idurl):
    global _SuppliersToHire
    idurl = strng.to_bin(idurl)
    if idurl not in _SuppliersToHire:
        _SuppliersToHire.append(idurl)
        if _Debug:
            lg.dbg(_DebugLevel, 'added %r as a supplier candidate' % idurl)


def InsertSupplierToHire(idurl):
    global _SuppliersToHire
    idurl = strng.to_bin(idurl)
    if idurl not in _SuppliersToHire:
        _SuppliersToHire.insert(0, idurl)
        if _Debug:
            lg.dbg(_DebugLevel, 'added %r as a FIRST supplier candidate' % idurl)


#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _SupplierFinder
    if _SupplierFinder is None:
        # set automat name and starting state here
        _SupplierFinder = SupplierFinder(
            name='supplier_finder',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _SupplierFinder.automat(event, *args, **kwargs)
    return _SupplierFinder


class SupplierFinder(automat.Automat):
    """
    This class implements all the functionality of the ``supplier_finder()``
    state machine.
    """

    timers = {
        'timer-30sec': (30.0, ['SERVICE?']),
        'timer-10sec': (10.0, ['ACK?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.target_idurl = None

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start' and not self.isSomeCandidatesListed(*args, **kwargs):
                self.state = 'RANDOM_USER'
                self.Attempts = 0
                self.doInit(*args, **kwargs)
                self.doDHTFindRandomUser(*args, **kwargs)
            elif event == 'start' and self.isSomeCandidatesListed(*args, **kwargs):
                self.state = 'ACK?'
                self.doInit(*args, **kwargs)
                self.doPopCandidate(*args, **kwargs)
                self.Attempts = 1
                self.doSendMyIdentity(*args, **kwargs)
        #---RANDOM_USER---
        elif self.state == 'RANDOM_USER':
            if event == 'users-not-found':
                self.state = 'FAILED'
                self.doDestroyMe(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
            elif event == 'found-one-user':
                self.state = 'ACK?'
                self.doCleanPrevUser(*args, **kwargs)
                self.doRememberUser(*args, **kwargs)
                self.Attempts += 1
                self.doSendMyIdentity(*args, **kwargs)
        #---ACK?---
        elif self.state == 'ACK?':
            if self.Attempts == 5 and (event == 'timer-10sec' or event == 'ping-failed'):
                self.state = 'FAILED'
                self.doDestroyMe(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
            elif (event == 'ping-failed' or event == 'timer-10sec') and self.Attempts < 5:
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(*args, **kwargs)
            elif event == 'ack-received':
                self.state = 'SERVICE?'
                self.doSupplierConnect(*args, **kwargs)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'supplier-connected':
                self.state = 'DONE'
                self.doDestroyMe(*args, **kwargs)
                self.doReportDone(*args, **kwargs)
            elif self.Attempts < 5 and event == 'supplier-not-connected':
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(*args, **kwargs)
            elif event == 'timer-30sec' and self.Attempts < 5:
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(*args, **kwargs)
            elif self.Attempts == 5 and (event == 'timer-30sec' or event == 'supplier-not-connected'):
                self.state = 'FAILED'
                self.doDestroyMe(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---DONE---
        elif self.state == 'DONE':
            pass
        return None

    def isSomeCandidatesListed(self, *args, **kwargs):
        """
        Condition method.
        """
        global _SuppliersToHire
        available = []
        for idurl in _SuppliersToHire:
            if id_url.is_not_in(idurl, contactsdb.suppliers(), as_field=False):
                available.append(idurl)
        return len(available) > 0

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.family_position = kwargs.get('family_position', None)
        self.ecc_map = kwargs.get('ecc_map')
        self.family_snapshot = kwargs.get('family_snapshot')

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        d = online_status.ping(
            idurl=self.target_idurl,
            channel='supplier_finder',
            keep_alive=False,
        )
        d.addCallback(lambda ok: self.automat('ack-received', ok))
        d.addErrback(lambda err: self.automat('ping-failed'))

    def doSupplierConnect(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.customer import supplier_connector
        from bitdust.customer import fire_hire
        from bitdust.raid import eccmap
        position = self.family_position
        if position is None or position == -1:
            lg.warn('position for new supplier is unknown, will "guess"')
            current_suppliers = list(contactsdb.suppliers())
            for i in range(len(current_suppliers)):
                supplier_idurl = current_suppliers[i].to_bin()
                if not supplier_idurl:
                    position = i
                    break
                if id_url.is_in(supplier_idurl, fire_hire.A().dismiss_list, as_field=False):
                    position = i
                    break
        sc = supplier_connector.by_idurl(self.target_idurl)
        if not sc:
            sc = supplier_connector.create(
                supplier_idurl=self.target_idurl,
                customer_idurl=my_id.getIDURL(),
            )
        sc.set_callback('supplier_finder', self._supplier_connector_state)
        sc.automat(
            'connect',
            family_position=position,
            ecc_map=(self.ecc_map or eccmap.Current().name),
            family_snapshot=self.family_snapshot,
        )

    def doDHTFindRandomUser(self, *args, **kwargs):
        """
        Action method.
        """
        tsk = lookup.random_supplier(ignore_idurls=contactsdb.suppliers())
        tsk.result_defer.addCallback(self._nodes_lookup_finished)
        tsk.result_defer.addErrback(lambda err: self.automat('users-not-found'))

    def doCleanPrevUser(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.customer import supplier_connector
        if id_url.is_cached(self.target_idurl):
            sc = supplier_connector.by_idurl(self.target_idurl)
            if sc:
                sc.remove_callback('supplier_finder', self._supplier_connector_state)
        self.target_idurl = None

    def doRememberUser(self, *args, **kwargs):
        """
        Action method.
        """
        self.target_idurl = id_url.field(args[0])
        if _Debug:
            lg.args(_DebugLevel, target_idurl=self.target_idurl)

    def doPopCandidate(self, *args, **kwargs):
        """
        Action method.
        """
        global _SuppliersToHire
        for idurl in _SuppliersToHire:
            if id_url.is_not_in(idurl, contactsdb.suppliers(), as_field=False):
                self.target_idurl = id_url.field(idurl)
                _SuppliersToHire.remove(idurl)
                break
        lg.info('populate supplier %r from "hire" list, %d more in the list' % (self.target_idurl, len(_SuppliersToHire)))

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.customer import fire_hire
        fire_hire.A('supplier-connected', *args, **kwargs)

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.customer import fire_hire
        fire_hire.A('search-failed', *args, **kwargs)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        from bitdust.customer import supplier_connector
        global _SupplierFinder
        del _SupplierFinder
        _SupplierFinder = None
        if self.target_idurl:
            sc = supplier_connector.by_idurl(self.target_idurl)
            if sc:
                sc.remove_callback('supplier_finder', self._supplier_connector_state)
            self.target_idurl = None
        self.destroy()

    #------------------------------------------------------------------------------

    def _nodes_lookup_finished(self, idurls):
        if _Debug:
            lg.out(_DebugLevel, 'supplier_finder._nodes_lookup_finished : %r' % idurls)
        if not idurls:
            lg.warn('no available nodes found via DHT lookup')
            self.automat('users-not-found')
            return
        found_idurl = None
        for idurl in idurls:
            #             if id_url.is_in(idurl, contactsdb.suppliers(), as_field=True):
            #                 if _Debug:
            #                     lg.out('    skip %r because already my supplier' % idurl)
            #                 continue
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if not len(myprotos.intersection(remoteprotos)):
                if _Debug:
                    lg.out(_DebugLevel, '    skip %r because no matching protocols exists' % idurl)
                continue
            found_idurl = idurl
            break
        if not found_idurl:
            lg.warn('found some nodes via DHT lookup, but none of them is available')
            self.automat('users-not-found')
            return
        if _Debug:
            lg.out(_DebugLevel, '    selected %r and will request supplier service' % found_idurl)
        self.automat('found-one-user', found_idurl)

    def _supplier_connector_state(self, supplier_idurl, newstate, **kwargs):
        if id_url.field(supplier_idurl) != self.target_idurl:
            return
        if newstate in ['DISCONNECTED', 'NO_SERVICE']:
            self.automat('supplier-not-connected')
            return
        if newstate != 'CONNECTED':
            return
        if contactsdb.is_supplier(self.target_idurl):
            return
        family_position = kwargs.get('family_position', None)
        ecc_map = kwargs.get('ecc_map')
        self.automat('supplier-connected', self.target_idurl, family_position=family_position, ecc_map=ecc_map, family_snapshot=self.family_snapshot)
