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
import locale
import traceback
import imp
import time

from twisted.internet import wxreactor
try:
    wxreactor.install()
except:
    pass

from twisted.internet import reactor

import wx.html2

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

#------------------------------------------------------------------------------ 

def main():
    try:
        port = open(sharedPath('localport', 'metadata')).read()
    except:
        port = 6116
    url = 'http://127.0.0.1:%s' % port

    reload(sys)
    denc = locale.getpreferredencoding()
    if denc != '':
        sys.setdefaultencoding(denc)

    WriteText('', 'bpgui-err.log', 'w')
    WriteText(time.asctime()+' started\n', 'bpgui.log', 'w')

    app = MyApp(url)

    reactor.registerWxApp(app)

    reactor.run()

    WriteText(time.asctime()+' finished\n', 'bpgui.log', 'a')

#------------------------------------------------------------------------------ 

class MyApp(wx.App):
    def __init__(self, url):
        WriteText('MyApp.__init__: %s\n' % url)
        self.url = url
        self.base_addr = ''
        self.base_port = 0
        self.busyInfo = None
        self.ready = False
        output_path = sharedPath('view-err.log')
        wx.App.__init__(self, True, output_path)

    def OnInit(self):
        WriteText('MyApp.OnInit %s:%s\n' % (self.base_addr, self.base_port))
        frame = wx.Frame(None, -1, 'A Simple Frame')
        browser = wx.html2.WebView.New(frame)
        browser.LoadURL(self.url)
        frame.Show()
        return True

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    main()
