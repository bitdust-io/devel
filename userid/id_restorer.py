#!/usr/bin/env python
#identity_restorer.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: id_restorer
.. role:: red


EVENTS:
    * :red:`my-id-failed`
    * :red:`my-id-received`
    * :red:`restore-failed`
    * :red:`restore-success`
    * :red:`start`

.. raw:: html

    <a href="http://bitpie.net/automats/identity_restorer/identity_restorer.png" target="_blank">
    <img src="http://bitpie.net/automats/identity_restorer/identity_restorer.png" style="max-width:100%;">
    </a>
    
A state machine to restore the user account.

Needed for restoration of the user account information using its Private key and ID url.
    * at first request user's identity file from Identity server
    * do verification and restoration of the his account locally and start the software   
"""

import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in identity_restorer.py')
    
from twisted.internet.defer import Deferred, DeferredList, maybeDeferred
from twisted.internet.task import LoopingCall

from logs import lg

from lib import automat
from lib import automats
from lib import bpio
from lib import misc
from lib import settings
from lib import net_misc

from crypt import key

from userid import identitycache
from userid import identity

#------------------------------------------------------------------------------ 

_IdRestorer = None
_WorkingIDURL = ''
_WorkingKey = ''

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _IdRestorer
    if _IdRestorer is None:
        # set automat name and starting state here
        _IdRestorer = IdRestorer('id_restorer', 'AT_STARTUP')
    if event is not None:
        _IdRestorer.automat(event, arg)
    return _IdRestorer


class IdRestorer(automat.Automat):
    """
    BitPie.NET identity_restorer() Automat.
    Class to run the process to restore user account. 
    """
    
    MESSAGES = {
        'MSG_01':   ['download central server identity'], 
        'MSG_02':   ['network connection failed', 'red'],
        'MSG_03':   ['download user identity'],
        'MSG_04':   ['user identity not exist', 'red'],
        'MSG_05':   ['verifying user identity and private key'],
        'MSG_06':   ['your account were restored!', 'green'], }

    def msg(self, msgid, arg=None): 
        msg = self.MESSAGES.get(msgid, ['', 'black'])
        text = msg[0]
        color = 'black'
        if len(msg) == 2:
            color = msg[1]
        return text, color

    def state_changed(self, oldstate, newstate):
        automats.set_global_state('ID_RESTORE ' + newstate)
        import p2p.installer as installer
        installer.A('id_restorer.state', newstate)

    def A(self, event, arg):
        #---MY_ID---
        if self.state == 'MY_ID':
            if event == 'my-id-received' :
                self.state = 'VERIFY'
                self.doPrint(self.msg('MSG_05', arg))
                self.doVerifyAndRestore(arg)
            elif event == 'my-id-failed' :
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_04', arg))
                self.doClearWorkingIDURL(arg)
                self.doClearWorkingKey(arg)
                self.doDestroyMe(arg)
        #---RESTORED!---
        elif self.state == 'RESTORED!':
            pass
        #---VERIFY---
        elif self.state == 'VERIFY':
            if event == 'restore-failed' :
                self.state = 'FAILED'
                self.doPrint(arg)
                self.doClearWorkingIDURL(arg)
                self.doClearWorkingKey(arg)
                self.doDestroyMe(arg)
            elif event == 'restore-success' :
                self.state = 'RESTORED!'
                self.doPrint(self.msg('MSG_06', arg))
                self.doRestoreSave(arg)
                self.doDestroyMe(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'start' :
                self.state = 'MY_ID'
                self.doPrint(self.msg('MSG_01', arg))
                self.doSetWorkingIDURL(arg)
                self.doSetWorkingKey(arg)
                self.doRequestMyIdentity(arg)
        #---FAILED---
        elif self.state == 'FAILED':
            pass

    def doSetWorkingIDURL(self, arg):
        global _WorkingIDURL
        _WorkingIDURL = arg['idurl']
        
    def doSetWorkingKey(self, arg):
        global _WorkingKey
        _WorkingKey = arg['keysrc']

    def doClearWorkingIDURL(self, arg):
        global _WorkingIDURL
        _WorkingIDURL = ''
        
    def doClearWorkingKey(self, arg):
        global _WorkingKey
        _WorkingKey = ''

    def doRequestMyIdentity(self, arg):
        global _WorkingIDURL
        idurl = _WorkingIDURL
        lg.out(4, 'identity_restorer.doRequestMyIdentity %s' % idurl)
        net_misc.getPageTwisted(idurl).addCallbacks(
            lambda src: self.automat('my-id-received', src),
            lambda err: self.automat('my-id-failed', err))
    
    def doVerifyAndRestore(self, arg):
        global _WorkingKey
        lg.out(4, 'identity_restorer.doVerifyAndRestore')
    
        remote_identity_src = arg

        if os.path.isfile(settings.KeyFileName()):
            lg.out(4, 'identity_restorer.doVerifyAndRestore will backup and remove ' + settings.KeyFileName())
            bpio.backup_and_remove(settings.KeyFileName())

        if os.path.isfile(settings.LocalIdentityFilename()):    
            lg.out(4, 'identity_restorer.doVerifyAndRestore will backup and remove ' + settings.LocalIdentityFilename())
            bpio.backup_and_remove(settings.LocalIdentityFilename())
    
        try:
            remote_ident = identity.identity(xmlsrc = remote_identity_src)
            local_ident = identity.identity(xmlsrc = remote_identity_src)
        except:
            # lg.exc()
            reactor.callLater(0.5, self.automat, 'restore-failed', ('remote identity have incorrect format', 'red'))
            return
    
        try:
            res = remote_ident.Valid()
        except:
            lg.exc()
            res = False
        if not res:
            reactor.callLater(0.5, self.automat, 'restore-failed', ('remote identity is not valid', 'red'))
            return
    
        key.ForgetMyKey()
        bpio.WriteFile(settings.KeyFileName(), _WorkingKey)
        try:
            key.InitMyKey()
        except:
            key.ForgetMyKey()
            # lg.exc()
            try:
                os.remove(settings.KeyFileName())
            except:
                pass
            reactor.callLater(0.5, self.automat, 'restore-failed', ('private key is not valid', 'red'))
            return
    
        try:
            local_ident.sign()
        except:
            # lg.exc()
            reactor.callLater(0.5, self.automat, 'restore-failed', ('error while signing identity', 'red'))
            return
    
        if remote_ident.signature != local_ident.signature:
            reactor.callLater(0.5, self.automat, 'restore-failed', ('signature did not match', 'red'))
            return
    
        misc.setLocalIdentity(local_ident)
        misc.saveLocalIdentity()
    
        bpio.WriteFile(settings.UserNameFilename(), misc.getIDName())
    
        if os.path.isfile(settings.KeyFileName()+'.backup'):
            lg.out(4, 'identity_restorer.doVerifyAndRestore will remove backup file for ' + settings.KeyFileName())
            bpio.remove_backuped_file(settings.KeyFileName())

        if os.path.isfile(settings.LocalIdentityFilename()+'.backup'):
            lg.out(4, 'identity_restorer.doVerifyAndRestore will remove backup file for ' + settings.LocalIdentityFilename())
            bpio.remove_backuped_file(settings.LocalIdentityFilename())

        reactor.callLater(0.5, self.automat, 'restore-success')
        
    def doRestoreSave(self, arg):
        settings.uconfig().set('storage.suppliers', '0')
        settings.uconfig().set('storage.needed', '0Mb')
        settings.uconfig().set('storage.donated', '0Mb')
        settings.uconfig().update()

    def doPrint(self, arg):
        import p2p.installer as installer
        installer.A().event('print', arg)

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        automat.objects().pop(self.index)
        global _IdRestorer
        _IdRestorer = None
        









