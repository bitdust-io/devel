#!/usr/bin/env python
# group_access_donor.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (group_access_donor.py) is part of BitDust Software.
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


"""
.. module:: group_access_donor
.. role:: red

BitDust group_access_donor() Automat

EVENTS:
    * :red:`audit-ok`
    * :red:`fail`
    * :red:`handshake-ok`
    * :red:`init`
    * :red:`private-key-shared`
    * :red:`timer-15sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import strng

from main import events

from dht import dht_relations

from userid import global_id
from userid import id_url

from p2p import commands
from p2p import p2p_service

from contacts import identitycache

from crypt import my_keys

from access import key_ring

from storage import backup_fs

from customer import supplier_connector

#------------------------------------------------------------------------------

class GroupAccessDonor(automat.Automat):
    """
    This class implements all the functionality of ``group_access_donor()`` state machine.
    """

    timers = {
        'timer-15sec': (15.0, ['PRIV_KEY', 'AUDIT']),
    }

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `group_access_donor()` state machine.
        """
        super(GroupAccessDonor, self).__init__(
            name="group_access_donor",
            state="AT_STARTUP",
            debug_level=debug_level or _DebugLevel,
            log_events=log_events or _Debug,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `group_access_donor()` machine.
        """
        self.log_transitions = _Debug
        self.group_key_id = None

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `group_access_donor()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `group_access_donor()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'HANDSHAKE!'
                self.doInit(*args, **kwargs)
                self.doHandshake(*args, **kwargs)
        #---HANDSHAKE!---
        elif self.state == 'HANDSHAKE!':
            if event == 'handshake-ok':
                self.state = 'AUDIT'
                self.doAuditUserMasterKey(*args, **kwargs)
            elif event == 'fail':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---AUDIT---
        elif self.state == 'AUDIT':
            if event == 'fail' or event == 'timer-15sec':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'audit-ok':
                self.state = 'PRIV_KEY'
                self.doSendPrivKeyToUser(*args, **kwargs)
        #---PRIV_KEY---
        elif self.state == 'PRIV_KEY':
            if event == 'fail' or event == 'timer-15sec':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'private-key-shared':
                self.state = 'SUCCESS'
                self.doReportDone(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---SUCCESS---
        elif self.state == 'SUCCESS':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass


    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doHandshake(self, *args, **kwargs):
        """
        Action method.
        """

    def doAuditUserMasterKey(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendPrivKeyToUser(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

