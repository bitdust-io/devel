#!/usr/bin/python
# backup_db_keeper.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (backup_db_keeper.py) is part of BitDust Software.
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
.. module:: backup_db_keeper.

.. raw:: html

    <a href="http://bitdust.io/automats/backup_db_keeper/backup_db_keeper.png" target="_blank">
    <img src="http://bitdust.io/automats/backup_db_keeper/backup_db_keeper.png" style="max-width:100%;">
    </a>


Here is a state machine ``backup_db_keeper()``, it is aimed to synchronize
local index database with remote suppliers.

This allows to restore the index file (with all your backup IDs and files and folders names)
from your suppliers in case of data lost.

The purpose of backup_db_keeper() automat is to sync users's backup database to remote computers.
In case of loss of all local data - backup database will be restored from the suppliers.

The database includes the list of folders to be backed up, schedule for the backups,
and most importantly, a list of already created backups by its ID.

Thus if the user has made recovery of his account and restore the backup database -
he can recover his data from remote machines by backup ID.

Every time any local change is made to the database it become sunchronized with remote copy.

At first, backup_db_keeper() request a remote copy of the database,
then send a latest version to the suppliers.

The backup_monitor() should be restarted every hour or every time when your backups is changed.

EVENTS:
    * :red:`all-responded`
    * :red:`db-info-acked`
    * :red:`init`
    * :red:`restart`
    * :red:`timer-1hour`
    * :red:`timer-1sec`
    * :red:`timer-30sec`
