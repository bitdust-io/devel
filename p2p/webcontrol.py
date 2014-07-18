#!/usr/bin/python
#webcontrol.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

import os
import sys
import time
import locale
import pprint
import random
import webbrowser
import math
import cStringIO
import base64
import re

try:
    from twisted.internet import reactor 
except:
    sys.exit('Error initializing twisted.internet.reactor in webcontrol.py')

from twisted.internet.defer import Deferred, succeed
from twisted.web import server
from twisted.web import resource
from twisted.web import static
from twisted.web import http
from twisted.web.server import NOT_DONE_YET

#-------------------------------------------------------------------------------

import lib.misc as misc
import lib.bpio as bpio
import lib.net_misc as net_misc
import lib.settings as settings
import lib.diskspace as diskspace
import lib.dirsize as dirsize
import lib.diskusage as diskusage
import lib.commands as commands
import lib.contacts as contacts
import lib.nameurl as nameurl
import lib.crypto as crypto
import lib.schedule as schedule
import lib.automat as automat
import lib.webtraffic as webtraffic
import lib.packetid as packetid

import transport.stats as stats
import transport.callback as callback
import transport.packet_out as packet_out

import userid.id_restorer as id_restorer
import userid.propagate as propagate

import initializer
import shutdowner
import installer
import install_wizard
import network_connector
import p2p_connector
import fire_hire
import contact_status
import customers_rejector

import p2p_service
import backup_fs
import backup_matrix
import backup_control
import backup_monitor
import restore_monitor
import io_throttle
import message
import events
import ratings 

#-------------------------------------------------------------------------------

myweblistener = None
init_done = False
read_only_state = True
local_port = 0
current_url = ''
current_pagename = ''
labels = {}
menu_order = []
installing_process_str = ''
install_page_ready = True
global_version = ''
local_version = ''
revision_number = ''
root_page_src = ''
centered_page_src = ''
url_history = [] # ['/main']
pagename_history = [] # ['main']

_GUICommandCallbacks = []
_SettingsTreeNodesDict = {}
_SettingsTreeComboboxNodeLists = {}

#------------------------------------------------------------------------------

_PAGE_ROOT = ''
_PAGE_STARTING = 'starting'
_PAGE_MAIN = 'main'
_PAGE_BACKUPS = 'main'
_PAGE_MENU = 'menu'
_PAGE_CONFIRM = 'confirm'
_PAGE_BUSY = 'busy'
_PAGE_BACKUP = 'backup_'
_PAGE_BACKUP_LOCAL_FILES = 'backuplocalfiles_'
_PAGE_BACKUP_REMOTE_FILES = 'backupremotefiles_'
_PAGE_BACKUP_IMAGE = 'backupimage_'
_PAGE_BACKUP_DIAGRAM = 'backupdiagram_'
_PAGE_BACKUP_RUNNING = 'running'
_PAGE_BACKUP_RESTORING = 'restoring'
_PAGE_SUPPLIERS = 'suppliers'
_PAGE_SUPPLIER = 'supplier'
_PAGE_SUPPLIER_REMOTE_FILES = 'supplierremotefiles'
_PAGE_SUPPLIER_LOCAL_FILES = 'supplierlocalfiles'
_PAGE_SUPPLIER_CHANGE = 'supplierchange'
_PAGE_CUSTOMERS = 'customers'
_PAGE_CUSTOMER = 'customer'
_PAGE_CUSTOMER_FILES = 'customerfiles'
_PAGE_STORAGE = 'storage'
_PAGE_STORAGE_NEEDED = 'neededstorage'
_PAGE_STORAGE_DONATED = 'donatedstorage'
_PAGE_CONFIG = 'config'
_PAGE_CONTACTS = 'contacts'
_PAGE_CENTRAL = 'central'
_PAGE_SETTINGS = 'settings'
_PAGE_SETTINGS_LIST = 'settingslist'
_PAGE_SETTING_NODE = 'settingnode'
_PAGE_PRIVATE = 'private'
_PAGE_MONEY = 'money'
_PAGE_MONEY_ADD = 'moneyadd'
_PAGE_MONEY_MARKET_BUY = 'moneybuy'
_PAGE_MONEY_MARKET_SELL = 'moneysell'
_PAGE_MONEY_MARKET_LIST = 'moneylist'
_PAGE_TRANSFER = 'transfer'
_PAGE_RECEIPTS = 'receipts'
_PAGE_RECEIPT = 'receipt'
_PAGE_DIR_SELECT = 'dirselect'
_PAGE_INSTALL = 'install'
_PAGE_INSTALL_NETWORK_SETTINGS = 'installproxy'
_PAGE_UPDATE = 'update'
_PAGE_MESSAGES = 'messages'
_PAGE_MESSAGE = 'message'
_PAGE_NEW_MESSAGE = 'newmessage'
_PAGE_CORRESPONDENTS = 'correspondents'
_PAGE_SHEDULE = 'shedule'
_PAGE_BACKUP_SHEDULE = 'backup_schedule'
_PAGE_UPDATE_SHEDULE = 'updateshedule'
_PAGE_DEV_REPORT = 'devreport'
_PAGE_BACKUP_SETTINGS = 'backupsettings'
_PAGE_SECURITY = 'security'
_PAGE_NETWORK_SETTINGS = 'network'
_PAGE_DEVELOPMENT = 'development'
_PAGE_BIT_COIN_SETTINGS = 'bitcoin'
_PAGE_AUTOMATS = 'automats'
_PAGE_MEMORY = 'memory'
_PAGE_EMERGENCY = 'emergency'
_PAGE_MONITOR_TRANSPORTS = 'monitortransports'
_PAGE_TRAFFIC = 'traffic'

#------------------------------------------------------------------------------ 

_MenuItems = {
    '0|backups'             :('/'+_PAGE_MAIN,               'icons/backup01.png'),
    '1|users'               :('/'+_PAGE_SUPPLIERS,          'icons/users01.png'),
    '2|storage'             :('/'+_PAGE_STORAGE,            'icons/storage01.png'),
    '3|settings'            :('/'+_PAGE_CONFIG,             'icons/settings01.png'),
#     '4|money'               :('/'+_PAGE_MONEY,              'icons/money01.png'),
    '4|messages'            :('/'+_PAGE_MESSAGES,           'icons/messages01.png'),
    '5|friends'             :('/'+_PAGE_CORRESPONDENTS,     'icons/handshake01.png'),
    #'4|shutdown'            :('/?action=exit',              'icons/exit.png'),
    }

_SettingsItems = {
    '0|backups'             :('/'+_PAGE_BACKUP_SETTINGS,    'icons/backup-options.png'),
    '1|security'            :('/'+_PAGE_SECURITY,           'icons/private-key.png'),
    '2|network'             :('/'+_PAGE_NETWORK_SETTINGS,   'icons/network-settings.png'),
    '3|emergency'           :('/'+_PAGE_EMERGENCY,          'icons/emergency01.png'),
    '4|updates'             :('/'+_PAGE_UPDATE,             'icons/software-update.png'),
    '5|development'         :('/'+_PAGE_DEVELOPMENT,        'icons/python.png'),
    #'5|shutdown'            :('/?action=exit',              'icons/exit.png'),
    }

_MessageColors = {
    'success': 'green',
    'done': 'green',
    'failed': 'red',
    'error': 'red',
    'info': 'black',
    'warning': 'red',
    'notify': 'blue',
    }

_BackupDiagramColors = {
    'D': {'000': '#ffffff', # white | nor local, nor remote
          '100': '#d2d2d2', # gray  | only local                       
          '010': '#e2e242', # yellow| only remote, user is not here - data is not available
          '110': '#7272f2', # blue  | local and remote, but user is out 
          '001': '#ffffff', # white | nor local, nor remote, but supplier is here
          '101': '#d2d2d2', # gray  | only local and user is here
          '011': '#20b220', # green | only remote and user is here - this should be GREEN!
          '111': '#20f220', # lgreen| all is here - absolutely GREEN! 
          }, 
    'P': {'000': '#ffffff', # lets make small difference in the colors for Parity packets
          '100': '#dddddd', 
          '010': '#eded4d',
          '110': '#7d7dfd', 
          '001': '#ffffff', 
          '101': '#dddddd', 
          '011': '#20bd20', 
          '111': '#20ff20',  
          }}

_CentralStatusColors = {
    '!': 'green', 
    '=': '#4CFF00',  
    '~': '#CCAA00',
    'x': 'red', 
    '?': 'gray',
    }

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

def init(port = 6001):
    global myweblistener
    bpio.log(2, 'webcontrol.init ')

    if myweblistener:
        global local_port
        bpio.log(2, 'webcontrol.init SKIP, already started on port ' + str(local_port))
        return succeed(local_port)

    events.init(SendCommandToGUI)
    
    # links
    # transport_control.SetContactAliveStateNotifierFunc(OnAliveStateChanged)
    # p2p_service.SetTrafficInFunc(OnTrafficIn)
    # p2p_service.SetTrafficOutFunc(OnTrafficOut)
    # io_throttle.SetPacketReportCallbackFunc(OnSupplierQueuePacketCallback)
    # list_files_orator.SetRepaintFunc(OnRepaintBackups)
    callback.add_inbox_callback(OnTrafficIn)
    callback.add_finish_file_sending_callback(OnTrafficOut)
    # callback.add_queue_item_status_callback(OnPacketOut)

    def version():
        global local_version
        global revision_number
        bpio.log(6, 'webcontrol.init.version')
        if bpio.Windows() and bpio.isFrozen():
            local_version = bpio.ReadBinaryFile(settings.VersionFile())
        else:
            local_version = None
        revision_number = bpio.ReadTextFile(settings.RevisionNumberFile()).strip()

    def html():
        global root_page_src
        global centered_page_src
        bpio.log(6, 'webcontrol.init.html')

        root_page_src = '''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
<title>%(title)s</title>
<meta http-equiv="Content-Type" content="text/html; charset=%(encoding)s" />
%(reload_tag)s
</head>
<body>
%(header)s
%(align1)s
%(body)s
%(debug)s
%(align2)s
</body>
</html>'''

        centered_page_src = '''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
<title>%(title)s</title>
<meta http-equiv="Content-Type" content="text/html; charset=%(encoding)s" />
</head>
<body>
<center>
%(body)s
<font size=-3>Copyright \xa9 2014, BitPie.NET</font>
</center>
</body>
</html>'''  

    def options():
        InitSettingsTreePages()

    def site():
        bpio.log(6, 'webcontrol.init.site')
        root = resource.Resource()
        root.putChild(_PAGE_STARTING, StartingPage())
        root.putChild(_PAGE_ROOT, RootPage())
        root.putChild(_PAGE_MAIN, MainPage())
        root.putChild(_PAGE_MENU, MenuPage())
        # root.putChild(_PAGE_BUSY, BusyPage())
        root.putChild(_PAGE_INSTALL, InstallPage())
        root.putChild(_PAGE_INSTALL_NETWORK_SETTINGS, InstallNetworkSettingsPage())
        root.putChild(_PAGE_SUPPLIERS, SuppliersPage())
        root.putChild(_PAGE_CUSTOMERS, CustomersPage())
        root.putChild(_PAGE_STORAGE, StoragePage())
        root.putChild(_PAGE_CONFIG, ConfigPage())
        root.putChild(_PAGE_BACKUP_SETTINGS, BackupSettingsPage())
        # root.putChild(_PAGE_UPDATE, UpdatePage())
        root.putChild(_PAGE_SETTINGS, SettingsPage())
        root.putChild(_PAGE_SETTINGS_LIST, SettingsListPage())
        root.putChild(_PAGE_SECURITY, SecurityPage())
        root.putChild(_PAGE_NETWORK_SETTINGS, NetworkSettingsPage())
        # root.putChild(_PAGE_MONEY, MoneyPage())
        # root.putChild(_PAGE_MONEY_ADD, MoneyAddPage())
        # root.putChild(_PAGE_MONEY_MARKET_BUY, MoneyMarketBuyPage())
        # root.putChild(_PAGE_MONEY_MARKET_SELL, MoneyMarketSellPage())
        # root.putChild(_PAGE_MONEY_MARKET_LIST, MoneyMarketListPage())
        # root.putChild(_PAGE_TRANSFER, TransferPage())
        # root.putChild(_PAGE_RECEIPTS, ReceiptsPage())
        root.putChild(_PAGE_MESSAGES, MessagesPage())
        root.putChild(_PAGE_NEW_MESSAGE, NewMessagePage())
        root.putChild(_PAGE_CORRESPONDENTS, CorrespondentsPage())
        # root.putChild(_PAGE_BACKUP_SHEDULE, BackupShedulePage())
        # root.putChild(_PAGE_UPDATE_SHEDULE, UpdateShedulePage())
        root.putChild(_PAGE_DEV_REPORT, DevReportPage())
        root.putChild(_PAGE_DEVELOPMENT, DevelopmentPage())
        # root.putChild(_PAGE_BIT_COIN_SETTINGS, BitCoinSettingsPage())
        root.putChild(_PAGE_AUTOMATS, AutomatsPage())
        root.putChild(_PAGE_MEMORY, MemoryPage())
        root.putChild(_PAGE_EMERGENCY, EmergencyPage())
        root.putChild(_PAGE_MONITOR_TRANSPORTS, MonitorTransportsPage())
        root.putChild(_PAGE_TRAFFIC, TrafficPage())
        root.putChild(_PAGE_CONFIRM, ConfirmPage())
        root.putChild(settings.IconFilename(), static.File(settings.IconFilename()))
        root.putChild('icons', static.File(settings.IconsFolderPath()))
        return LocalSite(root)

    def done(x):
        global local_port
        local_port = int(x)
        bpio.WriteFile(settings.LocalPortFilename(), str(local_port))
        bpio.log(4, 'webcontrol.init.done local server started on port %d' % local_port)

    def start_listener(site):
        bpio.log(6, 'webcontrol.start_listener')
        def _try(site, result):
            global myweblistener
            port = random.randint(6001, 6999)
            bpio.log(4, 'webcontrol.init.start_listener._try port=%d' % port)
            try:
                l = reactor.listenTCP(port, site)
            except:
                bpio.log(4, 'webcontrol.init.start_listener._try it seems port %d is busy' % port)
                l = None
            if l is not None:
                myweblistener = l
                result.callback(port)
                return
            reactor.callLater(1, _try, site, result)

        result = Deferred()
        reactor.callLater(0, _try, site, result)
        return result

    def run(site):
        bpio.log(6, 'webcontrol.init.run')
        d = start_listener(site)
        d.addCallback(done)
        return d

    version()
    html()
    options()
    s = site()
    d = run(s)
    return d

def show(x=None):
    global local_port
    if bpio.Linux() and not bpio.X11_is_running():
        bpio.log(0, 'X11 is not running, can not start BitPie.NET GUI')
        return
    if local_port == 0:
        try:
            local_port = int(bpio.ReadBinaryFile(settings.LocalPortFilename()))
        except:
            pass
    bpio.log(2, 'webcontrol.show local port is %s' % str(local_port))
    if not local_port:
        bpio.log(4, 'webcontrol.show ERROR can not read local port number')
        return
    appList = bpio.find_process(['bpgui.', ])
    if len(appList):
        bpio.log(2, 'webcontrol.show SKIP, we found another bpgui process running at the moment, pid=%s' % appList)
        SendCommandToGUI('raise')
        return
    try:
        if bpio.Windows():
            if bpio.isFrozen():
                pypath = os.path.abspath('bpgui.exe')
                os.spawnv(os.P_DETACH, pypath, ('bpgui.exe',))
            else:
                pypath = sys.executable
                os.spawnv(os.P_DETACH, pypath, ('python', 'bpgui.py',))
        else:
            pid = os.fork()
            if pid == 0:
                if bpio.Debug(30):
                    os.execlp('python', 'python', 'bpgui.py', 'logs')
                else:
                    os.execlp('python', 'python', 'bpgui.py',)
    except:
        bpio.exception()


def ready(state=True):
    global init_done
    init_done = state
    bpio.log(4, 'webcontrol.ready is ' + str(init_done))


def kill():
    bpio.log(2, 'webcontrol.kill')
    total_count = 0
    while True:
        count = 0
        bpio.log(2, 'webcontrol.kill do search for "bpgui." in the processes list')
        appList = bpio.find_process(['bpgui.', ])
        for pid in appList:
            count += 1
            bpio.log(2, 'webcontrol.kill want to stop pid %d' % pid)
            bpio.kill_process(pid)
        if len(appList) == 0:
            bpio.log(2, 'webcontrol.kill no more "bpgui." processes found')
            return 0
        total_count += 1
        if total_count > 3:
            bpio.log(2, 'webcontrol.kill ERROR: some "bpgui." processes found, but can not stop it')
            bpio.log(2, 'webcontrol.kill may be we do not have permissions to stop them?')
            return 1
        time.sleep(1)
    return 1


def shutdown():
    global myweblistener
    bpio.log(2, 'webcontrol.shutdown')
    result = Deferred()
    def _kill(x, reslt):
        bpio.log(2, 'webcontrol.shutdown._kill')
        res = kill()
        result.callback(res)
        return res
    if myweblistener is not None:
        d = myweblistener.stopListening()
        myweblistener = None
        if d: 
            d.addBoth(_kill, result)
        else:
            result.callback(1)
    else:
        result.callback(1)
    return result

#------------------------------------------------------------------------------ 

def currentVisiblePageName():
    global current_pagename
    return current_pagename

def currentVisiblePageUrl():
    global current_url
    return current_url

#------------------------------------------------------------------------------

def arg(request, key, default = ''):
    if request.args.has_key(key):
        return request.args[key][0]
    return default

def hasArg(request, key):
    return request.args.has_key(key)

def iconurl(request, icon_path):
    # return 'memory:'+icon_name
    # path = 'icons/' + icon_name
    # if icon_name == _PAGE_BACKUP_IMAGE:
    #     path = _PAGE_BACKUP_IMAGE
    if icon_path.startswith('icons/'):
        return 'memory:'+icon_path[6:]
    else:
        return 'http://%s:%s/%s' % (request.getHost().host, str(request.getHost().port), icon_path)

def confirmurl(request, yes=None, no=None, text='', back='', args=None):
    param = str((
        misc.pack_url_param(yes if yes else request.path),
        misc.pack_url_param(no if no else request.path),
        misc.pack_url_param(text),
        back if back else request.path))
    lnk = '%s?param=%s' % ('/'+_PAGE_CONFIRM, base64.urlsafe_b64encode(param))
    if args is not None:
        lnk += '&args=%s' % base64.urlsafe_b64encode(str(args))
    return lnk

def help_url(page_name, base_url='http://bitpie.net/gui.html'):
    return base_url + '#' + { _PAGE_MAIN: 'main', }.get(page_name, '')

#------------------------------------------------------------------------------

#possible arguments are: body, back, next, home, title, align
def html(request, **kwargs):
    src = html_from_args(request, **kwargs)
    request.write(str(src))
    request.finish()
    return NOT_DONE_YET

def html_from_args(request, **kwargs):
    d = {}
    d.update(kwargs)
    return html_from_dict(request, d)

def html_from_dict(request, d):
    global root_page_src
    global local_version
    global global_version
    global url_history
    global pagename_history
    if not d.has_key('encoding'):
        d['encoding'] = locale.getpreferredencoding()
    if not d.has_key('body'):
        d['body'] = ''
    if d.has_key('back') and d['back'] in [ 'none', '' ]:
        d['back'] = '&nbsp;'
    if not d.has_key('back'):
        back = ''
        if back == '' and len(url_history) > 0:
            url = url_history[-1]
            if url != request.path:
                back = url
        if back != '':
            if back == 'none':
                d['back'] = '&nbsp;'
            else: 
                d['back'] = '<a href="%s">[back]</a>' % back
        else:
            d['back'] = '&nbsp;'
    else:
        if d['back'] != '&nbsp;' and d['back'].count('href=') == 0:
            d['back'] = '<a href="%s">[back]</a>' % d['back']
    if not d.has_key('next'):
        d['next'] = '&nbsp;'
    else:
        if d['next'] != '' and d['next'].count('href=') == 0:
            if d['next'] == request.path:
                d['next'] = '&nbsp;'
            else:
                d['next'] = '<a href="%s">[next]</a>' % d['next']
    if not d.has_key('home'):
        d['home'] = '<a href="%s">[menu]</a>' % ('/'+_PAGE_MENU)
    else:
        if d['home'] == '':
            d['home'] = '&nbsp;'
    if bpio.Windows() and bpio.isFrozen():
        if global_version != '' and global_version != local_version:
            if request.path != '/'+_PAGE_UPDATE: 
                d['home'] += '&nbsp;&nbsp;&nbsp;<a href="%s">[update software]</a>' % ('/'+_PAGE_UPDATE)
    d['refresh'] = '<a href="%s">refresh</a>' % request.path
    if d.has_key('reload'):
        d['reload_tag'] = '<meta http-equiv="refresh" content="%s">' % d.get('reload', '600')
    else:
        d['reload_tag'] = ''
    if not d.has_key('debug'):
        if bpio.Debug(24):
            d['debug'] = '<br><br><br>request.args: '+str(request.args) + '\n<br>\n'
            d['debug'] += 'request.path: ' + str(request.path) + '<br>\n'
            d['debug'] += 'request.getClientIP: ' + str(request.getClientIP()) + '<br>\n'
            d['debug'] += 'request.getHost: ' + str(request.getHost()) + '<br>\n'
            d['debug'] += 'request.getRequestHostname: ' + str(request.getRequestHostname()) + '<br>\n'
            if bpio.Debug(30):
                d['debug'] += 'sys.modules:<br><pre>%s</pre><br>\n'+pprint.pformat(sys.modules) + '<br>\n'
        else:
            d['debug'] = ''
    d['title'] = 'BitPie.NET'
    if d.has_key('window_title'):
        d['title'] = d['window_title']
    if d.has_key('align'):
        d['align1'] = '<%s>' % d['align']
        d['align2'] = '</%s>' % d['align']
    else:
        d['align1'] = '<center>'
        d['align2'] = '</center>'
    if not d.has_key('header'):
        d['header'] = '''<table width="100%%" align=center cellspacing=0 cellpadding=0><tr>
<td align=left width=50 nowrap>%s</td>
<td>&nbsp;</td>
<td align=center width=50 nowrap>%s</td>
<td>&nbsp;</td>
<td align=right width=50 nowrap>%s</td>
</tr></table>\n''' % (d['back'], d['home'], d['next'])
    return str(root_page_src % d)

def html_centered_src(d, request):
    global centered_page_src
    if not d.has_key('encoding'):
        d['encoding'] = locale.getpreferredencoding()
#    if not d.has_key('iconfile'):
#        d['iconfile'] = '/' + settings.IconFilename()
#    if not d.has_key('reload') or d['reload'] == '':
#        d['reload_tag'] = ''
#    else:
#        d['reload_tag'] = '<meta http-equiv="refresh" content="%s" />' % d.get('reload', '600')
#    if d.has_key('noexit'):
#        d['exit'] = ''
#    else:
#        d['exit'] = '<div style="position: absolute; right:0px; padding: 5px;"><a href="?action=exit">Exit</a></div>'
    if not d.has_key('title'):
        d['title'] = 'BitPie.NET'
    if not d.has_key('body'):
        d['body'] = ''
    return centered_page_src % d


#    'success': 'green',
#    'done': 'green',
#    'failed': 'red',
#    'error': 'red',
#    'info': 'black',
#    'warning': 'red',
#    'notify': 'blue',
def html_message(text, typ='info'):
    global _MessageColors
    return'<font color="%s">%s</font>\n' % (_MessageColors.get(typ, 'black'), text)

def html_comment(text):
    return '<!--[begin] %s [end]-->\n' % text

#-------------------------------------------------------------------------------

def SetReadOnlyState(state):
    global read_only_state
    bpio.log(12, 'webcontrol.SetReadOnlyState ' + str(state))
    read_only_state = not state

def ReadOnly():
    # return p2p_connector.A().state not in ['CONNECTED', 'DISCONNECTED', 'INCOMMING?']
    # return p2p_connector.A().state in ['TRANSPORTS', 'NETWORK?']
    return False

def GetGlobalState():
    return 'unknown'

def check_install():
    return misc.isLocalIdentityReady() and crypto.isMyLocalKeyReady()

#------------------------------------------------------------------------------

def OnGlobalStateChanged(state):
    SendCommandToGUI('BITPIE-SERVER:' + state)
    if currentVisiblePageName() == _PAGE_STARTING:
        SendCommandToGUI('update')
#    elif currentVisiblePageUrl().count(_PAGE_SETTINGS):
#        SendCommandToGUI('update')

def OnSingleStateChanged(index, id, name, new_state):
    SendCommandToGUI('automat %s %s %s %s' % (str(index), id, name, new_state))

def OnGlobalVersionReceived(txt):
    bpio.log(4, 'webcontrol.OnGlobalVersionReceived ' + txt)
    global global_version
    global local_version
    if txt == 'failed':
        return
    global_version = txt
    bpio.log(6, '  global:' + str(global_version))
    bpio.log(6, '  local :' + str(local_version))
    SendCommandToGUI('version: ' + str(global_version) + ' ' + str(local_version))

def OnAliveStateChanged(idurl):
    if contacts.IsSupplier(idurl):
        if currentVisiblePageName() in [_PAGE_SUPPLIERS, 
                                        _PAGE_SUPPLIER, 
                                        _PAGE_SUPPLIER_REMOTE_FILES, 
                                        _PAGE_MAIN, 
                                        _PAGE_BACKUP,
                                        _PAGE_BACKUP_DIAGRAM,
                                        _PAGE_BACKUP_LOCAL_FILES,
                                        _PAGE_BACKUP_REMOTE_FILES,]:
            SendCommandToGUI('update')
    if contacts.IsCustomer(idurl):
        if currentVisiblePageName() in [_PAGE_CUSTOMERS, _PAGE_CUSTOMER]:
            SendCommandToGUI('update')
    if contacts.IsCorrespondent(idurl):
        if currentVisiblePageName() == _PAGE_CORRESPONDENTS:
            SendCommandToGUI('update')

def OnInitFinalDone():
    if currentVisiblePageName() in [_PAGE_MAIN,]:
        SendCommandToGUI('update')

def OnBackupStats(backupID):
    if currentVisiblePageName() in [ _PAGE_BACKUP,
                                     _PAGE_BACKUP_DIAGRAM,
                                     _PAGE_BACKUP_LOCAL_FILES,
                                     _PAGE_BACKUP_REMOTE_FILES,]:
        if currentVisiblePageUrl().count(backupID.replace('/','_')):         
            SendCommandToGUI('update')
    elif currentVisiblePageName() == _PAGE_MAIN:
        SendCommandToGUI('update')

def OnBackupDataPacketResult(backupID, packet):
    if currentVisiblePageName() in [ _PAGE_BACKUP,
                                     _PAGE_BACKUP_DIAGRAM,
                                     _PAGE_BACKUP_LOCAL_FILES,
                                     _PAGE_BACKUP_REMOTE_FILES,]:
        if currentVisiblePageUrl().count(backupID.replace('/','_')):
            SendCommandToGUI('update')

def OnBackupProcess(backupID, packet=None):
    if currentVisiblePageName() in [ _PAGE_BACKUP,
                                     _PAGE_BACKUP_DIAGRAM,
                                     _PAGE_BACKUP_LOCAL_FILES,
                                     _PAGE_BACKUP_REMOTE_FILES,]:
        if currentVisiblePageUrl().count(backupID.replace('/','_')):
            SendCommandToGUI('update')
    if currentVisiblePageName() in [_PAGE_MAIN]:
        SendCommandToGUI('update')

def OnRestoreProcess(backupID, SupplierNumber, packet):
    #bpio.log(18, 'webcontrol.OnRestorePacket %s %s' % (backupID, SupplierNumber))
    if currentVisiblePageName() in [ _PAGE_BACKUP,
                                     _PAGE_BACKUP_DIAGRAM,
                                     _PAGE_BACKUP_LOCAL_FILES,
                                     _PAGE_BACKUP_REMOTE_FILES,]:
        if currentVisiblePageUrl().count(backupID.replace('/','_')):
            SendCommandToGUI('update')
            
def OnRestoreSingleBlock(backupID, block):
    if currentVisiblePageName() in [ _PAGE_BACKUP,
                                     _PAGE_BACKUP_DIAGRAM,
                                     _PAGE_BACKUP_LOCAL_FILES,
                                     _PAGE_BACKUP_REMOTE_FILES,]:
        if currentVisiblePageUrl().count(backupID.replace('/','_')):
            SendCommandToGUI('update')

def OnRestoreDone(backupID, result):
    #bpio.log(18, 'webcontrol.OnRestoreDone ' + backupID)
    if currentVisiblePageName() in [ _PAGE_BACKUP,
                                     _PAGE_BACKUP_DIAGRAM,
                                     _PAGE_BACKUP_LOCAL_FILES,
                                     _PAGE_BACKUP_REMOTE_FILES,]:
        if currentVisiblePageUrl().count(backupID.replace('/','_')):
        # SendCommandToGUI('open %s?action=restore.done&result=%s' % ('/'+_PAGE_MAIN+'/'+backupID.replace('/','_'), result))
            SendCommandToGUI('update')
    elif currentVisiblePageName() in [_PAGE_MAIN,]:
        SendCommandToGUI('update')

def OnListSuppliers():
    if currentVisiblePageName() == _PAGE_SUPPLIERS:
        SendCommandToGUI('update')

def OnListCustomers():
    #bpio.log(18, 'webcontrol.OnListCustomers ')
    if currentVisiblePageName() == _PAGE_CUSTOMERS:
        SendCommandToGUI('update')
        
#def OnMarketList():
#    if currentVisiblePageName() == _PAGE_MONEY_MARKET_LIST:
#        SendCommandToGUI('update')
        
# msg is (sender, to, subject, dt, body)
def OnIncommingMessage(packet, msg):
    bpio.log(6, 'webcontrol.OnIncommingMessage')

def OnTrafficIn(newpacket, info, status, message):
    if message:
        message = message.replace(' ', '_')
    if newpacket is None:
        SendCommandToGUI(
            'packet in Unknown from (%s://%s) %s 0 %s "%s"' % (
                 info.proto, info.host, message, status, message))
    else:
        packet_from = newpacket.OwnerID
        if newpacket.OwnerID == misc.getLocalID() and newpacket.Command == commands.Data():
            packet_from = newpacket.RemoteID
        if newpacket.Command == commands.Fail():
            message = newpacket.Payload.replace(' ', '_')
        SendCommandToGUI(
            'packet in %s from %s (%s://%s) %s %d %s "%s"' % (
                newpacket.Command, nameurl.GetName(packet_from),
                info.proto, info.host, newpacket.PacketID,
                len(newpacket), status, message))

def OnPacketOut(pkt_out, status, message):
    if status == 'finished':
        return
    if message:
        message = message.replace(' ', '_')
    addr = ''
    error_message = ''
    size = 0
    for result in pkt_out.results:
        proto, host, status, size, description, error_message = result
        addr += proto + ' '
        if error_message:
            error_message = error_message.replace(' ', '_')
    SendCommandToGUI(
        'packet out %s to %s (%s) %s %d %s "%s"' % (
            pkt_out.outpacket.Command, nameurl.GetName(pkt_out.remote_idurl),
            addr, pkt_out.outpacket.PacketID, size, status, 
            error_message or message or ''))

#    for result in pkt_out.results:
#        proto, host, status, size, description, error_message = result
#        if error_message:
#            error_message = error_message.replace(' ', '_')
#        SendCommandToGUI(
#            'packet out %s to %s (%s://%s) %s %d %s "%s"' % (
#                pkt_out.outpacket.Command, nameurl.GetName(pkt_out.remote_idurl),
#                proto, host, pkt_out.outpacket.PacketID, size, status, 
#                error_message or message or ''))

def OnTrafficOut(pkt_out, item, status, size, message):
    # if status != 'finished':
    #     return
    if message:
        message = message.replace(' ', '_')    
    SendCommandToGUI(
        'packet out %s to %s (%s://%s) %s %d %s "%s"' % (
            pkt_out.outpacket.Command, nameurl.GetName(pkt_out.remote_idurl),
            item.proto, item.host, pkt_out.outpacket.PacketID, pkt_out.filesize,
            status, message))

#def OnSupplierQueuePacketCallback(sendORrequest, supplier_idurl, packetid, result):
#    SendCommandToGUI('queue %s %s %d %d %s %s' % (
#        sendORrequest, nameurl.GetName(supplier_idurl), 
#        contacts.numberForSupplier(supplier_idurl), contacts.numSuppliers(),
#        packetid, result))

def OnTrayIconCommand(cmd):
    if cmd == 'exit':
        SendCommandToGUI('exit')
        #reactor.callLater(0, init_shutdown.shutdown_exit)
        shutdowner.A('stop', 'exit')

    elif cmd == 'restart':
        SendCommandToGUI('exit')
        #reactor.callLater(0, init_shutdown.shutdown_restart, 'show')
        appList = bpio.find_process(['bpgui.',])
        if len(appList) > 0:
            shutdowner.A('stop', 'restartnshow') # ('restart', 'show'))
        else:
            shutdowner.A('stop', 'restart') # ('restart', ''))
        
    elif cmd == 'reconnect':
        network_connector.A('reconnect')

    elif cmd == 'show':
        show()

    elif cmd == 'hide':
        SendCommandToGUI('exit')
        
    elif cmd == 'toolbar':
        SendCommandToGUI('toolbar')

    else:
        bpio.log(2, 'webcontrol.OnTrayIconCommand WARNING: ' + str(cmd))

#def OnInstallMessage(txt):
#    global installing_process_str
#    bpio.log(6, 'webcontrol.OnInstallMessage %s' % txt)
#    installing_process_str += txt + '\n'
#    #installing_process_str = txt
#    if currentVisiblePageName() == _PAGE_INSTALL:
#        SendCommandToGUI('update')

def OnUpdateInstallPage():
    bpio.log(6, 'webcontrol.OnUpdateInstallPage')
    if currentVisiblePageName() in [_PAGE_INSTALL,]:
        SendCommandToGUI('open /'+_PAGE_INSTALL)

def OnUpdateStartingPage():
    if currentVisiblePageName() in [_PAGE_STARTING,]:
        SendCommandToGUI('open /'+_PAGE_STARTING)

def OnReadLocalFiles():
    if currentVisiblePageName() in [_PAGE_MAIN,
                                    _PAGE_BACKUP,
                                    _PAGE_SUPPLIER_LOCAL_FILES,]:
        SendCommandToGUI('update')

#def OnInboxReceipt(newpacket):
#    if currentVisiblePageName() in [_PAGE_MONEY, 
#                                    _PAGE_MONEY_ADD, ]:
#        SendCommandToGUI('update')

#def OnBitCoinUpdateBalance(balance):
#    if currentVisiblePageName() in [_PAGE_MONEY,]:
#        if not currentVisiblePageUrl().count('?'):
#            SendCommandToGUI('update')

#-------------------------------------------------------------------------------

def SendCommandToGUI(cmd):
    global _GUICommandCallbacks
    if isinstance(cmd, unicode):
        bpio.log(2, 'SendCommandToGUI WARNING cmd is unicode' + str(cmd))
    try:
        for f in _GUICommandCallbacks:
            f(str(cmd))
    except:
        bpio.exception()
        return False
    return True

#------------------------------------------------------------------------------

class LocalHTTPChannel(http.HTTPChannel):
    controlState = False
    def connectionMade(self):
        return http.HTTPChannel.connectionMade(self)

    def lineReceived(self, line):
        global _GUICommandCallbacks
        if line.strip().upper() == 'BITPIE-VIEW-REQUEST':
            bpio.log(2, 'GUI: view request received from ' + str(self.transport.getHost()))
            self.controlState = True
            _GUICommandCallbacks.append(self.send)
            SendCommandToGUI('BITPIE-SERVER:' + GetGlobalState())
            for index, object in automat.objects().items():
                SendCommandToGUI('automat %s %s %s %s' % (str(index), object.id, object.name, object.state))
        else:
            return http.HTTPChannel.lineReceived(self, line)

    def send(self, cmd):
        self.transport.write(cmd+'\r\n')

    def connectionLost(self, reason):
        global _GUICommandCallbacks
        if self.controlState:
            try:
                _GUICommandCallbacks.remove(self.send)
            except:
                bpio.exception()
            if not check_install() or GetGlobalState().lower().startswith('install'):
                reactor.callLater(0, shutdowner.A, 'ready')
                reactor.callLater(1, shutdowner.A, 'stop', 'exit')


class LocalSite(server.Site):
    protocol = LocalHTTPChannel

    def buildProtocol(self, addr):
        if addr.host != '127.0.0.1':
            bpio.log(2, 'webcontrol.LocalSite.buildProtocol WARNING NETERROR connection from ' + str(addr))
            return None
        try:
            res = server.Site.buildProtocol(self, addr)
        except:
            res = None
            bpio.exception()
        return res

#------------------------------------------------------------------------------ 

# This is the base class for all HTML pages
class Page(resource.Resource):
    # each page have unique name
    pagename = ''
    # we will save the last requested url
    # we want to know where is user at the moment
    def __init__(self):
        resource.Resource.__init__(self)
        self.created()

    # Every HTTP request by Web Browser will go here
    # So we can check everything in one place
    def render(self, request):
        global current_url
        global current_pagename
        global init_done
        global url_history
        global pagename_history

        # bpio.log(14, 'webcontrol.Page.render request=%s current_pagename=%s current_url=%s' % (request.path, current_pagename, current_url))
        
        if self.pagename in [_PAGE_MONITOR_TRANSPORTS, _PAGE_TRAFFIC]:
            return self.renderPage(request)

#        if len(pagename_history) == 0:
#            pagename_history.append(self.pagename)
#            url_history.append(request.path)
        
        # check if we refresh the current page
        if self.pagename != current_pagename or request.path != current_url: 
            # check if we are going back
            if len(pagename_history) > 0 and current_pagename != self.pagename and url_history[-1] == request.path:
                pagename_history.pop()
                url_history.pop()
            # if not going back - remember this place in history
            else:
                if current_pagename != '':
                    pagename_history.append(current_pagename)
                    url_history.append(current_url)
                    
        # remove old history
        while len(pagename_history) > 20:
            pagename_history.pop(0)
            url_history.pop(0)
            
        current_url = request.path
        current_pagename = self.pagename

        if arg(request, 'action') == 'exit': #  and not bpupdate.is_running():
            bpio.log(2, 'webcontrol.Page.render action is [exit]')
            reactor.callLater(0, shutdowner.A, 'stop', 'exit')
            d = {}
            d['body'] = ('<br>' * 10) + '\n<h1>Good Luck!<br><br>See you</h1>\n'
            print >>request, html_centered_src(d, request)
            request.finish()
            return NOT_DONE_YET

        elif arg(request, 'action') == 'restart': #  and not bpupdate.is_running():
            bpio.log(2, 'webcontrol.Page.render action is [restart]')
            appList = bpio.find_process(['bpgui.',])
            if len(appList) > 0:
                bpio.log(2, 'webcontrol.Page.render found bpgui process, add param "show"')
                reactor.callLater(0, shutdowner.A, 'stop', 'restartnshow') # ('restart', 'show'))
            else:
                bpio.log(2, 'webcontrol.Page.render did not found bpgui process')
                reactor.callLater(0, shutdowner.A, 'stop', 'restart')
            d = {}
            d['body'] = ('<br>' * 10) + '\n<h1>Restarting BitPie.NET</h1>\n'
            print >>request, html_centered_src(d, request)
            request.finish()
            return NOT_DONE_YET
        
        elif arg(request, 'action') == 'reconnect':
            reactor.callLater(0, network_connector.A,  'reconnect',)
            d = {}
            d['body'] = ('<br>' * 10) + '\n<h1>Reconnecting...</h1>\n'
            print >>request, html_centered_src(d, request)
            request.finish()
            return NOT_DONE_YET

        if not init_done:
            # init_shutdown did not finished yet
            # we should stop here at this moment
            # need to wait till all needed modules was initialized.
            # we want to call ".init()" method for all of them
            # let's show "Please wait ..." page here
            # typically we should not fall in this situation
            # because all local initializations should be done very fast
            # we will open the web browser only AFTER init_shutdown was finished
            bpio.log(4, 'webcontrol.Page.render will show "Please wait" page')
            d = {}
            d['reload'] = '1'
            d['body'] = '<h1>Please wait ...</h1>'
            print >>request, html_centered_src(d, request)
            request.finish()
            return NOT_DONE_YET

        # BitPie.NET is not installed or broken somehow
        if not check_install():
            # page requested is not the install page
            # we do not need this in that moment because bpmain is not installed
            if self.pagename not in [_PAGE_INSTALL, _PAGE_INSTALL_NETWORK_SETTINGS]:
                bpio.log(4, 'webcontrol.Page.render redirect to the page %s' % _PAGE_INSTALL)
                request.redirect('/'+_PAGE_INSTALL)
                request.finish()
                return NOT_DONE_YET

            # current page is install page - okay, show it
            return self.renderPage(request)

        # BitPie.NET is installed, show the requested page normally
        try:
            ret = self.renderPage(request)
        except:
            exc_src = '<center>\n'
            exc_src += '<h1>Exception on page "%s"!</h1>\n' % self.pagename
            exc_src += '<table width="400px"><tr><td>\n'
            exc_src += '<div align=left>\n'
            exc_src += '<code>\n'
            e = bpio.formatExceptionInfo()
            e = e.replace(' ', '&nbsp;').replace("'", '"')
            e = e.replace('<', '[').replace('>', ']').replace('\n', '<br>\n')
            exc_src += e
            exc_src += '</code>\n</div>\n</td></tr></table>\n'
            exc_src += '</center>'
            s = html_from_args(request, body=str(exc_src), back=arg(request, 'back', '/'+_PAGE_MAIN))
            request.write(s)
            request.finish()
            ret = NOT_DONE_YET
            bpio.exception()

        return ret

    def renderPage(self, request):
        bpio.log(4, 'webcontrol.Page.renderPage WARNING base page requested, but should not !')
        return html(request, body='ERROR!')

    def created(self):
        pass


class ConfirmPage(Page):
    pagename = _PAGE_CONFIRM
    param = ''
    def renderPage(self, request):
        back = arg(request, 'back', '/'+_PAGE_MAIN)
        confirm = arg(request, 'confirm')
        self.param = arg(request, 'param', self.param)
        decoded = base64.urlsafe_b64decode(self.param)
        splited = eval(decoded)
        (urlyes, urlno, text, back) = splited
        urlyes = misc.unpack_url_param(urlyes)
        urlno = misc.unpack_url_param(urlno)
        text = misc.unpack_url_param(text)
        text = re.sub('\%\(option\:(.+?)\)s', lambda m: settings.uconfig(m.group(1)), text)
        args = arg(request, 'args')
        if args:
            args = base64.urlsafe_b64decode(args)
            args = eval(args)
            text = text % args
        if confirm == 'yes':
            request.redirect(urlyes)
            request.finish()
            return NOT_DONE_YET
        elif confirm == 'no':
            request.redirect(urlno)
            request.finish()
            return NOT_DONE_YET
        src = ''
        src += '<br><br><br><br>\n'
        src += '<table width=70%><tr><td align=center>\n'
        src += '<p>%s</p><br>\n' % text
        src += '</td></tr>\n<tr><td align=center>\n'
        src += '<a href="%s?confirm=yes&param=%s"><b>YES</b></a>\n' % (
            request.path, self.param)
        src += '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        src += '<a href="%s?confirm=no&param=%s"><b>NO</b></a>\n' % (
            request.path, self.param,)
        src += '</td></tr></table>\n'
        return html(request, body=src, title='', home='', back=back)
            

class StartingPage(Page):
    pagename = _PAGE_STARTING
    labels = {
        'AT_STARTUP':          'starting',
        'LOCAL':               'local settings initialization',
        'CONTACTS':            'contacts initialization',
        'CONNECTION':          'preparing connections',
        'MODULES':             'starting modules', }

    def __init__(self):
        Page.__init__(self)
        self.state2page = {
            'AT_STARTUP':   self.renderStartingPage,
            'LOCAL':        self.renderStartingPage,
            'INSTALL':      self.renderInstallPage,
            'CONTACTS':     self.renderStartingPage,
            'CONNECTION':   self.renderStartingPage,
            'MODULES':      self.renderStartingPage,
            'READY':        self.renderStartingPage,
            'STOPPING':     self.renderStoppingPage,
            'EXIT':         self.renderStoppingPage, }

    def renderPage(self, request):
        current_state = initializer.A().state
        page = self.state2page.get(current_state, None)
        if page is None:
            raise Exception('incorrect state in initializer(): %s' % current_state)
        return page(request)

    def renderStartingPage(self, request):
        src = '<br>' * 3 + '\n'
        src += '<h1>launching BitPie.NET</h1>\n'
        src += '<table width="400px"><tr><td>\n'
        src += '<div align=left>'
        src += 'Now the program is starting a transport protocols.<br><br>\n'
        src += 'You connect to a Central server, which will prepare a list of suppliers for you.<br><br>\n'
        src += 'These users will store your data, and BitPie.NET will monitor every piece of your remote data.<br><br>\n'
        src += 'That is, first you have to wait for a response from the Central server and then connect with suppliers.<br><br>\n'
        src += 'All process may take a while.\n'
        src += '</div>'
        src += '</td></tr></table>\n'
        src += '<br><br>\n'
        disabled = ''
        button =     '      GO      '
        if initializer.A().state != 'READY':
            disabled = 'disabled'
            button = 'connecting ...'
        src += '<form action="%s" method="get">\n' % ('/'+_PAGE_MAIN)
        src += '<input type="submit" name="submit" value=" %s " %s />\n' % (button, disabled)
        src += '</form>'
        return html(request, body=src, title='launching', home='', back='', reload='1')

    def renderInstallPage(self, request):
        request.redirect('/'+_PAGE_INSTALL)
        request.finish()
        return NOT_DONE_YET

    def renderStoppingPage(self, request):
        src = ('<br>' * 8) + '\n<h1>Good Luck!<br><br>See you</h1>\n'
        return html(request, body=src, title='good luck!', home='', back='')


class InstallPage(Page):
    pagename = _PAGE_INSTALL
    def __init__(self):
        Page.__init__(self)
        self.state2page = {
            'READY':        self.renderSelectPage,
            'WHAT_TO_DO?':  self.renderSelectPage,
            'INPUT_NAME':   self.renderInputNamePage,
            'REGISTER':     self.renderRegisterNewUserPage,
            'AUTHORIZED':   self.renderRegisterNewUserPage,
            'LOAD_KEY':     self.renderLoadKeyPage,
            'RECOVER':      self.renderRestorePage,
            'WIZARD':       self.renderWizardPage,
            'DONE':         self.renderLastPage, }
        self.wizardstate2page = {
            'READY':        self.renderWizardSelectRolePage,
            'JUST_TRY_IT':  self.renderWizardJustTryItPage,
            'BETA_TEST':    self.renderWizardBetaTestPage,
            'DONATOR':      self.renderWizardDonatorPage,
            'FREE_BACKUPS': self.renderWizardFREEBackupsPage,
            'MOST_SECURE':  self.renderWizardMostSecurePage,
            'STORAGE':      self.renderWizardStoragePage,
            'CONTACTS':     self.renderWizardContactsPage,
            'LAST_PAGE':    self.renderLastPage,
            'DONE':         self.renderLastPage, }
        self.login = ''
        self.pksize = settings.DefaultPrivateKeySize()
        self.needed = ''
        self.donated = ''
        self.bandin = ''
        self.bandout = ''
        self.customersdir = settings.getCustomersFilesDir()
        self.localbackupsdir = settings.getLocalBackupsDir()
        self.restoredir = settings.getRestoreDir()
        self.showall = 'false'
        self.idurl = ''
        self.keysrc = ''
        self.name = ''
        self.surname = ''
        self.nickname = ''
        self.betatester = 'True'
        self.development = 'True'
        self.debuglevel = 8
        self.email = ''
        self.role = 1

    def renderPage(self, request):
        current_state = installer.A().state
        page = self.state2page.get(current_state, None)
        if page is None:
            raise Exception('incorrect state in installer(): %s' % current_state)
        return page(request)

    def renderSelectPage(self, request):
        src = '<br>' * 6 + '\n'
        src += '<h1>Install BitPie.NET</h1>\n'
        src += '<br>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<table align=center cellspacing=10>\n'
        src += '<tr><td align=left>\n'
        src += '<input fontsize="+5" id="radio1" type="radio" name="action" value="register a new account" checked />\n'
        src += '</td></tr>\n'
        src += '<tr><td align=left>\n'
        src += '<input fontsize="+5" id="radio2" type="radio" name="action" value="recover my account and backups" />\n'
        src += '</td></tr>\n'
        src += '<tr><td align=center>\n'
        src += '<br><br><input type="submit" name="submit" value=" next "/>\n'
        src += '</td></tr>\n'
        src += '</table>\n'
        src += '</form>\n'
        #src += '<br><br><br><br><br><br><a href="/?action=exit">[exit]</a>\n'
        action = arg(request, 'action', None)
        result = html(request, body=src, title='install', home='', back='')
        if action is not None:
            if action not in ['register a new account', 'recover my account and backups']:
                action = 'register a new account'
            action = action.replace('register a new account', 'register-selected')
            action = action.replace('recover my account and backups', 'recover-selected')
            installer.A(action)
        return result

    def renderRegisterNewUserPage(self, request):
        data = installer.A().getOutput('REGISTER').get('data')
        src = ''
        src += '<h1 align=center>registering new user identity</h1>\n'
        src += '<table width=95%><tr><td>\n'
        src += '<p align=justify>In order to allow others to send a data to you - \n'
        src += 'they must know the address of your computer on the Internet. \n'
        src += 'These contacts are kept in XML file called '
        src += '<a href="http://bitpie.net/glossary.html#identity" target=_blank>identity</a>.\n'
        src += 'File identity - is a publicly accessible file, '
        src += 'so that every user may download your identity file \n'
        src += 'and find out your contact information.\n'
        src += 'Identity file is digitally signed and that would change it '
        src += 'is necessary to know your <a href="http://bitpie.net/glossary.html#public_private_key" target=_blank>Private Key</a>. \n'
        src += 'The combination of these two keys provides '
        src += 'reliable identification of the user.</p>\n'
        src += '</td></tr></table>\n'
        # src += '<font size=-2>\n'
        src += '<table align=center width=300><tr><td align=left nowrap>\n'
        src += '<ul>\n'
        for text, color in data:
            if text.strip() == '':
                continue
            src += '<li><font color="%s">%s</font></li>\n' % (color, text)
        src += '</ul>\n'
        src += '</td></tr></table>\n'
        # src += '</font>\n'
        if installer.A().state == 'AUTHORIZED':
            idurl = misc.getLocalID()
            src += '<br>Here is your identity file: \n'
            src += '<a href="%s" target="_blank">%s</a><br>\n' % (idurl, idurl)
            src += '<br><form action="%s" method="get">\n' % ('/'+_PAGE_INSTALL)
            src += '<input type="submit" name="submit" value=" next " />\n'
            src += '<input type="hidden" name="action" value="next" />\n'
            src += '</form>\n'
        action = arg(request, 'action', None)
        result = html(request, body=src, title='register new user', home='', back='', reload='1' )
        if action == 'next':
            installer.A(action, self.login)
        return result

    def renderInputNamePage(self, request):
        self.login = arg(request, 'login', self.login)
        self.pksize = misc.ToInt(arg(request, 'pksize'), 2048)
        if self.login == '':
            self.login = bpio.ReadTextFile(settings.UserNameFilename())
        try:
            message, messageColor = installer.A().getOutput('INPUT_NAME').get('data', [('', '')])[-1]
        except:
            bpio.exception()
            message = messageColor = ''
        src = ''
        src += '<h1>enter your preferred username</h1>\n'
        src += '<table><tr><td align=left>\n'
        src += '<ul>\n'
        src += '<li>you can use <b>lower</b> case letters (a-z)\n'
        src += '<li>also digits (0-9), underscore (_) and dash (-)\n'
        src += '<li>the name must be from %s to %s characters\n' % (
            str(settings.MinimumUsernameLength()),
            str(settings.MaximumUsernameLength()))
        src += '<li>it must begin from a letter\n'
        src += '</ul>\n'
        src += '</td></tr></table>\n'
        if message != '':
            src += '<p><font color="%s">%s</font></p><br>\n' % (messageColor, message)
        else:
            src += '<br><br>\n'
            # src += '<p>&nbsp;</p>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<input type="text" name="login" value="%s" size=20 /><br>\n' % self.login
        src += '<table width="70%"><tr><td>\n'
        src += '<h3 align=center>select your private key size</h3>\n'
        src += '<p align=justify>Big key harder to crack, but it increases the time to back up your data. \n'
        src += 'If your computer is fast enough or you want more secure storage select 2048. \n'
        src += 'If you plan to do a lot of backups regularly choose 1024.</p>\n'
        src += '</td></tr>\n'
        src += '<tr><td align=center>\n'
        src += '<input id="radio2" type="radio" name="pksize" value="1024" %s />&nbsp;&nbsp;&nbsp;\n' % ('checked' if self.pksize==1024 else '')
        src += '<input id="radio3" type="radio" name="pksize" value="2048" %s />&nbsp;&nbsp;&nbsp;\n' % ('checked' if self.pksize==2048 else '')
        src += '<input id="radio4" type="radio" name="pksize" value="4096" %s />\n' % ('checked' if self.pksize==4096 else '')
        src += '</td></tr>'
        src += '</table>\n'
        src += '<br><br>\n'
        src += '<input type="submit" name="submit" value="register" />\n'
        src += '<input type="hidden" name="action" value="register-start" />\n'
        src += '</form><br>\n'
        # src += '<br><br><font size=-1><a href="%s?back=%s">[network settings]</a></font>\n' % ('/'+_PAGE_INSTALL_NETWORK_SETTINGS, request.path)
        action = arg(request, 'action', None)
        result = html(request, body=src, title='enter user name', home='', back='%s?action=back'%request.path )
        if action:
            settings.setPrivateKeySize(self.pksize)
            if action == 'register-start':
                installer.A(action, self.login)
            elif action == 'back':
                installer.A('back')
            else:
                bpio.log(2, 'webcontrol.InstallPage WARNING incorrect action: %s' % action)
        return result

    def renderRestorePage(self, request):
        data = installer.A().getOutput().get('data')
        src = ''
        # src += '<br>' * 4 + '\n'
        src += '<h1>restore my identity</h1>\n'
        src += '<table width=95%><tr><td>\n'
        src += '<p align=justify>In order to restore your account, you must verify Identity file '
        src += 'that is stored on the Identity server, with your Private Key. \n'
        src += 'If the signatures match - your account will be restored. \n'
        src += 'Next, list of your suppliers and other settings will be loaded from a Central server '
        src += 'and you will be able to connect with users who store your data.</p>\n'
        src += '</td></tr></table><br>\n'
        src += '<table><tr><td align=left>\n'
        src += '<br>\n<ul>\n'
        for text, color in data:
            if text.strip():
                src += '<li><font color="%s">%s</font></li>\n' % (color, text)
        src += '</ul>\n'
        src += '</td></tr></table>\n'
        if id_restorer.A().state == 'RESTORED!':
            src += '<br><br>Here is your identity file: \n'
            src += '<a href="%s" target="_blank">%s</a><br>\n' % (misc.getLocalID(), misc.getLocalID())
            src += '<br><br><form action="%s" method="get">\n' % request.path
            src += '<input type="submit" name="submit" value=" start " />\n'
            src += '<input type="hidden" name="action" value="start" />\n'
            src += '</form>\n'
        result = html(request, body=src, title='recover account', home='', back='' )
        action = arg(request, 'action', None)
        if action == 'start':
            id_restorer.A('start')
        return result

    def renderLoadKeyPage(self, request):
        self.idurl = arg(request, 'idurl', installer.A().getOutput().get('idurl', self.idurl))
        self.keysrc = arg(request, 'keysrc', installer.A().getOutput().get('keysrc', self.keysrc))
        try:
            message, messageColor = installer.A().getOutput('RECOVER').get('data', [('', '')])[-1] 
        except:
            message = messageColor = ''
        src = ''
        src += '<table width=90%><tr><td colspan=3 align=center>\n'
        src += '<h1>recover existing account</h1>\n'
        src += '<p align=justify>To <a href="http://bitpie.net/glossary.html#recovery" target=_blank>recover</a> '
        src += 'your previously backed up data you need to provide your Private Key and Identity file.\n'
        src += 'There are 3 different ways to do this below.\n'
        src += 'Choose depending on the way you stored a copy of your Key.</p>\n'
        src += '</td></tr>'
        src += '<tr><td align=center>\n'
        #TODO barcodes is not finished yet
        src += '<form action="%s" method="post" enctype="multipart/form-data">\n' % request.path
        src += '<input type="hidden" name="action" value="load-barcode" />\n'
        src += '<input type="file" name="barcodesrc" />\n'
        src += '<input type="submit" name="submit" value=" load from 2D barcode scan " disabled /> '
        src += '</form>\n'
        src += '</td><td align=center>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<input type="submit" name="openfile" value=" load from file or flash USB " />\n'
        src += '<input type="hidden" name="action" value="load-from-file" />\n'
        src += '</form>\n'
        src += '</td><td align=center>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<input type="hidden" name="action" value="paste-from-clipboard" />\n'
        src += '<input type="submit" name="submit" value=" paste from clipboard " %s />' % ('disabled' if bpio.Linux() else '')
        src += '</form>\n'
        src += '</td></tr></table>\n'
        src += '<table align=center><tr><td align=center>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<table width=100%><tr align=top><td nowrap>'
        src += 'Identity URL:</td><td align=right>\n'
        src += '<input type="text" name="idurl" size=70 value="%s" />\n' % self.idurl
        src += '</td></tr></table>\n'
        src += '<textarea name="keysrc" rows=7 cols=60 >'
        src += self.keysrc
        src += '</textarea><br>\n'
        src += '<input type="hidden" name="action" value="restore-start" />\n'
        if message != '':
            src += '<p><font color="%s">%s</font></p><br><br>\n' % (messageColor, message)
        else:
            src += '<br>\n'
        src += '<input type="submit" name="submit" value=" next " />\n'
        src += '</form>\n'
        src += '</td></tr></table>\n'
        result = html(request, body=src, title='restore identity', home='', back='%s?action=back'%request.path)
        action = arg(request, 'action', None)
        if action is not None:
            if action == 'load-from-file':
                installer.A(action, arg(request, 'openfile', ''))
            elif action == 'paste-from-clipboard':
                installer.A(action)
            elif action == 'back':
                installer.A('back')
            elif action == 'restore-start':
                installer.A(action, { 'idurl': self.idurl, 'keysrc': self.keysrc } )
            else:
                bpio.log(2, 'webcontrol.InstallPage WARNING incorrect action: %s' % action)
        return result

    def renderWizardPage(self, request):
        current_state = install_wizard.A().state
        page = self.wizardstate2page.get(current_state, None)
        if page is None:
            raise Exception('incorrect state in install_wizard(): %s' % current_state)
        return page(request)

    def renderWizardSelectRolePage(self, request):
        src = ''
        src += '<h1>how do you plan to participate in the project?</h1>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<table width=100% cellpadding=2>\n'
        src += '<tr><td align=center valign=top>\n'
        src += '<input fontsize="+5" fontweight="bold" id="radio1" type="radio" name="select-free-backups" value="FREE online backups" %s />\n' % (
            'checked' if self.role==1 else '')
        src += '<font size="-1"><ul>\n'
        src += '<li>donate HDD space and accumulate credits</li>\n'
        src += '<li>spent credits for your own backup storage</li>\n'
        src += '<li>keep your machine online 24/7</li>\n'
        src += '<li>set a schedule to do backups automatically</li>\n'
        src += '</ul></font>\n'
        src += '</td><td align=center valign=top nowrap>\n'
        src += '<input fontsize="+5" fontweight="bold" id="radio2" type="radio" name="select-secure" value="own encrypted storage" %s />\n' % (
            'checked' if self.role==2 else '')
        src += '<font size="-1"><ul>\n'
        src += '<li>completely hide your data from all but you</li>\n'
        src += '<li>secure encrypted distributed storage</li>\n'
        src += '<li>only you posses the Key</li>'
        src += '<li>local copy of your data can be erased, theft protection</li>\n'
        src += '<li>need to buy credits for $ US or BitCoins</li>\n'
        src += '</ul></font>\n'
        src += '</td></tr>\n'
        src += '<tr><td align=center valign=top>\n'
        src += '<br><br><input fontsize="+5" fontweight="bold" id="radio3" type="radio" name="select-donator" value="donate space for credits" %s />\n' % (
            'checked' if self.role==3 else '')
        src += '<font size="-1"><ul>\n'
        src += '<li>donate HDD space to others and earn credits</li>\n'
        src += '<li>keep your machine working 24/7, be online</li>\n'
        src += '<li>sell your credits for real $ or BitCoins</li>\n'
        src += '</ul></font>\n'
        src += '</td><td align=center valign=top>\n'
        src += '<br><br><input fontsize="+5" fontweight="bold" id="radio4" type="radio" name="select-beta-test" value="beta tester" %s />\n' % (
            'checked' if self.role==4 else '')
        src += '<font size="-1"><ul>\n'
        src += '<li>keep software working on your desktop machine</li>\n'
        src += '<li>report bugs, give feedback, do social posts</li>\n'
        src += '</ul></font>\n'
        src += '</td></tr>\n'
        src += '<tr><td colspan=2 align=center valign=top>\n'
        src += '<br><br><input fontsize="+5" fontweight="bold" id="radio5" type="radio" name="select-try-it" value="don\'t know, just let me try the software" %s />\n' % (
            'checked' if self.role==5 else '') 
        src += '<br><font size="-1">no problem, you can configure BitPie.NET later</font>\n'
        src += '</td></tr>\n'
        src += '</table>\n'
        src += '<input type="hidden" name="action" value="next" />\n'
        src += '<br><br><input type="submit" name="submit" value=" next " />\n'
        src += '</form>\n'
        result = html(request, body=src, title='select role', home='', back='')
        action = arg(request, 'action', None)
        if action is not None and action == 'next':
            if hasArg(request, 'select-free-backups'):
                self.role = 1
                install_wizard.A('select-free-backups')
            elif hasArg(request, 'select-secure'):
                self.role = 2
                install_wizard.A('select-secure')
            elif hasArg(request, 'select-donator'):
                self.role = 3
                install_wizard.A('select-donator')
            elif hasArg(request, 'select-beta-test'):
                self.role = 4
                install_wizard.A('select-beta-test')
            elif hasArg(request, 'select-try-it'):
                self.role = 5
                install_wizard.A('select-try-it')
            else:
                bpio.log(2, 'webcontrol.renderWizardSelectRolePage WARNING incorrect args: %s' % str(request.args))
        return result

    def renderWizardJustTryItPage(self, request):
        src = ''
        src += '<h1>almost ready to start</h1>\n'
        src += '<table width=80%><tr><td>\n'
        src += '<p align=justify>You spent <a href="http://bitpie.net/glossary.html#money" target="_blank">credits</a> '
        src += 'to rent a storage from your <a href="http://bitpie.net/glossary.html#supplier" target="_blank">suppliers</a>.\n'
        src += 'BitPie.NET gives you a <b>$ 10</b> virtual credits as gift, so you can '
        src += 'start doing backups immediately after installation.</p>\n'
        src += '<p align=justify>Thanks for your choice, we hope you like BitPie.NET!</p>\n'
        src += '<p align=justify>Feel free to send your feedback on '
        src += '<a href="mailto:bitpie.net@gmail.com" target=_blank>bitpie.net@gmail.com</a>, '
        src += 'visit our <a href="http://bitpie.net/forum" target=_blank>message board</a> to read talks. '
        src += 'Your attention is important to us!</p>\n'
        src += '</td></tr></table><br>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<br><br><br>\n'
        src += '<input type="submit" name="submit" value=" next " />\n'
        src += '<input type="hidden" name="action" value="next" />\n'
        src += '</form>'
        result = html(request, body=src, title='almost ready', home='', back='%s?action=back' % request.path)
        action = arg(request, 'action', None)
        if action:
            if action == 'next':
                install_wizard.A('next', {'needed': self.needed, 'donated': self.donated, })
            elif action == 'back':
                install_wizard.A('back')
            else:
                bpio.log(2, 'webcontrol.renderWizardJustTryItPage WARNING incorrect action: %s' % action)
        return result

    def renderWizardBetaTestPage(self, request):
        # self.development = ('False' if not hasArg(request, 'development') else 'True')
        action = arg(request, 'action', None)
        if action == 'next': 
            self.development = arg(request, 'development')
        src = ''
        src += '<form action="%s" method="post">\n' % request.path
        src += '<h1>beta testing</h1>\n'
        src += '<table width=80%><tr><td>\n'
        src += '<p align=justify>We offer a <b><a href="http://gold.ai" target=_blank>1 oz silver coin</a></b> or \n'
        src += '<b>$50 US</b> for beta test users who use the software for <b>365 days</b>.\n'
        src += 'You must donate at least <b>5 Gigabytes</b> to count as active user. </p>\n'
        src += '<p align=justify>Every hour, the program sends a short control packet on the Central \n'
        src += 'server so we know who is online, watch \n'
        src += '<a href="http://id.bitpie.net/statistics/" target=_blank>statistics page</a> \n'
        src += 'to check your online days.\n'
        src += 'To get 50$ US or 1 oz silver coin you have to collect <b>365</b> points '
        src += 'in the column <i>effective days active</i>.</p>\n'
        src += '<p align=justify>Users who report bugs, spread BitPie.NET around the world \n'
        src += 'and actively assist in the development may be further rewarded. \n'
        src += '<br>This offer is currently limited to the <b>first 75 people</b> '
        src += 'to sign up in the beta testing.</p>\n'
        src += '<br><br><table cellpadding=0 cellspacing=0 align=center>\n'
        src += '<tr><td valign=middle width=30>\n'
        src += '<input type="checkbox" name="development" value="True" %s />\n' % (('checked' if self.development == 'True' else ''))
        src += '</td><td valign=top align=left>\n'
        src += '<font size="+0"><b>enable development tools:</b> This will set higher debug level \n'
        src += 'to produce more logs, enable HTTP server to watch the logs and '
        src += 'start the memory profiler.</font>\n'
        src += '</td>\n'
        src += '</tr></table>\n'
        src += '</td></tr></table>\n'
        src += '<br><br><br>\n'
        src += '<input type="submit" name="submit" value=" next " />\n'
        src += '<input type="hidden" name="action" value="next" />\n'
        src += '</form>\n'
        result = html(request, body=src, title='beta testing', home='', back='%s?action=back' % request.path)
        if action:
            if action == 'next':
                install_wizard.A('next', {'development': self.development,})
            elif action == 'back':
                install_wizard.A('back')
            else:
                bpio.log(2, 'webcontrol.renderWizardBetaTestPage WARNING incorrect action: %s' % action)
        return result

    def renderWizardDonatorPage(self, request):
        src = ''
        src += '<h1>donate space to others</h1>\n'
        src += '<table width=80%><tr><td>\n'
        src += '<p align=justify>You gain <a href="http://bitpie.net/glossary.html#money" target="_blank">credits</a> '
        src += 'for providing space to your <a href="http://bitpie.net/glossary.html#customer" target="_blank">customers</a>. \n'
        src += 'It needs time to get customers from Central server and fill your donated space, '
        src += 'keep software working and stay online as much as possible to have higher '
        src += '<a href="http://bitpie.net/glossary.html#rating" target="_blank">rating</a> and count as '
        src += 'reliable <a href="http://bitpie.net/glossary.html#supplier" target="_blank">supplier</a>.\n'
        src += 'Donate more HDD space to accumulate more credits.</p>\n'
        src += '<p align=justify>We are going to provide a way to exchange accumulated credits for real money, bit coins or other currency.\n'
        src += 'At the moment we are focused on other things, this should be done early or later. '
        src += 'But you already able to accumulate credits and so you can start earning right now.</p>\n'
        src += '</td></tr></table>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<br><br><br><input type="submit" name="submit" value=" next " />\n'
        src += '<input type="hidden" name="action" value="next" />\n'
        src += '</form>'
        result = html(request, body=src, title='donate space', home='', back='%s?action=back' % request.path)
        action = arg(request, 'action', None)
        if action:
            if action == 'next':
                install_wizard.A('next', {})
            elif action == 'back':
                install_wizard.A('back')
            else:
                bpio.log(2, 'webcontrol.renderWizardBetaTestPage WARNING incorrect action: %s' % action)
        return result

    def renderWizardFREEBackupsPage(self, request):
        src = ''
        src += '<h1>needed and donated space</h1>\n'
        src += '<table width=90%><tr><td>\n'
        src += '<p align=justify>You gain <a href="http://bitpie.net/glossary.html#money" target=_blank>credits</a> for providing space to \n' 
        src += 'your <a href="http://bitpie.net/glossary.html#customer" target=_blank>customers</a> \n'
        src += 'and also spent credits to rent a space from <a href="http://bitpie.net/glossary.html#supplier" target="_blank">suppliers</a>. </p>\n'
        src += '<p align=justify>If other users takes from you twice more space than you need for your data - <b>it is FREE</b>!\n'
        src += 'This is because the <a href="http://bitpie.net/glossary.html#redundancy_in_backup" target=_blank>redundancy ratio</a> is 1:2, '
        src += 'so every your backup takes twice more space on suppliers machines.</p>\n'
        src += '<p align=justify>After registration the Central server starts counting your <a href="http://bitpie.net/glossary.html#rating" target="_blank">rating</a>, '
        src += 'more online hours - higher rating in the network.\n'
        src += 'The rating is used to decide who will be a more reliable supplier - new users probably wants you as supplier if you are mostly online.\n'
        src += 'So you get your customers early or later and fill most of your donated space.</p>\n'
        src += '<p align=justify>BitPie.NET gives you a <b>$ 10</b> virtual credits as gift, so you can \n'
        src += 'start doing backups immediately after installation.</p>\n'
        src += '<p align=justify>Go to <i>[menu]->[money]</i> page to check your current credits and daily history.</p>\n'
        src += '</td></tr></table><br>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<br><br><br><input type="submit" name="submit" value=" next " />\n'
        src += '<input type="hidden" name="action" value="next" />\n'
        src += '</form>'
        result = html(request, body=src, title='needed//donated space', home='', back='%s?action=back' % request.path)
        action = arg(request, 'action', None)
        if action:
            if action == 'next':
                install_wizard.A('next', {})
            elif action == 'back':
                install_wizard.A('back')
            else:
                bpio.log(2, 'webcontrol.renderWizardBetaTestPage WARNING incorrect action: %s' % action)
        return result

    def renderWizardMostSecurePage(self, request):
        src = ''
        src += '<h1>own encrypted storage</h1>\n'
        src += '<table width=90%><tr><td>\n'
        src += '<p align=justify>I wish to introduce a new feature in the BitPie.NET.</p>\n'
        src += '<p align=justify>Now you can create a <b>completely inaccessible for anybody but you</b>, keeping your data, \n'
        src += 'if after creating a distributed remote copy of your data - delete the original data from your computer.</p>\n'
        src += '<p align=justify>Your <a href="http://bitpie.net/glossary.html#public_private_key" target=_blank>Private Key</a> '
        src += 'can be stored on a USB flash drive and local copy of the Key can be removed from your HDD.</p>\n'
        src += '<p align=justify>Than, BitPie.NET will only run with this USB stick and read the Private Key at start up, \n'
        src += 'so it will only be stored in RAM. After starting the program, disconnect the USB stick, and hide it in a safe place.</p>\n'
        src += '<p align=justify>If control of that computer was lost - just be sure that the power is turned off, it is easy to provide. \n'
        src += 'In this case the memory is reset and working key will be erased, so that copy of your Private Key will remain only on a USB flash drive, hidden by you.</p>\n'
        src += '<p align=justify>This way, only you will have access to the data after a loss of the computer, where BitPie.NET were launched. '
        src += 'Just need to download BitPie.NET Software again and <a href="http://bitpie.net/glossary.html#recovery" target=_blank>recover your account</a> '
        src += 'with your Private Key and than you can restore your backed up data.</p>\n'
        src += '<p align=left>To move your Private Key on USB flash drive go to <i>[menu]->[settings]->[security]</i> page.</p>\n'
        src += '</td></tr></table><br>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<br><br><br><input type="submit" name="submit" value=" next " />\n'
        src += '<input type="hidden" name="action" value="next" />\n'
        src += '</form>\n'
        result = html(request, body=src, title='needed//donated space', home='', back='%s?action=back' % request.path)
        action = arg(request, 'action', None)
        if action:
            if action == 'next':
                install_wizard.A('next', {})
            elif action == 'back':
                install_wizard.A('back')
            else:
                bpio.log(2, 'webcontrol.renderWizardBetaTestPage WARNING incorrect action: %s' % action)
        return result

    def renderWizardStoragePage(self, request):
        message = ''
        action = arg(request, 'action', None)
        opendir = unicode(misc.unpack_url_param(arg(request, 'opendir'), ''))
        self.customersdir = unicode(
            misc.unpack_url_param(
                arg(request, 'customersdir', settings.getCustomersFilesDir()),
                    settings.getCustomersFilesDir()))
        self.localbackupsdir = unicode(
            misc.unpack_url_param(
                arg(request, 'localbackupsdir', settings.getLocalBackupsDir()),
                    settings.getLocalBackupsDir()))
        self.restoredir = unicode(
            misc.unpack_url_param(
                arg(request, 'restoredir', settings.getRestoreDir()),
                    settings.getRestoreDir()))
        if opendir != '':
            if hasArg(request, '_customersdir'):
                self.customersdir = misc.unpack_url_param(arg(request, '_customersdir'), self.customersdir)
            elif hasArg(request, '_localbackupsdir'):
                self.localbackupsdir = misc.unpack_url_param(arg(request, '_localbackupsdir'), self.localbackupsdir)
            elif hasArg(request, '_restoredir'):
                self.restoredir = misc.unpack_url_param(arg(request, '_restoredir'), self.restoredir)
            else:
                raise 'Not found target location: ' + str(request.args)
        self.needed = arg(request, 'needed', self.needed)
        if self.needed == '':
            self.needed = str(settings.DefaultNeededMb())
        self.donated = arg(request, 'donated', self.donated)
        if self.donated == '':
            self.donated = str(settings.DefaultDonatedMb())
        neededV = misc.ToInt(misc.DigitsOnly(str(self.needed)), settings.DefaultNeededMb())
        self.needed = str(int(neededV))
        donatedV = misc.ToInt(misc.DigitsOnly(str(self.donated)), settings.DefaultDonatedMb())
        self.donated = str(int(donatedV))
        mounts = []
        freeSpaceIsOk = True
        if bpio.Windows():
            for d in bpio.listLocalDrivesWindows():
                free, total = diskusage.GetWinDriveSpace(d[0])
                if free is None or total is None:
                    continue
                color = '#ffffff'
                if self.customersdir[0].upper() == d[0].upper():
                    color = '#60e060'
                    if (donatedV) * 1024 * 1024 >= free:
                        color = '#e06060'
                        freeSpaceIsOk = False
                if self.localbackupsdir[0].upper() == d[0].upper():
                    color = '#60e060'
                    if (neededV) * 1024 * 1024 >= free:
                        color = '#e06060'
                        freeSpaceIsOk = False
                mounts.append((d[0:2],
                               diskspace.MakeStringFromBytes(free), 
                               diskspace.MakeStringFromBytes(total),
                               color,))
        elif bpio.Linux():
            for mnt in bpio.listMountPointsLinux():
                free, total = diskusage.GetLinuxDriveSpace(mnt)
                if free is None or total is None:
                    continue
                color = '#ffffff'
                if bpio.getMountPointLinux(self.customersdir) == mnt:
                    color = '#60e060'
                    if (donatedV) * 1024 * 1024 >= free:
                        color = '#e06060'
                        freeSpaceIsOk = False
                if bpio.getMountPointLinux(self.localbackupsdir) == mnt:
                    color = '#60e060'
                    if (neededV) * 1024 * 1024 >= free:
                        color = '#e06060'
                        freeSpaceIsOk = False
                mounts.append((mnt, 
                               diskspace.MakeStringFromBytes(free), 
                               diskspace.MakeStringFromBytes(total),
                               color,))
        ok = True
        if not freeSpaceIsOk:
            message += '\n<br>' + html_message('you do not have enough free space on the disk', 'error')
            ok = False
        if donatedV < settings.MinimumDonatedMb():
            message += '\n<br>' + html_message('you must donate at least %d MB' % settings.MinimumDonatedMb(), 'notify')
            ok = False
        if not os.path.isdir(self.customersdir):
            message += '\n<br>' + html_message('directory %s not exist' % self.customersdir, 'error')
            ok = False
        if not os.access(self.customersdir, os.W_OK):
            message += '\n<br>' + html_message('folder %s does not have write permissions' % self.customersdir, 'error')
            ok = False
        if not os.path.isdir(self.localbackupsdir):
            message += '\n<br>' + html_message('directory %s not exist' % self.localbackupsdir, 'error')
            ok = False
        if not os.access(self.localbackupsdir, os.W_OK):
            message += '\n<br>' + html_message('folder %s does not have write permissions' % self.localbackupsdir, 'error')
            ok = False
        src = ''
        src += '<form action="%s" method="post">\n' % request.path
        src += '<h1>needed and donated space</h1>\n'
        if len(mounts) > 0:
            src += '<table align=center cellspacing=2><tr>\n'
            for d in mounts:
                src += '<td bgcolor=%s>&nbsp;&nbsp;<font size=-2><b>%s</b><br>%s free / %s total</font>&nbsp;&nbsp;</td>\n' % (d[3], d[0], d[1], d[2])
            src += '</tr></table><br><br>\n'
        # src += '<font size=1><hr width=80% size=1></font>\n'
        # src += '.............................................................................................................................................'
        src += '<table cellpadding=5 width=90%><tr>\n'
        src += '<td align=left nowrap valign=top width=100>'
        src += '<font size="+1"><b>megabytes needed</b></font>\n'
        src += '<br><br>'
        src += '<input type="text" name="needed" size="10" value="%s" />\n' % self.needed
        src += '</td>\n'
        src += '<td align=right valign=top nowrap>\n'
        # src += '<b>local backups location:</b><br>\n'
        src += '<font size=-1>%s</font><br>\n' % self.localbackupsdir
        src += '<input type="submit" target="_localbackupsdir" name="opendir" value=" location of your local files " label="Select folder for your backups" />\n'
        src += '</td>\n'
        src += '</tr>\n'
        # src += '</table>\n'
        src += '<br>\n'
        # src += '<font size=1><hr width=80% size=1></font>\n'
        # src += '.............................................................................................................................................'
        # src += '<table cellpadding=5 width=90%>'
        src += '<tr>\n'
        src += '<td align=left nowrap valign=top width=100>'
        src += '<font size="+1"><b>megabytes donated</b></font>\n'
        src += '<br><br>'
        src += '<input type="text" name="donated" size="10" value="%s" />\n' % self.donated
        src += '</td>\n'
        src += '<td align=right valign=top nowrap>\n'
        # src += '<b>donated space location:</b><br>\n'
        src += '<font size=-1>%s</font><br>\n' % self.customersdir
        src += '<input type="submit" target="_customersdir" name="opendir" value=" location for donated space " label="Select folder for donated space" />\n'
        src += '</td>\n'
        src += '</tr>\n'
        # src += '</table>\n'
        src += '<br>\n'
        # src += '<font size=1><hr width=80% size=1></font>\n'
        # src += '.............................................................................................................................................'
        # src += '<table cellpadding=5 width=90%>'
        src += '<tr>\n'
        src += '<td width=100>&nbsp;</td>\n'
        src += '<td align=right valign=top nowrap>'
        # src += '<b>location for restored files:</b><br>\n'
        src += '<font size=-1>%s</font><br>\n' % self.restoredir
        src += '<input type="submit" target="_restoredir" name="opendir" value=" location of your restored files " label="Select folder for your restored files"/>\n'
        src += '</td>\n'
        src += '</tr>\n'
        src += '</table>\n'
        src += message
        src += '\n'
        src += '<br><br><input type="submit" name="submit" value=" next " />\n'
        src += '<input type="hidden" name="action" value="next" />\n'
        src += '<input type="hidden" name="customersdir" value="%s" />\n' % self.customersdir
        src += '<input type="hidden" name="localbackupsdir" value="%s" />\n' % self.localbackupsdir
        src += '<input type="hidden" name="restoredir" value="%s" />\n' % self.restoredir
        src += '</form>\n'
        result = html(request, body=src, title='program paths', home='', back='%s?action=back' % request.path)
        if action:
            if action == 'next' and arg(request, 'submit').strip() == 'next':
                if ok:
                    install_wizard.A('next', {'needed': self.needed,
                                              'donated': self.donated,
                                              'customersdir': self.customersdir, 
                                              'localbackupsdir': self.localbackupsdir,
                                              'restoredir': self.restoredir,})
            elif action == 'back':
                install_wizard.A('back')
            else:
                bpio.log(2, 'webcontrol.renderWizardStoragePage WARNING incorrect action: %s' % action)
        return result

    def renderWizardContactsPage(self, request):
        message = ''
        action = arg(request, 'action', None)
        if action == 'next':
            self.name = arg(request, 'name')
            self.surname = arg(request, 'surname')
            self.nickname = arg(request, 'nickname')
            self.email = arg(request, 'email')
        src = ''
        src += '<h1>enter your personal information</h1>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<table width="95%" cellspacing=5>\n'
        src += '<tr><td align=left>\n'
        src += 'Please, enter information about yourself if you wish. \n'
        src += 'Provide email to contact with you, we do not send spam and do not publish your personal information. \n'
        src += 'This is to be able to notify you if your account balance is running low and your backups is at risk.\n'
        src += '</td></tr>\n'
        src += '<tr><td align=center>\n'
        src += '<table align=center><tr>\n'
        src += '<td>name:<br><input type="text" name="name" size="25" value="%s" /></td>\n' % self.name
        src += '<td>surname:<br><input type="text" name="surname" size="25" value="%s" /></td>\n' % self.surname
        src += '<td>nickname:<br><input type="text" name="nickname" size="25" value="%s" /></td>\n' % self.nickname
        src += '</tr></table>\n'
        src += '</td></tr>\n'
        src += '<tr><td align=center>\n'
        src += 'email:<br><input type="text" name="email" size="25" value="%s" />\n' % self.email
        src += '</td></tr>\n'
#         if message != '':
#             src += '<tr><td align=center>\n'
#             src += '<font color="%s">%s</font>\n' % (messageColor, message)
#             src += '</td></tr>\n'
        src += '<tr><td align=center>\n'
        src += '<input type="hidden" name="action" value="next" />\n'
        src += '<br><br><br><input type="submit" name="submit" value=" next " />\n'
        src += '</td></tr></table>\n'
        src += '</form>\n'
        result = html(request, body=src, title='my contacts', home='', back='%s?action=back'%request.path)
        if action:
            if action == 'next':
                install_wizard.A('next', {  'email': self.email,
                                            'name': self.name,
                                            'surname': self.surname,
                                            'nickname': self.nickname,})
            elif action == 'back':
                install_wizard.A('back')
            else:
                bpio.log(2, 'webcontrol.renderWizardContactsPage WARNING incorrect action: %s' % action)
        return result

#    def renderWizardUpdatesPage(self, request):
#        choice = arg(request, 'choice', 'hourly')
#        src = ''
#        src += '<table width=80%><tr><td>\n'
#        src += '<center><h1>software updates</h1><center>\n'
#        src += '<p align=justify>The BitPie.NET is now being actively developed and '
#        src += 'current software version can be updated several times a month.</p>\n'
#        src += '<p align=justify>If your computer will run an old version of BitPie.NET, '
#        src += 'then sooner or later, you can lose touch with other users.\n'
#        src += 'Since data transmission protocols may be changed - '
#        src += 'users will not be able to understand each other '
#        src += 'if both will have different software versions. \n'
#        src += 'Thus, your suppliers will not be able to communicate with you and all your backups will be lost.</p>\n'
#        src += '<p align=justify>We recommend that you enable automatic updates, '
#        src += 'at least for a period of active development of the project.</p>\n'
#        src += '<br>\n'
#        src += '<form action="%s" method="post">\n' % request.path
#        if bpio.Windows():
#            src += '<h3>how often you\'d like to check the latest version?</h3>\n'
#            src += '<table cellspacing=5><tr>\n'
#            items = ['disable updates', 'hourly', 'daily', 'weekly',]
#            for i in range(len(items)):
#                checked = ''
#                if items[i] == choice:
#                    checked = 'checked'
#                src += '<td>'
#                src += '<input id="radio%s" type="radio" name="choice" value="%s" %s />' % (
#                    str(i),
#                    items[i],
#                    checked,)
#                #src += '<label for="radio%s">  %s</label></p>\n' % (str(i), items[i],)
#                src += '</td>\n'
#            src += '</tr></table>'
#        elif bpio.Linux():
#            src += '<br><p align=justify>If you installed BitPie.NET through a package <b>bitpie-stable</b>, \n'
#            src += 'it should be updated automatically with daily cron job.</p>\n'
#        src += '<br><br><br>\n'
#        src += '<center><input type="hidden" name="action" value="next" />\n'
#        src += '<input type="submit" name="submit" value=" next " /></center>\n'
#        src += '</form>\n'
#        src += '</td></tr></table>\n'
#        action = arg(request, 'action', None)
#        result = html(request, body=src, title='updates', home='', back='%s?action=back'%request.path)
#        if action:
#            if action == 'next':
#                install_wizard.A('next', choice)
#            elif action == 'back':
#                install_wizard.A('back')
#            else:
#                bpio.log(2, 'webcontrol.renderWizardUpdatesPage WARNING incorrect action: %s' % action)
#        return result

    def renderLastPage(self, request):
        src = ''
        src += '<br>' * 6 + '\n'
        src += '<table width=80%><tr><td>\n'
        src += '<font size=+2 color=green><h1>BitPie.NET<br>is now configured</h1></font>\n'
        src += '<br><br><br>\n'
        src += '<form action="%s" method="get">\n' % request.path
        src += '<input type="hidden" name="action" value="next" />\n'
        src += '<input type="submit" name="submit" value=" start " />\n'
        src += '</form>'
        action = arg(request, 'action', None)
        result = html(request, body=src, title='installed', home='', back='%s?action=back'%request.path)
        if action:
            if action == 'next':
                install_wizard.A('next')
            elif action == 'back':
                install_wizard.A('back')
            else:
                bpio.log(2, 'webcontrol.renderLastPage WARNING incorrect action: %s' % action)
        return result
        

class InstallNetworkSettingsPage(Page):
    pagename = _PAGE_INSTALL_NETWORK_SETTINGS
    def renderPage(self, request):
        checked = {True: 'checked', False: ''}
        action = arg(request, 'action')
        back = arg(request, 'back', request.path)
        host = arg(request, 'host', settings.getProxyHost())
        port = arg(request, 'port', settings.getProxyPort())
        upnpenable = arg(request, 'upnpenable', '')
        # bpio.log(6, 'webcontrol.InstallNetworkSettingsPage.renderPage back=[%s]' % back)
        if action == 'set':
            settings.enableUPNP(upnpenable.lower()=='true')
            d = {'host': host.strip(), 'port': port.strip()}
            net_misc.set_proxy_settings(d)
            settings.setProxySettings(d)
            settings.enableProxy(d.get('host', '') != '')
            request.redirect(back)
            request.finish()
            return NOT_DONE_YET
        if upnpenable == '':
            upnpenable = str(settings.enableUPNP())
        src = '<br><br>'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<h3>Proxy server</h3>\n'
        src += '<table><tr>\n'
        src += '<tr><td valign=center align=left>host:</td>\n'
        src += '<td valign=center align=left>port:</td></tr>\n'
        src += '<tr><td><input type="text" name="host" value="%s" size="20" /></td>\n' % host
        src += '<td><input type="text" name="port" value="%s" size="6" />\n' % port
        src += '</td></tr></table>'
        src += '<p>Leave fields blank to not use proxy server.</p>\n'
        src += '<br><br><h3>UPnP port forwarding</h3>\n'
        src += '<table><tr><td>\n'
        src += '<br><input type="checkbox" name="upnpenable" value="%s" %s />' % ('True', checked.get(upnpenable=='True'))
        src += '</td><td valign=center align=left>'
        src += 'Use UPnP to automaticaly configure port forwarding for BitPie.NET.<br>'
        src += 'Enable this if you are connected to the Internet with network router.'
        src += '</td></tr></table>\n'
        src += '<br><br><br><input type="submit" name="button" value="   set   " />'
        src += '<input type="hidden" name="action" value="set" />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % back
        src += '</form><br><br>\n'
        return html(request, body=src, back=back, home = '',)


class RootPage(Page):
    pagename = _PAGE_ROOT
    def renderPage(self, request):
        request.redirect('/'+_PAGE_MAIN)
        request.finish()
        return NOT_DONE_YET


#--- Main (Backups) Page
class MainPage(Page):
    pagename = _PAGE_MAIN
    htmlComment = ''
    
    expanded_dirs = set(['',])
    expanded_items = set()
    selected_items = set()
    selected_backups = set()
    listExpandedDirs = None
    listExpandedVersions = None
    
    opened_dirs = {}

    def _body1(self, request):
        back = arg(request, 'back', request.path)
        src = '' 
        if self.htmlComment:
            src += self.htmlComment
            self.htmlComment = ''
#        #--- list items and backups
#        if self.listExpandedDirs is None:
#            self.listExpandedDirs, self.listExpandedVersions = backup_fs.ListExpandedFoldersAndBackups(self.expanded_dirs, self.selected_items)
        
        #--- table
        # for 
        


    def _body(self, request):
        back = arg(request, 'back', request.path)

        src = ''
        
        if self.htmlComment:
            src += self.htmlComment
            self.htmlComment = ''
            
        #--- list items and backups
        if self.listExpandedDirs is None or len(self.listExpandedDirs) == 0:
            self.listExpandedDirs, self.listExpandedVersions = backup_fs.ListExpandedFoldersAndBackups(self.expanded_dirs, self.selected_items)
            
        src += '<table width=100% align=center cellspacing=10 cellpadding=0 border=0>'
        src += '<tr>\n'
        src += '<td width=33%>&nbsp;</td>\n'
        src += '<td width=33%><h1>my files</h1></td>\n'
        src += '<td width=33% align=right>'
        
        #--- selected items label
        numitems = len(self.selected_items)
        numbackups = len(self.selected_backups)
        if numitems > 0 or numbackups > 0:
            if numitems > 0:
                src += '<font size=-2>'
                src += '%d items selected' % numitems
                src += '</font>'
            if numbackups > 0:
                src += '<font size=-2>'
                src += '%d backups selected' % numbackups
                src += '</font>'
            src += '<br>\n'
        
        #--- number of tasks label
        numtasks = len(backup_control.tasks())
        numjobs = len(backup_control.jobs())
        if numtasks == 0 and numjobs == 0:
            src += '&nbsp;' 
        else:
            src += '<font size=-2>'
            if numjobs:
                src += 'backup in progress, '
            if numtasks:
                src += '%d more tasks in queue, ' % numtasks
            # src += '<a href="%s?action=cancelall&back=%s">cancel</a>' % (request.path, back)
            msg = 'Do you want to abort current backup process and cancel all tasks in the queue?'
            src += '<a href="%s">cancel</a>' % confirmurl(request, text=msg, back=back,
                yes='%s?action=cancelall' % request.path)
            src += '</font>'
        src += '</td>\n'
        src += '</tr></table>\n'

        src += '<table width=100% align=center cellspacing=0 cellpadding=0 border=0>'
        src += '<tr>\n'
        
        #--- add button ---
        src += '<td align=center width=10%>'
        if len(self.selected_items) == 0 and len(self.selected_backups) == 0:
            src += '<a href="%s?action=diradd&path=%s&showincluded=true&label=%s" target="_opendir">' % (
                request.path, misc.pack_url_param(os.path.expanduser('~')), misc.pack_url_param('Add a given folder to My Files')) 
            src += '<img src="%s">' % iconurl(request, 'icons/folder-add.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/folder-add-gray.png')
        src += '</td>\n'

        #--- add many button ---
        src += '<td align=center width=10%>'
        if len(self.selected_items) == 0 and len(self.selected_backups) == 0:
            src += '<a href="%s?action=diraddrecursive&path=%s&showincluded=true&label=%s" target="_opendir">' % (
                request.path, misc.pack_url_param(os.path.expanduser('~')), misc.pack_url_param('Recursive add files and folders from given location')) 
            src += '<img src="%s">' % iconurl(request, 'icons/folders-many-add.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/folders-many-add-gray.png')
        src += '</td>\n'
        
        #--- delete button ---
        src += '<td align=center width=10%>'
        if len(self.selected_backups) == 0 and len(self.selected_items) > 0: 
            # src += '<a href="%s?action=delete">' % request.path
            msg = 'Delete <b>%d</b> selected items from the catalog and erase all remote backups associated with them?' % len(self.selected_items)
            msg += ' Your local files and folders will not be affected.'
            src += '<a href="%s">' % confirmurl(request, text=msg, back=back,  
                yes='%s?action=delete' % request.path) 
            src += '<img src="%s">' % iconurl(request, 'icons/folder-delete.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/folder-delete-gray.png')
        src += '</td>\n'

        #--- backup button ---
        src += '<td align=center width=10%>'
        if len(self.selected_backups) == 0 and len(self.selected_items) > 0: 
            src += '<a href="%s?action=start">' % request.path 
            src += '<img src="%s">' % iconurl(request, 'icons/box.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/box-gray.png')
        src += '</td>\n'

        #--- backup recursive button ---
        src += '<td align=center width=10%>'
        treeBackupPossible = False
        if len(self.selected_backups) == 0 and len(self.selected_items) == 1:
            selectedPathID = list(self.selected_items)[0]
            if backup_fs.HasChildsID(selectedPathID):
                treeBackupPossible = True
        if treeBackupPossible: 
            src += '<a href="%s?action=startrecursive">' % request.path 
            src += '<img src="%s">' % iconurl(request, 'icons/folder-tree-backup.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/folder-tree-backup-gray.png')
        src += '</td>\n'

        #--- delete backups button ---
        src += '<td align=center width=10%>'
        if len(self.selected_backups) > 0 or len(self.listExpandedVersions) > 0:
            # src += '<a href="%s?action=deletebackups">' % request.path
            if len(self.selected_backups) == 0:
                msg = 'Delete all backed up data stored on remote machines for selected items?'
            elif len(self.selected_backups) == 1:
                msg = 'You agree to erase this backup and delete corresponding data from remote machines?'
            else:
                msg = 'You agree to erase these <b>%d</b> backups and delete all corresponding data from remote machines?' % len(self.selected_backups)
            src += '<a href="%s">' % confirmurl(request, text=msg, back=back,
                yes='%s?action=deletebackups' % request.path)
            src += '<img src="%s">' % iconurl(request, 'icons/box-delete.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/box-delete-gray.png')
        src += '</td>\n'
        
        #--- select backups button ---
        src += '<td align=center width=10%>'
        if len(self.selected_items) > 0: # len(self.selected_backups) == 0 
            src += '<a href="%s?action=selectbackups">' % request.path
            src += '<img src="%s">' % iconurl(request, 'icons/select.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/select-gray.png')
        src += '</td>\n'

        #--- recursive select backups button ---
        src += '<td align=center width=10%>'
        if len(self.selected_items) > 0: # len(self.selected_backups) == 0 
            src += '<a href="%s?action=selectbackupsrecursive">' % request.path
            src += '<img src="%s">' % iconurl(request, 'icons/select-tree.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/select-tree-gray.png')
        src += '</td>\n'
        
        #--- restore button ---
        src += '<td align=center width=10%>'
        if len(self.selected_backups) > 0 and len(self.selected_items) == 0: 
            # src += '<a href="%s?action=restore">' % request.path
            msg = 'Restore selected items from remote machines<br>and place them to its original locations?'
            msg += '<br><font color=red><b>WARNING!</b></font><br>Existing files will be overwritten.'
            src += '<a href="%s">' % confirmurl(request, text=msg, back=back,
                yes='%s?action=restore' % request.path)
            src += '<img src="%s">' % iconurl(request, 'icons/restore.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/restore-gray.png')
        src += '</td>\n'

        #--- restore into folder button ---
        src += '<td align=center width=10%>'
        if len(self.selected_backups) > 0 and len(self.selected_items) == 0: 
            # src += '<a href="%s?action=restoretodir">' % request.path
            msg = 'Restore selected items from remote machines?<br><br>\n'
            msg += 'Your restored files will be placed into this location:<br>\n'
            msg += '<b>%(option:folder.folder-restore)s</b><br>'
            msg += '<a href="%s?back=%s">[change]</a><br>\n' % ('/'+_PAGE_SETTINGS+'/'+'folder.folder-restore', '/'+_PAGE_CONFIRM)
            src += '<a href="%s">' % confirmurl(request, text=msg, back=back, 
                yes='%s?action=restoretodir' % request.path)
            src += '<img src="%s">' % iconurl(request, 'icons/restoretodir.png')
            src += '</a>'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/restoretodir-gray.png')
        src += '</td>\n'
        
        src += '</tr>\n'

        #--- buttons labels ---
        src += '<tr valign=top>\n'
        src += '<td nowrap><font size=-2 color=gray>add folder<br>to the catalog</font></td>\n'
        src += '<td nowrap><font size=-2 color=gray>recursive add all<br>sub folders and files</font></td>\n'
        src += '<td nowrap><font size=-2 color=gray>remove from<br>catalog</font></td>\n'
        src += '<td nowrap><font size=-2 color=gray>backup to<br>remote peers</font></td>\n'
        src += '<td nowrap><font size=-2 color=gray>recursive backup<br>a directory</font></td>\n'
        src += '<td nowrap><font size=-2 color=gray>erase remote<br>data</font></td>\n'
        src += '<td nowrap><font size=-2 color=gray>select latest<br>versions</font></td>\n'
        src += '<td nowrap><font size=-2 color=gray>recursive select<br>latest versions</font></td>\n'
        src += '<td nowrap><font size=-2 color=gray>restore from<br>remote peers</font></td>\n'
        src += '<td nowrap><font size=-2 color=gray>restore to<br>given folder</font></td>\n'
        src += '</tr>\n'
        src += '</table>\n'

        if len(self.listExpandedDirs) == 0:
            # src += '<p>Add some files to backup on remote machines.</p>\n'
            src += html_comment('run "python bitpie.py add <folder path>" to add backup folder')
            # return src

        #--- list items
        if True:     
            src += '<hr width=100%>\n'
            # src += '<form action="%s" method="post">\n' % request.path
            # src += '<input type="submit" name="submit" value=" select "/>\n'
            # src += '<input type="hidden" name="action" value="select" />\n'
            src += '<table width=98% align=left cellspacing=0 cellpadding=0 border=0>\n'
            for type, pathID, localPath, sizeInBytes, versions in self.listExpandedDirs:
                if localPath in [settings.BackupIndexFileName(),]:
                    continue
                isExist = backup_fs.pathExist(localPath)
                x, x, name = localPath.rpartition('/')
                if len(name) == 2 and name[1] == ':':
                    name = name.capitalize()
                spaces = ('<img src="%s">' % iconurl(request, 'icons/white20x16.png')) * pathID.count('/')
                sizeString = diskspace.MakeStringFromBytes(sizeInBytes) if sizeInBytes else '&nbsp;'
                sizeVersions = 0
                versions_sorted = misc.sorted_versions(versions.keys(), reverse=True)
                for versionInfo in versions.values():
                    if versionInfo[1] > 0:
                        sizeVersions += versionInfo[1]
                backupsSize = 0 if contacts.numSuppliers() == 0 else sizeVersions/contacts.numSuppliers()

                src += '<tr>'
    
                src += '<td align=left valign=top nowrap>\n'
                src += spaces + '\n'
    
                #--- dir/file button
                if type in [ backup_fs.DIR, backup_fs.PARENT ] :
                    if pathID in self.expanded_dirs:
                        src += '<a href="%s?action=collapse&pathid=%s">' % (request.path, pathID)
                        src += '<img src="%s">' % iconurl(request, 'icons/dir-opened.png')
                        src += '</a>'
                    else:
                        src += '<a href="%s?action=expand&pathid=%s">' % (request.path, pathID)
                        src += '<img src="%s">' % iconurl(request, 'icons/dir-closed.png')
                        src += '</a>'
                else:
                    src += '<a href="%s?action=fileclicked&pathid=%s">' % (request.path, pathID)
                    src += '<img src="%s">' % iconurl(request, 'icons/file.png')
                    src += '</a>'
                
                #--- version box icon
                if len(versions_sorted) > 0:
                    isBackupSelected = False
                    if len(self.selected_backups) > 0:
                        for version in versions_sorted:
                            if pathID+'/'+version in self.selected_backups:
                                isBackupSelected = True
                                break
                    if pathID in self.expanded_items:
                        src += '<a href="%s?action=versionsclicked&pathid=%s">' % (request.path, pathID)
                        if backup_control.HasTask(pathID) or backup_control.IsPathInProcess(pathID):
                            src += '<img src="%s">' % iconurl(request, 'icons/hourglass20x16.png')
                        else:
                            if isBackupSelected:
                                src += '<img src="%s">' % iconurl(request, 'icons/box-open-selected.png')
                            else:
                                src += '<img src="%s">' % iconurl(request, 'icons/box-open.png')
                        src += '</a>'
                    else:
                        src += '<a href="%s?action=versionsclicked&pathid=%s">' % (request.path, pathID)
                        if backup_control.HasTask(pathID) or backup_control.IsPathInProcess(pathID):
                            src += '<img src="%s">' % iconurl(request, 'icons/hourglass20x16.png')
                        else:
                            if isBackupSelected:
                                src += '<img src="%s">' % iconurl(request, 'icons/box-close-selected.png')
                            else:
                                src += '<img src="%s">' % iconurl(request, 'icons/box-close.png')
                        src += '</a>'
                else:
                    if backup_control.HasTask(pathID):
                        src += '<a href="%s?action=versionsclicked&pathid=%s">' % (request.path, pathID)
                        src += '<img src="%s">' % iconurl(request, 'icons/hourglass20x16.png')
                        src += '</a>'
                    else:
                        src += '<img src="%s">' % iconurl(request, 'icons/white20x16.png')
                    
                src += '&nbsp;\n'
    
                #--- name and checkbox image
                # checkboxstate = 'checked' if pathID in self.selected_items else ''
                color = '' if isExist else 'color="#ffdddd"'
                itemname = misc.cut_long_string(name, 40, '...')
                if type in [ backup_fs.DIR, backup_fs.PARENT ] :
                    itemname = '[%s]' % itemname
                # label = misc.unicode_to_str_safe(itemname)
#                if not isExist:
#                    label += ' (not exist) '
                src += '<a href="%s?action=select&pathid=%s">' % (request.path, pathID.replace('/','_'))
                if pathID in self.selected_items:
                    src += '<img src="%s">' % iconurl(request, 'icons/checkbox-on.png')
                else: 
                    src += '<img src="%s">' % iconurl(request, 'icons/checkbox-off.png')
                src += '</a>'
                src += '<font size=+2 %s>' % color
                try:
                    src += misc.unicode_to_str_safe(itemname)
                except:
                    src += misc.unicode_to_str_safe(name[:40])
                src += '</font>'
#                src += '<input type="checkbox" fontweight="bold" name="pathid%s" value="1" label="%s" onclick=submit %s %s />' % (
#                    pathID.replace('/','_'), label, bgcolor, checkboxstate)
                src += '</td>\n'

                #--- image
                src += '<td nowrap width=100>\n'
                # if len(versions_sorted) > 0 and pathID not in self.expanded_items:
                if False: # dont want to show the image for all items because eat too much performance
                    backupID = pathID+'/'+versions_sorted[0]
                    backupIDurl = backupID.replace('/', '_')
                    src += '<a href="%s?back=%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_DIAGRAM+backupIDurl, request.path,)
                    src += '<img src="%s?type=bar&width=100&height=16" />' % (
                        iconurl(request, _PAGE_MAIN+'/'+_PAGE_BACKUP_IMAGE+backupIDurl))
                    src += '</a>\n'
                else:
                    src += '&nbsp;'
                src += '</td>\n'
    
                #--- versions size
                if sizeVersions > 0:
                    if pathID not in self.expanded_items:
                        src += '<td nowrap align=right>'
                        src += '<font size=-1 color=#80D080>%s</font>' % diskspace.MakeStringFromBytes(backupsSize)
                        src += '<font size=-1 color=gray>&nbsp;/&nbsp;</font>'
                        src += '<font size=-1 color=#8080D0>%s</font>' % diskspace.MakeStringFromBytes(sizeVersions)
                        src += '</td>\n'
                    else:
                        src += '<td nowrap align=right>&nbsp;</td>\n'
                else:
                    src += '<td nowrap align=right>&nbsp;</td>\n'

                #--- item size
                src += '<td nowrap align=right>'
                if isExist:
                    if type == backup_fs.PARENT:
                        src += '<font size=-1 color=gray>?</font>'
                    else:
                        src += '<font size=-1 color=gray>%s</font>' % sizeString
                else:
                    src += '&nbsp;'
                src += '</td>\n'

                src += '</tr>\n'

                #--- versions
                if len(versions_sorted) > 0 and pathID in self.expanded_items:
                    for version in versions_sorted:
                        backupID = pathID+'/'+version
                        backupIDurl = backupID.replace('/','_')
                        versionInfo = versions.get(version, [-1, -1])
                        src += '<tr>'
                        src += '<td align=left nowrap>\n'
                        src += spaces + '\n'
                        src += '<img src="%s">' % iconurl(request, 'icons/white20x16.png')
                        if restore_monitor.IsWorking(backupID):
                            src += '<img src="%s">' % iconurl(request, 'icons/restore16.png')
                        else:
                            src += '<img src="%s">' % iconurl(request, 'icons/white20x16.png')
                        src += '<a href="%s?back=%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+backupIDurl, request.path,)
                        src += '<img src="%s">' % iconurl(request, 'icons/document-green.png')
                        src += '</a>'
                        src += '&nbsp;\n'
                        src += '<a href="%s?action=select&backupid=%s">' % (request.path, backupIDurl)
                        if backupID in self.selected_backups:
                            src += '<img src="%s">' % iconurl(request, 'icons/checkbox-on.png')
                        else: 
                            src += '<img src="%s">' % iconurl(request, 'icons/checkbox-off.png')
                        src += '</a>'
                        src += '<font size=+2>'
                        # src += '<a href="%s?back=%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+backupIDurl, request.path,)
                        src += version
                        # src += '</a>'
                        src += '</font>'
                        # src += '<input type="checkbox" name="backupid%s" value="1" label="%s" onclick=submit %s />' % (
                        #     backupID.replace('/','_'), version, ('checked' if backupID in self.selected_backups else ''))
                        src += '</td>\n'
                        src += '<td nowrap width=100>\n'
                        if bpio.Linux():
                            src += '&nbsp;'
                        else:
                            src += '<a href="%s?back=%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_DIAGRAM+backupIDurl, request.path,)
                            src += '<img src="%s?type=bar&width=100&height=16" />' % (
                                iconurl(request, _PAGE_MAIN+'/'+_PAGE_BACKUP_IMAGE+backupIDurl))
                            src += '</a>\n'
                        src += '</td>\n'
                        if versionInfo[1] >= 0:
                            supplierSize = 0 if contacts.numSuppliers() == 0 else versionInfo[1]/contacts.numSuppliers()
                            src += '<td nowrap align=right>'
                            src += '<font size=-1 color=#80D080>%s</font>' % diskspace.MakeStringFromBytes(supplierSize)
                            src += '<font size=-1 color=gray>&nbsp;/&nbsp;</font>'
                            src += '<font size=-1 color=#8080D0>%s</font>' % diskspace.MakeStringFromBytes(versionInfo[1])
                            src += '</td>\n'  
                        else:
                            src += '<td>&nbsp;</td>\n'
                        src += '<td>&nbsp;</td>\n'
                        src += '</tr>\n'
            src += '</table>\n'
            src += '</form>\n'
            src += '<hr width=100%>\n'
        return src
        
    def _action(self, request):
        action = arg(request, 'action').strip()
        back = arg(request, 'back', request.path)
        self.htmlComment = ''

        #---diradd---
        if action == 'diradd':
            opendir = unicode(misc.unpack_url_param(arg(request, 'opendir'), ''))
            if opendir:
                newPathID, iter, iterID = backup_fs.AddDir(opendir, True)
                dirsize.ask(opendir, backup_control.FoundFolderSize, (newPathID, None))
                backup_fs.Calculate()
                backup_control.Save()
                self.listExpandedDirs = None
                self.listExpandedVersions = None
                self.htmlComment += html_comment('new folder was added:')
                self.htmlComment += html_comment('  %s %s' % (newPathID.ljust(27), opendir.ljust(70)))
                
        #---diraddrecursive---
        elif action == 'diraddrecursive':
            opendir = unicode(misc.unpack_url_param(arg(request, 'opendir'), ''))
            if opendir:
                newPathID, iter, iterID, num = backup_fs.AddLocalPath(opendir, True)
                backup_fs.Calculate()
                backup_control.Save()
                if newPathID:
                    for parentPathID in packetid.parentPathsList(newPathID):
                        self.expanded_dirs.add(parentPathID)
                    self.htmlComment += html_comment('%d items were added to catalog, parent path ID is:' % num)
                    self.htmlComment += html_comment('  %s %s' % (newPathID.ljust(27), opendir.ljust(70)))
                self.listExpandedDirs = None
                self.listExpandedVersions = None

        #---fileselected---
        elif action == 'fileadd':
            openfile = unicode(misc.unpack_url_param(arg(request, 'openfile'), ''))
            if openfile:
                newPathID, iter, iterID = backup_fs.AddFile(openfile, True)
                backup_fs.Calculate()
                backup_control.Save()
                self.listExpandedDirs = None
                self.listExpandedVersions = None
                self.htmlComment += html_comment('new file was added:')
                self.htmlComment += html_comment('  %s %s' % (newPathID.ljust(27), openfile.ljust(70)))

        #---expand---
        elif action == 'expand':
            pathid = arg(request, 'pathid')
            if pathid:
                self.expanded_dirs.add(pathid)
                if pathid in self.selected_items:
                    for type, subPathID, localPath, sizeInBytes, versions in backup_fs.ListSelectedFolders([pathid,]):
                        if subPathID.startswith(pathid+'/'):
                            self.selected_items.add(subPathID)
                self.listExpandedDirs = None
                self.listExpandedVersions = None

        #---collapse---
        elif action == 'collapse':
            pathid2remove = arg(request, 'pathid')
            if pathid2remove:
                eraselist = set()
                for pathid in self.expanded_dirs:
                    if pathid.startswith(pathid2remove):
                        eraselist.add(pathid)
                self.expanded_dirs.difference_update(eraselist)
                if pathid2remove in self.selected_items:
                    for type, subPathID, localPath, sizeInBytes, versions in backup_fs.ListSelectedFolders(eraselist):
                        if subPathID.startswith(pathid2remove+'/'):
                            self.selected_items.discard(subPathID)
                del eraselist
                self.listExpandedDirs = None
                self.listExpandedVersions = None

        #---versionsclicked---
        elif action == 'versionsclicked':
            pathid = arg(request, 'pathid', '')
            self.expanded_items.symmetric_difference_update(set([pathid,]))
        
        #---select---
        elif action == 'select':
            clickedPathID = arg(request, 'pathid').replace('_','/')
            clickedBackupID = arg(request, 'backupid').replace('_','/')
            if clickedPathID:
                self.selected_backups.clear()
                listExpandedItems = backup_fs.ListSelectedFolders(self.expanded_dirs)
                subItemsSelected = set()
                state = 0
                isAlreadyExpanded = False
                # if clicked item is expanded - remember that
                if clickedPathID in self.expanded_dirs:
                    isAlreadyExpanded = True
                # scan all selected items and see who is our childs
                for selectedPathID in self.selected_items:
                    if selectedPathID.startswith(clickedPathID+'/'):
                        subItemsSelected.add(selectedPathID)
                if clickedPathID not in self.selected_items:
                    if not isAlreadyExpanded:
                        state = 5 # clicked low level unchecked item        
                    else:
                        if len(subItemsSelected) == 0:
                            state = 1 # dir is clear, files is clear        -
                        else:
                            state = 4 # dir is clear, some files is checked 
                else:
                    if not isAlreadyExpanded:
                        state = 6 # clicked low level checked item          
                    else:
                        if len(subItemsSelected) == 0:
                            state = 2 # dir is checked, files is clear        
                        else:
                            state = 3 # dir is checked, some files also checked  
                if state == 1: # check on dir, keep files clear
                    for type, fsPathID, localPath, sizeInBytes, versions in listExpandedItems:
                        if clickedPathID.startswith(fsPathID+'/'): # this is a top level item
                            self.selected_items.discard(fsPathID)
                    self.selected_items.add(clickedPathID)
                elif state == 2: # keep dir checked, check sub items, uncheck top level items
                    for type, fsPathID, localPath, sizeInBytes, versions in listExpandedItems:
                        if fsPathID.startswith(clickedPathID+'/'): # this is our sub item - check it
                            self.selected_items.add(fsPathID)
                        if clickedPathID.startswith(fsPathID+'/'): # this is a top level item - uncheck
                            self.selected_items.discard(fsPathID)
                    self.selected_items.add(clickedPathID)
                elif state == 3: # uncheck dir, keep sub items checked, uncheck top level items
                    for type, fsPathID, localPath, sizeInBytes, versions in listExpandedItems:
                        if clickedPathID.startswith(fsPathID+'/'): # this is a top level item - uncheck 
                            self.selected_items.discard(fsPathID)
                    self.selected_items.discard(clickedPathID)
                elif state == 4: # keep dir unchecked, uncheck all files    
                    self.selected_items.difference_update(subItemsSelected) # uncheck sub items
                    for type, fsPathID, localPath, sizeInBytes, versions in listExpandedItems:
                        if clickedPathID.startswith(fsPathID+'/'): # this is a top level item - uncheck 
                            self.selected_items.discard(fsPathID)
                    self.selected_items.discard(clickedPathID)
                elif state == 5: # check that item, but uncheck all top level items   
                    for type, fsPathID, localPath, sizeInBytes, versions in listExpandedItems:
                        if clickedPathID.startswith(fsPathID+'/'): 
                            self.selected_items.discard(fsPathID)
                    self.selected_items.add(clickedPathID)
                elif state == 6: # just uncheck that item
                    self.selected_items.discard(clickedPathID)
                del listExpandedItems
                del subItemsSelected
            if clickedBackupID:
                self.selected_items.clear()
                self.selected_backups.symmetric_difference_update(set([clickedBackupID]))
                  
        #---selectbackups---
        elif action == 'selectbackups':
            # self.selected_backups.clear()
            for pathID in self.selected_items:
                item = backup_fs.GetByID(pathID)
                if item:
                    versions = item.list_versions(sorted=True, reverse=True)
                    if len(versions) > 0:
                        self.selected_backups.add(pathID+'/'+versions[0])
            self.selected_items.clear()
                    
        #---selectbackupsrecursive---
        elif action == 'selectbackupsrecursive':
            # self.selected_backups.clear()
            for pathID in self.selected_items:
                iter_and_path = backup_fs.WalkByID(pathID)
                if iter_and_path:
                    backup_fs.TraverseByID(lambda subpathID, path, info: self._selectionVisitor(pathID, subpathID, path, info), iter_and_path[0])
            self.selected_items.clear()
                            
        #---start---
        elif action == 'start':
            for pathID in self.selected_items:
                backup_control.StartSingle(pathID)
            if len(self.selected_items) < 10:
                for pathID in self.selected_items:
                    self.expanded_items.add(pathID)
            self.selected_items.clear()
            self.listExpandedDirs = None
            self.listExpandedVersions = None

        #---startpath---
        elif action == 'startpath':
            localPath = unicode(misc.unpack_url_param(arg(request, 'path'), ''))
            if backup_fs.pathExist(localPath):
                pathID = backup_fs.ToID(localPath)
                if pathID is None:
                    if backup_fs.pathIsDir(localPath):
                        pathID, iter, iterID = backup_fs.AddDir(localPath, True)
                        self.htmlComment += html_comment('new folder was added:')
                    else:
                        pathID, iter, iterID = backup_fs.AddFile(localPath, True)
                        self.htmlComment += html_comment('new file was added:')
                    backup_control.StartSingle(pathID)
                    backup_fs.Calculate()
                    backup_control.Save()
                    self.listExpandedDirs = None
                    self.listExpandedVersions = None
                    self.htmlComment += html_comment('  %s' % localPath)
                else:
                    backup_control.StartSingle(pathID)
                self.htmlComment += html_comment('  %s : backup started' % pathID)

        #---startid---
        elif action == 'startid':
            pathID = misc.unpack_url_param(arg(request, 'pathid'), '')
            if pathID:
                localPath = backup_fs.ToPath(pathID)
                if localPath is not None:
                    if backup_fs.pathExist(localPath):
                        backup_control.StartSingle(pathID)
                        backup_fs.Calculate()
                        backup_control.Save()
                        self.listExpandedDirs = None
                        self.listExpandedVersions = None
                        self.htmlComment += html_comment('  %s' % misc.unicode_to_str_safe(localPath))
                        self.htmlComment += html_comment('  %s : backup started' % pathID)
                    
        #---startrecursive---
        elif action == 'startrecursive':
            if len(self.selected_items) == 1:
                backup_control.StartRecursive(self.selected_items.pop())
            self.listExpandedDirs = None
            self.listExpandedVersions = None

        #---delete---
        elif action == 'delete':
            for pathID in self.selected_items:
                backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
                backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
                backup_fs.DeleteByID(pathID)
                for subPathID in list(self.expanded_dirs):
                    if subPathID.startswith(pathID+'/'):
                        self.expanded_dirs.discard(subPathID)
                self.expanded_dirs.discard(pathID)
                self.expanded_items.discard(pathID)
            self.selected_backups.clear()
            self.selected_items.clear()
            backup_fs.Scan()
            backup_fs.Calculate()
            backup_control.Save()
            backup_monitor.Restart()
            self.listExpandedDirs = None
            self.listExpandedVersions = None
            
        #---deletebackups---
        elif action == 'deletebackups':
            modified = False
            if len(self.selected_backups) > 0:
                for backupID in self.selected_backups:
                    backup_control.DeleteBackup(backupID, saveDB=False, calculate=False)
                    modified = True
                self.selected_backups.clear()
            if len(self.selected_items) > 0:
                for pathID in self.selected_items:
                    backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
                    self.expanded_items.discard(pathID)
                    modified = True
                self.selected_items.clear()
            if modified:
                backup_fs.Scan()
                backup_fs.Calculate()
                backup_control.Save()
                backup_monitor.Restart()
            self.listExpandedDirs = None
            self.listExpandedVersions = None
        
        #---deleteid---
        elif action == 'deleteid':
            pathID = arg(request, 'pathid').replace('_','/')
            if packetid.Valid(pathID):
                if packetid.IsCanonicalVersion(pathID.split('/')[-1]):
                    backup_control.DeleteBackup(pathID, saveDB=False, calculate=False)
                else:
                    backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
                    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
                    backup_fs.DeleteByID(pathID)
                    for subPathID in list(self.expanded_dirs):
                        if subPathID.startswith(pathID+'/'):
                            self.expanded_dirs.discard(subPathID)
                    self.expanded_dirs.discard(pathID)
                    self.expanded_items.discard(pathID)
                    self.selected_backups.clear()
                    self.selected_items.clear()
                backup_fs.Scan()
                backup_fs.Calculate()
                backup_control.Save()
                backup_monitor.Restart()
                self.listExpandedDirs = None
                self.listExpandedVersions = None

        #---deletepath---
        elif action == 'deletepath':
            localPath = unicode(misc.unpack_url_param(arg(request, 'path'), ''))
            pathID = backup_fs.ToID(localPath)
            if pathID and packetid.Valid(pathID):
                backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
                backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
                backup_fs.DeleteByID(pathID)
                for subPathID in list(self.expanded_dirs):
                    if subPathID.startswith(pathID+'/'):
                        self.expanded_dirs.discard(subPathID)
                self.expanded_dirs.discard(pathID)
                self.expanded_items.discard(pathID)
                self.selected_backups.clear()
                self.selected_items.clear()
                backup_fs.Scan()
                backup_fs.Calculate()
                backup_control.Save()
                backup_monitor.Restart()
                self.listExpandedDirs = None
                self.listExpandedVersions = None
        
        #---update---
        elif action == 'update':
            backup_monitor.Restart()
            self.listExpandedDirs = None
            self.listExpandedVersions = None
        
        #---restore---
        elif action == 'restore':
            for backupID in self.selected_backups:
                if backup_control.IsBackupInProcess(backupID):
                    continue
                pathID, version = packetid.SplitBackupID(backupID)
                if backup_control.HasTask(pathID):
                    continue
                localPath = backup_fs.ToPath(pathID)
                if not localPath:
                    continue
                restoreDir = os.path.dirname(localPath)
                restore_monitor.Start(backupID, restoreDir, self._itemRestored) 
            self.selected_backups.clear()
            
        #---restoretodir---
        elif action == 'restoretodir':
            for backupID in self.selected_backups:
                if backup_control.IsBackupInProcess(backupID):
                    continue
                pathID, version = packetid.SplitBackupID(backupID)
                if backup_control.HasTask(pathID):
                    continue
                localPath = backup_fs.ToPath(pathID)
                if not localPath:
                    continue
                if len(localPath) > 3 and localPath[1] == ':' and localPath[2] == '/':
                    # need to remove leading drive letter 
                    # even if we are not under windows - we may restore in other OS 
                    # so if the second character is ':' and third is '/' - means path starts from drive letter 
                    # here we assume the path is in portable form - separator is "/"
                    # TODO - also may need to check other options like network drive (//) or so 
                    localPath = localPath[3:]
                # remove the leading separator - for Linux we want to have relative path
                localPath = localPath.lstrip('/')
                # get the base folder - tar extract will take care of creating all directoriy tree 
                localDir = os.path.dirname(localPath)
                # make a restore dir, keep the folders tree, this will be a relative path
                restoreDir = os.path.join(settings.getRestoreDir(), localDir)
                restore_monitor.Start(backupID, restoreDir)
            self.selected_backups.clear()
        
        #---restoresingle---
        elif action == 'restoresingle':
            backupID = arg(request, 'backupid')
            dest = unicode(misc.unpack_url_param(arg(request, 'dest'), ''))
            if not backup_control.IsBackupInProcess(backupID):
                pathID, version = packetid.SplitBackupID(backupID)
                if not backup_control.HasTask(pathID):
                    localPath = backup_fs.ToPath(pathID)
                    if localPath:
                        if dest:
                            if len(localPath) > 3 and localPath[1] == ':' and localPath[2] == '/':
                                # TODO - also may need to check other options like network drive (//) or so 
                                localPath = localPath[3:]
                            localDir = os.path.dirname(localPath.lstrip('/'))
                            restoreDir = os.path.join(dest, localDir)
                            restore_monitor.Start(backupID, restoreDir)
                        else:
                            restoreDir = os.path.dirname(localPath)
                            restore_monitor.Start(backupID, restoreDir, self._itemRestored) 
                        self.selected_backups.clear()
                        self.htmlComment += html_comment('  %s : restore started to %s' % (backupID, restoreDir))

        #---cancelall---
        elif action == 'cancelall':
            backup_control.DeleteAllTasks()
            backup_control.AbortAllRunningBackups()
            self.listExpandedDirs = None
            self.listExpandedVersions = None
            
        #---list---
        elif action == 'list':
            src = ''
            src += html_comment('  %s %s %s' % ('[path ID]'.ljust(27), '[local path / version]'.ljust(70), '[size]'))
            for pathID, localPath, item in backup_fs.IterateIDs():
                sz = diskspace.MakeStringFromBytes(item.size) if item.exist() else 'not exist' 
                src += html_comment('  %s %s %s' % (pathID.ljust(27), localPath.ljust(70), sz.ljust(9)))
                for version, vinfo in item.get_versions().items():
                    if vinfo[1] >= 0:
                        szver = diskspace.MakeStringFromBytes(vinfo[1]/contacts.numSuppliers())+' / '+diskspace.MakeStringFromBytes(vinfo[1]) 
                    else:
                        szver = '?'
                    src += html_comment('  %s   %s %s' % (' '*27, version.ljust(70), szver))
            return html(request, body=str(src),)
        
        #---idlist---
        elif action == 'idlist':
            src = ''
            src += html_comment('  %s %s %s' % ('[path ID]'.ljust(37), '[size]'.ljust(20), '[local path]'))
            for backupID, versionInfo, localPath in backup_fs.ListAllBackupIDsFull(True, True):
                if versionInfo[1] >= 0 and contacts.numSuppliers() > 0:
                    szver = diskspace.MakeStringFromBytes(versionInfo[1]) + ' / ' + diskspace.MakeStringFromBytes(versionInfo[1]/contacts.numSuppliers()) 
                else:
                    szver = '?'
                szver = diskspace.MakeStringFromBytes(versionInfo[1]) if versionInfo[1] >= 0 else '?'
                src += html_comment('  %s %s %s' % (backupID.ljust(37), szver.ljust(20), localPath))
            return html(request, body=str(src),)
        else:
            return None
            
        return 0
    
    def _itemRestored(self, backupID, result): 
        backup_fs.ScanID(packetid.SplitBackupID(backupID)[0])
        backup_fs.Calculate()
        
    def _selectionVisitor(self, pathID, subpathID, path, info):
        versions = info.list_versions(sorted=True, reverse=True)
        if len(versions) > 0:
            self.selected_backups.add(pathID+'/'+subpathID+'/'+versions[0])
    
    def getChild(self, path, request):
        if path == '':
            return self
        elif path.startswith(_PAGE_BACKUP_IMAGE):
            return BackupDiagramImage(path)
        elif path.startswith(_PAGE_BACKUP):
            return BackupPage(path)
        elif path.startswith(_PAGE_BACKUP_LOCAL_FILES):
            return BackupLocalFilesPage(path)
        elif path.startswith(_PAGE_BACKUP_REMOTE_FILES):
            return BackupRemoteFilesPage(path)
        elif path.startswith(_PAGE_BACKUP_DIAGRAM):
            return BackupDiagramPage(path)

    def renderPage(self, request):
        if contacts.numSuppliers() == 0:
            src = ''
            src += '<h1>my files</h1>\n'
            src += '<table width="80%"><tr><td align=left>\n'
            src += '<p>List of your suppliers is empty.\n '
            src += 'This may be due to the fact that the connection to the Central server is not established yet\n'
            src += 'or the Central server can not find the number of users that meet your requirements.</p>\n'
            src += '<p>Wait a bit or check your backups options in the settings.\n '
            src += 'If you request too much needed space, you may not find the right number of suppliers.</p><br>\n'
            src += '</td></tr></table>\n'
            src += html_comment(
                'List of your suppliers is empty.\n'+
                'This may be due to the fact that the connection to the Central server is not established yet\n'+
                'or the Central server can not find the number of users that meet your requirements.')
            return html(request, body=str(src), title='my files', back='', reload=reload )
        
        ret = self._action(request)
        if ret == NOT_DONE_YET:
            return ret

        src = self._body(request)
        
        src += '<br><br><table><tr><td><div align=left>\n'
        availibleSpace = diskspace.MakeStringFromString(settings.getMegabytesNeeded())
        backupsSizeTotal = backup_fs.sizebackups()
        backupsSizeSupplier = -1 if contacts.numSuppliers() == 0 else backupsSizeTotal/contacts.numSuppliers()
        usedSpaceTotal = diskspace.MakeStringFromBytes(backupsSizeTotal)
        usedSpaceSupplier = '-' if backupsSizeSupplier<0 else diskspace.MakeStringFromBytes(backupsSizeSupplier)
        src += 'availible space:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="%s">%s</a><br>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'central-settings.needed-megabytes?back='+request.path, availibleSpace,)
        src += 'total space used:&nbsp;&nbsp;<a href="%s">%s</a><br>\n' % ('/'+_PAGE_STORAGE, usedSpaceTotal) 
        src += 'used per supplier:&nbsp;%s\n' % (usedSpaceSupplier) 
        src += '</div></td></tr></table>\n'

        src += html_comment('availible space :  %s' % availibleSpace)
        src += html_comment('total space used:  %s' % usedSpaceTotal)
        src += html_comment('used per supplier: %s' % usedSpaceSupplier)

        src += '<p><a href="%s?action=update">Request my suppliers to check my backups now</a></p>\n' % request.path
        src += '<p><a href="%s">Check the backup settings</a></p>\n' % ('/'+_PAGE_BACKUP_SETTINGS+'?back='+request.path,)
        # src += '<p><a href="%s" target=_blank>Get help on this page</a></p>\n' % help_url(self.pagename)

        return html(request, body=str(src), title='my files', back='')


class CentralPage(Page):
    pagename = _PAGE_CENTRAL
    def renderPage(self, request):
        src = ''
        return src
    
    
class AutomatsPage(Page):
    pagename = _PAGE_AUTOMATS
    def renderPage(self, request):
        src = ''
        for index, object in automat.objects().items():
            src += html_comment('  %s %s %s' % (
                str(index).ljust(4), 
                str(object.id).ljust(50), 
                object.state))
        return src
    

class MenuPage(Page):
    pagename = _PAGE_MENU
    
    def renderPage(self, request):
        global _MenuItems
        menuLabels = _MenuItems.keys()
        menuLabels.sort()
        w, h = misc.calculate_best_dimension(len(menuLabels))
        imgW = 128
        imgH = 128
        if w >= 4:
            imgW = 4 * imgW / w
            imgH = 4 * imgH / w
        padding = 64/w - 8
        back = arg(request, 'back', request.path)
        src = ''
        src += '<br><tr><td align=center>\n'
        src += '<table cellpadding=%d cellspacing=2>\n' % padding
        for y in range(h):
            src += '<tr valign=top>\n'
            for x in range(w):
                n = y * w + x
                src += '<td align=center valign=top>\n'
                if n >= len(menuLabels):
                    src += '&nbsp;\n'
                    continue
                label = menuLabels[n]
                link_url, icon_url = _MenuItems[label]
                if link_url.find('?') < 0:
                    link_url += '?back=' + back
                label = label.split('|')[1]
                src += '<a href="%s?back=%s">' % (link_url, request.path)
                src += '<img src="%s" width=%d height=%d>' % (
                    iconurl(request, icon_url),
                    imgW, imgH,)
                src += '<br>[%s]' % label
                src += '</a>\n'
                src += '</td>\n'
                src += html_comment('    [%s] %s' % (label, link_url))
            src += '</tr>\n'
        src += '</table>\n'
        src += '</td></tr></table>\n'
        src += '<br><br>\n'
        shutdown_link = confirmurl(request, 
            yes=request.path+'?action=exit', 
            text='Do you want to stop BitPie.NET?',
            back=back)
        return html(request, body=src, home='', title='menu', back=back, next='<a href="%s">[shutdown]</a>' % shutdown_link)


class BackupIDSplit:
    def splitpath(self, path):
        self.path = path
        x, x, self.backupIDurl = self.path.partition('_') 
        self.backupID = self.backupIDurl.replace('_', '/')
        self.pathID, self.version = packetid.SplitBackupID(self.backupID)
    def getfsitem(self):
        iter_path = backup_fs.WalkByID(self.pathID)
        if iter_path:
            self.fsitem, self.localPath = iter_path
            self.isDir = isinstance(self.fsitem, dict)
            if self.isDir:
                self.fsitem = self.fsitem[backup_fs.INFO_KEY]
            if self.fsitem.type == backup_fs.PARENT or self.fsitem.size == 0: 
                self.size = dirsize.getInBytes(self.localPath, 0)
            else:
                self.size = max(self.fsitem.size, 0)
        else:
            self.fsitem = None
            self.localPath = None
            self.isDir = None
            self.size = 0
        

class BackupPage(Page, BackupIDSplit):
    pagename = _PAGE_BACKUP
    def __init__(self, path):
        Page.__init__(self)
        self.splitpath(path)
        self.getfsitem()
        self.sizeStr = diskspace.MakeStringFromBytes(self.size) if self.size > 0 else ''
        self.isExist = os.path.exists(self.localPath)

    def _itemRestored(self, backupID, result):
        backup_fs.ScanID(self.pathID)
        backup_fs.Calculate()

    def _renderRunningPage(self, request, backupObj):
        totalPercent, totalNumberOfFiles, local_backup_size, maxBlockNum, statsArray = backup_matrix.GetBackupLocalStats(self.backupID)
        blockNumber = backupObj.blockNumber + 1
        dirSizeBytes = 0
        folder_or_file = 'folder' if self.isDir else 'file'
        dirSizeBytes = self.size
        dataSent = backupObj.dataSent
        blocksSent = backupObj.blocksSent
        percent = 0.0
        if dirSizeBytes > 0: # non zero and not None
            if dataSent > dirSizeBytes:
                dataSent = dirSizeBytes
            percent = 100.0 * dataSent / dirSizeBytes
        # percentSupplier = 0.0 if contacts.numSuppliers() == 0 else 100.0 / contacts.numSuppliers()
        # sizePerSupplier = 0.0 if contacts.numSuppliers() == 0 else dirSizeBytes / contacts.numSuppliers()
        w, h = misc.calculate_best_dimension(contacts.numSuppliers())
        imgW, imgH, padding =  misc.calculate_padding(w, h)
        #---info---
        src = ''
        src += '<table width=95%><tr><td align=center>'
        src += '<h3>%s</h3>\n' % misc.wrap_long_string(str(self.localPath), 60, '<br>\n')
        src += '<p><a href="%s">%s</a></p>\n' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl, self.backupID) 
        src += html_comment('  [%s] %s' % (self.backupID, self.localPath)) 
        src += '<table width=90%><tr><td align=center>\n'
        src += '<p align=justify>This backup is currently running.\n'
        src += 'Contents of the %s will be compressed, encrypted and divided into blocks. \n' % folder_or_file
        src += 'After this BitPie.NET will monitor your data and restore the missing blocks. </p>\n'
        src += html_comment('  this backup is currently running')
        src += '<p align=justify>'
        if dirSizeBytes == 0:
            src += '%s size is unknown, ' % folder_or_file.capitalize()
            src += 'currently <b>%s</b> read. ' % diskspace.MakeStringFromBytes(dataSent)
            src += 'Backup copy contains <b>%d</b> files at this point.\n' % totalNumberOfFiles
            src += html_comment('  %s size is unknown' % folder_or_file)
            src += html_comment('  currently %s read' % diskspace.MakeStringFromBytes(dataSent))
            src += html_comment('  backup copy contains %d files at this point' % totalNumberOfFiles)
        elif dataSent < dirSizeBytes:
            src += 'Currently <b>%s</b> read from total <b>%s</b> %s size, ' % (
                diskspace.MakeStringFromBytes(dataSent), diskspace.MakeStringFromBytes(dirSizeBytes), folder_or_file)
            src += 'this is <b>%s</b>.\n' % misc.percent2string(percent)
            src += 'Backup copy contains <b>%d</b> files at this point.\n' % totalNumberOfFiles
            src += html_comment('  currently %s read from total %s size, this is %s' % (
                diskspace.MakeStringFromBytes(dataSent), diskspace.MakeStringFromBytes(dirSizeBytes), misc.percent2string(percent)))
            src += html_comment('  backup copy contains %d files at this point' % totalNumberOfFiles)
        else:
            src += '%s size is <b>%s</b>, all the files have been processed ' % (
                folder_or_file.capitalize(), diskspace.MakeStringFromBytes(dirSizeBytes))
            src += 'and divided into <b>%s</b> blocks in <b>%d</b> files.\n' % (blockNumber, totalNumberOfFiles)
            src += html_comment('  %s size is %s, all %d files have been processed and divided into %s blocks' % (
                folder_or_file, diskspace.MakeStringFromBytes(dirSizeBytes), totalNumberOfFiles, blockNumber))
        src += ' Encrypted <b>%d</b> blocks of data.\n' % blocksSent
        src += html_comment('  encrypted %d blocks of data' % blocksSent)
#         if blockNumber > 0:
#             percent_complete = 100.0 * blocksSent / (blockNumber + 1) 
#             src += ' Backup is <b>%s</b> complete.\n' % misc.percent2string(percent_complete)
#             src += html_comment('  backup is %s complete' % misc.percent2string(percent_complete))
        src += '</p>\n'
        src += '</td></tr></table>\n'
        #---suppliers---
#        src += '<table cellpadding=%d cellspacing=2>\n' % padding
#        for y in range(h):
#            src += '<tr valign=top>\n'
#            for x in range(w):
#                src += '<td align=center valign=top>\n'
#                supplierNum = y * w + x
#                link = '/' + _PAGE_SUPPLIERS + '/' + str(supplierNum) + '?back=%s' % request.path
#                if supplierNum >= contacts.numSuppliers():
#                    src += '&nbsp;\n'
#                    continue
#                idurl = contacts.getSupplierID(supplierNum)
#                name = nameurl.GetName(idurl)
#                if not name:
#                    src += '&nbsp;\n'
#                    continue
#                if idurl:
#                    icon = 'icons/offline-user01.png'
#                else:
#                    icon = 'icons/unknown-user01.png'
#                state = 'offline'
#                if contact_status.isOnline(idurl):
#                    icon = 'icons/online-user01.png'
#                    state = 'online'
#                if w >= 5 and len(name) > 10:
#                    name = name[0:9] + '<br>' + name[9:]
#                src += '<a href="%s">' % link
#                src += '<img src="%s" width=%d height=%d>' % (
#                    iconurl(request, icon),
#                    imgW, imgH,)
#                src += '</a><br>\n'
#                percSupplier, filesNum = statsArray[supplierNum]
#                src += '%d files for<br>\n' % (filesNum)
#                src += '<a href="%s">%s</a><br>\n' % (link, name)
#                src += html_comment('    %d files for %s [%s]' % (filesNum, name, state))
#                src += '</td>\n'
#            src += '</tr>\n'
#        src += '</table>\n'
        #---buttons---
        src += '<table width=1 align=center cellspacing=20 cellpadding=0 border=0>'
        src += '<tr>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        if self.isExist:
            src += '<a href="%s?action=explore">' % request.path
            src += '<img src="%s">' % iconurl(request, 'icons/explore48.png') 
            src += '</a>\n'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/explore48-gray.png')
        src += '<br><font size=-1 color=gray>explore this<br>local %s</font>\n' % folder_or_file
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_REMOTE_FILES+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/remote-files48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>show remote files<br>stored on<br>suppliers machines</font>\n' 
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_LOCAL_FILES+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/local-files48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>show local files<br>stored on HDD</font>\n' 
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_DIAGRAM+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/chart48.png') 
        src += '</a>\n' 
        src += '<br><font size=-1 color=gray>let\'s see<br>the big picture</font>\n'
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s?action=backup.abort">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/backup-abort48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>abort this backup</font>\n' 
        src += '</td>\n'
        src += '</tr>\n'
        src += '</table>\n'
        return html(request, body=src, back='/'+_PAGE_MAIN)

    def _renderRestoringPage(self, request, restoreObj):
        bstats = restore_monitor.GetProgress(self.backupID)
        totalPercent, totalNumberOfFiles, local_backup_size, maxBlockNum, statsLocalArray = backup_matrix.GetBackupLocalStats(self.backupID)
        w, h = misc.calculate_best_dimension(contacts.numSuppliers())
        imgW, imgH, padding =  misc.calculate_padding(w, h)
        maxBlockNum = backup_matrix.GetKnownMaxBlockNum(self.backupID)
        currentBlock = max(0, restoreObj.BlockNumber)
        folder_or_file = 'folder' if self.isDir else 'file'
        #---info---
        src = '<h3>%s</h3>\n' % misc.wrap_long_string(str(self.localPath), 60, '<br>\n')
        src += '<p><a href="%s">%s</a></p>\n' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl, self.backupID) 
        src += html_comment('  [%s] %s' % (self.backupID, self.localPath)) 
        src += '<table width=90%><tr><td align=center>\n'
        src += '<p align=justify>This backup is currently restoring,\n'
        src += 'your data is downloaded from remote computers and will be decrypted.\n'
        src += 'It should be noted that if too many remote suppliers became offline - ' 
        src += 'you need to wait until they become available to restore your data.</p>\n'
        src += '<p>Currently restoring <b>%d</b>th block from all <b>%d</b> blocks.</p>' % (currentBlock, maxBlockNum+1)
        src += '</td></tr></table>\n'
        src += html_comment('  this backup is currently restoring')
        #---suppliers---
        src += '<table cellpadding=%d cellspacing=2>\n' % padding
        for y in range(h):
            src += '<tr valign=top>\n'
            for x in range(w):
                src += '<td align=center valign=top>\n'
                supplierNum = y * w + x
                link = '/' + _PAGE_SUPPLIERS + '/' + str(supplierNum) + '?back=%s' % request.path
                if supplierNum >= contacts.numSuppliers():
                    src += '&nbsp;\n'
                    continue
                idurl = contacts.getSupplierID(supplierNum)
                name = nameurl.GetName(idurl)
                if not name:
                    src += '&nbsp;\n'
                    continue
                if idurl:
                    icon = 'icons/offline-user01.png'
                else:
                    icon = 'icons/unknown-user01.png'
                state = 'offline'
                if contact_status.isOnline(idurl):
                    icon = 'icons/online-user01.png'
                    state = 'online '
                if w >= 5 and len(name) > 10:
                    name = name[0:9] + '<br>' + name[9:]
                src += '<a href="%s">' % link
                src += '<img src="%s" width=%d height=%d>' % (
                    iconurl(request, icon),
                    imgW, imgH,)
                src += '</a><br>\n'
                received = bstats.get(supplierNum, 0)
                try:
                    localFiles = statsLocalArray[supplierNum][1]
                except:
                    localFiles = 0
                src += '%d files on hand' % localFiles
                comment = '%d files on hand' % localFiles
                if received > 0:  
                    sreceived = diskspace.MakeStringFromBytes(received)
                    src += '<br>received %s' % sreceived
                    comment += ', received %s' % sreceived
                src += ' from<br><a href="%s">%s</a>\n' % (link, name)
                comment += ' from %s' % name
                src += '</td>\n'
                src += html_comment(comment)
            src += '</tr>\n'
        src += '</table>\n'
        #---buttons---
        src += '<table width=1 align=center cellspacing=20 cellpadding=0 border=0>'
        src += '<tr>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_REMOTE_FILES+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/remote-files48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>show remote files<br>stored on<br>suppliers machines</font>\n' 
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_LOCAL_FILES+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/local-files48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>show local files<br>stored on HDD</font>\n' 
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_DIAGRAM+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/chart48.png') 
        src += '</a>\n' 
        src += '<br><font size=-1 color=gray>let\'s see<br>the big picture</font>\n'
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s?action=restore.abort">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/restore-abort48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>abort restoring</font>\n' 
        src += '</td>\n'
        src += '</tr>\n'
        src += '</table>\n'
        return html(request, body=src, back='/'+_PAGE_MAIN)

    def _renderBackupPage(self, request):
        src = ''
        back = arg(request, 'back', '/'+_PAGE_MAIN)
        blocks, percent, weakBlock, weakPercent = backup_matrix.GetBackupRemoteStats(self.backupID)
        localPercent, localFiles, totalSize, maxBlockNum, localStats = backup_matrix.GetBackupLocalStats(self.backupID)
        start_tm = misc.TimeFromBackupID(self.version)
        start_dt, start_suf = misc.getDeltaTime(start_tm)
        #---info---
        src = '<h3>%s</h3>\n' % misc.wrap_long_string(str(self.localPath), 60, '<br>\n')
        src += html_comment('  [%s] %s' % (self.backupID, self.localPath))
        folder_or_file = 'folder' if self.isDir else 'file' 
        if self.isExist: 
            src += 'This %s exists on local HDD<br>\n' % folder_or_file
            src += html_comment('  this %s exists on local HDD' % folder_or_file)
        else:
            src += '<font color=red>This %s does not exist on local HDD</font><br>\n' % folder_or_file
            src += html_comment('  this %s does not exist on local HDD' % folder_or_file)
        if self.sizeStr: 
            src += 'Known %s size is %s<br>\n' % (folder_or_file, self.sizeStr)
            src += html_comment('  known %s size is %s' % (folder_or_file, self.sizeStr))
#         else:
#             src += '<font color=red>%s size unknown</font><br>\n' % (folder_or_file.capitalize()) 
#             src += html_comment('  %s size unknown' % folder_or_file)
        src += 'Full backup ID is <b>%s</b><br>\n' % self.backupID
        if maxBlockNum >= 0:
            src += 'Backed up data contains <b>%d</b> blocks and ready at <b>%s</b>.<br>' % (maxBlockNum + 1, misc.percent2string(weakPercent))
            src += 'Delivered <b>%s</b> and <b>%s</b> is stored on local HDD.' % (misc.percent2string(percent), misc.percent2string(localPercent))  
            src += html_comment('  contains %d blocks and ready by %s' % (maxBlockNum + 1, misc.percent2string(weakPercent)))
            src += html_comment('  %s delivered, %s stored' % (misc.percent2string(percent), misc.percent2string(localPercent)))
        else:
            src += 'No information about this backup yet.<br>'
            src += html_comment('  no information about this backup yet')
        src += '<br><br>\n'
        #---buttons---
        src += '<table width=1 align=center cellspacing=20 cellpadding=0 border=0>'
        src += '<tr>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s?action=restore">' % request.path
        src += '<img src="%s">' % iconurl(request, 'icons/restore48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>restore this<br>%s from<br>remote peers</font>\n' % folder_or_file 
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        msg = 'Restore this %s from remote machines and put into this location:<br>\n' % folder_or_file 
        msg += '<b>%(option:folder.folder-restore)s</b> ?<br>'
        msg += '<a href="%s?back=%s">[change]</a><br>\n' % ('/'+_PAGE_SETTINGS+'/'+'folder.folder-restore', '/'+_PAGE_CONFIRM)
        src += '<a href="%s">' % confirmurl(request, text=msg, back=back, 
            yes='%s?action=restoretodir' % request.path)
        src += '<img src="%s">' % iconurl(request, 'icons/restore-to-dir48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>restore %s into<br>specified location</font>\n' % folder_or_file 
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        if self.isExist:
            src += '<a href="%s?action=explore">' % request.path
            src += '<img src="%s">' % iconurl(request, 'icons/explore48.png') 
            src += '</a>\n'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/explore48-gray.png')
        src += '<br><font size=-1 color=gray>explore this<br>local %s</font>\n' % folder_or_file
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_REMOTE_FILES+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/remote-files48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>show remote files<br>stored on<br>suppliers machines</font>\n' 
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_LOCAL_FILES+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/local-files48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>show local files<br>stored on HDD</font>\n' 
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP_DIAGRAM+self.backupIDurl)
        src += '<img src="%s">' % iconurl(request, 'icons/chart48.png') 
        src += '</a>\n' 
        src += '<br><font size=-1 color=gray>let\'s see<br>the big picture</font>\n'
        src += '</td>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        src += '<a href="%s?action=delete">' % request.path
        src += '<img src="%s">' % iconurl(request, 'icons/delete-backup48.png') 
        src += '</a>\n'
        src += '<br><font size=-1 color=gray>delete this<br>backup forever</font>\n' 
        src += '</td>\n'
        src += '</tr>\n'
        src += '</table>\n'
        return html(request, body=src, back=back)

    def _action(self, request): 
        action = arg(request, 'action')
        #---delete---
        if action == 'delete':
            backup_control.DeleteBackup(self.backupID, saveDB=False)
            backup_control.Save()
            backup_monitor.Restart()
            request.redirect('/'+_PAGE_MAIN)
            request.finish()
            return NOT_DONE_YET
        #---delete.local---
        elif action == 'delete.local':
            num, sz = backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), self.backupID)
            backup_matrix.EraseBackupLocalInfo(self.backupID)
            backup_fs.ScanID(self.pathID)
            backup_fs.Calculate()
            src = '<br><br><br>\n'
            if num > 0:
                src += '%d files were removed with a total size of %s' % (num, diskspace.MakeStringFromBytes(sz))
                src += html_comment('  %d files were removed with a total size of %s' % (num, diskspace.MakeStringFromBytes(sz)))
            else:
                src += 'This backup does not contain any files stored on your hard disk.'
                src += html_comment('  this backup does not contain any files stored on your hard disk.')
            src += '<br><br>\n'
            src += '<a href="%s">[return]</a>\n' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl)
            return html(request, body=src, back=request.path)
        #---restore---
        elif action == 'restore':
            if not backup_control.IsBackupInProcess(self.backupID):
                if not backup_control.HasTask(self.pathID):
                    if self.localPath:
                        restore_monitor.Start(self.backupID, os.path.dirname(self.localPath), self._itemRestored) 
        #---restoretodir---
        elif action == 'restoretodir':
            if not backup_control.IsBackupInProcess(self.backupID):
                if not backup_control.HasTask(self.pathID):
                    if self.localPath:
                        restorePath = self.localPath
                        if len(restorePath) > 3 and restorePath[1] == ':' and restorePath[2] == '/':
                            # need to remove leading drive letter 
                            # even if we are not under windows - we may restore in other OS 
                            # so if the second character is ':' and third is '/' - means path starts from drive letter 
                            # here we assume the path is in portable form - separator is "/"
                            # TODO - also may need to check other options like network drive (//) or so 
                            restorePath = restorePath[3:]
                        restoreDir = os.path.dirname(restorePath)
                        restore_monitor.Start(self.backupID, os.path.join(settings.getRestoreDir(), restoreDir))
        #---explore---
        elif action == 'explore':
            if self.isExist:
                misc.ExplorePathInOS(self.localPath)
        #---restore.abort---
        elif action == 'restore.abort':
            restore_monitor.Abort(self.backupID)
        #---backup.abort---
        elif action == 'backup.abort':
            backup_control.AbortRunningBackup(self.backupID)
            request.redirect('/'+_PAGE_MAIN)
            request.finish()
            return NOT_DONE_YET
        else:
            return None
        return 0

    def renderPage(self, request):
        ret = self._action(request)
        if ret == NOT_DONE_YET:
            return ret
        backupObj = backup_control.GetRunningBackupObject(self.backupID)
        if backupObj is not None:
            return self._renderRunningPage(request, backupObj)
        restoreObj = restore_monitor.GetWorkingRestoreObject(self.backupID)
        if restoreObj is not None:
            return self._renderRestoringPage(request, restoreObj)
        return self._renderBackupPage(request)
            

class BackupLocalFilesPage(Page, BackupIDSplit):
    pagename = _PAGE_BACKUP_LOCAL_FILES
    def __init__(self, path):
        Page.__init__(self)
        self.splitpath(path)
        self.getfsitem()
        
    def renderPage(self, request):
        localPercent, numberOfFiles, totalSize, maxBlockNum, bstats = backup_matrix.GetBackupLocalStats(self.backupID)
        w, h = misc.calculate_best_dimension(contacts.numSuppliers())
        imgW, imgH, padding = misc.calculate_padding(w, h)
        #---info---
        src = '<h3>%s</h3>\n' % misc.wrap_long_string(str(self.localPath), 60, '<br>\n')
        src += '<p><a href="%s">%s</a></p>\n' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl, self.backupID) 
        src += html_comment('  [%s] %s' % (self.backupID, self.localPath)) 
        src += '<table width=95%><tr><td align=center><p align=justify>'
        src += 'Here is a list of local files stored on your hard drive for this backup.\n '
        src += 'This local copy of your backup folder will allow instantaneous data recovery in case of it loss.\n '
        src += 'If you wish these files can be deleted to save space on your disk.<br>\n'
        src += 'At the moment, saved <b>%d</b> files with total size of <b>%s</b>, this is <b>%s</b> of the whole data.<br>\n' % (
            numberOfFiles, diskspace.MakeStringFromBytes(totalSize), misc.percent2string(localPercent))
        src += '</p></td></tr></table>\n'
        src += html_comment('  saved %d files with total size of %s' % (numberOfFiles, diskspace.MakeStringFromBytes(totalSize)))
        #---suppliers---
        src += '<table cellpadding=%d cellspacing=2>\n' % padding #width="90%%"
        for y in range(h):
            src += '<tr valign=top>\n'
            for x in range(w):
                src += '<td align=center valign=top>\n'
                supplierNum = y * w + x
                link = '/' + _PAGE_SUPPLIERS + '/' + str(supplierNum) + '?back=%s' % request.path
                if supplierNum >= contacts.numSuppliers():
                    src += '&nbsp;\n'
                    continue
                idurl = contacts.getSupplierID(supplierNum)
                name = nameurl.GetName(idurl)
                if not name:
                    src += '&nbsp;\n'
                    continue
                if idurl:
                    icon = 'icons/offline-user01.png'
                else:
                    icon = 'icons/unknown-user01.png'
                state = 'offline'
                if contact_status.isOnline(idurl):
                    icon = 'icons/online-user01.png'
                    state = 'online '
                if w >= 5 and len(name) > 10:
                    name = name[0:9] + '<br>' + name[9:]
                src += '<a href="%s">' % link
                src += '<img src="%s" width=%d height=%d>' % (
                    iconurl(request, icon),
                    imgW, imgH,)
                src += '</a><br>\n'
                if supplierNum < len(bstats):
                    percent, localFiles = bstats[supplierNum]
                    src += misc.percent2string(percent)
                    src += ' in %d/%d files<br>for ' % (localFiles, 2 * (maxBlockNum + 1))
                    src += '<a href="%s">%s</a>\n' % (link, name)
                src += '</td>\n'
                src += html_comment('    %s in %d/%d files for %s [%s]' % (
                    misc.percent2string(percent), localFiles, 2 * (maxBlockNum + 1), name, state))
            src += '</tr>\n'
        src += '</table>\n'
        #---buttons---
        src += '<table width=1 align=center cellspacing=20 cellpadding=0 border=0>'
        src += '<tr>\n'
        src += '<td align=center valign=top width=70 nowrap>'
        if not backup_control.IsBackupInProcess(self.backupID) and not restore_monitor.IsWorking(self.backupID):
            src += '<a href="%s?action=delete.local">' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl)
            src += '<img src="%s">' % iconurl(request, 'icons/delete-local-files48.png') 
            src += '</a>\n'
        else:
            src += '<img src="%s">' % iconurl(request, 'icons/delete-local-files-gray48.png')
        src += '<br><font size=-1 color=gray>remove local files<br>for this backup</font>\n' 
        src += '</td>\n'
        src += '</tr>\n'
        src += '</table>\n'
        return html(request, body=src, back='/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl)


class BackupRemoteFilesPage(Page, BackupIDSplit):
    pagename = _PAGE_BACKUP_REMOTE_FILES
    def __init__(self, path):
        Page.__init__(self)
        self.splitpath(path)
        self.getfsitem()
        
    def renderPage(self, request):
        totalNumberOfFiles, maxBlockNumber, bstats = backup_matrix.GetBackupStats(self.backupID)
        blocks, percent = backup_matrix.GetBackupBlocksAndPercent(self.backupID)
        w, h = misc.calculate_best_dimension(contacts.numSuppliers())
        imgW, imgH, padding =  misc.calculate_padding(w, h)
        versionSize = 0
        if self.fsitem:
            versionSize = self.fsitem.get_version_info(self.version)[1]
            if versionSize < 0:
                versionSize = 0
        supplierSize = diskspace.MakeStringFromBytes(versionSize/contacts.numSuppliers())
        totalSize = diskspace.MakeStringFromBytes(versionSize)
        #---info---
        src = '<h3>%s</h3>\n' % misc.wrap_long_string(str(self.localPath), 60, '<br>\n')
        src += '<p><a href="%s">%s</a></p>\n' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl, self.backupID) 
        src += html_comment('  [%s] %s' % (self.backupID, self.localPath)) 
        src += '<table width=70%><tr><td align=center><p align=justify>'
        src += 'Each supplier keeps a piece of that backup.\n '
        src += 'Here you see the overall condition and availability of data at the moment.\n'
        if versionSize > 0:
            src += '<br>This backup contains <b>%d</b> blocks in <b>%d</b> remote files and ' % (blocks, totalNumberOfFiles)
            src += 'ready by <b>%s</b>. ' % misc.percent2string(percent)
            src += 'Each supplier should store <b>%s</b> and the total size is <b>%s</b>.\n' % (supplierSize, totalSize)
        src += '</p></td></tr></table>\n'
        src += html_comment('  this backup contains %d blocks in %d files and ready by %s' % (
            blocks, totalNumberOfFiles, misc.percent2string(percent)))
        src += html_comment('  each supplier should store %s and the total size is %s' % (supplierSize, totalSize))
        #---suppliers---
        src += '<table cellpadding=%d cellspacing=2>\n' % padding
        for y in range(h):
            src += '<tr valign=top>\n'
            for x in range(w):
                src += '<td align=center valign=top>\n'
                supplierNum = y * w + x
                link = '/' + _PAGE_SUPPLIERS + '/' + str(supplierNum) + '?back=%s' % request.path
                if supplierNum >= contacts.numSuppliers():
                    src += '&nbsp;\n'
                    continue
                idurl = contacts.getSupplierID(supplierNum)
                name = nameurl.GetName(idurl)
                if not name:
                    src += '&nbsp;\n'
                    continue
                if idurl:
                    icon = 'icons/offline-user01.png'
                else:
                    icon = 'icons/unknown-user01.png'
                state = 'offline'
                if contact_status.isOnline(idurl):
                    icon = 'icons/online-user01.png'
                    state = 'online '
                if w >= 5 and len(name) > 10:
                    name = name[0:9] + '<br>' + name[9:]
                src += '<a href="%s">' % link
                src += '<img src="%s" width=%d height=%d>' % (
                    iconurl(request, icon),
                    imgW, imgH,)
                src += '</a><br>\n'
                percent, remoteFiles = (bstats[supplierNum] if supplierNum < len(bstats) else (0, 0))
                if remoteFiles > 0:
                    src += misc.percent2string(percent)
                    src += ' in %d/%d files<br>on ' % (remoteFiles, 2 * (maxBlockNumber + 1))
                src += '<a href="%s">%s</a>\n' % (link, name)
                src += '</td>\n'
                src += html_comment('    %s in %d/%d files on %s [%s]' % (
                    misc.percent2string(percent), remoteFiles, 2 * (maxBlockNumber + 1), name, state))
            src += '</tr>\n'
        src += '</table>\n'
        return html(request, body=src, back='/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl)
    

class BackupDiagramPage(Page, BackupIDSplit):
    pagename = _PAGE_BACKUP_DIAGRAM
    def __init__(self, path):
        Page.__init__(self)
        self.splitpath(path)
        self.getfsitem()
    
    def renderPage(self, request):
        src = '<h3>%s</h3>\n' % misc.wrap_long_string(str(self.localPath), 60, '<br>\n')
        src += '<p><a href="%s">%s</a></p>\n' % ('/'+_PAGE_MAIN+'/'+_PAGE_BACKUP+self.backupIDurl, self.backupID) 
        src += html_comment('  [%s] %s' % (self.backupID, self.localPath))
        src += '<br><br>\n'
        src += '<img width=300 height=300 src="%s?type=circle&width=300&height=300" />\n' % (
           iconurl(request, _PAGE_MAIN+'/'+_PAGE_BACKUP_IMAGE+self.backupIDurl))
        src += '<br><br><table>\n'
        src += '<tr><td><table border=1 cellspacing=0 cellpadding=0><tr>'
        src += '<td bgcolor="#20f220">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td>local and remote copy is available</td></tr>\n'
        src += '<tr><td><table border=1 cellspacing=0 cellpadding=0><tr>'
        src += '<td bgcolor="#20b220">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td>no local data but remote copy is available</td></tr>\n'
        src += '<tr><td><table border=1 cellspacing=0 cellpadding=0><tr>'
        src += '<td bgcolor="#a2a2f2">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td>remote data exist but not available, local copy is here</td></tr>\n'
        src += '<tr><td><table border=1 cellspacing=0 cellpadding=0><tr>'
        src += '<td bgcolor="#d2d2d2">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td>only local block exist</td></tr>\n'
        src += '<tr><td><table border=1 cellspacing=0 cellpadding=0><tr>'
        src += '<td bgcolor="#e2e282">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td>only remote copy exist but not available</td></tr>\n'
        src += '</table>\n'
        src += '<br>\n'
        return html(request, body=src, back='/'+_PAGE_MAIN, reload='3')
        

class BackupDiagramImage(resource.Resource, BackupIDSplit):
    pagename = _PAGE_BACKUP_IMAGE
    def __init__(self, path):
        self.splitpath(path)
        self.getfsitem()
    
    def toInt(self, f):
        return int(round(f))
    
    def render_GET(self, request):
        global _BackupDiagramColors
        request.responseHeaders.setRawHeaders("content-type", ['image/png'])
        try:
            import Image
            import ImageDraw
            import ImageFont
            import cStringIO
        except:
            #  bpio.exception()
            # 1x1 png picture 
            src = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAAXNSR0IArs4c6QAAAARnQU1BAACx\njwv8YQUAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAABp0RVh0\nU29mdHdhcmUAUGFpbnQuTkVUIHYzLjUuMTAw9HKhAAAADElEQVQYV2P4//8/AAX+Av6nNYGEAAAA\nAElFTkSuQmCC\n'
            bin = misc.AsciiToBinary(src)
            request.write(bin)
            request.finish()
            return NOT_DONE_YET
        type = arg(request, 'type')
        width = misc.ToInt(arg(request, 'width'), 64)
        height = misc.ToInt(arg(request, 'height'), 64)
        img = Image.new("RGB", (width, height), "#fff")
        draw = ImageDraw.Draw(img)
        f = cStringIO.StringIO()
        try:
            font = ImageFont.truetype(settings.FontImageFile(), 12)
        except:
            font = None
        if not self.backupID:
            img.save(f, "PNG")
            f.seek(0)
            request.write(f.read())
            request.finish()
            f.close()
            return NOT_DONE_YET
        arrayLocal = backup_matrix.GetBackupLocalArray(self.backupID)
        arrayRemote = backup_matrix.GetBackupRemoteArray(self.backupID)
        suppliersActive = backup_matrix.suppliers_set().GetActiveArray()
        w = backup_matrix.suppliers_set().supplierCount
        h = backup_matrix.GetKnownMaxBlockNum(self.backupID) + 1
        backupObj = backup_control.GetRunningBackupObject(self.backupID)
        if backupObj is not None:
            if self.size > 0:
                h = ( self.size / backupObj.blockSize ) + 1 
        if h == 0 or w == 0:
            img.save(f, "PNG")
            f.seek(0)
            request.write(f.read())
            request.finish()
            f.close()
            return NOT_DONE_YET
        if type == 'bar':
            dx = float(width-2) / float(h)
            dy = float(height-2) / float(w)
            for x in range(h): # blocks
                for y in range(w): # suppliers
                    for DP in ['D', 'P']:
                        remote = (0 if (arrayRemote is None or not arrayRemote.has_key(x)) else (0 if arrayRemote[x][DP][y] != 1 else 1))
                        active = suppliersActive[y]
                        local = (0 if (arrayLocal is None or not arrayLocal.has_key(x)) else arrayLocal[x][DP][y])
                        color = _BackupDiagramColors[DP]['%d%d%d' % (local, remote, active)]
                        x0 = 1 + x * dx
                        y0 = 1 + y * dy
                        if DP == 'P':
                            draw.polygon([
                                (self.toInt(x0),                self.toInt(y0)),
                                (self.toInt(x0),                self.toInt(y0 + dy)), 
                                (self.toInt(x0 + dx / 2.0 - 1), self.toInt(y0 + dy)), 
                                (self.toInt(x0 + dx / 2.0 - 1), self.toInt(y0)),], 
                                fill=color, outline=None)
                        else: 
                            draw.polygon([
                                (self.toInt(x0 + dx / 2.0),     self.toInt(y0)),
                                (self.toInt(x0 + dx / 2.0),     self.toInt(y0 + dy)), 
                                (self.toInt(x0 + dx - 1),       self.toInt(y0 + dy)), 
                                (self.toInt(x0 + dx - 1),       self.toInt(y0)),], 
                                fill=color, outline=None) 
            draw.polygon([(0,0), (0, height-1), (width-1, height-1), (width-1, 0)], fill=None, outline="#555555")
        elif type == 'circle':
            x0 = (width - 2) / 2.0
            y0 = (height - 2) / 2.0
            R = float(min(width, height)) / 2.0 - 1
            dR = R / float(h) 
            dA = 360.0 / float(w)
            for x in range(h): # blocks
                for y in range(w): # suppliers
                    for DP in ['D', 'P']:
                        remote = (0 if (arrayRemote is None or not arrayRemote.has_key(x)) else (0 if arrayRemote[x][DP][y] != 1 else 1))
                        active = suppliersActive[y]
                        local = (0 if (arrayLocal is None or not arrayLocal.has_key(x)) else arrayLocal[x][DP][y])
                        color = _BackupDiagramColors[DP]['%d%d%d' % (local, remote, active)]
                        r1 = R - dR * x
                        r12 = R - dR * x - dR/2.0
                        r2 = R - dR * x - dR
                        if DP == 'D':
                            box = (self.toInt(x0 - r1), self.toInt(y0 - r1),
                                   self.toInt(x0 + r1), self.toInt(y0 + r1))
                        else:
                            box = (self.toInt(x0 - r12), self.toInt(y0 - r12),
                                   self.toInt(x0 + r12), self.toInt(y0 + r12))
                        start = float(y) * dA
                        end = start + dA
                        draw.pieslice(box, self.toInt(start), self.toInt(end), fill=color, outline=None)
            for y in range(w):
                start = float(y) * dA
                end = start + dA
                draw.pieslice(( self.toInt(x0 - R), self.toInt(y0 - R), 
                                self.toInt(x0 + R), self.toInt(y0 + R)),
                                self.toInt(start), self.toInt(end), outline='#555555', fill=None)
            if width > 256 and height > 256:
                for supplierNum in range(w):
                    a = float(supplierNum) * dA + dA / 2.0 
                    x1 = math.cos(a * math.pi / 180.0) * R * 0.7 + x0
                    y1 = math.sin(a * math.pi / 180.0) * R * 0.7 + y0
                    draw.text((x1-20, y1-5), 
                              '%s' % nameurl.GetName(contacts.getSupplierID(supplierNum)), 
                              fill="#000000", font=font)
        img.save(f, "PNG")
        f.seek(0)
        request.write(f.read())
        request.finish()
        f.close()
        return NOT_DONE_YET


class SupplierPage(Page):
    pagename = _PAGE_SUPPLIER
    ## isLeaf = True
    def __init__(self, path):
        Page.__init__(self)
        self.path = path
        try:
            self.index = int(self.path)
        except:
            self.index = -1
            self.idurl = ''
            self.name = ''
            return
        self.idurl = contacts.getSupplierID(self.index)
        protocol, host, port, self.name = nameurl.UrlParse(self.idurl)
        self.name = self.name.strip()[0:-4]

    def renderPage(self, request):
        back = arg(request, 'back', '/'+_PAGE_SUPPLIERS)
        src = ''
        if self.idurl == '':
            src = '<h1>Unknown supplier</h1>\n'
            return html(request, body=src)

        action = arg(request, 'action')

        #---replace
        if action == 'replace':
            msg = ''
            msg += '<font color=red><b>WARNING!</b></font><br>\n'
            msg += 'After changing one of your suppliers BitPie.NET start the rebuilding process to distribute your data.\n' 
            msg += 'This takes some time depending on data size and network speed.<br>\n'
            msg += 'If you change your suppliers too often you can loose your backed up data!<br>' 
            msg += 'Do you want to replace user <b>%s</b> with someone else?' % nameurl.GetName(self.idurl)
            replace_link = confirmurl(request, 
                yes='%s?action=yes.replace&back=%s' % (request.path, back), 
                text=msg,
                back=back)
            request.redirect(replace_link)
            request.finish()
            return NOT_DONE_YET
        elif action == 'yes.replace':
            url = '%s?action=replace&idurl=%s&back=%s' % ('/'+_PAGE_SUPPLIERS, misc.pack_url_param(self.idurl), request.path)
            request.redirect(url)
            request.finish()
            return NOT_DONE_YET

        bytesNeeded = diskspace.GetBytesFromString(settings.getMegabytesNeeded(), 0)
        bytesUsed = backup_fs.sizebackups() # backup_db.GetTotalBackupsSize() * 2
        suppliers_count = contacts.numSuppliers()
        if suppliers_count > 0: 
            bytesNeededPerSupplier = bytesNeeded / suppliers_count 
            bytesUsedPerSupplier = bytesUsed / suppliers_count
        else:
            bytesNeededPerSupplier = bytesUsedPerSupplier = 0
        try:
            percUsed = (100.0 * bytesUsedPerSupplier / bytesNeededPerSupplier)
        except:
            percUsed = 0.0

        #---draw
        src += '<h1>%s</h1>\n' % nameurl.GetName(self.idurl)
        src += '<table>\n'
        src += '<tr><td>IDURL</td><td><a href="%s" target="_blank">%s</a></td></tr>\n' % (self.idurl, self.idurl)
        src += '<tr><td>gives you</td><td>%s on his HDD</td></tr>\n' % diskspace.MakeStringFromBytes(bytesNeededPerSupplier)
        src += '<tr><td>your files takes</td><td>%s at the moment</td></tr>\n' % diskspace.MakeStringFromBytes(bytesUsedPerSupplier)
        src += '<tr><td>currenly taken</td><td>%3.2f%% space given to you</td></tr>\n' % percUsed
        src += '<tr><td>current status is</td><td>'
        if contact_status.isOnline(self.idurl):
            src += '<font color="green">online</font>\n'
        else:
            src += '<font color="red">offline</font>\n'
        src += '</td></tr>\n'
        src += '<tr><td>month rating</td><td>%s%% - %s/%s</td></tr>\n' % ( ratings.month_percent(self.idurl), ratings.month(self.idurl)['alive'], ratings.month(self.idurl)['all'])
        src += '</table>\n'
        src += '<br><br>\n'
        src += '<p><a href="%s?action=replace&back=%s">Fire <b>%s</b> and find another person to store My Files</a></p>\n' % (
            request.path, back, self.name)
        src += '<p><a href="%s/change?back=%s">I want to swap <b>%s</b> with another person, whom I will choose</a></p>\n' % (
            request.path, back, self.name)
        src += '<p><a href="%s/remotefiles?back=%s">Show me a list of My Files stored on <b>%s\'s</b> machine</a></p>\n' % (
            request.path, back, self.name)
        src += '<p><a href="%s/localfiles?back=%s">Print a list of My Files stored on my machine but intended for <b>%s</b></a></p>\n' % (
            request.path, back, self.name)
        src += '<br><br>\n'
        return html(request, body=src, back=back, title=self.name)

    def getChild(self, path, request):
        if self.idurl == '':
            return self
        if path == 'remotefiles':
            return SupplierRemoteFilesPage(self.idurl)
        elif path == 'localfiles':
            return SupplierLocalFilesPage(self.idurl)
        elif path == 'change':
            return SupplierChangePage(self.idurl)
        return self
    
class SupplierRemoteFilesPage(Page):
    pagename = _PAGE_SUPPLIER_REMOTE_FILES
    def __init__(self, idurl):
        Page.__init__(self)
        self.idurl = idurl
        self.supplierNum = contacts.numberForSupplier(self.idurl)
        self.name = nameurl.GetName(self.idurl)
        
    def renderPage(self, request):
        back = arg(request,'back','/'+_PAGE_SUPPLIERS+'/'+str(self.supplierNum))
        title = 'remote files on %s' % self.name
        action = arg(request, 'action')
        src = '<h1>%s</h1>\n' % title
        
        if action == 'files':
            packetID = p2p_service.RequestListFiles(self.supplierNum)
            src += html_message('list of your files were requested', 'notify')

        list_files_src = bpio.ReadTextFile(settings.SupplierListFilesFilename(self.idurl))
        if list_files_src:
            src += '<table width=70%><tr><td align=center>\n'
            src += '<div><code>\n'
            src += list_files_src[list_files_src.find('\n'):].replace('\n', '<br>\n').replace(' ', '&nbsp;')
            src += '</code></div>\n</td></tr></table>\n'
        else:
            src += '<p>no information about your files received yet</p>\n'
        src += '<p><a href="%s?action=files&back=%s">Request a list of My Files from %s</a></p>\n' % (request.path, back, self.name)
        return html(request, body=src, back=back, title=title)

class SupplierLocalFilesPage(Page):
    pagename = _PAGE_SUPPLIER_LOCAL_FILES

    def __init__(self, idurl):
        Page.__init__(self)
        self.idurl = idurl
        self.supplierNum = contacts.numberForSupplier(self.idurl)
        self.name = nameurl.GetName(self.idurl)
        
    def renderPage(self, request):
        back = arg(request,'back','/'+_PAGE_SUPPLIERS+'/'+str(self.supplierNum))
        title = 'local files for %s' % self.name
        src = '<h1>%s</h1>\n' % title
        list_files = []
        for filename in os.listdir(settings.getLocalBackupsDir()):
            if filename.startswith('newblock-'):
                continue
            try:
                backupID, blockNum, supplierNum, dataORparity  = filename.split('-')
                blockNum = int(blockNum)
                supplierNum = int(supplierNum)
            except:
                continue
            if dataORparity not in ['Data', 'Parity']:
                continue
            if supplierNum != self.supplierNum:
                continue
            list_files.append(filename)
        if len(list_files) > 0:
            src += '<table width=70%><tr><td align=center>\n'
            src += '<div><code>\n'
            for filename in list_files:
                src += filename + '<br>\n' 
            src += '</code></div>\n</td></tr></table>\n'
        else:
            src += '<p>no files found</p>\n' 
        return html(request, body=src, back=back, title=title)

class SupplierChangePage(Page):
    pagename = _PAGE_SUPPLIER_CHANGE

    def __init__(self, idurl):
        Page.__init__(self)
        self.idurl = idurl
        self.supplierNum = contacts.numberForSupplier(self.idurl)
        self.name = nameurl.GetName(self.idurl)
        
    def renderPage(self, request):
        back = arg(request, 'back', '/'+_PAGE_SUPPLIERS)
        action = arg(request, 'action')
        if action == 'do.change':
            newidurl = arg(request, 'newidurl')
            url = '%s?action=change&idurl=%s&newidurl=%s&back=%s' % (
                '/'+_PAGE_SUPPLIERS, misc.pack_url_param(self.idurl), 
                misc.pack_url_param(newidurl), request.path)
            request.redirect(url)
            request.finish()
            return NOT_DONE_YET
        src = ''
        src += '<br><br><br><br>\n'
        src += '<table width=50%><tr><td align=center>\n'
        src += '<p>'
        src += '<font color=red><b>WARNING!</b></font><br>\n'
        src += 'After changing one of your suppliers BitPie.NET start the rebuilding process to distribute your data.\n' 
        src += 'This takes some time depending on data size and network speed.<br>\n'
        src += 'If you change your suppliers too often you can loose your backed up data!'
        src += '</p><br><br>\n'
        src += '<p>Type a username or IDURL here:</p>\n' 
        src += '<form action="%s">\n' % request.path
        src += '<input type="text" name="newidurl" value="" size=60 /><br><br>\n'
        src += '<input type="submit" name="submit" value=" swap supplier " />\n'
        src += '<input type="hidden" name="action" value="do.change" />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % request.path
        src += '</form>\n'
        src += '</td></tr></table>\n'
        return html(request, body=src, back=back, title=self.name)
        

class SuppliersPage(Page):
    pagename = _PAGE_SUPPLIERS
    def __init__(self):
        Page.__init__(self)
        self.show_ratings = False

    def renderPage(self, request):
        back = arg(request, 'back', '/'+_PAGE_MENU)
        #---show_ratings---
        if arg(request, 'ratings') == '1':
            self.show_ratings = True
        elif arg(request, 'ratings') == '0':
            self.show_ratings = False
            
        action = arg(request, 'action')
        #---action call---
        if action == 'call':
            
            # transport_control.ClearAliveTimeSuppliers()
            # contact_status.check_contacts(contacts.getSupplierIDs())
            propagate.SlowSendSuppliers(0.2)
            # request.redirect(request.path)
            # request.finish()
            # return NOT_DONE_YET
            #SendCommandToGUI('open %s' % request.path)
            
        #---action request---
        elif action == 'request':
            pass
            # central_service.clear_users_statuses(contacts.getSupplierIDs())
            # central_service.SendRequestSuppliers()
        
        #---action replace---
        elif action == 'replace':
            idurl = arg(request, 'idurl')
            if idurl != '':
                if not idurl.startswith('http://'):
                    try:
                        idurl = contacts.getSupplierID(int(idurl))
                    except:
                        idurl = 'http://'+settings.IdentityServerName()+'/'+idurl+'.xml'
                if contacts.IsSupplier(idurl):
                    fire_hire.AddSupplierToFire(idurl)
                    backup_monitor.Restart()
                    # fire_hire.A('fire-him-now', [idurl,])
        
        #---action change---
        elif action == 'change':
            idurl = arg(request, 'idurl')
            newidurl = arg(request, 'newidurl')
            if idurl != '' and newidurl != '':
                if not idurl.startswith('http://'):
                    try:
                        idurl = contacts.getSupplierID(int(idurl))
                    except:
                        idurl = 'http://'+settings.IdentityServerName()+'/'+idurl+'.xml'
                if not newidurl.startswith('http://'):
                    newidurl = 'http://'+settings.IdentityServerName()+'/'+newidurl+'.xml'
                if contacts.IsSupplier(idurl):
                    # fire_hire.A('fire-him-now', (idurl, newidurl))
                    fire_hire.A('fire-him-now', [idurl,])

        #---draw page---
        src = ''
        src += '<p>my username is <a href="%s" target=_blank>@:</a>%s</p>\n' % (misc.getLocalID(), misc.getIDName())
        src += '<h1>my suppliers</h1>\n'

        if contacts.numSuppliers() > 0:
            w, h = misc.calculate_best_dimension(contacts.numSuppliers())
            #DEBUG
            #w = 8; h = 8
#            paddingX = str(40/w)
#            paddingY = str(160/h)
#            fontsize = str(60 + 200/(w*w))
#            fontsize = str(10-w)
            imgW = 64
            imgH = 64
            if w >= 4:
                imgW = 4 * imgW / w
                imgH = 4 * imgH / w
            padding = 64 / w - 8 
            src += html_comment('  index status    user                 month rating         total rating' ) 
            src += '<table cellpadding=%d cellspacing=2>\n' % padding #width="90%%"
            for y in range(h):
                src += '<tr valign=top>\n'
                for x in range(w):
                    src += '<td align=center valign=top>\n'
                    n = y * w + x
                    link = _PAGE_SUPPLIERS+'/'+str(n)+'?back='+back
                    if n >= contacts.numSuppliers():
                        src += '&nbsp;\n'
                        continue

                    idurl = contacts.getSupplierID(n)
                    name = nameurl.GetName(idurl)
                    if not name:
                        src += '&nbsp;\n'
                        continue
                    
        #---icon---
                    if idurl:
                        icon = 'icons/offline-user01.png'
                    else:
                        icon = 'icons/unknown-user01.png'
                    state = 'offline'
                    if contact_status.isOnline(idurl):
                        icon = 'icons/online-user01.png'
                        state = 'online '

#                    if w >= 5 and len(name) > 20:
#                        name = name[0:19] + '<br>' + name[19:]
                    src += '<a href="%s">' % link
                    src += '<img src="%s" width=%d height=%d>' % (
                        iconurl(request, icon),
                        imgW, imgH,)
                    src += '</a><br>\n'
                    # central_status = central_service._CentralStatusDict.get(idurl, '')
                    # central_status = central_service.get_user_status(idurl)
                    # central_status_color = _CentralStatusColors.get(central_status, 'gray')
                    central_status_color = 'gray'
                    #src += '<img src="%s" width=15 height=15>' % iconurl(request, central_status_icon)
                    src += '<a href="%s" target=_blank>@:</a>' % (idurl)
                    src += '<font color="%s">' % central_status_color
                    src += name
                    src += '</font>\n'

        #---show_ratings---
                    if self.show_ratings:
                        src += '<font size=1>\n'
                        src += '<table cellpadding=0 cellspacing=0 border=0>\n'
                        src += '<tr><td>%s%% - %s/%s</td></tr></table>\n' % (
                            ratings.month_percent(idurl),
                            ratings.month(idurl)['alive'],
                            ratings.month(idurl)['all'])

        #---show_contacts---
                    if bpio.Debug(8):
                        idobj = contacts.getSupplier(idurl)
                        idcontacts = []
                        idversion = ''
                        if idobj:
                            idcontacts = idobj.getContacts()
                            idversion = idobj.version.split(' ')[0]
                            try:
                                idversion += ' ' + idobj.version.split(' ')[2].split('-')[0]
                            except:
                                pass
                        if len(idcontacts) > 0:
                            src += '<table cellpadding=0 cellspacing=0 border=0>\n'
                            for c in idcontacts:
                                color = '404040'
                                # for proto in transport_control._PeersProtos.get(idurl, set()):
                                for proto in stats.peers_protos().get(idurl, set()):
                                    if c.startswith(proto+'://'):
                                        color = color[0:4]+'F0'
                                # for proto in transport_control._MyProtos.get(idurl, set()):
                                for proto in stats.my_protos().get(idurl, set()):
                                    if c.startswith(proto+'://'):
                                        color = color[0:2]+'F0'+color[4:6]
                                src += '<tr><td>'
                                src += '<font color="#%s" size=-4>' % color
                                src += c[0:26]
                                src += '</font>'
                                src += '</td></tr>\n'
                            try:
                                src += '<tr><td><font size=-4 color=gray>version: %s</font></td></tr>\n' % (idversion)
                            except:
                                pass
                            src += '</table>\n'

                    src += '</td>\n'

        #---html_comment---
                    month_str = '%d%% %s/%s' % (
                        ratings.month_percent(idurl),
                        ratings.month(idurl)['alive'],
                        ratings.month(idurl)['all'],)
                    total_str = '%d%% %s/%s' % (
                        ratings.total_percent(idurl),
                        ratings.total(idurl)['alive'],
                        ratings.total(idurl)['all'],)
                    src += html_comment('  %s [%s] %s %s %s' % (
                        str(n).rjust(5),
                        state, 
                        nameurl.GetName(idurl).ljust(20),
                        month_str.ljust(20),
                        total_str.ljust(20),))
                        
                src += '</tr>\n'

            src += '</table>\n'

            if bpio.Debug(8):
                idcontacts = misc.getLocalIdentity().getContacts()
                if len(idcontacts) > 0:
                    src += 'my contacts is:\n'
                    src += '<table cellpadding=0 cellspacing=0 border=0>\n'
                    for c in idcontacts:
                        proto,x,x = c.partition('://')
                        color = 'green' if proto in p2p_connector.active_protos() else 'gray'
                        src += '<tr><td>'
                        src += '<font color="%s" size=-4>' % color
                        src += c
                        src += '</font>'
                        src += '</td></tr>\n'
                    try:
                        idversion = misc.getLocalIdentity().version.split(' ')[0]
                        idversion += ' ' + misc.getLocalIdentity().version.split(' ')[2].split('-')[0]
                        src += '<tr><td><font size=-4 color=gray>my version: %s</font></td></tr>\n' % (idversion)
                    except:
                        pass
                    src += '</table>\n'

            src += '<br><br>'

        else:
            src += '<table width="80%"><tr><td>\n'
            src += '<p>List of your suppliers is empty.</p>\n'
            src += '<p>This may be due to the fact that the connection to the Central server is not established yet\n'
            src += 'or the Central server can not find the number of users that meet your requirements.</p>\n'
            src += '<p>Wait a bit or check your backups options in the settings.</p>\n'
            src += '<p>If you request too much needed space, you may not find the right number of suppliers.</p><br>\n'
            src += '</td></tr></table>\n'
            src += html_comment(
                'List of your suppliers is empty.\n'+
                'This may be due to the fact that the connection to the Central server is not finished yet\n'+
                'or the Central server can not find the number of users that meet your requirements.')

        #---links---
        if contacts.numSuppliers() > 0:
            src += '<p><a href="?action=call&back=%s">Call all suppliers to find out who is alive</a></p><br>\n' % back 
        src += '<p><a href="?action=request&back=%s">Request list of suppliers from Central server</a></p>\n' % (back)
        src += '<p><a href="%s?back=%s">Switch to Customers</a></p>\n' % ('/'+_PAGE_CUSTOMERS, back)
        if self.show_ratings:
            src += '<p><a href="%s?ratings=0&back=%s">Hide monthly ratings</a></p>\n' % (request.path, back)
        else:
            src += '<p><a href="%s?ratings=1&back=%s">Show monthly ratings</a></p>\n' % (request.path, back)
        return html(request, body=src, title='suppliers', back=back, reload='5',)

    def getChild(self, path, request):
        if path == '':
            return self
        return SupplierPage(path)

class CustomerPage(Page):
    pagename = _PAGE_CUSTOMER
    
    def __init__(self, path):
        Page.__init__(self)
        self.path = path
        try:
            self.index = int(self.path)
        except:
            self.index = -1
            self.idurl = ''
            self.name = ''
            return
        self.idurl = contacts.getCustomerID(self.index)
        protocol, host, port, self.name = nameurl.UrlParse(self.idurl)
        self.name = self.name.strip()[0:-4]

    def renderPage(self, request):
        back = arg(request, 'back', '/'+_PAGE_CUSTOMERS)

        if self.idurl == '':
            src = '<p>Wrong customer number.</p>\n'
            return html(request, body=src, back=back)

        action = arg(request, 'action')
        
        if action == 'remove':
            if contacts.IsCustomer(self.idurl):
                # central_service.SendReplaceCustomer(self.idurl)
                request.redirect('/'+_PAGE_CUSTOMERS)
                request.finish()
                return NOT_DONE_YET

        spaceDict = bpio._read_dict(settings.CustomersSpaceFile(), {})
        bytesGiven = int(float(spaceDict.get(self.idurl, 0)) * 1024 * 1024)
        dataDir = settings.getCustomersFilesDir()
        customerDir = os.path.join(dataDir, nameurl.UrlFilename(self.idurl))
        if os.path.isdir(customerDir):
            bytesUsed = bpio.getDirectorySize(customerDir)
        else:
            bytesUsed = 0
        try:
            percUsed = 100.0 * bytesUsed / bytesGiven
        except:
            percUsed = 0.0

        src = ''
        src += '<br><h1>%s</h1>\n' % nameurl.GetName(self.idurl)

        src += '<table>\n'
        src += '<tr><td>IDURL</td><td><a href="%s" target="_blank">%s</a></td></tr>\n' % (self.idurl, self.idurl)
        src += '<tr><td>takes</td><td>%s on your HDD</td></tr>\n' % diskspace.MakeStringFromBytes(bytesGiven)
        src += '<tr><td>he use</td><td>%s at the moment</td></tr>\n' % diskspace.MakeStringFromBytes(bytesUsed)
        src += '<tr><td>currently used</td><td>%3.2f%% of his taken space</td></tr>\n' % percUsed
        src += '<tr><td>current status is</td><td>'
        if contact_status.isOnline(self.idurl):
            src += '<font color="green">online</font>\n'
        else:
            src += '<font color="red">offline</font>\n'
        src += '</td></tr>\n'
        src += '<tr><td>month rating</td><td>%s%% - %s/%s</td></tr>\n' % ( ratings.month_percent(self.idurl), ratings.month(self.idurl)['alive'], ratings.month(self.idurl)['all'])
        src += '</table>\n'
        src += '<br><br>\n'
        src += '<p><a href="%s?action=remove&back=%s">Dismis customer <b>%s</b> and throw out His/Her Files from my HDD</a></p>\n' % (
            request.path, back, self.name)
        src += '<p><a href="%s/files?back=%s">Show me <b>%s\'s</b> Files</a></p>\n' % (
            request.path, back, self.name)
        return html(request, body=src, title=self.name, back=back)

    def getChild(self, path, request):
        if path == 'files':
            return CustomerFilesPage(self.idurl)
        return self 

class CustomerFilesPage(Page):
    pagename = _PAGE_CUSTOMER_FILES

    def __init__(self, idurl):
        Page.__init__(self)
        self.idurl = idurl
        self.customerNum = contacts.numberForCustomer(self.idurl)
        self.name = nameurl.GetName(self.idurl)
        
    def renderPage(self, request):
        back = arg(request,'back','/'+_PAGE_CUSTOMERS+'/'+str(self.customerNum))
        title = '%s\'s files' % self.name
        src = '<h1>%s</h1>\n' % title
        list_files = []
        customer_dir = settings.getCustomerFilesDir(self.idurl)
        if os.path.isdir(customer_dir):
            for filename in os.listdir(customer_dir):
                list_files.append(filename)
        if len(list_files) > 0:
            src += '<table width=70%><tr><td align=center>\n'
            src += '<div><code>\n'
            for filename in list_files:
                src += filename + '<br>\n' 
            src += '</code></div>\n</td></tr></table>\n'
        else:
            src += '<p>no files found</p>\n' 
        return html(request, body=src, back=back, title=title)
    
class CustomersPage(Page):
    pagename = _PAGE_CUSTOMERS
    def __init__(self):
        Page.__init__(self)
        self.show_ratings = False

    def renderPage(self, request):
        back = arg(request, 'back', '/'+_PAGE_MENU)
        #---show_ratings---
        if arg(request, 'ratings') == '1':
            self.show_ratings = True
        elif arg(request, 'ratings') == '0':
            self.show_ratings = False
        
        action = arg(request, 'action')

        #---action call---
        if action == 'call':
            # transport_control.ClearAliveTimeCustomers()
            # contact_status.check_contacts(contacts.getCustomerIDs())
            propagate.SlowSendCustomers(0.2)
            # request.redirect(request.path)
            # request.finish()
            # return NOT_DONE_YET

        #---action request---
        elif action == 'request':
            pass
            # central_service.clear_users_statuses(contacts.getCustomerIDs())
            # central_service.SendRequestCustomers()

        #---action remove---
        elif action == 'remove':
            idurl = arg(request, 'idurl')
            if idurl != '':
                if not idurl.startswith('http://'):
                    try:
                        idurl = contacts.getCustomerID(int(idurl))
                    except:
                        idurl = 'http://'+settings.IdentityServerName()+'/'+idurl+'.xml'
                # if contacts.IsCustomer(idurl):
                #     central_service.SendReplaceCustomer(idurl)

        #---draw page---
        src = ''
        src += '<p>me is <a href="%s" target=_blank>@:</a>%s</p>\n' % (misc.getLocalID(), misc.getIDName())
        src += '<h1>my customers</h1>\n'

        if contacts.numCustomers() > 0:
            w, h = misc.calculate_best_dimension(contacts.numCustomers())
            imgW = 64
            imgH = 64
            if w > 4:
                imgW = 4 * imgW / w
                imgH = 4 * imgH / w
            padding = 64/w - 8
            src += html_comment('  index status    user                 month rating         total rating' ) 
            src += '<table cellpadding=%d cellspacing=2>\n' % padding
            for y in range(h):
                src += '<tr valign=top>\n'
                for x in range(w):
                    src += '<td align=center valign=top>\n'
                    n = y * w + x
                    link = _PAGE_CUSTOMERS+'/'+str(n)+'?back='+back
                    if n >= contacts.numCustomers():
                        src += '&nbsp;\n'
                        continue

                    idurl = contacts.getCustomerID(n)
                    name = nameurl.GetName(idurl)
                    if not name:
                        src += '&nbsp;\n'
                        continue

        #---icon---
                    icon = 'icons/offline-user01.png'
                    state = 'offline'
                    if contact_status.isOnline(idurl):
                        icon = 'icons/online-user01.png'
                        state = 'online '

                    # if w >= 5 and len(name) > 10:
                    #     name = name[0:9] + '<br>' + name[9:]
                    src += '<a href="%s">' % link
                    src += '<img src="%s" width=%d height=%d>' % (
                        iconurl(request, icon),
                        imgW, imgH,)
                    src += '</a><br>\n'
                    # central_status = central_service.get_user_status(idurl)
                    # central_status_color = _CentralStatusColors.get(central_status, 'gray')
                    central_status_color = 'gray'
                    src += '<a href="%s" target=_blank>@:</a>' % (idurl)
                    src += '<font color="%s">' % central_status_color
                    src += '%s' % name
                    src += '</font>\n'

        #---show_ratings---
                    if self.show_ratings:
                        src += '<font size=1>\n'
                        src += '<table cellpadding=0 cellspacing=0 border=0>\n'
                        src += '<tr><td>%s%% - %s/%s</td></tr></table>\n' % (
                            ratings.month_percent(idurl),
                            ratings.month(idurl)['alive'],
                            ratings.month(idurl)['all'])

        #---show_contacts---
                    if bpio.Debug(8):
                        idobj = contacts.getCustomer(idurl)
                        idcontacts = []
                        idversion = ''
                        if idobj:
                            idcontacts = idobj.getContacts()
                            idversion = idobj.version.split(' ')[0]
                            try:
                                idversion += ' ' + idobj.version.split(' ')[2].split('-')[0]
                            except:
                                pass
                        if len(idcontacts) > 0:
                            src += '<table cellpadding=0 cellspacing=0 border=0>\n'
                            for c in idcontacts:
                                color = '404040'
                                # for proto in transport_control._PeersProtos.get(idurl, set()):
                                for proto in stats.peers_protos().get(idurl, set()):
                                    if c.startswith(proto+'://'):
                                        color = color[0:4]+'F0'
                                for proto in stats.my_protos().get(idurl, set()):
                                # for proto in transport_control._MyProtos.get(idurl, set()):
                                    if c.startswith(proto+'://'):
                                        color = color[0:2]+'F0'+color[4:6]
                                src += '<tr><td>'
                                src += '<font color="#%s" size=-4>' % color
                                src += c[0:26]
                                src += '</font>'
                                src += '</td></tr>\n'
                            try:
                                src += '<tr><td><font size=-4 color=gray>version: %s</font></td></tr>\n' % (idversion)
                            except:
                                pass
                            src += '</table>\n'

                    src += '</td>\n'
                    
        #---html_comment---
                    month_str = '%d%% %s/%s' % (
                        ratings.month_percent(idurl),
                        ratings.month(idurl)['alive'],
                        ratings.month(idurl)['all'],)
                    total_str = '%d%% %s/%s' % (
                        ratings.total_percent(idurl),
                        ratings.total(idurl)['alive'],
                        ratings.total(idurl)['all'],)
                    src += html_comment('  %s [%s] %s %s %s' % (
                        str(n).rjust(5),
                        state, 
                        nameurl.GetName(idurl).ljust(20),
                        month_str.ljust(20),
                        total_str.ljust(20),))

                src += '</tr>\n'
            src += '</table>\n'
            src += '<br><br>'

        else:
            src += '<p>List of your customers is empty.<br></p>\n'
            src += html_comment('List of your customers is empty.\n')

        #---links---
        if contacts.numCustomers() > 0:
            src += '<p><a href="?action=call&back=%s">Call all customers to find out who is alive</a></p><br>\n' % back
        src += '<p><a href="?action=request&back=%s">Request list of my customers from Central server</a></p>\n' % (back)
        src += '<p><a href="%s?back=%s">Switch to Suppliers</a></p>\n' % ('/'+_PAGE_SUPPLIERS, back)
        if self.show_ratings:
            src += '<p><a href="%s?ratings=0&back=%s">Hide monthly ratings</a></p>\n' % (request.path, back)
        else:
            src += '<p><a href="%s?ratings=1&back=%s">Show monthly ratings</a></p>\n' % (request.path, back)
        return html(request, body=src, title='customers', back=back, reload='5',)

    def getChild(self, path, request):
        if path == '': 
            return self
        return CustomerPage(path)


class StoragePage(Page):
    pagename = _PAGE_STORAGE
    def renderPage(self, request):
        bytesNeeded = diskspace.GetBytesFromString(settings.getMegabytesNeeded(), 0)
        bytesDonated = diskspace.GetBytesFromString(settings.getMegabytesDonated(), 0)
        usedDict = bpio._read_dict(settings.CustomersUsedSpaceFile(), {})
        bytesUsed = 0
        for customer_bytes_used in usedDict:
            try:
                bytesUsed += int(customer_bytes_used)
            except:
                bpio.exception() 
        # backup_fs.sizebackups() # backup_db.GetTotalBackupsSize() * 2
        suppliers_count = contacts.numSuppliers()
        if suppliers_count > 0: 
            bytesNeededPerSupplier = bytesNeeded / suppliers_count 
            bytesUsedPerSupplier = bytesUsed / suppliers_count
        else:
            bytesNeededPerSupplier = bytesUsedPerSupplier = 0
        dataDir = settings.getCustomersFilesDir()
        dataDriveFreeSpace, dataDriveTotalSpace = diskusage.GetDriveSpace(dataDir)
        if dataDriveFreeSpace is None:
            dataDriveFreeSpace = 0
        customers_count = contacts.numCustomers()
        spaceDict = bpio._read_dict(settings.CustomersSpaceFile(), {})
        totalCustomersMB = 0.0
        try:
            freeDonatedMB = float(spaceDict.get('free', bytesDonated/(1024*1024)))
        except:
            bpio.exception()
            freeDonatedMB = 0.0
        if freeDonatedMB < 0:
            freeDonatedMB = 0.0
        try:
            for idurl in contacts.getCustomerIDs():
                totalCustomersMB += float(spaceDict.get(idurl, '0.0'))
        except:
            bpio.exception()
            totalCustomersMB = 0.0
        if totalCustomersMB < 0:
            totalCustomersMB = 0.0
        currentlyUsedDonatedBytes = bpio.getDirectorySize(dataDir)
        StringNeeded = diskspace.MakeStringFromBytes(bytesNeeded)
        StringDonated = diskspace.MakeStringFromBytes(bytesDonated)
        StringUsed = diskspace.MakeStringFromBytes(bytesUsed)
        StringNeededPerSupplier = diskspace.MakeStringFromBytes(bytesNeededPerSupplier)
        StringUsedPerSupplier = diskspace.MakeStringFromBytes(bytesUsedPerSupplier)
        StringDiskFreeSpace = diskspace.MakeStringFromBytes(dataDriveFreeSpace)
        StringTotalCustomers = diskspace.MakeStringFromBytes(totalCustomersMB*1024.0*1024.0)
        StringFreeDonated = diskspace.MakeStringFromBytes(freeDonatedMB*1024.0*1024.0)
        StringUsedDonated = diskspace.MakeStringFromBytes(currentlyUsedDonatedBytes)
        try:
            PercNeed = 100.0 * bytesUsed / bytesNeeded
        except:
            PercNeed = 0.0
        try:
            PercAllocated = (100.0*totalCustomersMB/(totalCustomersMB+freeDonatedMB))
        except:
            PercAllocated = 0.0
        try:
            PercDonated = (100.0*currentlyUsedDonatedBytes/bytesDonated)
        except:
            PercDonated = 0.0
        src = ''
        src += '<h1>storage</h1>\n'
        src += '<table><tr>\n'
        src += '<td valign=top align=center>\n'
        src += '<h3>needed</h3>\n'
        src += '<img src="%s?width=300&height=300" /><br>\n' % (iconurl(request, _PAGE_STORAGE+'/needed'))
        src += '<table>\n'
        src += '<tr><td><table border=1 cellspacing=0 cellpadding=0><tr>\n'
        src += '<td bgcolor="#82f282">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td nowrap>needed</td>\n'
        src += '<td><table border=1 cellspacing=0 cellpadding=0><tr>'
        src += '<td bgcolor="#22b222">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td nowrap>used</td></tr>\n'
        src += '</table>\n'
        src += '<table>\n'
        src += html_comment('needed space:')
        src += '<tr><td nowrap>number of <a href="%s">suppliers</a>:</td><td nowrap><b>%d</b></td></tr>\n' % ('/'+_PAGE_SUPPLIERS, suppliers_count)
        src += html_comment('  number of suppliers: %d' % suppliers_count)
        src += '<tr><td nowrap>space given to you:</td><td nowrap><b>%s</b></td></tr>\n' % StringNeeded 
        src += html_comment('  space given to you: %s' % StringNeeded)
        src += '<tr><td nowrap>space used at the moment:</td><td nowrap><b>%s</b></td></tr>\n' % StringUsed
        src += html_comment('  space used at the moment: %s' % StringUsed) 
        src += '<tr><td nowrap>percentage used:</td><td nowrap><b>%3.2f%%</b></td></tr>\n' % PercNeed
        src += html_comment('  percentage used: %3.2f%%' % PercNeed)
        src += '<tr><td nowrap>each supplier gives you:</td><td nowrap><b>%s</b></td></tr>\n' % StringNeededPerSupplier 
        src += html_comment('  each supplier gives you: %s' % StringNeededPerSupplier)
        src += '<tr><td nowrap>space used per supplier:</td><td nowrap><b>%s</b></td></tr>\n' % StringUsedPerSupplier
        src += html_comment('  space used per supplier: %s' % StringUsedPerSupplier)   
        src += '</table>\n'
        src += '</td>\n'
        src += '<td valign=top align=center>\n'
        src += '<h3 align=center>donated</h3>\n'
        src += '<img src="%s?width=300&height=300" /><br>\n' % (iconurl(request, _PAGE_STORAGE+'/donated'))
        src += '<table>\n'
        src += '<tr><td><table border=1 cellspacing=0 cellpadding=0><tr>\n'
        src += '<td bgcolor="#e2e242">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td nowrap>donated</td>\n'
        src += '<td><table border=1 cellspacing=0 cellpadding=0><tr>'
        src += '<td bgcolor="#a2a202">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td nowrap>used</td>\n'
        src += '<td align=center><table border=1 cellspacing=0 cellpadding=0><tr>\n'
        src += '<td bgcolor="#ffffff">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr></table></td>\n'
        src += '<td nowrap>free</td><td>&nbsp;</td></tr>\n'
        src += '</table>\n'
        src += '<table>\n'
        src += html_comment('donated space:')
        src += '<tr><td nowrap>number of <a href="%s">customers</a>:</td><td nowrap><b>%d</b></td></tr>\n' % ('/'+_PAGE_CUSTOMERS, customers_count)
        src += html_comment('  number of customers: %d' % customers_count)
        if bytesDonated > dataDriveFreeSpace:
            src += '<tr><td nowrap>your donated space:</td><td nowrap><b><font color="red">%s</font></b></td></tr>\n' % StringDonated
        else:
            src += '<tr><td nowrap>your donated space:</td><td nowrap><b>%s</b></td></tr>\n' % StringDonated
        src += html_comment('  your donated space: %s' % StringDonated) 
        src += '<tr><td nowrap>free space on the disk:</td><td nowrap><b>%s</b></td></tr>\n' % StringDiskFreeSpace 
        src += html_comment('  free space on the disk: %s' % StringDiskFreeSpace)
        src += '<tr><td nowrap>space taken by customers:</td><td nowrap><b>%s</b></td></tr>\n' % StringTotalCustomers
        src += html_comment('  space taken by customers: %s' % StringTotalCustomers) 
        src += '<tr><td nowrap>free donated space:</td><td nowrap><b>%s</b></td></tr>\n' % StringFreeDonated 
        src += html_comment('  free donated space: %s' % StringFreeDonated) 
        src += '<tr><td nowrap>percentage allocated:</td><td nowrap><b>%3.2f%%</b></td></tr>\n' % PercAllocated 
        src += html_comment('  percentage allocated: %3.2f%%' % PercAllocated) 
        src += '<tr><td nowrap>space used by customers:</td><td nowrap><b>%s</b></td></tr>\n' % StringUsedDonated   
        src += html_comment('  space used by customers: %s' % StringUsedDonated) 
        src += '<tr><td nowrap>percentage used:</td><td nowrap><b>%3.2f%%</b></td></tr>\n' % PercDonated 
        src += html_comment('  percentage used: %3.2f%%' % PercDonated) 
        src += '</table>\n'
        src += '</td>\n'
        src += '</tr></table>\n'
        return html(request, body=src, title='storage',)

    def getChild(self, path, request):
        if path == 'needed':
            return StorageNeededImage() 
        elif path == 'donated':
            return StorageDonatedImage()
        return self
        

class StorageNeededImage(resource.Resource):
    pagename = _PAGE_STORAGE_NEEDED
    # isLeaf = True

    def toInt(self, f):
        return int(round(f))
    
    def render_GET(self, request):
        request.responseHeaders.setRawHeaders("content-type", ['image/png'])
        try:
            import Image
            import ImageDraw
            import ImageFont 
        except:
            bpio.exception()
            # 1x1 png picture 
            src = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAAXNSR0IArs4c6QAAAARnQU1BAACx\njwv8YQUAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAABp0RVh0\nU29mdHdhcmUAUGFpbnQuTkVUIHYzLjUuMTAw9HKhAAAADElEQVQYV2P4//8/AAX+Av6nNYGEAAAA\nAElFTkSuQmCC\n'
            bin = misc.AsciiToBinary(src)
            request.write(bin)
            request.finish()
            return NOT_DONE_YET
        width = misc.ToInt(arg(request, 'width'), 256)
        height = misc.ToInt(arg(request, 'height'), 256)
        img = Image.new("RGB", (width, height), "#fff")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(settings.FontImageFile(), 12)
        except:
            font = None
        f = cStringIO.StringIO()
        bytesNeeded = diskspace.GetBytesFromString(settings.getMegabytesNeeded(), None)
        if bytesNeeded is None:
            img.save(f, "PNG")
            f.seek(0)
            request.write(f.read())
            request.finish()
            return NOT_DONE_YET
        bytesUsed = backup_fs.sizebackups() # backup_db.GetTotalBackupsSize() * 2
        w = backup_matrix.suppliers_set().supplierCount
        if w == 0:
            img.save(f, "PNG")
            f.seek(0)
            request.write(f.read())
            request.finish()
            return NOT_DONE_YET
        x0 = (width - 2) / 2.0
        y0 = (height - 2) / 2.0
        R = float(min(width, height)) / 2.0 - 1
        dR = ( R / float(bytesNeeded) ) * float(bytesUsed) 
        dA = 360.0 / float(w)
        for y in range(w): # needed
            start = float(y) * dA
            end = start + dA
            draw.pieslice((self.toInt(x0 - R), self.toInt(y0 - R),
                           self.toInt(x0 + R), self.toInt(y0 + R)), 
                           self.toInt(start), self.toInt(end), fill='#82f282', outline='#777777')
        for y in range(w): # used
            start = float(y) * dA
            end = start + dA
            draw.pieslice((self.toInt(x0 - dR), self.toInt(y0 - dR), 
                           self.toInt(x0 + dR), self.toInt(y0 + dR)),
                           self.toInt(start), self.toInt(end), fill='#22b222', outline='#777777')
        if width >= 256 and height >= 256:
            for supplierNum in range(w):
                a = float(supplierNum) * dA + dA / 2.0 
                x1 = math.cos(a * math.pi / 180.0) * R * 0.7 + x0
                y1 = math.sin(a * math.pi / 180.0) * R * 0.7 + y0
                s = nameurl.GetName(contacts.getSupplierID(supplierNum))
                sw, sh = draw.textsize(s, font=font)
                draw.text((self.toInt(x1-sw/2.0), self.toInt(y1-sh/2.0)), s, fill="#000000", font=font)
        img.save(f, "PNG")
        f.seek(0)
        request.write(f.read())
        request.finish()
        return NOT_DONE_YET
    
    
class StorageDonatedImage(resource.Resource):
    pagename = _PAGE_STORAGE_NEEDED
    # isLeaf = True

    def toInt(self, f):
        return int(round(f))
    
    def render_GET(self, request):
        request.responseHeaders.setRawHeaders("content-type", ['image/png'])
        try:
            import Image
            import ImageDraw
            import ImageFont 
        except:
            bpio.exception()
            # 1x1 png picture 
            src = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAAXNSR0IArs4c6QAAAARnQU1BAACx\njwv8YQUAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAABp0RVh0\nU29mdHdhcmUAUGFpbnQuTkVUIHYzLjUuMTAw9HKhAAAADElEQVQYV2P4//8/AAX+Av6nNYGEAAAA\nAElFTkSuQmCC\n'
            bin = misc.AsciiToBinary(src)
            request.write(bin)
            request.finish()
            return NOT_DONE_YET
        width = misc.ToInt(arg(request, 'width'), 256)
        height = misc.ToInt(arg(request, 'height'), 256)
        img = Image.new("RGB", (width, height), "#fff")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(settings.FontImageFile(), 12)
        except:
            font = None
        f = cStringIO.StringIO()
        dataDir = settings.getCustomersFilesDir()
        dataDriveFreeSpace, dataDriveTotalSpace = diskusage.GetDriveSpace(dataDir)
        if dataDriveFreeSpace is None:
            dataDriveFreeSpace = 0
        customers_ids = list(contacts.getCustomerIDs())
        customers_count = contacts.numCustomers()
        spaceDict = bpio._read_dict(settings.CustomersSpaceFile(), {})
        usedSpaceDict = {}
        totalCustomersBytes = 0
        bytesDonated = diskspace.GetBytesFromString(settings.getMegabytesDonated(), 0)
        try:
            freeDonatedBytes = int(float(spaceDict['free'])*1024.0*1024.0)
        except:
            freeDonatedBytes = bytesDonated
            spaceDict['free'] = freeDonatedBytes/(1024.0*1024.0)
        if freeDonatedBytes < 0:
            freeDonatedBytes = 0
        for idurl in customers_ids:
            try:
                totalCustomersBytes += int(float(spaceDict.get(idurl, 0.0))*1024.0*1024.0)
            except:
                bpio.exception()
            customerDir = os.path.join(dataDir, nameurl.UrlFilename(idurl))
            if os.path.isdir(customerDir):
                sz = bpio.getDirectorySize(customerDir)
            else:
                sz = 0
            usedSpaceDict[idurl] = sz
        x0 = (width - 2) / 2.0
        y0 = (height - 2) / 2.0
        R = float(min(width, height)) / 2.0 - 1
        A = 0.0
        # idurls = spaceDict.keys()
        # idurls.append('free')
        try:
            if customers_count == 0:
                colorGiven = '#ffffff'
                draw.ellipse((self.toInt(x0 - R), self.toInt(y0 - R),
                              self.toInt(x0 + R), self.toInt(y0 + R)), 
                              fill=colorGiven, outline='#777777')
            else:
                for idurl in customers_ids + ['free',]:
                    usedBytes = usedSpaceDict.get(idurl, 0)
                    givenBytes = int(float(spaceDict[idurl])*1024*1024)
                    dA = 360.0 * givenBytes / ( totalCustomersBytes + freeDonatedBytes )
#                    if dA < 1.0:
#                        A += dA
#                        continue
                    try:
                        dR = R * float(usedBytes) / float(givenBytes)
                    except:
                        dR = 0 
                    start = A
                    end = start + dA
                    colorGiven = '#ffffff' if idurl == 'free' else '#e2e242'
                    colorUsed = '#a2a202'
                    draw.pieslice((self.toInt(x0 - R), self.toInt(y0 - R),
                                   self.toInt(x0 + R), self.toInt(y0 + R)), 
                                   self.toInt(start), self.toInt(end), fill=colorGiven, outline='#777777')
                    draw.pieslice((self.toInt(x0 - dR), self.toInt(y0 - dR), 
                                   self.toInt(x0 + dR), self.toInt(y0 + dR)),
                                   self.toInt(start), self.toInt(end), fill=colorUsed, outline='#777777')
                    A += dA
            A = 0.0
            if width >= 256 and height >= 256:
                if customers_count == 0:
                    s = 'free ' + diskspace.MakeStringFromBytes(freeDonatedBytes)
                    sw, sh = draw.textsize(s, font=font)
                    draw.text((self.toInt(x0-sw/2.0), self.toInt(y0-sh/2.0)), s, fill="#000000", font=font)
                else:
                    for idurl in customers_ids:
                        usedBytes = usedSpaceDict.get(idurl, 0)
                        givenBytes = int(float(spaceDict[idurl])*1024*1024)
                        dA = 360.0 * givenBytes / bytesDonated
                        if dA < 15.0:
                            A += dA
                            continue
                        a = A + dA / 2.0 
                        x1 = math.cos(a * math.pi / 180.0) * R * 0.7 + x0
                        y1 = math.sin(a * math.pi / 180.0) * R * 0.7 + y0
                        if idurl == 'free':
                            s = 'free ' + diskspace.MakeStringFromBytes(givenBytes)
                            sw, sh = draw.textsize(s, font=font)
                            draw.text((self.toInt(x1-sw/2.0), self.toInt(y1-sh/2.0)), s, fill="#000000", font=font)
                        else:
                            s1 = nameurl.GetName(idurl) 
                            s2 = '%s/%s' % (diskspace.MakeStringFromBytes(usedBytes),
                                            diskspace.MakeStringFromBytes(givenBytes))
                            sw1, sh1 = draw.textsize(s1, font=font)
                            sw2, sh2 = draw.textsize(s2, font=font)
                            draw.text((self.toInt(x1-sw1/2.0), self.toInt(y1-sh1)), s1, fill="#000000", font=font)
                            draw.text((self.toInt(x1-sw2/2.0), self.toInt(y1)), s2, fill="#000000", font=font)
                        A += dA
        except:
            bpio.exception()
            img.save(f, "PNG")
            f.seek(0)
            request.write(f.read())
            request.finish()
            return NOT_DONE_YET
        img.save(f, "PNG")
        f.seek(0)
        request.write(f.read())
        request.finish()
        return NOT_DONE_YET

    
class ConfigPage(Page):
    pagename = _PAGE_CONFIG
    def renderPage(self, request):
        global _SettingsItems
        menuLabels = _SettingsItems.keys()
        menuLabels.sort()
        w, h = misc.calculate_best_dimension(len(menuLabels))
        imgW = 128
        imgH = 128
        if w >= 4:
            imgW = 4 * imgW / w
            imgH = 4 * imgH / w
        padding = 64/w - 8
        src = '<h1>settings</h1>\n'
        src += '<table width="90%%" cellpadding=%d cellspacing=2>\n' % padding
        for y in range(h):
            src += '<tr valign=top>\n'
            for x in range(w):
                n = y * w + x
                src += '<td align=center valign=top>\n'
                if n >= len(menuLabels):
                    src += '&nbsp;\n'
                    continue
                label = menuLabels[n]
                link_url, icon_url = _SettingsItems[label]
                if link_url.find('?') < 0:
                    link_url += '?back='+request.path
                label = label.split('|')[1]
                src += '<a href="%s">' % link_url
                src += '<img src="%s" width=%d height=%d>' % (
                    iconurl(request, icon_url),
                    imgW, imgH,)
                src += '<br>[%s]' % label
                src += '</a>\n'
                src += '</td>\n'
                # src += html_comment('  [%s] %s' % (label, link_url))
            src += '</tr>\n'
        src += '</table>\n'
        return html(request, body=str(src), title='settings', back='/'+_PAGE_MENU, )


class BackupSettingsPage(Page):
    pagename = _PAGE_BACKUP_SETTINGS
    def renderPage(self, request):
        # bpio.log(14, 'webcontrol.BackupSettingsPage.renderPage')
        donatedStr = diskspace.MakeStringFromString(settings.getMegabytesDonated())
        neededStr = diskspace.MakeStringFromString(settings.getMegabytesNeeded())

        src = '<h1>backup settings</h1>\n'
        src += '<br><h3>needed space: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'central-settings.needed-megabytes',
            request.path,
            neededStr)
#        src += '<p>This will cost %s$ per day.</p>\n' % 'XX.XX'

        src += '<br><h3>donated space: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'central-settings.donated-megabytes',
            request.path,
            donatedStr)
#        src += '<p>This will earn up to %s$ per day, depending on space used.</p>\n' % 'XX.XX'

        numSuppliers = settings.getDesiredSuppliersNumber()
        src += '<br><h3>number of suppliers: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'central-settings.desired-suppliers',
            request.path, str(numSuppliers))

        blockSize = settings.getBackupBlockSize()
        src += '<br><h3>preferred block size: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'backup.backup-block-size',
            request.path, str(blockSize))

        blockSizeMax = settings.getBackupMaxBlockSize()
        src += '<br><h3>maximum block size: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'backup.backup-max-block-size',
            request.path, str(blockSizeMax))

        backupCount = settings.getGeneralBackupsToKeep()
        if backupCount == '0':
            backupCount = 'unlimited'
        src += '<br><h3>backup copies: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'general.general-backups',
            request.path, backupCount)
        
        keepLocalFiles = settings.getGeneralLocalBackups()
        src += '<br><h3>local backups: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'general.general-local-backups-enable', request.path,
            'yes' if keepLocalFiles else 'no')
        if not keepLocalFiles:
            src += '<br><h3>remove the local data, but wait 24 hours,<br>to check suppliers: <a href="%s?back=%s">%s</a></h3>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'general.general-wait-suppliers-enable', request.path,
                'yes' if settings.getGeneralWaitSuppliers() else 'no')

        src += '<br><h3>directory for donated space:</h3>\n'
        src += '<a href="%s?back=%s">%s</a></p>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'folder.folder-customers',
            request.path, settings.getCustomersFilesDir())

        src += '<br><br><h3>directory for local backups:</h3>\n'
        src += '<a href="%s?back=%s">%s</a></p>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'folder.folder-backups',
            request.path, settings.getLocalBackupsDir())
        
        src += '<br><br><h3>directory for restored files:</h3>\n'
        src += '<a href="%s?back=%s">%s</a></p>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'folder.folder-restore',
            request.path, settings.getRestoreDir())

        src += '<br><br>\n'

        back = arg(request, 'back', '/'+_PAGE_BACKUP_SETTINGS)
        return html(request, body=src, title='backup settings', back=back)


class SecurityPage(Page):
    pagename = _PAGE_SECURITY
    def renderPage(self, request):
        messageA = ''
        messageB = ''
        comment = ''
        action = arg(request, 'action')
        back = arg(request, 'back', '/'+_PAGE_CONFIG)

        if action == 'copy':
            TextToSave = misc.getLocalID() + "\n" + crypto.MyPrivateKey()
            misc.setClipboardText(TextToSave)
            messageA = '<font color="green">Now you can "paste" with Ctr+V your Private Key where you want.</font>'
            comment = 'now you can "paste" with Ctr+V your private key where you want.'
            del TextToSave

        elif action == 'view':
            TextToSave = misc.getLocalID() + "\n" + crypto.MyPrivateKey()
            TextToSave = TextToSave.replace('\n', '<br>\n').replace(' ', '&nbsp;')
            src = '<h1>private key</h1>\n'
            src += '<table align=center><tr><td align=center>\n'
            src += '<div align=left><code>\n'
            src += TextToSave
            src += '</code></div>\n'
            src += '</td></tr></table>\n'
            src += html_comment('\n'+TextToSave+'\n')
            del TextToSave
            return html(request, body=src, back=back, title='private key')

        elif action == 'write':
            TextToSave = misc.getLocalID() + "\n" + crypto.MyPrivateKey()
            savefile = unicode(misc.unpack_url_param(arg(request, 'savefile'), ''))
            bpio.AtomicWriteFile(savefile, TextToSave)
            messageA = '<font color="green">Your Private Key were copied to the file %s</font>' % savefile
            comment = 'your private key were copied to the file %s' % savefile
            del TextToSave
            
        elif action == 'move':
            TextToSave = crypto.MyPrivateKey()
            savefile = unicode(misc.unpack_url_param(arg(request, 'savefile'), ''))
            if bpio.AtomicWriteFile(savefile, TextToSave):
                keyfilename = settings.KeyFileName()
                if bpio.AtomicWriteFile(keyfilename+'_location', savefile):
                    try:
                        os.remove(keyfilename)
                    except:
                        bpio.exception()
                        messageB = '<font color="red">Failed to remove your Private Key from %s</font>' % keyfilename
                        comment = 'failed to remove your Private Key from %s' % keyfilename
                    messageB = '<font color="green">Your Private Key were moved to %s,<br>be sure to have the file in same place during next program start</font>' % savefile
                    comment = 'your private key were moved to %s,\nbe sure to have the file in same place during next program start' % savefile
                else:
                    messageB = '<font color="red">Failed to write to the file %s</font>' % (keyfilename+'_location')
                    comment = 'failed to write to the file %s' % (keyfilename+'_location')
            else:
                messageB = '<font color="red">Failed to write your Private Key to the file %s</font>' % savefile
                comment = 'failed to write your Private Key to the file %s' % savefile
            del TextToSave
            
        elif action == 'openmyid':
            webbrowser.open(misc.getLocalID(), new=1, autoraise=1)

        src = '<h1>public and private key</h1>\n'
        src += '<table width="80%"><tr><td>\n'
        
        src += '<p><b>Saving the key to your backups</b> someplace other than this machine <b>is vitally important!</b></p>\n'
        src += '<p>If this machine is lost due to a broken disk, theft, fire, flood, earthquake, tornado, hurricane, etc. you must have a copy of your key someplace else to recover your data.</p>\n'
        src += '<p>We recommend at least 3 copies in different locations. For example one in your safe deposit box at the bank, one in your fireproof safe, and one at work.'
        src += 'You only need to do this at the beginning, then the keys can stay put till you need one.<\p>\n'
        src += '<p><b>Without a copy of your key nobody can recover your data!</b><br>Not even BitPie.NET ...</p>\n'
        src += '<p>You can do the following with your Private Key:</p>\n'

        src += '<table><tr>\n'
        
        src += '<td>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<input type="submit" name="submit" value=" view the whole key " />\n'
        src += '<input type="hidden" name="action" value="view" />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % request.path
        src += '</form>\n'
        src += '</td>\n'
        
        src += '<td>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<input type="submit" name="submit" value=" copy to clipboard " />\n'
        src += '<input type="hidden" name="action" value="copy" />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % back
        src += '</form>\n'
        src += '</td>\n'

        src += '<td>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<input type="hidden" name="action" value="write" />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % back
        src += '<input type="hidden" name="parent" value="%s" />\n' % _PAGE_SECURITY
        src += '<input type="hidden" name="label" value="Select filename to save" />\n'
        src += '<input type="hidden" name="showincluded" value="true" />\n'
        src += '<input type="submit" name="savefile" value=" write to file " path="%s" />\n' % (
            misc.pack_url_param(os.path.join(os.path.expanduser('~'), '%s-BitPie.NET.key' % misc.getIDName())))
        src += '</form>\n'
        src += '</td>\n'

        src += '</tr></table>\n'

        src += '<br>' + messageA

        src += '<p>You can create <b>a completely inaccessible for anybody but you</b>, keeping your data, if after creating a distributed remote backup - delete the original data from your computer. '
        src += 'Private key can be stored on a USB flash drive and <b>local copy of the Key can be removed from your HDD</b>.</p>\n'
        src += '<p>Than, BitPie.NET will only run with this USB stick and read the Private Key at startup, it will only be stored in RAM. '
        src += 'After starting the program, disconnect the USB stick, and hide it in a safe place.</p>\n'
        src += '<p>If control of the computer was lost - just <b>be sure that the power is turned off</b>, it is easy to provide. '
        src += 'In this case the memory is reset and working key will be erased, so that copy of your Key will remain only on USB flash drive, hidden by you.</p>\n'
        src += '<p>This way, <b>only you will have access to the data</b> after a loss of the computer, where BitPie.NET were launched.</p>\n'
        
        src += '<table><tr>\n'
        src += '<td>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<input type="hidden" name="action" value="move" />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % back
        src += '<input type="hidden" name="parent" value="%s" />\n' % _PAGE_SECURITY
        src += '<input type="hidden" name="label" value="Select filename to save" />\n'
        src += '<input type="hidden" name="showincluded" value="true" />\n'
        removable_drives = bpio.listRemovableDrives()
        if len(removable_drives) > 0:
            start_path = os.path.join(removable_drives[0], misc.getIDName()+'-BitPie.NET.key')
        else:
            start_path = ''
        src += '<input type="submit" name="savefile" value=" move my key to removable media " path="%s" />\n' % start_path 
        src += '</form>\n'
        src += '</td>\n'
        src += '</tr></table>\n'

        src += '<br>' + messageB
        
        src += '<br><p>The public part of your key is stored in the <b>Identity File</b>.' 
        src += 'This is a publicly accessible file wich keeps information needed to connect to you.\n'
        src += 'Identity file has a <b>unique address on the Internet</b>,' 
        src += 'so that every user may download it and find out your contact information.</p>\n'
        src += '<p>Your Identity is <b>digitally signed</b> and that would change it is '
        src += 'necessary to know the Private Key.</p>\n'
        # src += '<br><br>\n'
        src += '<table><tr>\n'
        src += '<td>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<input type="hidden" name="action" value="openmyid" />\n'
        src += '<input type="submit" value=" open my public identity file " />\n' 
        src += '</form>\n'
        # src += '<a href="%s" target="_blank">open my public identity file</a>\n' % misc.getLocalID()
        src += '<br>\n'
        src += '</td>\n'
        src += '</tr></table>\n'
        
        src += '</td></tr></table>\n'
        
        src += html_comment(comment)

        return html(request, body=src, title='security', back=back)


class NetworkSettingsPage(Page):
    pagename = _PAGE_NETWORK_SETTINGS
    def renderPage(self, request):
        src = '<h1>network settings</h1>\n'
        src += '<table width=1 cellspacing=30><tr>\n'
        src += '<td width=50% valign=top nowrap><h3>TCP transport</h3>\n'
        src += '<p>enable: <a href="%s?back=%s">%s</a></p>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'transport.transport-tcp.transport-tcp-enable', request.path,
            'yes' if settings.enableTCP() else 'no')
        if settings.enableTCP():
            src += '<p>use for sending: <a href="%s?back=%s">%s</a></p>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'transport.transport-tcp.transport-tcp-sending-enable', request.path,
                'yes' if settings.enableTCPsending() else 'no')
            src += '<br><p>use for receiving: <a href="%s?back=%s">%s</a></p>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'transport.transport-tcp.transport-tcp-receiving-enable', request.path,
                'yes' if settings.enableTCPreceiving() else 'no')
            src += '<br><p>listen on port: <a href="%s?back=%s">%s</a></p>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'transport.transport-tcp.transport-tcp-port', request.path,
                settings.getTCPPort())
            src += '<br><p>enable UPnP: <a href="%s?back=%s">%s</a></p>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'other.upnp-enabled', request.path,
                'yes' if settings.enableUPNP() else 'no')
        src += '</td>\n'
#        src += '<td width=50% valign=top nowrap><h3>UDP transport</h3>\n'
#        src += '<p>enable transport_udp: <a href="%s?back=%s">%s</a></p>\n' % (
#            '/'+_PAGE_SETTINGS+'/'+'transport.transport-udp.transport-udp-enable', request.path,
#            'yes' if settings.enableUDP() else 'no')
#        if settings.enableUDP():
#            src += '<p>use for sending: <a href="%s?back=%s">%s</a></p>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'transport.transport-udp.transport-udp-sending-enable', request.path,
#                'yes' if settings.enableUDPsending() else 'no')
#            src += '<br><p>use for receiving: <a href="%s?back=%s">%s</a></p>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'transport.transport-udp.transport-udp-receiving-enable', request.path,
#                'yes' if settings.enableUDPreceiving() else 'no')
#            src += '<p>transport_udp port: <a href="%s?back=%s">%s</a></h3>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'transport.transport-udp.transport-udp-port', request.path,
#                settings.getUDPPort())
#        src += '</td>\n'
#        src += '</tr>\n<tr>\n'
#        src += '<td width=50% valign=top nowrap><h3>CSpace transport</h3>\n'
#        src += '<p>enable transport_cspace: <a href="%s?back=%s">%s</a></p>\n' % (
#            '/'+_PAGE_SETTINGS+'/'+'transport.transport-cspace.transport-cspace-enable', request.path,
#            'yes' if settings.enableCSpace() else 'no')
#        if settings.enableCSpace():
#            src += '<p>use for sending: <a href="%s?back=%s">%s</a></p>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'transport.transport-cspace.transport-cspace-sending-enable', request.path,
#                'yes' if settings.enableCSPACEsending() else 'no')
#            src += '<br><p>use for receiving: <a href="%s?back=%s">%s</a></p>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'transport.transport-cspace.transport-cspace-receiving-enable', request.path,
#                'yes' if settings.enableCSPACEreceiving() else 'no')
#        src += '</td>\n'
        src += '<td width=50% valign=top nowrap><h3>DHTUDP transport</h3>\n'
        src += '<p>enable transport: <a href="%s?back=%s">%s</a></p>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'transport.transport-dhtudp.transport-dhtudp-enable', request.path,
            'yes' if settings.enableDHTUDP() else 'no')
        if settings.enableDHTUDP():
            src += '<p>use for sending: <a href="%s?back=%s">%s</a></p>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'transport.transport-dhtudp.transport-dhtudp-sending-enable', request.path,
                'yes' if settings.enableDHTUDPsending() else 'no')
            src += '<br><p>use for receiving: <a href="%s?back=%s">%s</a></p>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'transport.transport-dhtudp.transport-dhtudp-receiving-enable', request.path,
                'yes' if settings.enableDHTUDPreceiving() else 'no')
            src += '<p>UDP port for data transport: <a href="%s?back=%s">%s</a></h3>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'transport.transport-dhtudp.transport-dhtudp-port', request.path,
                settings.getDHTUDPPort())
            src += '<p>UDP port for DHT network: <a href="%s?back=%s">%s</a></h3>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'transport.transport-dhtudp.transport-dht-port', request.path,
                settings.getDHTPort())
        src += '</td>\n'
        src += '</tr></table>\n'
        # src += '<br><p><a href="http://bitpie.net/network.html" target=_blank>Read info about network protocol transports</a></p>\n'
        
#        src += '<br><h3>outgoing bandwidth limit: <a href="%s?back=%s">%s</a></h3>\n' % (
#            '/'+_PAGE_SETTINGS+'/'+'network.network-send-limit', request.path,
#            str(settings.getBandOutLimit()))
#        src += '<br><h3>incoming bandwidth limit: <a href="%s?back=%s">%s</a></h3>\n' % (
#            '/'+_PAGE_SETTINGS+'/'+'network.network-receive-limit', request.path,
#            str(settings.getBandInLimit()))
        return html(request, body=src,  back=arg(request, 'back', '/'+_PAGE_CONFIG), title='network settings')


#class UpdatePage(Page):
#    pagename = _PAGE_UPDATE
#    debug = False
#    def _check_callback(self, x, request):
#        global local_version
#        global revision_number
#        local_version = bpio.ReadBinaryFile(settings.VersionFile())
#        src = '<h1>update software</h1>\n'
#        src += '<p>your software revision number is <b>%s</b></p>\n' % revision_number
#        src += self._body_windows_frozen(request)
#        back = '/'+_PAGE_CONFIG
#        request.write(html_from_args(request, body=str(src), title='update software', back=back))
#        request.finish()
#
#    def _body_windows_frozen(self, request, repo_msg=None):
#        global local_version
#        global global_version
#        try:
#            repo, update_url = bpio.ReadTextFile(settings.RepoFile()).split('\n')
#        except:
#            repo = settings.DefaultRepo()
#            update_url = settings.UpdateLocationURL()
#        if repo == '':
#            repo = 'test' 
#        button = None
#        if global_version == '':
#            button = (' check latest version ', True, 'check')
#        else:
#            if local_version == '':
#                button = (' update BitPie.NET now ', True, 'update')
#            else:
#                if local_version != global_version:
#                    button = (' update BitPie.NET now ', True, 'update')
#                else:
#                    button = (' BitPie.NET updated! ', False, 'check')
#        src = ''
#        src += '<h3>Update repository</h3>\n'
#        src += '<form action="%s" method="post">\n' % request.path
#        src += '<table align=center>\n'
#        src += '<tr><td align=left>\n'
#        src += '<input id="test" type="radio" name="repo" value="testing" %s />\n' % ('checked' if repo=='test' else '')
#        src += '</td></tr>\n'
#        src += '<tr><td align=left>\n'
#        src += '<input id="devel" type="radio" name="repo" value="development" %s />\n' % ('checked' if repo=='devel' else '') 
#        src += '</td></tr>\n'
#        src += '<tr><td align=left>\n'
#        src += '<input id="stable" type="radio" name="repo" value="stable" %s />\n' % ('checked' if repo=='stable' else '')
#        src += '</td></tr>\n'
#        src += '<tr><td align=center>\n'
#        if repo_msg is not None:
#            src += '<p><font color=%s>%s</font></p>\n' % (repo_msg[1], repo_msg[0])
#        src += '<input type="hidden" name="action" value="repo" />\n'
#        src += '<br><input type="submit" name="submit" value=" set "/>\n'
#        src += '</td></tr>\n'
#        src += '</table>\n'
#        src += '</form>\n'
#        src += '<h3>Update schedule</h3>\n'
#        shed = schedule.Schedule(from_dict=bpupdate.read_shedule_dict())
#        next = shed.next_time()
#        src += '<p>'
#        if next is None:
#            src += 'icorrect schedule<br>\n'
#        elif next < 0:
#            src += 'not scheduled<br>\n'
#        else:
#            src += shed.html_description() + ',<br>\n'
#            src += shed.html_next_start() + ',<br>\n'
#        src += '<a href="%s?back=%s">change schedule</a>\n' % ('/'+_PAGE_UPDATE_SHEDULE, request.path)
#        src += '</p>\n' 
#        if button is not None:
#            src += '<br><br><form action="%s" method="post">\n' % request.path
#            src += '<table align=center>\n'
#            src += '<tr><td>\n'
#            src += '<input type="hidden" name="action" value="%s" />\n' % button[2]
#            src += '<input type="submit" name="submit" value="%s" %s />\n' % (button[0], ('disabled' if not button[1] else '')) 
#            src += '</td></tr>\n'
#            src += '</table>\n'
#            src += '</form>\n'
#        src += '<br>\n'
#        return src 
#        
#    def _body_windows_soures(self, request):
#        src = '<p>Running from python sources.</p>\n'
#        return src
#
#    def _body_linux_deb(self, request):
#        src = ''
#        src += '<table align=center><tr><td><div align=left>\n'
#        src += '<p>You can manually update BitPie.NET<br>\n'
#        src += 'from command line using apt-get:</p>\n'
#        src += '<code><br>\n'
#        src += 'sudo apt-get update<br>\n'
#        src += 'sudo apt-get install bitpie-stable\n'
#        src += '</code></div></td></tr></table>\n'
#        return src
#           
#    def _body_linux_sources(self, request):
#        src = '<p>Running from python sources.</p>\n'
#        return src
#    
#    def renderPage(self, request):
#        global local_version
#        global global_version
#        global revision_number
#        action = arg(request, 'action')
#        repo_msg = None
#        update_msg = None
#
#        if action == 'update':
#            if self.debug or (bpio.Windows() and bpio.isFrozen()):
#                if not bpupdate.is_running():
#                    bpupdate.run()
#                    update_msg = 'preparing update process ...'
#
#        elif action == 'check':
#            if self.debug or (bpio.Windows() and bpio.isFrozen()):
#                d = bpupdate.check()
#                d.addCallback(self._check_callback, request)
#                d.addErrback(self._check_callback, request)
#                request.notifyFinish().addErrback(self._check_callback, request)
#                return NOT_DONE_YET
#            
#        elif action == 'repo':
#            repo = arg(request, 'repo')
#            repo = {'development': 'devel', 'testing': 'test', 'stable': 'stable'}.get(repo, 'test')
#            repo_file_src = '%s\n%s' % (repo, settings.UpdateLocationURL(repo))
#            bpio.WriteFile(settings.RepoFile(), repo_file_src)
#            global_version = ''
#            repo_msg = ('repository changed', 'green')
#            
#        src = '<h1>update software</h1>\n'
#        src += '<p>Current revision number is <b>%s</b></p>\n' % revision_number
#        if update_msg is not None:
#            src += '<h3><font color=green>%s</font></h3>\n' % update_msg
#            back = '/'+_PAGE_CONFIG
#            return html(request, body=src, title='update software', back=back)
#        
#        if bpio.Windows():
#            if bpio.isFrozen():
#                src += self._body_windows_frozen(request, repo_msg)
#            else:
#                if self.debug:
#                    src += self._body_windows_frozen(request, repo_msg)
#                else:
#                    src += self._body_windows_soures(request)
#        else:
#            if bpio.getExecutableDir().count('/usr/share/bitpie'):
#                src += self._body_linux_deb(request)
#            else:
#                src += self._body_linux_sources(request)
#                
#        back = '/'+_PAGE_CONFIG
#        return html(request, body=src, title='update software', back=back)


class DevelopmentPage(Page):
    pagename = _PAGE_DEVELOPMENT
    def renderPage(self, request):
        src = '<h1>for developers</h1>\n'
        src += '<br><h3>debug level: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'logs.debug-level', request.path,
            settings.getDebugLevelStr())
        src += '<br><h3>use http server for logs: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'logs.stream-enable', request.path,
            'yes' if settings.enableWebStream() else 'no')
        src += '<br><h3>http server port number: <a href="%s?back=%s">%s</a></h3>\n' % (
            '/'+_PAGE_SETTINGS+'/'+'logs.stream-port', request.path,
            str(settings.getWebStreamPort()))
        if settings.enableWebStream():
            src += '<p>You can browse logs by clicking on icon "Logs" in top right of the main window, '
            src += 'or <a href="http://127.0.0.1:%d" target="_blank">here</a>.<br>\n' % settings.getWebStreamPort()
            src += 'It is needed to restart BitPie.NET to be able to see the logs.</p>\n'
        # src += '<br><br><h3>To see current packets transfers go to the <a href="%s">Packet Transfers page</a>.</h3>\n' % ('/'+_PAGE_MONITOR_TRANSPORTS)
        src += '<p>You can watch current memory usage on the <a href="%s">Memory page</a>.</p>\n' % ('/'+_PAGE_MEMORY)
        src += '<h3>If you want to give a feedback or you found a bug or other cause,<br>you can <a href="%s?back=%s">send a developer report</a> now.</h3>' % (
            '/'+_PAGE_DEV_REPORT, request.path)
        src += '<br><br>\n'
        return html(request, body=src, back=arg(request, 'back', '/'+_PAGE_CONFIG), title='developers')


#class MoneyPage(Page):
#    pagename = _PAGE_MONEY
#    
#    def renderPage(self, request):
#        action = arg(request, 'action')
#        bal, balnt, rcptnum = money.LoadBalance()
#        bitcoins = bitcoin.balance()
#        back = arg(request, 'back', '/'+_PAGE_MENU)
#        if action == 'update':
#            bitcoin.update(OnBitCoinUpdateBalance)
#        src = '<h1>money</h1>\n'
#        src += '<table align=center>'
#        src += '<tr><td align=right>total balance:</td>\n'
#        src += '<td align=left><b>%s BP</b></td></tr>\n' % misc.float2str(bal + balnt) # (<b>%d</b> days remaining)
#        src += '<tr><td align=right>transferable balance:</td>\n'
#        src += '<td align=left><b>%s BP</b></td></tr>\n' % misc.float2str(bal)
#        src += '<tr><td align=right>not transferable balance:</td>\n'
#        src += '<td align=left><b>%s BP</b></td></tr>\n' % misc.float2str(balnt)
#        src += '<tr><td align=right><a href="/%s?back=%s">BitCoins</a> balance:</td>\n' % (_PAGE_BIT_COIN_SETTINGS, request.path) 
#        src += '<td align=left><b>%s</b>\n' % misc.float2str(bitcoins)
#        if bitcoin.installed():
#            src += '&nbsp;&nbsp; <a href="%s?action=update&back=%s">[update]</a>\n' % (request.path, back)
#        src += '</td></tr>\n'        
#        src += '</table>\n'
#        src += html_comment('total balance: %s BP' % misc.float2str(bal + balnt))
#        src += html_comment('transferable balance: %s BP' % misc.float2str(bal))
#        src += html_comment('not transferable balance: %s BP' % misc.float2str(balnt))
#        src += html_comment('bitcoins: %s BTC' % str(bitcoins))
#        src += '<br>\n'
#        src += '<br><br><a href="%s">I want to <b>BUY</b> BitPie.NET credits <b>for $ US</b> with my <b>CreditCard</b></a>\n' % _PAGE_MONEY_ADD
#        src += '<br><br><a href="%s"><b>BUY/SELL</b> BP credits <b>for BitCoins</b> on the BitPie.NET Market Place</a>\n' % _PAGE_MONEY_MARKET_LIST
#        src += '<br><br><a href="%s">Let\'s <b>SEND</b> some of my <b>earned</b> BP credits to one of my friends</a>\n' % _PAGE_TRANSFER
#        src += '<br><br><a href="%s">Show me the full receipts <b>HISTORY</b></a>\n' % _PAGE_RECEIPTS
#        return html(request, body=src, back=arg(request, 'back', '/'+_PAGE_MENU), title='money')


#class MoneyAddPage(Page):
#    pagename = _PAGE_MONEY_ADD
#    def renderPage(self, request):
#        action = arg(request, 'action')
#        back = arg(request, 'back', '/'+_PAGE_MONEY)
#        src = '<h1>add BitPie.NET credits</h1>\n'
#        
#        if action == 'pay':
#            url = 'http://%s:%s?id=%s' % (
#                settings.MoneyServerName(), str(settings.MoneyServerPort()),
#                misc.encode64(misc.getLocalID()))
#            webbrowser.open(url, new=1, autoraise=1)
#            request.redirect('/'+_PAGE_MONEY)
#            request.finish()
#            return NOT_DONE_YET
#            
#        src += '<table width=55%><tr><td>\n'
#        src += '<p align=justify>At the moment, that would increase your balance you can use credit card: Visa or MasterCard.</p>\n'
#        src += '<p align=justify>The money will be transferred without commission.</p>\n'
#        src += '<p align=justify>In the opened browser window, fill in your credit card info and payment will be accomplished immediately,\n'
#        src += 'check receipts history to monitor money transfer.</p>\n'
#        src += '</td></tr></table>\n'
#        src += '<br><br><br>\n'
#        src += '<form action="%s" method="post">\n' % request.path
#        src += '<input type="hidden" name="action" value="pay" />\n'
#        src += '<input type="hidden" name="back" value="%s" />\n' % back
#        src += '<input type="submit" name="submit" value=" buy BitPie.NET credits ON-LINE with your Credit Card " />\n'
#        src += '</form>\n'
#        return html(request, body=src, back=back, title='buy credits for $ US')


#class MoneyMarketBuyPage(Page):
#    pagename = _PAGE_MONEY_MARKET_BUY
#    def _checkInput(self, maxamount, price, days, comment, btcaddress):
#        if '' in [maxamount.strip(), price.strip(), days.strip(), btcaddress]:
#            return 'enter required info, please'
#        try:
#            float(maxamount)
#            float(price)
#            float(days)
#        except:
#            return 'enter number, please'
#        if not misc.ValidateBitCoinAddress(btcaddress):
#            return 'BitCoin address is not valid'
#        if len(comment) > 256:
#            return 'your comment is too long'
#        return ''
#    
#    def renderPage(self, request):
#        bal, balnt, rcptnum = money.LoadBalance()
#        bitcoins = bitcoin.balance()
#        action = arg(request, 'action')
#        back = arg(request, 'back', '/'+_PAGE_MONEY)
#        message = ''
#        maxamount = arg(request, 'maxamount', '10.0')
#        price = arg(request, 'price', str(settings.DefaultBitCoinCostPerBitPie.NETCredit())) 
#        days = arg(request, 'days', '365')
#        comment = misc.MakeValidHTMLComment(arg(request, 'comment'))
#        btcaddress = arg(request, 'btcaddress')
#        
#        if action == 'bid':
#            message = self._checkInput(maxamount, price, days, comment, btcaddress)
#            if not message:
#                amount = float(maxamount) * float(price)
#                src = '<br>' * 3
#                src += '<table width=70%><tr><td align=center>\n'
#                src += '<h1>Please, confirm your bid</h1>\n'
#                src += '<font size=+1><p align=center>Buy <b>%s BitPie.NET</b> for <b>%s BTC</b> each, <br><br>\n' % (misc.float2str(maxamount), misc.float2str(price)) 
#                src += 'a total of <b>%s BTC</b> will be deducted from your BitCoin account. <br><br>\n' % misc.float2str(amount)
#                src += 'This bid will be available for <b>%s</b> days' % days
#                if comment.strip():
#                    src += ' and published with comment:</p></font>\n'
#                    src += '<br><br><font color=gray>%s</font>\n' % comment
#                else:
#                    src += '.</p></font>\n'
#                src += '</td></tr></table>\n'
#                src += '<br><br><br>\n'
#                src += '<table><tr>\n'
#                src += '<td>\n'
#                src += '<form action="%s" method="post">\n' % request.path
#                src += '<input type="hidden" name="action" value="acceptbid" />\n'
#                src += '<input type="hidden" name="maxamount" value="%s" />\n' % maxamount
#                src += '<input type="hidden" name="price" value="%s" />\n' % price
#                src += '<input type="hidden" name="days" value="%s" />\n' % days 
#                src += '<input type="hidden" name="comment" value="%s" />\n' % comment
#                src += '<input type="hidden" name="btcaddress" value="%s" />\n' % btcaddress
#                src += '<input type="hidden" name="back" value="%s" />\n' % back
#                src += '<input type="submit" name="submit" value=" confirm " />\n'
#                src += '</form>\n'
#                src += '</td>\n<td>\n'
#                src += '<form action="%s" method="post">\n' % request.path
#                src += '<input type="hidden" name="action" value="" />\n'
#                src += '<input type="hidden" name="maxamount" value="%s" />\n' % maxamount
#                src += '<input type="hidden" name="price" value="%s" />\n' % price
#                src += '<input type="hidden" name="days" value="%s" />\n' % days 
#                src += '<input type="hidden" name="comment" value="%s" />\n' % comment
#                src += '<input type="hidden" name="btcaddress" value="%s" />\n' % btcaddress
#                src += '<input type="hidden" name="back" value="%s" />\n' % back
#                src += '<input type="submit" name="submit" value=" cancel " />\n'
#                src += '</form>\n'
#                src += '</td>\n'
#                src += '</tr></table>\n'
#                return html(request, body=src, back=back, title='buy credits for BitCoins') 
#            
#        elif action == 'acceptbid':
#            message = self._checkInput(maxamount, price, days, comment, btcaddress)
#            if not message:
#                try:
#                    amount = float(maxamount) * float(price)
#                    ret = bitcoin.connection().sendtoaddress( 
#                                   settings.MarketServerBitCoinAddress(), 
#                                   float( float(maxamount) * float(price) ),
#                                   'BitPie.NET bid from ' + misc.getLocalID())
#                    message = ''
#                except Exception, e:
#                    message = str(e)
#                if not message:
#                    # central_service.SendBid(maxamount, price, days, comment, btcaddress, ret)
#                    src = '<br><br><br>\n'
#                    src += '<tabler width=50%><tr><td>\n'
#                    src += '<h1>your successfully made a bid</h1>\n'
#                    src += '<font color=green><p><b>%s BTC</b> were sent to the Market Server</p></font>\n' % misc.float2str(amount)
#                    src += '<p>Transaction ID is <a href="https://blockchain.info/tx/%s" target=_blank>%s</a></p>\n' % (str(ret), str(ret))
#                    src += '<p>Your bid will be published as soon as we receive your BitCoins in our account.<br>\n'
#                    src += 'When will be found suitable offer - <b>%s BitPie.NET</b> will be credited to your account.<br>\n' % misc.float2str(maxamount)
#                    src += 'After <b>%s</b> days there will be no suitable offer - <b>%s BTC</b> will be transferred back to this address:' % (days, misc.float2str(amount))
#                    src += '<br><font color=green>%s</font></p>\n' % btcaddress
#                    src += '<p>You can view offers and bids from all users on the BitPie.NET <a href="%s" target=_blank>Market Place</a>.</p>\n' % settings.MarketPlaceURL()
#                    src += '<br><br><a href="%s">Go to a list of my current bids and offers</a>\n' % ('/'+_PAGE_MONEY_MARKET_LIST) 
#                    src += '</td></tr></table>\n'
#                    return html(request, body=src, back=back, title='buy BitPie.NET credits for BitCoins')
#                    
#        # elif action == 'update':
#        #     bitcoin.update(OnBitCoinUpdateBalance)
#                
#        src = ''
#        src += '<h3>place a bid to buy credits for BitCoins</h3>\n'
#        src += '<table align=center><tr><td align=left>\n'
#        src += 'Transferable balance: <b>%s BitPie.NET</b>\n' % misc.float2str(bal)
#        src += '<br><br>BitCoins: <b>%s</b> \n' % str(bitcoins)
#        # src += '&nbsp;&nbsp;&nbsp; <a href="%s?action=update&back=%s">[update]</a>\n' % (request.path, request.path)
#        # src += '&nbsp;&nbsp;&nbsp; <a href="/%s?back=%s">[BitCoin settings]</a></p>\n' % (_PAGE_BIT_COIN_SETTINGS, request.path)
#        src += '</td></tr></table>\n'
#        src += html_comment('transferable balance: %s BitPie.NET' % misc.float2str(bal))
#        src += html_comment('bitcoins: %s BTC' % str(bitcoins))
#        src += '<br>\n'
#        src += '<form action="%s" method="post">\n' % request.path
#        src += '<input type="hidden" name="action" value="bid" />\n'
#        src += '<table><tr><td align=left>\n'
#        src += '<table><tr><td align=left colspan=2>buy:</td></tr>\n'
#        src += '<tr><td><input type="text" name="maxamount" value="%s" size=12 /></td>\n' % maxamount
#        src += '<td align=left>BitPie.NET credits</td></tr></table>\n'
#        src += '<table><tr><td align=left colspan=2>price is:</td></tr>\n'
#        src += '<tr><td><input type="text" name="price" value="%s" size=12 /></td>\n' % price
#        src += '<td align=left>BTC per 1 BitPie.NET </td></tr></table>\n'
#        src += '<table><tr><td align=left colspan=2>duration:</td></tr>\n'
#        src += '<tr><td><input type="text" name="days" value="%s" size=4 /></td>\n' % days 
#        src += '<td align=left>days</td></tr></table>\n'
#        src += '<table><tr><td align=left>return BitCoin address:</td></tr>\n'
#        src += '<tr><td><input type="text" name="btcaddress" value="%s" size=38></td></tr>\n' % btcaddress
#        src += '<tr><td align=right nowrap><font color=gray size=-1>to receive funds if your bid is cancelled or expired</font></td></tr></table>\n'
#        src += '<table><tr><td align=left>short comment:</td></tr>\n'
#        src += '<tr><td><input type="text" name="comment" value="%s" size=40></td></tr>\n' % comment
#        src += '<tr><td align=right nowrap><font color=gray size=-1>up to 256 chars long</font></td></tr></table>\n'
#        src += '</td></tr></table>\n'
#        if message:
#            src += '<br><br>' + html_message(message, 'error') + '\n'
#        src += '<input type="hidden" name="back" value="%s" />\n' % back
#        src += '<br><br><br><input type="submit" name="submit" value=" make a bid " />\n'
#        src += '</form>\n'
#        return html(request, body=src, back=back, title='buy credits for BitCoins')
        

#class MoneyMarketSellPage(Page):
#    pagename = _PAGE_MONEY_MARKET_SELL
#    def _checkInput(self, maxamount, minamount, price, days, comment, btaddress):
#        if '' in [maxamount.strip(), minamount.strip(), price.strip(), days.strip(), btaddress.strip()]:
#            return 'enter required info, please'
#        try:
#            float(maxamount)
#            float(minamount)
#            float(price)
#            float(days)
#        except:
#            return 'enter number, please'
#        if float(maxamount) <= float(minamount):
#            return 'incorrect minimum and maximum amount values'
#        if float(minamount) < 1.0:
#            return 'minimum amount is 1 BitPie.NET'
#        if len(comment) > 256:
#            return 'your comment is too long'
#        if not misc.ValidateBitCoinAddress(btaddress):
#            return 'BitCoin address is not valid'
#        bal, balnt, rcptnum = money.LoadBalance()
#        if float(bal) <= float(maxamount):
#            return 'you have insufficient funds in your BitPie.NET account'
#        return ''
#
#    def renderPage(self, request):
#        bal, balnt, rcptnum = money.LoadBalance()
#        bitcoins = bitcoin.balance()
#        action = arg(request, 'action')
#        back = arg(request, 'back', '/'+_PAGE_MONEY)
#        message = ''
#        maxamount = arg(request, 'maxamount', '10.0')
#        minamount = arg(request, 'minamount', '1.0')
#        price = arg(request, 'price', str(settings.DefaultBitCoinCostPerBitPie.NETCredit())) 
#        days = arg(request, 'days', '365')
#        comment = misc.MakeValidHTMLComment(arg(request, 'comment'))
#        btcaddress = arg(request, 'btcaddress')
#        
#        if action == 'offer':
#            message = self._checkInput(maxamount, minamount, price, days, comment, btcaddress)
#            if not message:
#                amount = float(maxamount) * float(price)
#                src = '<br>' * 3
#                src += '<table width=70%><tr><td align=center>\n'
#                src += '<h1>Please, confirm your offer</h1>\n'
#                src += '<font size=+1><p align=center>Sell up to <b>%s BitPie.NET</b> for <b>%s BTC</b> each, <br><br>\n' % (misc.float2str(maxamount), misc.float2str(price)) 
#                src += 'a total of <b>%s BitPie.NET</b> will be deducted from your BitPie.NET account. <br><br>\n' % misc.float2str(maxamount)
#                src += 'Your purchased BitCoins will be transferred to this address:<br>\n'
#                src += '<font color=green>%s</font><br><br>\n' % btcaddress
#                src += 'The minimum amount of the deal is <b>%s BitPie.NET</b> credits.\n' % minamount
#                src += 'If there is a bid on the Market that satisfies only part of your offer, the remainder of the loans will be transferred back to your BitPie.NET account.<br><br>\n'
#                src += 'This offer will be available for <b>%s</b> days' % days
#                if comment.strip():
#                    src += ' and published with comment:</p></font>\n'
#                    src += '<br><br><font color=gray>%s</font>\n' % comment
#                else:
#                    src += '.</p></font>\n'
#                src += '</td></tr></table>\n'
#                src += '<br><br><br>\n'
#                src += '<table><tr>\n'
#                src += '<td>\n'
#                src += '<form action="%s" method="post">\n' % request.path
#                src += '<input type="hidden" name="action" value="acceptoffer" />\n'
#                src += '<input type="hidden" name="maxamount" value="%s" />\n' % maxamount
#                src += '<input type="hidden" name="minamount" value="%s" />\n' % minamount
#                src += '<input type="hidden" name="price" value="%s" />\n' % price
#                src += '<input type="hidden" name="days" value="%s" />\n' % days 
#                src += '<input type="hidden" name="comment" value="%s" />\n' % comment
#                src += '<input type="hidden" name="btcaddress" value="%s" />\n' % btcaddress
#                src += '<input type="hidden" name="back" value="%s" />\n' % back
#                src += '<input type="submit" name="submit" value=" confirm " />\n'
#                src += '</form>\n'
#                src += '</td>\n<td>\n'
#                src += '<form action="%s" method="post">\n' % request.path
#                src += '<input type="hidden" name="action" value="" />\n'
#                src += '<input type="hidden" name="maxamount" value="%s" />\n' % maxamount
#                src += '<input type="hidden" name="minamount" value="%s" />\n' % minamount
#                src += '<input type="hidden" name="price" value="%s" />\n' % price
#                src += '<input type="hidden" name="days" value="%s" />\n' % days 
#                src += '<input type="hidden" name="comment" value="%s" />\n' % comment
#                src += '<input type="hidden" name="btcaddress" value="%s" />\n' % btcaddress
#                src += '<input type="hidden" name="back" value="%s" />\n' % back
#                src += '<input type="submit" name="submit" value=" cancel " />\n'
#                src += '</form>\n'
#                src += '</td>\n'
#                src += '</tr></table>\n'
#                return html(request, body=src, back=back, title='sell BitPie.NET credits for BitCoins') 
#
#        elif action == 'acceptoffer':
#            message = self._checkInput(maxamount, minamount, price, days, comment, btcaddress)
#            if not message:
#                amount = float(maxamount) * float(price)
#                # central_service.SendOffer(maxamount, minamount, price, days, comment, btcaddress)
#                src = '<br><br><br>\n'
#                src += '<tabler width=50%><tr><td>\n'
#                src += '<h1>your successfully made an offer</h1>\n'
#                src += '<font color=green><p><b>%s BitPie.NET</b> were transferred to the Market Server</p></font>\n' % misc.float2str(maxamount)
#                src += '<p>Your offer should be published immediately.<br>\n'
#                src += 'When will be found a suitable bid your purchased BTC will be credited to this BitCoin address:<br>\n'
#                src += '<font color=green>%s</font><br><br>\n' % btcaddress
#                src += 'After <b>%s</b> days there will be no suitable offer - <b>%s BitPie.NET</b> will be transferred back to your account.</p>\n' % (days, misc.float2str(maxamount))
#                src += '<p>You can view offers and bids from all users on the BitPie.NET <a href="%s" target=_blank>Market Place</a>.</p>\n' % settings.MarketPlaceURL()
#                src += '<br><br><a href="%s">Go to a list of my current bids and offers</a>\n' % ('/'+_PAGE_MONEY_MARKET_LIST) 
#                src += '</td></tr></table>\n'
#                return html(request, body=src, back=back, title='buy BitPie.NET credits for BitCoins')
#                                
#        # elif action == 'update':
#        #     bitcoin.update(OnBitCoinUpdateBalance)
#        
#        src = '<h3>place offer to sell credits for BitCoins</h3>\n'
#        src += '<table align=center><tr><td align=left>\n'
#        src += 'Transferable balance: <b>%s BitPie.NET</b>\n' % misc.float2str(bal)
#        src += '<br><br>BitCoins: <b>%s</b>\n' % bitcoins
#        # src += '&nbsp;&nbsp;&nbsp; <a href="%s?action=update&back=%s">[update]</a>\n' % (request.path, request.path)
#        # src += '&nbsp;&nbsp;&nbsp; <a href="/%s?back=%s">[BitCoin settings]</a></p>\n' % (_PAGE_BIT_COIN_SETTINGS, request.path)
#        src += '</td></tr></table>\n'
#        src += html_comment('transferable balance: %s BitPie.NET' % misc.float2str(bal))
#        src += html_comment('bitcoins: %s' % bitcoins)
#        src += '<br>\n'
#        src += '<form action="%s" method="post">\n' % request.path
#        src += '<input type="hidden" name="action" value="offer" />\n'
#        src += '<table><tr><td align=left>\n'
#        src += '<table><tr><td align=left colspan=2>sell up to:</td></tr>\n'
#        src += '<tr><td><input type="text" name="maxamount" value="%s" size=12 /></td>\n' % maxamount
#        src += '<td align=left>BitPie.NET credits</td></tr></table>\n'
#        src += '</td><td align=left>\n'
#        src += '<table><tr><td align=left colspan=2>but not less than:</td></tr>\n'
#        src += '<tr><td><input type="text" name="minamount" value="%s" size=12 /></td>\n' % minamount
#        src += '<td align=left>BitPie.NET credits</td></tr></table>\n'
#        src += '</td></tr><tr><td align=left>\n'
#        src += '<table><tr><td align=left colspan=2>price is:</td></tr>\n'
#        src += '<tr><td><input type="text" name="price" value="%s" size=12 /></td>\n' % price
#        src += '<td align=left nowrap>BTC per 1 BitPie.NET </td></tr></table>\n'
#        src += '</td><td align=left>\n'
#        src += '<table><tr><td align=left colspan=2>duration:</td></tr>\n'
#        src += '<tr><td><input type="text" name="days" value="%s" size=4 /></td>\n' % days 
#        src += '<td align=left>days</td></tr></table>\n'
#        src += '</td></tr><tr><td align=left colspan=2>\n'
#        src += '<table><tr><td align=left colspan=2 nowrap>BitCoin address to receive the payment:</td></tr>\n'
#        src += '<tr><td><input type="text" name="btcaddress" value="%s" size=38></td>\n' % btcaddress
#        src += '<td align=left nowrap>&nbsp;</td></tr></table>\n'
#        src += '</td></tr><tr><td align=left colspan=2>\n'
#        src += '<table><tr><td align=left>comment:</td></tr>\n'
#        src += '<tr><td><input type="text" name="comment" value="%s" size=60></td></tr>\n' % comment
#        src += '<tr><td align=right nowrap><font color=gray size=-1>up to 256 chars long</font></td></tr></table>\n'
#        src += '</td></tr></table>\n'
#        if message:
#            src += '<br><br>' + html_message(message, 'error') + '\n'
#        src += '<input type="hidden" name="back" value="%s" />\n' % back
#        src += '<br><br><input type="submit" name="submit" value=" place offer " />\n'
#        src += '</form>\n'
#        return html(request, body=src, back=back, title='sell credits for BitCoins')


#class MoneyMarketListPage(Page):
#    pagename = _PAGE_MONEY_MARKET_LIST
#    def renderPage(self, request):
#        action = arg(request, 'action')
#        back = arg(request, 'back', '/'+_PAGE_MONEY)
#
#        if action == 'request':
#            pass
#            # central_service.SendRequestMarketList()
#            
#        elif action == 'canceloffer':
#            pass
#            # central_service.SendCancelOffer(arg(request, 'offerid'))
#            
#        elif action == 'cancelbid':
#            pass
#            # central_service.SendCancelBid(arg(request, 'bidid'))
#        
#        src = ''
#        src += '<h3>BitCoin Market</h3>\n'
#        src += '<p>Here you can watch your bids and offers currently placed on the Market.<p>\n'
#        src += '<table width=90%>\n'
#        # if central_service._MarketOffers is None and central_service._MarketBids is None:
#        if True:
#            src += '<tr>\n'
#            src += '<td align=center colspan=2>\n'
#            src += '<br><br><br><font color=gray size=-1>no responses yet from the Market Server</font><br>\n'
#            src += '</td>\n'
#            src += '</tr>\n'
#        src += '<tr>\n'
#        src += '<td align=center valign=top width=50%>\n'
#        if True:
#        # if central_service._MarketBids is not None:
#            # if len(central_service._MarketBids) == 0:
#            if True:
#                src += '<br><br><br><font color=gray size=-1>no bids</font><br>\n'
##            else:
##                src += '<h3>your bids</h3>\n'
##                src += '<table width=300 border=0 cellspacing=10 cellpadding=0>\n'
##                src += '<tr>\n'
##                src += '<td align=center>price</td>\n'
##                src += '<td align=center>amount</td>\n'
##                src += '<td align=center>time left<br></td>\n'
##                src += '<td align=center>&nbsp;</td>\n'
##                src += '</tr>\n'
##                for bid in central_service._MarketBids:
##                    timeleft = bid.get('timeleft', '')
##                    public = True
##                    if timeleft != 'bitcoins expected':
##                        timeleft = misc.seconds_to_time_left_string(timeleft)
##                    else:
##                        timeleft = '<font color=red>%s</font>' % timeleft
##                        public = False 
##                    src += '<tr><td colspan=4><hr></td></tr>\n'
##                    src += '<tr>\n'
##                    if public:
##                        src += '<td align=center><font color=red>%s</font><font color=gray size=-2> BTC</font></td>\n' % misc.float2str(bid.get('price', 'error'))
##                        src += '<td align=center><font color=blue>%s</font><font color=gray size=-2> BitPie.NET</font></td>\n' % misc.float2str(bid.get('maxamount', 'error'))
##                    else:
##                        src += '<td align=center><font color=gray>%s</font><font color=gray size=-2> BTC</font></td>\n' % misc.float2str(bid.get('price', 'error'))
##                        src += '<td align=center><font color=gray>%s</font><font color=gray size=-2> BitPie.NET</font></td>\n' % misc.float2str(bid.get('maxamount', 'error'))
##                    src += '<td align=center><font color=green>%s</font></td>\n' % timeleft 
##                    src += '<td align=right><a href="%s"><img src="%s" width=16 height=16></a></td>\n' % (request.path+'?action=cancelbid&bidid='+bid.get('id', ''), iconurl(request, 'icons/delete01.png'))
##                    src += '</tr>\n'
##                    src += '<tr><td colspan=4 align=left><font color=gray size=-1>\n'
##                    if bid.get('comment', '') == '':
##                        src += '<p align=center>the amount of the transaction will be %s BTC</p>' % (
##                            misc.float2str(float(bid['maxamount'])*float(bid['price'])))
##                    else:
##                        src += bid.get('comment', '')                        
##                    src += '\n</font></td></tr>\n'
#                src += '</table>\n'
#        src += '</td>\n'
#        src += '<td align=center valign=top width=50%>\n'
#        # if central_service._MarketOffers is not None:
#        if True:
#            # if len(central_service._MarketOffers) == 0:
#            if True:
#                src += '<br><br><br><font color=gray size=-1>no offers</font><br>\n'
##            else:
##                src += '<h3>your offers</h3>\n'
##                src += '<table width=300 border=0 cellspacing=10 cellpadding=0>\n'
##                src += '<tr>\n'
##                src += '<td align=center>price</td>\n'
##                src += '<td align=center>amount</td>\n'
##                src += '<td align=center>time left</td>\n'
##                src += '<td align=center>&nbsp;</td>\n'
##                src += '</tr>\n'
##                for offer in central_service._MarketOffers:
##                    src += '<tr><td colspan=4><hr></td></tr>\n'
##                    src += '<tr>\n'
##                    src += '<td align=center><font color=red>%s</font><font color=gray size=-2> BTC</font></td>\n' % misc.float2str(offer.get('price', 'error'))
##                    src += '<td align=center><font color=blue>%s - %s</font><font color=gray size=-2> BitPie.NET</font></td>\n' % (misc.float2str(offer.get('minamount', 'error')), misc.float2str(offer.get('maxamount', 'error')))
##                    src += '<td align=center><font color=green>%s</font></td>\n' % misc.seconds_to_time_left_string(offer.get('timeleft', 0))
##                    src += '<td align=right><a href="%s"><img src="%s" width=16 height=16></a></td>\n' % (request.path+'?action=canceloffer&offerid='+offer.get('id', ''), iconurl(request, 'icons/delete01.png'))
##                    src += '</tr>\n'
##                    src += '<tr><td colspan=4 align=left><font color=gray size=-1>\n'
##                    if offer.get('comment', '') == '':
##                        src += '<p align=center>the amount of the transaction will be from %s to %s BTC</p>' % (
##                            misc.float2str(float(offer['minamount'])*float(offer['price'])),
##                            misc.float2str(float(offer['maxamount'])*float(offer['price'])))
##                    else:
##                        src += offer.get('comment', '')                        
##                    src += '\n</font></td></tr>\n'
##                src += '</table>\n'
#        src += '</td>\n'
#        src += '</tr>\n'
#        src += '<tr>\n'
#        src += '<td align=center>\n'
#        src += '<br><br><br>\n'
#        src += '<font size=4><b><a href="%s?back=%s">[buy BitPie.NET credits]</a></b></font><br><br>\n' % ('/'+_PAGE_MONEY_MARKET_BUY, request.path)
#        src += '</td>\n'
#        src += '<td align=center>\n'
#        src += '<br><br><br>\n'
#        src += '<font size=4><b><a href="%s?back=%s">[sell BitPie.NET credits]</a></b></font><br><br>\n' % ('/'+_PAGE_MONEY_MARKET_SELL, request.path)
#        src += '</td>\n'
#        src += '</tr>\n'
#        src += '</table>\n'
#        src += '<p><a href="%s?action=request&back=%s">Send a request to the Market Server for a list of my bids and offers</a></p>\n' % (request.path, back)
#        src += '<br><p>To see bids and offers from all users go to the BitPie.NET <a href="%s" target=_blank>Market Place</a>.</p>' % settings.MarketPlaceURL() 
#        return html(request, body=src, back=back, title='list of my bids and offers')


#class BitCoinSettingsPage(Page):
#    pagename = _PAGE_BIT_COIN_SETTINGS
#    def renderPage(self, request):
#        src = '<h1>BitCoin settings</h1>\n'
#        src += '<table width=70%><tr><td align=center>\n'
#        src += '<p align=justify>Bitcoin is a cryptocurrency where the creation and transfer of bitcoins '
#        src += 'is based on an open-source cryptographic protocol that is independent of any central authority.\n'
#        src += '<a href="http://en.wikipedia.org/wiki/Bitcoin" target=_blank>Read wiki</a> or '
#        src += 'visit <a href="http://bitcoin.org" target="_blank">BitCoin.org</a> to get started.</p>\n'
#        src += '<p align=justify>Here you can specify how to connect with your local or remote BitCoin JSON-RPC server '
#        src += 'on which you installed your wallet.\n '
#        src += 'Read how to get started installing '
#        src += '<a href="https://en.bitcoin.it/wiki/Getting_started_installing_bitcoin-qt" target=_blank>bitcoin-qt</a>\n '
#        src += 'or <a href="http://rdmsnippets.com/2013/03/12/installind-bitcoind-on-ubuntu-12-4-lts/" target=_blank>bitcoind</a> command line server.</p>\n'
#        if not bitcoin.installed():
#            src += '<br><br><font color=red><b>WARNING!!!</b><br>Module bitcoin-python is not installed</font>\n'
#            if bpio.Linux():
#                src += '<font size=-1><br><br>To install it type this commands:\n'
#                src += '<table>\n\n'
#                src += '<tr><td align=left>sudo apt-get update</td></tr>\n'
#                src += '<tr><td align=left>sudo apt-get install python-setuptools</td></tr>\n'
#                src += '<tr><td align=left>sudo easy_install bitcoin-python</td></tr>\n'
#                src += '</table></font>\n'
#        src += '</td></tr></table>\n'
#        src += '<br>\n' 
#        src += '<br><h3>use local or remote server: <a href="%s?back=%s">%s</a></h3>\n' % (
#            '/'+_PAGE_SETTINGS+'/'+'other.bitcoin.bitcoin-server-is-local', request.path,
#            'local' if settings.getBitCoinServerIsLocal() else 'remote')
#        if settings.getBitCoinServerIsLocal():
#            src += '<br><h3>config file location: <a href="%s?back=%s">%s</a></h3>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'other.bitcoin.bitcoin-config-filename', request.path,
#                settings.getBitCoinServerConfigFilename().strip() or 'not specified')
#        else:
#            src += '<br><h3>ip address or host name: <a href="%s?back=%s">%s</a></h3>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'other.bitcoin.bitcoin-host', request.path,
#                settings.getBitCoinServerHost().strip() or 'not specified')
#            src += '<br><h3>port: <a href="%s?back=%s">%s</a></h3>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'other.bitcoin.bitcoin-port', request.path,
#                settings.getBitCoinServerPort().strip() or 'not set')
#            src += '<br><h3>username: <a href="%s?back=%s">%s</a></h3>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'other.bitcoin.bitcoin-username', request.path,
#                settings.getBitCoinServerUserName().strip() or 'not set')
#            src += '<br><h3>password: <a href="%s?back=%s">%s</a></h3>\n' % (
#                '/'+_PAGE_SETTINGS+'/'+'other.bitcoin.bitcoin-password', request.path,
#                ('*'*len(settings.getBitCoinServerPassword()) or 'not set' ))
#        src += '<br><br>\n'
#        return html(request, body=src,  back=arg(request, 'back', '/'+_PAGE_CONFIG), title='BitCoin settings')


#class TransferPage(Page):
#    pagename = _PAGE_TRANSFER
#    def _checkInput(self, amount, bal, recipient):
#        if recipient.strip() == '':
#            return 3
#        try:
#            float(amount)
#        except:
#            return 1
#        if float(amount) > float(bal):
#            return 2
#        return 0
#
#    def renderPage(self, request):
#        bal, balnt, rcptnum = money.LoadBalance()
#        idurls = contacts.getContactsAndCorrespondents()
#        idurls.sort()
#        recipient = arg(request, 'recipient')
#        if recipient.strip() and not recipient.startswith('http://'):
#            recipient = 'http://'+settings.IdentityServerName()+'/'+recipient+'.xml'
#        amount = arg(request, 'amount', '0.0')
#        action = arg(request, 'action')
#        bpio.log(6, 'webcontrol.TransferPage.renderPage [%s] [%s] [%s]' % (action, amount, recipient))
#        msg = ''
#        typ = 'info'
#        button = 'Send money'
#        modify = True
#
#        if action == '':
#            action = 'send'
#
#        elif action == 'send':
#            res = self._checkInput(amount, bal, recipient)
#            if res == 0:
#                action = 'commit'
#                button = 'Yes! Send the money!'
#                modify = False
#                msg = '<table width="60%"><tr><td align=center>'
#                msg += 'Do you want to transfer <font color=blue><b>%s BitPie.NET</b></font>' % misc.float2str(amount)
#                msg += ' of your total <font color=blue><b>%s BitPie.NET</b></font> transferable funds ' % misc.float2str(bal)
#                msg += ' to user <font color=blue><b>%s</b></font> ?<br>\n' % nameurl.GetName(recipient)
#                msg += '<br>Your transferable balance will become <font color=blue><b>%s BitPie.NET</b></font>.' % misc.float2str(float(bal)-float(amount))
#                msg += '</td></tr></table>'
#                typ = 'info'
#            elif res == 1:
#                msg = 'Wrong amount! Please enter a number!'
#                typ = 'error'
#            elif res == 2:
#                msg = 'Sorry! But you do not have enough transferable funds.'
#                typ = 'error'
#            else:
#                msg = 'Unknown error! Please try again.'
#                typ = 'error'
#
#        elif action == 'commit':
#            res = self._checkInput(amount, bal, recipient)
#            if res == 0:
#                # central_service.SendTransfer(recipient, amount)
#                msg = 'A request for the transfer of funds to user <b>%s</b> was sent to the Central server.' % nameurl.GetName(recipient)
#                typ = 'success'
#                button = 'Return'
#                modify = False
#                action = 'return'
#            elif res == 1:
#                action = 'send'
#                button = 'Send money'
#                modify = True
#                msg = 'Wrong amount! Please enter a number!'
#                typ = 'error'
#            elif res == 2:
#                action = 'send'
#                button = 'Send money'
#                modify = True
#                msg = 'Sorry! But you do not have enough transferable funds.'
#                typ = 'error'
#            else:
#                action = 'send'
#                button = 'Send money'
#                modify = True
#                msg = 'Unknown error! Please try again.'
#                typ = 'error'
#
#        elif action == 'return':
#            request.redirect('/'+_PAGE_MONEY)
#            request.finish()
#            return NOT_DONE_YET
#        
#        else:
#            action = 'send'
#            button = 'Send money'
#            modify = True
#            msg = 'Unknown action! Please try again.'
#            typ = 'error'
#
#        src = '<h1>money</h1>\n'
#        src += '<table align=center><tr><td align=left>\n'
#        # src += 'Total balance: <b>%s BitPie.NET</b>\n' % misc.float2str(bal + balnt)
#        src += 'transferable balance: <b>%s BitPie.NET</b>\n' % misc.float2str(bal)
#        # src += '<br><br>Not transferable balance: <b>%s BitPie.NET</b>\n' % misc.float2str(balnt)
#        src += '</td></tr></table>\n'
#        src += '<br><br><br>\n'
#        src += '<form action="%s" method="post">\n' % request.path
#        src += '<input type="hidden" name="action" value="%s" />\n' % action
#        if modify:
#            src += '<table><tr>\n'
#            src += '<td align=right><input type="text" name="amount" value="%s" size=12 /></td>\n' % amount
#            src += '<td align=left>$</td>\n'
#            src += '</tr></table><br>\n'
#            src += '<select name="recipient">\n'
#            for idurl in idurls:
#                name = nameurl.GetName(idurl)
#                src += '<option value="%s"' % idurl
#                if idurl == recipient:
#                    src += ' selected '
#                src += '>%s</option>\n' % name
#            src += '</select><br><br>\n'
#        else:
#            src += '<input type="hidden" name="amount" value="%s" />\n' % amount
#            src += '<input type="hidden" name="recipient" value="%s" />\n' % recipient
#        src += html_message(msg, typ)
#        src += '<br><br>\n'
#        src += '<input type="submit" name="submit" value="%s" />\n' % button
#        src += '</form><br><br>\n'
#        src += html_comment(msg.lower().replace('<b>', '').replace('</b>', ''))
#        return html(request, body=src, back='/'+_PAGE_MONEY, title='money transfer')


#class ReceiptPage(Page):
#    pagename = _PAGE_RECEIPT
#    # isLeaf = True
#    def __init__(self, path):
#        Page.__init__(self)
#        self.path = path
#
#    def renderPage(self, request):
#        bpio.log(6, 'webcontrol.ReceiptPage.renderPage ' + self.path)
#        receipt = money.ReadReceipt(self.path)
#        typ = str(receipt[2])
#        src = '<h1>receipt %s</h1>\n' % self.path
#        if receipt is None:
#            src += html_message('Can not read receipt with number ' + self.path , 'error')
#            return html(request, body=src, back='/'+_PAGE_RECEIPTS)
#        src += '<table cellspacing=5 width=80% align=center>\n'
#        src += '<tr><td align=right width=20%><b>ID:</b></td><td width=80% align=left>' + str(receipt[0]) + '</td></tr>\n'
#        src += html_comment('  ID:     %s' % str(receipt[0]))
#        src += '<tr><td align=right><b>Type:</b></td><td align=left>' + typ + '</td></tr>\n'
#        src += html_comment('  Type:   %s' % typ)
#        src += '<tr><td align=right><b>From:</b></td><td align=left>' + str(receipt[3]) + '</td></tr>\n'
#        src += html_comment('  From:   %s' % str(receipt[3]))
#        src += '<tr><td align=right><b>To:</b></td><td align=left>' + str(receipt[4]) + '</td></tr>\n'
#        src += html_comment('  To:     %s' % str(receipt[4]))
#        if str(receipt[2]) not in ['bid', 'offer', 'cancelbid', 'canceloffer']:
#            src += '<tr><td align=right><b>Amount:</b></td><td align=left>' + misc.float2str(money.GetTrueAmount(receipt)) + ' BitPie.NET</td></tr>\n'
#            src += html_comment('  Amount: %s BitPie.NET' % misc.float2str(money.GetTrueAmount(receipt)))
#        src += '<tr><td align=right><b>Date:</b></td><td align=left>' + str(receipt[1]) + '</td></tr>\n'
#        src += html_comment('  Date:   %s' % str(receipt[1]))
#        d = money.UnpackReport(receipt[-1])
#        if typ == 'space':
#            src += '<tr><td colspan=2>\n'
#            src += '<br><br><table width=100%><tr><td valign=top align=right>\n'
#            src += '<table>\n'
#            src += '<tr><td colspan=2 align=left><b>Suppliers:</b></td></tr>\n'
#            src += '<tr><td>user</td><td>taken Mb</td></tr>\n'
#            src += html_comment('    suppliers, taken Mb')
#            for idurl, mb in d['suppliers'].items():
#                if idurl == 'space' or idurl == 'costs':
#                    continue
#                src += '<tr><td>%s</td>' % nameurl.GetName(idurl)
#                src += '<td nowrap>%s Mb</td>\n' % str(mb)
#                src += '</tr>\n'
#                src += html_comment('      %s  %s' % (nameurl.GetName(idurl).ljust(20), str(mb)))
#            src += '<tr><td>&nbsp;</td></tr>\n'
#            # src += '<tr><td nowrap>total taken space</td><td nowrap>%s Mb</td></tr>\n' % str(d['suppliers']['space'])
#            # src += '<tr><td nowrap>suppliers costs</td><td nowrap>%s$</td></tr>\n' % str(d['suppliers']['costs'])
#            src += '</table>\n'
#            src += '</td><td valign=top align=left>\n'
#            src += '<table>'
#            src += '<tr><td colspan=2 align=left><b>Customers:</b></td></tr>\n'
#            src += html_comment('    customers, given Mb')
#            src += '<tr><td>user</td><td>given Mb</td></tr>\n'
#            for idurl, mb in d['customers'].items():
#                if idurl == 'space' or idurl == 'income':
#                    continue
#                src += '<tr><td>%s</td>' % nameurl.GetName(idurl)
#                src += '<td nowrap>%s Mb</td>\n' % str(mb)
#                src += '</tr>\n'
#                src += html_comment('      %s  %s' % (nameurl.GetName(idurl).ljust(20), str(mb)))
#            src += '<tr><td>&nbsp;</td></tr>\n'
#            # src += '<tr><td nowrap>total given space</td><td nowrap>%s Mb</td></tr>\n' %  str(d['customers']['space'])
#            # src += '<tr><td>customers income</td><td nowrap>%s$</td></tr>\n' % str(d['customers']['income'])
#            src += '</table>\n'
#            src += '</td></tr>\n'
#            src += '<tr><td align=right>\n'
#            src += '<table><tr><td nowrap>total taken space</td><td nowrap>%s Mb</td></tr>\n' % str(d['suppliers']['space'])
#            src += html_comment('    total taken space: %s Mb' % str(d['suppliers']['space']))
#            src += '<tr><td nowrap>suppliers costs</td><td nowrap>%s BitPie.NET</td></tr></table>\n' % str(d['suppliers']['costs'])
#            src += html_comment('    suppliers costs:   %s BitPie.NET' % str(d['suppliers']['costs']))
#            src += '</td><td>\n'
#            src += '<table><tr><td nowrap>total given space</td><td nowrap>%s Mb</td></tr>\n' %  str(d['customers']['space'])
#            src += html_comment('    total given space: %s Mb' % str(d['customers']['space']))
#            src += '<tr><td>customers income</td><td nowrap>%s BitPie.NET</td></tr></table>\n' % str(d['customers']['income'])
#            src += html_comment('    customers income:  %s BitPie.NET' % str(d['customers']['income']))
#            src += '</td></tr>'
#            src += '</table>\n'
#            src += '</td></tr>\n'
#            src += '<tr><td colspan=2 align=center>\n'
#            src += '<br><b>Total profits:</b> %s BitPie.NET\n' % str(d['total']).strip()
#            src += html_comment('    total profits:     %s BitPie.NET' % str(d['total']).strip())
#            src += '</td></tr>\n'
#            src += '<tr><td colspan=2>\n'
#            src += d['text']
#            src += '</td></tr>\n'
#            src += html_comment('    ' + d['text'])
#        else:
#            src += '<tr><td align=right valign=top><b>Details:</b></td><td align=left>' + str(d['text']).replace('\n','<br>') + '</td></tr>\n'
#            src += html_comment('  Details: %s' % str(d['text']))
#        src += '</table>\n'
#        return html(request, body=src, back='/'+_PAGE_RECEIPTS)

#class ReceiptsPage(Page):
#    pagename = _PAGE_RECEIPTS
#    def renderPage(self, request):
#        receipts_list = money.ReadAllReceipts()
#        page = arg(request, 'page', time.strftime('%Y%m'))
#        pageYear = nextYear = prevYear = misc.ToInt(page[:4], int(time.strftime('%Y')))
#        pageMonth =  nextMonth = prevMonth = misc.ToInt(page[4:], int(time.strftime('%m')))
#        nextMonth = pageMonth + 1
#        if nextMonth == 13:
#            nextMonth = 1
#            nextYear += 1
#        prevMonth = pageMonth -1
#        if prevMonth == 0:
#            prevMonth = 12
#            prevYear -= 1
#        next = '%d%02d' % (nextYear, nextMonth)
#        prev = '%d%02d' % (prevYear, prevMonth)
#        nextLabel = '%d %s' % (nextYear, calendar.month_name[nextMonth])
#        prevLabel = '%d %s' % (prevYear, calendar.month_name[prevMonth])
#        src = '<h1>receipts</h1>\n'
#        src += '<br><br>\n'
#        src += '<a href="%s?page=%s">[%s]</a>\n' % (request.path, prev, prevLabel)
#        src += '<a href="%s?page=%s">[%s]</a>\n' % (request.path, next, nextLabel)
#        src += '<table cellpadding=5>\n'
#        src += '<tr align=left>\n'
#        src += '<th>ID</th>\n'
#        src += '<th>Type</th>\n'
#        src += '<th>Amount</th>\n'
#        src += '<th>From</th>\n'
#        src += '<th>To</th>\n'
#        src += '<th>Date</th>\n'
#        src += '</tr>\n'
#        src += html_comment('  ID          Type      Amount        From            To              Date')
#        for receipt in receipts_list:
#            src += html_comment('  %s  %s  %s  %s  %s  %s' % (
#                receipt[0].ljust(10), receipt[1].ljust(8), misc.float2str(receipt[2]).ljust(12), 
#                receipt[3].ljust(14), receipt[4].ljust(14), receipt[5]))
#            try:
#                d = time.strptime(receipt[5], "%a, %d %b %Y %H:%M:%S")
#                if d[0] != pageYear or d[1] != pageMonth:
#                    continue
#            except:
#                bpio.exception()
#                continue
#            src += '<tr><td>'
#            src += '<a href="%s/%s">' % (request.path, receipt[0])
#            src += '%s</a></td>\n' % receipt[0]
#            src += '<td>%s</td>\n' % receipt[1]
#            src += '<td>%s</td>\n' % ('&nbsp;' if float(receipt[2]) == 0.0 else misc.float2str(receipt[2]))
#            src += '<td>%s</td>\n' % receipt[3]
#            src += '<td>%s</td>\n' % receipt[4]
#            src += '<td nowrap>%s</td>\n' % receipt[5]
#            src += '</tr>\n'
#        src += '\n</table>\n'
#        return html(request, body=src, back='/'+_PAGE_MONEY, title='receipts')
#
#    def getChild(self, path, request):
#        if path == '':
#            return self
#        return ReceiptPage(path)

class MessagePage(Page):
    pagename = _PAGE_MESSAGE
    # isLeaf = True
    def __init__(self, path):
        Page.__init__(self)
        self.path = path

    def renderPage(self, request):
        msg = message.ReadMessage(self.path)
        src = ''
        if msg[0] == misc.getLocalID():
            src += '<h1>message to %s</h1>\n' % nameurl.GetName(msg[1])
        else:
            src += '<h1>message from %s</h1>\n' % nameurl.GetName(msg[0])
        src += '<table width=70%><tr><td align=center>'
        src += '<table>\n'
        src += '<tr><td align=right><b>From:</b></td><td>%s</td></tr>\n' % nameurl.GetName(msg[0])
        src += '<tr><td align=right><b>To:</b></td><td>%s</td></tr>\n' % nameurl.GetName(msg[1])
        src += '<tr><td align=right><b>Date:</b></td><td>%s</td></tr>\n' % msg[3]
        src += '<tr><td align=right><b>Subject:</b></td><td>%s</td></tr>\n' % msg[2]
        src += '</table>\n'
        src += '</td></tr>\n'
        src += '<tr><td align=left>\n'
        src += '<table border=1 width=90%><tr><td>\n'
        src += msg[4].replace('\n', '<br>\n')
        src += '<br><br></td></tr></table>\n'
        src += '</td></tr></table>\n'
        src += '<br><br>\n'
        return html(request, body=src, back=_PAGE_MESSAGES)

class MessagesPage(Page):
    pagename = _PAGE_MESSAGES
    sortby = 0
    sortreverse = False
    
    def renderPage(self, request):
        action = arg(request, 'action')
        mid = arg(request, 'mid')
        if action == 'delete' and mid:
            message.DeleteMessage(mid)
        myname = misc.getIDName()
        mlist = message.ListAllMessages()
        _sortby = arg(request, 'sortby', '')
        if _sortby != '':
            _sortby = misc.ToInt(arg(request, 'sortby'), 0)
            if self.sortby == _sortby:
                self.sortreverse = not self.sortreverse
            self.sortby = _sortby
        _reverse = self.sortreverse
        if self.sortby == 0:
            _reverse = not _reverse
        mlist.sort(key=lambda item: item[self.sortby], reverse=_reverse)
        src = ''
        src += '<h1>messages</h1>\n'
        src += '<a href="%s?back=%s">Create a new message</a><br><br>\n' % (
            _PAGE_NEW_MESSAGE, request.path)
        src += '<a href="%s?back=%s">Edit my correspondents list</a><br><br><br>\n' % (
            _PAGE_CORRESPONDENTS, request.path)
        if len(mlist) == 0:
            src += '<p>you have no messages</p>\n'
        else:
            src += '<table width=80% cellpadding=5 cellspacing=0>\n'
            src += '<tr align=left>\n'
            src += '<th><a href="%s?sortby=1">From</a></th>\n' % request.path
            src += '<th><a href="%s?sortby=2">To</a></th>\n' % request.path
            src += '<th><a href="%s?sortby=3">Received/Created</a></th>\n' % request.path
            src += '<th><a href="%s?sortby=4">Subject</a></th>\n' % request.path
            src += '</tr>\n'
            for i in range(len(mlist)):
                msg = mlist[i]
                mid = msg[0]
                bgcolor = '#DDDDFF'
                if myname != msg[1]:
                    bgcolor = '#DDFFDD'
                src += '<tr bgcolor="%s">\n' % bgcolor
                src += '<a href="%s/%s">\n' % (request.path, mid)
                for m in msg[1:]:
                    src += '<td>'
                    src += str(m)
                    src += '</td>\n'
                src += '</a>\n'
                src += '<a href="%s?action=delete&mid=%s"><td>' % (request.path, mid)
                src += '<img src="%s" /></td></a>\n' % iconurl(request, 'icons/delete-message.png')
                src += '</tr>\n'
            src += '</table><br><br>\n'
        return html(request, body=src, title='messages', back=arg(request, 'back', '/'+_PAGE_MENU))

    def getChild(self, path, request):
        if path == '':
            return self
        return MessagePage(path)


class NewMessagePage(Page):
    pagename = _PAGE_NEW_MESSAGE
    
    def renderPage(self, request):
        idurls = contacts.getContactsAndCorrespondents()
        idurls.sort()
        recipient = arg(request, 'recipient', '')
        subject = arg(request, 'subject')
        body = arg(request, 'body')
        action = arg(request, 'action').lower().strip()
        errmsg = ''

        if action == 'send':
            if recipient:
                msgbody = message.MakeMessage(recipient, subject, body)
                message.SendMessage(recipient, msgbody)
                message.SaveMessage(msgbody)
                request.redirect('/'+_PAGE_MESSAGES)
                request.finish()
                return NOT_DONE_YET
            errmsg = 'need to choose recipient'

        src = ''
        src += '<h1>new message</h1>\n'
        if errmsg:
            src += '<font color=red>%s</font><br>\n' % errmsg
        src += '<form action="%s", method="post">\n' % request.path
        src += '<table>\n'
        src += '<tr><td align=right>'
        src += '<b>To:</b></td>\n'
        src += '<td><select name="recipient">\n'
        for idurl in ['',] + idurls:
            name = nameurl.GetName(idurl)
            src += '<option value="%s"' % idurl
            if idurl == recipient:
                src += ' selected '
            src += '>%s</option>\n' % name
        src += '</select></td>\n'
        src += '<td align=right><a href="%s?back=%s">Add new correspondent</a></td></tr>\n' % (
            '/'+_PAGE_CORRESPONDENTS, request.path)
        src += '<tr><td align=right><b>Subject:</b></td>\n'
        src += '<td colspan=2><input type="text" name="subject" value="%s" size="51" /></td></tr>\n' % subject
        src += '</table>\n'
        src += '<textarea name="body" rows="10" cols="60">%s</textarea><br><br>\n' % body
        src += '<input type="submit" name="action" value=" Send " /><br>\n'
        src += '</form>'
        return html(request, body=src, back=_PAGE_MESSAGES)

class CorrespondentsPage(Page):
    pagename = _PAGE_CORRESPONDENTS

    def _check_name_cb(self, x, request, name):
        idurl = 'http://' + settings.IdentityServerName() + '/' + name + '.xml'
        contacts.addCorrespondent(idurl)
        contacts.saveCorrespondentIDs()
        propagate.SendToID(idurl) #, lambda packet: self._ack_handler(packet, request, idurl))
        src = self._body(request, '', '%s was found' % name, 'success')
        request.write(html_from_args(request, body=src, back=arg(request, 'back', '/'+_PAGE_MENU)))
        request.finish()

    def _check_name_eb(self, x, request, name):
        src = self._body(request, name, '%s was not found' % name, 'failed')
        request.write(html_from_args(request, body=src, back=arg(request, 'back', '/'+_PAGE_MENU)))
        request.finish()

    def _body(self, request, name, msg, typ):
        #idurls = contacts.getContactsAndCorrespondents()
        idurls = contacts.getCorrespondentIDs()
        idurls.sort()
        src = ''
        src += '<h1>friends</h1>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += 'enter user name:<br>\n'
        src += '<input type="text" name="name" value="%s" size="20" />\n' % name
        src += '<input type="submit" name="button" value=" add " />'
        src += '<input type="hidden" name="action" value="add" />\n'
        src += '</form><br><br>\n'
        src += html_message(msg, typ)
        src += '<br><br>\n'
        if len(idurls) == 0:
            src += '<p>you have no friends</p>\n'
        else:
            w, h = misc.calculate_best_dimension(len(idurls))
            imgW = 64
            imgH = 64
            if w >= 4:
                imgW = 4 * imgW / w
                imgH = 4 * imgH / w
            padding = 64 / w - 8 
            src += '<table cellpadding=%d cellspacing=2>\n' % padding
            for y in range(h):
                src += '<tr valign=center>\n'
                for x in range(w):
                    src += '<td align=center width="%s%%">\n' % ((str(int(100.0/float(w)))))
                    n = y * w + x
                    if n >= len(idurls):
                        src += '&nbsp;\n'
                        continue
                    idurl = idurls[n]
                    name = nameurl.GetName(idurl)
                    if not name:
                        src += '&nbsp;\n'
                        continue
                    # central_status = central_service.get_user_status(idurl)
                    central_status = '?'
                    icon = 'icons/offline-user01.png'
                    state = 'offline'
                    #if contact_status.isOnline(idurl):
                    if central_status in ['!', '=']:
                        icon = 'icons/online-user01.png'
                        state = 'online '
                    if w >= 5 and len(name) > 10:
                        name = name[0:9] + '<br>' + name[9:]
                    src += '<img src="%s" width=%d height=%d>' % (
                        iconurl(request, icon), imgW, imgH,)
                    src += '<br>\n'
                    src += '%s' % name
                    src += '&nbsp;[<a href="%s?action=remove&idurl=%s&back=%s">x</a>]\n' % (
                        request.path, nameurl.Quote(idurl), arg(request, 'back', '/'+_PAGE_MENU))
                    src += '</td>\n'
                src += '</tr>\n'
            src += '</table>\n'
        src += '<br><br>\n'
        return src

    def renderPage(self, request):
        idurls = contacts.getCorrespondentIDs()
        idurls.sort()
        action = arg(request, 'action')
        idurl = nameurl.UnQuote(arg(request, 'idurl'))
        name = arg(request, 'name', nameurl.GetName(idurl))
        msg = ''
        typ = 'info'
        if action == 'add':
            idurl = 'http://' + settings.IdentityServerName() + '/' + name + '.xml'
            if not misc.ValidUserName(name):
                msg = 'incorrect user name'
                typ = 'error'
            elif idurl in idurls:
                msg = '%s is your friend already' % name
                typ = 'error' 
            else:
                bpio.log(6, 'webcontrol.CorrespondentsPage.renderPage (add) will request ' + idurl)
                res = net_misc.getPageTwisted(idurl)
                res.addCallback(self._check_name_cb, request, name)
                res.addErrback(self._check_name_eb, request, name)
                request.notifyFinish().addErrback(self._check_name_eb, request, name)
                return NOT_DONE_YET
        elif action == 'remove':
            if idurl in contacts.getCorrespondentIDs():
                contacts.removeCorrespondent(idurl)
                contacts.saveCorrespondentIDs()
                msg = '%s were removed from friends list' % name
                typ = 'success'
                name = ''
            else:
                msg = '%s is not your friend' % name
                typ = 'error'
        src = self._body(request, name, msg, typ)
        return html(request, body=src, back=arg(request, 'back', _PAGE_CORRESPONDENTS))


class ShedulePage(Page):
    pagename = _PAGE_SHEDULE
    set_change = False
    available_types = {  '0': 'none',
                         '1': 'hourly',
                         '2': 'daily',
                         '3': 'weekly',
                         '4': 'monthly',
                         '5': 'continuously'}

    def load_from_data(self, request):
        return schedule.default()

    def read_from_html(self, request, default=schedule.default_dict()):
        shedule_type = arg(request, 'type', default['type'])
        shedule_time = arg(request, 'daytime', default['daytime'])
        shedule_interval = arg(request, 'interval', default['interval'])
        shedule_details = arg(request, 'details',  '')
        if shedule_details.strip() == '':
            shedule_details = default['details']
        shedule_details_str = ''
        for i in range(32):
            if request.args.has_key('detail'+str(i)):
                shedule_details_str += request.args['detail'+str(i)][0] + ' '
        if shedule_details_str != '':
            shedule_details = shedule_details_str.strip()
        return schedule.Schedule(from_dict={
            'type':     shedule_type,
            'daytime':  shedule_time,
            'interval': shedule_interval,
            'details':  shedule_details,
            'lasttime': ''})

    def store_params(self, request):
        return ''

    def save(self, request):
        pass

    def print_shedule(self, request):
        stored = self.load_from_data(request)
        src = '<p>'
        src += stored.html_description()
        src += '<br>\n'
        src += stored.html_next_start()
        src += '</p>\n'
        return src
    
    def renderPage(self, request):
        action = arg(request, 'action')
        submit = arg(request, 'submit').strip()
        back = arg(request, 'back', '/'+_PAGE_MAIN)
        
        stored = self.load_from_data(request)
        bpio.log(6, 'webcontrol.ShedulePage.renderPage stored=%s args=%s' % (str(stored), str(request.args)))

        src = ''

        #---form                    
        src += '<form action="%s" method="post">\n' % request.path

        if action == '':
            src += '<input type="hidden" name="action" value="type" />\n'
            src += '<input type="hidden" name="back" value="%s" />\n' % back
            src += self.store_params(request)
            src += '<br><br>\n<input type="submit" name="submit" value=" change "/>\n'
            
        elif action == 'type' or ( action == 'save' and submit == 'back'):
            #---type
            current_type = stored.type #arg(request, 'type', 'none')
            src += '<input type="hidden" name="action" value="details" />\n'
            src += '<input type="hidden" name="back" value="%s" />\n' % back
            src += self.store_params(request)
            src += '<br><br>\n'
            for i in range(len(self.available_types)):
                src += '<input id="radio%s" type="radio" name="type" value="%s" %s />&nbsp;&nbsp;&nbsp;\n' % (
                    str(i), self.available_types[str(i)],
                    ( 'checked' if current_type == self.available_types[str(i)] else '' ), )
            src += '<br><br>\n<input type="submit" name="submit" value=" select "/>\n'
        
        elif action == 'details':
            #---details
            current_type = arg(request, 'type', 'none')
            if current_type != stored.type:
                current = schedule.Schedule(typ=current_type)
            else:
                current = stored
            src += '<input type="hidden" name="action" value="save" />\n'
            src += '<input type="hidden" name="back" value="%s" />\n' % back
            src += '<input type="hidden" name="type" value="%s" />\n' % current.type
            src += self.store_params(request)
            src += '<br><br>\n'
            #---none
            if current.type == 'none':
                src += '<input type="hidden" name="details" value="%s" />\n' % current.details
                src += 'start only one time, after you press a button<br>\n'
                src += '<input type="hidden" name="daytime" value="%s" />\n' % current.daytime
                src += '<input type="hidden" name="interval" value="%s" />\n' % current.interval
            #---continuously
            elif current.type == 'continuously':
                src += '<input type="hidden" name="details" value="%s" />\n' % current.details
                src += 'start every '
                src += '<input type="text" name="interval" value="%s" size=4 />' % current.interval
                src += '&nbsp;seconds<br>\n'
                src += '<input type="hidden" name="daytime" value="%s" />\n' % current.daytime
            #---hourly
            elif current.type == 'hourly':
                src += '<input type="hidden" name="details" value="%s" />\n' % current.details
                src += 'start every '
                src += '<input type="text" name="interval" value="%s" size=2 />' % current.interval
                src += '&nbsp;hour(s)<br>\n'
                src += '<input type="hidden" name="daytime" value="%s" size=10 />\n' % current.daytime
            #---daily
            elif current.type == 'daily':
                src += '<input type="hidden" name="details" value="%s" />\n' % current.details
                src += 'start at&nbsp;&nbsp;'
                src += '<input type="text" name="daytime" value="%s" size=10 />' % current.daytime
                src += '&nbsp;&nbsp;every&nbsp;&nbsp;'
                src += '<input type="text" name="interval" value="%s" size=1 />' % current.interval
                src += '&nbsp;&nbsp;day(s)<br>\n'
            #---weekly
            elif current.type == 'weekly':
                src += '<input type="hidden" name="details" value="%s" />\n' % current.details
                src += 'start at '
                src += '<input type="text" name="daytime" value="%s" size=10 />' % current.daytime
                src += '&nbsp;every&nbsp;'
                src += '<input type="text" name="interval" value="%s" size=1 />' % current.interval
                src += '&nbsp;week(s) in:<br><br>\n'
                src += '<table><tr>\n'
                labels = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
                days = current.details.split(' ')
                for i in range(len(labels)):
                    day = labels[i]
                    src += '<td>'
                    src += '<input type="checkbox" name="detail%d" value="%s" %s /> &nbsp;&nbsp;%s\n' % (
                        i, day, ('checked' if day in days else ''), day)
                    src += '</td>\n'
                    if i == 3:
                        src += '</tr>\n<tr>\n'
                src += '<td>&nbsp;</td>\n'
                src += '</tr></table><br>\n'
            #---monthly
            elif current.type == 'monthly':
                src += '<input type="hidden" name="details" value="%s" />\n' % current.details
                src += 'start at '
                src += '<input type="text" name="daytime" value="%s" size=10 />' % current.daytime
                src += '&nbsp;every&nbsp;'
                src += '<input type="text" name="interval" value="%s" size=1 />' % current.interval
                src += '&nbsp;month(s) at dates:<br><br>\n'
                src += '<table><tr>\n'
                labels = current.details.split(' ')
                for i in range(0,4):
                    for j in range(0, 8):
                        label = str(i*8 + j + 1)
                        if int(label) > 31:
                            src += '<td>&nbsp;</td>\n'
                        else:
                            src += '<td><input type="checkbox" name="detail%s" value="%s" %s />&nbsp;&nbsp;%s</td>\n' % (
                                label, label, ('checked' if label in labels else ''), label)
                    src += '</tr>\n<tr>\n'
                src += '</tr></table><br>\n'
            src += '<br>\n'
            src += '<input type="submit" name="submit" value=" back "/>&nbsp;&nbsp;&nbsp;&nbsp;\n'
            src += '<input type="submit" name="submit" value=" save "/>\n'
            
        elif action == 'save':
            #---save
            if submit == 'save':
                self.save(request)
                src += '<br><br>\n'
                src += html_message('saved!', 'done')
            else:
                bpio.log(2, 'webcontrol.ShedulePage.renderPage ERROR incorrect "submit" parameter value: ' + submit)
                src += '<input type="hidden" name="action" value="type" />\n'
                src += '<input type="hidden" name="back" value="%s" />\n' % back
                src += self.store_params(request)
                src += '<br><br>\n<input type="submit" name="submit" value=" change "/>\n'
                
        src += '</form><br><br>\n'

        #---print schedule
        src = '<br><br>\n' + self.print_shedule(request) + '<br>\n' + src
        src += '\n<a href="%s">[return]</a><br>\n' % back


        return html(request, body=src, back=back)
        

# class BackupShedulePage(ShedulePage):
#     pagename = _PAGE_BACKUP_SHEDULE
# 
#     def load_from_data(self, request):
#         backupdir = unicode(misc.unpack_url_param(arg(request, 'backupdir'), None))
#         if backupdir is None:
#             bpio.log(1, 'webcontrol.BackupShedulePage.load WARNING backupdir=%s' % str(backupdir))
#             return schedule.empty()
#         current = backup_db.GetSchedule(backupdir)
#         if current is None:
#             return schedule.empty()
#         return current
# 
#     def save(self, request):
#         backupdir = unicode(misc.unpack_url_param(arg(request, 'backupdir'), None))
#         if backupdir is None:
#             bpio.log(1, 'webcontrol.BackupShedulePage.save ERROR backupdir=None')
#             return
#         if backupdir != '' and not backup_db.CheckDirectory(backupdir):
#             backup_db.AddDirectory(backupdir, True)
#         dirsize.ask(backupdir)
#         current = self.read_from_html(request)
#         backup_db.SetSchedule(backupdir, current)
#         backup_db.Save()
#         # reactor.callLater(0, backup_schedule.run)
#         bpio.log(6, 'webcontrol.BackupShedulePage.save success %s %s' % (backupdir, current))
# 
#     def list_params(self):
#         return ('backupdir',)
# 
#     def store_params(self, request):
#         src = ''
#         backupdir = unicode(misc.unpack_url_param(arg(request, 'backupdir'), None))
#         if backupdir is not None:
#             src += '<input type="hidden" name="backupdir" value="%s" />\n' % str(misc.pack_url_param(backupdir))
#         return src
# 
#     def print_shedule(self, request):
#         backupdir = unicode(misc.unpack_url_param(arg(request, 'backupdir'), None))
#         src = ''
#         if backupdir is None:
#             src += '<p>icorrect backup directory</p>\n'
#             src += html_comment('icorrect backup directory\n')
#             return src
#         src += '<h3>%s</h3>\n' % backupdir
#         src += html_comment(str(backupdir))
#         stored = self.load_from_data(request)
#         description = stored.html_description()
#         next_start = stored.html_next_start()
#         src += '<p>'
#         src += description+'<br>\n'
#         src += html_comment(description.replace('<b>', '').replace('</b>', ''))+'\n'
#         src += next_start+'\n'
#         src += html_comment(next_start.replace('<b>', '').replace('</b>', ''))+'\n'
#         src += '</p>\n'
#         return src


#class UpdateShedulePage(ShedulePage):
#    pagename = _PAGE_UPDATE_SHEDULE
#    available_types = {  '0': 'none',
#                         '1': 'hourly',
#                         '2': 'daily',
#                         '3': 'weekly',
#                         '4': 'monthly',}
#
#    def load_from_data(self, request):
#        return schedule.Schedule(from_dict=bpupdate.read_shedule_dict())
#
#    def save(self, request):
#        current = self.read_from_html(request)
#        settings.setUpdatesSheduleData(current.to_string())
#        bpupdate.update_shedule_file(settings.getUpdatesSheduleData())
#        bpupdate.update_sheduler()
#        bpio.log(6, 'webcontrol.UpdateShedulePage.save success')
#
#    def print_shedule(self, request):
#        src = '<h3>update schedule</h3>\n'
#        stored = self.load_from_data(request)
#        src += '<p>'
#        description = stored.html_description()
#        next_start = stored.html_next_start()
#        src += description + ',<br>\n'
#        src += next_start
#        src += '</p>\n'
#        return src


_DevReportProcess = ''
class DevReportPage(Page):
    pagename = _PAGE_DEV_REPORT

    def progress_callback(self, x, y):
        global _DevReportProcess
        if x == y:
            _DevReportProcess = ''
        else:
            _DevReportProcess = '%d/%d' % (x,y)
        
    def renderPage(self, request):
        global local_version
        global _DevReportProcess

        subject = arg(request, 'subject')
        body = arg(request, 'body')
        action = arg(request, 'action').lower().strip()
        includelogs = arg(request, 'includelogs', 'True')

        src = ''
        if action == 'send' and _DevReportProcess == '':
            misc.SendDevReport(subject, body, includelogs=='True', 
                progress=self.progress_callback)
            _DevReportProcess = '0/0'
            # src += '<br><br><br><h3>Thank you for your help!</h3>'
            # return html(request, body=src, back=_PAGE_CONFIG, reload='5')
            
        if _DevReportProcess:
            src += '<br><br><br><h3>Thank you for your help !!!</h3>'
            src += '<br><br><h3>progress</h3>\n'
            if _DevReportProcess == '0/0':
                src += 'compressing ... '
            else:
                src += 'sending: ' + _DevReportProcess
            return html(request, body=src, back='/'+_PAGE_CONFIG, reload='0.2')
        
        src += '<h3>send Message</h3>\n'
        src += '<form action="%s", method="post">\n' % request.path
        src += '<table>\n'
        src += '<tr><td align=right><b>To:</b></td>\n'
        src += '<td>BitPie.NET'
        src += '</td>\n'
        src += '<td align=right>\n'
        src += '<input type="checkbox" name="includelogs" value="True" %s /> include logs\n' % (
            'checked' if includelogs=='True' else '')
        src += '</td></tr>\n'
        src += '<tr><td align=right><b>Subject:</b></td>\n'
        src += '<td colspan=2><input type="text" name="subject" value="%s" size="51" /></td></tr>\n' % subject
        src += '</table>\n'
        src += '<textarea name="body" rows="10" cols="40">%s</textarea><br><br>\n' % body
        src += '<input type="submit" name="action" value=" Send " /><br>\n'
        src += '</form>'
        return html(request, body=src, back='/'+_PAGE_CONFIG)


class MemoryPage(Page):
    pagename = _PAGE_MEMORY

    def renderPage(self, request):
        src = '<h1>memory usage</h1>\n'
        if not settings.enableMemoryProfile():
            src = '<p>You need to switch on <a href="%s">memory profiler</a> in the settings and restart BitPie.NET.</p>\n' % (
                '/'+_PAGE_SETTINGS+'/'+'logs.memprofile-enable')
            src += html_comment('You need to switch on memory profiler in the settings.')
            return html(request, back=arg(request, 'back', '/'+_PAGE_CONFIG), body=src)
        try:
            from guppy import hpy #@UnresolvedImport
        except:
            src = 'guppy package is not installed in your system.'
            src += html_comment('guppy package is not installed in your system.')
            return html(request, back=arg(request, 'back', '/'+_PAGE_CONFIG), body=src)
        # bpio.log(6, 'webcontrol.MemoryPage')
        h = hpy()
        out = str(h.heap())
        bpio.log(6, '\n'+out)
        src = ''
        src += '<table width="600px"><tr><td>\n'
        src += '<div align=left>\n'
        src += '<code>\n'
        wwwout = out.replace(' ', '&nbsp;').replace("'", '"').replace('<', '[').replace('>', ']').replace('\n', '<br>\n')
        src += wwwout
        src += '</code>\n</div>\n</td></tr></table>\n'
        for line in out.splitlines():
            src += html_comment(line)
        return html(request, back=arg(request, 'back', '/'+_PAGE_CONFIG), body=src)

                   
class EmergencyPage(Page):
    pagename = _PAGE_EMERGENCY
    
    def renderPage(self, request):
        back = arg(request, 'back') 
        message = ''
        src = ''
        src += '<h1>emergency contacts</h1>\n'
        src += '<form action="%s" method="post">\n' % request.path
        src += '<table width="70%"><tr><td align=center>\n'
        src += '<p>We can contact you if your account balance is running low,' 
        src += 'if your backups are not working, or if your machine appears to not be working.</p>\n'
        src += '<br><br><b>What email address should we contact you at? Email contact is free.</b>\n'
        src += '<br><br><input type="text" name="email" size="25" value="%s" />\n' % arg(request, 'email')
        src += '<br><br><b>%s</b>\n' % settings.uconfig().get('emergency.emergency-phone', 'info')
        src += '<br><br><input type="text" name="phone" size="25" value="%s" />\n' % arg(request, 'phone')
        src += '<br><br><b>%s</b>\n' % settings.uconfig().get('emergency.emergency-fax', 'info')
        src += '<br><br><input type="text" name="fax" size="25" value="%s" />\n' % arg(request, 'fax')
        src += '<br><br><b>%s</b>\n' % settings.uconfig().get('emergency.emergency-text', 'info')
        src += '<br><br><textarea name="text" rows="5" cols="40">%s</textarea><br>\n' % arg(request, 'text')
        # if message != '':
        #     src += '<br><br><font color="%s">%s</font>\n' % (messageColor, message)
        src += '<br><center><input type="submit" name="submit" value=" save " /></center>\n'
        src += '<input type="hidden" name="action" value="contacts-ready" />\n'
        src += '<input type="hidden" name="showall" value="true" />\n'
        src += '</td></tr></table>\n'
        src += '</form>\n'
        return html(request, body=src, back=back)     
   

class MonitorTransportsPage(Page):
    pagename = _PAGE_MONITOR_TRANSPORTS
    mode = 'connections'
    
    def renderPage(self, request):
        reloadtime = arg(request, 'reloadtime', '1')
        modeswitch = arg(request, 'modeswitch', '')
        if modeswitch == 'transfers':
            self.mode = 'transfers'
        elif modeswitch == 'connections':
            self.mode = 'connections'
        src = ''
        if self.mode == 'transfers':
            src += '<a href="?modeswitch=connections">connections</a> | <b>transfers</b> '
        else:
            src += ' <b>connections</b> | <a href="?modeswitch=transfers">transfers</a>'
        src += '&nbsp;&nbsp;&nbsp;'
        src += 'reload: <a href="?reloadtime=0.1">[1/10 sec.]</a>|'
        src += '<a href="?reloadtime=0.2">[1/5 sec.]</a>|'
        src += '<a href="?reloadtime=0.5">[1/2 sec.]</a>|'
        src += '<a href="?reloadtime=1">[1 sec.]</a>|'
        src += '<a href="?reloadtime=5">[5 sec.]</a>\n'
        src += '<br>\n'
        if self.mode == 'transfers':
            src += self.renderTransfers(request)
        else:
            src += self.renderConnections(request)
        return html(request, body=src, back='none', home='', reload=reloadtime, window_title='Traffic')
    
    def renderTransfers(self, request):
        index = {'unknown': {'send': [], 'receive':[]}}
#        for tid, info_in in gate.transfers_in().items():
#            idurl = info_in.remote_idurl
#            if not index.has_key(idurl):
#                index[idurl] = {'send': [], 'receive':[]}
#            index[idurl]['receive'].append((info_in.transfer_id, info_in.proto, 
#                                            info_in.size, ''))
#        for tid, info_out in gate.transfers_out().items():
#            idurl = info_out.remote_idurl
#            if not index.has_key(idurl):
#                index[idurl] = {'send': [], 'receive':[]}
#            index[idurl]['send'].append((info_out.transfer_id, info_out.proto, 
#                                         info_out.size, info_out.description))
        for idurl in stats.counters_in().keys() + stats.counters_out().keys():
            if idurl in ['total_bytes', 'total_packets', 'unknown_bytes', 'unknown_packets']:
                continue
            if not index.has_key(idurl):
                index[idurl] = {'send': [], 'receive':[]}
        src = ''        
        src += '<font size=-4>\n'
        src += '<table width=100%>'
        src += '<tr><td width=50% valign=top>\n'
        src += '<p>send queue length: <b>%d</b>\n</p>\n' % len(packet_out.queue())
        if len(packet_out.queue()) > 0:
            src += '<table width=100% cellspacing=0 cellpadding=2 border=0>\n'
            src += '<tr bgcolor="#000000">\n'
            src += '<td align=left nowrap><b><font color="#ffffff">remote IDURL</font></b></td>\n'
            src += '<td align=left nowrap><b><font color="#ffffff">command</font></b></td>\n'
            src += '<td align=left nowrap><b><font color="#ffffff">packet ID</font></b></td>\n'
            # src += '<td align=left><b><font color="#ffffff">file name</font></b></td>\n'
            src += '<td align=left nowrap><b><font color="#ffffff">file size</font></b></td>\n'
            src += '<td align=left nowrap><b><font color="#ffffff">host</font></b></td>\n'
            src += '<td align=left nowrap><b><font color="#ffffff">transfer ID</font></b></td>\n'
            src += '</tr>\n'
            i = 0
            for workitem in []: # packet_out.queue():
                if i % 2: 
                    src += '<tr>\n'
                else:
                    src += '<tr bgcolor="#f0f0f0">\n'
                src += '<td>%s</td>\n' % nameurl.GetName(workitem.remoteid)
                src += '<td>%s</td>\n' % workitem.command
                packetid = workitem.packetid if len(workitem.packetid) < 30 else ('...'+workitem.packetid[-30:])
                src += '<td>%s</td>\n' % packetid
                # src += '<td>%s</td>\n' % os.path.basename(workitem.filename)
                src += '<td>%d</td>\n' % workitem.filesize
                src += '<td>%s://%s</td>\n' % (workitem.proto, workitem.host) 
                src += '<td>%s</td>\n' % (str(workitem.transfer_id) or '') 
                src += '</tr>\n'
                i += 1
            src += '</table>\n'
        src += '</td>\n<td width=50% valign=top>\n' 
        src += '<p>current transfers: <b>%d</b>\n</p>\n' % (0, 0)
           # len(gate.transfers_in())+len(gate.transfers_out()))
        if False:
        # if len(index) > 0:
            src += '<table width=100% cellspacing=0 cellpadding=2 border=0>\n'
            src += '<tr bgcolor="#000000">\n'
            src += '<td align=left><b><font color="#ffffff">received</font></b></td>\n'
            src += '<td align=right width=45%>&nbsp;</td>\n'
            src += '<td align=center width=10><font color="#ffffff">reqs.</font></td>\n'
            src += '<td align=center width=100>&nbsp;</td>\n'
            src += '<td align=center width=10><font color="#ffffff">send</font></td>\n'
            src += '<td align=left width=45%>&nbsp;</td>\n'
            src += '<td align=right><b><font color="#ffffff">sent</font></b></td>\n'
            src += '</tr>\n'
            i = 0
            for idurl in sorted(index.keys()):
                i += 1
                if idurl == 'unknown':
                    bytes_in = stats.counters_in().get('unknown_bytes', {'receive': 0})
                    bytes_in = '&nbsp;' if bytes_in == 0 else diskspace.MakeStringFromBytes(bytes_in) 
                    bytes_out = stats.counters_out().get('unknown_bytes', {'send': 0})['send']
                    bytes_out = '&nbsp;' if bytes_out == 0 else diskspace.MakeStringFromBytes(bytes_out)
                    send_queue = 0
                    request_queue = 0
                else:
                    bytes_in = stats.counters_in().get(idurl, {'receive': 0})['receive']
                    bytes_in = '&nbsp;' if bytes_in == 0 else diskspace.MakeStringFromBytes(bytes_in) 
                    bytes_out = stats.counters_out().get(idurl, {'send': 0})['send']
                    bytes_out = '&nbsp;' if bytes_out == 0 else diskspace.MakeStringFromBytes(bytes_out)
                    send_queue = io_throttle.GetSendQueueLength(idurl)
                    request_queue = io_throttle.GetRequestQueueLength(idurl)
                if i % 2: 
                    src += '<tr>\n'
                else:
                    src += '<tr bgcolor="#f0f0f0">\n'
                src += '<td nowrap align=left>%s</td>\n' % bytes_in
                src += '<td align=right>\n'
                if len(index.get(idurl, {'receive': []})['receive']) > 0:
                    src += '<table border=0 cellspacing=0 cellpadding=0><tr><td align=right>\n'
                    counter = 0
                    for tranfer_id, proto, size, description in index[idurl]['receive']:
                        command = description
                        if description.count('('):
                            command = description[:description.find('(')]
                        b = 0 # bytes_stats[tranfer_id]
                        if str(size) not in ['', '0', '-1']:
                            progress = '%s/%s' % (diskspace.MakeStringFromBytes(b).replace(' ',''), diskspace.MakeStringFromBytes(size).replace(' ',''))
                        else:
                            progress = '%s' %  diskspace.MakeStringFromBytes(b).replace(' ','')
                        src += '<table bgcolor="#a0a0f0"><tr><td nowrap><font>%s:%s[%s]</font></td></tr></table>\n' % (
                            proto, command, progress)
                        counter += 1
                    src += '</td></tr></table>\n'
                else:
                    src += '&nbsp;'
                src += '</td>\n'
                if contact_status.isOnline(idurl):
                    color = 'green'
                else:
                    color = 'gray'
                src += '<td align=right nowrap><font color=gray>%d</font></td>\n' % request_queue
                src += '<td align=center nowrap><b><font color=%s> %s </font></b></td>\n' % (
                    color, 
                    'unknown' if idurl == 'unknown' else nameurl.GetName(idurl), 
                    )
                src += '<td align=left nowrap><font color=gray>%d</font></td>\n' % send_queue
                src += '<td align=left>'
                if len(index.get(idurl, {'send': []})['send']) > 0:
                    src += '<table border=0 cellspacing=0 cellpadding=0><tr><td align=left>\n'
                    for tranfer_id, proto, size, description in index[idurl]['send']:
                        b = 0 # bytes_stats[tranfer_id]
                        command = description
                        if description.count('('):
                            command = description[:description.find('(')]
                        if b:
                            progress = '%s/%s' % (diskspace.MakeStringFromBytes(b).replace(' ',''), diskspace.MakeStringFromBytes(size).replace(' ',''))
                        else:
                            progress = '%s' %  diskspace.MakeStringFromBytes(size).replace(' ','')
                        src += '<table bgcolor="#a0f0a0"><tr><td nowrap><font>%s:%s[%s]</font></td></tr></table>\n' % (
                            proto, command, progress)
                    src += '</td></tr></table>\n'
                else:
                    src += '&nbsp;'
                src += '</td>\n'
                src += '<td nowrap align=right>%s</td>\n' % bytes_out
                src += '</tr>\n'
            src += '<tr bgcolor="#d0d0d0">\n'
            src += '<td nowrap>%s</td>\n' % '0 b' # diskspace.MakeStringFromBytes(counters.get('total_bytes', {'receive': 0})['receive'])
            src += '<td>&nbsp;</td>\n'
            src += '<td>&nbsp;</td>\n'
            src += '<td>&nbsp;</td>\n'
            src += '<td>&nbsp;</td>\n'
            src += '<td>&nbsp;</td>\n'
            src += '<td nowrap>%s</td>\n' % '0 b' # diskspace.MakeStringFromBytes(counters.get('total_bytes', {'send': 0})['send'])
            src += '</tr>\n'
            src += '</table>\n'
        src += '</td></tr>\n'
        src += '</table>\n'
        src += '</font>\n'
        return src

    def renderConnections(self, request):
        src = ''
        src += '<font size=-4>\n'
        src += '<table width=100%>'
        src += '<tr>'
#        src += '<td width=33% valign=top>\n'
#        if False:
#            src += '<p>opened TCP connections: <b>%d</b></p>' % gate.opened_connections_count()
#            if len(transport_tcp.opened_connections()) > 0:
#                src += '<table width=100% cellspacing=0 cellpadding=2 border=0>\n'
#                src += '<tr bgcolor="#000000">\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">remote host</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">remote port</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">pending files</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">sent</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">received</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">sending/receiving</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">mode</font></b></td>\n'
#                src += '</tr>\n'
#                i = 0
#                for address, connections in transport_tcp.opened_connections().items():
#                    for connection in connections:
#                        if i % 2: 
#                            src += '<tr>\n'
#                        else:
#                            src += '<tr bgcolor="#f0f0f0">\n'
#                        i += 1
#                        src += '<td nowrap>%s</td>' % address[0]
#                        src += '<td nowrap>%d</td>' % address[1]
#                        src += '<td nowrap>%d</td>' % len(connection.outbox)
#                        src += '<td nowrap>%s</td>' % diskspace.MakeStringFromBytes(connection.totalBytesSent)
#                        src += '<td nowrap>%s</td>' % diskspace.MakeStringFromBytes(connection.totalBytesReceived)
#                        st = []
#                        if connection.fileSender is not None:
#                            st.append('sending')
#                        if connection.fileReceiver is not None:
#                            st.append('receiving')
#                        src += '<td nowrap>%s</td>' % (','.join(st))
#                        src += '<td nowrap>%s</td>' % (str(connection.type)[0])
#                        src += '</tr>\n'
#                src += '</table>\n'
#            src += '<p>started TCP connections: <b>%d</b></p>\n' % len(transport_tcp.started_connections())
#            if len(transport_tcp.started_connections()) > 0:
#                src += '<table width=100% cellspacing=0 cellpadding=2 border=0>\n'
#                src += '<tr bgcolor="#000000">\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">remote host</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">remote port</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">pending files</font></b></td>\n'
#                src += '</tr>\n'
#                i = 0
#                for address, connection in transport_tcp.started_connections().items():
#                    if i % 2: 
#                        src += '<tr>\n'
#                    else:
#                        src += '<tr bgcolor="#f0f0f0">\n'
#                    i += 1
#                    src += '<td nowrap>%s</td>' % address[0]
#                    src += '<td nowrap>%d</td>' % address[1]
#                    src += '<td nowrap>%d</td>' % len(connection.pendingoutboxfiles)
#                    src += '</tr>\n'
#                src += '</table>\n'
#        src += '</td>\n'
#        src += '<td width=33% valign=top>\n' 
#        if False: # transport_control._TransportCSpaceEnable:
#            src += '<p>opened CSpace connections: <b>%d</b></p>\n' % (
#                len(transport_cspace.opened_opened_streams_list()))
#            if len(transport_cspace.opened_opened_streams_list()) > 0:
#                src += '<table width=100% cellspacing=0 cellpadding=2 border=0>\n'
#                src += '<tr bgcolor="#000000">\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">key ID</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">state</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">sent</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">received</font></b></td>\n'
#                src += '</tr>\n'
#                i = 0
#                for item in transport_cspace.opened_opened_streams_list():
#                    keyID, state, sentBytes, receivedBytes = item.split(':')
#                    if i % 2: 
#                        src += '<tr>\n'
#                    else:
#                        src += '<tr bgcolor="#f0f0f0">\n'
#                    i += 1
#                    src += '<td nowrap>%s</td>' % keyID
#                    src += '<td nowrap>%s</td>' % state
#                    src += '<td nowrap>%s</td>' % diskspace.MakeStringFromBytes(sentBytes)
#                    src += '<td nowrap>%s</td>' % diskspace.MakeStringFromBytes(receivedBytes)
#                    src += '</tr>\n'
#                src += '</table>\n'
#        src += '</td>\n'
#        src += '<td width=33% valign=top>\n' 
#        if False: # transport_control._TransportUDPEnable:
#            sessions = [] # list(transport_udp_session.sessions())
#            src += '<p>opened UDP sessions: <b>%d</b></p>\n' % len(sessions)
#            if len(sessions) > 0:
#                src += '<table width=100% cellspacing=0 cellpadding=2 border=0>\n'
#                src += '<tr bgcolor="#000000">\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">address</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">state</font></b></td>\n'
#                src += '<td align=left nowrap><b><font color="#ffffff">files in/out</font></b></td>\n'
#                src += '</tr>\n'
#                i = 0
#                for session in sessions:
#                    if i % 2: 
#                        src += '<tr>\n'
#                    else:
#                        src += '<tr bgcolor="#f0f0f0">\n'
#                    i += 1
#                    src += '<td nowrap>%s:%d</td>' % session.remote_address
#                    src += '<td nowrap>%s</td>' % session.state
#                    src += '<td nowrap>%d/%d</td>' % (
#                        len(session.incommingFiles), len(session.outgoingFiles))
#                    src += '</tr>\n'
#                src += '</table>\n'
#        src += '</td>\n'
        src += '</tr>\n'
        src += '</table>\n'
        src += '</font>\n'
        return src


class TrafficPage(Page):
    pagename = _PAGE_TRAFFIC
    def renderPage(self, request):
        src = ''
        src += '<a href="%(baseurl)s?type=%(type)s&dir=in">[incoming]</a>|\n'
        src += '<a href="%(baseurl)s?type=%(type)s&dir=out">[outgoing]</a>\n'
        src += '&nbsp;&nbsp;&nbsp;\n'
        src += '<a href="%(baseurl)s?type=idurl&dir=%(dir)s">[by idurl]</a>|\n'
        src += '<a href="%(baseurl)s?type=host&dir=%(dir)s">[by host]</a>|\n'
        src += '<a href="%(baseurl)s?type=proto&dir=%(dir)s">[by proto]</a>\n'
        src += '<a href="%(baseurl)s?type=type&dir=%(dir)s">[by type]</a>\n'
        direction = request.args.get('dir', [''])[0]
        if direction not in ('in', 'out'):
            direction = 'in'
        typ = request.args.get('type', [''])[0]
        if typ not in ('idurl', 'host', 'proto', 'type'):
            typ = 'idurl'
        if direction == 'in' and webtraffic.inbox_packets_count() > 0:
            src += '<hr>\n'
            src += '<table width=100%%><tr>\n'
            src += '<td align=left>%(type)s</td>\n'
            src += '<td nowrap>total bytes</td>\n'
            src += '<td nowrap>total packets</td>\n'
            src += '<td nowrap>finished packets</td>\n'
            src += '<td nowrap>failed packets</td></tr>\n'
            if typ == 'idurl':
                for i, v in webtraffic.inbox_by_idurl().items():
                    src += '<tr><td><a href="%s">%s</a></td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>\n' % (
                        i, i, v[0], v[3], v[1], v[2])
            elif typ == 'host':
                for i, v in webtraffic.inbox_by_host().items():
                    src += '<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>\n' % (
                        i, v[0], v[3], v[1], v[2])
            elif typ == 'proto':
                for i, v in webtraffic.inbox_by_proto().items():
                    src += '<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>\n' % (
                        i, v[0], v[3], v[1], v[2])
            elif typ == 'type':
                for i, v in webtraffic.inbox_by_type().items():
                    src += '<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>\n' % (
                        i, v[0], v[3], v[1], v[2])
            src += '</table>'
        if direction == 'out' and webtraffic.outbox_packets_count() > 0:
            src += '<hr>\n'
            src += '<table width=100%%><tr>\n'
            src += '<td align=left>%(type)s</td>\n'
            src += '<td nowrap>total bytes</td>\n'
            src += '<td nowrap>total packets</td>\n'
            src += '<td nowrap>finished packets</td>\n'
            src += '<td nowrap>failed packets</td></tr>\n'
            if typ == 'idurl':
                for i, v in webtraffic.outbox_by_idurl().items():
                    src += '<tr><td><a href="%s">%s</a></td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>\n' % (
                        i, i, v[0], v[3], v[1], v[2])
            elif typ == 'host':
                for i, v in webtraffic.outbox_by_host().items():
                    src += '<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>\n' % (
                        i, v[0], v[3], v[1], v[2])
            elif typ == 'proto':
                for i, v in webtraffic.outbox_by_proto().items():
                    src += '<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>\n' % (
                        i, v[0], v[3], v[1], v[2])
            elif typ == 'type':
                for i, v in webtraffic.outbox_by_type().items():
                    src += '<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>\n' % (
                        i, v[0], v[3], v[1], v[2])
            src += '</table>'
        src += '<hr>\n'
        if direction == 'in':
            src += '<p>total income packets: %d</p>' % webtraffic.inbox_packets_count()
        if direction == 'out':
            src += '<p>total outgoing packets: %d</p>' % webtraffic.outbox_packets_count()
        src += '</body></html>'
        d = {'type': typ, 'dir': direction, 'baseurl': 'http://127.0.0.1:%d%s' % (local_port, request.path)}
        src = src % d
        return html(request, body=src, back='none', home='', reload=1, window_title='Counters')

#------------------------------------------------------------------------------

def InitSettingsTreePages():
    global _SettingsTreeNodesDict
    bpio.log(4, 'webcontrol.init.options')
    SettingsTreeAddComboboxList('desired-suppliers', settings.getECCSuppliersNumbers())
    SettingsTreeAddComboboxList('updates-mode', settings.getUpdatesModeValues())
    SettingsTreeAddComboboxList('general-display-mode', settings.getGeneralDisplayModeValues())
    SettingsTreeAddComboboxList('emergency-first', settings.getEmergencyMethods())
    SettingsTreeAddComboboxList('emergency-second', settings.getEmergencyMethods())

    _SettingsTreeNodesDict = {
    'settings':                 SettingsTreeNode,

    'central-settings':         SettingsTreeNode,
    'desired-suppliers':        SettingsTreeComboboxNode,
    'donated-megabytes':         SettingsTreeDiskSpaceNode,
    'needed-megabytes':         SettingsTreeDiskSpaceNode,
    
    'backup-block-size':        SettingsTreeNumericNonZeroPositiveNode,
    'backup-max-block-size':    SettingsTreeNumericNonZeroPositiveNode,

    'folder':                   SettingsTreeNode,
    'folder-customers':         SettingsTreeDirPathNode,
    'folder-backups':           SettingsTreeDirPathNode,
    'folder-restore':           SettingsTreeDirPathNode,

    'network':                  SettingsTreeNode,
    'network-send-limit':       SettingsTreeNumericPositiveNode,
    'network-receive-limit':    SettingsTreeNumericPositiveNode,

    'other':                    SettingsTreeNode,
    'upnp-enabled':             SettingsTreeYesNoNode,
    'upnp-at-startup':          SettingsTreeYesNoNode,
    'bitcoin':                  SettingsTreeNode,
    'bitcoin-host':             SettingsTreeUStringNode,
    'bitcoin-port':             SettingsTreeNumericPositiveNode,
    'bitcoin-username':         SettingsTreeUStringNode,
    'bitcoin-password':         SettingsTreePasswordNode,
    'bitcoin-server-is-local':  SettingsTreeYesNoNode,
    'bitcoin-config-filename':  SettingsTreeFilePathNode,

    'emergency':                SettingsTreeNode,
    'emergency-first':          SettingsTreeComboboxNode,
    'emergency-second':         SettingsTreeComboboxNode,
    'emergency-email':          SettingsTreeUStringNode,
    'emergency-phone':          SettingsTreeUStringNode,
    'emergency-fax':            SettingsTreeUStringNode,
    'emergency-text':           SettingsTreeTextNode,
    
    'id-server-enable':         SettingsTreeYesNoNode,
    'id-server-host':           SettingsTreeTextNode,
    'id-server-web-port':       SettingsTreeNumericNonZeroPositiveNode,
    'id-server-tcp-port':       SettingsTreeNumericNonZeroPositiveNode,

    # 'updates':                  SettingsTreeNode,
    # 'updates-mode':             SettingsTreeComboboxNode,

    'general':                          SettingsTreeNode,
    'general-desktop-shortcut':         SettingsTreeYesNoNode,
    'general-start-menu-shortcut':      SettingsTreeYesNoNode,
    'general-backups':                  SettingsTreeNumericPositiveNode,
    'general-local-backups-enable':     SettingsTreeYesNoNode,
    'general-wait-suppliers-enable':    SettingsTreeYesNoNode,

    'logs':                     SettingsTreeNode,
    'debug-level':              SettingsTreeNumericNonZeroPositiveNode,
    'stream-enable':            SettingsTreeYesNoNode,
    'stream-port':              SettingsTreeNumericPositiveNode,
    'traffic-enable':           SettingsTreeYesNoNode,
    'traffic-port':             SettingsTreeNumericPositiveNode,
    'memdebug-enable':          SettingsTreeYesNoNode,
    'memdebug-port':            SettingsTreeNumericPositiveNode,
    'memprofile-enable':        SettingsTreeYesNoNode,

    'transport':                SettingsTreeNode,
    'transport-tcp':            SettingsTreeNode,
    'transport-tcp-enable':     SettingsTreeYesNoNode,
    'transport-tcp-port':       SettingsTreeNumericNonZeroPositiveNode,
    'transport-tcp-sending-enable':   SettingsTreeYesNoNode,
    'transport-tcp-receiving-enable': SettingsTreeYesNoNode,
    'transport-udp':            SettingsTreeNode,
    'transport-udp-enable':     SettingsTreeYesNoNode,
    'transport-udp-port':       SettingsTreeNumericPositiveNode,
    'transport-udp-sending-enable':   SettingsTreeYesNoNode,
    'transport-udp-receiving-enable': SettingsTreeYesNoNode,
    'transport-cspace':         SettingsTreeNode,
    'transport-cspace-enable':  SettingsTreeYesNoNode,
    'transport-cspace-key-id':  SettingsTreeUStringNode,
    'transport-cspace-sending-enable':   SettingsTreeYesNoNode,
    'transport-cspace-receiving-enable': SettingsTreeYesNoNode,
    'transport-dhtudp':         SettingsTreeNode,
    'transport-dhtudp-port':    SettingsTreeNumericPositiveNode,
    'transport-dht-port':       SettingsTreeNumericPositiveNode,
    'transport-dhtudp-enable':  SettingsTreeYesNoNode,
    'transport-dhtudp-sending-enable':   SettingsTreeYesNoNode,
    'transport-dhtudp-receiving-enable': SettingsTreeYesNoNode,
    }

class SettingsTreeNode(Page):
    pagename = _PAGE_SETTING_NODE
    # isLeaf = True
    def __init__(self, path):
        Page.__init__(self)
        self.path = path
        self.modifyList = []
        self.modifyTask = None
        self.update()

    def renderPage(self, request):
        bpio.log(6, 'webcontrol.SettingsTreeNode.renderPage [%s] args=%s' % (self.path, str(request.args)))
        src = ''
        if self.exist:
            src += '<h3>%s</h3>\n' % self.label 
            if self.info != '':
                src += '<table width=80%><tr><td align=center>\n'
                src += '<p>%s</p>\n' % self.info
                src += '</td></tr></table><br>\n'
            old_value = self.value
            #bpio.log(6, 'webcontrol.SettingsTreeNode.renderPage before %s: %s' % (self.path, self.value))
            ret = self.body(request)
            #src += self.body(request)
            #bpio.log(6, 'webcontrol.SettingsTreeNode.renderPage after %s: %s' % (self.path, self.value))
            src += html_comment('  path:     %s' % self.path)
            src += html_comment('  label:    %s' % self.label)
            src += html_comment('  info:     %s' % self.info)
            src += html_comment('  value:    %s' % self.value)
            if old_value != self.value:
                src += html_comment('  modified: [%s]->[%s]' % (old_value, self.value))
            if ret.startswith('redirect'):
                ret = ret.split(' ', 1)[1]
                request.redirect(ret)
                request.finish()
                return NOT_DONE_YET
            src += ret
        else:
            src += '<p>This setting is not exist.</p><br>'
            src += html_comment('  incorrect name, this option is not exist')
        d = {}
        header = ''
        if self.exist and len(self.leafs) >= 1:
            header = 'settings'
            try:
                bpio.log(14, 'webcontrol.SettingsTreeNode.renderPage leafs=%s' % (self.leafs))
                for i in range(0, len(self.leafs)):
                    fullname = '.'.join(self.leafs[0:i+1])
                    label = settings.uconfig().get(fullname, 'label')
                    if label is None:
                        label = self.leafs[i]
                    header += ' > ' + label
                    bpio.log(14, 'webcontrol.SettingsTreeNode.renderPage fullname=%s label=%s' % (fullname, label))
            except:
                bpio.exception()
        else:
            header = str(self.label)
        back = ''
        if arg(request, 'back', None) is not None:
            back = arg(request, 'back')
        else:
            back = '/' + _PAGE_CONFIG
        return html(request, body=src, back=back, title=header)

    def requestModify(self, path, value):
        if p2p_connector.A().state in ['TRANSPORTS', 'NETWORK?']:
            self.modifyList.append((path, value))
            if self.modifyTask is None:
                self.modifyTask = reactor.callLater(1, self.modifyWorker)
                bpio.log(4, 'webcontrol.SettingsTreeNode.requestModify (%s) task for %s' % (self.path, path))
        else:
            oldvalue = settings.uconfig(path)
            settings.uconfig().set(path, value)
            settings.uconfig().update()
            self.update()
            self.modified(oldvalue)
            
    def modifyWorker(self):
        #bpio.log(4, 'webcontrol.SettingsTreeNode.modifyWorker(%s)' % self.path)
        if len(self.modifyList) == 0:
            return
        if p2p_connector.A().state in ['TRANSPORTS', 'NETWORK?']:
            self.modifyTask = reactor.callLater(1, self.modifyWorker)
            return
        oldvalue = settings.uconfig(self.path)
        for path, value in self.modifyList:
            settings.uconfig().set(path, value)
        settings.uconfig().update()
        self.update()
        self.modified(oldvalue)
        self.modifyList = []
        self.modifyTask = None

    def update(self):
        self.exist = settings.uconfig().has(self.path)
        self.value = settings.uconfig().data.get(self.path, '')
        self.label = settings.uconfig().labels.get(self.path, '')
        self.info = settings.uconfig().infos.get(self.path, '')
        self.leafs = self.path.split('.')
        self.has_childs = len(settings.uconfig().get_childs(self.path)) > 0

    def modified(self, old_value=None):
        bpio.log(8, 'webcontrol.SettingsTreeNode.modified %s %s' % (self.path, self.value))

        if self.path in (
                'transport.transport-dhtudp.transport-dhtudp-port',
                'transport.transport-dhtudp.transport-dht-port',
                'transport.transport-tcp.transport-tcp-port',
                'transport.transport-tcp.transport-tcp-enable',
                'transport.transport-tcp.transport-tcp-receiving-enable',
                'transport.transport-dhtudp.transport-dhtudp-enable',
                'transport.transport-dhtudp.transport-dhtudp-receiving-enable',
                ):
            network_connector.A('reconnect')
            p2p_connector.A('reconnect')

        elif self.path in (
                'central-settings.desired-suppliers',
                'central-settings.needed-megabytes',
                # 'central-settings.donated-megabytes',
                ):
            fire_hire.ClearLastFireTime()
            backup_monitor.A('restart')

        elif self.path in (
                'central-settings.donated-megabytes',
                ):
            customers_rejector.A('restart')

        elif self.path == 'logs.stream-enable':
            if settings.enableWebStream():
                misc.StartWebStream()
            else:
                misc.StopWebStream()

        elif self.path == 'logs.stream-port':
            misc.StopWebStream()
            if settings.enableWebStream():
                reactor.callLater(0, misc.StartWebStream)

        elif self.path == 'logs.traffic-port':
            misc.StopWebTraffic()
            if settings.enableWebTraffic():
                reactor.callLater(0, misc.StartWebTraffic)

        elif self.path == 'logs.debug-level':
            try:
                bpio.SetDebug(int(self.value))
            except:
                bpio.log(1, 'webcontrol.SettingsTreeNode.modified ERROR wrong value!')

        elif self.path == 'backup.backup-block-size':
            settings.setBackupBlockSize(self.value)

        elif self.path == 'backup.backup-max-block-size':
            settings.setBackupMaxBlockSize(self.value)
            

    def body(self, request):
        global SettingsTreeNodesDict
        bpio.log(12, 'webcontrol.SettingsTreeNode.body path='+self.path)
        if not self.has_childs:
            return ''
        src = '<br>'
        back = arg(request, 'back')
        childs = settings.uconfig().get_childs(self.path).keys()
        bpio.log(12, 'webcontrol.SettingsTreeNode.body childs='+str(childs))
        for path in settings.uconfig().default_order:
            if path.strip() == '':
                continue
            if path not in childs:
                continue
            leafs = path.split('.')
            name = leafs[-1]
            typ = _SettingsTreeNodesDict.get(name, None)
            if typ is None:
                continue
            if len(leafs) == len(self.leafs)+1:
                label = settings.uconfig().labels.get(path, '')
                args = ''
                if back:
                    args += '?back=' + back
                src += '<br><a href="%s%s">%s</a>\n' % ('/' + _PAGE_SETTINGS + '/' + path, args , label)
        return src

class SettingsTreeYesNoNode(SettingsTreeNode):
    def body(self, request):
        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        message = ('', 'info')
        choice = arg(request, 'choice', None)
        if choice is not None and not ReadOnly():
            if choice.lower() != self.value.lower():
                self.requestModify(self.path, choice)
            return 'redirect ' + back

        yes = no = ''
        if self.value.lower() == 'true':
            yes = 'checked'
        else:
            no = 'checked'

        if back:
            back = '&back=' + back

        src = ''
        src += '<br><font size=+2>\n'
        if not ReadOnly():
            src += '<a href="%s?choice=True%s">' % (request.path, back)
        if yes:
            src += '<b>[Yes]</b>'
        else:
            src += ' Yes '
        if not ReadOnly():
            src += '</a>'
        src += '\n&nbsp;&nbsp;&nbsp;\n'
        if not ReadOnly():
            src += '<a href="%s?choice=False%s">' % (request.path, back)
        if no:
            src += '<b>[No]</b>'
        else:
            src += ' No '
        if not ReadOnly():
            src += '</a>'
        src += '\n</font>'
        src += '<br>\n'
        src += html_message(message[0], message[1])
        return src


def SettingsTreeAddComboboxList(name, l):
    global _SettingsTreeComboboxNodeLists
    _SettingsTreeComboboxNodeLists[name] = l

class SettingsTreeComboboxNode(SettingsTreeNode):
    def listitems(self):
        global _SettingsTreeComboboxNodeLists
        combo_list = _SettingsTreeComboboxNodeLists.get(self.leafs[-1], list())
        return map(str, combo_list)
    def body(self, request):
        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        items = self.listitems()
        message = ('', 'info')
        
        choice = arg(request, 'choice', None)
        if choice is not None and not ReadOnly():
            self.requestModify(self.path, choice)
            return 'redirect ' + back

        src = ''
        src += '<br><form action="%s" method="post">\n' % request.path
        src += '<table>\n'
        for i in range(len(items)):
            checked = ''
            if items[i] == self.value or items[i] == self.leafs[-1]:
                checked = 'checked'
            src += '<tr><td><input id="radio%s" type="radio" name="choice" value="%s" %s />' % (
                str(i),
                items[i],
                checked,)
            #src += '<label for="radio%s">  %s</label></p>\n' % (str(i), items[i],)
            src += '</td></tr>\n'
        src += '</table><br>\n'
        src += '<br>'
        src += '<input class="buttonsave" type="submit" name="submit" value=" Save " %s />&nbsp;\n' % ('disabled' if ReadOnly() else '')
        # src += '<input class="buttonreset" type="reset" name="reset" value=" Reset " /><br>\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % arg(request, 'back', '/'+_PAGE_CONFIG)
        src += '</form><br>\n'
        src += html_message(message[0], message[1])
        return src

class SettingsTreeUStringNode(SettingsTreeNode):
    def body(self, request):
        bpio.log(12, 'webcontrol.SettingsTreeUStringNode.body path='+self.path)

        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        message = ('', 'info')
        text = arg(request, 'text', None)
        if text is not None and not ReadOnly():
            self.requestModify(self.path, unicode(text))
            return 'redirect ' + back

        src = ''
        src += '<br><form action="%s" method="post">\n' % request.path
        src += '<input type="text" name="text" value="%s" /><br>\n' % self.value
        src += '<br>'
        src += '<input type="submit" name="submit" value=" Save " %s />&nbsp;\n' % ('disabled' if ReadOnly() else '')
        # src += '<input type="reset" name="reset" value=" Reset " /><br>\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % arg(request, 'back', '/'+_PAGE_CONFIG)
        src += '</form><br>\n'
        src += html_message(message[0], message[1])
        return src

class SettingsTreePasswordNode(SettingsTreeNode):
    def body(self, request):
        bpio.log(12, 'webcontrol.SettingsTreePasswordNode.body path='+self.path)

        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        message = ('', 'info')
        text = arg(request, 'text', None)
        if text is not None and not ReadOnly():
            self.requestModify(self.path, unicode(text))
            return 'redirect ' + back

        src = ''
        src += '<br><form action="%s" method="post">\n' % request.path
        src += '<input type="password" name="text" value="%s" /><br>\n' % self.value
        src += '<br>'
        src += '<input type="submit" name="submit" value=" Save " %s />&nbsp;\n'  % ('disabled' if ReadOnly() else '')
        # src += '<input type="reset" name="reset" value=" Reset " /><br>\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % arg(request, 'back', '/'+_PAGE_CONFIG)
        src += '</form><br>\n'
        src += html_message(message[0], message[1])
        return src

class SettingsTreeNumericNonZeroPositiveNode(SettingsTreeNode):
    def body(self, request):
        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        message = ('', 'info')
        text = arg(request, 'text', None)
        if text is not None:
            try:
                text = int(text)
            except:
                message = ('wrong value. enter positive non zero number.', 'failed')
                text = None
            if text <= 0:
                message = ('wrong value. enter positive non zero number.', 'failed')
                text = None
        if text is not None and not ReadOnly():
            self.requestModify(self.path, unicode(text))
            return 'redirect ' + back

        src = ''
        src += '<br><form action="%s" method="post">\n' % request.path
        src += '<input type="text" name="text" value="%s" />\n' % self.value
        src += '<br><br>\n'
        src += '<input type="submit" name="submit" value=" Save " %s />&nbsp;\n' % ('disabled' if ReadOnly() else '')
        # src += '<input type="reset" name="reset" value=" Reset " />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % back
        src += '</form><br>\n'
        src += html_message(message[0], message[1])
        return src

class SettingsTreeNumericPositiveNode(SettingsTreeNode):
    def body(self, request):
        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        message = ('', 'info')
        text = arg(request, 'text', None)
        if text is not None and not ReadOnly():
            try:
                text = int(text)
            except:
                message = ('wrong value. enter positive number.', 'failed')
                text = None
            if text < 0:
                message = ('wrong value. enter positive number.', 'failed')
                text = None
        if text is not None:
            self.requestModify(self.path, unicode(text))
            return 'redirect ' + back

        src = ''
        src += '<br><form action="%s" method="post">\n' % request.path
        src += '<input type="text" name="text" value="%s" />\n' % self.value
        src += '<br><br>\n'
        src += '<input type="submit" name="submit" value=" Save " %s />&nbsp;\n' % ('disabled' if ReadOnly() else '')
        # src += '<input type="reset" name="reset" value=" Reset " />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % back
        src += '</form><br>\n'
        src += html_message(message[0], message[1])
        return src

class SettingsTreeDirPathNode(SettingsTreeNode):
    def body(self, request):
        src = ''
        msg = None
        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        action = arg(request, 'action')
        opendir = unicode(misc.unpack_url_param(arg(request, 'opendir'), ''))
        if action == 'dirselected' and not ReadOnly():
            if opendir:
#                oldValue = settings.uconfig(self.path)
                self.requestModify(self.path, str(opendir))
                return 'redirect ' + back

        src += '<p>%s</p><br>' % (self.value.strip() or 'not specified')
        
        if msg is not None:
            src += '<br>\n'
            src += html_message(msg[0], msg[1])

        src += '<br><form action="%s" method="post">\n' % request.path
        src += '<input type="hidden" name="action" value="dirselected" />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % arg(request, 'back', '/'+_PAGE_CONFIG)
        src += '<input type="hidden" name="parent" value="%s" />\n' % request.path
        src += '<input type="hidden" name="label" value="Select folder" />\n'
        src += '<input type="hidden" name="showincluded" value="true" />\n'
        src += '<input type="submit" name="opendir" value=" browse " path="%s" %s />\n' % (self.value, ('disabled' if ReadOnly() else ''))
        src += '</form>\n'
        return src

class SettingsTreeFilePathNode(SettingsTreeNode):
    def body(self, request):
        src = ''
        msg = None
        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        action = arg(request, 'action')
        openfile = unicode(misc.unpack_url_param(arg(request, 'openfile'), ''))
        if action == 'fileselected' and not ReadOnly():
            if openfile:
                self.requestModify(self.path, str(openfile))
                return 'redirect ' + back

        src += '<p>%s</p><br>' % (self.value.strip() or 'not specified')
        
        if msg is not None:
            src += '<br>\n'
            src += html_message(msg[0], msg[1])

        src += '<br><form action="%s" method="post">\n' % request.path
        src += '<input type="hidden" name="action" value="fileselected" />\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % arg(request, 'back', '/'+_PAGE_CONFIG)
        src += '<input type="hidden" name="parent" value="%s" />\n' % request.path
        src += '<input type="hidden" name="label" value="Select file" />\n'
        src += '<input type="hidden" name="showincluded" value="true" />\n'
        src += '<input type="submit" name="openfile" value=" browse " path="%s" %s />\n' % (self.value, ('disabled' if ReadOnly() else ''))
        src += '</form>\n'
        return src

class SettingsTreeTextNode(SettingsTreeNode):
    def body(self, request):
        bpio.log(12, 'webcontrol.SettingsTreeTextNode.body path='+self.path)

        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        message = ('', 'info')
        text = arg(request, 'text', None)
        if text is not None and not ReadOnly():
            self.requestModify(self.path, unicode(text))
            return 'redirect ' + back

        src = ''
        src += '<br><form action="%s" method="post">\n' % request.path
        src += '<textarea name="text" rows="5" cols="40">%s</textarea><br>\n' % self.value
        src += '<br>'
        src += '<input type="submit" name="submit" value=" Save " %s />&nbsp;\n' % ('disabled' if ReadOnly() else '')
        # src += '<input type="reset" name="reset" value=" Reset " /><br>\n'
        src += '<input type="hidden" name="back" value="%s" />\n' % arg(request, 'back', '/'+_PAGE_CONFIG)
        src += '</form><br>\n'
        src += html_message(message[0], message[1])
        return src

class SettingsTreeDiskSpaceNode(SettingsTreeNode):
    def body(self, request):
        bpio.log(6, 'webcontrol.SettingsTreeDiskSpaceNode.body args=%s' % str(request.args))

        number = arg(request, 'number', None)
        suffix = arg(request, 'suffix', None)
        back = arg(request, 'back', '/'+_PAGE_CONFIG)
        message = ('', 'info')

        if number is not None and suffix is not None:
            try:
                float(number)
            except:
                message = ('wrong value. enter number.', 'failed')
                number = None
            if float(number) < 0:
                message = ('wrong value. enter positive value.', 'failed')
                number = None
            if not diskspace.SuffixIsCorrect(suffix):
                message = ('wrong suffix. use values from the drop down list only.', 'failed')
                suffix = None

        if number is not None and suffix is not None and not ReadOnly():
            newvalue = number + ' ' + suffix
            newvalue = diskspace.MakeString(number, suffix)
            self.requestModify(self.path, newvalue)
            return 'redirect ' + back

        number_current, suffix_current = diskspace.SplitString(self.value)

        src = ''
        src += '<br><form action="%s" method="post">\n' % request.path
        src += '<input type="text" name="number" value="%s" />\n' % number_current
        src += '<input type="hidden" name="back" value="%s" />\n' % arg(request, 'back', '/'+_PAGE_CONFIG)
        src += '<select name="suffix">\n'
        for suf in diskspace.SuffixLabels():
            if diskspace.SameSuffix(suf, suffix_current):
                src += '<option value="%s" selected >%s</option>\n' % (suf, suf)
            else:
                src += '<option value="%s">%s</option>\n' % (suf, suf)
        src += '</select><br><br>\n'
        src += '<input type="submit" name="submit" value=" Save " %s />&nbsp;\n' % ('disabled' if ReadOnly() else '')
        # src += '<input type="reset" name="reset" value=" Reset " /><br>\n'
        src += '</form><br>\n'
        src += html_message(message[0], message[1])
        #src += html_comment(message[0])
        return src


class SettingsPage(Page):
    pagename = _PAGE_SETTINGS
    def renderPage(self, request):
        global _SettingsTreeNodesDict
        bpio.log(6, 'webcontrol.SettingsPage.renderPage args=%s' % str(request.args))

        src = ''

        for path in settings.uconfig().default_order:
            if path.strip() == '':
                continue
#            if path not in settings.uconfig().public_options:
#                continue
            value = settings.uconfig().data.get(path, '')
            label = settings.uconfig().labels.get(path, '')
            info = settings.uconfig().infos.get(path, '')
            leafs = path.split('.')
            name = leafs[-1]
            typ = _SettingsTreeNodesDict.get(name, None)

            if len(leafs) == 1 and typ is not None:
                src += '<h3><a href="%s">%s</a></h3>\n' % (
                    _PAGE_SETTINGS+'/'+path,
                    label.capitalize())
                
        return html(request, body=src, back='/'+_PAGE_CONFIG, title='settings')

    def getChild(self, path, request):
        global _SettingsTreeNodesDict
        if path == '':
            return self
        leafs = path.split('.')
        name = leafs[-1]
        cls = _SettingsTreeNodesDict.get(name, SettingsTreeNode)
        #TODO
        if isinstance(cls, str):
            return SettingsTreeNode(path)

        return cls(path)


class SettingsListPage(Page):
    pagename = _PAGE_SETTINGS_LIST
    def renderPage(self, request):
        src = ''
        src += '<table>\n'
        for path in settings.uconfig().default_order:
            if path.strip() == '':
                continue
            if path not in settings.uconfig().public_options:
                continue
            value = settings.uconfig().data.get(path, '').replace('\n', ' ')
            label = settings.uconfig().labels.get(path, '')
            info = settings.uconfig().infos.get(path, '')
            src += '<tr>\n'
            src += '<td><a href="%s">%s</a></td>\n' % (_PAGE_SETTINGS+'/'+path, path)
            src += '<td>%s</td>\n' % label
            src += '<td>%s</td>\n' % value
            src += '</tr>\n'
            #src += html_comment('  %s    %s    %s' % (label.ljust(30), value.ljust(20)[:20], path))
            src += html_comment('  %s    %s' % (path.ljust(50), value.ljust(20)))
        src += '</table>\n'
        return html(request, body=src, back='/'+_PAGE_CONFIG, title='settings')
    
#------------------------------------------------------------------------------

