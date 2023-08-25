#!/usr/bin/env python
# file_down.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (file_down.py) is part of BitDust Software.
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

    <a href="https://bitdust.io/automats/customer/file_down.png" target="_blank">
    <img src="https://bitdust.io/automats/customer/file_down.png" style="max-width:100%;">
    </a>


.. module:: file_down
.. role:: red


BitDust file_down() Automat

EVENTS:
    * :red:`fail-received`
    * :red:`file-already-exists`
    * :red:`init`
    * :red:`request-failed`
    * :red:`retrieve-sent`
    * :red:`start`
    * :red:`stop`
    * :red:`valid-data-received`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 16

#------------------------------------------------------------------------------

import sys
import time

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in file_down.py')

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import utime
from bitdust.lib import packetid
from bitdust.lib import nameurl

from bitdust.userid import global_id

from bitdust.main import settings

from bitdust.p2p import p2p_service
from bitdust.p2p import commands

from bitdust.transport import packet_out

from bitdust.stream import io_throttle

#------------------------------------------------------------------------------


class FileDown(automat.Automat):
    """
    This class implements all the functionality of ``file_down()`` state machine.
    """
    def __init__(self, parent, callOnReceived, creatorID, packetID, ownerID, remoteID, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `file_down()` state machine.
        """
        self.parent = parent
        self.callOnReceived = []
        self.callOnReceived.append(callOnReceived)
        self.creatorID = creatorID
        self.packetID = global_id.CanonicalID(packetID)
        parts = global_id.NormalizeGlobalID(packetID)
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
        self.requestTimeout = max(30, 2*int(settings.getBackupBlockSize()/settings.SendingSpeedLimit()))
        self.result = ''
        self.created = utime.utcnow_to_sec1970()
        super(FileDown, self).__init__(
            name='file_down_%s_%s/%s/%s' % (nameurl.GetName(self.remoteID), remotePath, versionName, fileName), state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions,
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
            if event == 'file-already-exists':
                self.state = 'EXIST'
                self.doQueueRemove(*args, **kwargs)
                self.doReportExist(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'start':
                self.state = 'STARTED'
                self.doSendRetreive(*args, **kwargs)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doQueueRemove(*args, **kwargs)
                self.doReportStopped(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---STARTED---
        elif self.state == 'STARTED':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doCancelPackets(*args, **kwargs)
                self.doQueueRemove(*args, **kwargs)
                self.doReportStopped(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'request-failed':
                self.state = 'FAILED'
                self.doQueueRemove(*args, **kwargs)
                self.doReportFailed(event, *args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'retrieve-sent':
                self.state = 'REQUESTED'
        #---REQUESTED---
        elif self.state == 'REQUESTED':
            if event == 'valid-data-received':
                self.state = 'RECEIVED'
                self.doQueueRemove(*args, **kwargs)
                self.doReportReceived(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'fail-received':
                self.state = 'FAILED'
                self.doQueueRemove(*args, **kwargs)
                self.doReportFailed(event, *args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doCancelPackets(*args, **kwargs)
                self.doQueueRemove(*args, **kwargs)
                self.doReportStopped(*args, **kwargs)
                self.doQueueNext(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---EXIST---
        elif self.state == 'EXIST':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---STOPPED---
        elif self.state == 'STOPPED':
            pass
        #---RECEIVED---
        elif self.state == 'RECEIVED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        io_throttle.PacketReport('request', self.remoteID, self.packetID, 'init')

    def doQueueAppend(self, *args, **kwargs):
        """
        Action method.
        """
        if self.packetID in self.parent.fileRequestQueue:
            raise Exception('file %r already in downloading queue for %r' % (self.packetID, self.remoteID))
        if self.packetID in self.parent.fileRequestDict:
            raise Exception('file %r already in downloading dict for %r' % (self.packetID, self.remoteID))
        self.parent.fileRequestDict[self.packetID] = self
        self.parent.fileRequestQueue.append(self.packetID)

    def doQueueRemove(self, *args, **kwargs):
        """
        Action method.
        """
        if self.packetID not in self.parent.fileRequestDict:
            raise Exception('file %r not found in downloading dict for %r' % (self.packetID, self.remoteID))
        if self.packetID not in self.parent.fileRequestQueue:
            raise Exception('file %r not found in downloading queue for %r' % (self.packetID, self.remoteID))
        self.parent.fileRequestQueue.remove(self.packetID)
        del self.parent.fileRequestDict[self.packetID]

    def doSendRetreive(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, packetID=self.packetID, remoteID=self.remoteID)
        p2p_service.SendRetreive(
            self.ownerID,
            self.parent.creatorID,
            self.packetID,
            self.remoteID,
            callbacks={
                commands.Data(): self.parent.OnDataReceived,
                commands.Fail(): self.parent.OnDataReceived,
                # None: lambda pkt_out: self.OnDataReceived(fileRequest.packetID, 'timeout'),  # timeout
            },
            # response_timeout=10,
        )
        self.requestTime = time.time()

    def doCancelPackets(self, *args, **kwargs):
        """
        Action method.
        """
        packetsToCancel = packet_out.search_by_packet_id(self.packetID)
        for pkt_out in packetsToCancel:
            if pkt_out.outpacket.Command == commands.Retrieve():
                if _Debug:
                    lg.dbg(_DebugLevel, 'sending "cancel" to %s addressed to %s because downloading cancelled' % (pkt_out, pkt_out.remote_idurl))
                pkt_out.automat('cancel')

    def doQueueNext(self, *args, **kwargs):
        """
        Action method.
        """
        self.parent.DoRequest()

    def doReportExist(self, *args, **kwargs):
        """
        Action method.
        """
        for callBack in self.callOnReceived:
            reactor.callLater(0, callBack, self.packetID, 'exist')  # @UndefinedVariable

    def doReportStopped(self, *args, **kwargs):
        """
        Action method.
        """
        for callBack in self.callOnReceived:
            reactor.callLater(0, callBack, self.packetID, 'cancelled')  # @UndefinedVariable

    def doReportReceived(self, *args, **kwargs):
        """
        Action method.
        """
        self.fileReceivedTime = time.time()
        for callBack in self.callOnReceived:
            reactor.callLater(0, callBack, args[0], 'received')  # @UndefinedVariable

    def doReportFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        if event == 'fail-received':
            for callBack in self.callOnReceived:
                reactor.callLater(0, callBack, args[0], 'failed')  # @UndefinedVariable
        else:
            for callBack in self.callOnReceived:
                reactor.callLater(0, callBack, self.packetID, 'failed')  # @UndefinedVariable

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        io_throttle.PacketReport('request', self.remoteID, self.packetID, self.result)
        self.parent = None
        self.callOnReceived = None
        self.creatorID = None
        self.packetID = None
        self.customerID = None
        self.remotePath = None
        self.customerIDURL = None
        self.backupID = None
        self.fileName = None
        self.ownerID = None
        self.remoteID = None
        self.requestTime = None
        self.fileReceivedTime = None
        self.requestTimeout = None
        self.result = None
        self.created = None
        self.destroy()
