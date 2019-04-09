#!/usr/bin/env python
# installer.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import
import sys

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
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


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _Installer
    if _Installer is None:
        _Installer = Installer('installer', 'AT_STARTUP', 2, True)
    if event is not None:
        _Installer.automat(event, *args, **kwargs)
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

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        global_state.set_global_state('INSTALL ' + newstate)
        initializer.A('installer.state', newstate)

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'WHAT_TO_DO?'
                self.flagCmdLine=False
            elif event == 'register-cmd-line':
                self.state = 'REGISTER'
                self.flagCmdLine=True
                self.doInit(*args, **kwargs)
                id_registrator.A('start', *args, **kwargs)
            elif event == 'recover-cmd-line':
                self.state = 'RECOVER'
                self.flagCmdLine=True
                self.doInit(*args, **kwargs)
                id_restorer.A('start', *args, **kwargs)
        #---WHAT_TO_DO?---
        elif self.state == 'WHAT_TO_DO?':
            if event == 'register-selected':
                self.state = 'INPUT_NAME'
                self.doUpdate(*args, **kwargs)
            elif event == 'recover-selected':
                self.state = 'LOAD_KEY'
                self.doUpdate(*args, **kwargs)
        #---INPUT_NAME---
        elif self.state == 'INPUT_NAME':
            if event == 'back':
                self.state = 'WHAT_TO_DO?'
                self.doClearOutput(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif event == 'register-start' and self.isNameValid(*args, **kwargs):
                self.state = 'REGISTER'
                self.doClearOutput(*args, **kwargs)
                self.doSaveName(*args, **kwargs)
                id_registrator.A('start', *args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif event == 'register-start' and not self.isNameValid(*args, **kwargs):
                self.doClearOutput(*args, **kwargs)
                self.doPrintIncorrectName(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif event == 'print':
                self.doPrint(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
        #---LOAD_KEY---
        elif self.state == 'LOAD_KEY':
            if event == 'back':
                self.state = 'WHAT_TO_DO?'
                self.doClearOutput(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif event == 'load-from-file':
                self.doReadKey(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif event == 'paste-from-clipboard':
                self.doPasteKey(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif event == 'restore-start':
                self.state = 'RECOVER'
                self.doClearOutput(*args, **kwargs)
                id_restorer.A('start', *args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif event == 'print':
                self.doPrint(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
        #---REGISTER---
        elif self.state == 'REGISTER':
            if event == 'print':
                self.doPrint(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif ( event == 'id_registrator.state' and args[0] == 'FAILED' ) and not self.flagCmdLine:
                self.state = 'INPUT_NAME'
                self.doShowOutput(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif ( event == 'id_registrator.state' and args[0] == 'DONE' ) and not self.flagCmdLine:
                self.state = 'AUTHORIZED'
                self.doPrepareSettings(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif ( event == 'id_registrator.state' and args[0] in [ 'DONE' , 'FAILED' ] ) and self.flagCmdLine:
                self.state = 'DONE'
                self.doUpdate(*args, **kwargs)
        #---AUTHORIZED---
        elif self.state == 'AUTHORIZED':
            if event == 'next':
                self.state = 'WIZARD'
                self.doUpdate(*args, **kwargs)
            elif event == 'print':
                self.doPrint(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
        #---RECOVER---
        elif self.state == 'RECOVER':
            if event == 'print':
                self.doPrint(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif ( event == 'id_restorer.state' and args[0] in [ 'RESTORED!' , 'FAILED' ] ) and self.flagCmdLine:
                self.state = 'DONE'
                self.doUpdate(*args, **kwargs)
            elif ( event == 'id_restorer.state' and args[0] == 'RESTORED!' ) and not self.flagCmdLine:
                self.state = 'RESTORED'
                self.doRestoreSettings(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif ( event == 'id_restorer.state' and args[0] == 'FAILED' ) and not self.flagCmdLine:
                self.state = 'LOAD_KEY'
                self.doUpdate(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            if event == 'print':
                self.doPrint(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
        #---WIZARD---
        elif self.state == 'WIZARD':
            if event == 'print':
                self.doPrint(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif ( event == 'install_wizard.state' and args[0] == 'DONE' ):
                self.state = 'DONE'
                self.doUpdate(*args, **kwargs)
        #---RESTORED---
        elif self.state == 'RESTORED':
            if event == 'print':
                self.doPrint(*args, **kwargs)
                self.doUpdate(*args, **kwargs)
            elif event == 'next':
                self.state = 'WIZARD'
                self.doUpdate(*args, **kwargs)
        return None

    def isNameValid(self, *args, **kwargs):
        if not misc.ValidUserName(args[0]['username']):
            return False
        return True

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doUpdate(self, *args, **kwargs):
        # lg.out(4, 'installer.doUpdate')
        from main import control
        control.request_update([{'state': self.state}, ])

    def doClearOutput(self, *args, **kwargs):
        # lg.out(4, 'installer.doClearOutput')
        for state in self.output.keys():
            self.output[state] = {'data': [('', 'black')]}

    def doPrint(self, *args, **kwargs):
        lg.out(8, 'installer.doPrint %s %s' % (self.state, str(*args, **kwargs)))
        if self.state not in self.output:
            self.output[self.state] = {'data': [('', 'black')]}
        if not args or args[0] is None:
            self.output[self.state]['data'] = [('', 'black')]
        else:
            self.output[self.state]['data'].append(args[0])
        if self.flagCmdLine:
            ch = '+'
            if args and args[0][1] == 'red':
                ch = '!'
            lg.out(0, '  %s %s' % (ch, args[0][0] if args else ''))

    def doShowOutput(self, *args, **kwargs):
        """
        Action method.
        """
        if 'INPUT_NAME' not in self.output:
            self.output['INPUT_NAME'] = {'data': [('', 'black')]}
        self.output['INPUT_NAME']['data'] = self.output['REGISTER']['data']

    def doPrintIncorrectName(self, *args, **kwargs):
        text, color = ('incorrect user name', 'red')
        if self.state not in self.output:
            self.output[self.state] = {'data': [('', 'black')]}
        self.output[self.state]['data'].append((text, color))
        # lg.out(0, '  [%s]' % text)

    def doSaveName(self, *args, **kwargs):
        settings.setPrivateKeySize(args[0]['pksize'])
        bpio.WriteTextFile(settings.UserNameFilename(), args[0]['username'])

    def doReadKey(self, *args, **kwargs):
        # keyfn = arg['keyfilename']
        src = args[0]['keysrc']
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

    def doPasteKey(self, *args, **kwargs):
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

    def doPrepareSettings(self, *args, **kwargs):
        """
        Action method.
        """

    def doRestoreSettings(self, *args, **kwargs):
        """
        Action method.
        """

#    def doIncreaseDebugLevel(self, *args, **kwargs):
#        """
#        """
#        if self.flagCmdLine and not lg.is_debug(10):
#            lg.set_debug_level(0)
#        else:
#            lg.set_debug_level(18)
