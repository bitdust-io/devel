#!/usr/bin/env python
#install_wizard.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: install_wizard

.. raw:: html

    <a href="http://bitpie.net/automats/install_wizard/install_wizard.png" target="_blank">
    <img src="http://bitpie.net/automats/install_wizard/install_wizard.png" style="max-width:100%;">
    </a>
    
A state machine to show installation wizard for BitPie.NET software.
User need to answer some questions step by step to configure the program first time.

This is several pages:
    * select a role: "free backups", "secure storage", "donator", "just to try", "beta tester"
    * set up needed and donated space and local folders locations
    * provide some personal information about your self if you wish
    * set software update settings  
    
EVENTS:
    * :red:`back`
    * :red:`next`
    * :red:`select-beta-test`
    * :red:`select-donator`
    * :red:`select-free-backups`
    * :red:`select-secure`
    * :red:`select-try-it`
"""

import sys
try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in install_wizard.py')

import lib.bpio as bpio
import lib.settings as settings
from lib.automat import Automat

import installer
import webcontrol
# import bpupdate

#------------------------------------------------------------------------------ 

_InstallWizard = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _InstallWizard
    if _InstallWizard is None:
        _InstallWizard = InstallWizard('install_wizard', 'READY', 2)
    if event is not None:
        _InstallWizard.automat(event, arg)
    return _InstallWizard

class InstallWizard(Automat):
    """
    BitPie.NET install_wizard() Automat.
    Runs install wizard process.
    """
    
    role_args = None
    role = None

    def state_changed(self, oldstate, newstate):
        reactor.callLater(0, webcontrol.OnUpdateInstallPage)
        installer.A('install_wizard.state', newstate)

    def A(self, event, arg):
        #---READY---
        if self.state == 'READY':
            if event == 'select-donator' :
                self.state = 'DONATOR'
                self.doSaveRole(arg)
            elif event == 'select-free-backups' :
                self.state = 'FREE_BACKUPS'
                self.doSaveRole(arg)
            elif event == 'select-beta-test' :
                self.state = 'BETA_TEST'
                self.doSaveRole(arg)
            elif event == 'select-secure' :
                self.state = 'MOST_SECURE'
                self.doSaveRole(arg)
            elif event == 'select-try-it' :
                self.state = 'JUST_TRY_IT'
                self.doSaveRole(arg)
        #---MOST_SECURE---
        elif self.state == 'MOST_SECURE':
            if event == 'back' :
                self.state = 'READY'
            elif event == 'next' :
                self.state = 'STORAGE'
                self.doSaveParams(arg)
        #---FREE_BACKUPS---
        elif self.state == 'FREE_BACKUPS':
            if event == 'back' :
                self.state = 'READY'
            elif event == 'next' :
                self.state = 'STORAGE'
                self.doSaveParams(arg)
        #---BETA_TEST---
        elif self.state == 'BETA_TEST':
            if event == 'back' :
                self.state = 'READY'
            elif event == 'next' :
                self.state = 'STORAGE'
                self.doSaveParams(arg)
        #---DONATOR---
        elif self.state == 'DONATOR':
            if event == 'back' :
                self.state = 'READY'
            elif event == 'next' :
                self.state = 'STORAGE'
        #---JUST_TRY_IT---
        elif self.state == 'JUST_TRY_IT':
            if event == 'back' :
                self.state = 'READY'
            elif event == 'next' :
                self.state = 'LAST_PAGE'
        #---STORAGE---
        elif self.state == 'STORAGE':
            if event == 'next' :
                self.state = 'CONTACTS'
                self.doSaveStorage(arg)
            elif event == 'back' and self.isRoleSecure(arg) :
                self.state = 'MOST_SECURE'
            elif event == 'back' and self.isRoleDonator(arg) :
                self.state = 'DONATOR'
            elif event == 'back' and self.isRoleFreeBackups(arg) :
                self.state = 'FREE_BACKUPS'
            elif event == 'back' and self.isRoleBetaTest(arg) :
                self.state = 'BETA_TEST'
        #---CONTACTS---
        elif self.state == 'CONTACTS':
            if event == 'back' :
                self.state = 'STORAGE'
            elif event == 'next' :
                self.state = 'LAST_PAGE'
                self.doSaveContacts(arg)
        #---DONE---
        elif self.state == 'DONE':
            if event == 'back' :
                self.state = 'LAST_PAGE'
        #---LAST_PAGE---
        elif self.state == 'LAST_PAGE':
            if event == 'next' :
                self.state = 'DONE'
            elif event == 'back' :
                self.state = 'CONTACTS'

    def isRoleSecure(self, arg):
        return self.role == 'MOST_SECURE'

    def isRoleFreeBackups(self, arg):
        return self.role == 'FREE_BACKUPS'

    def isRoleBetaTest(self, arg):
        return self.role == 'BETA_TEST'

    def isRoleDonator(self, arg):
        return self.role == 'DONATOR'

    def doSaveRole(self, arg):
        self.role = self.state

    def doSaveParams(self, arg):
        self.role_args = arg

    def doSaveStorage(self, arg):
        needed = arg.get('needed', '')
        donated = arg.get('donated', '')
        customersdir = arg.get('customersdir', '')
        localbackupsdir = arg.get('localbackupsdir', '')
        restoredir = arg.get('restoredir', '')
        if needed:
            settings.uconfig().set('storage.needed', needed+' MB')
        if donated:
            settings.uconfig().set('storage.donated', donated+' MB')
        if customersdir:
            settings.uconfig().set('folder.folder-customers', customersdir)
        if localbackupsdir:
            settings.uconfig().set('folder.folder-backups', localbackupsdir)
        if restoredir:
            settings.uconfig().set('folder.folder-restore', restoredir)
        if self.role == 'MOST_SECURE':
            settings.uconfig().set('general.general-local-backups-enable', 'False')
        settings.uconfig().update()

    def doSaveContacts(self, arg):
        settings.uconfig().set('emergency.emergency-email', arg.get('email', '').strip())
        settings.uconfig().set('personal.personal-name', arg.get('name', ''))
        settings.uconfig().set('personal.personal-surname', arg.get('surname', ''))
        settings.uconfig().set('personal.personal-nickname', arg.get('nickname', ''))
        if self.role == 'BETA_TEST':
            settings.uconfig().set('personal.personal-betatester', 'True')
            if self.role_args and self.role_args.get('development', '').lower() == 'true':
                settings.uconfig().set("logs.debug-level", '10')
                settings.uconfig().set("logs.stream-enable", 'True')
                bpio.SetDebug(10)
        settings.uconfig().update()

#    def doSaveUpdates(self, arg):
#        """
#        """
#        shedule = bpupdate.blank_shedule(arg)
#        settings.uconfig().set('updates.updates-shedule', bpupdate.shedule_to_string(shedule))
#        settings.uconfig().update()




