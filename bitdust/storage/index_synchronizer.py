#!/usr/bin/python
# index_synchronizer.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
    * :red:`instant`
    * :red:`pull`
    * :red:`push`
    * :red:`shutdown`
    * :red:`timer-10sec`
    * :red:`timer-15sec`
    * :red:`timer-1min`
    * :red:`timer-5min`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import time

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import nameurl

from bitdust.p2p import commands
from bitdust.p2p import online_status
from bitdust.p2p import p2p_service
from bitdust.p2p import propagate

from bitdust.system import bpio

from bitdust.userid import my_id
from bitdust.userid import global_id

from bitdust.contacts import contactsdb

from bitdust.main import settings
from bitdust.main import events

from bitdust.crypt import encrypted
from bitdust.crypt import signed
from bitdust.crypt import key

from bitdust.transport import packet_out

from bitdust.services import driver

from bitdust.customer import supplier_connector

#------------------------------------------------------------------------------

_IndexSynchronizer = None

#------------------------------------------------------------------------------


def is_synchronized():
    if not A():
        return False
    if A().state == 'IN_SYNC!':
        return True
    if A().state in ['REQUEST?', 'SENDING']:
        if A().last_time_in_sync > 0 and time.time() - A().last_time_in_sync < 30:
            return True
    return False


