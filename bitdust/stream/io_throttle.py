#!/usr/bin/python
# io_throttle.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (io_throttle.py) is part of BitDust Software.
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
.. module:: io_throttle.

When reconstructing a backup we don't want to take over everything
and make BitDust unresponsive by requesting 1000's of files at once
and make it so no other packets can go out.

This just tries to limit how much we are sending out or receiving at any time
so that we still have control.

Before requesting another file or sending another one out
I check to see how much stuff I have waiting.

Keep track of every supplier, store packets send/request in many queues.

TODO:
We probably want to be able to send not only to suppliers but to any contacts.
In future we can use that to do "overlay" communications to hide users.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

import os
import sys
import time

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in io_throttle.py')

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import misc
from bitdust.lib import nameurl
from bitdust.lib import packetid

from bitdust.main import settings
from bitdust.main import config

from bitdust.userid import my_id
from bitdust.userid import global_id
from bitdust.userid import id_url

from bitdust.p2p import commands
from bitdust.p2p import online_status

from bitdust.crypt import signed

from bitdust.transport import callback

#------------------------------------------------------------------------------

_IOThrottle = None
_PacketReportCallbackFunc = None

#------------------------------------------------------------------------------


def throttle():
    """
    Access method to the IO interface object.
    """
    global _IOThrottle
    if _IOThrottle is None:
        _IOThrottle = IOThrottle()
    return _IOThrottle


def init():
    """
    Init ``throttle()`` object and link with transports.
    This is the mechanism for sending and requesting files pieces.
    """
    if _Debug:
        lg.out(_DebugLevel, 'io_throttle.init')
    throttle()
    callback.add_queue_item_status_callback(OutboxStatus)
    callback.add_finish_file_sending_callback(FileSendingFinished)


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'io_throttle.shutdown')
    callback.remove_finish_file_sending_callback(FileSendingFinished)
    callback.remove_queue_item_status_callback(OutboxStatus)
    throttle().DeleteBackupRequests('')
    throttle().DeleteBackupSendings('')
    throttle().DeleteSuppliers(list(throttle().supplierQueues.keys()))


#------------------------------------------------------------------------------


def SetPacketReportCallbackFunc(func):
    """
    You can pass a callback to catch a moment when some packet is
    added/removed.
    """
    global _PacketReportCallbackFunc
    _PacketReportCallbackFunc = func


def PacketReport(sendORrequest, supplier_idurl, packetID, result):
    """
    Called from other methods here to notify about packets events.
    """
    if _Debug:
        lg.out(_DebugLevel, 'io_throttle.PacketReport %s:%s %s to/from %s' % (sendORrequest, result, packetID, supplier_idurl))
    global _PacketReportCallbackFunc
    if _PacketReportCallbackFunc is not None:
        _PacketReportCallbackFunc(sendORrequest, supplier_idurl, packetID, result)


#------------------------------------------------------------------------------


def QueueSendFile(fileName, packetID, remoteID, ownerID, callOnAck=None, callOnFail=None):
    """
    Most used method - add an outgoing file to send to given remote peer.
    """
    return throttle().QueueSendFile(fileName, packetID, remoteID, ownerID, callOnAck, callOnFail)


def QueueRequestFile(callOnReceived, creatorID, packetID, ownerID, remoteID):
    """
    Place a request to download a single data packet from given remote supplier
    Remote user will verify our identity and decide to send the Data or not.
    Two scenarios possible when executing a `callOnReceived` callback:

        callOnReceived(newpacket, result)  or  callOnReceived(packetID, result)
    """
    return throttle().QueueRequestFile(callOnReceived, creatorID, packetID, ownerID, remoteID)


def DeleteBackupSendings(backupName):
    """
    Checks all send queues and search for packets with ``backupName`` in the
    packetID field.

    For example, this is used to remove old transfers if rebuilding
    process is restarted.
    """
    return throttle().DeleteBackupSendings(backupName)


def DeleteBackupRequests(backupName):
    """
    Checks all request queues and search for packets with ``backupName`` in the
    packetID field.

    For example, this is used to remove old requests if the restore
    process is aborted.
    """
    return throttle().DeleteBackupRequests(backupName)


def DeleteSuppliers(suppliers_IDURLs):
    """
    Erase the whole queue with this peer and remove him from throttle()
    completely.
    """
    return throttle().DeleteSuppliers(suppliers_IDURLs)


