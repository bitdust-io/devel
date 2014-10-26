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

if __name__ == '__main__':
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

from logs import lg

from lib import automat
from lib import bpio

#------------------------------------------------------------------------------ 

_Services = {}
_BootUpOrder = []
_EnabledServices = set()

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

def init(callback=None):
    """
    """
    lg.out(2, 'driver.init')
    available_services_dir = os.path.join(bpio.getExecutableDir(), 'services', 'available')
    for filename in os.listdir(available_services_dir):
        if not filename.endswith('.py'):
            continue
        if filename == '__init__.py':
            continue
        # filepath = os.path.join(available_services_dir, filename)
        name = filename[:-3]
        if name in disabled_services():
            continue
        try:
            py_mod = importlib.import_module('services.available.'+name)
        except:
            lg.exc()
            continue
        try:
            services()[name] = py_mod.create_service()
        except:
            lg.exc()
        if services()[name].is_enabled():
            enabled_services().add(name)
    build_order()
    if callback:
        callback()


def shutdown(callback=None):
    """
    """
    lg.out(2, 'driver.shutdown')
    for svc in services().values():
        lg.out(2, '    closing %r' % svc)
        automat.clear_object(svc.index)
    services().clear()
    if callback:
        callback()


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
    #    for svc_name in services().keys():
    #        if svc_name not in enabled_services():
    #            continue
    #        if svc_name not in order:
    #            lg.warn('dependency not satisfied: %s' % svc_name)
    #            continue
    #        for depend_name in services()[svc_name].dependent_on():
    #            if depend_name not in order:
    #                lg.warn('dependency not satisfied: #%d:%s depend on %s' % (
    #                    order.index(svc_name), svc_name, depend_name,))
    #                continue
    #            if order.index(svc_name) < order.index(depend_name):
    #                lg.warn('dependency recursion: #%d:%s depend on #%d:%s' % (
    #                    order.index(svc_name), svc_name, order.index(depend_name), depend_name,))
    _BootUpOrder = order
    return order


def start():
    """
    """
    lg.out(2, 'driver.start')
    run(boot_up_order())
        
        
def stop():
    """
    """
    lg.out(2, 'driver.stop')
    for name in boot_up_order().reverse():
        if name not in enabled_services():
            continue
        svc = services().get(name, None)
        if not svc:
            raise ServiceNotFound(name)
        svc.automat('stop')
        

def run(services_list):
    """
    """
    progress = 0
    for name in services_list:
        svc = services().get(name, None)
        if not svc:
            raise ServiceNotFound(name)
        if not svc.is_enabled():
            continue
        if svc.state == 'ON':
            continue
        # lg.out(8, '    sending "start" to %r' % svc)
        svc.automat('start', service_callback)
        progress += 1
    lg.out(18, 'driver.run services=%d progress=%d' % (len(services_list), progress))
    return progress


def service_callback(service_name, result):
    """
    """
    lg.out(18, 'driver.service_callback %s : [%s]' % (service_name, result))
    svc = services().get(service_name, None)
    if not svc:
        raise ServiceNotFound(service_name)
    if result == 'started':
        lg.out(4, 'service [%s] STARTED' % service_name)
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
                    relative_services.append(other_name)
        if len(relative_services) > 0:
            run(relative_services)

#------------------------------------------------------------------------------ 

class ServiceAlreadyExist(Exception):
    pass

class RequireSubclass(Exception):
    pass

class ServiceNotFound(Exception):
    pass

#------------------------------------------------------------------------------ 

def main():
    lg.set_debug_level(20)
    init()
    print '\n'.join(boot_up_order())
    shutdown()


if __name__ == '__main__':
    main()
    