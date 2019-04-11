#!/usr/bin/python
# index_synchronizer.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

    <a href="https://bitdust.io/automats/index_synchronizer/index_synchronizer.png" target="_blank">
    <img src="https://bitdust.io/automats/index_synchronizer/index_synchronizer.png" style="max-width:100%;">
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
or every time when your files were changed.
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

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import nameurl

from p2p import commands
from p2p import online_status
from p2p import p2p_service

from system import bpio

from userid import my_id
from userid import global_id

from contacts import contactsdb

from main import settings
from main import events

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


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _IndexSynchronizer
    if event is None and not args:
        return _IndexSynchronizer
    if _IndexSynchronizer is None:
        _IndexSynchronizer = IndexSynchronizer(
            name='index_synchronizer',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _IndexSynchronizer.automat(event, *args, **kwargs)
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
        'timer-15sec': (15.0, ['REQUEST?','SENDING']),
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

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when index_synchronizer() state were
        changed.
        """
        if newstate == 'IN_SYNC!' and oldstate != newstate:
            events.send('my-backup-index-synchronized', data={})
        if newstate == 'NO_INFO' and oldstate in ['REQUEST?', 'SENDING', ]:
            events.send('my-backup-index-out-of-sync', data={})

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in
        the index_synchronizer() but its state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python
        <https://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'NO_INFO'
                self.doInit(*args, **kwargs)
        #---IN_SYNC!---
        elif self.state == 'IN_SYNC!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'push':
                self.state = 'SENDING'
                self.doSuppliersSendIndexFile(*args, **kwargs)
            elif event == 'pull' or event == 'timer-5min':
                self.state = 'REQUEST?'
                self.doSuppliersRequestIndexFile(*args, **kwargs)
        #---REQUEST?---
        elif self.state == 'REQUEST?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doCancelRequests(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-15sec' and not self.isSomeResponded(*args, **kwargs):
                self.state = 'NO_INFO'
                self.doCancelRequests(*args, **kwargs)
            elif ( event == 'all-responded' or ( event == 'timer-15sec' and self.isSomeResponded(*args, **kwargs) ) ) and self.isVersionChanged(*args, **kwargs):
                self.state = 'SENDING'
                self.doCancelRequests(*args, **kwargs)
                self.doSuppliersSendIndexFile(*args, **kwargs)
            elif event == 'index-file-received':
                self.doCheckVersion(*args, **kwargs)
            elif ( event == 'all-responded' or ( event == 'timer-15sec' and self.isSomeResponded(*args, **kwargs) ) ) and not self.isVersionChanged(*args, **kwargs):
                self.state = 'IN_SYNC!'
                self.doCancelRequests(*args, **kwargs)
        #---SENDING---
        elif self.state == 'SENDING':
            if event == 'timer-15sec' and not self.isSomeAcked(*args, **kwargs):
                self.state = 'NO_INFO'
            elif event == 'all-acked' or ( event == 'timer-15sec' and self.isSomeAcked(*args, **kwargs) ):
                self.state = 'IN_SYNC!'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'pull':
                self.state = 'REQUEST?'
                self.doSuppliersRequestIndexFile(*args, **kwargs)
        #---NO_INFO---
        elif self.state == 'NO_INFO':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'push' or event == 'pull' or event == 'timer-1min':
                self.state = 'REQUEST?'
                self.doSuppliersRequestIndexFile(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isSomeAcked(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.sending_suppliers) < self.sent_suppliers_number

    def isSomeResponded(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.requesting_suppliers) < self.requested_suppliers_number

    def isVersionChanged(self, *args, **kwargs):
        """
        Condition method.
        """
        if self.current_local_revision < 0:
            # no info about current local version : assume version was changed
            return True
        return self.current_local_revision != self.latest_supplier_revision

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doSuppliersRequestIndexFile(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer.doSuppliersRequestIndexFile')
        if driver.is_on('service_backups'):
            from storage import backup_control
            self.current_local_revision = backup_control.revision()
        else:
            self.current_local_revision = -1
        self.latest_supplier_revision = -1
        self.requesting_suppliers.clear()
        self.requested_suppliers_number = 0
        packetID = global_id.MakeGlobalID(
            customer=my_id.getGlobalID(key_alias='master'),
            path=settings.BackupIndexFileName(),
        )
        # packetID = settings.BackupIndexFileName()
        localID = my_id.getLocalIDURL()
        for supplierId in contactsdb.suppliers():
            if not supplierId:
                continue
            if online_status.isOffline(supplierId):
                continue
            pkt_out = p2p_service.SendRetreive(
                localID,
                localID,
                packetID,
                supplierId,
                callbacks={
                    commands.Data(): self._on_supplier_response,
                    commands.Fail(): self._on_supplier_response,
                }
            )
#             newpacket = signed.Packet(
#                 commands.Retrieve(),
#                 localID,
#                 localID,
#                 packetid.RemotePath(packetID),
#                 '',
#                 supplierId)
#             pkt_out = gateway.outbox(newpacket, callbacks={
#                 commands.Data(): self._on_supplier_response,
#                 commands.Fail(): self._on_supplier_response, })
            if pkt_out:
                self.requesting_suppliers.add(supplierId)
                self.requested_suppliers_number += 1
            if _Debug:
                lg.out(_DebugLevel, '    %s sending to %s' %
                       (pkt_out, nameurl.GetName(supplierId)))

    def doSuppliersSendIndexFile(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer.doSuppliersSendIndexFile')
        packetID = global_id.MakeGlobalID(
            customer=my_id.getGlobalID(key_alias='master'),
            path=settings.BackupIndexFileName(),
        )
        self.sending_suppliers.clear()
        self.sent_suppliers_number = 0
        localID = my_id.getLocalIDURL()
        b = encrypted.Block(
            CreatorID=localID,
            BackupID=packetID,
            BlockNumber=0,
            SessionKey=key.NewSessionKey(),
            SessionKeyType=key.SessionKeyType(),
            LastBlock=True,
            Data=bpio.ReadBinaryFile(settings.BackupIndexFilePath()),
        )
        Payload = b.Serialize()
        for supplierId in contactsdb.suppliers():
            if not supplierId:
                continue
            if online_status.isOffline(supplierId):
                continue
            newpacket, pkt_out = p2p_service.SendData(
                raw_data=Payload,
                ownerID=localID,
                creatorID=localID,
                remoteID=supplierId,
                packetID=packetID,
                callbacks={
                    commands.Ack(): self._on_supplier_acked,
                    commands.Fail(): self._on_supplier_acked,
                },
            )
            # newpacket = signed.Packet(
            #     commands.Data(), localID, localID, packetID,
            #     Payload, supplierId)
            # pkt_out = gateway.outbox(newpacket, callbacks={
            #     commands.Ack(): self._on_supplier_acked,
            #     commands.Fail(): self._on_supplier_acked, })
            if pkt_out:
                self.sending_suppliers.add(supplierId)
                self.sent_suppliers_number += 1
            if _Debug:
                lg.out(_DebugLevel, '    %s sending to %s' %
                       (newpacket, nameurl.GetName(supplierId)))

    def doCancelRequests(self, *args, **kwargs):
        """
        Action method.
        """
#         packetID = global_id.MakeGlobalID(
#             customer=my_id.getGlobalID(key_alias='master'),
#             path=settings.BackupIndexFileName(),
#         )
#         packetsToCancel = packet_out.search_by_backup_id(packetID)
#         for pkt_out in packetsToCancel:
#             if pkt_out.outpacket.Command == commands.Retrieve():
#                 lg.warn('sending "cancel" to %s addressed to %s from index_synchronizer' % (
#                     pkt_out, pkt_out.remote_idurl, ))
#                 pkt_out.automat('cancel')

    def doCheckVersion(self, *args, **kwargs):
        """
        Action method.
        """
        _, supplier_revision = args[0]
        if supplier_revision > self.latest_supplier_revision:
            self.latest_supplier_revision = supplier_revision

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.unregister()
        global _IndexSynchronizer
        del _IndexSynchronizer
        _IndexSynchronizer = None

    def _on_supplier_response(self, newpacket, pkt_out):
        if newpacket.Command == commands.Data():
            wrapped_packet = signed.Unserialize(newpacket.Payload)
            if not wrapped_packet or not wrapped_packet.Valid():
                lg.err('incoming Data() is not valid')
                return
            from storage import backup_control
            backup_control.IncomingSupplierBackupIndex(wrapped_packet)
            # p2p_service.SendAck(newpacket)
            self.requesting_suppliers.discard(wrapped_packet.RemoteID)
        elif newpacket.Command == commands.Fail():
            self.requesting_suppliers.discard(newpacket.OwnerID)
        else:
            raise Exception('wrong type of response')
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer._on_supplier_response %s, pending: %d, total: %d' % (
                newpacket, len(self.requesting_suppliers), self.requested_suppliers_number))
        if len(self.requesting_suppliers) == 0:
            self.automat('all-responded')

    def _on_supplier_acked(self, newpacket, info):
        self.sending_suppliers.discard(newpacket.OwnerID)
        sc = supplier_connector.by_idurl(newpacket.OwnerID)
        if sc:
            sc.automat(newpacket.Command.lower(), newpacket)
        else:
            lg.warn('did not found supplier connector for %r' % newpacket.OwnerID)
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer._on_supplier_acked %s, pending: %d, total: %d' % (
                newpacket, len(self.sending_suppliers), self.sent_suppliers_number))
        if len(self.sending_suppliers) == 0:
            self.automat('all-acked')