def is_synchronizing():
    if not A():
        return False
    return A().state in ['REQUEST?', 'SENDING']


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

    fast = False

    timers = {
        'timer-1min': (60, ['NO_INFO']),
        'timer-10sec': (10.0, ['REQUEST?']),
        'timer-15sec': (15.0, ['REQUEST?', 'SENDING']),
        'timer-5min': (300, ['IN_SYNC!']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation phase
        of index_synchronizer() machine.
        """
        self.latest_supplier_revision = -1
        self.current_local_revision = -1
        self.requesting_suppliers = set()
        self.requests_packets_sent = []
        self.requested_suppliers_number = 0
        self.sending_suppliers = set()
        self.sent_suppliers_number = 0
        self.outgoing_packets_ids = []
        self.last_time_in_sync = -1
        self.PushAgain = False

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when index_synchronizer() state were
        changed.
        """
        if newstate == 'IN_SYNC!':
            if A().last_time_in_sync > 0 and time.time() - A().last_time_in_sync < 30:
                if _Debug:
                    lg.dbg(_DebugLevel, 'backup index already synchronized %r seconds ago' % (time.time() - A().last_time_in_sync))
            else:
                if _Debug:
                    lg.dbg(_DebugLevel, 'backup index just synchronized, sending "my-backup-index-synchronized" event')
                events.send('my-backup-index-synchronized', data={})
            self.last_time_in_sync = time.time()
            if self.PushAgain:
                reactor.callLater(0, self.automat, 'instant')  # @UndefinedVariable
        if newstate == 'NO_INFO' and oldstate in ['REQUEST?', 'SENDING']:
            events.send('my-backup-index-out-of-sync', data={})
        if newstate == 'NO_INFO':
            self.last_time_in_sync = -1

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
            elif event == 'pull' or event == 'timer-5min':
                self.state = 'REQUEST?'
                self.doSuppliersRequestIndexFile(*args, **kwargs)
            elif event == 'push' or (event == 'instant' and self.PushAgain):
                self.state = 'SENDING'
                self.doSuppliersSendIndexFile(*args, **kwargs)
                self.PushAgain = False
                self.PullAgain = False
        #---REQUEST?---
        elif self.state == 'REQUEST?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doCancelRequests(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif (event == 'all-responded' or (event == 'timer-15sec' and self.isSomeResponded(*args, **kwargs))) and self.isVersionChanged(*args, **kwargs):
                self.state = 'SENDING'
                self.doCancelRequests(*args, **kwargs)
                self.doSuppliersSendIndexFile(*args, **kwargs)
                self.PushAgain = False
                self.PullAgain = False
            elif event == 'index-file-received':
                self.doCheckVersion(*args, **kwargs)
            elif (event == 'all-responded' or (event == 'timer-15sec' and self.isSomeResponded(*args, **kwargs))) and not self.isVersionChanged(*args, **kwargs):
                self.state = 'IN_SYNC!'
                self.doCancelRequests(*args, **kwargs)
            elif event == 'timer-10sec' and not self.isSomeResponded(*args, **kwargs) and self.isAllTimedOut(*args, **kwargs):
                self.state = 'NO_INFO'
                self.doCancelRequests(*args, **kwargs)
        #---SENDING---
        elif self.state == 'SENDING':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doCancelSendings(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'push':
                self.PushAgain = True
            elif event == 'timer-15sec' and not self.isSomeAcked(*args, **kwargs) and not self.PullAgain:
                self.state = 'NO_INFO'
                self.doCancelSendings(*args, **kwargs)
            elif (event == 'all-acked' or (event == 'timer-15sec' and self.isSomeAcked(*args, **kwargs))) and not self.PullAgain:
                self.state = 'IN_SYNC!'
                self.doCancelSendings(*args, **kwargs)
            elif event == 'pull':
                self.PullAgain = True
            elif (event == 'all-acked' or event == 'timer-15sec') and self.PullAgain:
                self.state = 'REQUEST?'
                self.doCancelSendings(*args, **kwargs)
                self.doSuppliersRequestIndexFile(*args, **kwargs)
                self.PullAgain = False
        #---NO_INFO---
        elif self.state == 'NO_INFO':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'push' or event == 'pull' or event == 'timer-1min':
                self.state = 'REQUEST?'
                self.doSuppliersRequestIndexFile(*args, **kwargs)
                self.PushAgain = False
                self.PullAgain = False
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
            # no info about current local version - assume version was changed
            return True
        return self.current_local_revision != self.latest_supplier_revision

    def isAllTimedOut(self, *args, **kwargs):
        """
        Condition method.
        """
        for packetID, supplierIDURL in self.requests_packets_sent:
            pkts_out = packet_out.search_many(
                command=commands.Retrieve(),
                remote_idurl=supplierIDURL,
                packet_id=packetID,
            )
            if pkts_out:
                return False
        return True

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.ping_required = False

    def doSuppliersRequestIndexFile(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer.doSuppliersRequestIndexFile')
        if driver.is_on('service_backups'):
            from bitdust.storage import backup_fs
            self.current_local_revision = backup_fs.revision()
        else:
            self.current_local_revision = -1
        self.latest_supplier_revision = -1
        self.requesting_suppliers.clear()
        self.requested_suppliers_number = 0
        self.requests_packets_sent = []
        if self.ping_required:
            propagate.ping_suppliers().addBoth(self._do_retrieve)
            self.ping_required = False
        else:
            self._do_retrieve()

    def doSuppliersSendIndexFile(self, *args, **kwargs):
        """
        Action method.
        """
        packetID = global_id.MakeGlobalID(
            customer=my_id.getGlobalID(key_alias='master'),
            # path=packetid.MakeIndexFileNamePacketID(),
            path=settings.BackupIndexFileName(),
        )
        self.sending_suppliers.clear()
        self.outgoing_packets_ids = []
        self.sent_suppliers_number = 0
        localID = my_id.getIDURL()
        data = bpio.ReadBinaryFile(settings.BackupIndexFilePath())
        b = encrypted.Block(
            CreatorID=localID,
            BackupID=packetID,
            BlockNumber=0,
            SessionKey=key.NewSessionKey(session_key_type=key.SessionKeyType()),
            SessionKeyType=key.SessionKeyType(),
            LastBlock=True,
            Data=data,
        )
        Payload = b.Serialize()
        if _Debug:
            lg.args(_DebugLevel, pid=packetID, sz=len(data), payload=len(Payload), length=b.Length)
        for supplier_idurl in contactsdb.suppliers():
            if not supplier_idurl:
                continue
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc is None or sc.state != 'CONNECTED':
                continue
            if online_status.isOffline(supplier_idurl):
                continue
            newpacket, pkt_out = p2p_service.SendData(
                raw_data=Payload,
                ownerID=localID,
                creatorID=localID,
                remoteID=supplier_idurl,
                packetID=packetID,
                callbacks={
                    commands.Ack(): self._on_supplier_acked,
                    commands.Fail(): self._on_supplier_acked,
                },
            )
            if pkt_out:
                self.sending_suppliers.add(supplier_idurl)
                self.sent_suppliers_number += 1
                if newpacket.PacketID not in self.outgoing_packets_ids:
                    self.outgoing_packets_ids.append(newpacket.PacketID)
            if _Debug:
                lg.out(_DebugLevel, '    %s sending to %s' % (newpacket, nameurl.GetName(supplier_idurl)))

    def doCancelSendings(self, *args, **kwargs):
        """
        Action method.
        """
        for packet_id in self.outgoing_packets_ids:
            packetsToCancel = packet_out.search_by_packet_id(packet_id)
            for pkt_out in packetsToCancel:
                if pkt_out.outpacket.Command == commands.Data():
                    pkt_out.automat('cancel')

    def doCancelRequests(self, *args, **kwargs):
        """
        Action method.
        """


#         packetID = global_id.MakeGlobalID(
#             customer=my_id.getGlobalID(key_alias='master'),
#             path=settings.BackupIndexFileName(),
#         )
#         from bitdust.transport import packet_out
#         packetsToCancel = packet_out.search_by_packet_id(packetID)
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
        self.destroy()
        global _IndexSynchronizer
        del _IndexSynchronizer
        _IndexSynchronizer = None

    def _on_supplier_response(self, newpacket, info):
        wrapped_packet = signed.Unserialize(newpacket.Payload)
        if _Debug:
            lg.args(_DebugLevel, newpacket=newpacket, wrapped_packet=wrapped_packet)
        if not wrapped_packet or not wrapped_packet.Valid():
            lg.err('incoming Data() is not valid')
            return
        supplier_idurl = wrapped_packet.RemoteID
        from bitdust.storage import backup_control
        supplier_revision = backup_control.IncomingSupplierBackupIndex(wrapped_packet)
        self.requesting_suppliers.discard(supplier_idurl)
        if supplier_revision is not None:
            reactor.callLater(0, self.automat, 'index-file-received', (newpacket, supplier_revision))  # @UndefinedVariable
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer._on_supplier_response %s from %r, rev:%s, pending: %d, total: %d' % (newpacket, supplier_idurl, supplier_revision, len(self.requesting_suppliers), self.requested_suppliers_number))
        if len(self.requesting_suppliers) == 0:
            reactor.callLater(0, self.automat, 'all-responded')  # @UndefinedVariable

    def _on_supplier_fail(self, newpacket, info):
        if _Debug:
            lg.args(_DebugLevel, newpacket=newpacket)
        supplier_idurl = newpacket.CreatorID
        self.requesting_suppliers.discard(supplier_idurl)
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer._on_supplier_fail %s from %r, pending: %d, total: %d' % (newpacket, supplier_idurl, len(self.requesting_suppliers), self.requested_suppliers_number))
        if len(self.requesting_suppliers) == 0:
            reactor.callLater(0, self.automat, 'all-responded')  # @UndefinedVariable

    def _on_supplier_acked(self, newpacket, info):
        self.sending_suppliers.discard(newpacket.OwnerID)
        # if newpacket.PacketID in self.outgoing_packets_ids:
        #     self.outgoing_packets_ids.remove(newpacket.PacketID)
        sc = supplier_connector.by_idurl(newpacket.OwnerID)
        if sc:
            sc.automat(newpacket.Command.lower(), newpacket)
        else:
            lg.warn('did not found supplier connector for %r' % newpacket.OwnerID)
        if _Debug:
            lg.out(_DebugLevel, 'index_synchronizer._on_supplier_acked %s, pending: %d, total: %d' % (newpacket, len(self.sending_suppliers), self.sent_suppliers_number))
        if len(self.sending_suppliers) == 0:
            reactor.callLater(0, self.automat, 'all-acked')  # @UndefinedVariable

    def _do_retrieve(self, x=None):
        packetID = global_id.MakeGlobalID(
            customer=my_id.getGlobalID(key_alias='master'),
            # path=packetid.MakeIndexFileNamePacketID(),
            path=settings.BackupIndexFileName(),
        )
        localID = my_id.getIDURL()
        for supplier_idurl in contactsdb.suppliers():
            if not supplier_idurl:
                continue
            sc = supplier_connector.by_idurl(supplier_idurl)
            if sc is None or sc.state != 'CONNECTED':
                continue
            if online_status.isOffline(supplier_idurl):
                continue
            pkt_out = p2p_service.SendRetreive(
                ownerID=localID,
                creatorID=localID,
                packetID=packetID,
                remoteID=supplier_idurl,
                response_timeout=settings.P2PTimeOut(),
                callbacks={
                    commands.Data(): self._on_supplier_response,
                    commands.Fail(): self._on_supplier_fail,
                },
            )
            if pkt_out:
                self.requesting_suppliers.add(supplier_idurl)
                self.requested_suppliers_number += 1
                self.requests_packets_sent.append((packetID, supplier_idurl))
            if _Debug:
                lg.dbg(_DebugLevel, '%s sending to %s' % (pkt_out, nameurl.GetName(supplier_idurl)))
