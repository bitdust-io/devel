#!/usr/bin/python

import os
import sys

try:
    try:
        import py2exe.mf as modulefinder
    except ImportError:
        import modulefinder
    import win32com, sys
    for p in win32com.__path__[1:]:
        modulefinder.AddPackagePath("win32com", p)
    for extra in ["win32com.shell"]: #,"win32com.mapi"
        __import__(extra)
        m = sys.modules[extra]
        for p in m.__path__[1:]:
            modulefinder.AddPackagePath(extra, p)
except ImportError:
    pass


from distutils.core import setup
import py2exe
import twisted.web.resource as resource
import optparse
import zope
import zope.interface
import zope.interface.adapter


packages = [
    'encodings',
    ]

includes = [
    'encodings',
    'encodings.*',
    'twisted.web.resource',
    'optparse',
    ]

excludes =[
    'ICCProfile',
    '_imaging_gif', 
    '_imagingagg',           
    'DLFCN',
    'PAM',
    'PyQt4',
    'PyQt4.QtCore',
    'PyQt4.QtGui',
    'Tkinter',
    '_ssl',
    '_tkinter',
    'cherrypy',
    'difflib',
    'dl',
    'doctest',
    'dowser',
    'email.Generator',
    'email.Iterators',
    'email.Utils',
    'email.Encoders', 
    'email.MIMEBase', 
    'email.MIMEMultipart', 
    'email.MIMEText', 
    'email.base64MIME',    
    'guppy',
    'guppy.heapy.RM',
    'hotshot',
    'hotshot.stats',
    'lib.dowser',
    'paste',
    'pip',
    'pyreadline',
    'qtrayicon',
    'reprlib',
    'resource',
    'shadow',
    'spwd',
    'twisted.internet._sigchld',
    'twisted.python._epoll',
    'twisted.python.sendmsg',
    'twisted.python._initgroups',
    'wx.Timer',
    'http.client',
    'urllib.parse',
    '_scproxy',
    'gmpy',
    'Carbon',
    'Carbon.Files',
    '_sysconfigdata',
    'html',
    'queue',
    ]

ignores = [
    ]

setup(

    name = 'BitPie.NET',

    description = 'BitPie.NET',

    version = open('release/version').read().strip(), 

    console = [
        {
            'script': 'bppipe.py',
            'icon_resources': [(1, "icons/tray_icon.ico")],
        },
        {
            'script': 'bptester.py',
            'icon_resources': [(1, "icons/tray_icon.ico")],
        },
        {
            'script': 'bpworker.py',
            'icon_resources': [(1, "icons/tray_icon.ico")],
            'unbuffered': True,
        },
    ],

    windows = [

        {
            'script': 'bitpie.py',
            'icon_resources': [(1, "icons/tray_icon.ico")],
        },

        {
            'script': 'bpgui.py',
            'icon_resources': [(1, "icons/tray_icon.ico")],
        },

    ],

    options = {
        'py2exe': {
            'packages': packages,
            'includes': includes,
            'excludes': excludes,
            'ignores':  ignores,
            'ascii': 1,
            'optimize': 2,
            'skip_archive': 1,
            'dist_dir': 'release/windows/build',
        },
    },

)

