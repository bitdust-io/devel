#!/usr/bin/python
#driver.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: driver

"""

import os
import sys
import importlib

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList 

if __name__ == '__main__':
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

from logs import lg

from lib import bpio
from lib import config

#------------------------------------------------------------------------------ 

_Services = {}
_BootUpOrder = []
_EnabledServices = set()
_StartingDeferred = None
_StopingDeferred = None

#------------------------------------------------------------------------------ 

def services():
    """
    """
    global _Services
    return _Services

def enabled_services():
    global _EnabledServices
    return _EnabledServices

def disabled_services():
    return set()
    
def boot_up_order():
    global _BootUpOrder
    return _BootUpOrder
    
def is_started(name):
    svc = services().get(name, None)
    if svc is None:
        return False
    return svc.state == 'ON'

def is_exist(name):
    return services().has_key(name)

#------------------------------------------------------------------------------ 

def init():
    """
    """
    lg.out(2, 'driver.init')
    available_services_dir = os.path.join(bpio.getExecutableDir(), 'services')
    for filename in os.listdir(available_services_dir):
        if not filename.endswith('.py'):
            continue
        if not filename.startswith('service_'):
            continue
        name = filename[:-3]
        if name in disabled_services():
            continue
        try:
            py_mod = importlib.import_module('services.'+name)
        except:
            lg.exc()
            continue
        try:
            services()[name] = py_mod.create_service()
        except:
            lg.exc() 
        if services()[name].enabled():
            enabled_services().add(name)
    # print '\n'.join(enabled_services())
    build_order()
    config.conf().addCallback('services/', on_service_enabled_disabled)


def shutdown():
    """
    """
    lg.out(2, 'driver.shutdown')
    config.conf().removeCallback('services/')
    while len(services()):
        name, svc = services().popitem()
        # print sys.getrefcount(svc) 
        lg.out(2, '[%s] CLOSING' % name)
        svc.automat('shutdown')
        del svc
        svc = None
        enabled_services().discard(name)


def build_order():
    """
    """
    global _BootUpOrder
    order = list(enabled_services())
    progress = True
    fail = False
    counter = 0
    while progress and not fail:
        progress = False
        counter += 1
        if counter > len(enabled_services())*len(enabled_services()):
            lg.warn('dependency recursion')
            fail = True
            break
        for position in range(len(order)):
            name = order[position]
            svc = services()[name]
            depend_position_max = -1 
            for depend_name in svc.dependent_on():
                if depend_name not in order:
                    fail = True
                    lg.warn('dependency not satisfied: #%d:%s depend on %s' % (
                        position, name, depend_name,))
                    break
                depend_position = order.index(depend_name)
                if depend_position > depend_position_max:
                    depend_position_max = depend_position
            if fail:
                break
            if position < depend_position_max: 
                # print name, order[depend_position_max] 
                order.insert(depend_position_max+1, name)
                del order[position]
                progress = True
                break
    _BootUpOrder = order
    return order


def start():
    """
    """
    global _StartingDeferred
    if _StartingDeferred:
        lg.warn('driver.start already called')
        return _StartingDeferred
    lg.out(2, 'driver.start')
    dl = []
    for name in boot_up_order():
        svc = services().get(name, None)
        if not svc:
            raise ServiceNotFound(name)
        if not svc.enabled():
            continue
        if svc.state == 'ON':
            continue
        d = Deferred()
        dl.append(d)
        svc.automat('start', d)
    _StartingDeferred = DeferredList(dl)
    _StartingDeferred.addCallback(on_started_all_services)
    return _StartingDeferred

        
def stop():
    """
    """
    global _StopingDeferred
    if _StopingDeferred:
        lg.warn('driver.stop already called')
        return _StopingDeferred
    lg.out(2, 'driver.stop')
    dl = []
    for name in reversed(boot_up_order()):
        svc = services().get(name, None)
        if not svc:
            raise ServiceNotFound(name)
        d = Deferred()
        dl.append(d)
        svc.automat('stop', d)
    _StopingDeferred = DeferredList(dl)
    _StopingDeferred.addCallback(on_stopped_all_services)
    return _StopingDeferred

#------------------------------------------------------------------------------ 

def on_service_callback(result, service_name):
    """
    """
    lg.out(14, 'driver.on_service_callback %s : [%s]' % (service_name, result))
    svc = services().get(service_name, None)
    if not svc:
        raise ServiceNotFound(service_name)
    if result == 'started':
        lg.out(2, '[%s] STARTED' % service_name)
        relative_services = []
        for other_name in services().keys():
            if other_name == service_name:
                continue
            other_service = services().get(other_name, None)
            if not other_service:
                raise ServiceNotFound(other_name)
            if other_service.state == 'ON':
                continue
            for depend_name in other_service.dependent_on():
                if depend_name == service_name:
                    relative_services.append(other_service)
        if len(relative_services) > 0:
            # global _StartingDeferred
            # if _StartingDeferred:
            for relative_service in relative_services:
                if not relative_service.enabled():
                    continue
                if relative_service.state == 'ON':
                    continue
                relative_service.automat('start')
    elif result == 'stopped':
        lg.out(2, '[%s] STOPPED' % service_name)
        for depend_name in svc.dependent_on():
            depend_service = services().get(depend_name, None)
            if not depend_service:
                raise ServiceNotFound(depend_name)
            depend_service.automat('depend-service-stopped')
    return result

def on_started_all_services(results):
    lg.out(2, 'driver.on_started_all_services')
    global _StartingDeferred
    _StartingDeferred = None
    return results
    
def on_stopped_all_services(results):
    lg.out(2, 'driver.on_stopped_all_services')
    global _StopingDeferred
    _StopingDeferred = None
    return results

def on_service_enabled_disabled(path, newvalue, oldvalue, result):
    if not result:
        return
    if not path.endswith('/enabled'):
        return
    svc_name = path.replace('services/', 'service_').replace('/enabled', '').replace('-', '_')
    svc = services().get(svc_name, None) 
    if svc:
        if newvalue == 'true':
            svc.automat('start')
        else:
            svc.automat('stop')
    else:
        lg.warn('%s not found: %s' % (svc_name, path))    

#------------------------------------------------------------------------------ 

class ServiceAlreadyExist(Exception):
    pass

class RequireSubclass(Exception):
    pass

class ServiceNotFound(Exception):
    pass

#------------------------------------------------------------------------------ 

def main():
    from lib import settings
    lg.set_debug_level(20)
    settings.init()
    init()
    # print '\n'.join(_BootUpOrder)
    shutdown()


if __name__ == '__main__':
    main()
    