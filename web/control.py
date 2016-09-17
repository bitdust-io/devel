#!/usr/bin/python
# control.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (control.py) is part of BitDust Software.
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
#
#
#
#

"""
.. module:: control

"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 20

#------------------------------------------------------------------------------ 

import os
import sys
import time
import pprint
import random
import webbrowser

#------------------------------------------------------------------------------ 

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.web import wsgi
from twisted.web import server
from twisted.web import resource
from twisted.web import static
from twisted.python import threadpool

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(
        0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio

from main import settings

# from web import sqlio
from web import dbwrite
# from web import shortpool

#------------------------------------------------------------------------------

_WSGIListener = None
_WSGIPort = None
_ShortPoolPort = None
_UpdateFlag = None
_UpdateItems = {}

#------------------------------------------------------------------------------

def init():
    global _WSGIListener
    global _WSGIPort
    result = Deferred()
    if _Debug:
        lg.out(_DebugLevel, 'control.init')
    request_update()
    if _WSGIListener:
        if _Debug:
            lg.out(_DebugLevel, '    SKIP listener already exist')
        result.callback(0)
        return result
    
    try:
        import django
        ver = django.get_version()
        if not ver.startswith('1.7'):
            if _Debug:
                lg.out(_DebugLevel, '    Django version must be 1.7, skip!')
            result.callback(0)
            return result
    except:
        lg.exc()
        result.callback(0)
        return result

    if _Debug:
        lg.out(_DebugLevel+6, '    \n' + pprint.pformat(sys.path))

    if _Debug:
        lg.out(_DebugLevel, '    setting environment DJANGO_SETTINGS_MODULE=web.asite.settings')
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.asite.settings")

    from django.core.wsgi import get_wsgi_application
    from django.conf import settings as django_settings
    from django.core import management
    from django.contrib.auth.management.commands import changepassword
    
    if _Debug:
        lg.out(_DebugLevel, '    configuring WSGI bridge from Twisted to Django')
    wsgi_handler = get_wsgi_application()
    my_wsgi_handler = MyFakedWSGIHandler(wsgi_handler) 
    pool = threadpool.ThreadPool()
    pool.start()
    reactor.addSystemEventTrigger('after', 'shutdown', pool.stop)
    resource = wsgi.WSGIResource(reactor, pool, my_wsgi_handler)
    root = DjangoRootResource(resource)
    root_static_dir = os.path.join(bpio.getExecutableDir(), "web")  
    for sub in os.listdir(root_static_dir):
        static_path = os.path.join(root_static_dir, sub, 'static')
        if not os.path.isdir(static_path):
            continue
        node = static.File(static_path) 
        root.putChild(sub, node)
        if _Debug:
            lg.out(_DebugLevel, '        added static dir: %s->%s' % (sub, static_path))
        if sub == 'asite':
            admin_path = os.path.join(root_static_dir, sub, 'admin', 'static')
            node.putChild('admin', static.File(admin_path))
            if _Debug:
                lg.out(_DebugLevel, '        added ADMIN static dir: admin->%s' % admin_path)
    site = server.Site(root)
    _WSGIPort = 8080 # TODO: read port num from settings 
    if _Debug:
        lg.out(_DebugLevel, '        %s' % my_wsgi_handler)
        lg.out(_DebugLevel, '        %s' % resource)
        lg.out(_DebugLevel, '        %s' % site)

    verbosity = 0
    if lg.is_debug(18):
        verbosity = 3
    if lg.is_debug(12):
        verbosity = 2
    if lg.is_debug(8):
        verbosity = 1
        
    # lg.out(4, '    running django "flush" command')
    # management.call_command('flush', interactive=False, verbosity=verbosity)

    # lg.out(4, '    running django "createsuperuser" command')
    # management.call_command('createsuperuser',
    #     interactive=False, verbosity=verbosity, 
    #     username="admin", email="admin@localhost")
    # command = changepassword.Command()
    # command._get_pass = lambda *args: 'admin'
    # command.execute("admin")

    if _Debug:
        lg.out(_DebugLevel, '    running django "syncdb" command')
    management.call_command('syncdb', 
        stdout=open(os.path.join(settings.LogsDir(), 'django-syncdb.log'), 'w'),
        interactive=False, verbosity=verbosity)

    _ShortPoolPort = 8081 # TODO: read port num from settings
    # shortpool.init(get_update_items, set_updated, _ShortPoolPort)

    if _Debug:
        lg.out(_DebugLevel, '    starting listener: %s' % site)
    result = start_listener(site)
    result.addCallback(lambda portnum: post_init(portnum))

    return result

def post_init(portnum):
    if _Debug:
        lg.out(_DebugLevel, 'control.post_init')
    from contacts import contactsdb
    contactsdb.SetCorrespondentsChangedCallback(dbwrite.update_friends)
    from contacts import identitydb
    identitydb.AddCacheUpdatedCallback(dbwrite.update_identities)
    from chat import message
    message.AddIncomingMessageCallback(dbwrite.incoming_message)
    # sqlio.init(database_info)
#    contactsdb.SetSuppliersChangedCallback(sqlio.update_suppliers)
#    contactsdb.SetCustomersChangedCallback(sqlio.update_customers)
    return portnum
    

def shutdown():
    global _WSGIListener
    global _WSGIPort
    if _Debug:
        lg.out(_DebugLevel, 'control.shutdown')
    from chat import message
    message.RemoveIncomingMessageCallback(dbwrite.incoming_message)
    # sqlio.shutdown()
    # shortpool.shutdown()
    if _WSGIListener:
        if _Debug:
            lg.out(_DebugLevel, '    close listener %s' % _WSGIListener)
        result = _WSGIListener.stopListening()
        _WSGIListener.connectionLost("Closing WSGIListener as requested")
        del _WSGIListener
    else:
        if _Debug:
            lg.out(_DebugLevel, '    listener is None')
        result = Deferred()
        result.callback(1)
    _WSGIListener = None
    _WSGIPort = None
    return result

#------------------------------------------------------------------------------ 

def start_listener(site):
    if _Debug:
        lg.out(_DebugLevel, 'control.start_listener %s' % site)
    
    def _try(site, result, counter):
        global _WSGIListener
        global _WSGIPort
        if counter > 10:
            _WSGIPort = random.randint(8001, 8999)
        if _Debug:
            lg.out(_DebugLevel, '                _try port=%d counter=%d' % (_WSGIPort, counter))
        try:
            _WSGIListener = reactor.listenTCP(_WSGIPort, site)
        except:
            if _Debug:
                lg.out(_DebugLevel, '                _try it seems port %d is busy' % _WSGIPort)
            _WSGIListener = None
        if _WSGIListener is None:
            reactor.callLater(0.5, _try, site, result, counter+1)
            return
        bpio.WriteFile(settings.LocalWSGIPortFilename(), str(_WSGIPort))
        if _Debug:
            lg.out(_DebugLevel, '                _try STARTED on port %d' % _WSGIPort)
        result.callback(_WSGIPort)

    result = Deferred()
    _try(site, result, 0)
    return result

#------------------------------------------------------------------------------ 

def show():
    global _WSGIPort
    if _WSGIPort is not None:
        if _Debug:
            lg.out(_DebugLevel, 'control.show on port %d' % _WSGIPort)
        webbrowser.open('http://localhost:%d' % _WSGIPort)

    else:
        try:
            local_port = int(bpio.ReadBinaryFile(settings.LocalWSGIPortFilename()))
        except:
            local_port = None
        if not local_port:
            if _Debug:
                lg.out(_DebugLevel, 'control.show SKIP, LocalWebPort is None, %s is empty' % settings.LocalWSGIPortFilename())
        else:
            if _Debug:
                lg.out(_DebugLevel, 'control.show on port %d' % local_port)
            webbrowser.open('http://localhost:%d' % local_port)

#------------------------------------------------------------------------------ 

def stop_updating():
    global _UpdateFlag
    global _UpdateItems
    if _Debug:
        lg.out(_DebugLevel, 'control.stop_updating  _UpdateFlag=None, current items: %s' % str(_UpdateItems))
    _UpdateFlag = None
    _UpdateItems.clear()
    _UpdateItems['stop'] = int(time.time())

def set_updated():
    global _UpdateFlag
    global _UpdateItems
    if _Debug:
        lg.out(_DebugLevel, 'control.set_updated  _UpdateFlag=False, current items: %s' % str(_UpdateItems))
    _UpdateFlag = False
    _UpdateItems.clear()
   
def get_update_flag():
    global _UpdateFlag
    return _UpdateFlag

def get_update_items():
    global _UpdateItems
    return _UpdateItems

def request_update(items=None):
    global _UpdateFlag
    global _UpdateItems
    if _Debug:
        lg.out(_DebugLevel, 'control.request_update  _UpdateFlag=True, new items=%s' % str(items) )
    _UpdateFlag = True
    _UpdateItems['refresh'] = int(time.time())
    if items is not None:
        for item in items:
            if isinstance(item, str):
                _UpdateItems[item] = int(time.time())
            elif isinstance(item, tuple) and len(item) == 2:
                key, value = item
                if key not in _UpdateItems:
                    _UpdateItems[key] = []
                _UpdateItems[key].append(value)
            else:
                for item in items:
                    _UpdateItems.update(item)

#------------------------------------------------------------------------------ 

def on_suppliers_changed(current_suppliers):
    request_update()

def on_backup_stats(backupID):
    request_update([('backupID', backupID),])
    
def on_read_local_files():
    request_update()

#------------------------------------------------------------------------------ 

class MyFakedWSGIHandler:
    def __init__(self, original_handler):
        self.orig_handler = original_handler
        
    def __call__(self, environ, start_response):
        return self.orig_handler(environ, start_response)   


class DjangoRootResource(resource.Resource):

    def __init__(self, wsgi_resource):
        resource.Resource.__init__(self)
        self.wsgi_resource = wsgi_resource

    def getChild(self, path, request):
        path0 = request.prepath.pop(0)
        request.postpath.insert(0, path0)
        # lg.out(4, 'control.DjangoRootResource.getChild %s' % path0)
        return self.wsgi_resource


class DebugMixin(object):
    def get_context_data(self, **kwargs):
        if 'debug' not in kwargs:
            try:
                kwargs['debug'] = str(pprint.pformat(self.context))
                pprint.pprint(self.context)
            except:
                lg.exc()
        return kwargs
    
#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)
    reactor.callWhenRunning(init)
    reactor.run()
    lg.out(0, 'reactor stopped, EXIT')
