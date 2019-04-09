#!/usr/bin/env python
# list_files_orator.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (list_files_orator.py) is part of BitDust Software.
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
#

"""
.. module:: list_files_orator.

.. raw:: html

    <a href="https://bitdust.io/automats/list_files_orator/list_files_orator.png" target="_blank">
    <img src="https://bitdust.io/automats/list_files_orator/list_files_orator.png" style="max-width:100%;">
    </a>

This simple state machine requests a list of files stored on remote machines.

Before that, it scans the local backup folder and prepare an index of existing data pieces.


EVENTS:
    * :red:`inbox-files`
    * :red:`init`
    * :red:`local-files-done`
    * :red:`need-files`
    * :red:`timer-10sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from twisted.internet.defer import maybeDeferred

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from contacts import contactsdb

from main import events

from services import driver

from p2p import p2p_service
from p2p import online_status
from p2p import p2p_connector

#------------------------------------------------------------------------------

_ListFilesOrator = None
_RequestedListFilesPacketIDs = set()
_RequestedListFilesCounter = 0

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _ListFilesOrator
    if _ListFilesOrator is None:
        _ListFilesOrator = ListFilesOrator('list_files_orator', 'NO_FILES', 4)
    if event is not None:
        _ListFilesOrator.automat(event, *args, **kwargs)
    return _ListFilesOrator


def Destroy():
    """
    Destroy list_files_orator() automat and remove its instance from memory.
    """
    global _ListFilesOrator
    if _ListFilesOrator is None:
        return
    _ListFilesOrator.destroy()
    del _ListFilesOrator
    _ListFilesOrator = None


class ListFilesOrator(automat.Automat):
    """
    A class to request list of my files from my suppliers and also scan the
    local files.
    """

    timers = {
        'timer-10sec': (10.0, ['REMOTE_FILES']),
    }

    def init(self):
        self.log_transitions = True

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        if driver.is_on('service_backups'):
            # TODO: rebuild using "list-files-orator-state-changed" event
            from storage import backup_monitor
            backup_monitor.A('list_files_orator.state', newstate)
        if newstate == 'SAW_FILES' and oldstate != newstate:
            events.send('my-list-files-refreshed', data={})

    def A(self, event, *args, **kwargs):
        #---NO_FILES---
        if self.state == 'NO_FILES':
            if event == 'need-files':
                self.state = 'LOCAL_FILES'
                self.doReadLocalFiles(*args, **kwargs)
            elif event == 'init':
                pass
        #---LOCAL_FILES---
        elif self.state == 'LOCAL_FILES':
            if event == 'local-files-done' and p2p_connector.A().state is 'CONNECTED':
                self.state = 'REMOTE_FILES'
                self.doRequestRemoteFiles(*args, **kwargs)
            elif event == 'local-files-done' and p2p_connector.A().state is not 'CONNECTED':
                self.state = 'NO_FILES'
        #---REMOTE_FILES---
        elif self.state == 'REMOTE_FILES':
            if (event == 'timer-10sec' and self.isSomeListFilesReceived(*args, **kwargs)) or (event == 'inbox-files' and self.isAllListFilesReceived(*args, **kwargs)):
                self.state = 'SAW_FILES'
            elif event == 'timer-10sec' and not self.isSomeListFilesReceived(*args, **kwargs):
                self.state = 'NO_FILES'
        #---SAW_FILES---
        elif self.state == 'SAW_FILES':
            if event == 'need-files':
                self.state = 'LOCAL_FILES'
                self.doReadLocalFiles(*args, **kwargs)
        return None

    def isAllListFilesReceived(self, *args, **kwargs):
        global _RequestedListFilesPacketIDs
        lg.out(6, 'list_files_orator.isAllListFilesReceived need %d more' % len(_RequestedListFilesPacketIDs))
        return len(_RequestedListFilesPacketIDs) == 0

    def isSomeListFilesReceived(self, *args, **kwargs):
        global _RequestedListFilesCounter
        lg.out(6, 'list_files_orator.isSomeListFilesReceived %d list files was received' % _RequestedListFilesCounter)
        return _RequestedListFilesCounter > 0

    def doReadLocalFiles(self, *args, **kwargs):
        from storage import backup_matrix
        maybeDeferred(backup_matrix.ReadLocalFiles).addBoth(
            lambda x: self.automat('local-files-done'))

    def doRequestRemoteFiles(self, *args, **kwargs):
        global _RequestedListFilesCounter
        global _RequestedListFilesPacketIDs
        _RequestedListFilesCounter = 0
        _RequestedListFilesPacketIDs.clear()
        for idurl in contactsdb.suppliers():
            if idurl:
                if online_status.isOnline(idurl):
                    lg.out(6, 'list_files_orator.doRequestRemoteFiles from my supplier %s' % idurl)
                    p2p_service.SendListFiles(target_supplier=idurl)
                    _RequestedListFilesPacketIDs.add(idurl)
                else:
                    lg.out(6, 'list_files_orator.doRequestRemoteFiles SKIP %s is not online' % idurl)

#------------------------------------------------------------------------------


def IncomingListFiles(newpacket):
    """
    Called from ``p2p.backup_control`` to pass incoming "ListFiles" packet
    here.
    """
    global _RequestedListFilesPacketIDs
    global _RequestedListFilesCounter
    _RequestedListFilesCounter += 1
    _RequestedListFilesPacketIDs.discard(newpacket.OwnerID)
    A('inbox-files', newpacket)
