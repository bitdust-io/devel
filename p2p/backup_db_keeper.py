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
    * :red:`db-info-acked`
    * :red:`incoming-db-info`
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
    
import lib.dhnio as dhnio
import lib.misc as misc
import lib.contacts as contacts
import lib.settings as settings
import lib.dhnpacket as dhnpacket
import lib.commands as commands
import lib.dhncrypto as dhncrypto
import lib.automats as automats
from lib.automat import Automat

import transport.callback as callback
import transport.gate as gate

import dhnblock
import p2p_connector
import contact_status
import supplier_connector

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

class BackupDBKeeper(Automat):
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
            elif ( event == 'incoming-db-info' and self.isAllSuppliersResponded(arg) ) or event == 'timer-30sec' :
                self.state = 'SENDING'
                self.doCountResponse(arg)
                self.doSuppliersSendDBInfo(arg)
            elif event == 'incoming-db-info' and not self.isAllSuppliersResponded(arg) :
                self.doCountResponse(arg)
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

    def isAllSuppliersResponded(self, arg):
        return len(self.requestedSuppliers) == 0
            
    def isAllSuppliersAcked(self, arg):
        return len(self.sentSuppliers) == 0

    def isTimePassed(self, arg):
        return time.time() - self.lastRestartTime > settings.BackupDBSynchronizeDelay()
    
    def doRememberTime(self, arg):
        self.lastRestartTime = time.time()        
    
    def doSuppliersRequestDBInfo(self, arg):
        # dhnio.Dprint(4, 'backup_db_keeper.doSuppliersRequestDBInfo')
        # packetID_ = settings.BackupInfoFileName()
        # packetID = settings.BackupInfoEncryptedFileName()
        packetID = settings.BackupIndexFileName()
        for supplierId in contacts.getSupplierIDs():
            if supplierId:
                callback.remove_interest(supplierId, packetID)
        self.requestedSuppliers.clear()
        Payload = ''
        localID = misc.getLocalID()
        for supplierId in contacts.getSupplierIDs():
            if not supplierId:
                continue
            newpacket = dhnpacket.dhnpacket(commands.Retrieve(), localID, localID, packetID, Payload, supplierId)
            gate.outbox(newpacket, False,) 
                        # ack_callback=self._supplier_response,
                        # fail_callback=self._supplier_response)
            # callback.register_interest(self._supplier_response, supplierId, packetID)
            self.requestedSuppliers.add(supplierId)

    def doSuppliersSendDBInfo(self, arg):
        # dhnio.Dprint(4, 'backup_db_keeper.doSuppliersSendDBInfo')
        # packetID = settings.BackupInfoEncryptedFileName()
        packetID = settings.BackupIndexFileName()
        # for supplierId in contacts.getSupplierIDs():
        #     if supplierId:
        #         callback.remove_interest(supplierId, packetID)
        self.sentSuppliers.clear()
        # src = dhnio.ReadBinaryFile(settings.BackupInfoFileFullPath())
        src = dhnio.ReadBinaryFile(settings.BackupIndexFilePath())
        localID = misc.getLocalID()
        block = dhnblock.dhnblock(localID, packetID, 0, dhncrypto.NewSessionKey(), dhncrypto.SessionKeyType(), True, src)
        Payload = block.Serialize() 
        for supplierId in contacts.getSupplierIDs():
            if not supplierId:
                continue
            if not contact_status.isOnline(supplierId):
                continue
            newpacket = dhnpacket.dhnpacket(commands.Data(), localID, localID, packetID, Payload, supplierId)
            gate.outbox(newpacket, True,
                        ack_callback=self._supplier_acked,
                        fail_callback=self._supplier_acked)
            # callback.register_interest(self._supplier_acked, supplierId, packetID)
            self.sentSuppliers.add(supplierId)
            # dhnio.Dprint(6, 'backup_db_keeper.doSuppliersSendDBInfo to %s' % supplierId)

    def doSetSyncFlag(self, arg):
        if not self.syncFlag:
            dhnio.Dprint(4, 'backup_db_keeper.doSetSyncFlag backup database is now SYNCHRONIZED !!!!!!!!!!!!!!!!!!!!!!')
        self.syncFlag = True

    def doCountResponse(self, arg):
        """
        Action method.
        """
        packet = arg
        dhnio.Dprint(6, 'backup_db_keeper.doCountResponse %r from %s' % (packet, packet.OwnerID))
        self.requestedSuppliers.discard(packet.OwnerID)
        sc = supplier_connector.by_idurl(packet.OwnerID)
        if sc:
            # if packet.Command == commands.Fail():
            #     sc.automat('fail', packet)
            elif packet.Command == commands.Data():
                sc.automat('data', packet)
            elif packet.Command == commands.Retrieve():
                pass
            elif packet.Command == commands.Ack():
                pass
            else:
                raise
        else:
            raise

#    def _supplier_response(self, packet, info):
#        dhnio.Dprint(6, 'backup_db_keeper._supplier_response %s' % packet)
#        self.requestedSuppliers.discard(packet.OwnerID)
#        sc = supplier_connector.by_idurl(packet.OwnerID)
#        if sc:
#            if packet.Command == commands.Fail():
#                sc.automat('fail', packet)
#            elif packet.Command == commands.Data():
#                sc.automat('data', packet)
#            elif packet.Command == commands.Retrieve():
#                pass
#            elif packet.Command == commands.Ack():
#                pass
#            else:
#                raise
#        else:
#            raise

    def _supplier_acked(self, packet, info):
        self.sentSuppliers.discard(packet.OwnerID)
        self.automat('db-info-acked', packet.OwnerID)
        sc = supplier_connector.by_idurl(packet.OwnerID)
        if sc:
            sc.automat('ack', packet)
        else:
            raise
    
    def IsSynchronized(self):
        return self.syncFlag
    
    

