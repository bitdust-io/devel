#!/usr/bin/env python
# supplier_finder.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
    * :red:`found-one-user`
    * :red:`inbox-packet`
    * :red:`start`
    * :red:`supplier-connected`
    * :red:`supplier-not-connected`
    * :red:`timer-10sec`
    * :red:`users-not-found`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import strng

from p2p import commands
from p2p import p2p_service
from p2p import lookup

from contacts import identitycache
from contacts import contactsdb

from userid import my_id

from transport import callback

#------------------------------------------------------------------------------

_SupplierFinder = None
_SuppliersToHire = []

#------------------------------------------------------------------------------


def AddSupplierToHire(idurl):
    """
    """
    global _SuppliersToHire
    _SuppliersToHire.append(idurl)

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _SupplierFinder
    if _SupplierFinder is None:
        # set automat name and starting state here
        _SupplierFinder = SupplierFinder('supplier_finder', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _SupplierFinder.automat(event, *args, **kwargs)
    return _SupplierFinder


class SupplierFinder(automat.Automat):
    """
    This class implements all the functionality of the ``supplier_finder()``
    state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['ACK?', 'SERVICE?']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.target_idurl = None

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when automat's state were
        changed.
        """

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start' and not self.isSomeCandidatesListed(*args, **kwargs):
                self.state = 'RANDOM_USER'
                self.Attempts=0
                self.doInit(*args, **kwargs)
                self.doDHTFindRandomUser(*args, **kwargs)
            elif event == 'start' and self.isSomeCandidatesListed(*args, **kwargs):
                self.state = 'ACK?'
                self.doInit(*args, **kwargs)
                self.doPopCandidate(*args, **kwargs)
                self.Attempts=1
                self.doSendMyIdentity(*args, **kwargs)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'inbox-packet' and self.isAckFromUser(*args, **kwargs):
                self.state = 'SERVICE?'
                self.doSupplierConnect(*args, **kwargs)
            elif self.Attempts==5 and event == 'timer-10sec':
                self.state = 'FAILED'
                self.doDestroyMe(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
            elif event == 'timer-10sec' and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(*args, **kwargs)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---DONE---
        elif self.state == 'DONE':
            pass
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
                self.Attempts+=1
                self.doSendMyIdentity(*args, **kwargs)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'supplier-connected':
                self.state = 'DONE'
                self.doDestroyMe(*args, **kwargs)
                self.doReportDone(*args, **kwargs)
            elif event == 'timer-10sec' and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(*args, **kwargs)
            elif self.Attempts==5 and ( event == 'timer-10sec' or event == 'supplier-not-connected' ):
                self.state = 'FAILED'
                self.doDestroyMe(*args, **kwargs)
                self.doReportFailed(*args, **kwargs)
            elif self.Attempts<5 and event == 'supplier-not-connected':
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(*args, **kwargs)
        return None

    def isAckFromUser(self, *args, **kwargs):
        """
        Condition method.
        """
        newpacket, info, status, error_message = args[0]
        if newpacket.Command == commands.Ack():
            if newpacket.OwnerID == self.target_idurl:
                # TODO: also check PacketID
                return True
        return False

    def isSomeCandidatesListed(self, *args, **kwargs):
        """
        Condition method.
        """
        global _SuppliersToHire
        return len(_SuppliersToHire) > 0

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        callback.append_inbox_callback(self._inbox_packet_received)
        self.family_position = kwargs.get('family_position')
        self.ecc_map = kwargs.get('ecc_map')
        self.family_snapshot = kwargs.get('family_snapshot')

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        p2p_service.SendIdentity(self.target_idurl, wide=True)

    def doSupplierConnect(self, *args, **kwargs):
        """
        Action method.
        """
        from customer import supplier_connector
        from customer import fire_hire
        from raid import eccmap
        position = self.family_position
        if not position:
            lg.warn('position for new supplier is unknown, will "guess"')
            current_suppliers = list(contactsdb.suppliers())
            for i in range(len(current_suppliers)):
                if not current_suppliers[i].strip():
                    position = i
                    break
                if current_suppliers[i] in fire_hire.A().dismiss_list:
                    position = i
                    break
        sc = supplier_connector.by_idurl(self.target_idurl)
        if not sc:
            sc = supplier_connector.create(
                supplier_idurl=self.target_idurl,
                customer_idurl=my_id.getLocalID(),
            )
        sc.automat(
            'connect',
            family_position=position,
            ecc_map=(self.ecc_map or eccmap.Current().name),
            family_snapshot=self.family_snapshot,
        )
        sc.set_callback('supplier_finder', self._supplier_connector_state)

    def doDHTFindRandomUser(self, *args, **kwargs):
        """
        Action method.
        """
        t = lookup.start()
        t.result_defer.addCallback(self._nodes_lookup_finished)
        t.result_defer.addErrback(lambda err: self.automat('users-not-found'))

    def doCleanPrevUser(self, *args, **kwargs):
        """
        Action method.
        """
        from customer import supplier_connector
        sc = supplier_connector.by_idurl(self.target_idurl)
        if sc:
            sc.remove_callback('supplier_finder')
        self.target_idurl = None

    def doRememberUser(self, *args, **kwargs):
        """
        Action method.
        """
        self.target_idurl = strng.to_bin(args[0])

    def doPopCandidate(self, *args, **kwargs):
        """
        Action method.
        """
        global _SuppliersToHire
        self.target_idurl = _SuppliersToHire.pop()

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """
        from customer import fire_hire
        fire_hire.A('supplier-connected', *args, **kwargs)

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        from customer import fire_hire
        fire_hire.A('search-failed', *args, **kwargs)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        from customer import supplier_connector
        global _SupplierFinder
        del _SupplierFinder
        _SupplierFinder = None
        callback.remove_inbox_callback(self._inbox_packet_received)
        if self.target_idurl:
            sc = supplier_connector.by_idurl(self.target_idurl)
            if sc:
                sc.remove_callback('supplier_finder')
            self.target_idurl = None
        self.destroy()
        lg.out(14, 'supplier_finder.doDestroyMy index=%s' % self.index)

    #------------------------------------------------------------------------------

    def _inbox_packet_received(self, newpacket, info, status, error_message):
        self.automat('inbox-packet', (newpacket, info, status, error_message))
        return False

    def _nodes_lookup_finished(self, idurls):
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._nodes_lookup_finished : %r' % idurls)
        if not idurls:
            self.automat('users-not-found')
            return
        # if driver.is_on('service_proxy_transport'):
        #     current_router_idurl = config.conf().getString('services/proxy-transport/current-router', '').strip()
        #     if current_router_idurl and current_router_idurl in idurls:
        #         idurls.remove(current_router_idurl)
        for idurl in idurls:
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if len(myprotos.intersection(remoteprotos)) > 0:
                self.automat('found-one-user', idurl)
                return
        self.automat('users-not-found')

    def _supplier_connector_state(self, supplier_idurl, newstate, **kwargs):
        if supplier_idurl != self.target_idurl:
            return
        if newstate in ['DISCONNECTED', 'NO_SERVICE', ]:
            self.automat('supplier-not-connected')
            return
        if newstate is not 'CONNECTED':
            return
        if contactsdb.is_supplier(self.target_idurl):
            return
        family_position = kwargs.get('family_position')
        ecc_map = kwargs.get('ecc_map')
        self.automat('supplier-connected', self.target_idurl, family_position=family_position, ecc_map=ecc_map, family_snapshot=self.family_snapshot)
