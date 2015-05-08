import os
gettext = lambda s: s
PROJECT_PATH = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]

SECRET_KEY = '7a9*@f0v9z3ma7my+=oxfi6!q9nrm0fu#bu94bz%o5_1bc$=51'

DEBUG = False

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
    'web.myfilesapp',
)

#STATICFILES_DIRS = (
#     os.path.join(PROJECT_PATH, 'asite', '/static/'),
#     os.path.join(PROJECT_PATH, 'updateapp', '/static/'),
#     os.path.join(PROJECT_PATH, 'mainapp', '/static/'),
#     os.path.join(PROJECT_PATH, 'setupapp', '/static/'),
#     os.path.join(PROJECT_PATH, 'jqchatapp', '/static/'),
#)

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
        'NAME': os.path.join(PROJECT_PATH, 'asite.db'),
    }
}

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

ADMIN_MEDIA_PREFIX = '/media/admin/'

STATIC_ROOT = os.path.join(PROJECT_PATH, 'static')

STATIC_URL = '/static/'

