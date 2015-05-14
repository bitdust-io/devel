#!/usr/bin/python
# control.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: control

"""

import os
import sys
import random
import webbrowser

#------------------------------------------------------------------------------ 

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.application import internet
from twisted.application import service
from twisted.web import wsgi
from twisted.web import server
from twisted.web import resource
from twisted.web import static
from twisted.python import threadpool

#------------------------------------------------------------------------------ 

from django.conf import settings as django_settings
from django.core.wsgi import get_wsgi_application

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

#------------------------------------------------------------------------------

_WSGIListener = None
_WSGIPort = None
_UpdateFlag = None

#------------------------------------------------------------------------------

def init():
    global _WSGIListener
    global _WSGIPort
    lg.out(4, 'control.init')
    if _WSGIListener:
        lg.out(4, '    SKIP listener already exist')
        return

    lg.out(4, '    setting environment DJANGO_SETTINGS_MODULE=web.asite.settings')
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.asite.settings")
    
    # TODO run "python manage.py syncdb"


    lg.out(4, '    configuring WSGI bridge from Twisted to Django')
    wsgi_handler = get_wsgi_application()
    my_wsgi_handler = MyFakedWSGIHandler(wsgi_handler) 
    pool = threadpool.ThreadPool()
    pool.start()
    reactor.addSystemEventTrigger('after', 'shutdown', pool.stop)
    resource = wsgi.WSGIResource(reactor, pool, my_wsgi_handler)
    root = DjangoRootResource(resource) 
    static_path = os.path.join(bpio.getExecutableDir(), "web", "static")
    root.putChild('static', static.File(static_path))
    site = server.Site(root)
    _WSGIPort = 8080
    lg.out(4, '        %s' % my_wsgi_handler)
    lg.out(4, '        %s' % resource)
    lg.out(4, '        %s' % site)
    
    result = start_listener(site)
    result.addCallback(lambda portnum: post_init())

    return result

def post_init():
    lg.out(4, 'control.post_init')
    from contacts import contactsdb
    contactsdb.SetCorrespondentsChangedCallback(dbwrite.update_friends)
    from contacts import identitydb
    identitydb.AddCacheUpdatedCallback(dbwrite.update_identities)
    from chat import message
    message.SetIncomingMessageCallback(dbwrite.incoming_message)
    
    # sqlio.init(database_info)
#    contactsdb.SetSuppliersChangedCallback(sqlio.update_suppliers)
#    contactsdb.SetCustomersChangedCallback(sqlio.update_customers)
    

def shutdown():
    global _WSGIListener
    global _WSGIPort
    lg.out(4, 'control.shutdown')
    # sqlio.shutdown()
    result = Deferred()
    if _WSGIListener:
        lg.out(4, '    close listener %s' % _WSGIListener)
        result = _WSGIListener.stopListening()
        _WSGIListener.connectionLost("Closing WSGIListener as requested")
        del _WSGIListener
    else:
        lg.out(4, '    listener is None')
        result.callback(1)
    _WSGIListener = None
    _WSGIPort = None
    return result

#------------------------------------------------------------------------------ 

def start_listener(site):
    lg.out(4, 'control.start_listener %s' % site)
    
    def _try(site, result, counter):
        global _WSGIListener
        global _WSGIPort
        if counter > 10:
            _WSGIPort = random.randint(8001, 8999)
        lg.out(4, '                _try port=%d counter=%d' % (_WSGIPort, counter))
        try:
            _WSGIListener = reactor.listenTCP(_WSGIPort, site)
        except:
            lg.out(4, '                _try it seems port %d is busy' % _WSGIPort)
            _WSGIListener = None
        if _WSGIListener is None:
            reactor.callLater(0.5, _try, site, result, counter+1)
            return
        lg.out(4, '                _try STARTED on port %d' % _WSGIPort)
        result.callback(_WSGIPort)

    result = Deferred()
    # wsgiport = 8080
    _try(site, result, 0)
    return result

#------------------------------------------------------------------------------ 

def show():
    global _WSGIPort
    lg.out(4, 'control.show')
    if _WSGIPort is not None:
        webbrowser.open('http://localhost:%d' % _WSGIPort)
        # webbrowser.open_new('http://127.0.0.1:%d' % _WSGIPort)
        # webbrowser.open_new('http://localhost/:%d' % _WSGIPort)
        # webbrowser.open_new('http://localhost:8080')
        # webbrowser.open('http://localhost:8080')
    else:
        lg.out(4, '    SKIP,    LocalWebPort is None')
    
#------------------------------------------------------------------------------ 

def stop_updating():
    global _UpdateFlag
    _UpdateFlag = None

def request_update():
    global _UpdateFlag
    _UpdateFlag = True

def set_updated():
    global _UpdateFlag
    _UpdateFlag = False
    
def get_update_flag():
    global _UpdateFlag
    return _UpdateFlag

#------------------------------------------------------------------------------ 

def on_suppliers_changed(current_suppliers):
    pass
    # sqlio.update_suppliers([], current_suppliers)


def on_tray_icon_command(cmd):
    from main import shutdowner
    from p2p import network_connector
    if cmd == 'exit':
        # SendCommandToGUI('exit')
        shutdowner.A('stop', 'exit')

    elif cmd == 'restart':
        # SendCommandToGUI('exit')
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
        pass
        # SendCommandToGUI('exit')
        
    elif cmd == 'toolbar':
        pass
        # SendCommandToGUI('toolbar')

    else:
        lg.warn('wrong command: ' + str(cmd))    

#------------------------------------------------------------------------------ 

class MyFakedWSGIHandler:
    def __init__(self, original_handler):
        self.orig_handler = original_handler
        
    def __call__(self, environ, start_response):
        # print 'MyFakedWSGIHandler', environ['PATH_INFO']
        return self.orig_handler(environ, start_response)   


class DjangoRootResource(resource.Resource):

    def __init__(self, wsgi_resource):
        resource.Resource.__init__(self)
        self.wsgi_resource = wsgi_resource

    def getChild(self, path, request):
        path0 = request.prepath.pop(0)
        request.postpath.insert(0, path0)
        return self.wsgi_resource

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)
    reactor.callWhenRunning(init)
    reactor.run()
    lg.out(2, 'reactor stopped, EXIT')