"""

#------------------------------------------------------------------------------

import time

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import nameurl

from p2p import commands

from system import bpio

from userid import my_id
from contacts import contactsdb

from main import settings

from transport import gateway

from crypt import encrypted
from crypt import signed
from crypt import key

#------------------------------------------------------------------------------

_BackupDBKeeper = None

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _BackupDBKeeper
    if _BackupDBKeeper is None:
        _BackupDBKeeper = BackupDBKeeper('backup_db_keeper', 'AT_STARTUP', 4)
    if event is not None:
        _BackupDBKeeper.automat(event, arg)
    return _BackupDBKeeper


def Destroy():
    """
    Destroy backup_db_keeper() automat and remove its instance from memory.
    """
    global _BackupDBKeeper
    if _BackupDBKeeper is None:
        return
    _BackupDBKeeper.destroy()
    del _BackupDBKeeper
    _BackupDBKeeper = None


#------------------------------------------------------------------------------

class BackupDBKeeper(automat.Automat):
    """
    A class to provides logic for database synchronization process.
    """
    timers = {
        'timer-1hour': (3600, ['READY']),
        'timer-1sec': (1.0, ['RESTART']),
        'timer-30sec': (30.0, ['RESTART', 'REQUEST', 'SENDING']),
    }

    def init(self):
        """
        Set initial values.
        """
        self.requestedSuppliers = set()
        self.sentSuppliers = set()
        self.lastRestartTime = 0
        self.syncFlag = False

    def A(self, event, arg):
        from p2p import p2p_connector
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'restart':
                self.state = 'RESTART'
            elif event == 'init':
                self.state = 'READY'
        #---RESTART---
        elif self.state == 'RESTART':
            if event == 'timer-1sec' and self.isTimePassed(
                    arg) and p2p_connector.A().state is 'CONNECTED':
                self.state = 'REQUEST'
                self.doSuppliersRequestDBInfo(arg)
                self.doRememberTime(arg)
            elif event == 'timer-30sec':
                self.state = 'READY'
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'restart':
                self.state = 'RESTART'
            elif event == 'all-responded' or event == 'timer-30sec':
                self.state = 'SENDING'
                self.doSuppliersSendDBInfo(arg)
        #---SENDING---
        elif self.state == 'SENDING':
            if event == 'restart':
                self.state = 'RESTART'
            elif event == 'db-info-acked' and self.isAllSuppliersAcked(arg):
                self.state = 'READY'
                self.doSetSyncFlag(arg)
            elif event == 'timer-30sec':
                self.state = 'READY'
            elif event == 'db-info-acked' and not self.isAllSuppliersAcked(arg):
                self.doSetSyncFlag(arg)
        #---READY---
        elif self.state == 'READY':
            if event == 'timer-1hour' or event == 'restart':
                self.state = 'RESTART'

    def isAllSuppliersAcked(self, arg):
        return len(self.sentSuppliers) == 0

    def isTimePassed(self, arg):
        return time.time() - self.lastRestartTime > settings.BackupDBSynchronizeDelay()

    def doRememberTime(self, arg):
        self.lastRestartTime = time.time()

    def doSuppliersRequestDBInfo(self, arg):
        lg.out(4, 'backup_db_keeper.doSuppliersRequestDBInfo')
        packetID = settings.BackupIndexFileName()
        self.requestedSuppliers.clear()
        Payload = ''
        localID = my_id.getLocalID()
        for supplierId in contactsdb.suppliers():
            if not supplierId:
                continue
            newpacket = signed.Packet(
                commands.Retrieve(),
                localID,
                localID,
                packetID,
                Payload,
                supplierId)
            gateway.outbox(newpacket, callbacks={
                commands.Data(): self._supplier_response,
                commands.Fail(): self._supplier_response, })
            self.requestedSuppliers.add(supplierId)

    def doSuppliersSendDBInfo(self, arg):
        from p2p import contact_status
        lg.out(4, 'backup_db_keeper.doSuppliersSendDBInfo')
        packetID = settings.BackupIndexFileName()
        self.sentSuppliers.clear()
        src = bpio.ReadBinaryFile(settings.BackupIndexFilePath())
        localID = my_id.getLocalID()
        b = encrypted.Block(
            localID,
            packetID,
            0,
            key.NewSessionKey(),
            key.SessionKeyType(),
            True,
            src,
        )
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
                commands.Ack(): self._supplier_acked,
                commands.Fail(): self._supplier_acked, })
            self.sentSuppliers.add(supplierId)
            lg.out(
                4, '    %s sending to %s' %
                (pkt_out, nameurl.GetName(supplierId)))

    def doSetSyncFlag(self, arg):
        if not self.syncFlag:
            lg.out(
                4,
                'backup_db_keeper.doSetSyncFlag backup database is now SYNCHRONIZED !!!!!!!!!!!!!!!!!!!!!!')
        self.syncFlag = True

#    def doCountResponse(self, arg):
#        """
#        Action method.
#        """
#        newpacket = arg
#        lg.out(6, 'backup_db_keeper.doCountResponse %r from %s' % (newpacket, packet.OwnerID))
#        self.requestedSuppliers.discard(packet.OwnerID)
#        if packet.Command == commands.Fail():
#            sc = supplier_connector.by_idurl(packet.OwnerID)
#            if sc:
#                sc.automat('fail', newpacket)
#            else:
#                raise Exception('not found supplier connector')

    def _supplier_response(self, newpacket, pkt_out):
        from customer import supplier_connector
        if newpacket.Command == commands.Data():
            self.requestedSuppliers.discard(newpacket.RemoteID)
        elif newpacket.Command == commands.Fail():
            self.requestedSuppliers.discard(newpacket.OwnerID)
            sc = supplier_connector.by_idurl(newpacket.OwnerID)
            if sc:
                sc.automat('fail', newpacket)
            else:
                raise Exception('supplier connector was not found')
        else:
            raise Exception('wrong type of response')
        if len(self.requestedSuppliers) == 0:
            self.automat('all-responded')
        # lg.out(6, 'backup_db_keeper._supplier_response %s others: %r' % (packet, self.requestedSuppliers))

    def _supplier_acked(self, newpacket, info):
        from customer import supplier_connector
        self.sentSuppliers.discard(newpacket.OwnerID)
        self.automat('db-info-acked', newpacket.OwnerID)
        sc = supplier_connector.by_idurl(newpacket.OwnerID)
        if sc:
            sc.automat(newpacket.Command.lower(), newpacket)
        else:
            raise Exception('not found supplier connector')

    def IsSynchronized(self):
        return self.syncFlag