def DeleteAllSuppliers():
    return throttle().DeleteSuppliers(list(throttle().supplierQueues.keys()))


def OutboxStatus(pkt_out, status, error):
    return throttle().OutboxStatus(pkt_out, status, error)


def FileSendingFinished(pkt_out, item, status, size, error_message):
    return throttle().FileSendingFinished(pkt_out, item, status, size, error_message)


def IsSendingQueueEmpty():
    return throttle().IsSendingQueueEmpty()


def HasPacketInSendQueue(supplierIDURL, packetID):
    return throttle().HasPacketInSendQueue(supplierIDURL, packetID)


def HasPacketInRequestQueue(supplierIDURL, packetID):
    return throttle().HasPacketInRequestQueue(supplierIDURL, packetID)


def HasBackupIDInSendQueue(supplierIDURL, backupID):
    return throttle().HasBackupIDInSendQueue(supplierIDURL, backupID)


def HasBackupIDInRequestQueue(supplierIDURL, backupID):
    return throttle().HasBackupIDInRequestQueue(supplierIDURL, backupID)


def IsBackupSending(backupID):
    return throttle().IsBackupSending(backupID)


def OkToSend(supplierIDURL):
    return throttle().OkToSend(supplierIDURL)


def OkToRequest(supplierIDURL):
    return throttle().OkToRequest(supplierIDURL)


def GetSendQueueLength(supplierIDURL):
    return throttle().GetSendQueueLength(supplierIDURL)


def GetRequestQueueLength(supplierIDURL):
    return throttle().GetRequestQueueLength(supplierIDURL)


#------------------------------------------------------------------------------


