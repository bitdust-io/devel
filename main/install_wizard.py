#!/usr/bin/env python
# install_wizard.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (install_wizard.py) is part of BitDust Software.
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
.. module:: install_wizard.

.. raw:: html

    <a href="https://bitdust.io/automats/install_wizard/install_wizard.png" target="_blank">
    <img src="https://bitdust.io/automats/install_wizard/install_wizard.png" style="max-width:100%;">
    </a>

A state machine to show installation wizard for BitDust software.
User need to answer some questions step by step to configure the program first time.

This is several pages:
    * select a role: "free backups", "secure storage", "donator", "just to try", "beta tester"
    * set up needed and donated space and local folders locations
    * provide some personal information about yourself if you wish
    * set software update settings

EVENTS:
    * :red:`back`
    * :red:`next`
    * :red:`skip`
"""

from __future__ import absolute_import
import sys
try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in install_wizard.py')

from logs import lg

from lib import misc
from main import settings
from main import config
from automats import automat

from . import installer

#------------------------------------------------------------------------------

_InstallWizard = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _InstallWizard
    if _InstallWizard is None:
        _InstallWizard = InstallWizard('install_wizard', 'READY', 2)
    if event is not None:
        _InstallWizard.automat(event, *args, **kwargs)
    return _InstallWizard


class InstallWizard(automat.Automat):
    """
    BitDust install_wizard() Automat.

    Runs install wizard process.
    """

    fast = True

    role_args = None
    role = None

    def init(self):
        self.log_events = True
        # TODO: we do not need 'READY' state now
        # because only have one page "STORAGE"
        self.state = 'STORAGE'

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        if newstate == 'CONTACTS' and oldstate == 'STORAGE':
            self.event('next', {})
            # TODO:
            # here just skip Contacts page!
            # we do not need that now, but can back to that soon when add chat
        from main import control
        control.request_update()
        installer.A('install_wizard.state', newstate)

    def A(self, event, *args, **kwargs):
        #---READY---
        if self.state == 'READY':
            if event == 'next':
                self.state = 'STORAGE'
            elif event == 'skip':
                self.state = 'LAST_PAGE'
        #---STORAGE---
        elif self.state == 'STORAGE':
            if event == 'next':
                self.state = 'CONTACTS'
                self.doSaveStorage(*args, **kwargs)
            elif event == 'back':
                self.state = 'READY'
        #---CONTACTS---
        elif self.state == 'CONTACTS':
            if event == 'back':
                self.state = 'STORAGE'
            elif event == 'next':
                self.state = 'LAST_PAGE'
                self.doSaveContacts(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---LAST_PAGE---
        elif self.state == 'LAST_PAGE':
            if event == 'next':
                self.state = 'DONE'
            elif event == 'back':
                self.state = 'CONTACTS'
        return None

    def doSaveStorage(self, *args, **kwargs):
        needed = args[0].get('needed', '')
        donated = args[0].get('donated', '')
        customersdir = args[0].get('customersdir', '')
        localbackupsdir = args[0].get('localbackupsdir', '')
        restoredir = args[0].get('restoredir', '')
        if needed:
            config.conf().setData('services/customer/needed-space', needed + ' MB')
        if donated:
            config.conf().setData('services/supplier/donated-space', donated + ' MB')
        if customersdir:
            config.conf().setString('paths/customers', customersdir)
        if localbackupsdir:
            config.conf().setString('paths/backups', localbackupsdir)
        if restoredir:
            config.conf().setString('paths/restore', restoredir)

    def doSaveContacts(self, *args, **kwargs):
        config.conf().setData('personal/email', args[0].get('email', '').strip())
        config.conf().setData('personal/name', args[0].get('name', '').strip())
        config.conf().setData('personal/surname', args[0].get('surname', '').strip())
        config.conf().setData('personal/nickname', args[0].get('nickname', '').strip())
