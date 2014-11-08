#!/usr/bin/python
#bpgui.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: bpgui

Here is a child process to drive the GUI part.
This is a simple WEB browser, the HTTP server is started in the main process to show the user interface.

TODO:
Soon we will replace that with user's WEB browser.
"""

import os
import sys
import time
import locale
import platform
import urllib
import urlparse
import imp
import re
import traceback

import wx.html

from twisted.internet import wxreactor
try:
    wxreactor.install()
except:
    pass

from twisted.internet import reactor

from twisted.internet import protocol
from twisted.protocols import basic
from twisted.web import client
from twisted.web import http
from twisted.internet import _threadedselect

try:
    import forms
except:
    sys.path.append(os.path.abspath('..'))
    import forms
    
#------------------------------------------------------------------------------

ShowLogs = False
GUISettingsExists = False

WindowTitle = 'BitPie.NET'
LogWindowTitle = 'Logs'
TrafficWindowTitle = 'Packets'
EventsWindowTitle = 'Events'
StatesWindowTitle = 'State machines'
QueuesWindowTitle = 'Traffic'
CountersWindowTitle = 'Counters'

WindowPos = (1, 1)
WindowSize = (800, 600)
TrafficWindowSize = (800, 150)
EventsWindowSize = (640, 300)
LogWindowSize = (800, 600)
StatesWindowSize = (640, 300)
QueuesWindowSize = (800, 150)
CountersWindowSize = (700, 300)
ToolbarIsVisible = 'False'

SettingsDict = {
    'WindowPos': '%d %d' % WindowPos, 
    'WindowSize': '%d %d' % WindowSize,
    'TrafficWindowSize': '%d %d' % TrafficWindowSize,
    'LogWindowSize': '%d %d' % LogWindowSize,
    'EventsWindowSize': '%d %d' % EventsWindowSize,
    'StatesWindowSize': '%d %d' % StatesWindowSize,
    'QueuesWindowSize': '%d %d' % QueuesWindowSize,
    'CountersWindowSize': '%d %d' % CountersWindowSize,
    'ToolbarIsVisible': '%s' % ToolbarIsVisible,
    }

"""
Here is a labels displayed in the status line of the GUI,
so user can see what is going on at the moment.
When given State Machines changes its state the event is fired and another label is taken from that dictionary
and printed in the GUI.
"""   
StatesDict = {
    'init at startup':          (False, 'beginning'),
    'init local':               (True,  'local settings initialization'),
    'init contacts':            (True,  'contacts initialization'),
    'init connection':          (True,  'preparing connections'),
    'init modules':             (True,  'starting other modules'),
    'init install':             (True,  'preparing install section'),
    'init ready':               (True,  'ready'),
    
    'shutdown at startup':      (True,  'starting'),
    'shutdown init':            (True,  'initializing'),
    'shutdown ready':           (True,  'ready'),
    'shutdown blocked':         (True,  'process blocking operations'),
    'shutdown finished':        (True,  'finished'),
    
    'network at startup':       (True,  'starting connection'),
    'network stun':             (True,  'detecting external IP address'),
    'network upnp':             (True,  'configuring UPnP'),
    'network connected':        (True,  'internet connection is fine'),
    'network disconnected':     (True,  'internet connection is not working'),
    'network network?':         (True,  'checking network interfaces'),
    'network google?':          (True,  'is www.google.com available?'),
    
    'p2p at startup':           (True,  'initial peer-to-peer state'),
    'p2p network?':             (True,  'checking internet connection'),
    'p2p transports':           (True,  'starting network transports'),
    'p2p id server':            (True,  'sending my identity to the identity server'),
    'p2p central server':       (True,  'start connecting to central server'),
    'p2p contacts':             (True,  'sending my identity to other users'),
    'p2p incomming?':           (True,  'waiting response from other users'),
    'p2p connected':            (True,  'connected'),
    'p2p disconnected':         (True,  'disconnected'),
    
    'central at startup':       (True,  'starting central server connection'),
    'central identity':         (True,  'sending my identity to the central server'),
    'central settings':         (True,  'sending my settings to the central server'),
    'central request settings': (True,  'request my settings from the central server'),
    'central suppliers':        (True,  'requesting suppliers from the central server'),
    'central connected':        (True,  'connected to the central server'),
    'central disconnected':     (True,  'disconnected from the central server'),
    'central only id':          (True,  'got response from the central server'),

    'monitor ready':            (True,  'backups ready'),      
    'monitor restart':          (True,  'checking backups'),  
    'monitor ping':             (True,  'ping suppliers'),    
    'monitor list files':       (True,  'requesting list of my files from suppliers'),      
    'monitor list backups':     (True,  'prepare list of backups'),      
    'monitor rebuilding':       (True,  'rebuilding backups'),      
    'monitor fire hire':        (True,  'checking suppliers availability'),      
    
    'rebuild next backup':      (True,  'checking next backups'),      
    'rebuild next block':       (True,  'checking next block'),      
    'rebuild rebuilding':       (True,  'rebuilding block'),      
    'rebuild done':             (True,  'rebuilding done'),      
    'rebuild stopped':          (True,  'rebuilding stopped'),      

    'firehire ready':           (True,  'suppliers ready'),      
    'firehire call all':        (True,  'ping all supliers'),      
    'firehire lost supplier':   (True,  'checking suppliers availability'),      
    'firehire fire him!':       (True,  'dismissal of supplier'),      
    'firehire new supplier?':   (True,  'checking new supplier'),   
    
    'datasend at startup':      (True,  'starting sending machine'),
    'datasend ready':           (True,  'ready to send the data'),
    'datasend scan blocks':     (True,  'prepare to send missing blocks'),
    'datasend sending':         (True,  'sending data'),   

    'install at startup':       (True,  ' '),
    'install what to do?':      (True,  ' '),
    'install input name':       (True,  ' '),
    'install load key':         (True,  ' '),
    'install register':         (True,  ' '),
    'install authorized':       (True,  ' '),
    'install central':          (True,  ' '),
    'install contacts':         (True,  ' '),
    'install recover':          (True,  ' '),
    'install done':             (True,  ' '),
    
    'id register ready':        (True,  ' '),
    'id register user name':    (True,  ' '),
    'id register local ip':     (True,  ' '),
    'id register external ip':  (True,  ' '),
    'id register central id':   (True,  ' '),
    'id register send my id':   (True,  ' '),
    'id register request my id':(True,  ' '),
    'id register registered':   (True,  ' '),
    
    'id restore ready':         (True,  ' '),
    'id restore central id':    (True,  ' '),
    'id restore my id':         (True,  ' '),
    'id restore work':          (True,  ' '),
    'id restore done':          (True,  ' '),
}

NO_IMAGE = 'icons/delete01.png'

#------------------------------------------------------------------------------

def sharedPath(filename, subdir='logs'):
    return os.path.join(os.path.expanduser('~'), '.bitpie', subdir, filename)


def WriteText(txt, filename='bpgui.log', mode='a', sharedLocation=True, subdir='logs'):
#    global ShowLogs
#    if ShowLogs and filename not in ['view-html.log', 'view-form.log',]:
#        sys.stdout.write(txt)
#        return
    filename_ = filename
    if sharedLocation:
        filename_ = sharedPath(filename, subdir)
    fout = open(filename_, mode)
    fout.write(txt)
    fout.close()


def WriteException(filename='view.log', mode='a', sharedLocation=True, subdir='logs'):
    maxTBlevel=100
    cla, exc, trbk = sys.exc_info()
    try:
        excArgs = str(exc.__dict__["args"])
    except KeyError:
        excArgs = "<no args>"
    excTb = traceback.format_tb(trbk, maxTBlevel)
    WriteText('Exception: <'+unicode(exc, errors='replace')+'>   args: ' + excArgs, filename, mode, sharedLocation, subdir)
    for s in excTb:
        WriteText(s, filename, mode, sharedLocation, subdir)


def main_is_frozen():
    return (hasattr(sys, "frozen") or # new py2exe
            hasattr(sys, "importers") or# old py2exe
            imp.is_frozen("__main__")) # tools/freeze


def getExecutableDir():
    if main_is_frozen():
        path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        path = os.path.dirname(os.path.abspath(sys.argv[0]))
    return unicode(path)


def about():
    try:
        vernum = open('version').read()
    except:
        vernum = '0'
    return '''<html>
<b>BitPie.NET<b> is a peer-to-peer backup utility.<br>
Current release is %s.<br>
</html>''' % (vernum,)

#------------------------------------------------------------------------------ 


def _parse(url, defaultPort=None):
    """
    Split the given URL into the scheme, host, port, and path.

    @type url: C{str}
    @param url: An URL to parse.

    @type defaultPort: C{int} or C{None}
    @param defaultPort: An alternate value to use as the port if the URL does
    not include one.

    @return: A four-tuple of the scheme, host, port, and path of the URL.  All
    of these are C{str} instances except for port, which is an C{int}.
    """
    url = url.strip()
    parsed = http.urlparse(url)
    scheme = parsed[0]
    path = urlparse.urlunparse(('', '') + parsed[2:])
    if defaultPort is None:
        if scheme == 'https':
            defaultPort = 443
        else:
            defaultPort = 80
    host, port = parsed[1], defaultPort
    if ':' in host:
        host, port = host.split(':')
        try:
            port = int(port)
        except ValueError:
            port = defaultPort
    if path == '':
        path = '/'
    return scheme, host, port, path

def load_gui_settings():
    global SettingsDict
    if not os.path.exists(sharedPath('guisettings', 'metadata')):
        return False
    try:
        fin = open(sharedPath('guisettings', 'metadata'))
        src = fin.read()
        fin.close()
        for line in src.split('\n'):
            words = line.split(' ')
            if len(words) < 2:
                continue
            SettingsDict[words[0]] = ' '.join(words[1:])
        return True
    except:
        WriteException()
        return False

def save_gui_settings():
    global SettingsDict
    src = ''
    for k in sorted(SettingsDict.keys()):
        src += k + ' ' + str(SettingsDict[k]) + '\n'
    try:
        fout = open(sharedPath('guisettings', 'metadata'), 'w')
        fout.write(src)
        fout.flush()
        os.fsync(fout)
        fout.close()
    except:
        WriteException()

def read_setting(key, typ='str', default=None):
    global SettingsDict
    data = SettingsDict.get(key, None)
    if data is None:
        return default
    if typ == 'str':
        return data
    elif typ == 'int':
        try:
            return int(data)
        except:
            return default
    elif typ == 'size':
        try:
            w, h = data.split(' ')
            return (int(w), int(h))
        except:
            return default
    elif typ == 'pos':
        try:
            w, h = data.split(' ')
            w = int(w)
            h = int(h)
        except:
            return default
        return (w if w >= 0 else 0, h if h >= 0 else 0)
    return default

def write_setting(key, value, typ='str'):
    global SettingsDict
    data = value
    if typ in ['size', 'pos']:
        data = '%d %d' % (value[0], value[1])
    elif typ == 'int':
        data = str(value)
    SettingsDict[key] = data

#------------------------------------------------------------------------------ 

def openWxImage(path, type=wx.BITMAP_TYPE_PNG):
    if not os.path.isfile(path):
        if not os.path.isfile(os.path.join('..', path)):
            if not os.path.isfile(NO_IMAGE):
                return None
            else:
                path = NO_IMAGE
        else:
            path = os.path.join('..', path)
    try:
        return wx.Image(path, type).ConvertToBitmap()
    except:
        WriteException()
    return None

def openWxIcon(path, type=wx.BITMAP_TYPE_ICO):
    if not os.path.isfile(path):
        if not os.path.isfile(os.path.join('..', path)):
            if not os.path.isfile(NO_IMAGE):
                return None
            else:
                path = NO_IMAGE
        else:
            path = os.path.join('..', path)
    try:
        return wx.Icon(path, type)
    except:
        WriteException()
    return None
    
#------------------------------------------------------------------------------

def unicode_to_str_safe(unicode_string, encodings=None):
    try:
        return str(unicode_string) # .decode('utf-8')
    except:
        try:
            return unicode(unicode_string).encode(locale.getpreferredencoding(), errors='replace')
        except:
            pass
    if encodings is None:
        encodings = [locale.getpreferredencoding(),] #  'utf-8' 
    output = ''
    for i in xrange(len(unicode_string)):
        unicode_char = unicode_string[i]
        char = '?'
        try:
            char = unicode_char.encode(encodings[0])
            # print char, encodings[0]
        except:
            for encoding in encodings:
                try:
                    char = unicode_char.encode(encoding)
                    # print char, encoding
                    break
                except:
                    pass
        output += char
    return output

#------------------------------------------------------------------------------ 

class MyTagHandler(wx.html.HtmlWinTagHandler):
    def __init__(self):
        wx.html.HtmlWinTagHandler.__init__(self)
    def GetSupportedTags(self):
        return "A"
    def HandleTag(self, tag):
        oldlnk = self.GetParser().GetLink()
        oldclr = self.GetParser().GetActualColor()
        oldund = self.GetParser().GetFontUnderlined()
        href = str(tag.GetParam("HREF"))
        target = ''
        if tag.HasParam("TARGET"):
            target = tag.GetParam("TARGET")
        self.GetParser().SetActualColor(self.GetParser().GetLinkColor())
        self.GetParser().GetContainer().InsertCell(wx.html.HtmlColourCell(self.GetParser().GetLinkColor()))
        self.GetParser().SetFontUnderlined(False)
        self.GetParser().GetContainer().InsertCell(wx.html.HtmlFontCell(self.GetParser().CreateCurrentFont()))
        # TODO: need to handle target argument too, but this fails:
        # newlnk = wx.html.HtmlLinkInfo(href, target=target)
        # self.GetParser().SetLink(newlnk)
        self.GetParser().SetLink(href)
        self.ParseInner(tag)
        self.GetParser().SetLink(oldlnk.GetHref())
        self.GetParser().SetFontUnderlined(oldund)
        self.GetParser().GetContainer().InsertCell(wx.html.HtmlFontCell(self.GetParser().CreateCurrentFont()))
        self.GetParser().SetActualColor(oldclr)
        self.GetParser().GetContainer().InsertCell(wx.html.HtmlColourCell(oldclr))
        return True
#wx.html.HtmlWinParser_AddTagHandler(MyTagHandler)

#------------------------------------------------------------------------------

class MyBusyInfoFrame(wx.Frame):
    def __init__(self, parent, message):
        wx.Frame.__init__(self,
                          parent,
                          wx.ID_ANY,
                          "Busy",
                          wx.DefaultPosition,
                          wx.DefaultSize,
                          wx.SIMPLE_BORDER | wx.FRAME_TOOL_WINDOW | wx.FRAME_FLOAT_ON_PARENT
                          )
        panel = wx.Panel(self)
        panel.SetCursor(wx.HOURGLASS_CURSOR)
        self.text = wx.StaticText(panel, wx.ID_ANY, message)
        self.text.SetCursor(wx.HOURGLASS_CURSOR)
        sizeText = self.text.GetBestSize()
        self.SetClientSize((max(sizeText.x, 150), max(sizeText.y, 100)))
        panel.SetSize(self.GetClientSize())
        self.text.Centre(wx.BOTH)
        self.Centre(wx.BOTH)

class MyBusyInfo(object):
    def __init__(self, message, parent=None):
        self._infoFrame = MyBusyInfoFrame(parent, message)
        self._infoFrame.Show(True)
        self._infoFrame.Refresh()
        self._infoFrame.Update()
    def __del__(self):
        self._infoFrame.Show(False)
        self._infoFrame.Destroy()
    def set_text(self, txt):
        self._infoFrame.text.SetLabel(txt)
        self._infoFrame.Refresh()
        self._infoFrame.Update()

#------------------------------------------------------------------------------
        
class MyHtmlWindow(wx.html.HtmlWindow):
    def __init__(self, parent, enable_logs=False, is_child_window=False, base_addr='', base_port=0):
        # BufferedCanvas.__init__(self,parent,-1)
        wx.html.HtmlWindow.__init__(self, parent, -1,
            style=wx.NO_FULL_REPAINT_ON_RESIZE | wx.BORDER_STATIC )
        self.current_url = ''
        self.base_addr = base_addr
        self.base_port = base_port
        self.no_repaint = False
        self.opening = False
        self.enable_logs = enable_logs
        self.busyInfo = None
        self.is_child = is_child_window
        self.Bind(forms.form.EVT_FORM_SUBMIT, self.OnFormSubmit)
        # if "gtk2" in wx.PlatformInfo:
        #     self.SetStandardFonts()
#            _FONT_SIZES = [7, 8, 10, 12, 16, 22, 30]
#            _FONT_SIZES = [7, 9, 12, 14, 18, 28, 38]
#            self.SetFonts("arial", "courier new", _FONT_SIZES)
        if "wxMSW" in wx.PlatformInfo:
#            # Original font sizes are [7, 8, 10, 12, 16, 22, 30]
            _FONT_SIZES = [5, 6,  8, 10, 14, 20, 24]
            self.SetFonts("Microsoft Sans Serif", "Courier New", _FONT_SIZES)
        self.SetBorders(5)
        self.SetDoubleBuffered(True)
        self.clickedTime = None
        self.clickWaitTask = None
        self.refreshTask = None
        # self.buttons = {0:[], 1:[]}
        # self.current_buttons = 0
        self.buttons = []
    
#    def OnPaint(self, e):
#        WriteText('OnPaint %s\n' % str(e))
#        wx.html.HtmlWindow.OnPaint(e)
    
    def RegisterButton(self, obj):
        # print 'RegisterButton', obj
        # self.buttons[self.current_buttons].append(obj)
        self.buttons.append(obj)
        
    def ShowButtons(self):
        # print 'ShowButtons.1'
        # self.buttons_ = []
        # for b in self.buttons[self.current_buttons]:
        for b in self.buttons:
            # b.Raise()
            b.Show(True)
        self.buttons = []
        # self.buttons[self.current_buttons] = []
        # self.current_buttons = 1 - self.current_buttons
        # print 'ShowButtons.2'
        
    def UnRegisterButtons(self):
        # print 'UnRegisterButtons'
        # self.buttons = []
        # for b in self.buttons:
        #     self.buttons_.append(b) 
        # self.buttons[1 - self.current_buttons] = []
        # print 'UnRegisterButtons.end'
        pass
    
    def BlockRepaint(self):
        self.no_repaint = True

    def UnblockRepaint(self):
        self.no_repaint = False

    def ResolveURL(self, url, noargs=False):
        parts = list(urlparse.urlsplit(str(url), 'http'))
        parts[0] = 'http'
        if parts[1] == '':
            parts[1] = self.base_addr+':'+str(self.base_port)
        if parts[2] == '':
            partsCurrent = urlparse.urlsplit(self.current_url, 'http')
            parts[2] = partsCurrent[2]
        if noargs:
            parts[3] = ''
            parts[4] = ''
        ret = urlparse.urlunsplit(parts)
        # WriteText('ResolveURL: %s -> %s current=%s\n' % (url, ret, self.current_url))
        return ret

    def SaveCurrentURL(self, page, factory):
        self.current_url = factory.url
        #WriteText('SaveCurrentURL: %s\n' % self.current_url)
        return page

    def GetPageTwisted(self, url, method='GET', postdata=None, headers=None):
        # WriteText('GetPageTwisted %s\n' % url)
        try:
            scheme, hostport, path, query, fragment = urlparse.urlsplit(url)
            host,x,port = hostport.partition(':')
            port = int(port)
        except:
            WriteException()
        factory = client.HTTPClientFactory(url, method, postdata, headers)
        reactor.connectTCP(host, port, factory)
        factory.deferred.addCallback(self.SaveCurrentURL, factory)
        # WriteText('GetPageTwisted %s:%d path=%s postdata=%s\n' % (host, port, path, str(postdata)))
        return factory.deferred

    def DownloadURL(self, url):
        # WriteText('DownloadURL: %s\n' % url)
        return self.GetPageTwisted(url)

    def DownloadForm(self, url, method, args):
        # WriteText('DownloadForm: %s method=%s args=%s\n' % (url, method, str(args)))
        if method == 'POST':
            data = urllib.urlencode(args)
            headers = {}
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            return self.GetPageTwisted(
                                  str(url),
                                  method=method,
                                  postdata=data,
                                  headers=headers,)
        elif method == 'GET':
            u = str(url+'?'+urllib.urlencode(args))
            return self.GetPageTwisted(u)
        else:
            WriteText('DownloadForm ERROR, unsupported method: %s\n' % method)

    def OpenURL(self, url_, save_scroll_pos=True):
        def callback(src, url, save_scroll_pos):
            tm = time.time()
            # WriteText('OpenURL.callback %s \n' % time.time())
            if self.enable_logs:
                WriteText(src, 'page.html', mode='w')
            self.UnRegisterClick()
            pos = self.GetViewStart()[1]
            self.Freeze()
            self.UnRegisterButtons()
            # WriteText('SetPage begin %s \n' % str(time.time() - tm))
            try:
                self.SetPage(src)
            except:
                u = unicode(src, errors='ignore')
                self.SetPage(unicode_to_str_safe(u))
            # WriteText('SetPage end %s\n' % str(time.time() - tm))
            self.ShowButtons()
            if save_scroll_pos:
                self.Scroll(0, pos)
            self.Thaw()
            self.CheckRefresh(src)
            # WriteText('OpenURL finish %s\n' % str(time.time() - tm))
            self.opening = False
            return src
        def errback(err):
            self.UnRegisterClick()
            if not self.is_child:
                src = '<html><center><br><br>\n'
                src += '<h1>BitPie.NET is not working<br>\nor some error happens in the main process</h1><br><br>\n'
                src += 'Go <a href="%s">Back</a>\n' % self.current_url
                src += 'or just close this window.<br><br><br>\n'
                src += '<font size=-2>\n'
                src += '<table><tr><td>\n'
                src += '<div align=left>\n'
                src += 'Error message is:<br>\n'
                src += err.getErrorMessage()
                src += '<br><br>\n'
                exc = ''
                if exc:
                    src += exc.replace('\n', '<br>\n')
                src += 'If you wish to participate in the development of the project,<br>'
                src += 'refer to Veselin Penev and <a href="/devreport">describe your situation</a>,'
                src += 'which led to this error.<br>'
                src += '</div>\n'
                src += '</td></tr></table>\n'
                src += '</font>\n'
                src += '</center></html>\n'
                self.UnRegisterButtons()
                self.SetPage(src)
                self.ShowButtons()
            self.opening = False
            return err
        if self.opening:
            return
        self.opening = True
        url = self.ResolveURL(url_)
        # WriteText('OpenURL url=%s\n' % url) 
        d = self.DownloadURL(url)
        d.addCallback(callback, url, save_scroll_pos)
        d.addErrback(errback)
        return d

#     def UpdateAndOpenURL(self, url):
#         d = self.DownloadURL(url)
#         d.addCallback(callback, url, save_scroll_pos)
#         d.addErrback(errback)

    def OnFormSubmit(self, evt, save_scroll_pos=True):
        if self.no_repaint:
            return
        def callback(src):
            if self.enable_logs:
                WriteText(src, 'form.html', mode='w')
            self.UnRegisterClick()
            pos = self.GetViewStart()[1]
            self.Freeze()
            self.UnRegisterButtons()
            self.SetPage(src)
            self.ShowButtons()
            if save_scroll_pos:
                self.Scroll(0, pos)
            self.Thaw()
            #self.CheckRefresh(src)
            return src
        def errback(err):
            if self.enable_logs:
                WriteText('OnFormSubmit.errback: %s\n' % str(err))
            self.UnRegisterClick()
            src = '<html><center><br><br><br><br>\n'
            src += 'BitPie.NET is not working or some errors happens.<br><br>\n'
            src += 'Error message is:<br>\n'
            src += err.getErrorMessage()
            src += '<br><br>\n'
            src += 'You can try to go <a href="%s">Back</a>\n' % self.current_url
            src += 'or just close this window.\n'
            src += '</center></html>\n'
            self.UnRegisterButtons()
            self.SetPage(src)
            self.ShowButtons()
            return err
        if not self.RegisterClick(evt):
            return
        url = self.ResolveURL(evt.form.action)
        # WriteText('OnFormSubmit url=%s, args=%s\n' % (url, str(evt.args)))
        d = self.DownloadForm(url, evt.form.method, evt.args)
        d.addCallback(callback)
        d.addErrback(errback)

    def OnLinkClicked(self, linkinfo):
        if self.no_repaint:
            return
        if isinstance(linkinfo, str):
            url = linkinfo
            target = ''
        else:
            url = linkinfo.GetHref()
            target = linkinfo.GetTarget()
        if target == '_blank':
            wx.LaunchDefaultBrowser(url)
            return
        elif target == '_opendir':
            return self.OnOpenDir(linkinfo)
        if not self.RegisterClick(linkinfo):
            return
        self.OpenURL(url)

    def RegisterClick(self, clickinfo):
        if clickinfo is None:
            self.UnRegisterClick()
            return True
        if self.clickedTime is not None:
            return False
        self.clickedTime = time.time()
        self.clickWaitTask = reactor.callLater(1, self.ClickTimeout, clickinfo)
        return True

    def UnRegisterClick(self):
        if self.clickWaitTask is not None and self.clickWaitTask.active():
            self.clickWaitTask.cancel()
        self.clickWaitTask = None
        self.clickedTime = None
        if self.refreshTask is not None and self.refreshTask.active():
            self.refreshTask.cancel()
        self.refreshTask = None
        if not self.Enabled:
            self.Enable()
            if self.busyInfo is not None:
                del self.busyInfo
                self.busyInfo = None

    def OnOpenDir(self, linkinfo):
        url = linkinfo.GetHref()
        target = linkinfo.GetTarget()
        parts = list(urlparse.urlsplit(str(url), 'http'))
        args = {}
        for arg in parts[3].split('&'):
            k, v = arg.split('=')
            args[k] = urllib.unquote(v)
        self.BlockRepaint()
        dialog = wx.DirDialog(self, args.get('label', "Choose a directory"),
            style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON | wx.DD_DIR_MUST_EXIST,
            defaultPath = args.get('path', os.path.expanduser('~')))
        if dialog.ShowModal() == wx.ID_OK:
            Path = dialog.GetPath()
        else:
            Path = None
        dialog.Destroy()
        self.UnblockRepaint()
        if Path is not None:
            args['opendir'] = Path
            query = urllib.urlencode(args)
            WriteText(query+'\n')
            resp = urlparse.urlunsplit((parts[0], parts[1], parts[2], query, parts[4]))
            WriteText(resp+'\n')
            self.OpenURL(resp)

    def ClickTimeout(self, clickinfo):
        self.Disable()
        self.busyInfo = MyBusyInfo('busy', self)
        self.clickWaitTask = reactor.callLater(60, self.ClickFailed, clickinfo)

    def ClickFailed(self, clickinfo):
        self.UnRegisterClick()

    def RefreshTimer(self, url):
        if self.no_repaint:
            return
        if self.RegisterClick(None):
            self.OpenURL(url)

    def CheckRefresh(self, src):
        regexp = "^\<meta.+?http\-equiv.+?refresh.+?content.*?([0-9\.]+).*?\>$"
        search_reload = re.search(regexp, src, re.MULTILINE)
        if search_reload is None:
            return
        try:
            refresh_time = float(search_reload.group(1))
        except:
            return
        self.refreshTask = reactor.callLater(refresh_time, self.RefreshTimer, self.current_url)

    def ScrollWindow(self, dx, dy, rect):
        wx.html.HtmlWindow.ScrollWindow(self, dx, dy, rect)

    def OnCommandUpdate(self):
        if self.no_repaint:
            return
        if self.RegisterClick(None):
            # WriteText( 'OnCommandUpdate %s %s\n' % (self.current_url, self.base_addr))
            if self.current_url != '':
                url = self.ResolveURL(self.current_url, True)
            else:
                url = self.ResolveURL(self.base_addr+':'+str(self.base_port), True)
            self.OpenURL(url)

    def OnCommandOpen(self, url):
        if self.no_repaint:
            return
        if self.RegisterClick(None):
            self.OpenURL(url)

#------------------------------------------------------------------------------

class MyLogWindow(wx.Frame):
    def __init__(self, parent, base_addr, base_port):
        wx.Frame.__init__(self,
                          parent,
                          title=LogWindowTitle,
                          size=read_setting('LogWindowSize', 'size', LogWindowSize),
                          style=wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX|wx.CLIP_CHILDREN,)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.html_log = MyHtmlWindow(self, base_addr=base_addr, base_port=base_port)
        self.html_log.SetRelatedFrame(self, '%s')
        self.SetTitle(LogWindowTitle)
        if os.path.isfile('icons/logs.ico'):
            icon = openWxIcon('icons/logs.ico')
        else:
            icon = openWxIcon('icons/tray_icon.ico')
        self.SetIcon(icon)
        
    def OnClose(self, event):
        write_setting('LogWindowSize', self.GetSizeTuple(), 'size')
        self.Hide()

#------------------------------------------------------------------------------ 

class MyTrafficWindow(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self,
                          parent,
                          size=read_setting('TrafficWindowSize', 'size', TrafficWindowSize),
                          title=TrafficWindowTitle,
                          style=wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX|wx.CLIP_CHILDREN,)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.cb = wx.CheckBox(self, label='disable auto scrolling?')
        self.cb.SetValue(False)
        self.lst = wx.ListCtrl(self, size=(600,-1), style=wx.LC_REPORT|wx.BORDER_SUNKEN)
        self.lst.InsertColumn(0, 'time')
        self.lst.InsertColumn(1, 'out')
        self.lst.InsertColumn(2, 'in')
        self.lst.InsertColumn(3, 'address') 
        self.lst.InsertColumn(4, 'length', wx.LIST_FORMAT_RIGHT) 
        self.lst.InsertColumn(5, 'id')
        self.lst.InsertColumn(6, 'status')
        self.lst.SetColumnWidth(0, read_setting('TrafficWindowColumnWidth0', 'int', 70))
        self.lst.SetColumnWidth(1, read_setting('TrafficWindowColumnWidth1', 'int', 200))
        self.lst.SetColumnWidth(2, read_setting('TrafficWindowColumnWidth2', 'int', 200))
        self.lst.SetColumnWidth(3, read_setting('TrafficWindowColumnWidth3', 'int', 170))
        self.lst.SetColumnWidth(4, read_setting('TrafficWindowColumnWidth4', 'int', 50))
        self.lst.SetColumnWidth(5, read_setting('TrafficWindowColumnWidth5', 'int', 300))
        self.lst.SetColumnWidth(6, read_setting('TrafficWindowColumnWidth6', 'int', 200))
        self.index = 0
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.cb, 0)
        vbox.Add(self.lst, 1, wx.EXPAND)
        self.SetSizer(vbox)
        if os.path.isfile('icons/history.ico'):
            icon = openWxIcon('icons/history.ico')
        else:
            icon = openWxIcon('icons/tray_icon.ico')
        self.SetIcon(icon)

    def OnClose(self, event):
        write_setting('TrafficWindowSize', self.GetSizeTuple(), 'size')
        for col in range(self.lst.GetColumnCount()):
            write_setting('TrafficWindowColumnWidth%d' % col, self.lst.GetColumnWidth(col), 'int')
        self.Hide()

    def add(self, parts):
        try:
            s = '[%s] %s %s' % (parts[2], parts[3], parts[4])
            addr = parts[5].strip('() ')
            length = parts[7]
            id = parts[6]
            status = parts[8]
            message = parts[9].replace('"None"', '').replace('_', ' ').strip('"')
        except:
            WriteException()
        c = 'black'
        i = 0
        if parts[1] == 'in':
            i = 2
            c = 'forest green'
            if status == 'failed':
                c = 'purple'
        elif parts[1] == 'out':
            i = 1
            c = 'blue'
            if status == 'failed':
                c = 'red'
        if parts[2].lower() == 'fail':
            c = 'red'
        # pos = self.lst.GetScrollPos(wx.VERTICAL)
        
        list_total  = self.lst.GetItemCount()
        list_top    = self.lst.GetTopItem()
        list_pp     = self.lst.GetCountPerPage()
        list_bottom = min(list_top + list_pp, list_total - 1)
        
        # WriteText('pos: %s, items: %s\n' % (str(pos), str(self.lst.GetItemCount())))
        self.lst.InsertStringItem(0, '')
        self.lst.SetStringItem(0, 0, time.strftime('%H:%M:%S'))
        self.lst.SetStringItem(0, i, s)
        self.lst.SetStringItem(0, 3, addr)
        self.lst.SetStringItem(0, 4, length)
        self.lst.SetStringItem(0, 5, id)
        self.lst.SetStringItem(0, 6, message)
        self.lst.SetItemTextColour(0, c)
        while self.lst.GetItemCount() > 1000:
            self.lst.DeleteItem(self.lst.GetItemCount()-1)
            # pos -= 1
            
        if self.cb.IsChecked():
            self.lst.EnsureVisible(list_bottom)

#------------------------------------------------------------------------------ 

class MyEventInfoDialog(wx.Dialog):
    def __init__(self, eTime, eModule, eMessage, eBody):
        wx.Dialog.__init__(self, None, -1, eModule.capitalize() + " event", size=(400,300),
            style = wx.SIMPLE_BORDER | wx.FRAME_TOOL_WINDOW | wx.FRAME_FLOAT_ON_PARENT,)

        panel = wx.Panel(self)
        box = wx.BoxSizer(wx.VERTICAL)

        hwin = wx.html.HtmlWindow(panel, -1, size=(300,100))
        box.Add(hwin, 1, wx.ALL, 10)

        btn1 = wx.Button(panel, wx.ID_CLOSE, "Close")
        btn1.Bind(wx.EVT_BUTTON, lambda x: self.Destroy())
        box.Add(btn1, 1, wx.ALL, 10)

        panel.SetSizer(box)
        panel.Layout()

        WriteText('event %s %s\n' % (eModule, eMessage))

        src = '<br><br><br><br>'
        src += '<center>'
        src += '<b>%s</b><br>\n' % eMessage
        src += '</center>'

        hwin.SetPage(src)
        self.CentreOnParent(wx.BOTH)
        self.SetFocus()

class MyEventsWindow(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self,
                          parent,
                          size=read_setting('EventsWindowSize', 'size', EventsWindowSize),
                          title=EventsWindowTitle,
                          style=wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX|wx.CLIP_CHILDREN,)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        if os.path.isfile('icons/event.ico'):
            icon = openWxIcon('icons/event.ico')
        else:
            icon = openWxIcon('icons/tray_icon.ico')
        self.SetIcon(icon)
        self.lst = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.lst.InsertColumn(0, 'Time', )
        self.lst.InsertColumn(1, 'Message', width=300)
        self.lst.InsertColumn(2, 'Module', width=100)
        self.lst.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivated)
        self.id = -sys.maxint
        self.eventsDataDict = {}
        self.lst.Bind(wx.EVT_LIST_DELETE_ITEM, self.OnDeleteItem)
        self.lst.Bind(wx.EVT_LIST_DELETE_ALL_ITEMS, self.OnDeleteAllItems)

    def add(self, txt):
        try:
            typ = txt.split(' ')[1]
            msg = re.search('\[\[\[(.*)\]\]\]', txt).group(1)
            modul = re.search('\(\(\((.*)\)\)\)', txt).group(1)
            body = re.search('\]\]\](.*)', txt+'\n', re.S).group(1)
        except:
            WriteException()
            return
        pos = self.lst.InsertStringItem(0, time.strftime('%H:%M:%S'))
        self.lst.SetStringItem(pos, 1, msg)
        self.lst.SetStringItem(pos, 2, modul)
        self.SetPyData(pos, body)
        while self.lst.GetItemCount() > 1000:
            self.lst.DeleteItem(self.lst.GetItemCount()-1)
#        if typ == 'notify':
#            self.openEvent(pos)

    def openEvent(self, index):
        try:
            eTime = self.lst.GetItem(index, 0).GetText()
            eMessage = self.lst.GetItem(index, 1).GetText()
            eModule = self.lst.GetItem(index, 2).GetText()
            eBody = self.eventsDataDict.get(self.lst.GetItemData(index))
            dlg = MyEventInfoDialog(eTime, eModule, eMessage, eBody)
            dlg.Show(True)
        except:
            WriteException()

    def SetPyData(self, item, data):
        self.eventsDataDict[self.id] = data
        self.lst.SetItemData(item, self.id)
        self.id += 1

    def OnClose(self, event):
        write_setting('EventsWindowSize', self.GetSizeTuple(), 'size')
        self.Hide()

    def OnActivated(self, event):
        index = event.GetIndex()
        self.openEvent(index)

    def OnDeleteItem(self, event):
        try:
            del self.eventsDataDict[event.Data]
        except KeyError:
            WriteException()
        event.Skip()

    def OnDeleteAllItems(self, event):
        self.eventsDataDict.clear()
        event.Skip()

#------------------------------------------------------------------------------ 

class MyStatesWindow(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self,
                          parent,
                          size=read_setting('StatesWindowSize', 'size', StatesWindowSize),
                          title=StatesWindowTitle,
                          style=wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX|wx.CLIP_CHILDREN,)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        if os.path.isfile('icons/states.ico'):
            icon = openWxIcon('icons/states.ico')
        else:
            icon = openWxIcon('icons/tray_icon.ico')
        self.SetIcon(icon)
        self.lst = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.lst.InsertColumn(0, 'ID', )
        self.lst.InsertColumn(1, 'Name', width=300)
        self.lst.InsertColumn(2, 'State', width=200)
        #self.lst.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivated)
        #self.indexDict = {}

    def OnClose(self, event):
        write_setting('StatesWindowSize', self.GetSizeTuple(), 'size')
        self.Hide()
        
    def update(self, cmd):
        words = cmd.split(' ')
        if len(words) >= 4:
            index = words[1]
            id = words[2]
            name = words[3]
            state = ''
        if name.endswith('_status'):
            return
        if len(words) >= 5:
            state = words[4]
        found = False
        for i in range(self.lst.GetItemCount()):
            _index = self.lst.GetItem(i, 0).GetText() 
            if index == _index:
                if state == '':
                    self.lst.DeleteItem(i)
                    found = True
                    break
                else:
                    self.lst.SetStringItem(i, 2, state)
                    found = True
                    break
        if not found:
            self.lst.Append((index, id, state)) 

#------------------------------------------------------------------------------ 

class MyQueuesWindow(wx.Frame):
    def __init__(self, parent, url, base_addr, base_port):
        wx.Frame.__init__(self,
                          parent,
                          size=read_setting('QueuesWindowSize', 'size', QueuesWindowSize),
                          title=QueuesWindowTitle,
                          style=wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX|wx.CLIP_CHILDREN,)
        self._url = url
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.html = MyHtmlWindow(self, is_child_window=True, base_addr=base_addr, base_port=base_port)
        self.html.SetRelatedFrame(self, '%s')
        if os.path.isfile('icons/traffic.ico'):
            icon = openWxIcon('icons/traffic.ico')
        else:
            icon = openWxIcon('icons/tray_icon.ico')
        self.SetIcon(icon)

    def OnClose(self, event):
        write_setting('QueuesWindowSize', self.GetSizeTuple(), 'size')
        self.Hide()
        self.html.SetPage('')

    def Show(self):
        self.html.OpenURL(self._url)
        wx.Frame.Show(self)

#------------------------------------------------------------------------------ 

class MyCountersWindow(wx.Frame):
    def __init__(self, parent, url, base_addr, base_port):
        wx.Frame.__init__(self,
                          parent,
                          size=read_setting('CountersWindowSize', 'size', CountersWindowSize),
                          title=CountersWindowTitle,
                          style=wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX|wx.CLIP_CHILDREN,)
        self._url = url
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.html = MyHtmlWindow(self, is_child_window=True, base_addr=base_addr, base_port=base_port)
        self.html.SetRelatedFrame(self, '%s')
        if os.path.isfile('icons/counter.ico'):
            icon = openWxIcon('icons/counter.ico')
        else:    
            icon = openWxIcon('icons/tray_icon.ico')
        self.SetIcon(icon)

    def OnClose(self, event):
        write_setting('CountersWindowSize', self.GetSizeTuple(), 'size')
        self.Hide()
        self.html.SetPage('')
        
    def Show(self):
        self.html.OpenURL(self._url)
        wx.Frame.Show(self)

#------------------------------------------------------------------------------

class MyUpdateSoftwareDialog(wx.MessageDialog):
    def __init__(self, parent):
        msg = 'New software version is available.\n'
        msg += 'Would you like to update BitPie.NET Software now?'
        label = 'Update BitPie.NET Software'
        wx.MessageDialog.__init__(self, parent, msg, label, wx.OK | wx.CANCEL)
 
#------------------------------------------------------------------------------ 

class MyFrame(wx.Frame):
    def __init__(self, parent, ID, url, base_addr, base_port):
        wx.Frame.__init__(self,
                          parent,
                          ID,
                          title=WindowTitle,
                          size=read_setting('WindowSize', 'size', WindowSize),
                          pos=read_setting('WindowPos', 'pos', WindowPos),
                          style=wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|wx.SYSTEM_MENU|wx.CAPTION|wx.CLOSE_BOX|wx.CLIP_CHILDREN,
                          )
        self.base_addr = base_addr
        self.base_port = base_port
        
        self.SetMinSize((800, 480))
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        #---windows
        self.html = MyHtmlWindow(self, True, base_addr=self.base_addr, base_port=self.base_port)
        self.html.SetRelatedFrame(self, '%s')
        self.log = MyLogWindow(self.Parent, '127.0.0.1', 9999)
        self.traf = MyTrafficWindow(self.Parent)
        self.events = MyEventsWindow(self.Parent)
        self.states = MyStatesWindow(self.Parent)
        self.queues = MyQueuesWindow(self.Parent, url + '/monitortransports', base_addr=self.base_addr, base_port=self.base_port)
        self.counters = MyCountersWindow(self.Parent, url + '/traffic', base_addr=self.base_addr, base_port=self.base_port)

        #---menu
        if False:
            menuFile = wx.Menu()
            self.Bind(wx.EVT_MENU, self.OnClose, menuFile.Append(wx.ID_EXIT, "E&xit\tAlt-X", "Close window, BitPie.NET will work in background."))
            menuView = wx.Menu()
            self.Bind(wx.EVT_MENU, self.OnLogs, menuView.Append(-1, "&Logs", "Browse system messages"))
            self.Bind(wx.EVT_MENU, self.OnTraffic, menuView.Append(-1, "&Traffic", "View packets traffic"))
            self.Bind(wx.EVT_MENU, self.OnEvents, menuView.Append(-1, "&Events", "Show system events"))
            self.Bind(wx.EVT_MENU, self.OnStates, menuView.Append(-1, "&States", "Show program states"))
            self.menuBar = wx.MenuBar()
            self.menuBar.Append(menuFile, "&File")
            self.menuBar.Append(menuView, "&View")
            self.SetMenuBar(self.menuBar)

        #---tool bar
        self.toolbar = None
        if read_setting('ToolbarIsVisible', 'str') == 'True':
            self.OnToolbar()

        #status bar
        # self.statusBar = self.CreateStatusBar(2)
        self.CreateStatusBar(2)
        if platform.uname()[0] == 'Windows': 
            self.SetStatusWidths([-1, 200])
            self.SetStatusText('  \xa9 2014, BitPie.NET Inc.', 1)
        else:
            self.SetStatusWidths([-1, 300])
            self.SetStatusText(u'  \u00a9 2014, BitPie.NET Inc.'.encode('utf8'), 1)
        
        # self.statusTextTimer = None

        #---icon
        icon = openWxIcon('icons/tray_icon.ico')
        self.SetIcon(icon)

        #---start page
        if self.html.RegisterClick(None):
            self.html.OpenURL(url)

    def OnLogs(self, evt):
        def cb(x):
            self.log.Show()
        def eb(x):
            d = wx.MessageDialog(
                self,
                'To enable logs go to [menu]->[settings]->[development] and enable http server to watch the logs.',
                'Logs disabled',
                wx.ICON_INFORMATION | wx.OK)
            d.ShowModal()
            d.Destroy()
        self.log.html_log.OpenURL('http://127.0.0.1:9999').addCallbacks(cb, eb)

    def OnTraffic(self, evt):
        self.traf.Show()

    def OnEvents(self, evt):
        self.events.Show()

    def OnStates(self, evt):
        self.states.Show()
        
    def OnQueues(self, evt):
        # self.queues = MyQueuesWindow(self.Parent, self._url + '/monitortransports')
        self.queues.Show()
            
    def OnCounters(self, evt):
        # self.counters = MyCountersWindow(self.Parent, self._url + '/traffic')
        self.counters.Show()

    def OnClose(self, evt):
        WriteText('OnClose\n')
        write_setting('WindowSize', self.GetSizeTuple(), 'size')
        write_setting('WindowPos', self.GetPositionTuple(), 'pos')
        write_setting('ToolbarIsVisible', str(self.toolbar is not None), 'str')
        reactor._stopping = True
        reactor.callFromThread(_threadedselect.ThreadedSelectReactor.stop, reactor)
        
    def OnToolbar(self):
        if self.toolbar is None:
            if os.path.isfile(sharedPath('mykeyfile', 'metadata')) and os.path.isfile(sharedPath('localidentity', 'metadata')):
                self.toolbar = self.CreateToolBar(wx.TB_RIGHT)
                self.toolbar.SetToolBitmapSize((31,31))
                self.Bind(wx.EVT_MENU, self.OnLogs, self.toolbar.AddSimpleTool(1, openWxImage('icons/log32.png'), 'Logs', ''))
                self.Bind(wx.EVT_MENU, self.OnTraffic, self.toolbar.AddSimpleTool(2, openWxImage('icons/history32.png'), 'Packet History', ''))
                self.Bind(wx.EVT_MENU, self.OnQueues, self.toolbar.AddSimpleTool(3, openWxImage('icons/traffic32.png'), 'Traffic', ''))
                self.Bind(wx.EVT_MENU, self.OnCounters, self.toolbar.AddSimpleTool(4, openWxImage('icons/counter32.png'), 'Counters', ''))
                self.Bind(wx.EVT_MENU, self.OnEvents, self.toolbar.AddSimpleTool(5, openWxImage('icons/event32.png'), 'Events', ''))
                self.Bind(wx.EVT_MENU, self.OnStates, self.toolbar.AddSimpleTool(6, openWxImage('icons/states32-1.png'), 'Automats', ''))
                self.toolbar.AddSeparator()
                self.Bind(wx.EVT_MENU, self.OnClose, self.toolbar.AddSimpleTool(7, openWxImage('icons/exit32-3.png'), 'Close', ''))
                self.toolbar.Realize()
        else:
            self.toolbar.Destroy()
            del self.toolbar
            self.toolbar = None
        
    def NewVersion(self, global_and_local_tuple):
        try:
            if self.IsShown():
                if len(global_and_local_tuple) >= 2:
                    if global_and_local_tuple[0] != global_and_local_tuple[1]:
                        dialog = MyUpdateSoftwareDialog(self)
                        if dialog.ShowModal() == wx.ID_OK:
                            self.html.OnCommandOpen('/softwareupdate?action=update')
        except:
            pass

    def SetStatusBarText(self, text):
        # if self.statusTextTimer is not None:
        #     if self.statusTextTimer.active():
        #         self.statusTextTimer.cancel()
        #         self.statusTextTimer = None
        #if text in ['ready',]:
            #self.statusTextTimer = reactor.callLater(20, self.statusBar.SetStatusText, '')
        # self.statusBar.SetStatusText(' ' + text, 0)
        self.SetStatusText(' ' + text, 0)

#------------------------------------------------------------------------------
 
class MyAppBusyInfoFrame(wx.Frame):
    def __init__(self, parent, message):
        wx.Frame.__init__(self, parent, wx.ID_ANY, "Busy",
            wx.DefaultPosition, wx.DefaultSize,
            wx.SIMPLE_BORDER | wx.FRAME_TOOL_WINDOW | wx.FRAME_FLOAT_ON_PARENT )
        #self.panel = MyAppBusyPanel(self)
        self.panel = wx.Panel(self)
        self.panel.SetCursor(wx.HOURGLASS_CURSOR)
        self.text = wx.StaticText(self.panel, wx.ID_ANY, message,  style=wx.ALIGN_CENTRE)
        self.text.SetCursor(wx.HOURGLASS_CURSOR)
        self.label = wx.StaticText(self.panel, wx.ID_ANY, 'BitPie.NET', style=wx.ALIGN_CENTRE)
        self.label.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.label.SetCursor(wx.HOURGLASS_CURSOR)
        sizeText = self.text.GetBestSize()
        sizeLabel = self.label.GetBestSize()
        self.SetClientSize((280, 80))
        self.panel.SetSize(self.GetClientSize())
        self.text.SetPosition((0, 60))
        self.text.Centre(wx.HORIZONTAL)
        self.label.SetPosition((0, 20))
        self.label.Centre(wx.HORIZONTAL)
        self.Centre(wx.BOTH)


class MyAppBusyInfo(object):
    def __init__(self, message, parent=None):
        self._infoFrame = MyAppBusyInfoFrame(parent, message)
        self._infoFrame.Show(True)
        self._infoFrame.Refresh()
        self._infoFrame.Update()

    def __del__(self):
        self._infoFrame.Show(False)
        self._infoFrame.Destroy()

    def set_text(self, txt):
        self._infoFrame.text.SetLabel(txt)
        self._infoFrame.text.Centre(wx.HORIZONTAL)
        self._infoFrame.Refresh()
        self._infoFrame.Update()

#------------------------------------------------------------------------------

class MyApp(wx.App):
    def __init__(self, url):
        global ShowLogs
        self.url = url
        self.base_addr = ''
        self.base_port = 0
        self.busyInfo = None
        self.ready = False
        # WriteText('MyApp.__init__: %s\n' % url)
        output_path = sharedPath('view-err.log')
        wx.App.__init__(self, not ShowLogs, output_path)

    def OnInit(self):
        global GUISettingsExists
        parts = urlparse.urlsplit(self.url)
        try:
            self.base_addr, x, self.base_port = parts[1].partition(':')
            if self.base_port:
                self.base_port = int(self.base_port)
            else:
                self.base_port = 6116
        except:
            WriteException()
        WriteText('OnInit %s:%s\n' % (self.base_addr, self.base_port))
        self.memFSHandler = wx.MemoryFSHandler()
        wx.FileSystem.AddHandler(self.memFSHandler)
        iconsDir = os.path.join(getExecutableDir(), 'icons')
        if os.path.isdir(iconsDir):
            for filename in os.listdir(iconsDir):
                if not ( filename.endswith('.png') or filename.endswith('.ico') ):
                    continue
                filepath = os.path.join(iconsDir, filename)
                if not os.path.isfile(filepath):
                    continue
                fin = open(filepath, 'rb')
                src = fin.read()
                fin.close()
                self.memFSHandler.AddFile(filename, src, wx.BITMAP_TYPE_PNG)
                WriteText('AddFile %s\n' % filepath)
        self.frame = MyFrame(None, -1, self.url, self.base_addr, self.base_port)
        WriteText('GUISettingsExists=%s\n' % str(GUISettingsExists))
        if not GUISettingsExists:
            self.frame.Center()
        #self.frame.Show()
        self.SetTopWindow(self.frame)
        factory = MyClientFactory(self)
        reactor.connectTCP(self.base_addr, self.base_port, factory)
        return True

    def ShowBusy(self, label='busy'):
        if self.busyInfo is not None:
            self.busyInfo.set_text(label)
            return
        self.busyInfo = MyAppBusyInfo(label, None)

    def CloseBusy(self):
        if self.busyInfo is None:
            return
        del self.busyInfo
        self.busyInfo = None

    def OnExit(self):
        WriteText('OnExit\n')
        return True

    def OnCommand(self, cmd):
        # WriteText('OnCommand %s\n' % cmd)

        if cmd == 'exit':
            reactor.stop()

        elif cmd == 'update':
            self.frame.html.OnCommandUpdate()

        elif cmd.startswith('open'):
            parts = cmd.split(' ')
            if len(parts) >= 2:
                self.frame.html.OnCommandOpen(parts[1].strip())

        elif cmd.startswith('packet'):
            self.frame.traf.add(cmd.split(' '))

        elif cmd.startswith('event'):
            self.frame.events.add(cmd)

        elif cmd.startswith('state:'):
            state = cmd[6:].replace('_', ' ').lower()
            ready_, label = StatesDict.get(state, (True, ''))
            WriteText('state [%s] %s, %s\n' % (state, str(ready_), label))
            if label == '':
                label = state
            if ready_:
                self.ready = True
            if self.ready:
                self.CloseBusy()
                self.frame.Show()
            else:
                self.ShowBusy(label)
            self.frame.SetStatusBarText(label)
            
        elif cmd == 'raise':
            self.frame.Raise()
            
        elif cmd.startswith('automat'):
            self.frame.states.update(cmd)
        
        elif cmd.startswith('version:'):
            self.frame.NewVersion(cmd[8:].strip().split(' '))
            
        elif cmd == 'toolbar':
            self.frame.OnToolbar()
            
        else:
            WriteText('OnCommand unknown command: %s\n' % cmd)

#------------------------------------------------------------------------------

class MyClientProtocol(basic.LineReceiver):
    connectedFlag = False
    def connectionMade(self):
        self.transport.write('BITPIE-VIEW-REQUEST\r\n')

    def lineReceived(self, line):
        cmd = line.strip()
        #WriteText('>>>' + cmd + '\n')
        if cmd.startswith('BITPIE-SERVER:'):
            self.connectedFlag = True
            state = cmd.replace('BITPIE-SERVER:', '')
            self.factory.app.OnCommand('state:' + state)
            return
        if not self.connectedFlag:
            return
        self.factory.app.OnCommand(cmd)

    def connectionLost(self, reason):
        WriteText('connectionLost: %s\n' % reason.getErrorMessage())
        reactor._stopping = True
        reactor.callFromThread(_threadedselect.ThreadedSelectReactor.stop, reactor)


class MyClientFactory(protocol.ClientFactory):
    protocol = MyClientProtocol
    def __init__(self, app):
        self.app = app

    def clientConnectionFailed(self, connector, reason):
        WriteText('clientConnectionFailed: %s\n' % reason.getErrorMessage())
        reactor._stopping = True
        reactor.callFromThread(_threadedselect.ThreadedSelectReactor.stop, reactor)


#------------------------------------------------------------------------------

def main():
    global ShowLogs
    global GUISettingsExists
    if sys.argv.count('logs'):
        ShowLogs = True
        from twisted.internet import defer
        defer.setDebugging(True)
        # print '======================================================================='
        # print '======================================================================='

    # detect port number to connect
    try:
        port = open(sharedPath('localport', 'metadata')).read()
    except:
        port = 6116
    url = 'http://127.0.0.1:%s' % port

    GUISettingsExists = load_gui_settings()

    reload(sys)
    denc = locale.getpreferredencoding()
    if denc != '':
        sys.setdefaultencoding(denc)

    WriteText('', 'bpgui-err.log', 'w')
    WriteText(time.asctime()+' started\n', 'bpgui.log', 'w')
    WriteText('Forms: %s\n' % str(forms))

    app = MyApp(url)

    reactor.registerWxApp(app)

    reactor.run()

    save_gui_settings()

    WriteText(time.asctime()+' finished\n', 'bpgui.log', 'a')


#------------------------------------------------------------------------------


def test():
    reload(sys)
    denc = locale.getpreferredencoding()
    if denc != '':
        sys.setdefaultencoding(denc)
    class MyTestApp(wx.App):
        def __init__(self):
            global ShowLogs
            wx.App.__init__(self, not ShowLogs, sharedPath('bpgui-err.log'))
        def OnInit(self):
            self.frame = MyTrafficWindow(None)
            self.frame.Show()
            self.SetTopWindow(self.frame)
            reactor.callLater(0, self.run)
            return True
        def run(self):
            self.frame.add('packet out Data to veeesel (tcp://91.203.188.111:7790) ID=F20111223102523AM-0-0-Parity LENGTH=1047848(1048826) finished'.split(' '))
            #reactor.callLater(1, self.run)

    app = MyTestApp()
    reactor.registerWxApp(app)
    reactor.run()

def test2():
    global ShowLogs
    ShowLogs = True

    WriteText('sdfsdf')

    factory = MyClientFactory(None)
    reactor.connectTCP('localhost', 6789, factory)
    reactor.run()

#------------------------------------------------------------------------------

if __name__ == "__main__":
    if sys.argv.count('test'):
        test()
        sys.exit(0)
    main()

#------------------------------------------------------------------------------ 

'''
http://docs.wxwidgets.org/trunk/overview_html.html

Table 16.1 Valid HTML tags for the HTML window widget

Document Structure Tags:
<a href name target>
<body alignment bgcolor link text>
<meta content http-equiv>
<title>

Text Structure Tags:
<br>
<div align>
<hr align noshade size width>
<p>

Text Display Tags:
<address>
<b>
<big>
<blockquote>
<center>
<cite>
<code>
<em>
<font color face size>
<h1>
<h2>

List Tags:
<dd>
<dl>
<dt>
<li>
<ol>
<ul>

Image and Map Tags:
<area coords href shape>
<img align height src width usemap>
<map name>

Table Tags:
<table align bgcolor border cellpadding cellspacing valign width>
<td align bgcolor colspan rowspan valign width nowrap>
<th align bgcolor colspan valign width rowspan>
<tr align bgcolor valign>

Veselin also found the package "forms":
<form action method>
<input type ...>
<select>
<textarea> - seems have some problems here

'''

'''
Another description:
Table of common parameter values
We will use these substitutions in tags descriptions:

[alignment]     CENTER
                LEFT
                RIGHT
                JUSTIFY

[v_alignment]   TOP
                BOTTOM
                CENTER

[color]         HTML 4.0-compliant colour specification

[fontsize]      -2
                -1
                +0
                +1
                +2
                +3
                +4
                 1
                 2
                 3
                 4
                 5
                 6
                 7

[pixels]        integer value that represents dimension in pixels

[percent]       i%
                where i is integer

[url]           an URL

[string]        text string

[coords]        c(1),c(2),c(3),...,c(n)
                where c(i) is integer

List of supported tags
A               NA5ME=[string]
                HREF=[url]
                TARGET=[target window spec]
ADDRESS
AREA            SHAPE=POLY
                SHAPE=CIRCLE
                SHAPE=RECT
                COORDS=[coords]
                HREF=[url]
B
BIG
BLOCKQUOTE
BODY            TEXT=[color]
                LINK=[color]
                BGCOLOR=[color]
BR              ALIGN=[alignment]
CENTER
CITE
CODE
DD
DIV             ALIGN=[alignment]
DL
DT
EM
FONT            COLOR=[color]
                SIZE=[fontsize]
                FACE=[comma-separated list of facenames]
HR              ALIGN=[alignment]
                SIZE=[pixels]
                WIDTH=[percent|pixels]
                NOSHADE
H1
H2
H3
H4
H5
H6
I
IMG             SRC=[url]
                WIDTH=[pixels]
                HEIGHT=[pixels]
                ALIGN=TEXTTOP
                ALIGN=CENTER
                ALIGN=ABSCENTER
                ALIGN=BOTTOM
                USEMAP=[url]
KBD
LI
MAP             NAME=[string]
META            HTTP-EQUIV="Content-Type"
                CONTENT=[string]
OL
P               ALIGN=[alignment]
PRE
SAMP
SMALL
STRIKE
STRONG
SUB
SUP
TABLE           ALIGN=[alignment]
                WIDTH=[percent|pixels]
                BORDER=[pixels]
                VALIGN=[v_alignment]
                BGCOLOR=[color]
                CELLSPACING=[pixels]
                CELLPADDING=[pixels]
TD              ALIGN=[alignment]
                VALIGN=[v_alignment]
                BGCOLOR=[color]
                WIDTH=[percent|pixels]
                COLSPAN=[pixels]
                ROWSPAN=[pixels]
                NOWRAP
TH              ALIGN=[alignment]
                VALIGN=[v_alignment]
                BGCOLOR=[color]
                WIDTH=[percent|pixels]
                COLSPAN=[pixels]
                ROWSPAN=[pixels]
TITLE
TR              ALIGN=[alignment]
                VALIGN=[v_alignment]
                BGCOLOR=[color]
TT
U
UL

'''

