#!/usr/bin/python
#io_throttle.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: io_throttle

When reconstructing a backup we don't want to take over everything
and make BitPie.NET unresponsive by requesting 1000's of files at once
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

import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in io_throttle.py')

from logs import lg

from lib import bpio
from lib import settings
from lib import commands
from lib import misc
from lib import nameurl

from crypt import signed

from transport import gateway
from transport import callback

import contact_status
import supplier_connector

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
    This is the mechanism for sending and requesting files to drive backups.
    """
    lg.out(4,"io_throttle.init")
    throttle()
    callback.add_queue_item_status_callback(OutboxStatus)

def shutdown():
    """
    To stop program correctly - need to call this before shut down.
    """
    lg.out(4,"io_throttle.shutdown")
    throttle().DeleteBackupRequests('')
    throttle().DeleteBackupSendings('')
    throttle().DeleteSuppliers(throttle().supplierQueues.keys())

def SetPacketReportCallbackFunc(func):
    """
    You can pass a callback to catch a moment when some packet is added/removed. 
    """
    global _PacketReportCallbackFunc
    _PacketReportCallbackFunc = func
    
def PacketReport(sendORrequest, supplier_idurl, packetID, result):
    """
    Called from other methods here to notify about packets events.
    """
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
    Place a request to download a single file from given remote peer.
    Remote user will verify our identity and decide to send the Data or not.
    """
    return throttle().QueueRequestFile(callOnReceived, creatorID, packetID, ownerID, remoteID)

def DeleteBackupSendings(backupName):
    """
    Checks all send queues and search for packets with ``backupName`` in the packetID field.
    For example, this is used to remove old transfers if rebuilding process is restarted.  
    """
    return throttle().DeleteBackupSendings(backupName)

def DeleteBackupRequests(backupName):
    """
    Checks all request queues and search for packets with ``backupName`` in the packetID field.
    For example, this is used to remove old requests if the restore process is aborted.  
    """
    return throttle().DeleteBackupRequests(backupName)

def DeleteSuppliers(suppliers_IDURLs):
    """
    Erase the whole queue with this peer and remove him from throttle() completely. 
    """
    return throttle().DeleteSuppliers(suppliers_IDURLs)

def DeleteAllSuppliers():
    """
    """
    return throttle().DeleteSuppliers(throttle().supplierQueues.keys())

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

#def HasBackupIDInAllQueues(backupID):
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
        self.packetID = packetID
        self.ownerID = ownerID
        self.remoteID = remoteID
        self.backupID, x, self.fileName = packetID.rpartition('/')  # [0:packetID.find("-")]
        self.requestTime = None
        self.fileReceivedTime = None
        self.requestTimeout = max(30, 2*int(settings.getBackupBlockSize()/settings.SendingSpeedLimit()))
        self.result = ''
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
        self.packetID = packetID
        self.remoteID = remoteID
        self.ownerID = ownerID
        self.callOnAck = callOnAck
        self.callOnFail = callOnFail
        self.sendTime = None
        self.ackTime = None
        self.sendTimeout = max( int(self.fileSize/settings.SendingSpeedLimit() ), 5 ) + 5 # maximum 5 seconds to get an Ack
        self.result = ''
        PacketReport('send', self.remoteID, self.packetID, 'init')
        
    def __del__(self):
        PacketReport('send', self.remoteID, self.packetID, self.result)

#------------------------------------------------------------------------------ 