class SupplierQueue:

    def __init__(self, supplierIdentity, creatorID, customerIDURL=None):
        self.customerIDURL = customerIDURL
        if self.customerIDURL is None:
            self.customerIDURL = my_id.getIDURL()
        self.creatorID = creatorID
        self.remoteID = supplierIdentity
        self.remoteName = nameurl.GetName(self.remoteID)

        # all sends we'll hold on to, only several will be active,
        # but will hold onto the next ones to be sent
        # active files
        self.fileSendMaxLength = config.conf().getInt('services/data-motion/supplier-sending-queue-size', 8)
        # an array of packetId, preserving first in first out,
        # of which the first maxLength are the "active" sends
        self.fileSendQueue = []
        # dictionary of FileUp's using packetId as index,
        # hold onto stuff sent and acked for some period as a history?
        self.fileSendDict = {}

        # all requests we'll hold on to,
        # only several will be active, but will hold onto the next ones to be sent
        # active requests
        self.fileRequestMaxLength = config.conf().getInt('services/data-motion/supplier-request-queue-size', 8)
        # an array of PacketIDs, preserving first in first out
        self.fileRequestQueue = []
        # FileDown's, indexed by PacketIDs
        self.fileRequestDict = {}

        self.shutdown = False

        self.ackedCount = 0
        self.failedCount = 0

        self.uploadingTimeoutCount = 0
        self.downloadingTimeoutCount = 0

        self._runSend = False
        self.sendTask = None
        self.sendTaskDelay = 0.1
        self.requestTask = None
        self.requestTaskDelay = 0.1

    #------------------------------------------------------------------------------

    def SupplierSendFile(self, fileName, packetID, ownerID, callOnAck=None, callOnFail=None):
        if self.shutdown:
            if _Debug:
                lg.out(_DebugLevel, 'io_throttle.SupplierSendFile finishing to %s, shutdown is True' % self.remoteName)
            if callOnFail is not None:
                reactor.callLater(0, callOnFail, self.remoteID, packetID, 'shutdown')  # @UndefinedVariable
            return False
        if online_status.isOffline(self.remoteID):
            if _Debug:
                lg.out(_DebugLevel, 'io_throttle.SupplierSendFile %s is offline, so packet %s is failed' % (self.remoteName, packetID))
            if callOnFail is not None:
                reactor.callLater(0, callOnFail, self.remoteID, packetID, 'offline')  # @UndefinedVariable
            return False
        if packetID in self.fileSendQueue:
            lg.warn('packet %s already in the queue for %s' % (packetID, self.remoteName))
            if callOnFail is not None:
                reactor.callLater(0, callOnFail, self.remoteID, packetID, 'in queue')  # @UndefinedVariable
            return False
        from bitdust.stream import file_up
        f_up = file_up.FileUp(
            self,
            fileName,
            packetID,
            self.remoteID,
            ownerID,
            callOnAck,
            callOnFail,
        )
        f_up.event('init')
        if _Debug:
            lg.out(_DebugLevel, 'io_throttle.SupplierSendFile %s to %s, %d queued items' % (packetID, self.remoteName, len(self.fileSendQueue)))
        self.DoSend()
        return True

    def StopAllSindings(self):
        for packetID in list(self.fileSendDict.keys()):
            f_up = self.fileSendDict.get(packetID)
            if f_up:
                if _Debug:
                    lg.args(_DebugLevel, packetID=packetID, obj=f_up, event='stop')
                f_up.event('stop')

    def DeleteBackupSendings(self, backupName):
        if self.shutdown:
            # if we're closing down this queue, don't do anything, but just stop all uploads
            self.StopAllSindings()
            return
        if _Debug:
            lg.args(_DebugLevel, backupName=backupName)
        packetsToRemove = set()
        for packetID in self.fileSendQueue:
            if (backupName and packetID.count(backupName)) or not backupName:
                packetsToRemove.add(packetID)
                if _Debug:
                    lg.out(_DebugLevel, 'io_throttle.DeleteBackupRequests %s from downloading queue' % packetID)
        for packetID in packetsToRemove:
            if packetID in self.fileSendDict:
                f_up = self.fileSendDict[packetID]
                f_up.event('stop')
                if _Debug:
                    lg.out(_DebugLevel, 'io_throttle.DeleteBackupRequests stopped %s in %s uploading queue, %d more items' % (packetID, self.remoteID, len(self.fileSendQueue)))
        if len(self.fileSendQueue) > 0:
            reactor.callLater(0, self.DoSend)  # @UndefinedVariable

    def OnFileSendAckReceived(self, newpacket, info):
        if self.shutdown:
            if _Debug:
                lg.out(_DebugLevel, 'io_throttle.OnFileSendAckReceived finishing to %s, shutdown is True' % self.remoteName)
            return
        if not newpacket and not info:
            lg.warn('packet timed out during responding')
            return
        if _Debug:
            lg.out(_DebugLevel, 'io_throttle.OnFileSendAckReceived with %r' % newpacket)
        self.ackedCount += 1
        packetID = global_id.CanonicalID(newpacket.PacketID)
        if packetID not in self.fileSendQueue:
            lg.warn('packet %s not in sending queue for %s' % (newpacket.PacketID, self.remoteName))
            return
        if packetID not in list(self.fileSendDict.keys()):
            lg.warn('packet %s not in sending dict for %s' % (newpacket.PacketID, self.remoteName))
            return
        f_up = self.fileSendDict[packetID]
        if newpacket.Command == commands.Ack():
            f_up.event('ack-received', newpacket)
        elif newpacket.Command == commands.Fail():
            f_up.event('fail-received', newpacket)
        else:
            raise Exception('wrong command received in response: %r' % newpacket)
        from bitdust.customer import supplier_connector
        sc = supplier_connector.by_idurl(newpacket.OwnerID)
        if sc:
            if newpacket.Command == commands.Ack():
                sc.automat('ack', newpacket)
            elif newpacket.Command == commands.Fail():
                sc.automat('fail', newpacket)
            else:
                raise Exception('incorrect packet type received: %r' % newpacket)
        else:
            if _Debug:
                lg.dbg(_DebugLevel, 'supplier connector for %r was not found' % newpacket.OwnerID)
        if _Debug:
            lg.out(_DebugLevel, 'io_throttle.OnFileSendAckReceived %s from %s, queue=%d' % (str(newpacket), self.remoteName, len(self.fileSendQueue)))

    def RunSend(self):
        if self._runSend:
            return -1
        self._runSend = True
        if _Debug:
            lg.out(_DebugLevel*2, 'io_throttle.RunSend  fileSendQueue=%d' % len(self.fileSendQueue))
        packetsToBeFailed = {}
        packetsToRemove = set()
        packetsSent = 0
        # let's check only beginning of the queue and try to process it.
        # once we finish and remove some items from the queue we can take more items
        for i in range(0, min(self.fileSendMaxLength, len(self.fileSendQueue))):
            try:
                packetID = self.fileSendQueue[i]
            except:
                lg.warn('item at position %d not exist in send queue' % i)
                continue

            f_up = self.fileSendDict[packetID]

            if f_up.state != 'IN_QUEUE':
                # we are sending that file at the moment
                packetsSent += 1
                # and we got ack
                if f_up.ackTime is None:
                    # if we did not get an ack yet we do not want to wait to long
                    if time.time() - f_up.sendTime > f_up.sendTimeout:
                        # so this packet is failed because no response for too long
                        packetsToBeFailed[packetID] = 'timeout'
                        lg.warn('uploading %r failed because of timeout %d src' % (packetID, f_up.sendTimeout))
                # this packet already in progress - check next one
                continue

            # the data file to send no longer exists - it is failed situation
            if not os.path.exists(f_up.fileName):
                lg.warn('file %s not exist' % (f_up.fileName))
                packetsToBeFailed[packetID] = 'not exist'
                continue

            # item is in the queue, but not started yet
            f_up.event('start')

        # process failed packets
        for packetID, why in packetsToBeFailed.items():
            f_up = self.fileSendDict[packetID]
            if why == 'timeout':
                f_up.event('timeout')
            elif why == 'not exist':
                f_up.event('file-not-exist')
            else:
                raise Exception('unknown result %r for %r' % (why, packetID))
        # remember results
        result = max(len(packetsToRemove), packetsSent)
        # erase temp lists
        del packetsToBeFailed
        del packetsToRemove
        self._runSend = False
        return result

    def SendingTask(self):
        if self.shutdown:
            self.StopAllSindings()
            return
        try:
            sends = self.RunSend()
        except:
            lg.exc()
            sends = -1
        if sends == -1:
            if _Debug:
                lg.dbg(_DebugLevel, 'sending task complete %r' % self)
            return
        self.sendTaskDelay = misc.LoopAttenuation(self.sendTaskDelay, sends > 0, settings.MinimumSendingDelay(), settings.MaximumSendingDelay())
        # attenuation
        self.sendTask = reactor.callLater(self.sendTaskDelay, self.SendingTask)  # @UndefinedVariable

    def DoSend(self):
        if self.sendTask is None:
            self.SendingTask()
            return
        if self._runSend:
            return
        if self.sendTaskDelay > 1.0:
            self.sendTask.cancel()
            self.sendTask = None
            reactor.callLater(0, self.SendingTask)  # @UndefinedVariable

    #------------------------------------------------------------------------------

    def SupplierRequestFile(self, callOnReceived, creatorID, packetID, ownerID):
        if self.shutdown:
            if _Debug:
                lg.out(_DebugLevel, 'io_throttle.SupplierRequestFile finishing to %s, shutdown is True' % self.remoteName)
            if callOnReceived:
                reactor.callLater(0, callOnReceived, packetID, 'shutdown')  # @UndefinedVariable
            self.StopAllRequests()
            return False
        if packetID in self.fileRequestQueue:
            lg.warn('packet %s already in the queue for %s' % (packetID, self.remoteName))
            if callOnReceived:
                reactor.callLater(0, callOnReceived, packetID, 'in queue')  # @UndefinedVariable
            return False
        from bitdust.stream import file_down
        f_down = file_down.FileDown(self, callOnReceived, creatorID, packetID, ownerID, self.remoteID)
        f_down.event('init')
        if _Debug:
            lg.out(_DebugLevel, 'io_throttle.SupplierRequestFile %s from %s, %d queued items' % (packetID, self.remoteName, len(self.fileRequestQueue)))
        self.DoRequest()
        return True

    def StopAllRequests(self):
        for packetID in list(self.fileRequestDict.keys()):
            f_down = self.fileRequestDict.get(packetID)
            if f_down:
                if _Debug:
                    lg.args(_DebugLevel, packetID=packetID, obj=f_down, event='stop')
                f_down.event('stop')

    def DeleteBackupRequests(self, backupName):
        if self.shutdown:
            # if we're closing down this queue, don't do anything, but just stop all requests
            lg.warn('supplier queue is shutting down')
            self.StopAllRequests()
            return
        if _Debug:
            lg.out(_DebugLevel, 'io_throttle.DeleteBackupRequests  will cancel all requests for %s' % backupName)
        packetsToRemove = set()
        for packetID in self.fileRequestQueue:
            if (backupName and packetID.count(backupName)) or not backupName:
                packetsToRemove.add(packetID)
                if _Debug:
                    lg.out(_DebugLevel, 'io_throttle.DeleteBackupRequests %s from downloading queue' % packetID)
        for packetID in packetsToRemove:
            f_down = self.fileRequestDict.get(packetID)
            if f_down:
                f_down.event('stop')
                if _Debug:
                    lg.out(_DebugLevel, 'io_throttle.DeleteBackupRequests stopped %r in %s downloading queue, %d more items' % (packetID, self.remoteID, len(self.fileRequestQueue)))
            else:
                lg.warn('can not find %r in request queue' % packetID)
        if len(self.fileRequestQueue) > 0:
            reactor.callLater(0, self.DoRequest)  # @UndefinedVariable

    def OnDataReceived(self, newpacket, result):
        # we requested some data from a supplier, and just received it
        if self.shutdown:
            lg.warn('skip, supplier queue is shutting down')
            self.StopAllRequests()
            return
        if _Debug:
            lg.args(_DebugLevel, newpacket=newpacket, result=result, queue=len(self.fileRequestQueue), remoteName=self.remoteName)
        packetID = global_id.CanonicalID(newpacket.PacketID)
        if (packetID not in self.fileRequestQueue) or (packetID not in self.fileRequestDict):
            latest_idurl = global_id.NormalizeGlobalID(packetID, as_field=True)['idurl'].latest
            another_packetID = global_id.SubstitutePacketID(packetID, idurl=latest_idurl)
            if (another_packetID in self.fileRequestQueue) and (another_packetID in self.fileRequestDict):
                packetID = another_packetID
                lg.warn('found incoming %r with outdated packet id, corrected: %r' % (newpacket, another_packetID))
        if (packetID not in self.fileRequestQueue) or (packetID not in self.fileRequestDict):
            lg.err('unexpected %r received which is not in the downloading queue' % newpacket)
        else:
            f_down = self.fileRequestDict[packetID]
            if newpacket.Command == commands.Data():
                wrapped_packet = signed.Unserialize(newpacket.Payload)
                if not wrapped_packet or not wrapped_packet.Valid():
                    lg.err('incoming Data() packet is not valid')
                    f_down.event('fail-received', newpacket)
                    return
                f_down.event('valid-data-received', wrapped_packet)
            elif newpacket.Command == commands.Fail():
                f_down.event('fail-received', newpacket)
            else:
                lg.err('incorrect response command: %r' % newpacket)

    def RunRequest(self):
        packetsToRemove = {}
        for i in range(0, min(self.fileRequestMaxLength, len(self.fileRequestQueue))):
            packetID = self.fileRequestQueue[i]
            # must never happen, but just in case
            if packetID not in self.fileRequestDict:
                packetsToRemove[packetID] = 'broken'
                lg.err('file %r not found in downloading queue for %r' % (packetID, self.remoteID))
                continue
            f_down = self.fileRequestDict[packetID]
            if f_down.state == 'IN_QUEUE':
                customer, pathID = packetid.SplitPacketID(packetID)
                if os.path.exists(os.path.join(settings.getLocalBackupsDir(), customer, pathID)):
                    # we have the data file, no need to request it
                    packetsToRemove[packetID] = 'exist'
                else:
                    f_down.event('start')
        # remember requests results
        result = len(packetsToRemove)
        # remove finished requests
        for packetID, why in packetsToRemove.items():
            if _Debug:
                lg.out(_DebugLevel, 'io_throttle.RunRequest %r to be removed from [%s] downloading queue because %r, %d more items' % (packetID, self.remoteID, why, len(self.fileRequestQueue)))
            if packetID in self.fileRequestQueue:
                f_down = self.fileRequestDict[packetID]
                if why == 'exist':
                    f_down.event('file-already-exists')
                else:
                    lg.warn('unexpected result "%r" for %r in downloading queue for %s' % (why, packetID, self.remoteID))
                    f_down.event('stop')
            else:
                lg.warn('packet %r not found in request queue for [%s]' % (packetID, self.remoteID))
        del packetsToRemove
        if result:
            self.DoRequest()
        return result

    def RequestTask(self):
        if self.shutdown:
            self.StopAllRequests()
            return
        requests = self.RunRequest()
        self.requestTaskDelay = misc.LoopAttenuation(self.requestTaskDelay, requests > 0, settings.MinimumReceivingDelay(), settings.MaximumReceivingDelay())
        # attenuation
        self.requestTask = reactor.callLater(self.requestTaskDelay, self.RequestTask)  # @UndefinedVariable

    def DoRequest(self):
        if self.requestTask is None:
            self.RequestTask()
        else:
            if self.requestTaskDelay > 1.0:
                self.requestTask.cancel()
                self.requestTask = None
                self.RequestTask()

    #------------------------------------------------------------------------------

    def OnFileSendingFinished(self, pkt_out, item, status, size, error_message):
        if self.shutdown:
            lg.warn('skip, supplier queue is shutting down')
            return
        if not pkt_out.outpacket:
            lg.warn('skip, outpacket is already None')
            return
        packetID = global_id.CanonicalID(pkt_out.outpacket.PacketID)
        if status == 'finished':
            if pkt_out.outpacket.Command == commands.Retrieve():
                if packetID in self.fileRequestQueue:
                    f_down = self.fileRequestDict[packetID]
                    if _Debug:
                        lg.args(_DebugLevel, obj=f_down, status=status, packetID=packetID, event='retrieve-sent')
                    f_down.event('retrieve-sent', pkt_out.outpacket)
            elif pkt_out.outpacket.Command == commands.Data():
                if packetID in self.fileSendQueue:
                    f_up = self.fileSendDict[packetID]
                    if _Debug:
                        lg.args(_DebugLevel, obj=f_up, status=status, packetID=packetID, event='data-sent')
                    f_up.event('data-sent', pkt_out.outpacket)
        else:
            if pkt_out.outpacket.Command == commands.Retrieve():
                if packetID in self.fileRequestQueue:
                    if _Debug:
                        lg.dbg(_DebugLevel, 'packet %r is %r during downloading from %s' % (packetID, status, self.remoteID))
                    f_down = self.fileRequestDict[packetID]
                    f_down.event('request-failed')
            elif pkt_out.outpacket.Command == commands.Data():
                if packetID in self.fileSendQueue:
                    if _Debug:
                        lg.dbg(_DebugLevel, 'packet %r is %r during uploading to %s' % (packetID, status, self.remoteID))
                    f_up = self.fileSendDict[packetID]
                    f_up.event('sending-failed')

    def OutboxStatus(self, pkt_out, status, error):
        if self.shutdown:
            lg.warn('supplier queue is shutting down')
            return False
        packetID = global_id.CanonicalID(pkt_out.outpacket.PacketID)
        if status == 'finished':
            if pkt_out.outpacket.Command == commands.Data():
                if packetID in self.fileSendQueue:
                    f_up = self.fileSendDict[packetID]
                    if _Debug:
                        lg.args(_DebugLevel, obj=f_up, status=status, packetID=packetID, event='data-sent')
                    if error == 'unanswered':
                        f_up.event('timeout', pkt_out.outpacket)
                    else:
                        f_up.event('data-sent', pkt_out.outpacket)
                    return False
        else:
            if pkt_out.outpacket.Command == commands.Data():
                if packetID in self.fileSendQueue:
                    lg.warn('packet %r is %r during uploading to %s' % (packetID, status, self.remoteID))
                    f_up = self.fileSendDict[packetID]
                    f_up.event('sending-failed')
                    return False
        return False

    #------------------------------------------------------------------------------

    def RemoveSupplierWork(self):
        if _Debug:
            lg.out(_DebugLevel, 'io_throttle.RemoveSupplierWork for %r' % self.remoteID)
        self.DeleteBackupSendings(backupName=None)
        self.DeleteBackupRequests(backupName=None)

    #------------------------------------------------------------------------------

    def ListSendItems(self):
        return self.fileSendQueue

    def GetSendItem(self, packetID):
        return self.fileSendDict.get(packetID)

    def ListRequestItems(self):
        return self.fileRequestQueue

    def GetRequestItem(self, packetID):
        return self.fileRequestDict.get(packetID)

    def HasSendingFiles(self):
        return len(self.fileSendQueue) > 0

    def HasRequestedFiles(self):
        return len(self.fileRequestQueue) > 0

    def OkToSend(self):
        return len(self.fileSendQueue) < self.fileSendMaxLength

    def OkToRequest(self):
        return len(self.fileRequestQueue) < self.fileRequestMaxLength

    def GetSendQueueLength(self):
        return len(self.fileSendQueue)

    def GetRequestQueueLength(self):
        return len(self.fileRequestQueue)


