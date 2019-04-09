#!/usr/bin/env python
# identity_restorer.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (id_restorer.py) is part of BitDust Software.
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
.. module:: id_restorer.

.. role:: red


EVENTS:
    * :red:`my-id-failed`
    * :red:`my-id-received`
    * :red:`restore-failed`
    * :red:`restore-success`
    * :red:`start`
    * :red:`stun-failed`
    * :red:`stun-success`

.. raw:: html

    <a href="https://bitdust.io/automats/identity_restorer/identity_restorer.png" target="_blank">
    <img src="https://bitdust.io/automats/identity_restorer/identity_restorer.png" style="max-width:100%;">
    </a>

A state machine to restore the user account.

Needed for restoration of the user account information using its Private key and ID url.
    * at first request user's identity file from Identity server
    * do verification and restoration of his locally identity to be able to start the software
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

import os
import sys
import random

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in identity_restorer.py')

#------------------------------------------------------------------------------

from automats import automat
from automats import global_state

from logs import lg

from main import settings

from system import bpio

from lib import net_misc

from crypt import key

from stun import stun_client

from userid import identity
from userid import my_id


#------------------------------------------------------------------------------

_IdRestorer = None
_WorkingIDURL = ''
_WorkingKey = ''

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _IdRestorer
    if _IdRestorer is None:
        # set automat name and starting state here
        _IdRestorer = IdRestorer(
            name='id_restorer',
            state='AT_STARTUP',
            debug_level=2,
            log_transitions=True,
            log_events=True,
            publish_events=True,
        )
    if event is not None:
        _IdRestorer.automat(event, *args, **kwargs)
    return _IdRestorer


