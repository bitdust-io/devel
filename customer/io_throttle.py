#!/usr/bin/python
# io_throttle.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

_Debug = True
_DebugLevel = 10

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

from logs import lg

from system import bpio

from lib import misc
from lib import nameurl
from lib import packetid
from lib import utime

from main import settings

from userid import my_id
from userid import global_id

from p2p import commands
from p2p import p2p_service
from p2p import online_status

from crypt import signed

from transport import callback
from transport import packet_out

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

    This is the mechanism for sending and requesting files to drive
    backups.
    """
    lg.out(4, "io_throttle.init")
    throttle()
    callback.add_queue_item_status_callback(OutboxStatus)


def shutdown():
    """
    To stop program correctly - need to call this before shut down.
    """
    lg.out(4, "io_throttle.shutdown")
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
        lg.out(_DebugLevel, 'io_throttle.PacketReport %s:%s %s to/from %s' % (
            sendORrequest, result, packetID, supplier_idurl))
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
    """
    """
    return throttle().DeleteSuppliers(list(throttle().supplierQueues.keys()))


def OutboxStatus(pkt_out, status, error):
    """
    """
    return throttle().OutboxStatus(pkt_out, status, error)


def IsSendingQueueEmpty():
    """
    """
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

# def HasBackupIDInAllQueues(backupID):
#    return throttle().HasBackupIDInAllQueues(backupID)


def OkToSend(supplierIDURL):
    return throttle().OkToSend(supplierIDURL)


def OkToRequest(supplierIDURL):
    return throttle().OkToRequest(supplierIDURL)


def GetSendQueueLength(supplierIDURL):
    return throttle().GetSendQueueLength(supplierIDURL)


def GetRequestQueueLength(supplierIDURL):
    return throttle().GetRequestQueueLength(supplierIDURL)

#------------------------------------------------------------------------------


class FileToRequest:

    def __init__(self, callOnReceived, creatorID, packetID, ownerID, remoteID):
        self.callOnReceived = []
        self.callOnReceived.append(callOnReceived)
        self.creatorID = creatorID
        self.packetID = global_id.CanonicalID(packetID)
        parts = global_id.ParseGlobalID(packetID)
        self.customerID = parts['customer']
        self.remotePath = parts['path']
        self.customerIDURL = parts['idurl']
        customerGlobalID, remotePath, versionName, fileName = packetid.SplitVersionFilename(packetID)
        self.backupID = packetid.MakeBackupID(customerGlobalID, remotePath, versionName)
        self.fileName = fileName
        self.ownerID = ownerID
        self.remoteID = remoteID
        self.requestTime = None
        self.fileReceivedTime = None
        self.requestTimeout = max(30, 2 * int(settings.getBackupBlockSize() / settings.SendingSpeedLimit()))
        self.result = ''
        self.created = utime.get_sec1970()
        PacketReport('request', self.remoteID, self.packetID, 'init')

    def __del__(self):
        PacketReport('request', self.remoteID, self.packetID, self.result)

#------------------------------------------------------------------------------


class FileToSend:

    def __init__(self, fileName, packetID, remoteID, ownerID, callOnAck=None, callOnFail=None):
        self.fileName = fileName
        try:
            self.fileSize = os.path.getsize(os.path.abspath(fileName))
        except:
            lg.exc()
            self.fileSize = 0
        self.packetID = global_id.CanonicalID(packetID)
        parts = global_id.ParseGlobalID(packetID)
        self.customerID = parts['customer']
        self.remotePath = parts['path']
        self.customerIDURL = parts['idurl']
        customerGlobalID, remotePath, versionName, _ = packetid.SplitVersionFilename(packetID)
        self.backupID = packetid.MakeBackupID(customerGlobalID, remotePath, versionName)
        self.remoteID = remoteID
        self.ownerID = ownerID
        self.callOnAck = callOnAck
        self.callOnFail = callOnFail
        self.sendTime = None
        self.ackTime = None
        self.sendTimeout = 10 * 2 * (max(int(self.fileSize / settings.SendingSpeedLimit()), 5) + 5)  # maximum 5 seconds to get an Ack
        self.result = ''
        self.created = utime.get_sec1970()
        PacketReport('send', self.remoteID, self.packetID, 'init')

    def __del__(self):
        PacketReport('send', self.remoteID, self.packetID, self.result)

#------------------------------------------------------------------------------


class SupplierQueue:

    def __init__(self, supplierIdentity, creatorID, customerIDURL=None):
        self.customerIDURL = customerIDURL
        if self.customerIDURL is None:
            self.customerIDURL = my_id.getLocalID()
        self.creatorID = creatorID
        self.remoteID = supplierIdentity
        self.remoteName = nameurl.GetName(self.remoteID)

        # all sends we'll hold on to, only several will be active,
        # but will hold onto the next ones to be sent
        # self.fileSendQueueMaxLength = 32
        # active files
        self.fileSendMaxLength = 4
        # an array of packetId, preserving first in first out,
        # of which the first maxLength are the "active" sends
        self.fileSendQueue = []
        # dictionary of FileToSend's using packetId as index,
        # hold onto stuff sent and acked for some period as a history?
        self.fileSendDict = {}

        # all requests we'll hold on to,
        # only several will be active, but will hold onto the next ones to be sent
        # self.fileRequestQueueMaxLength = 6
        # active requests
        self.fileRequestMaxLength = 2
        # an arry of PacketIDs, preserving first in first out
        self.fileRequestQueue = []
        # FileToRequest's, indexed by PacketIDs
        self.fileRequestDict = {}

        self.shutdown = False

        self.ackedCount = 0
        self.failedCount = 0

        self.sendFailedPacketIDs = []
        self.requestFailedPacketIDs = []

        self._runSend = False
        self.sendTask = None
        self.sendTaskDelay = 0.1
        self.requestTask = None
        self.requestTaskDelay = 0.1

    def ListSendItems(self):
        return self.fileSendQueue

    def GetSendItem(self, packetID):
        return self.fileSendDict.get(packetID)

    def ListRequestItems(self):
        return self.fileRequestQueue

    def GetRequestItem(self, packetID):
        return self.fileRequestDict.get(packetID)

    def RemoveSupplierWork(self):
        self.DeleteBackupSendings(backupName=None)
        self.DeleteBackupRequests(backupName=None)

    def SupplierSendFile(self, fileName, packetID, ownerID, callOnAck=None, callOnFail=None):
        if self.shutdown:
            if _Debug:
                lg.out(_DebugLevel, "io_throttle.SupplierSendFile finishing to %s, shutdown is True" % self.remoteName)
            return False
        if online_status.isOffline(self.remoteID):
            if _Debug:
                lg.out(_DebugLevel, "io_throttle.SupplierSendFile %s is offline, so packet %s is failed" % (
                    self.remoteName, packetID))
            if callOnFail is not None:
                reactor.callLater(0, callOnFail, self.remoteID, packetID, 'offline')  # @UndefinedVariable
            return False
        if packetID in self.fileSendQueue:
            lg.warn("packet %s already in the queue for %s" % (packetID, self.remoteName))
            if callOnFail is not None:
                reactor.callLater(0, callOnFail, self.remoteID, packetID, 'in queue')  # @UndefinedVariable
            return False
        self.fileSendQueue.append(packetID)
        self.fileSendDict[packetID] = FileToSend(
            fileName,
            packetID,
            self.remoteID,
            ownerID,
            callOnAck,
            callOnFail,)
        if _Debug:
            lg.out(_DebugLevel, "io_throttle.SupplierSendFile %s to %s, %d queued items" % (
                packetID, self.remoteName, len(self.fileSendQueue)))
        # reactor.callLater(0, self.DoSend)
        self.DoSend()
        return True

    def RunSend(self):
        if self._runSend:
            return
        self._runSend = True
        if _Debug:
            lg.out(_DebugLevel + 6, 'io_throttle.RunSend\n    fileSendQueue=%r\n    sendFailedPacketIDs=%r' % (
                self.fileSendQueue, self.sendFailedPacketIDs))
        packetsToBeFailed = {}
        packetsToRemove = set()
        packetsSent = 0
        # let's check all packets in the queue
        for i in range(len(self.fileSendQueue)):
            try:
                packetID = self.fileSendQueue[i]
            except:
                lg.warn("item at position %d not exist in send queue" % i)
                continue
            fileToSend = self.fileSendDict[packetID]
            # we got notify that this packet was failed to send
            if packetID in self.sendFailedPacketIDs:
                self.sendFailedPacketIDs.remove(packetID)
                packetsToBeFailed[packetID] = 'failed'
                continue
            # we already sent the file
            if fileToSend.sendTime is not None:
                packetsSent += 1
                # and we got ack
                if fileToSend.ackTime is not None:
                    # deltaTime = fileToSend.ackTime - fileToSend.sendTime
                    # so remove it from queue
                    packetsToRemove.add(packetID)
                # if we do not get an ack ...
                else:
                    # ... we do not want to wait to long
                    if time.time() - fileToSend.sendTime > fileToSend.sendTimeout:
                        # so this packet is failed because no response on it
                        packetsToBeFailed[packetID] = 'timeout'
                # we sent this packet already - check next one
                continue
            # the data file to send no longer exists - it is failed situation
            if not os.path.exists(fileToSend.fileName):
                lg.warn("file %s not exist" % (fileToSend.fileName))
                packetsToBeFailed[packetID] = 'not exist'
                continue
            # do not send too many packets, need to wait for ack
            # hold other packets in the queue and may be send next time
            if packetsSent > self.fileSendMaxLength:
                # if we sending big file - we want to wait
                # other packets must go without waiting in the queue
                # 10K seems fine, because we need to filter only Data and Parity packets here
                try:
                    if os.path.getsize(fileToSend.fileName) > 1024 * 10:
                        continue
                except:
                    lg.exc()
                    continue
            # prepare the packet
            # dt = time.time()
            Payload = bpio.ReadBinaryFile(fileToSend.fileName)
            p2p_service.SendData(
                raw_data=Payload,
                ownerID=fileToSend.ownerID,
                creatorID=self.creatorID,
                remoteID=fileToSend.remoteID,
                packetID=fileToSend.packetID,
                callbacks={
                    commands.Ack(): self.OnFileSendAckReceived,
                    commands.Fail(): self.OnFileSendAckReceived,
                },
            )
            # outbox will not resend, because no ACK, just data,
            # need to handle resends on own
            # transport_control.outboxNoAck(newpacket)
            # gateway.outbox(newpacket, callbacks={
            #     commands.Ack(): self.OnFileSendAckReceived,
            #     commands.Fail(): self.OnFileSendAckReceived,
            # })

            # str(bpio.ReadBinaryFile(fileToSend.fileName))
            # {commands.Ack(): self.OnFileSendAckReceived,
            # commands.Fail(): self.OnFileSendAckReceived}

            # transport_control.RegisterInterest(
            #     self.OnFileSendAckReceived,
            #     fileToSend.remoteID,
            #     fileToSend.packetID)
            # callback.register_interest(self.OnFileSendAckReceived, fileToSend.remoteID, fileToSend.packetID)
            # lg.out(12, 'io_throttle.RunSend %s to %s, dt=%s' % (
            #     str(newpacket), nameurl.GetName(fileToSend.remoteID), str(time.time()-dt)))
            # mark file as been sent
            fileToSend.sendTime = time.time()
            packetsSent += 1
        # process failed packets
        for packetID, why in packetsToBeFailed.items():
            remoteID = self.fileSendDict[packetID].remoteID
            reactor.callLater(0, self.OnFileSendFailReceived, remoteID, packetID, why)  # @UndefinedVariable
            packetsToRemove.add(packetID)
        # remove finished packets
        for packetID in packetsToRemove:
            self.fileSendQueue.remove(packetID)
            del self.fileSendDict[packetID]
            if _Debug:
                lg.out(_DebugLevel, "io_throttle.RunSend removed %s from %s sending queue, %d more items" % (
                    packetID, self.remoteName, len(self.fileSendQueue)))
        # if sending queue is empty - remove all records about packets failed to send
        if len(self.fileSendQueue) == 0:
            del self.sendFailedPacketIDs[:]
        # remember results
        result = max(len(packetsToRemove), packetsSent)
        # erase temp lists
        del packetsToBeFailed
        del packetsToRemove
        self._runSend = False
        return result

    def SendingTask(self):
        sends = self.RunSend()
        self.sendTaskDelay = misc.LoopAttenuation(
            self.sendTaskDelay,
            sends > 0,
            settings.MinimumSendingDelay(),
            settings.MaximumSendingDelay())
        # attenuation
        self.sendTask = reactor.callLater(self.sendTaskDelay, self.SendingTask)  # @UndefinedVariable

    def DoSend(self):
        #out(6, 'io_throttle.DoSend')
        if self.sendTask is None:
            self.SendingTask()
            return
        if self._runSend:
            return
        if self.sendTaskDelay > 1.0:
            self.sendTask.cancel()
            self.sendTask = None
            reactor.callLater(0, self.SendingTask)  # @UndefinedVariable

    def SupplierRequestFile(self, callOnReceived, creatorID, packetID, ownerID):
        if self.shutdown:
            if _Debug:
                lg.out(_DebugLevel, "io_throttle.SupplierRequestFile finishing to %s, shutdown is True" % self.remoteName)
            if callOnReceived:
                reactor.callLater(0, callOnReceived, packetID, 'shutdown')  # @UndefinedVariable
            return False
        if packetID in self.fileRequestQueue:
            lg.warn("packet %s already in the queue for %s" % (packetID, self.remoteName))
            if callOnReceived:
                reactor.callLater(0, callOnReceived, packetID, 'in queue')  # @UndefinedVariable
            return False
        self.fileRequestQueue.append(packetID)
        self.fileRequestDict[packetID] = FileToRequest(
            callOnReceived, creatorID, packetID, ownerID, self.remoteID)
        if _Debug:
            lg.out(_DebugLevel, "io_throttle.SupplierRequestFile %s from %s, %d queued items" % (
                packetID, self.remoteName, len(self.fileRequestQueue)))
        # reactor.callLater(0, self.DoRequest)
        self.DoRequest()
        return True

    def RunRequest(self):
        #out(6, 'io_throttle.RunRequest')
        packetsToRemove = {}
        for i in range(0, min(self.fileRequestMaxLength, len(self.fileRequestQueue))):
            packetID = self.fileRequestQueue[i]
            # we got notify that this packet was failed to send
            if packetID in self.requestFailedPacketIDs:
                self.requestFailedPacketIDs.remove(packetID)
                packetsToRemove[packetID] = 'failed'
                continue
            # request timeouts are disabled for now
#             currentTime = time.time()
#             if self.fileRequestDict[packetID].requestTime is not None:
#                 # the packet was requested
#                 if self.fileRequestDict[packetID].fileReceivedTime is None:
#                     # but no answer yet ...
#                     if currentTime - self.fileRequestDict[packetID].requestTime > self.fileRequestDict[packetID].requestTimeout:
#                         # and time is out!!!
#                         self.fileRequestDict[packetID].report = 'timeout'
#                         packetsToRemove[packetID] = 'timeout'
#                 else:
#                     # the packet were received (why it is not removed from the queue yet ???)
#                     self.fileRequestDict[packetID].result = 'received'
#                     packetsToRemove[packetID] = 'received'
            # the packet was not requested yet
            if self.fileRequestDict[packetID].requestTime is None:
                customer, pathID = packetid.SplitPacketID(packetID)
                if not os.path.exists(os.path.join(settings.getLocalBackupsDir(), customer, pathID)):
                    fileRequest = self.fileRequestDict[packetID]
                    if _Debug:
                        lg.out(_DebugLevel, "io_throttle.RunRequest for packetID " + fileRequest.packetID)
                    # transport_control.RegisterInterest(self.DataReceived,fileRequest.creatorID,fileRequest.packetID)
                    # callback.register_interest(self.DataReceived, fileRequest.creatorID, fileRequest.packetID)
                    p2p_service.SendRetreive(
                        fileRequest.ownerID,
                        fileRequest.creatorID,
                        fileRequest.packetID,
                        fileRequest.remoteID,
                        callbacks={
                            commands.Data(): self.OnDataReceived,
                            commands.Fail(): self.OnDataReceived,
                            # None: lambda pkt_out: self.OnDataReceived(fileRequest.packetID, 'timeout'),  # timeout
                        },
                        # response_timeout=10,
                    )
#                     newpacket = signed.Packet(
#                         commands.Retrieve(),
#                         fileRequest.ownerID,
#                         fileRequest.creatorID,
#                         packetid.RemotePath(fileRequest.packetID),
#                         "",
#                         fileRequest.remoteID)
#                     gateway.outbox(newpacket, callbacks={
#                         commands.Data(): self.DataReceived,
#                         commands.Fail(): self.DataReceived})
                    fileRequest.requestTime = time.time()
                else:
                    # we have the data file, no need to request it
                    self.fileRequestDict[packetID].result = 'exist'
                    packetsToRemove[packetID] = 'exist'
        # if request queue is empty - remove all records about packets failed to request
        if len(self.fileRequestQueue) == 0:
            del self.requestFailedPacketIDs[:]
        # remember requests results
        result = len(packetsToRemove)
        # remove finished requests
        for packetID, why in packetsToRemove.items():
            # self.fileRequestQueue.remove(packetID)
            if _Debug:
                lg.out(_DebugLevel, "io_throttle.RunRequest removed %s from %s receiving queue, %d more items" % (
                    packetID, self.remoteName, len(self.fileRequestQueue)))
            self.OnDataRequestFailed(packetID, why)
        del packetsToRemove
        return result

    def RequestTask(self):
        if self.shutdown:
            return
#        if self.RunRequest() > 0:
#            self.requestTaskDelay = 0.1
#        else:
#            if self.requestTaskDelay < 8.0:
#                self.requestTaskDelay *= 2.0
        requests = self.RunRequest()
        self.requestTaskDelay = misc.LoopAttenuation(
            self.requestTaskDelay,
            requests > 0,
            settings.MinimumReceivingDelay(),
            settings.MaximumReceivingDelay())
        # attenuation
        self.requestTask = reactor.callLater(self.requestTaskDelay, self.RequestTask)  # @UndefinedVariable

    def DoRequest(self):
        #out(6, 'io_throttle.DoRequest')
        if self.requestTask is None:
            self.RequestTask()
        else:
            if self.requestTaskDelay > 1.0:
                self.requestTask.cancel()
                self.requestTask = None
                self.RequestTask()

    def DeleteBackupSendings(self, backupName):
        if self.shutdown:
            # if we're closing down this queue
            # (supplier replaced, don't any anything new)
            return
        packetsToRemove = set()
        for packetID in self.fileSendQueue:
            if (backupName and packetID.count(backupName)) or not backupName:
                remoteID = self.fileSendDict[packetID].remoteID
                reactor.callLater(0, self.OnFileSendFailReceived, remoteID, packetID, 'delete request')  # @UndefinedVariable
                packetsToRemove.add(packetID)
        for packetID in packetsToRemove:
            if packetID in self.fileSendDict:
                self.fileSendQueue.remove(packetID)
                del self.fileSendDict[packetID]
                if _Debug:
                    lg.out(_DebugLevel, "io_throttle.DeleteBackupSendings removed %s from %s sending queue, %d more items" % (
                        packetID, self.remoteName, len(self.fileSendQueue)))
        if len(self.fileSendQueue) > 0:
            reactor.callLater(0, self.DoSend)  # @UndefinedVariable
            # self.DoSend()

    def DeleteBackupRequests(self, backupName):
        if self.shutdown:
            # if we're closing down this queue
            # (supplier replaced, don't any anything new)
            return
        packetsToRemove = set()
        packetsToCancel = []
        for packetID in self.fileRequestQueue:
            if (backupName and packetID.count(backupName)) or not backupName:
                packetsToRemove.add(packetID)
                if _Debug:
                    lg.out(_DebugLevel, 'io_throttle.DeleteBackupRequests %s from request queue' % packetID)
        for packetID in packetsToRemove:
            self.fileRequestQueue.remove(packetID)
            del self.fileRequestDict[packetID]
            if _Debug:
                lg.out(_DebugLevel, "io_throttle.DeleteBackupRequests removed %s from %s receiving queue, %d more items" % (
                    packetID, self.remoteName, len(self.fileRequestQueue)))
        if backupName:
            packetsToCancel.extend(packet_out.search_by_backup_id(backupName))
        else:
            for packetID in packetsToRemove:
                packetsToCancel.extend(packet_out.search_by_backup_id(packetID))
        for pkt_out in packetsToCancel:
            if pkt_out.outpacket.Command == commands.Retrieve():
                if pkt_out.outpacket.PacketID in packetsToRemove:
                    lg.warn('sending "cancel" to %s addressed to %s   from io_throttle' % (
                        pkt_out, pkt_out.remote_idurl, ))
                    pkt_out.automat('cancel')
        if len(self.fileRequestQueue) > 0:
            reactor.callLater(0, self.DoRequest)  # @UndefinedVariable

    def OutboxStatus(self, pkt_out, status, error):
        packetID = global_id.CanonicalID(pkt_out.outpacket.PacketID)
        if status != 'finished':
            if packetID in self.fileSendQueue:
                lg.warn('packet %s status is %s in sending queue for %s' % (packetID, status, self.remoteName))
                self.sendFailedPacketIDs.append(packetID)
                # reactor.callLater(0, self.DoSend)
                self.DoSend()
            if packetID in self.fileRequestQueue:
                lg.warn('packet %s status is %s in request queue for %s' % (packetID, status, self.remoteName))
                self.requestFailedPacketIDs.append(packetID)
                self.DoRequest()

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

    def OnFileSendAckReceived(self, newpacket, info):
        if self.shutdown:
            if _Debug:
                lg.out(_DebugLevel, "io_throttle.OnFileSendAckReceived finishing to %s, shutdown is True" % self.remoteName)
            return
        if not newpacket and not info:
            lg.warn('packet timed out during responding')
            return
        self.ackedCount += 1
        packetID = global_id.CanonicalID(newpacket.PacketID)
        if packetID not in self.fileSendQueue:
            lg.warn("packet %s not in sending queue for %s" % (newpacket.PacketID, self.remoteName))
            return
        if packetID not in list(self.fileSendDict.keys()):
            lg.warn("packet %s not in sending dict for %s" % (newpacket.PacketID, self.remoteName))
            return
        self.fileSendDict[packetID].ackTime = time.time()
        if newpacket.Command == commands.Ack():
            self.fileSendDict[packetID].result = 'acked'
            if self.fileSendDict[packetID].callOnAck:
                reactor.callLater(0, self.fileSendDict[packetID].callOnAck, newpacket, newpacket.OwnerID, packetID)  # @UndefinedVariable
        elif newpacket.Command == commands.Fail():
            self.fileSendDict[packetID].result = 'failed'
            if self.fileSendDict[packetID].callOnFail:
                reactor.callLater(0, self.fileSendDict[packetID].callOnFail, newpacket.CreatorID, packetID, 'failed')  # @UndefinedVariable
        from customer import supplier_connector
        sc = supplier_connector.by_idurl(newpacket.OwnerID)
        if sc:
            if newpacket.Command == commands.Ack():
                sc.automat('ack', newpacket)
            elif newpacket.Command == commands.Fail():
                sc.automat('fail', newpacket)
            # elif newpacket.Command == commands.Data():
            #     sc.automat('data', newpacket)
            else:
                raise Exception('incorrect packet type received')
        self.DoSend()
        # self.RunSend()
        if _Debug:
            lg.out(_DebugLevel, "io_throttle.OnFileSendAckReceived %s from %s, queue=%d" % (
                str(newpacket), self.remoteName, len(self.fileSendQueue)))

    def OnFileSendFailReceived(self, RemoteID, PacketID, why):
        if self.shutdown:
            if _Debug:
                lg.out(_DebugLevel, "io_throttle.OnFileSendFailReceived finishing to %s, shutdown is True" % self.remoteName)
            return
        self.failedCount += 1
        if PacketID not in list(self.fileSendDict.keys()):
            lg.warn("packet %s not in fileSendDict anymore" % PacketID)
            return
        self.fileSendDict[PacketID].result = why
        fileToSend = self.fileSendDict[PacketID]
        assert fileToSend.remoteID == RemoteID
        # transport_control.RemoveSupplierRequestFromSendQueue(fileToSend.packetID, fileToSend.remoteID, commands.Data())
        # queue.remove_supplier_request(fileToSend.packetID, fileToSend.remoteID, commands.Data())
        # transport_control.RemoveInterest(fileToSend.remoteID, fileToSend.packetID)
        # callback.remove_interest(fileToSend.remoteID, fileToSend.packetID)
        if why == 'timeout':
            online_status.PacketSendingTimeout(RemoteID, PacketID)
        if fileToSend.callOnFail:
            reactor.callLater(0, fileToSend.callOnFail, RemoteID, PacketID, why)  # @UndefinedVariable
        self.DoSend()
        # self.RunSend()
        if _Debug:
            lg.out(_DebugLevel, "io_throttle.OnFileSendFailReceived %s to [%s] because %s" % (
                PacketID, nameurl.GetName(fileToSend.remoteID), why))

    def OnDataReceived(self, newpacket, result):
#         if result == 'timeout':
#             packetID = global_id.CanonicalID(newpacket)
#             if packetID in self.fileRequestDict:
#                 self.fileRequestDict[packetID].fileReceivedTime = time.time()
#                 self.fileRequestDict[packetID].result = 'timeout'
#                 for callBack in self.fileRequestDict[packetID].callOnReceived:
#                     callBack(None, 'timeout')
#             return
        # we requested some data from a supplier, just received it
        packetID = global_id.CanonicalID(newpacket.PacketID)
        if self.shutdown:
            # if we're closing down this queue (supplier replaced, don't any anything new)
            if packetID in self.fileRequestDict:
                for callBack in self.fileRequestDict[packetID].callOnReceived:
                    callBack(newpacket, 'shutdown')
            if packetID in self.fileRequestDict:
                del self.fileRequestDict[packetID]
            lg.warn('supplier queue is shutting down')
            return
        if _Debug:
            lg.out(_DebugLevel, "io_throttle.OnDataReceived  %s with result=[%s]" % (newpacket, result, ))
        if packetID in self.fileRequestQueue:
            self.fileRequestQueue.remove(packetID)
            if _Debug:
                lg.out(_DebugLevel, "    removed %s from %s receiving queue, %d more items" % (
                    packetID, self.remoteName, len(self.fileRequestQueue)))
        if newpacket.Command == commands.Data():
            wrapped_packet = signed.Unserialize(newpacket.Payload)
            if not wrapped_packet or not wrapped_packet.Valid():
                lg.err('incoming Data() is not valid')
                return
            if packetID in self.fileRequestDict:
                self.fileRequestDict[packetID].fileReceivedTime = time.time()
                self.fileRequestDict[packetID].result = 'received'
                for callBack in self.fileRequestDict[packetID].callOnReceived:
                    callBack(wrapped_packet, 'received')
        elif newpacket.Command == commands.Fail():
            if packetID in self.fileRequestDict:
                self.fileRequestDict[packetID].fileReceivedTime = time.time()
                self.fileRequestDict[packetID].result = 'failed'
                for callBack in self.fileRequestDict[packetID].callOnReceived:
                    callBack(newpacket, 'failed')
        else:
            lg.err('incorrect response command')
        if packetID in self.fileRequestDict:
            del self.fileRequestDict[packetID]
        if _Debug:
            lg.out(_DebugLevel, "io_throttle.OnDataReceived %s from %s, queue=%d" % (
                newpacket, self.remoteName, len(self.fileRequestQueue)))
        self.DoRequest()

    def OnDataRequestFailed(self, packetID, why=None):
        # we requested some data from a supplier, but this failed for some reason
        if self.shutdown:
            # if we're closing down this queue (supplier replaced, don't any anything new)
            if packetID in self.fileRequestDict:
                for callBack in self.fileRequestDict[packetID].callOnReceived:
                    callBack(packetID, 'shutdown')
            if packetID in self.fileRequestDict:
                del self.fileRequestDict[packetID]
            lg.warn('supplier queue is shutting down')
            return
        if packetID in self.fileRequestQueue:
            self.fileRequestQueue.remove(packetID)
            if _Debug:
                lg.out(_DebugLevel, "io_throttle.OnDataRequestFailed removed %s from %s receiving queue because %s, %d more items" % (
                    packetID, self.remoteName, why, len(self.fileRequestQueue)))
        else:
            lg.warn('packet %s not found in request queue for %s' % (packetID, self.remoteName))
        if packetID in self.fileRequestDict:
            self.fileRequestDict[packetID].fileReceivedTime = time.time()
            self.fileRequestDict[packetID].result = why or 'failed'
            for callBack in self.fileRequestDict[packetID].callOnReceived:
                callBack(packetID, why or 'failed')
            del self.fileRequestDict[packetID]
        else:
            lg.warn('packet %s not found request info for %s' % (packetID, self.remoteName))
        self.DoRequest()

#------------------------------------------------------------------------------


class IOThrottle:
    """
    All of the backup rebuilds will run their data requests through this
    So it gets throttled, also to reduce duplicate requests.
    """

    def __init__(self):
        self.creatorID = my_id.getLocalID()
        self.supplierQueues = {}
        self.paintFunc = None

    def GetSupplierQueue(self, supplierIDURL):
        return self.supplierQueues.get(supplierIDURL)

    def ListSupplierQueues(self):
        return list(self.supplierQueues.keys())

    def SetSupplierQueueCallbackFunc(self, func):
        self.paintFunc = func

    def DeleteSuppliers(self, suppliers_IDURLs):
        for supplierIDURL in suppliers_IDURLs:
            if supplierIDURL:
                if supplierIDURL in self.supplierQueues:
                    self.supplierQueues[supplierIDURL].RemoveSupplierWork()
                    del self.supplierQueues[supplierIDURL]

    def DeleteBackupSendings(self, backupName):
        # lg.out(10, 'io_throttle.DeleteBackupSendings for %s' % backupName)
        for supplierIdentity in self.supplierQueues.keys():
            self.supplierQueues[supplierIdentity].DeleteBackupSendings(backupName)

    def DeleteBackupRequests(self, backupName):
        # lg.out(10, 'io_throttle.DeleteBackupRequests for %s' % backupName)
        for supplierIdentity in self.supplierQueues.keys():
            self.supplierQueues[supplierIdentity].DeleteBackupRequests(backupName)

    def QueueSendFile(self, fileName, packetID, remoteID, ownerID, callOnAck=None, callOnFail=None):
        #out(10, "io_throttle.QueueSendFile %s to %s" % (packetID, nameurl.GetName(remoteID)))
        if not os.path.exists(fileName):
            lg.err("%s not exist" % fileName)
            if callOnFail is not None:
                reactor.callLater(.01, callOnFail, remoteID, packetID, 'not exist')  # @UndefinedVariable
            return False
        if remoteID not in list(self.supplierQueues.keys()):
            self.supplierQueues[remoteID] = SupplierQueue(remoteID, self.creatorID)
            lg.info("made a new sending queue for %s" % nameurl.GetName(remoteID))
        return self.supplierQueues[remoteID].SupplierSendFile(
            fileName, packetID, ownerID, callOnAck, callOnFail,)

    # return result in the callback: callOnReceived(packet or packetID, state)
    # state is: received, exist, in queue, shutdown
    def QueueRequestFile(self, callOnReceived, creatorID, packetID, ownerID, remoteID):
        # make sure that we don't actually already have the file
        # if packetID != settings.BackupInfoFileName():
        if packetID not in [
                settings.BackupInfoFileName(),
                settings.BackupInfoFileNameOld(),
                settings.BackupInfoEncryptedFileName(), ]:
            customer, pathID = packetid.SplitPacketID(packetID)
            filename = os.path.join(settings.getLocalBackupsDir(), customer, pathID)
            if os.path.exists(filename):
                lg.warn("%s already exist " % filename)
                if callOnReceived:
                    reactor.callLater(0, callOnReceived, packetID, 'exist')  # @UndefinedVariable
                return False
        if remoteID not in list(self.supplierQueues.keys()):
            # made a new queue for this man
            self.supplierQueues[remoteID] = SupplierQueue(remoteID, self.creatorID)
            lg.info("made a new receiving queue for %s" % nameurl.GetName(remoteID))
        # lg.out(10, "io_throttle.QueueRequestFile asking for %s from %s" % (packetID, nameurl.GetName(remoteID)))
        return self.supplierQueues[remoteID].SupplierRequestFile(
            callOnReceived, creatorID, packetID, ownerID)

    def OutboxStatus(self, pkt_out, status, error):
        """
        Called from outside to notify about single file sending result.
        """
        for supplierIdentity in self.supplierQueues.keys():
            self.supplierQueues[supplierIdentity].OutboxStatus(pkt_out, status, error)
        return False

    def IsSendingQueueEmpty(self):
        """
        Return True if all outgoing queues is empty, no sending at the moment.
        """
        for idurl in self.supplierQueues.keys():
            if self.supplierQueues[idurl].HasSendingFiles():
                if _Debug:
                    lg.out(_DebugLevel, 'io_throttle.IsSendingQueueEmpty   supplier %r has sending files:\n%r' % (
                        idurl, self.supplierQueues[idurl].fileSendQueue))
                return False
        return True

    def IsRequestQueueEmpty(self):
        """
        Return True if all incoming queues is empty, no requests at the moment.
        """
        for idurl in self.supplierQueues.keys():
            if not self.supplierQueues[idurl].HasRequestedFiles():
                if _Debug:
                    lg.out(_DebugLevel, 'io_throttle.IsRequestQueueEmpty   supplier %r has requested files:\n%r' % (
                        idurl, self.supplierQueues[idurl].fileRequestQueue))
                return False
        return True

    def HasPacketInSendQueue(self, supplierIDURL, packetID):
        """
        Return True if that packet is found in the sending queue to given
        remote peer.
        """
        if supplierIDURL not in self.supplierQueues:
            return False
        return packetID in self.supplierQueues[supplierIDURL].fileSendDict

    def HasPacketInRequestQueue(self, supplierIDURL, packetID):
        """
        Return True if that packet is found in the request queue from given
        remote peer.
        """
        if supplierIDURL not in self.supplierQueues:
            return False
        return packetID in self.supplierQueues[supplierIDURL].fileRequestDict

    def HasBackupIDInSendQueue(self, supplierIDURL, backupID):
        """
        Same to ``HasPacketInSendQueue()``, but looks for packets for the whole
        backup, not just a single packet .
        """
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
        if supplierIDURL not in self.supplierQueues:
            # no queue opened to this man, so the queue is ready
            return True
        return self.supplierQueues[supplierIDURL].OkToSend()

    def GetRequestQueueLength(self, supplierIDURL):
        """
        Return number of requested packets from given user.
        """
        if supplierIDURL not in self.supplierQueues:
            # no queue opened to this man, so length is zero
            return 0
        return self.supplierQueues[supplierIDURL].GetRequestQueueLength()

    def GetSendQueueLength(self, supplierIDURL):
        """
        Return number of packets sent to this guy.
        """
        if supplierIDURL not in self.supplierQueues:
            # no queue opened to this man, so length is zero
            return 0
        return self.supplierQueues[supplierIDURL].GetSendQueueLength()
