#!/usr/bin/env python
# settings.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (settings.py) is part of BitDust Software.
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
import sys

LOGGING_CONFIG = None
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'simple'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'propagate': True,
            'level': 'INFO',
        },
    },
}

# gettext = lambda s: s
PROJECT_PATH = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]

APP_DATA_PATH = ''

if APP_DATA_PATH == '':
    try:
        import sys
        reload(sys)
        if hasattr(sys, "setdefaultencoding"):
            import locale
            denc = locale.getpreferredencoding()
            if denc != '':
                sys.setdefaultencoding(denc)
    except:
        pass

    curdir = os.getcwd()  # os.path.dirname(os.path.abspath(sys.executable))
    appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
    if os.path.isfile(os.path.join(curdir, 'appdata')):
        try:
            appdata = os.path.abspath(open(os.path.join(curdir, 'appdata'), 'rb').read().strip())
        except:
            pass
    if not os.path.exists(appdata):
        try:
            os.makedirs(appdata)
        except:
            pass

    APP_DATA_PATH = unicode(appdata)

SQLITE_DB_FILENAME = os.path.join(APP_DATA_PATH, 'metadata', 'asite.db')
if not os.path.isdir(os.path.dirname(SQLITE_DB_FILENAME)):
    os.makedirs(os.path.dirname(SQLITE_DB_FILENAME))

SECRET_KEY = '7a9*@f0v9z3ma7my+=oxfi6!q9nrm0fu#bu94bz%o5_1bc$=51'

DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'web.asite',
    'web.setupapp',
    'web.identityapp',
    'web.jqchatapp',
    'web.customerapp',
    'web.supplierapp',
    'web.friendapp',
    # 'web.myfilesapp',
    'web.filemanagerapp',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.request',
)

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

ROOT_URLCONF = 'web.asite.urls'

WSGI_APPLICATION = 'web.asite.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': SQLITE_DB_FILENAME,
    }
}

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

ADMIN_MEDIA_PREFIX = '/media/admin/'

STATIC_ROOT = os.path.join(PROJECT_PATH, 'asite', 'static')

STATIC_URL = '/asite/'
