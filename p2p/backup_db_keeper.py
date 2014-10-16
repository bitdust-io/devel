#!/usr/bin/python
#backup_db_keeper.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: backup_db_keeper

.. raw:: html

    <a href="http://bitpie.net/automats/backup_db_keeper/backup_db_keeper.png" target="_blank">
    <img src="http://bitpie.net/automats/backup_db_keeper/backup_db_keeper.png" style="max-width:100%;">
    </a>


Here is a state machine ``backup_db_keeper()``, it is aimed to synchronize 
local index database with remote suppliers.

This allows to restore the index file (with all your backup IDs and files and folders names)
from your suppliers in case of data lost.

The purpose of backup_db_keeper() automat is to store users's backup database on remote computers. 
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

import os
import sys
import time

#------------------------------------------------------------------------------ 

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in backup_rebuilder.py')
    
from logs import lg

from lib import bpio
from lib import misc
from lib import contacts
from lib import settings
from lib import commands
from lib import automat

from transport import gate

from crypt import encrypted
from crypt import signed
from crypt import key

import p2p_connector
import contact_status
import supplier_connector

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
    
#------------------------------------------------------------------------------ 

class BackupDBKeeper(automat.Automat):
    """
    A class to provides logic for database synchronization process.
    """
    timers = {
        'timer-1hour': (3600, ['READY']),
        'timer-1sec': (1.0, ['RESTART']),
        'timer-30sec': (30.0, ['RESTART','REQUEST','SENDING']),
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
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'restart' :
                self.state = 'RESTART'
            elif event == 'init' :
                self.state = 'READY'
        #---RESTART---
        elif self.state == 'RESTART':
            if event == 'timer-1sec' and self.isTimePassed(arg) and p2p_connector.A().state is 'CONNECTED' :
                self.state = 'REQUEST'
                self.doSuppliersRequestDBInfo(arg)
                self.doRememberTime(arg)
            elif event == 'timer-30sec' :
                self.state = 'READY'
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'restart' :
                self.state = 'RESTART'
            elif event == 'all-responded' or event == 'timer-30sec' :
                self.state = 'SENDING'
                self.doSuppliersSendDBInfo(arg)
        #---SENDING---
        elif self.state == 'SENDING':
            if event == 'restart' :
                self.state = 'RESTART'
            elif event == 'db-info-acked' and self.isAllSuppliersAcked(arg) :
                self.state = 'READY'
                self.doSetSyncFlag(arg)
            elif event == 'timer-30sec' :
                self.state = 'READY'
            elif event == 'db-info-acked' and not self.isAllSuppliersAcked(arg) :
                self.doSetSyncFlag(arg)
        #---READY---
        elif self.state == 'READY':
            if event == 'timer-1hour' or event == 'restart' :
                self.state = 'RESTART'

    def isAllSuppliersAcked(self, arg):
        return len(self.sentSuppliers) == 0

    def isTimePassed(self, arg):
        return time.time() - self.lastRestartTime > settings.BackupDBSynchronizeDelay()
    
    def doRememberTime(self, arg):
        self.lastRestartTime = time.time()        
    
    def doSuppliersRequestDBInfo(self, arg):
        # lg.out(4, 'backup_db_keeper.doSuppliersRequestDBInfo')
        # packetID_ = settings.BackupInfoFileName()
        # packetID = settings.BackupInfoEncryptedFileName()
        packetID = settings.BackupIndexFileName()
        # for supplierId in contacts.getSupplierIDs():
        #     if supplierId:
        #         callback.remove_interest(supplierId, packetID)
        self.requestedSuppliers.clear()
        Payload = ''
        localID = misc.getLocalID()
        for supplierId in contacts.getSupplierIDs():
            if not supplierId:
                continue
            newpacket = signed.Packet(commands.Retrieve(), localID, localID, packetID, Payload, supplierId)
            gate.outbox(newpacket, callbacks={
                commands.Data(): self._supplier_response,
                commands.Fail(): self._supplier_response,}) 
                        # ack_callback=self._supplier_response,
                        # fail_callback=self._supplier_response)
            # callback.register_interest(self._supplier_response, supplierId, packetID)
            self.requestedSuppliers.add(supplierId)

    def doSuppliersSendDBInfo(self, arg):
        # lg.out(4, 'backup_db_keeper.doSuppliersSendDBInfo')
        # packetID = settings.BackupInfoEncryptedFileName()
        packetID = settings.BackupIndexFileName()
        # for supplierId in contacts.getSupplierIDs():
        #     if supplierId:
        #         callback.remove_interest(supplierId, packetID)
        self.sentSuppliers.clear()
        # src = bpio.ReadBinaryFile(settings.BackupInfoFileFullPath())
        src = bpio.ReadBinaryFile(settings.BackupIndexFilePath())
        localID = misc.getLocalID()
        b = encrypted.Block(localID, packetID, 0, key.NewSessionKey(), key.SessionKeyType(), True, src)
        Payload = b.Serialize() 
        for supplierId in contacts.getSupplierIDs():
            if not supplierId:
                continue
            if not contact_status.isOnline(supplierId):
                continue
            newpacket = signed.Packet(commands.Data(), localID, localID, packetID, Payload, supplierId)
            gate.outbox(newpacket, callbacks={
                commands.Ack(): self._supplier_acked,
                commands.Fail(): self._supplier_acked})
            # callback.register_interest(self._supplier_acked, supplierId, packetID)
            self.sentSuppliers.add(supplierId)
            # lg.out(6, 'backup_db_keeper.doSuppliersSendDBInfo to %s' % supplierId)

    def doSetSyncFlag(self, arg):
        if not self.syncFlag:
            lg.out(4, 'backup_db_keeper.doSetSyncFlag backup database is now SYNCHRONIZED !!!!!!!!!!!!!!!!!!!!!!')
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
        self.sentSuppliers.discard(newpacket.OwnerID)
        self.automat('db-info-acked', newpacket.OwnerID)
        sc = supplier_connector.by_idurl(newpacket.OwnerID)
        if sc:
            sc.automat(newpacket.Command.lower(), newpacket)
        else:
            raise Exception('not found supplier connector')
    
    def IsSynchronized(self):
        return self.syncFlag
    
    

