#!/usr/bin/env python
#views.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (views.py) is part of BitDust Software.
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
import os

#------------------------------------------------------------------------------ 

from twisted.internet import reactor

#------------------------------------------------------------------------------ 

from django.views.generic import TemplateView
from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.contrib.auth import logout

#------------------------------------------------------------------------------ 

from system import bpio

from lib import misc
from lib import diskspace
from system import diskusage 

from userid import my_id

from main import settings

from main import installer
from main import install_wizard

#------------------------------------------------------------------------------ 

_ALREADY_CONFIGURED_REDIRECT_URL = '/'

#------------------------------------------------------------------------------ 

_SetupControllerObject = None
_FinishedState = False

#------------------------------------------------------------------------------ 

class SetupView(TemplateView):
    def dispatch(self, request):
        global _SetupControllerObject
        global _FinishedState
        
        if _SetupControllerObject is None:
            if not installer.IsExist():
                return HttpResponseRedirect(_ALREADY_CONFIGURED_REDIRECT_URL)
            _SetupControllerObject = SetupController()
            
        result = _SetupControllerObject.render(request)
        
        if result is None:
            return HttpResponseRedirect(request.path)
        
        template, context, new_request = result
        
        context['context_instance'] = RequestContext(new_request)
        
        if _FinishedState:
            logout(new_request)

        response = TemplateResponse(new_request, template, context)

        if _FinishedState:
            response.delete_cookie('sessionid')

        return response
        
#------------------------------------------------------------------------------ 

