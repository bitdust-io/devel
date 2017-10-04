#!/usr/bin/python
# index_synchronizer.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (index_synchronizer.py) is part of BitDust Software.
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
.. module:: index_synchronizer.

.. role:: red

.. raw:: html

    <a href="http://bitdust.io/automats/index_synchronizer/index_synchronizer.png" target="_blank">
    <img src="http://bitdust.io/automats/index_synchronizer/index_synchronizer.png" style="max-width:100%;">
    </a>


Here is a state machine ``index_synchronizer()``, it is aimed to synchronize
local backup index database with remote suppliers.

This allows to restore the index file (with all your backup IDs and files and folders names)
from your suppliers in case of data lost.

The purpose of index_synchronizer() automat is to sync users's backup database to remote computers.
In case of loss of all local data - backup database will be restored from the suppliers.

The database includes the list of folders to be backed up, optional schedule for the backups,
and most importantly, a list of already created backups by its ID.

Thus if the user has made recovery of his account and restore the backup database -
he can recover his data from remote machines by recognized backup ID.

Every time any local change was made to the database it must synchronized with remote copies.

At first step, index_synchronizer() requests all remote copies of the database from suppliers.
When new file arrives from supplier, "backup_control" starts a validation against
current local index file and update local copy if required.
On next step index_synchronizer() sends a latest version of index file to all suppliers to hold.

The backup_monitor() machine should be restarted every one hour
or every time when your backups is changed.
It sends "restart" event to index_synchronizer() to synchronize index file.


BitDust index_synchronizer() Automat

EVENTS:
    * :red:`all-acked`
    * :red:`all-responded`
    * :red:`index-file-received`
    * :red:`init`
    * :red:`pull`
    * :red:`push`
    * :red:`shutdown`
    * :red:`timer-15sec`
    * :red:`timer-1min`
    * :red:`timer-5min`
"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import nameurl
from lib import packetid

from p2p import commands
from p2p import contact_status

from system import bpio

from userid import my_id
from contacts import contactsdb

from main import settings

from transport import gateway

from crypt import encrypted
from crypt import signed
from crypt import key

from services import driver

from customer import supplier_connector

#------------------------------------------------------------------------------

_IndexSynchronizer = None

#------------------------------------------------------------------------------


