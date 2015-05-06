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

from twisted.internet import reactor
from twisted.web import wsgi
from twisted.web import server
from twisted.internet.defer import Deferred

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

from contacts import contactsdb
from contacts import identitydb

import sqlio

#------------------------------------------------------------------------------

_WSGIListener = None
_WSGIPort = None
_UpdateFlag = False

#------------------------------------------------------------------------------

def init():
    global _WSGIListener
    global _WSGIPort
    lg.out(4, 'control.init')
    if _WSGIListener:
        lg.out(4, '    SKIP listener already exist')
        return
    lg.out(4, '    system variable: DJANGO_SETTINGS_MODULE=web.asite.settings')
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.asite.settings")
    sub_path = str(os.path.abspath(os.path.join(bpio.getExecutableDir(), 'web')))
    if not sys.path.count(sub_path):
        lg.out(4, '    new entry added to PYTHON_PATH: %s' % sub_path)
        # sys.path.insert(0, sub_path)

    wsgi_handler = get_wsgi_application()
    wsgi_resource = wsgi.WSGIResource(
        reactor, reactor.getThreadPool(), wsgi_handler)
    site = server.Site(wsgi_resource)
    lg.out(4, '    created WSGI django application handler')
    lg.out(4, '        %s' % wsgi_handler)
    lg.out(4, '        %s' % wsgi_resource)
    res = start_listener(site)

    sqlio.init(django_settings.DATABASES['default']['NAME'])
    contactsdb.SetSuppliersChangedCallback(sqlio.update_suppliers)
    contactsdb.SetCustomersChangedCallback(sqlio.update_customers)
    contactsdb.SetCorrespondentsChangedCallback(sqlio.update_friends)
    identitydb.AddCacheUpdatedCallback(sqlio.update_identities)
    return res

def shutdown():
    global _WSGIListener
    global _WSGIPort
    lg.out(4, 'control.shutdown')
    sqlio.shutdown()
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
    
    def _try(wsgiport, site, result, counter):
        global _WSGIListener
        global _WSGIPort
        if counter > 10:
            wsgiport = random.randint(8001, 8999)
        lg.out(4, '                _try port=%d counter=%d' % (wsgiport, counter))
        try:
            _WSGIListener = reactor.listenTCP(wsgiport, site)
        except:
            lg.out(4, '                _try it seems port %d is busy' % wsgiport)
            _WSGIListener = None
        if _WSGIListener is None:
            reactor.callLater(0.5, _try, wsgiport, site, result, counter+1)
            return
        _WSGIPort = wsgiport
        lg.out(4, '                _try STARTED on port %d' % wsgiport)
        result.callback(wsgiport)

    result = Deferred()
    wsgiport = 8080
    _try(wsgiport, site, result, 0)
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
    sqlio.update_suppliers([], current_suppliers)


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

if __name__ == "__main__":
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)
    reactor.callWhenRunning(init)
    reactor.run()
    lg.out(2, 'reactor stopped, EXIT')