class SetupController:

    def __init__(self):
        self.installer_state_to_page = {
            'AT_STARTUP':   self.renderSelectPage,
            'WHAT_TO_DO?':  self.renderSelectPage,
            'INPUT_NAME':   self.renderInputNamePage,
            'REGISTER':     self.renderRegisterNewUserPage,
            'AUTHORIZED':   self.renderRegisterNewUserPage,
            'LOAD_KEY':     self.renderLoadKeyPage,
            'RECOVER':      self.renderRestorePage,
            'RESTORED':     self.renderRestorePage,
            'WIZARD':       self.renderWizardPage,
            'DONE':         self.renderLastPage, 
            }
        self.install_wizard_state_to_page = {
            'READY':        self.renderWizardStartPage,
            'STORAGE':      self.renderWizardStoragePage,
            'CONTACTS':     self.renderWizardContactsPage,
            'LAST_PAGE':    self.renderLastPage,
            'DONE':         self.renderLastPage, 
            }
        self.data = {
            'username': bpio.ReadTextFile(settings.UserNameFilename()).strip(),
            'pksize': settings.DefaultPrivateKeySize(),
            'needed': str( int( settings.DefaultNeededBytes() / (1024*1024) ) ),
            'donated': str( int( settings.DefaultDonatedBytes() / (1024*1024) ) ),
            'suppliers': str(settings.DefaultDesiredSuppliers()),
            'customersdir': unicode(settings.getCustomersFilesDir()),
            'localbackupsdir': unicode(settings.getLocalBackupsDir()),
            'restoredir': unicode(settings.getRestoreDir()),
            'idurl': '',
            'keysrc': '',
            'name': '',
            'surname': '',
            'nickname': '',
            }
        installer.A('init')
        
    def _get_output(self, state):
        out = ''
        for text, color in installer.A().getOutput(state).get('data', []):
            if text.strip():
                out += '<font color="%s">%s</font><br />\n' % (color, text)
        return out
    
    def render(self, request):
        current_state = installer.A().state
        current_page = self.installer_state_to_page.get(current_state, None)
        if current_page is None:
            raise Exception('incorrect state in installer(): %s' % current_state)
        result = current_page(request)
        return result

    def renderWizardPage(self, request):
        current_state = install_wizard.A().state
        current_page = self.install_wizard_state_to_page.get(current_state, None)
        if current_page is None:
            raise Exception('incorrect state in install_wizard(): %s' % current_state)
        result = current_page(request)
        return result

    def renderSelectPage(self, request):
        template = 'pages/select_action.html'
        context = { }
        if request is None:
            return template, context, request 
        action = request.REQUEST.get('action', None)
        if action == 'next':
            installer.A(request.REQUEST.get('mode', 'register-selected'))
            return None
        return template, context, request

    def renderInputNamePage(self, request):
        template = 'pages/input_name.html'
        possible_name = bpio.getUserName().lower()
        if misc.isEnglishString(possible_name):
            possible_name = 'e.g.: ' + possible_name
        else:
            possible_name = ''
        context = {'username': self.data['username'],
                   'pksize': self.data['pksize'], 
                   'output': '', 
                   'usernameplaceholder': possible_name, }
        try:
            text, color = installer.A().getOutput().get('data', [('', '')])[-1]
            context['output'] = '<font color="%s">%s</font><br />\n' % (color, text)
        except:
            pass
        if request is None:
            return template, context, request 
        action = request.REQUEST.get('action', None)
        if action == 'next':
            self.data['pksize'] = int(request.REQUEST.get('pksize', self.data['pksize']))
            self.data['username'] = request.REQUEST.get('username', self.data['username']).lower()
            installer.A('register-start', self.data)
            return None
        if action == 'back':
            installer.A('back')
            return None
        return template, context, request
            
    def renderRegisterNewUserPage(self, request):
        template = 'pages/new_user.html'
        out = ''
        for text, color in installer.A().getOutput().get('data', []):
            if text.strip():
                out += '     <li><font color="%s">%s</font></li>\n' % (color, text)
        if out:
            out = '    <ul>\n' + out + '    </ul>\n'
        context = {'idurl': '', 
                   'output': out,
                   }
        if installer.A().state == 'AUTHORIZED':
            context['idurl'] = my_id.getLocalID()
            self.data['idurl'] = str(context['idurl'])
        if request is None:
            return template, context, request 
        action = request.REQUEST.get('action', None)
        if action == 'next':
            installer.A(action, self.data)
            return None
        return template, context, request
    
    def renderLoadKeyPage(self, request):
        template = 'pages/load_key.html'
        out = ''
        try:
            text, color = installer.A().getOutput('RECOVER').get('data', [('', '')])[-1]
            if text:
                out = '    <p><font color="%s">%s</font></p>\n' % (color, text)
        except:
            pass
        context = {'idurl': request.REQUEST.get('idurl', 
                        installer.A().getOutput().get('idurl', '')),
                   'keysrc': request.REQUEST.get('keysrc',
                        installer.A().getOutput().get('keysrc', '')),
                   'output': out,
                   }
        if context['idurl']:
            self.data['idurl'] = str(context['idurl'])
        if context['keysrc']:
            self.data['keysrc'] = str(context['keysrc'])
        if request is None:
            return template, context, request 
        action = request.REQUEST.get('action', None)
        if action == 'load-from-file':
            try:
                self.data['keysrc'] = request.FILES['keyfilename'].read()
                context['output'] = ''
            except:
                self.data['keysrc'] = ''
                context['output'] = '<p><font color="red">error reading file</font></p>'
            if self.data['keysrc']:    
                installer.A(action, self.data)
            return None
        if action == 'paste-from-clipboard':
            installer.A(action)
            return None
        if action == 'next':
            installer.A('restore-start', self.data)
            return None 
        if action == 'back':
            installer.A(action)
            return None
        return template, context, request
    
    def renderRestorePage(self, request):
        template = 'pages/restore_identity.html'
        out = ''
        for text, color in installer.A().getOutput().get('data', []): 
            if text.strip():
                out += '     <li><font color="%s">%s</font></li>\n' % (color, text)
        if out:
            out = '    <ul>\n' + out + '    </ul>\n'
        context = {'output': out,
                   'idurl': '',
                   }
        if installer.A().state == 'RESTORED':
            context['idurl'] = my_id.getLocalID()
            self.data['idurl'] = str(context['idurl'])
        if request is None:
            return template, context, request 
        action = request.REQUEST.get('action', None)
        if action == 'next':
            installer.A(action)
            return None
        return template, context, request

    def renderWizardStartPage(self, request):
        template = 'pages/wizard_start.html'
        context = { }
        if request is None:
            return template, context, request 
        action = request.REQUEST.get('action', None)
        if action == 'next':
            install_wizard.A(action)
            return None
        if action == 'skip':
            install_wizard.A(action)
            template = 'pages/last_page.html'
        return template, context, request
    
    def renderWizardStoragePage(self, request):
        template = 'pages/wizard_storage.html'
        req = {}
        if request is not None:
            req = request.REQUEST
        self.data['customersdir'] = unicode(req.get('customersdir',
            settings.getCustomersFilesDir()))
        self.data['localbackupsdir'] = unicode(req.get('localbackupsdir',
            settings.getLocalBackupsDir()))
        self.data['restoredir'] = unicode(req.get('restoredir',
            settings.getRestoreDir()))
        self.data['needed'] = req.get('needed', self.data['needed'])
        neededV = diskspace.GetBytesFromString(self.data['needed']+' Mb',
            settings.DefaultNeededBytes())  
        self.data['donated'] = req.get('donated', self.data['donated'])
        donatedV = diskspace.GetBytesFromString(self.data['donated']+' Mb',
            settings.DefaultDonatedBytes())
        self.data['suppliers'] = req.get('suppliers', self.data['suppliers'])
        mounts = []
        freeSpaceIsOk = True
        if bpio.Windows():
            for d in bpio.listLocalDrivesWindows():
                free, total = diskusage.GetWinDriveSpace(d[0])
                if free is None or total is None:
                    continue
                color = '#ffffff'
                if self.data['customersdir'][0].upper() == d[0].upper():
                    color = '#60e060'
                    if donatedV >= free:
                        color = '#e06060'
                        freeSpaceIsOk = False
                if self.data['localbackupsdir'][0].upper() == d[0].upper():
                    color = '#60e060'
                    if neededV >= free:
                        color = '#e06060'
                        freeSpaceIsOk = False
                mounts.append((d[0:2],
                               diskspace.MakeStringFromBytes(free), 
                               diskspace.MakeStringFromBytes(total),
                               color,))
        elif bpio.Linux() or bpio.Mac():
            for mnt in bpio.listMountPointsLinux():
                free, total = diskusage.GetLinuxDriveSpace(mnt)
                if free is None or total is None:
                    continue
                color = '#ffffff'
                if bpio.getMountPointLinux(self.data['customersdir']) == mnt:
                    color = '#60e060'
                    if donatedV >= free:
                        color = '#e06060'
                        freeSpaceIsOk = False
                if bpio.getMountPointLinux(self.data['localbackupsdir']) == mnt:
                    color = '#60e060'
                    if neededV >= free:
                        color = '#e06060'
                        freeSpaceIsOk = False
                mounts.append((mnt, 
                               diskspace.MakeStringFromBytes(free), 
                               diskspace.MakeStringFromBytes(total),
                               color,))
        ok = True
        out = ''
        if not freeSpaceIsOk:
            out += '<font color=red>you do not have enough free space on the disk</font><br/>\n'
            ok = False
        if donatedV < settings.MinimumDonatedBytes():
            out += '<font color=red>you must donate at least %f MB</font><br/>\n' % (
                round(settings.MinimumDonatedBytes()/(1024.0*1024.0), 2))
            ok = False
        if not os.path.isdir(self.data['customersdir']):
            out += '<font color=red>directory %s not exist</font><br/>\n' % self.data['customersdir']
            ok = False
        if not os.access(self.data['customersdir'], os.W_OK):
            out += '<font color=red>folder %s does not have write permissions</font><br/>\n' % self.data['customersdir']
            ok = False
        if not os.path.isdir(self.data['localbackupsdir']):
            out += '<font color=red>directory %s not exist</font><br/>\n' % self.data['localbackupsdir']
            ok = False
        if not os.access(self.data['localbackupsdir'], os.W_OK):
            out += '<font color=red>folder %s does not have write permissions</font><br/>\n' % self.data['localbackupsdir']
            ok = False
        if int(self.data['suppliers']) not in settings.getECCSuppliersNumbers():
            out += '<font color=red>incorrect number of suppliers, correct values are: %s</font><br/>\n' % (
                str(settings.getECCSuppliersNumbers()).strip('[]'))
            ok = False
        context = {'output': out, 
                   'mounts': mounts, 
                   'needed': self.data['needed'],
                   'donated': self.data['donated'],
                   'localbackupsdir': self.data['localbackupsdir'],
                   'customersdir': self.data['customersdir'],
                   'restoredir': self.data['restoredir'],
                   'suppliers': self.data['suppliers'],
                   }
        if request is None:
            return template, context, request 
        action = request.REQUEST.get('action', None)
        if action == 'next':
            if ok:
                install_wizard.A(action, self.data)
            return None
        if action == 'back':
            install_wizard.A(action)
            return None
        return template, context, request

    def renderWizardContactsPage(self, request):
        template = 'pages/wizard_contacts.html'
        context = {'idurl': self.data['idurl'],
                   'name': self.data['name'],
                   'surname': self.data['surname'],
                   'nickname': self.data['nickname'],
                   }
        if request is None:
            return template, context, request 
        action = request.REQUEST.get('action', None)
        if action == 'next':
            self.data['name'] = request.REQUEST['name']
            self.data['surname'] = request.REQUEST['surname']
            self.data['nickname'] = request.REQUEST['nickname']
            install_wizard.A(action, self.data)
            return None
        if action == 'back':
            install_wizard.A(action)
            return None
        return template, context, request

    def renderLastPage(self, request):
        global _FinishedState
        global _SetupControllerObject
        if not _FinishedState:
            reactor.callLater(3, install_wizard.A, 'next')
            _FinishedState = True
        template = 'pages/last_page.html'
        context = {}
        return template, context, request
        
    
    
    