def is_synchronized():
    if not A():
        return False
    return A().state == 'IN_SYNC!'

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _IndexSynchronizer
    if event is None and arg is None:
        return _IndexSynchronizer
    if _IndexSynchronizer is None:
        _IndexSynchronizer = IndexSynchronizer('index_synchronizer', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _IndexSynchronizer.automat(event, arg)
    return _IndexSynchronizer

#------------------------------------------------------------------------------


class IndexSynchronizer(automat.Automat):
    """
    This class implements all the functionality of the ``index_synchronizer()``
    state machine.
    """

    timers = {
        'timer-1min': (60, ['NO_INFO']),
        'timer-5min': (300, ['IN_SYNC!']),
        'timer-15sec': (15.0, ['REQUEST?', 'SENDING']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of index_synchronizer() machine.
        """
        self.latest_supplier_revision = -1
        self.current_local_revision = -1
        self.requesting_suppliers = set()
        self.requested_suppliers_number = 0
        self.sending_suppliers = set()
        self.sent_suppliers_number = 0

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when index_synchronizer() state were
        changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in
        the index_synchronizer() but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python
        <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'NO_INFO'
                self.doInit(arg)
        #---IN_SYNC!---
        elif self.state == 'IN_SYNC!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'push':
                self.state = 'SENDING'
                self.doSuppliersSendIndexFile(arg)
            elif event == 'pull' or event == 'timer-5min':
                self.state = 'REQUEST?'
                self.doSuppliersRequestIndexFile(arg)
        #---REQUEST?---
        elif self.state == 'REQUEST?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'timer-15sec' and not self.isSomeResponded(arg):
                self.state = 'NO_INFO'
            elif (event == 'all-responded' or (event == 'timer-15sec' and self.isSomeResponded(arg))) and self.isVersionChanged(arg):
                self.state = 'SENDING'
                self.doSuppliersSendIndexFile(arg)
            elif event == 'index-file-received':
                self.doCheckVersion(arg)
            elif (event == 'all-responded' or (event == 'timer-15sec' and self.isSomeResponded(arg))) and not self.isVersionChanged(arg):
                self.state = 'IN_SYNC!'
        #---SENDING---
        elif self.state == 'SENDING':
            if event == 'timer-15sec' and not self.isSomeAcked(arg):
                self.state = 'NO_INFO'
            elif event == 'all-acked' or (event == 'timer-15sec' and self.isSomeAcked(arg)):
                self.state = 'IN_SYNC!'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'pull':
                self.state = 'REQUEST?'
                self.doSuppliersRequestIndexFile(arg)
        #---NO_INFO---
        elif self.state == 'NO_INFO':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'push' or event == 'pull' or event == 'timer-1min':
                self.state = 'REQUEST?'
                self.doSuppliersRequestIndexFile(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isSomeAcked(self, arg):
        """
        Condition method.
        """
        return len(self.sending_suppliers) < self.sent_suppliers_number

    def isSomeResponded(self, arg):
        """
        Condition method.
        """
        return len(self.requesting_suppliers) < self.requested_suppliers_number

    def isVersionChanged(self, arg):
        """
        Condition method.
        """
        if self.current_local_revision < 0:
            # no info about current local version : assume version was changed
            return True
        return self.current_local_revision != self.latest_supplier_revision

    def doInit(self, arg):
        """
        Action method.
        """

    def doSuppliersRequestIndexFile(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer.doSuppliersRequestIndexFile')
        if driver.is_started('service_backups'):
            from storage import backup_control
            self.current_local_revision = backup_control.revision()
        else:
            self.current_local_revision = -1
        self.latest_supplier_revision = -1
        self.requesting_suppliers.clear()
        self.requested_suppliers_number = 0
        packetID = settings.BackupIndexFileName()
        localID = my_id.getLocalID()
        for supplierId in contactsdb.suppliers():
            if not supplierId:
                continue
            if not contact_status.isOnline(supplierId):
                continue
            newpacket = signed.Packet(
                commands.Retrieve(),
                localID,
                localID,
                packetid.RemotePath(packetID),
                '',
                supplierId)
            pkt_out = gateway.outbox(newpacket, callbacks={
                commands.Data(): self._on_supplier_response,
                commands.Fail(): self._on_supplier_response, })
            if pkt_out:
                self.requesting_suppliers.add(supplierId)
                self.requested_suppliers_number += 1
            if _Debug:
                lg.out(_DebugLevel, '    %s sending to %s' %
                       (pkt_out, nameurl.GetName(supplierId)))

    def doSuppliersSendIndexFile(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer.doSuppliersSendIndexFile')
        packetID = settings.BackupIndexFileName()
        self.sending_suppliers.clear()
        self.sent_suppliers_number = 0
        src = bpio.ReadBinaryFile(settings.BackupIndexFilePath())
        localID = my_id.getLocalID()
        b = encrypted.Block(
            localID,
            packetID,
            0,
            key.NewSessionKey(),
            key.SessionKeyType(),
            True,
            src)
        Payload = b.Serialize()
        for supplierId in contactsdb.suppliers():
            if not supplierId:
                continue
            if not contact_status.isOnline(supplierId):
                continue
            newpacket = signed.Packet(
                commands.Data(), localID, localID, packetID,
                Payload, supplierId)
            pkt_out = gateway.outbox(newpacket, callbacks={
                commands.Ack(): self._on_supplier_acked,
                commands.Fail(): self._on_supplier_acked, })
            if pkt_out:
                self.sending_suppliers.add(supplierId)
                self.sent_suppliers_number += 1
            if _Debug:
                lg.out(_DebugLevel, '    %s sending to %s' %
                       (pkt_out, nameurl.GetName(supplierId)))

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()
        global _IndexSynchronizer
        del _IndexSynchronizer
        _IndexSynchronizer = None

    def doCheckVersion(self, arg):
        """
        Action method.
        """
        _, supplier_revision = arg
        if supplier_revision > self.latest_supplier_revision:
            self.latest_supplier_revision = supplier_revision

    def _on_supplier_response(self, newpacket, pkt_out):
        if newpacket.Command == commands.Data():
            self.requesting_suppliers.discard(newpacket.RemoteID)
        elif newpacket.Command == commands.Fail():
            self.requesting_suppliers.discard(newpacket.OwnerID)
#             sc = supplier_connector.by_idurl(newpacket.OwnerID)
#             if sc:
#                 sc.automat('fail', newpacket)
#             else:
#                 raise Exception('supplier connector was not found')
        else:
            raise Exception('wrong type of response')
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer._on_supplier_response %s, pending: %d, total: %d' % (
                newpacket, len(self.requesting_suppliers), self.requested_suppliers_number))
        if len(self.requesting_suppliers) == 0:
            self.automat('all-responded')

    def _on_supplier_acked(self, newpacket, info):
        sc = supplier_connector.by_idurl(newpacket.OwnerID)
        if sc:
            sc.automat(newpacket.Command.lower(), newpacket)
        else:
            raise Exception('not found supplier connector')
        self.sending_suppliers.discard(newpacket.OwnerID)
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer._on_supplier_acked %s, pending: %d, total: %d' % (
                newpacket, len(self.sending_suppliers), self.sent_suppliers_number))
        if len(self.sending_suppliers) == 0:
            self.automat('all-acked')
