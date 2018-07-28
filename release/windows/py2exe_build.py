#!/usr/bin/python
# py2exe_build.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (py2exe_build.py) is part of BitDust Software.
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

#------------------------------------------------------------------------------
#--- win32com patch ---
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

modulefinder.AddPackagePath('django', 'util')

#------------------------------------------------------------------------------

from distutils.core import setup
import py2exe
import twisted.web.resource as resource
import optparse
import zope
import zope.interface
import zope.interface.adapter

import pprint
pprint.pprint(sys.path)

#------------------------------------------------------------------------------

packages = [
    'encodings',
    "django",
    "sqlite3",
    'email',
    'web',
    'unittest',
]

#------------------------------------------------------------------------------

includes = [
    'django.*',
    'django.template.loaders.filesystem',
    'django.template.loaders.app_directories',
    'django.middleware.common',
    'django.contrib.sessions.middleware',
    'django.contrib.auth.middleware',
    'django.middleware.doc',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sessions.backends.db',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.core.cache.backends',
    'django.db.backends.sqlite3.base',
    'django.db.backends.sqlite3.introspection',
    'django.db.backends.sqlite3.creation',
    'django.db.backends.sqlite3.client',
    'django.template.defaulttags',
    'django.template.defaultfilters',
    'django.template.loader_tags',
    'django.contrib.admin.views.main',
    'django.core.context_processors',
    'django.contrib.auth.views',
    'django.contrib.auth.backends',
    'django.views.static',
    'django.contrib.admin.templatetags.admin_list',
    'django.contrib.admin.templatetags.admin_modify',
    'django.contrib.admin.templatetags.log',
    'django.conf.urls.shortcut',
    'django.views.defaults',
    'django.core.cache.backends.locmem',
    'django.templatetags.i18n',
    'django.views.i18n',
    'email',
    'email.mime.audio',
    'email.mime.base',
    'email.mime.image',
    'email.mime.message',
    'email.mime.multipart',
    'email.mime.nonmultipart',
    'email.mime.text',
    'email.charset',
    'email.encoders',
    'email.errors',
    'email.feedparser',
    'email.generator',
    'email.header',
    'email.iterators',
    'email.message',
    'email.parser',
    'email.utils',
    'email.base64mime',
    'email.quoprimime',
    'encodings',
    'encodings.*',
    'twisted.web.resource',
    'optparse',
    'services.*',
    'Cookie',
    'htmlentitydefs',
    'difflib',
    'web.asite.*',
    'web.customerapp.*',
    'web.friendapp.*',
    'web.identityapp.*',
    'web.jqchatapp.*',
    'web.myfilesapp.*',
    'web.setupapp.*',
    'web.supplierapp.*',
]

#------------------------------------------------------------------------------

excludes = [
    '__pypy__.builders',
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
    # 'email.Generator',
    # 'email.Iterators',
    # 'email.Utils',
    # 'email.Encoders',
    # 'email.MIMEBase',
    # 'email.MIMEMultipart',
    # 'email.MIMEText',
    # 'email.base64MIME',
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
    'queue',
]

#------------------------------------------------------------------------------

ignores = [
]

#------------------------------------------------------------------------------
#--- SETUP --------------------------------------------------------------------

setup(

    name='BitDust',

    description='BitDust',

    version=open('release/version').read().strip(),

    console=[
        {
            'script': 'bitdust.py',
            'icon_resources': [(1, "icons/tray_icon.ico")],
        },
        {
            'script': 'bpcmd.py',
            'icon_resources': [(1, "icons/tray_icon.ico")],
        },
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
        {
            'script': 'manage.py',
            'icon_resources': [(1, "icons/tray_icon.ico")],
        },
    ],

    # windows = [

    #{
    #    'script': 'bitdust.py',
    #    'icon_resources': [(1, "icons/tray_icon.ico")],
    #},

    # {
    #     'script': 'bpgui.py',
    #     'icon_resources': [(1, "icons/tray_icon.ico")],
    # },

    # ],

    options={
        'py2exe': {
            'packages': packages,
            'includes': includes,
            'excludes': excludes,
            'ignores': ignores,
            'ascii': 1,
            'optimize': 2,
            'skip_archive': 1,
            'dist_dir': 'release/windows/build',
        },
    },

)
