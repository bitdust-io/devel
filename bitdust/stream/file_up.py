#!/usr/bin/env python
# file_up.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (file_up.py) is part of BitDust Software.
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

.. raw:: html

    <a href="https://bitdust.io/automats/customer/file_up.png" target="_blank">
    <img src="https://bitdust.io/automats/customer/file_up.png" style="max-width:100%;">
    </a>


.. module:: file_up
.. role:: red


BitDust file_up() Automat

EVENTS:
    * :red:`ack-received`
    * :red:`data-sent`
    * :red:`error`
    * :red:`fail-received`
    * :red:`file-not-exist`
    * :red:`init`
    * :red:`sending-failed`
    * :red:`start`
    * :red:`stop`
    * :red:`timeout`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 16

#------------------------------------------------------------------------------

import os
import sys
import time

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in file_up.py')

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import utime
from bitdust.lib import packetid
from bitdust.lib import nameurl

from bitdust.system import bpio

from bitdust.userid import global_id

from bitdust.main import settings

from bitdust.p2p import p2p_service
from bitdust.p2p import commands

from bitdust.transport import packet_out

from bitdust.stream import io_throttle

#------------------------------------------------------------------------------


class FileUp(automat.Automat):
    """
    This class implements all the functionality of ``file_up()`` state machine.
    """
    def __init__(self, parent, fileName, packetID, remoteID, ownerID, callOnAck=None, callOnFail=None, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `file_up()` state machine.
        """
        self.parent = parent
        self.fileName = fileName
        try:
            self.fileSize = os.path.getsize(os.path.abspath(fileName))
        except:
            lg.exc()
            self.fileSize = 0
        self.packetID = global_id.CanonicalID(packetID)
        parts = global_id.NormalizeGlobalID(packetID)
        self.customerID = parts['customer']
        self.remotePath = parts['path']
        self.customerIDURL = parts['idurl']
        customerGlobalID, remotePath, versionName, fileName = packetid.SplitVersionFilename(packetID)
        self.backupID = packetid.MakeBackupID(customerGlobalID, remotePath, versionName)
        self.remoteID = remoteID
        self.ownerID = ownerID
        self.callOnAck = callOnAck
        self.callOnFail = callOnFail
        self.sendTime = None
        self.ackTime = None
        self.sendTimeout = 10*2*(max(int(self.fileSize/settings.SendingSpeedLimit()), 5) + 5)  # maximum 5 seconds to get an Ack
        self.result = ''
        self.created = utime.utcnow_to_sec1970()
        super(FileUp, self).__init__(
            name='file_up_%s_%s/%s/%s' % (nameurl.GetName(self.remoteID), remotePath, versionName, fileName), state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions,
            publish_events=publish_events, **kwargs
        )

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'IN_QUEUE'
                self.doInit(*args, **kwargs)
                self.doQueueAppend(*args, **kwargs)
        #---IN_QUEUE---
        elif self.state == 'IN_QUEUE':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doQueueRemove(*args, **kwargs)
                self.doReportStopped(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'start':
                self.state = 'UPLOADING'
                self.doSendData(*args, **kwargs)
            elif event == 'file-not-exist':
                self.state = 'NO_FILE'
                self.doCancelPackets(*args, **kwargs)
                self.doQueueRemove(*args, **kwargs)
                self.doReportFailed(event, *args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---UPLOADING---
        elif self.state == 'UPLOADING':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doCancelPackets(*args, **kwargs)
                self.doQueueRemove(*args, **kwargs)
                self.doReportStopped(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-received':
                self.state = 'DELIVERED'
                self.doQueueRemove(*args, **kwargs)
                self.doReportDelivered(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timeout' or event == 'fail-received' or event == 'error' or event == 'sending-failed':
                self.state = 'FAILED'
                self.doCancelPackets(*args, **kwargs)
                self.doQueueRemove(*args, **kwargs)
                self.doReportFailed(event, *args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'data-sent':
                self.state = 'ACK?'
        #---DELIVERED---
        elif self.state == 'DELIVERED':
            pass
        #---STOPPED---
        elif self.state == 'STOPPED':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---NO_FILE---
        elif self.state == 'NO_FILE':
            pass
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doCancelPackets(*args, **kwargs)
                self.doQueueRemove(*args, **kwargs)
                self.doReportStopped(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-received':
                self.state = 'DELIVERED'
                self.doQueueRemove(*args, **kwargs)
                self.doReportDelivered(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'error' or event == 'timeout' or event == 'fail-received' or event == 'sending-failed':
                self.state = 'FAILED'
                self.doCancelPackets(*args, **kwargs)
                self.doQueueRemove(*args, **kwargs)
                self.doReportFailed(event, *args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        io_throttle.PacketReport('send', self.remoteID, self.packetID, 'init')

    def doQueueAppend(self, *args, **kwargs):
        """
        Action method.
        """
        if self.packetID in self.parent.fileSendQueue:
            raise Exception('file %r already in uploading queue for %r' % (self.packetID, self.remoteID))
        if self.packetID in self.parent.fileSendDict:
            raise Exception('file %r already in uploading dict for %r' % (self.packetID, self.remoteID))
        self.parent.fileSendQueue.append(self.packetID)
        self.parent.fileSendDict[self.packetID] = self

    def doQueueRemove(self, *args, **kwargs):
        """
        Action method.
        """
        if self.packetID not in self.parent.fileSendDict:
            raise Exception('file %r not found in uploading dict for %r' % (self.packetID, self.remoteID))
        if self.packetID not in self.parent.fileSendQueue:
            raise Exception('file %r not found in uploading queue for %r' % (self.packetID, self.remoteID))
        self.parent.fileSendQueue.remove(self.packetID)
        del self.parent.fileSendDict[self.packetID]

    def doSendData(self, *args, **kwargs):
        """
        Action method.
        """
        payload = bpio.ReadBinaryFile(self.fileName)
        if not payload:
            self.event('error', Exception('file %r reading error' % self.fileName))
            return
        p2p_service.SendData(
            raw_data=payload,
            ownerID=self.ownerID,
            creatorID=self.parent.creatorID,
            remoteID=self.remoteID,
            packetID=self.packetID,
            callbacks={
                commands.Ack(): self.parent.OnFileSendAckReceived,
                commands.Fail(): self.parent.OnFileSendAckReceived,
            },
        )
        self.sendTime = time.time()

    def doCancelPackets(self, *args, **kwargs):
        """
        Action method.
        """
        packetsToCancel = packet_out.search_by_packet_id(self.packetID)
        for pkt_out in packetsToCancel:
            if pkt_out.outpacket.Command == commands.Data():
                if _Debug:
                    lg.dbg(_DebugLevel, 'sending "cancel" to %s addressed to %s because downloading cancelled' % (pkt_out, pkt_out.remote_idurl))
                pkt_out.automat('cancel')

    def doQueueNext(self, *args, **kwargs):
        """
        Action method.
        """
        self.parent.DoSend()

    def doReportDelivered(self, *args, **kwargs):
        """
        Action method.
        """
        self.ackTime = time.time()
        self.parent.uploadingTimeoutCount = 0
        if self.callOnAck:
            newpacket = args[0]
            reactor.callLater(0, self.callOnAck, newpacket, newpacket.OwnerID, self.packetID)  # @UndefinedVariable

    def doReportStopped(self, *args, **kwargs):
        """
        Action method.
        """
        if self.callOnFail:
            reactor.callLater(0, self.callOnFail, self.remoteID, self.packetID, 'failed')  # @UndefinedVariable

    def doReportFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        if event == 'fail-received':
            if self.callOnFail:
                reactor.callLater(0, self.callOnFail, self.remoteID, self.packetID, 'failed')  # @UndefinedVariable
        elif event == 'timeout':
            self.parent.uploadingTimeoutCount += 1
            if self.callOnFail:
                reactor.callLater(0, self.callOnFail, self.remoteID, self.packetID, 'timeout')  # @UndefinedVariable
        elif event == 'sending-failed':
            if self.callOnFail:
                reactor.callLater(0, self.callOnFail, self.remoteID, self.packetID, 'failed')  # @UndefinedVariable
        else:
            if self.callOnFail:
                reactor.callLater(0, self.callOnFail, self.remoteID, self.packetID, 'failed')  # @UndefinedVariable

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        io_throttle.PacketReport('send', self.remoteID, self.packetID, self.result)
        self.parent = None
        self.fileName = None
        self.fileSize = None
        self.packetID = None
        self.customerID = None
        self.remotePath = None
        self.customerIDURL = None
        self.backupID = None
        self.remoteID = None
        self.ownerID = None
        self.callOnAck = None
        self.callOnFail = None
        self.sendTime = None
        self.ackTime = None
        self.sendTimeout = None
        self.result = None
        self.created = None
        self.destroy()