class IdRestorer(automat.Automat):
    """
    BitDust identity_restorer() Automat.

    Class to run the process to restore user account.
    """

    MESSAGES = {
        'MSG_01': ['requesting user identity from remote ID server', ],
        'MSG_02': ['key verification failed!', 'red'],
        'MSG_03': ['downloading user identity from remote ID server', ],
        'MSG_04': ['incorrect IDURL or user identity file not exist anymore', 'red'],
        'MSG_05': ['verifying user identity and private key', ],
        'MSG_06': ['your identity restored successfully!', 'green'],
        'MSG_07': ['checking network connectivity', ],
        'MSG_08': ['network connection failed', 'red', ],
    }

    def init(self):
        self.last_message = ''

    def msg(self, msgid, *args, **kwargs):
        msg = self.MESSAGES.get(msgid, ['', 'black'])
        text = msg[0]
        color = 'black'
        if len(msg) == 2:
            color = msg[1]
        return text, color

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        global_state.set_global_state('ID_RESTORE ' + newstate)
        from main import installer
        installer.A('id_restorer.state', newstate)

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'STUN_MY_IP'
                self.doPrint(self.msg('MSG_07', *args, **kwargs))
                self.doSetWorkingIDURL(*args, **kwargs)
                self.doSetWorkingKey(*args, **kwargs)
                self.doStunExternalIP(*args, **kwargs)
        #---STUN_MY_IP---
        elif self.state == 'STUN_MY_IP':
            if event == 'stun-failed':
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_08', *args, **kwargs))
                self.doClearWorkingIDURL(*args, **kwargs)
                self.doClearWorkingKey(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stun-success':
                self.state = 'MY_ID'
                self.doPrint(self.msg('MSG_01', *args, **kwargs))
                self.doRequestMyIdentity(*args, **kwargs)
        #---MY_ID---
        elif self.state == 'MY_ID':
            if event == 'my-id-received':
                self.state = 'VERIFY'
                self.doPrint(self.msg('MSG_05', *args, **kwargs))
                self.doVerifyAndRestore(*args, **kwargs)
            elif event == 'my-id-failed':
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_04', *args, **kwargs))
                self.doClearWorkingIDURL(*args, **kwargs)
                self.doClearWorkingKey(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---VERIFY---
        elif self.state == 'VERIFY':
            if event == 'restore-failed':
                self.state = 'FAILED'
                self.doPrint(*args, **kwargs)
                self.doClearWorkingIDURL(*args, **kwargs)
                self.doClearWorkingKey(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'restore-success':
                self.state = 'RESTORED!'
                self.doPrint(self.msg('MSG_06', *args, **kwargs))
                self.doRestoreSave(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---RESTORED!---
        elif self.state == 'RESTORED!':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def doStunExternalIP(self, *args, **kwargs):
        """
        Action method.
        """
        lg.out(4, 'identity_restorer.doStunExternalIP')

        def save(result):
            lg.out(4, '            external IP : %s' % result)
            if result['result'] != 'stun-success':
                self.automat('stun-failed')
                return
            ip = result['ip']
            bpio.WriteTextFile(settings.ExternalIPFilename(), ip)
            self.automat('stun-success', ip)

        rnd_udp_port = random.randint(
            settings.DefaultUDPPort(),
            settings.DefaultUDPPort() + 500,
        )
        rnd_dht_port = random.randint(
            settings.DefaultDHTPort(),
            settings.DefaultDHTPort() + 500,
        )
        d = stun_client.safe_stun(udp_port=rnd_udp_port, dht_port=rnd_dht_port)
        d.addCallback(save)
        d.addErrback(lambda _: self.automat('stun-failed'))

    def doSetWorkingIDURL(self, *args, **kwargs):
        global _WorkingIDURL
        _WorkingIDURL = args[0]['idurl']

    def doSetWorkingKey(self, *args, **kwargs):
        global _WorkingKey
        _WorkingKey = args[0]['keysrc']

    def doClearWorkingIDURL(self, *args, **kwargs):
        global _WorkingIDURL
        _WorkingIDURL = ''

    def doClearWorkingKey(self, *args, **kwargs):
        global _WorkingKey
        _WorkingKey = ''

    def doRequestMyIdentity(self, *args, **kwargs):
        global _WorkingIDURL
        idurl = _WorkingIDURL
        lg.out(4, 'identity_restorer.doRequestMyIdentity %s %s' % (idurl, type(idurl)))
        net_misc.getPageTwisted(idurl).addCallbacks(
            lambda src: self.automat('my-id-received', src),
            lambda err: self.automat('my-id-failed', err))

    def doVerifyAndRestore(self, *args, **kwargs):
        global _WorkingKey
        lg.out(4, 'identity_restorer.doVerifyAndRestore')

        remote_identity_src = args[0]

        if os.path.isfile(settings.KeyFileName()):
            lg.out(4, 'identity_restorer.doVerifyAndRestore will backup and remove ' + settings.KeyFileName())
            bpio.backup_and_remove(settings.KeyFileName())

        if os.path.isfile(settings.LocalIdentityFilename()):
            lg.out(4, 'identity_restorer.doVerifyAndRestore will backup and remove ' + settings.LocalIdentityFilename())
            bpio.backup_and_remove(settings.LocalIdentityFilename())

        try:
            remote_ident = identity.identity(xmlsrc=remote_identity_src)
            local_ident = identity.identity(xmlsrc=remote_identity_src)
        except:
            # lg.exc()
            reactor.callLater(0.1, self.automat, 'restore-failed', ('remote identity have incorrect format', 'red'))  # @UndefinedVariable
            return

        lg.out(4, 'identity_restorer.doVerifyAndRestore checking remote identity')
        try:
            res = remote_ident.isCorrect()
        except:
            lg.exc()
            res = False
        if not res:
            lg.out(4, 'identity_restorer.doVerifyAndRestore remote identity is not correct FAILED!!!!')
            reactor.callLater(0.1, self.automat, 'restore-failed', ('remote identity format is not correct', 'red'))  # @UndefinedVariable
            return

        lg.out(4, 'identity_restorer.doVerifyAndRestore validate remote identity')
        try:
            res = remote_ident.Valid()
        except:
            lg.exc()
            res = False
        if not res:
            lg.out(4, 'identity_restorer.doVerifyAndRestore validate remote identity FAILED!!!!')
            reactor.callLater(0.1, self.automat, 'restore-failed', ('remote identity is not valid', 'red'))  # @UndefinedVariable
            return

        key.ForgetMyKey()
        bpio.WriteTextFile(settings.KeyFileName(), _WorkingKey)
        try:
            key.InitMyKey()
        except:
            key.ForgetMyKey()
            # lg.exc()
            try:
                os.remove(settings.KeyFileName())
            except:
                pass
            reactor.callLater(0.1, self.automat, 'restore-failed', ('private key is not valid', 'red'))  # @UndefinedVariable
            return

        try:
            local_ident.sign()
        except:
            # lg.exc()
            reactor.callLater(0.1, self.automat, 'restore-failed', ('error while signing identity', 'red'))  # @UndefinedVariable
            return

        if remote_ident.signature != local_ident.signature:
            reactor.callLater(0.1, self.automat, 'restore-failed', ('signature did not match, key verification failed!', 'red'))  # @UndefinedVariable
            return

        my_id.setLocalIdentity(local_ident)
        my_id.saveLocalIdentity()
        # my_id.rebuildLocalIdentity(save_identity=True)

        bpio.WriteTextFile(settings.UserNameFilename(), my_id.getIDName())

        if os.path.isfile(settings.KeyFileName() + '.backup'):
            lg.out(4, 'identity_restorer.doVerifyAndRestore will remove backup file for ' + settings.KeyFileName())
            bpio.remove_backuped_file(settings.KeyFileName())

        if os.path.isfile(settings.LocalIdentityFilename() + '.backup'):
            lg.out(4, 'identity_restorer.doVerifyAndRestore will remove backup file for ' + settings.LocalIdentityFilename())
            bpio.remove_backuped_file(settings.LocalIdentityFilename())

        reactor.callLater(0.1, self.automat, 'restore-success')  # @UndefinedVariable

    def doRestoreSave(self, *args, **kwargs):
        """
        TODO: use lib.config here request settings from DHT my suppliers need
        to keep that settings in DHT.
        """
        # settings.uconfig().set('storage.suppliers', '0')
        # settings.uconfig().set('storage.needed', '0Mb')
        # settings.uconfig().set('storage.donated', '0Mb')
        # settings.uconfig().update()

    def doPrint(self, *args, **kwargs):
        from main import installer
        installer.A().event('print', args[0])
        self.last_message = args[0][0]
        lg.out(6, 'id_restorer.doPrint: %s' % str(args[0]))

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.executeStateChangedCallbacks(oldstate=None, newstate=self.state, event_string=None, args=args)
        self.destroy(dead_state=self.state)
        global _IdRestorer
        _IdRestorer = None