#TODO I'm not removing items from the dict's at the moment
class SupplierQueue:
    def __init__(self, supplierIdentity, creatorID):
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
        self.fileRequestMaxLength = 4 
        # an arry of PacketIDs, preserving first in first out
        self.fileRequestQueue = []      
        # FileToRequest's, indexed by PacketIDs
        self.fileRequestDict = {}       

        self.shutdown = False

        self.ackedCount = 0
        self.failedCount = 0
        
        self.sendFailedPacketIDs = []
        
        self._runSend = False
        self.sendTask = None
        self.sendTaskDelay = 0.1
        self.requestTask = None
        self.requestTaskDelay = 0.1


    def RemoveSupplierWork(self):
        """
        """ 
        # in the case that we're doing work with a supplier who has just been replaced ...
        # Need to remove the register interests
        # our dosend is using acks?
        # self.shutdown = True
        # for i in range(min(self.fileSendMaxLength, len(self.fileSendQueue))):
        #     fileToSend = self.fileSendDict[self.fileSendQueue[i]]
            # queue.remove_supplier_request(fileToSend.packetID, fileToSend.remoteID, commands.Data())
            # transport_control.RemoveSupplierRequestFromSendQueue(fileToSend.packetID, fileToSend.remoteID, commands.Data())
        #     callback.remove_interest(fileToSend.remoteID, fileToSend.packetID)
            # transport_control.RemoveInterest(fileToSend.remoteID, fileToSend.packetID)
        # for i in range(min(self.fileRequestMaxLength, len(self.fileRequestQueue))):
        #     fileToRequest = self.fileRequestDict[self.fileRequestQueue[i]]
            # queue.remove_supplier_request(fileToRequest.packetID, fileToRequest.remoteID, commands.Retrieve())
            # transport_control.RemoveSupplierRequestFromSendQueue(fileToRequest.packetID, fileToRequest.remoteID, commands.Retrieve())
        #     callback.remove_interest(fileToRequest.remoteID, fileToRequest.packetID)
            # transport_control.RemoveInterest(fileToRequest.remoteID, fileToRequest.packetID)


    def SupplierSendFile(self, fileName, packetID, ownerID, callOnAck=None, callOnFail=None):
        if self.shutdown: 
            lg.out(10, "io_throttle.SupplierSendFile finishing to %s, shutdown is True" % self.remoteName)
            return False       
        if contact_status.isOffline(self.remoteID):
            lg.out(10, "io_throttle.SupplierSendFile %s is offline, so packet %s is failed" % (self.remoteName, packetID))
            if callOnFail is not None:
                reactor.callLater(0, callOnFail, self.remoteID, packetID, 'offline')
            return False
        if packetID in self.fileSendQueue:
            lg.warn("packet %s already in the queue for %s" % (packetID, self.remoteName))
            if callOnFail is not None:
                reactor.callLater(0, callOnFail, self.remoteID, packetID, 'in queue')
            return False
        self.fileSendQueue.append(packetID)
        self.fileSendDict[packetID] = FileToSend(
            fileName, 
            packetID, 
            self.remoteID, 
            ownerID, 
            callOnAck,
            callOnFail,)
        lg.out(10, "io_throttle.SupplierSendFile %s to %s, queue=%d" % (packetID, self.remoteName, len(self.fileSendQueue)))
        # reactor.callLater(0, self.DoSend)
        self.DoSend()
        return True
            
            
    def RunSend(self):
        if self._runSend:
            return
        self._runSend = True
        #out(6, 'io_throttle.RunSend')
        packetsFialed = {}
        packetsToRemove = set()
        packetsSent = 0
        # let's check all packets in the queue        
        for i in xrange(len(self.fileSendQueue)):
            packetID = self.fileSendQueue[i]
            fileToSend = self.fileSendDict[packetID]
            # we got notify that this packet was failed to send
            if packetID in self.sendFailedPacketIDs:
                self.sendFailedPacketIDs.remove(packetID)
                packetsFialed[packetID] = 'failed'
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
                        packetsFialed[packetID] = 'timeout'
                # we sent this packet already - check next one
                continue
            # the data file to send no longer exists - it is failed situation
            if not os.path.exists(fileToSend.fileName):
                lg.warn("file %s not exist" % (fileToSend.fileName))
                packetsFialed[packetID] = 'not exist'
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
            dt = time.time()
            Payload = str(bpio.ReadBinaryFile(fileToSend.fileName))
            newpacket = signed.Packet(
                commands.Data(), 
                fileToSend.ownerID, 
                self.creatorID, 
                fileToSend.packetID, 
                Payload, 
                fileToSend.remoteID)
            # outbox will not resend, because no ACK, just data, 
            # need to handle resends on own
            # transport_control.outboxNoAck(newpacket)
            gateway.outbox(newpacket, callbacks={
                commands.Ack(): self.FileSendAck,
                commands.Fail(): self.FileSendAck}) 
            # transport_control.RegisterInterest(
            #     self.FileSendAck, 
            #     fileToSend.remoteID, 
            #     fileToSend.packetID)
            # callback.register_interest(self.FileSendAck, fileToSend.remoteID, fileToSend.packetID)
            lg.out(12, 'io_throttle.RunSend %s to %s, dt=%s' % (
                str(newpacket), nameurl.GetName(fileToSend.remoteID), str(time.time()-dt)))
            # mark file as been sent
            fileToSend.sendTime = time.time()
            packetsSent += 1
        # process failed packets
        for packetID, why in packetsFialed.items():
            self.FileSendFailed(self.fileSendDict[packetID].remoteID, packetID, why)
            packetsToRemove.add(packetID)
        # remove finished packets    
        for packetID in packetsToRemove:
            self.fileSendQueue.remove(packetID)
            del self.fileSendDict[packetID]
        # if sending queue is empty - remove all records about packets failed to send
        if len(self.fileSendQueue) == 0:
            del self.sendFailedPacketIDs[:]
        # remember results
        result = max(len(packetsToRemove), packetsSent)
        # erase temp lists    
        del packetsFialed
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
        self.sendTask = reactor.callLater(self.sendTaskDelay, self.SendingTask)
        
    
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
            reactor.callLater(0, self.SendingTask)
            

    def FileSendAck(self, newpacket, info):    
        if self.shutdown: 
            lg.out(10, "io_throttle.FileSendAck finishing to %s, shutdown is True" % self.remoteName)
            return
        self.ackedCount += 1
        if newpacket.PacketID not in self.fileSendQueue:
            lg.warn("packet %s not in sending queue for %s" % (newpacket.PacketID, self.remoteName))
            return
        if newpacket.PacketID not in self.fileSendDict.keys():
            lg.warn("packet %s not in sending dict for %s" % (newpacket.PacketID, self.remoteName))
            return
        self.fileSendDict[newpacket.PacketID].ackTime = time.time()
        if newpacket.Command == commands.Ack():
            self.fileSendDict[newpacket.PacketID].result = 'acked'
            if self.fileSendDict[newpacket.PacketID].callOnAck:
                reactor.callLater(0, self.fileSendDict[newpacket.PacketID].callOnAck, newpacket, newpacket.OwnerID, newpacket.PacketID)
        elif newpacket.Command == commands.Fail():
            self.fileSendDict[newpacket.PacketID].result = 'failed'
            if self.fileSendDict[newpacket.PacketID].callOnFail:
                reactor.callLater(0, self.fileSendDict[newpacket.PacketID].callOnFail, newpacket.CreatorID, newpacket.PacketID, 'failed')
        sc = supplier_connector.by_idurl(newpacket.OwnerID)
        if sc:
            if newpacket.Command == commands.Ack():
                sc.automat('ack', newpacket)
            elif newpacket.Command == commands.Fail():
                sc.automat('fail', newpacket)
            elif newpacket.Command == commands.Data():
                sc.automat('data', newpacket)
            else:
                raise Exception('incorrect packet type received')
        self.DoSend()
        # self.RunSend()
        lg.out(14, "io_throttle.FileSendAck %s from %s, queue=%d" % (
            str(newpacket), self.remoteName, len(self.fileSendQueue)))

        
    def FileSendFailed(self, RemoteID, PacketID, why):
        if self.shutdown: 
            lg.out(10, "io_throttle.FileSendFailed finishing to %s, shutdown is True" % self.remoteName)
            return
        self.failedCount += 1
        if PacketID not in self.fileSendDict.keys():
            lg.warn("packet %s not in send dict" % PacketID)
            return
        self.fileSendDict[PacketID].result = why
        fileToSend = self.fileSendDict[PacketID]
        assert fileToSend.remoteID == RemoteID
        # transport_control.RemoveSupplierRequestFromSendQueue(fileToSend.packetID, fileToSend.remoteID, commands.Data())
        # queue.remove_supplier_request(fileToSend.packetID, fileToSend.remoteID, commands.Data())
        # transport_control.RemoveInterest(fileToSend.remoteID, fileToSend.packetID)
        # callback.remove_interest(fileToSend.remoteID, fileToSend.packetID)
        if why == 'timeout':
            contact_status.PacketSendingTimeout(RemoteID, PacketID)
        if fileToSend.callOnFail:
            reactor.callLater(0, fileToSend.callOnFail, RemoteID, PacketID, why)
        self.DoSend()
        # self.RunSend()
        lg.out(10, "io_throttle.FileSendFailed %s to [%s] because %s" % (PacketID, nameurl.GetName(fileToSend.remoteID), why))


    def SupplierRequestFile(self, callOnReceived, creatorID, packetID, ownerID):
        if self.shutdown: 
            lg.out(10, "io_throttle.SupplierRequestFile finishing to %s, shutdown is True" % self.remoteName)
            if callOnReceived:
                reactor.callLater(0, callOnReceived, packetID, 'shutdown')
            return False
        if packetID in self.fileRequestQueue:
            lg.warn("packet %s already in the queue for %s" % (packetID, self.remoteName))
            if callOnReceived:
                reactor.callLater(0, callOnReceived, packetID, 'in queue')
            return False
        self.fileRequestQueue.append(packetID)
        self.fileRequestDict[packetID] = FileToRequest(
            callOnReceived, creatorID, packetID, ownerID, self.remoteID)
        lg.out(10, "io_throttle.SupplierRequestFile for %s from %s, queue length is %d" % (packetID, self.remoteName, len(self.fileRequestQueue)))
        # reactor.callLater(0, self.DoRequest)
        self.DoRequest()
        return True


    def RunRequest(self):
        #out(6, 'io_throttle.RunRequest')
        packetsToRemove = set()
        for i in range(0, min(self.fileRequestMaxLength, len(self.fileRequestQueue))):
            packetID = self.fileRequestQueue[i]
            currentTime = time.time()
            if self.fileRequestDict[packetID].requestTime is not None:
                # the packet were requested
                if self.fileRequestDict[packetID].fileReceivedTime is None:
                    # but no answer yet ...
                    if currentTime - self.fileRequestDict[packetID].requestTime > self.fileRequestDict[packetID].requestTimeout:
                        # and time is out!!!
                        self.fileRequestDict[packetID].report = 'timeout' 
                        packetsToRemove.add(packetID)
                else:
                    # the packet were received (why it is not removed from the queue yet ???)
                    self.fileRequestDict[packetID].result = 'received'
                    packetsToRemove.add(packetID)
            if self.fileRequestDict[packetID].requestTime is None:
                if not os.path.exists(os.path.join(settings.getLocalBackupsDir(), packetID)): 
                    fileRequest = self.fileRequestDict[packetID]
                    lg.out(10, "io_throttle.RunRequest for packetID " + fileRequest.packetID)
                    # transport_control.RegisterInterest(self.DataReceived,fileRequest.creatorID,fileRequest.packetID)
                    # callback.register_interest(self.DataReceived, fileRequest.creatorID, fileRequest.packetID)
                    newpacket = signed.Packet(
                        commands.Retrieve(), 
                        fileRequest.ownerID, 
                        fileRequest.creatorID, 
                        fileRequest.packetID, 
                        "", 
                        fileRequest.remoteID)
                    # transport_control.outboxNoAck(newpacket)
                    gateway.outbox(newpacket, callbacks={
                        commands.Data(): self.DataReceived,
                        commands.Fail(): self.DataReceived})  
                    fileRequest.requestTime = time.time()
                else:
                    # we have the data file, no need to request it
                    self.fileRequestDict[packetID].result = 'exist'
                    packetsToRemove.add(packetID)
        # remember requests results
        result = len(packetsToRemove)
        # remove finished requests
        if len(packetsToRemove) > 0:
            for packetID in packetsToRemove:
                self.fileRequestQueue.remove(packetID)
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
        self.requestTask = reactor.callLater(self.requestTaskDelay, self.RequestTask)
        
    
    def DoRequest(self):
        #out(6, 'io_throttle.DoRequest')
        if self.requestTask is None:
            self.RequestTask()
        else:
            if self.requestTaskDelay > 1.0:
                self.requestTask.cancel()
                self.requestTask = None
                self.RequestTask()


    def DataReceived(self, newpacket, info):   
        # we requested some data from a supplier, just received it
        if self.shutdown: 
            # if we're closing down this queue (supplier replaced, don't any anything new)
            return
        if newpacket.PacketID in self.fileRequestQueue:
            self.fileRequestQueue.remove(newpacket.PacketID)
        if newpacket.Command == commands.Data():
            if self.fileRequestDict.has_key(newpacket.PacketID):
                self.fileRequestDict[newpacket.PacketID].fileReceivedTime = time.time()
                self.fileRequestDict[newpacket.PacketID].result = 'received'
                for callBack in self.fileRequestDict[newpacket.PacketID].callOnReceived:
                    callBack(newpacket, 'received')
        elif newpacket.Command == commands.Fail():
            if self.fileRequestDict.has_key(newpacket.PacketID):
                self.fileRequestDict[newpacket.PacketID].fileReceivedTime = time.time()
                self.fileRequestDict[newpacket.PacketID].result = 'failed'
                for callBack in self.fileRequestDict[newpacket.PacketID].callOnReceived:
                    callBack(newpacket, 'failed')
        else:
            raise Exception('incorrect response command')    
        if self.fileRequestDict.has_key(newpacket.PacketID):
            del self.fileRequestDict[newpacket.PacketID]
        lg.out(10, "io_throttle.DataReceived %s from %s, queue=%d" % (
            newpacket, self.remoteName, len(self.fileRequestQueue)))
        self.DoRequest()


    def DeleteBackupSendings(self, backupName):
        if self.shutdown: 
            # if we're closing down this queue 
            # (supplier replaced, don't any anything new)
            return
        packetsToRemove = set()
        for packetID in self.fileSendQueue:
            if packetID.count(backupName):
                self.FileSendFailed(self.fileSendDict[packetID].remoteID, packetID, 'delete request')
                packetsToRemove.add(packetID)
                lg.out(12, 'io_throttle.DeleteBackupSendings %s from send queue' % packetID)
        for packetID in packetsToRemove:
            self.fileSendQueue.remove(packetID)
            del self.fileSendDict[packetID]
        if len(self.fileSendQueue) > 0:
            reactor.callLater(0, self.DoSend)
            #self.DoSend()


    def DeleteBackupRequests(self, backupName):
        if self.shutdown: 
            # if we're closing down this queue 
            # (supplier replaced, don't any anything new)
            return
        packetsToRemove = set()
        for packetID in self.fileRequestQueue:
            if packetID.count(backupName):
                packetsToRemove.add(packetID)
                lg.out(12, 'io_throttle.DeleteBackupRequests %s from request queue' % packetID)
        for packetID in packetsToRemove:
            self.fileRequestQueue.remove(packetID)
            del self.fileRequestDict[packetID]
        if len(self.fileRequestQueue) > 0:
            reactor.callLater(0, self.DoRequest)


    def OutboxStatus(self, pkt_out, status, error):
        packetID = pkt_out.outpacket.PacketID
        if status != 'finished' and packetID in self.fileSendQueue:
            self.sendFailedPacketIDs.append(packetID)
            # reactor.callLater(0, self.DoSend)
            self.DoSend()
            

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

