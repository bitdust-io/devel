#!/usr/bin/env python
# identity_restorer.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
    * :red:`suppliers-read-failed`
    * :red:`suppliers-read-ok`

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

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import sys
import random

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in identity_restorer.py')

#------------------------------------------------------------------------------

from bitdust.automats import automat

from bitdust.logs import lg

from bitdust.main import settings

from bitdust.system import bpio

from bitdust.lib import net_misc

from bitdust.raid import eccmap

from bitdust.crypt import key

from bitdust.contacts import contactsdb

from bitdust.stun import stun_client

from bitdust.dht import dht_relations

from bitdust.userid import identity
from bitdust.userid import my_id
from bitdust.userid import id_url

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
        'MSG_01': ['requesting user identity from remote ID server'],
        'MSG_02': ['key verification failed!', 'red'],
        'MSG_03': ['downloading user identity from remote ID server'],
        'MSG_04': ['incorrect or non-existing IDURL provided', 'red'],
        'MSG_05': ['verifying user identity and private key'],
        'MSG_06': ['your identity restored successfully!', 'green'],
        'MSG_07': ['checking network connectivity'],
        'MSG_08': [
            'network connection failed',
            'red',
        ],
        'MSG_09': ['reading list of my suppliers from DHT'],
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
        from bitdust.main import installer
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
                self.state = 'SUPPLIERS?'
                self.doPrint(self.msg('MSG_09', *args, **kwargs))
                self.doDHTReadMySuppliers(*args, **kwargs)
        #---SUPPLIERS?---
        elif self.state == 'SUPPLIERS?':
            if event == 'suppliers-read-ok' or event == 'suppliers-read-failed':
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
        if _Debug:
            lg.out(_DebugLevel, 'identity_restorer.doStunExternalIP')

        def save(result):
            if _Debug:
                lg.out(_DebugLevel, '            external IP : %s' % result)
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
        if _Debug:
            lg.out(_DebugLevel, 'identity_restorer.doRequestMyIdentity %s %s' % (idurl, type(idurl)))
        net_misc.getPageTwisted(idurl).addCallbacks(lambda src: self.automat('my-id-received', src), lambda err: self.automat('my-id-failed', err))

    def doVerifyAndRestore(self, *args, **kwargs):
        global _WorkingKey
        if _Debug:
            lg.out(_DebugLevel, 'identity_restorer.doVerifyAndRestore')

        remote_identity_src = args[0]

        if os.path.isfile(settings.KeyFileName()):
            if _Debug:
                lg.out(_DebugLevel, 'identity_restorer.doVerifyAndRestore will backup and remove ' + settings.KeyFileName())
            bpio.backup_and_remove(settings.KeyFileName())

        if os.path.isfile(settings.LocalIdentityFilename()):
            if _Debug:
                lg.out(_DebugLevel, 'identity_restorer.doVerifyAndRestore will backup and remove ' + settings.LocalIdentityFilename())
            bpio.backup_and_remove(settings.LocalIdentityFilename())

        try:
            remote_ident = identity.identity(xmlsrc=remote_identity_src)
            local_ident = identity.identity(xmlsrc=remote_identity_src)
        except:
            # lg.exc()
            reactor.callLater(0.1, self.automat, 'restore-failed', ('remote identity have incorrect format', 'red'))  # @UndefinedVariable
            return

        if _Debug:
            lg.out(_DebugLevel, 'identity_restorer.doVerifyAndRestore checking remote identity')
        try:
            res = remote_ident.isCorrect()
        except:
            lg.exc()
            res = False
        if not res:
            if _Debug:
                lg.out(_DebugLevel, 'identity_restorer.doVerifyAndRestore remote identity is not correct FAILED!!!!')
            reactor.callLater(0.1, self.automat, 'restore-failed', ('remote identity format is not correct', 'red'))  # @UndefinedVariable
            return

        if _Debug:
            lg.out(_DebugLevel, 'identity_restorer.doVerifyAndRestore validate remote identity')
        try:
            res = remote_ident.Valid()
        except:
            lg.exc()
            res = False
        if not res:
            if _Debug:
                lg.out(_DebugLevel, 'identity_restorer.doVerifyAndRestore validate remote identity FAILED!!!!')
            reactor.callLater(0.1, self.automat, 'restore-failed', ('remote identity is not valid', 'red'))  # @UndefinedVariable
            return

        my_id.forgetLocalIdentity()
        my_id.eraseLocalIdentity(do_backup=True)
        key.ForgetMyKey(erase_file=True, do_backup=True)
        bpio.WriteTextFile(settings.KeyFileName(), _WorkingKey)
        try:
            key.InitMyKey()
        except:
            key.ForgetMyKey(erase_file=True, do_backup=False)
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
            if _Debug:
                lg.out(_DebugLevel, 'identity_restorer.doVerifyAndRestore will remove backup file for ' + settings.KeyFileName())
            bpio.remove_backuped_file(settings.KeyFileName())

        if os.path.isfile(settings.LocalIdentityFilename() + '.backup'):
            if _Debug:
                lg.out(_DebugLevel, 'identity_restorer.doVerifyAndRestore will remove backup file for ' + settings.LocalIdentityFilename())
            bpio.remove_backuped_file(settings.LocalIdentityFilename())

        reactor.callLater(0.1, self.automat, 'restore-success')  # @UndefinedVariable

    def doDHTReadMySuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        known_suppliers = len(contactsdb.suppliers())
        if known_suppliers > 0:
            lg.warn('skip reading my suppliers from DHT, currently known %d suppliers already' % known_suppliers)
            self.automat('suppliers-read-ok')
            return
        d = dht_relations.read_customer_suppliers(my_id.getIDURL(), use_cache=False)
        d.addCallback(self._on_my_dht_relations_discovered)
        d.addErrback(self._on_my_dht_relations_failed)

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
        from bitdust.main import installer
        installer.A().event('print', args[0])
        self.last_message = args[0][0]
        if _Debug:
            lg.out(_DebugLevel, 'id_restorer.doPrint: %s' % str(args[0]))

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.executeStateChangedCallbacks(oldstate=None, newstate=self.state, event_string=None, args=args)
        self.destroy(dead_state=self.state)
        global _IdRestorer
        _IdRestorer = None

    def _on_my_dht_relations_discovered(self, dht_result):
        if not (dht_result and isinstance(dht_result, dict) and len(dht_result.get('suppliers', [])) > 0):
            lg.warn('no dht records found for my customer family')
            self.automat('suppliers-read-failed')
            return
        dht_suppliers = id_url.to_bin_list(dht_result['suppliers'])
        dht_ecc_map = dht_result.get('ecc_map', settings.DefaultEccMapName())
        try:
            dht_desired_suppliers_number = eccmap.GetEccMapSuppliersNumber(dht_ecc_map)
        except:
            lg.exc()
            dht_desired_suppliers_number = eccmap.GetEccMapSuppliersNumber(settings.DefaultEccMapName())
        settings.config.conf().setInt('services/customer/suppliers-number', dht_desired_suppliers_number)
        contactsdb.set_suppliers(dht_suppliers)
        contactsdb.save_suppliers()
        lg.info('found and restored list of %d suppliers from DHT' % dht_desired_suppliers_number)
        self.automat('suppliers-read-ok')

    def _on_my_dht_relations_failed(self, err):
        lg.err(err)
        self.automat('suppliers-read-failed')
