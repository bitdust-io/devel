#!/usr/bin/env python
# installer.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (installer.py) is part of BitDust Software.
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
.. module:: installer.

.. role:: red

.. raw:: html

    <a href="https://bitdust.io/automats/installer/installer.png" target="_blank">
    <img src="https://bitdust.io/automats/installer/installer.png" style="max-width:100%;">
    </a>

The ``installer()`` machine is a sort of installation wizard
which is executed when user first time executes BitDust software.

It have two directions:

    1) ``register a new user`` and
    2) ``recover existing user account``

A ``id_registrator()`` and ``id_restorer()`` automats is called from here
and ``installer()`` will wait until they are finished.


EVENTS:
    * :red:`back`
    * :red:`id_registrator.state`
    * :red:`id_restorer.state`
    * :red:`init`
    * :red:`install_wizard.state`
    * :red:`load-from-file`
    * :red:`next`
    * :red:`paste-from-clipboard`
    * :red:`print`
    * :red:`recover-cmd-line`
    * :red:`recover-selected`
    * :red:`register-cmd-line`
    * :red:`register-selected`
    * :red:`register-start`
    * :red:`restore-start`
"""

#------------------------------------------------------------------------------

import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in installer.py')

#------------------------------------------------------------------------------

from logs import lg

from automats import automat
from automats import global_state

from system import bpio

from main import settings

from lib import misc
from lib import nameurl

from userid import id_registrator
from userid import id_restorer

from main import initializer

#------------------------------------------------------------------------------

_Installer = None

#------------------------------------------------------------------------------


def IsExist():
    """
    """
    global _Installer
    return _Installer is not None

#------------------------------------------------------------------------------


def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _Installer
    if _Installer is None:
        _Installer = Installer('installer', 'AT_STARTUP', 2, True)
    if event is not None:
        _Installer.automat(event, arg)
    return _Installer


class Installer(automat.Automat):
    """
    A class to control the whole process of program installation.
    """

    fast = True

    output = {}
    RECOVER_RESULTS = {
        'remote_identity_not_valid': ('remote Identity is not valid', 'red'),
        'invalid_identity_source': ('incorrect source of the Identity file', 'red'),
        'invalid_identity_url': ('incorrect Identity file location', 'red'),
        'remote_identity_bad_format': ('incorrect format of the Identity file', 'red'),
        'incorrect_key': ('Private Key is not valid', 'red'),
        'idurl_not_exist': ('Identity URL address not exist or not reachable at this moment', 'blue'),
        'signing_error': ('unable to sign the local Identity file', 'red'),
        'signature_not_match': ('remote Identity and Private Key did not match', 'red'),
        'success': ('account restored!', 'green'), }

    def getOutput(self, state=None):
        if state is None:
            state = self.state
        return self.output.get(state, {})

    def init(self):
        self.log_events = True
        self.flagCmdLine = False

    def state_changed(self, oldstate, newstate, event, arg):
        global_state.set_global_state('INSTALL ' + newstate)
        initializer.A('installer.state', newstate)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'WHAT_TO_DO?'
                self.flagCmdLine=False
            elif event == 'register-cmd-line':
                self.state = 'REGISTER'
                self.flagCmdLine=True
                self.doInit(arg)
                id_registrator.A('start', arg)
            elif event == 'recover-cmd-line':
                self.state = 'RECOVER'
                self.flagCmdLine=True
                self.doInit(arg)
                id_restorer.A('start', arg)
        #---WHAT_TO_DO?---
        elif self.state == 'WHAT_TO_DO?':
            if event == 'register-selected':
                self.state = 'INPUT_NAME'
                self.doUpdate(arg)
            elif event == 'recover-selected':
                self.state = 'LOAD_KEY'
                self.doUpdate(arg)
        #---INPUT_NAME---
        elif self.state == 'INPUT_NAME':
            if event == 'back':
                self.state = 'WHAT_TO_DO?'
                self.doClearOutput(arg)
                self.doUpdate(arg)
            elif event == 'register-start' and self.isNameValid(arg):
                self.state = 'REGISTER'
                self.doClearOutput(arg)
                self.doSaveName(arg)
                id_registrator.A('start', arg)
                self.doUpdate(arg)
            elif event == 'register-start' and not self.isNameValid(arg):
                self.doClearOutput(arg)
                self.doPrintIncorrectName(arg)
                self.doUpdate(arg)
            elif event == 'print':
                self.doPrint(arg)
                self.doUpdate(arg)
        #---LOAD_KEY---
        elif self.state == 'LOAD_KEY':
            if event == 'back':
                self.state = 'WHAT_TO_DO?'
                self.doClearOutput(arg)
                self.doUpdate(arg)
            elif event == 'load-from-file':
                self.doReadKey(arg)
                self.doUpdate(arg)
            elif event == 'paste-from-clipboard':
                self.doPasteKey(arg)
                self.doUpdate(arg)
            elif event == 'restore-start':
                self.state = 'RECOVER'
                self.doClearOutput(arg)
                id_restorer.A('start', arg)
                self.doUpdate(arg)
            elif event == 'print':
                self.doPrint(arg)
                self.doUpdate(arg)
        #---REGISTER---
        elif self.state == 'REGISTER':
            if event == 'print':
                self.doPrint(arg)
                self.doUpdate(arg)
            elif ( event == 'id_registrator.state' and arg == 'FAILED' ) and not self.flagCmdLine:
                self.state = 'INPUT_NAME'
                self.doShowOutput(arg)
                self.doUpdate(arg)
            elif ( event == 'id_registrator.state' and arg == 'DONE' ) and not self.flagCmdLine:
                self.state = 'AUTHORIZED'
                self.doPrepareSettings(arg)
                self.doUpdate(arg)
            elif ( event == 'id_registrator.state' and arg in [ 'DONE' , 'FAILED' ] ) and self.flagCmdLine:
                self.state = 'DONE'
                self.doUpdate(arg)
        #---AUTHORIZED---
        elif self.state == 'AUTHORIZED':
            if event == 'next':
                self.state = 'WIZARD'
                self.doUpdate(arg)
            elif event == 'print':
                self.doPrint(arg)
                self.doUpdate(arg)
        #---RECOVER---
        elif self.state == 'RECOVER':
            if event == 'print':
                self.doPrint(arg)
                self.doUpdate(arg)
            elif ( event == 'id_restorer.state' and arg in [ 'RESTORED!' , 'FAILED' ] ) and self.flagCmdLine:
                self.state = 'DONE'
                self.doUpdate(arg)
            elif ( event == 'id_restorer.state' and arg == 'RESTORED!' ) and not self.flagCmdLine:
                self.state = 'RESTORED'
                self.doRestoreSettings(arg)
                self.doUpdate(arg)
            elif ( event == 'id_restorer.state' and arg == 'FAILED' ) and not self.flagCmdLine:
                self.state = 'LOAD_KEY'
                self.doUpdate(arg)
        #---DONE---
        elif self.state == 'DONE':
            if event == 'print':
                self.doPrint(arg)
                self.doUpdate(arg)
        #---WIZARD---
        elif self.state == 'WIZARD':
            if event == 'print':
                self.doPrint(arg)
                self.doUpdate(arg)
            elif ( event == 'install_wizard.state' and arg == 'DONE' ):
                self.state = 'DONE'
                self.doUpdate(arg)
        #---RESTORED---
        elif self.state == 'RESTORED':
            if event == 'print':
                self.doPrint(arg)
                self.doUpdate(arg)
            elif event == 'next':
                self.state = 'WIZARD'
                self.doUpdate(arg)
        return None

    def isNameValid(self, arg):
        if not misc.ValidUserName(arg['username']):
            return False
        return True

    def doInit(self, arg):
        """
        Action method.
        """

    def doUpdate(self, arg):
        # lg.out(4, 'installer.doUpdate')
        from main import control
        control.request_update([{'state': self.state}, ])

    def doClearOutput(self, arg):
        # lg.out(4, 'installer.doClearOutput')
        for state in self.output.keys():
            self.output[state] = {'data': [('', 'black')]}

    def doPrint(self, arg):
        lg.out(8, 'installer.doPrint %s %s' % (self.state, str(arg)))
        if self.state not in self.output:
            self.output[self.state] = {'data': [('', 'black')]}
        if arg is None:
            self.output[self.state]['data'] = [('', 'black')]
        else:
            self.output[self.state]['data'].append(arg)
        if self.flagCmdLine:
            ch = '+'
            if arg[1] == 'red':
                ch = '!'
            lg.out(0, '  %s %s' % (ch, arg[0]))

    def doShowOutput(self, arg):
        """
        Action method.
        """
        if 'INPUT_NAME' not in self.output:
            self.output['INPUT_NAME'] = {'data': [('', 'black')]}
        self.output['INPUT_NAME']['data'] = self.output['REGISTER']['data']

    def doPrintIncorrectName(self, arg):
        text, color = ('incorrect user name', 'red')
        if self.state not in self.output:
            self.output[self.state] = {'data': [('', 'black')]}
        self.output[self.state]['data'].append((text, color))
        # lg.out(0, '  [%s]' % text)

    def doSaveName(self, arg):
        settings.setPrivateKeySize(arg['pksize'])
        bpio.WriteFile(settings.UserNameFilename(), arg['username'])

    def doReadKey(self, arg):
        # keyfn = arg['keyfilename']
        src = arg['keysrc']
        lg.out(2, 'installer.doReadKey length=%s' % len(src))
        # src = bpio.ReadBinaryFile(keyfn)
        if len(src) > 1024 * 10:
            self.doPrint(('file is too big for private key', 'red'))
            return
        try:
            lines = src.splitlines()
            idurl = lines[0].strip()
            keysrc = '\n'.join(lines[1:])
            if idurl != nameurl.FilenameUrl(nameurl.UrlFilename(idurl)):
                idurl = ''
                keysrc = src
        except:
            lg.exc()
            idurl = ''
            keysrc = src
        if self.state not in self.output:
            self.output[self.state] = {'data': [('', 'black')]}
        self.output[self.state] = {'data': [('', 'black')]}
        self.output[self.state]['idurl'] = idurl
        self.output[self.state]['keysrc'] = keysrc
        if 'RECOVER' not in self.output:
            self.output['RECOVER'] = {'data': [('', 'black')]}
        if keysrc and idurl:
            self.output['RECOVER']['data'].append(('private key and IDURL was loaded', 'green'))
        elif not idurl and keysrc:
            self.output['RECOVER']['data'].append(('private key was loaded, provide correct IDURL now', 'blue'))

    def doPasteKey(self, arg):
        src = misc.getClipboardText()
        try:
            lines = src.split('\n')
            idurl = lines[0]
            keysrc = '\n'.join(lines[1:])
            if idurl != nameurl.FilenameUrl(nameurl.UrlFilename(idurl)):
                idurl = ''
                keysrc = src
        except:
            lg.exc()
            idurl = ''
            keysrc = src
        if self.state not in self.output:
            self.output[self.state] = {'data': [('', 'black')]}
        self.output[self.state]['idurl'] = idurl
        self.output[self.state]['keysrc'] = keysrc
        if 'RECOVER' not in self.output:
            self.output['RECOVER'] = {'data': [('', 'black')]}
        if keysrc and idurl:
            self.output['RECOVER']['data'].append(('private key and IDURL was loaded', 'green'))
        elif not idurl and keysrc:
            self.output['RECOVER']['data'].append(('private key was loaded, provide correct IDURL now', 'blue'))

    def doPrepareSettings(self, arg):
        """
        Action method.
        """

    def doRestoreSettings(self, arg):
        """
        Action method.
        """

#    def doIncreaseDebugLevel(self, arg):
#        """
#        """
#        if self.flagCmdLine and not lg.is_debug(10):
#            lg.set_debug_level(0)
#        else:
#            lg.set_debug_level(18)