# all of the backup rebuilds will run their data requests through this 
# so it gets throttled, also to reduce duplicate requests
class IOThrottle:
    def __init__(self):
        self.creatorID = misc.getLocalID()
        self.supplierQueues = {} #
        self.paintFunc = None
        

    def SetSupplierQueueCallbackFunc(self, func):
        self.paintFunc = func


    def DeleteSuppliers(self, suppliers_IDURLs):
        for supplierIDURL in suppliers_IDURLs:
            if supplierIDURL:
                if self.supplierQueues.has_key(supplierIDURL):
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
            lg.out(2, "io_throttle.QueueSendFile ERROR %s not exist" % fileName)
            if callOnFail is not None:
                reactor.callLater(.01, callOnFail, remoteID, packetID, 'not exist')
            return False
        if remoteID not in self.supplierQueues.keys():
            self.supplierQueues[remoteID] = SupplierQueue(remoteID, self.creatorID)
            lg.out(6, "io_throttle.QueueSendFile made a new queue for %s" % nameurl.GetName(remoteID))
        return self.supplierQueues[remoteID].SupplierSendFile(
                   fileName, packetID, ownerID, callOnAck, callOnFail,)
            
            
    # return result in the callback: callOnReceived(packet or packetID, state)
    # state is: received, exist, in queue, shutdown
    def QueueRequestFile(self, callOnReceived, creatorID, packetID, ownerID, remoteID):
        # make sure that we don't actually already have the file
        #if packetID != settings.BackupInfoFileName():
        if packetID not in [ settings.BackupInfoFileName(), settings.BackupInfoFileNameOld(), settings.BackupInfoEncryptedFileName(), ]:
            filename = os.path.join(settings.getLocalBackupsDir(), packetID)
            if os.path.exists(filename):
                lg.warn("%s already exist " % filename)
                if callOnReceived:
                    reactor.callLater(0, callOnReceived, packetID, 'exist')
                return False
        if remoteID not in self.supplierQueues.keys():
            # made a new queue for this man
            self.supplierQueues[remoteID] = SupplierQueue(remoteID, self.creatorID)
            lg.out(6, "io_throttle.QueueRequestFile made a new queue for %s" % nameurl.GetName(remoteID))
        # lg.out(10, "io_throttle.QueueRequestFile asking for %s from %s" % (packetID, nameurl.GetName(remoteID)))
        return self.supplierQueues[remoteID].SupplierRequestFile(
                   callOnReceived, creatorID, packetID, ownerID)


    def OutboxStatus(self, pkt_out, status, error):
        """
        Called from outside to notify about single file sending result.  
        """
        for supplierIdentity in self.supplierQueues.keys():
            self.supplierQueues[supplierIdentity].OutboxStatus(pkt_out, status, error)


    def IsSendingQueueEmpty(self):
        """
        Return True if all outgoing queues is empty, no sending at the moment.
        """
        for idurl in self.supplierQueues.keys():
            if self.supplierQueues[idurl].HasSendingFiles():
                return False
        return True
    
    
    def IsRequestQueueEmpty(self):
        """
        Return True if all incoming queues is empty, no requests at the moment.
        """
        for idurl in self.supplierQueues.keys():
            if not self.supplierQueues[idurl].HasRequestedFiles():
                return False
        return True
    
    
    def HasPacketInSendQueue(self, supplierIDURL, packetID):
        """
        Return True if that packet is found in the sending queue to given remote peer. 
        """
        if not self.supplierQueues.has_key(supplierIDURL):
            return False
        return self.supplierQueues[supplierIDURL].fileSendDict.has_key(packetID)


    def HasPacketInRequestQueue(self, supplierIDURL, packetID):
        """
        Return True if that packet is found in the request queue from given remote peer.
        """
        if not self.supplierQueues.has_key(supplierIDURL):
            return False
        return self.supplierQueues[supplierIDURL].fileRequestDict.has_key(packetID)
        
    
    def HasBackupIDInSendQueue(self, supplierIDURL, backupID):
        """
        Same to ``HasPacketInSendQueue()``, but looks for packets for the whole backup, 
        not just a single packet .
        """
        if not self.supplierQueues.has_key(supplierIDURL):
            return False
        for packetID in self.supplierQueues[supplierIDURL].fileSendDict.keys():
            if packetID.startswith(backupID):
                return True
        return False
    
    
    def HasBackupIDInRequestQueue(self, supplierIDURL, backupID):
        """
        Same to ``HasPacketInRequestQueue()``, but looks for packets for the whole backup, 
        not just a single packet .
        """
        if not self.supplierQueues.has_key(supplierIDURL):
            return False
        for packetID in self.supplierQueues[supplierIDURL].fileRequestDict.keys():
            if packetID.startswith(backupID):
                return True
        return False
    
    
    def IsBackupSending(self, backupID):
        """
        Return True if some packets for given backup is found in the sending queues.  
        """
        for supplierIDURL in self.supplierQueues.keys():
            if self.HasBackupIDInSendQueue(supplierIDURL, backupID):
                return True 
        return False
        
        
    def IsBackupRequesting(self, backupID):
        """
        Return True if some packets for given backup is found in the request queues.  
        """
        for supplierIDURL in self.supplierQueues.keys():
            if self.HasBackupIDInRequestQueue(supplierIDURL, backupID):
                return True 
        return False

    
    def OkToSend(self, supplierIDURL):
        """
        The maximum size of any queue is limited, if this limit is not reached yet
        you can put more files to send to that remote user. 
        This method return True if you can put more outgoing files to that man in the ``throttle()``.
        """
        if not self.supplierQueues.has_key(supplierIDURL):
            # no queue opened to this man, so the queue is ready 
            return True
        return self.supplierQueues[supplierIDURL].OkToSend()
          
    
    def GetRequestQueueLength(self, supplierIDURL):
        """
        Return number of requested packets from given user.
        """
        if not self.supplierQueues.has_key(supplierIDURL):
            # no queue opened to this man, so length is zero 
            return 0
        return self.supplierQueues[supplierIDURL].GetRequestQueueLength()
        
 
    def GetSendQueueLength(self, supplierIDURL):
        """
        Return number of packets sent to this guy.
        """
        if not self.supplierQueues.has_key(supplierIDURL):
            # no queue opened to this man, so length is zero 
            return 0
        return self.supplierQueues[supplierIDURL].GetSendQueueLength()


