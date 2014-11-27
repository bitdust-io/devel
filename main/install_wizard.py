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
    * provide some personal information about yourself if you wish
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

from logs import lg

from lib import misc
from main import settings
from main import config
from automats import automat

import installer

from web import webcontrol

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

class InstallWizard(automat.Automat):
    """
    BitPie.NET install_wizard() Automat.
    Runs install wizard process.
    """
    
    role_args = None
    role = None

    def state_changed(self, oldstate, newstate, event, arg):
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
            config.conf().setData('services/customer/needed-space', needed+' MB')
        if donated:
            config.conf().setData('services/supplier/donated-space', donated+' MB')
        if customersdir:
            config.conf().setData('paths/customers', customersdir)
        if localbackupsdir:
            config.conf().setData('paths/backups', localbackupsdir)
        if restoredir:
            config.conf().setData('paths/restore', restoredir)
        if self.role == 'MOST_SECURE':
            config.conf().setBool('services/backups/keep-local-copies-enabled', False)
        

    def doSaveContacts(self, arg):
        config.conf().setData('emergency/emergency-email', arg.get('email', '').strip())
        config.conf().setData('personal/name', arg.get('name', ''))
        config.conf().setData('personal/surname', arg.get('surname', ''))
        config.conf().setData('personal/nickname', arg.get('nickname', ''))
        if self.role == 'BETA_TEST':
            config.conf().setBool('personal/betatester', True)
            if self.role_args and self.role_args.get('development', '').lower() == 'true':
                config.conf().setInt("logs/debug-level", 14)
                config.conf().setBool("logs/stream-enable", True)
                lg.set_debug_level(14)
        repo, locationURL = misc.ReadRepoLocation()
        if repo == 'test':
            config.conf().setInt("logs/debug-level", 18)
        elif repo == 'devel':
            config.conf().setInt("logs/debug-level", 12)
        

#    def doSaveUpdates(self, arg):
#        """
#        """
#        shedule = bpupdate.blank_shedule(arg)
#        config.conf().setData('updates.updates-shedule', bpupdate.shedule_to_string(shedule))
#        