#------------------------------------------------------------------------------


class IOThrottle:

    """
    All of the backup rebuilds will run their data requests through this
    So it gets throttled, also to reduce duplicate requests.
    """

    def __init__(self):
        self.creatorID = my_id.getIDURL()
        self.supplierQueues = {}
        self.paintFunc = None

    def GetSupplierQueue(self, supplierIDURL):
        supplierIDURL = id_url.field(supplierIDURL)
        return self.supplierQueues.get(supplierIDURL)

    def ListSupplierQueues(self):
        return list(self.supplierQueues.keys())

    def SetSupplierQueueCallbackFunc(self, func):
        self.paintFunc = func

    def DeleteSuppliers(self, suppliers_IDURLs):
        for supplierIDURL in id_url.to_list(suppliers_IDURLs):
            if supplierIDURL:
                if supplierIDURL in self.supplierQueues:
                    self.supplierQueues[supplierIDURL].RemoveSupplierWork()
                    del self.supplierQueues[supplierIDURL]

    def DeleteBackupSendings(self, backupName):
        # lg.out(10, 'io_throttle.DeleteBackupSendings for %s' % backupName)
        for supplierQueue in self.supplierQueues.values():
            supplierQueue.DeleteBackupSendings(backupName)

    def DeleteBackupRequests(self, backupName):
        # lg.out(10, 'io_throttle.DeleteBackupRequests for %s' % backupName)
        for supplierQueue in self.supplierQueues.values():
            supplierQueue.DeleteBackupRequests(backupName)

    def QueueSendFile(self, fileName, packetID, remoteID, ownerID, callOnAck=None, callOnFail=None):
        #out(10, "io_throttle.QueueSendFile %s to %s" % (packetID, nameurl.GetName(remoteID)))
        remoteID = id_url.field(remoteID)
        ownerID = id_url.field(ownerID)
        if not os.path.exists(fileName):
            lg.err('%s not exist' % fileName)
            if callOnFail is not None:
                reactor.callLater(.01, callOnFail, remoteID, packetID, 'not exist')  # @UndefinedVariable
            return False
        if remoteID not in list(self.supplierQueues.keys()):
            self.supplierQueues[remoteID] = SupplierQueue(remoteID, self.creatorID)
            lg.info('made a new sending queue for %s' % nameurl.GetName(remoteID))
        return self.supplierQueues[remoteID].SupplierSendFile(
            fileName,
            packetID,
            ownerID,
            callOnAck,
            callOnFail,
        )

    # return result in the callback: callOnReceived(packet or packetID, state)
    # state is: received, exist, in queue, shutdown
    def QueueRequestFile(self, callOnReceived, creatorID, packetID, ownerID, remoteID):
        # make sure that we don't actually already have the file
        remoteID = id_url.field(remoteID)
        ownerID = id_url.field(ownerID)
        creatorID = id_url.field(creatorID)
        if packetID != settings.BackupIndexFileName() and not packetid.IsIndexFileName(packetID):
            customer, pathID = packetid.SplitPacketID(packetID)
            filename = os.path.join(settings.getLocalBackupsDir(), customer, pathID)
            if os.path.exists(filename):
                lg.warn('%s already exist ' % filename)
                if callOnReceived:
                    reactor.callLater(0, callOnReceived, packetID, 'exist')  # @UndefinedVariable
                return False
        if remoteID not in list(self.supplierQueues.keys()):
            # made a new queue for this man
            self.supplierQueues[remoteID] = SupplierQueue(remoteID, self.creatorID)
            lg.info('made a new receiving queue for %s' % nameurl.GetName(remoteID))
        # lg.out(10, "io_throttle.QueueRequestFile asking for %s from %s" % (packetID, nameurl.GetName(remoteID)))
        return self.supplierQueues[remoteID].SupplierRequestFile(callOnReceived, creatorID, packetID, ownerID)

    def OutboxStatus(self, pkt_out, status, error):
        """
        Called from outside to notify about single file sending result.
        """
        for supplierQueue in self.supplierQueues.values():
            if supplierQueue.OutboxStatus(pkt_out, status, error):
                return True
        return False

    def FileSendingFinished(self, pkt_out, item, status, size, error_message):
        for supplierQueue in self.supplierQueues.values():
            supplierQueue.OnFileSendingFinished(pkt_out, item, status, size, error_message)
        return False

    def IsSendingQueueEmpty(self):
        """
        Return True if all outgoing queues is empty, no sending at the moment.
        """
        for idurl in self.supplierQueues.keys():
            if self.supplierQueues[idurl].HasSendingFiles():
                # if _Debug:
                #     lg.out(_DebugLevel, 'io_throttle.IsSendingQueueEmpty   supplier %r has sending files:\n%r' % (
                #         idurl, self.supplierQueues[idurl].fileSendQueue))
                return False
        return True

    def IsRequestQueueEmpty(self):
        """
        Return True if all incoming queues is empty, no requests at the moment.
        """
        for idurl in self.supplierQueues.keys():
            if not self.supplierQueues[idurl].HasRequestedFiles():
                if _Debug:
                    lg.out(_DebugLevel, 'io_throttle.IsRequestQueueEmpty   supplier %r has requested files:\n%r' % (idurl, self.supplierQueues[idurl].fileRequestQueue))
                return False
        return True

    def HasPacketInSendQueue(self, supplierIDURL, packetID):
        """
        Return True if that packet is found in the sending queue to given
        remote peer.
        """
        supplierIDURL = id_url.field(supplierIDURL)
        if supplierIDURL not in self.supplierQueues:
            return False
        return packetID in self.supplierQueues[supplierIDURL].fileSendDict

    def HasPacketInRequestQueue(self, supplierIDURL, packetID):
        """
        Return True if that packet is found in the request queue from given
        remote peer.
        """
        supplierIDURL = id_url.field(supplierIDURL)
        if supplierIDURL not in self.supplierQueues:
            return False
        return packetID in self.supplierQueues[supplierIDURL].fileRequestDict

    def HasBackupIDInSendQueue(self, supplierIDURL, backupID):
        """
        Same to ``HasPacketInSendQueue()``, but looks for packets for the whole
        backup, not just a single packet .
        """
        supplierIDURL = id_url.field(supplierIDURL)
        if supplierIDURL not in self.supplierQueues:
            return False
        for packetID in self.supplierQueues[supplierIDURL].fileSendDict.keys():
            if packetID.count(backupID):
                return True
        return False

    def HasBackupIDInRequestQueue(self, supplierIDURL, backupID):
        """
        Same to ``HasPacketInRequestQueue()``, but looks for packets for the
        whole backup, not just a single packet .
        """
        supplierIDURL = id_url.field(supplierIDURL)
        if supplierIDURL not in self.supplierQueues:
            return False
        for packetID in self.supplierQueues[supplierIDURL].fileRequestDict.keys():
            if packetID.count(backupID):
                return True
        return False

    def IsBackupSending(self, backupID):
        """
        Return True if some packets for given backup is found in the sending
        queues.
        """
        for supplierIDURL in self.supplierQueues.keys():
            if self.HasBackupIDInSendQueue(supplierIDURL, backupID):
                return True
        return False

    def IsBackupRequesting(self, backupID):
        """
        Return True if some packets for given backup is found in the request
        queues.
        """
        for supplierIDURL in self.supplierQueues.keys():
            if self.HasBackupIDInRequestQueue(supplierIDURL, backupID):
                return True
        return False

    def OkToSend(self, supplierIDURL):
        """
        The maximum size of any queue is limited, if this limit is not reached
        yet you can put more files to send to that remote user.

        This method return True if you can put more outgoing files to
        that man in the ``throttle()``.
        """
        supplierIDURL = id_url.field(supplierIDURL)
        if supplierIDURL not in self.supplierQueues:
            # no queue opened to this man, so the queue is ready
            return True
        return self.supplierQueues[supplierIDURL].OkToSend()

    def GetRequestQueueLength(self, supplierIDURL):
        """
        Return number of requested packets from given user.
        """
        supplierIDURL = id_url.field(supplierIDURL)
        if supplierIDURL not in self.supplierQueues:
            # no queue opened to this man, so length is zero
            return 0
        return self.supplierQueues[supplierIDURL].GetRequestQueueLength()

    def GetSendQueueLength(self, supplierIDURL):
        """
        Return number of packets sent to this guy.
        """
        supplierIDURL = id_url.field(supplierIDURL)
        if supplierIDURL not in self.supplierQueues:
            # no queue opened to this man, so length is zero
            return 0
        return self.supplierQueues[supplierIDURL].GetSendQueueLength()
