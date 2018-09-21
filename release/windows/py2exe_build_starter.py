#!/usr/bin/python
# py2exe_build_starter.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (py2exe_build_starter.py) is part of BitDust Software.
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

from __future__ import absolute_import
import os
import sys


try:
    try:
        import py2exe.mf as modulefinder
    except ImportError:
        import modulefinder
    import win32com
    import sys
    for p in win32com.__path__[1:]:
        modulefinder.AddPackagePath("win32com", p)
    for extra in ["win32com.shell"]:  # ,"win32com.mapi"
        __import__(extra)
        m = sys.modules[extra]
        for p in m.__path__[1:]:
            modulefinder.AddPackagePath(extra, p)
except ImportError:
    pass


from distutils.core import setup
import py2exe


import twisted.web.resource as resource

packages = [
    'encodings',
]

includes = [
    'encodings',
    'encodings.*',
    'twisted.web.resource',
    'optparse',
]

excludes = [
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


setup(

    name='BitDust Starter',

    description='BitDust Starter',

    version=open('release/version').read().strip(),

    windows=[

        {
            'script': 'bitstarter.py',
            'icon_resources': [(1, "icons/tray_icon.ico")],
        },

    ],

    options={
        'py2exe': {
            'packages': packages,
            'includes': includes,
            'excludes': excludes,
            'ascii': 1,
            'compressed': True,
            'optimize': 2,
            'bundle_files': 2,
            'dist_dir': 'release\windows\starter',
        },
    },

    zipfile=None,
)
