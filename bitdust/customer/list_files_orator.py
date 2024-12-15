#!/usr/bin/env python
# list_files_orator.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (list_files_orator.py) is part of BitDust Software.
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
#
"""
.. module:: list_files_orator.

.. raw:: html

    <a href="https://bitdust.io/automats/list_files_orator/list_files_orator.png" target="_blank">
    <img src="https://bitdust.io/automats/list_files_orator/list_files_orator.png" style="max-width:100%;">
    </a>

This simple state machine requests a list of files stored on remote nodes.

Before that, it scans the local backup folder and prepare an index of existing data pieces.


EVENTS:
    * :red:`inbox-files`
    * :red:`init`
    * :red:`local-files-done`
    * :red:`need-files`
    * :red:`supplier-connected`
    * :red:`timer-20sec`
    * :red:`timer-2sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

import time

#------------------------------------------------------------------------------

from twisted.internet.defer import maybeDeferred, Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.contacts import contactsdb

from bitdust.main import events
from bitdust.main import settings

from bitdust.services import driver

from bitdust.p2p import p2p_service
from bitdust.p2p import online_status
from bitdust.p2p import p2p_connector
from bitdust.p2p import propagate

from bitdust.userid import my_id
from bitdust.userid import id_url

#------------------------------------------------------------------------------

_ListFilesOrator = None

#------------------------------------------------------------------------------


def is_synchronized(customer_idurl=None):
    if not A():
        return False
    customer_idurl = customer_idurl or my_id.getIDURL()
    if A().state == 'SAW_FILES':
        if A().last_time_saw_files.get(customer_idurl, -1) > 0:
            return True
        return False
    if A().state in [
        'LOCAL_FILES',
        'REMOTE_FILES',
    ]:
        if A().target_customer_idurl != customer_idurl:
            return A().last_time_saw_files.get(customer_idurl, -1) > 0
        lt_saw_files = A().last_time_saw_files.get(customer_idurl, -1)
        if lt_saw_files > 0 and time.time() - lt_saw_files < 20:
            return True
    return False


def synchronize_files(customer_idurl=None):
    ret = Deferred()
    if not A():
        ret.errback(Exception('not initialized'))
        return ret
    customer_idurl = customer_idurl or my_id.getIDURL()
    if A().state in ['SAW_FILES', 'NO_FILES']:
        A('need-files', customer_idurl=customer_idurl, result_defer=ret)
        return ret

    def _on_list_files_orator_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, oldstate=oldstate, newstate=newstate, event=event_string)
        if newstate != oldstate and newstate in ['SAW_FILES', 'NO_FILES']:
            A().removeStateChangedCallback(_on_list_files_orator_state_changed)
            A('need-files', customer_idurl=customer_idurl, result_defer=ret)

    A().addStateChangedCallback(_on_list_files_orator_state_changed)
    return ret


#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _ListFilesOrator
    if event is None:
        return _ListFilesOrator
    if _ListFilesOrator is None:
        _ListFilesOrator = ListFilesOrator(
            name='list_files_orator',
            state='NO_FILES',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _ListFilesOrator.automat(event, *args, **kwargs)
    return _ListFilesOrator


def Destroy():
    """
    Destroy list_files_orator() automat and remove its instance from memory.
    """
    global _ListFilesOrator
    if _ListFilesOrator is None:
        return
    _ListFilesOrator.destroy()
    del _ListFilesOrator
    _ListFilesOrator = None


class ListFilesOrator(automat.Automat):

    """
    A class to request list of my files from my suppliers and also scan the
    local files.
    """

    timers = {
        'timer-2sec': (2.0, ['REMOTE_FILES']),
        'timer-20sec': (20.0, ['REMOTE_FILES']),
    }

    def init(self):
        self.target_customer_idurl = None
        self.result_defer = None
        self.critical_suppliers_number = 0
        self.last_time_saw_files = {}
        self.ping_required = True
        self.received_lf_counter = 0
        self.requested_lf_packet_ids = set()
        events.add_subscriber(self._on_my_identity_rotated, 'my-identity-rotated')
        events.add_subscriber(self._on_supplier_connected, 'supplier-connected')

    def shutdown(self):
        self.result_defer = None
        self.received_lf_counter = 0
        self.last_time_saw_files.clear()
        self.requested_lf_packet_ids.clear()
        events.remove_subscriber(self._on_supplier_connected, 'supplier-connected')
        events.remove_subscriber(self._on_my_identity_rotated, 'my-identity-rotated')

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        if self.target_customer_idurl is None or self.target_customer_idurl == my_id.getIDURL():
            if driver.is_on('service_backups'):
                # TODO: rebuild using "list-files-orator-state-changed" event
                from bitdust.storage import backup_monitor
                backup_monitor.A('list_files_orator.state', newstate)
        if newstate == 'SAW_FILES':
            lt_saw_files = self.last_time_saw_files.get(self.target_customer_idurl, -1)
            if lt_saw_files <= 0 or time.time() - lt_saw_files < 20:
                events.send('my-list-files-refreshed', data={'customer_idurl': self.target_customer_idurl})
            self.last_time_saw_files[self.target_customer_idurl] = time.time()
        if newstate == 'NO_FILES':
            self.last_time_saw_files[self.target_customer_idurl] = -1
        if newstate in ['SAW_FILES', 'NO_FILES']:
            self.target_customer_idurl = None
            if self.result_defer:
                if not self.result_defer.called:
                    self.result_defer.callback(self.state)
                self.result_defer = None

    def A(self, event, *args, **kwargs):
        #---NO_FILES---
        if self.state == 'NO_FILES':
            if event == 'need-files':
                self.state = 'LOCAL_FILES'
                self.doReadLocalFiles(*args, **kwargs)
            elif event == 'init':
                pass
        #---LOCAL_FILES---
        elif self.state == 'LOCAL_FILES':
            if event == 'local-files-done' and p2p_connector.A().state == 'CONNECTED':
                self.state = 'REMOTE_FILES'
                self.doRequestFilesAllSuppliers(*args, **kwargs)
            elif event == 'local-files-done' and p2p_connector.A().state != 'CONNECTED':
                self.state = 'NO_FILES'
        #---REMOTE_FILES---
        elif self.state == 'REMOTE_FILES':
            if event == 'supplier-connected':
                self.doRequestFilesOneSupplier(*args, **kwargs)
            elif event == 'timer-20sec' and not self.isEnoughListFilesReceived(*args, **kwargs) and not self.isSomeConnecting(*args, **kwargs):
                self.state = 'NO_FILES'
            elif (event == 'timer-2sec' and self.isEnoughListFilesReceived(*args, **kwargs)) or (event == 'inbox-files' and self.isAllListFilesReceived(*args, **kwargs)):
                self.state = 'SAW_FILES'
        #---SAW_FILES---
        elif self.state == 'SAW_FILES':
            if event == 'need-files':
                self.state = 'LOCAL_FILES'
                self.doReadLocalFiles(*args, **kwargs)
        return None

    def isAllListFilesReceived(self, *args, **kwargs):
        if _Debug:
            lg.out(_DebugLevel, 'list_files_orator.isAllListFilesReceived need %d more' % len(self.requested_lf_packet_ids))
        return len(self.requested_lf_packet_ids) == 0

    def isSomeConnecting(self, *args, **kwargs):
        """
        Condition method.
        """
        from bitdust.customer import supplier_connector
        for one_supplier_connector in supplier_connector.connectors(customer_idurl=self.target_customer_idurl).values():
            if one_supplier_connector.state not in ['CONNECTED', 'DISCONNECTED', 'NO_SERVICE']:
                return True
        return False

    def isEnoughListFilesReceived(self, *args, **kwargs):
        """
        Condition method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'list_files_orator.isEnoughListFilesReceived %d list files received' % self.received_lf_counter)
        return self.received_lf_counter >= self.critical_suppliers_number

    def doReadLocalFiles(self, *args, **kwargs):
        from bitdust.storage import backup_matrix
        self.target_customer_idurl = kwargs.get('customer_idurl') or my_id.getIDURL()
        self.result_defer = kwargs.get('result_defer')
        self.critical_suppliers_number = 0
        maybeDeferred(backup_matrix.ReadLocalFiles).addBoth(lambda x: self.automat('local-files-done'))

    def doRequestFilesAllSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        if self.ping_required:
            self.ping_required = False
            propagate.ping_suppliers(customer_idurl=self.target_customer_idurl).addBoth(self._do_request)
        else:
            self._do_request()

    def doRequestFilesOneSupplier(self, *args, **kwargs):
        """
        Action method.
        """
        supplier_idurl = args[0]
        if _Debug:
            lg.out(_DebugLevel, 'list_files_orator.doRequestFilesOneSupplier from %s' % supplier_idurl)
        outpacket = p2p_service.SendListFiles(
            target_supplier=supplier_idurl,
            customer_idurl=self.target_customer_idurl,
            timeout=settings.P2PTimeOut(),
        )
        if outpacket:
            self.requested_lf_packet_ids.add(outpacket.PacketID)
        else:
            lg.err('failed sending ListFiles() to %r' % supplier_idurl)

    def _do_request(self, x=None):
        from bitdust.raid import eccmap
        self.received_lf_counter = 0
        self.requested_lf_packet_ids.clear()
        known_suppliers = contactsdb.suppliers(customer_idurl=self.target_customer_idurl)
        try:
            self.critical_suppliers_number = eccmap.GetCorrectableErrors(len(known_suppliers))
        except:
            lg.warn('number of known suppliers for customer %r is not standard' % self.target_customer_idurl)
            self.critical_suppliers_number = int(float(len(known_suppliers))*0.75)
        for idurl in known_suppliers:
            if idurl:
                if online_status.isOnline(idurl):
                    if _Debug:
                        lg.out(_DebugLevel, 'list_files_orator._do_request  ListFiles() from my supplier %s' % idurl)
                    outpacket = p2p_service.SendListFiles(
                        target_supplier=idurl,
                        customer_idurl=self.target_customer_idurl,
                        timeout=settings.P2PTimeOut(),
                    )
                    if outpacket:
                        self.requested_lf_packet_ids.add(outpacket.PacketID)
                    else:
                        lg.err('failed sending ListFiles() to %r' % idurl)
                else:
                    lg.warn('skip sending ListFiles() because %s is not online' % idurl)

    def _on_my_identity_rotated(self, evt):
        self.ping_required = True
        if _Debug:
            lg.dbg(_DebugLevel, 'updating ping_required=True')

    def _on_supplier_connected(self, evt):
        if id_url.field(evt.data['customer_idurl']) == self.target_customer_idurl:
            if _Debug:
                lg.dbg(_DebugLevel, 'for customer %r single supplier %r was connected' % (self.target_customer_idurl, evt.data['supplier_idurl']))
            self.automat('supplier-connected', evt.data['supplier_idurl'])


#------------------------------------------------------------------------------


def IncomingListFiles(newpacket):
    """
    Called from ``p2p.backup_control`` to pass incoming "ListFiles" packet
    here.
    """
    if not A():
        return
    if newpacket.PacketID in A().requested_lf_packet_ids:
        A().received_lf_counter += 1
        A().requested_lf_packet_ids.discard(newpacket.PacketID)
        A('inbox-files', newpacket)
    else:
        if _Debug:
            lg.dbg(_DebugLevel, 'received and ignored %r, currently target customer is %r' % (newpacket, A().target_customer_idurl))
