#!/usr/bin/python
# driver.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (driver.py) is part of BitDust Software.
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
..

module:: driver
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import sys
import importlib

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred, DeferredList, succeed, failure  # @UnresolvedImport

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(
        0, _p.abspath(
            _p.join(
                _p.dirname(
                    _p.abspath(
                        sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import config

#------------------------------------------------------------------------------

_Services = {}
_BootUpOrder = []
_EnabledServices = set()
_DisabledServices = set()
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
    global _DisabledServices
    return _DisabledServices


def boot_up_order():
    global _BootUpOrder
    return _BootUpOrder


def is_on(name):
    svc = services().get(name, None)
    if svc is None:
        return False
    return svc.state == 'ON'


def is_off(name):
    svc = services().get(name, None)
    if svc is None:
        return False
    return svc.state == 'OFF' or svc.state == 'NOT_INSTALLED' or svc.state == 'DEPENDS_OFF'


def is_started(name):
    svc = services().get(name, None)
    if svc is None:
        return False
    return svc.state != 'ON' and svc.state != 'OFF' and svc.state != 'NOT_INSTALLED' and svc.state != 'DEPENDS_OFF'


def is_enabled(name):
    svc = services().get(name, None)
    if svc is None:
        return False
    return svc.enabled()


def is_exist(name):
    return name in services()


def is_healthy(service_name):
    result = Deferred()
    svc = services().get(service_name, None)
    if svc is None:
        result.errback(Exception('service %s not found' % service_name))
        return result
    if not svc.enabled():
        result.errback(Exception('service %s is disabled' % service_name))
        return result
    service_health = svc.health_check()
    if isinstance(service_health, Deferred):
        return service_health
    if service_health is True:
        result.callback(True)
    else:
        result.callback(False)
    return result


def dependent(name):
    svc = services().get(name, None)
    if svc is None:
        return []
    return svc.dependent_on()


def affecting(name):
    svc = services().get(name, None)
    if svc is None:
        return []
    results = set()
    order = list(enabled_services())
    for position in range(len(order)):
        child_name = order[position]
        if child_name == name:
            continue
        child = services()[child_name]
        for depend_name in child.dependent_on():
            if depend_name == name:
                results.add(child_name)
    return list(results)


def request(service_name, service_request_payload, request, info):
    svc = services().get(service_name, None)
    if svc is None:
        raise Exception('service %s not found' % service_name)
    try:
        result = svc.request(service_request_payload, request, info)
    except RequireSubclass:
        from p2p import p2p_service
        lg.warn('service %s can not be requested remotely' % service_name)
        return p2p_service.SendFail(request, 'refused')
    except:
        lg.exc()
        return None
    return result


def cancel(service_name, service_cancel_payload, request, info):
    svc = services().get(service_name, None)
    if svc is None:
        raise Exception('service %s not found' % service_name)
    try:
        result = svc.cancel(service_cancel_payload, request, info)
    except RequireSubclass:
        from p2p import p2p_service
        lg.warn('service %s can not be cancelled remotely' % service_name)
        return p2p_service.SendFail(request, 'refused')
    except:
        lg.exc()
        return None
    return result

#------------------------------------------------------------------------------


def init():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'driver.init')
    available_services_dir = os.path.join(bpio.getExecutableDir(), 'services')
    loaded = set()
    for filename in os.listdir(available_services_dir):
        if not filename.endswith('.py') and not filename.endswith('.pyo') and not filename.endswith('.pyc'):
            continue
        if not filename.startswith('service_'):
            continue
        name = str(filename[:filename.rfind('.')])
        if name in loaded:
            continue
        if name in disabled_services():
            if _Debug:
                lg.out(_DebugLevel, '%s is hard disabled' % name)
            continue
        try:
            py_mod = importlib.import_module('services.' + name)
        except:
            if _Debug:
                lg.out(_DebugLevel, '%s exception during module import' % name)
            lg.exc()
            continue
        try:
            services()[name] = py_mod.create_service()
        except:
            if _Debug:
                lg.out(_DebugLevel, '%s exception while creating service instance' % name)
            lg.exc()
            continue
        loaded.add(name)
        if not services()[name].enabled():
            if _Debug:
                lg.out(_DebugLevel, '%s is switched off' % name)
            continue
        enabled_services().add(name)
        if _Debug:
            lg.out(_DebugLevel, '%s initialized' % name)
    build_order()
    config.conf().addCallback('services/', on_service_enabled_disabled)


def shutdown():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'driver.shutdown')
    config.conf().removeCallback('services/')
    while len(services()):
        name, svc = services().popitem()
        # print sys.getrefcount(svc)
        if _Debug:
            lg.out(_DebugLevel, '[%s] CLOSING' % name)
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
        if counter > len(enabled_services()) * len(enabled_services()):
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
                order.insert(depend_position_max + 1, name)
                del order[position]
                progress = True
                break
    _BootUpOrder = order
    return order


def start(services_list=[]):
    """
    """
    global _StartingDeferred
    global _StopingDeferred
    if _StartingDeferred:
        lg.warn('driver.start already called')
        return _StartingDeferred
    if _StopingDeferred:
        d = Deferred()
        d.errback(Exception('currently another service is stopping'))
        return d
    if not services_list:
        services_list.extend(boot_up_order())
    if _Debug:
        lg.out(_DebugLevel, 'driver.start with %d services' % len(services_list))
    dl = []
    for name in services_list:
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
    if len(dl) == 0:
        return succeed(1)
    _StartingDeferred = DeferredList(dl)
    _StartingDeferred.addCallback(on_started_all_services)
    return _StartingDeferred


def stop(services_list=[]):
    """
    """
    global _StopingDeferred
    global _StartingDeferred
    if _StopingDeferred:
        lg.warn('driver.stop already called')
        return _StopingDeferred
    if _StartingDeferred:
        d = Deferred()
        d.errback(Exception('currently another service is starting'))
        return d
    if not services_list:
        services_list.extend(reversed(boot_up_order()))
    if _Debug:
        lg.out(_DebugLevel, 'driver.stop with %d services' % len(services_list))
    dl = []
    for name in services_list:
        svc = services().get(name, None)
        if not svc:
            raise ServiceNotFound(name)
        d = Deferred()
        dl.append(d)
        svc.automat('stop', d)
    _StopingDeferred = DeferredList(dl)
    _StopingDeferred.addCallback(on_stopped_all_services)
    return _StopingDeferred


def restart(service_name, wait_timeout=None):
    """
    """
    global _StopingDeferred
    global _StartingDeferred
    restart_result = Deferred()

    def _on_started(start_result, stop_result, dependencies_results):
        lg.out(4, 'driver.restart._on_started : %s with %s, dependencies_results=%r' % (service_name, start_result, dependencies_results))
        try:
            stop_resp = {stop_result[0][1]: stop_result[0][0], }
        except:
            stop_resp = {'stopped': str(stop_result), }
        try:
            start_resp = {start_result[0][1]: start_result[0][0], }
        except:
            start_resp = {'started': str(start_result), }
        restart_result.callback([stop_resp, start_resp, ])
        return start_result

    def _on_failed(err):
        lg.err(err)
        restart_result.errback(str(err))
        return None

    def _do_start(stop_result=None, dependencies_results=None):
        lg.out(4, 'driver.restart._do_start : %s' % service_name)
        start_defer = start(services_list=[service_name, ])
        start_defer.addCallback(_on_started, stop_result, dependencies_results)
        start_defer.addErrback(_on_failed)
        return start_defer

    def _on_stopped(stop_result, dependencies_results):
        lg.out(4, 'driver.restart._on_stopped : %s with %s' % (service_name, stop_result))
        _do_start(stop_result, dependencies_results)
        return stop_result

    def _do_stop(dependencies_results=None):
        lg.out(4, 'driver.restart._do_stop : %s' % service_name)
        stop_defer = stop(services_list=[service_name, ])
        stop_defer.addCallback(_on_stopped, dependencies_results)
        stop_defer.addErrback(_on_failed)
        return stop_defer

    def _on_timeout(err):
        lg.out(4, 'driver.restart._on_timeout : %s' % service_name)
        all_states = [_svc.state for _svc in services().values()]
        if 'INFLUENCE' in all_states or 'STARTING' in all_states or 'STOPPING' in all_states:
            restart_result.errback(failure.Failure(Exception('timeout')))
            return err
        _do_stop()
        return None

    dl = []
    if _StopingDeferred:
        dl.append(_StopingDeferred)
    if _StartingDeferred:
        dl.append(_StartingDeferred)
    if wait_timeout:
        all_states = [_svc.state for _svc in services().values()]
        if 'INFLUENCE' in all_states or 'STARTING' in all_states or 'STOPPING' in all_states:
            wait_timeout_defer = Deferred()
            wait_timeout_defer.addTimeout(wait_timeout, clock=reactor)
            dl.append(wait_timeout_defer)
    if not dl:
        dl.append(succeed(True))

    lg.out(4, 'driver.restart %s' % service_name)
    dependencies = DeferredList(dl, fireOnOneErrback=True, consumeErrors=True)
    dependencies.addCallback(_do_stop)
    dependencies.addErrback(_on_timeout)
    return restart_result


def start_single(service_name):
    result = Deferred()
    _starting = Deferred()
    _stopping = Deferred()
    
    def _on_started(response):
        if response in ['started', ]:
            return result.callback(True)
        if response in ['not_installed', 'failed', 'depends_off', ]:
            return result.callback(False)
        raise Exception('bad response')

    def _on_stopped(response):
        if response != 'stopped':
            raise Exception('unpredicted response')
        svc.automat('start', _starting)
        return True
        
    _starting.addCallback(_on_started)
    _stopping.addCallback(_on_stopped)
    svc = services().get(service_name, None)
    if not svc:
        return succeed(False)
    if svc.state == 'ON':
        return succeed(True)
    if svc.state in ['STARTING', ]:
        svc.add_callback(_starting)
        return result
    if svc.state in ['STOPPING', 'INFLUENCE', ]:
        svc.add_callback(_stopping)
        return result
    svc.automat('start', _starting)
    return result


def stop_single(service_name):
    result = Deferred()
    _starting = Deferred()
    _stopping = Deferred()

    def _on_stopped(response):
        if response != 'stopped':
            raise Exception('unpredicted response')
        return result.callback(True)

    def _on_started(response):
        if response in ['started', ]:
            svc.automat('stop', _stopping)
            return True
        if response in ['not_installed', 'failed', 'depends_off', ]:
            return result.callback(True)
        raise Exception('bad response')

    _starting.addCallback(_on_started)
    _stopping.addCallback(_on_stopped)
    svc = services().get(service_name, None)
    if not svc:
        return succeed(False)
    if svc.state == 'OFF':
        return succeed(True)
    if svc.state in ['STARTING', ]:
        svc.add_callback(_starting)
        return result
    if svc.state in ['STOPPING', 'INFLUENCE', ]:
        svc.add_callback(_stopping)
        return result
    svc.automat('stop', _stopping)
    return result


def health_check(services_list=[]):
    if not services_list:
        services_list.extend(reversed(boot_up_order()))
    if _Debug:
        lg.out(_DebugLevel, 'driver.health_check with %d services' % len(services_list))
    dl = []
    for name in services_list:
        svc = services().get(name, None)
        if not svc:
            continue
        service_health = svc.health_check()
        if isinstance(service_health, Deferred):
            dl.append(service_health)
        else:
            d = Deferred()
            d.callback(bool(service_health))
            dl.append(service_health)
    health_result = DeferredList(dl, consumeErrors=True)
    return health_result


#     def _on_started(start_result):
#         lg.out(4, 'api.start_later._on_started : %s with %s' % (services_list, start_result))
#         result.callback(start_result)
#         return start_result
# 
#     def _on_failed(err):
#         print 'start_later._on_failed'
#         lg.err(err)
#         result.errback(str(err))
#         return None
# 
#     def _do_start(x=None):
#         lg.out(4, 'driver.start_later._do_start : %s' % services_list)
#         start_defer = start(services_list=services_list)
#         start_defer.addCallback(_on_started)
#         start_defer.addErrback(_on_failed)
#         return start_defer
# 
#     lg.out(4, 'driver.start_later %s' % services_list)
# 
#     if _StopingDeferred:
#         _StopingDeferred.addCallback(_do_start)
#         _StopingDeferred.addErrback(_on_failed)
#         lg.warn('driver.stop already called, added pending callback')
#         return result
#     
#     if _StartingDeferred:
#         _StartingDeferred.addCallback(_do_start)
#         _StartingDeferred.addErrback(_on_failed)
#         lg.warn('driver.start already called, added pending callback')
#         return result
# 
#     _do_start()
#     return result

#     def _on_timeout(err):
#         lg.out(4, 'driver.start_later._on_timeout : %s' % services_list)
#         all_states = [_svc.state for _svc in services().values()]
#         if 'INFLUENCE' in all_states or 'STARTING' in all_states or 'STOPPING' in all_states:
#             result.errback(failure.Failure(Exception('timeout')))
#             return err
#         _do_start()
#         return None

#     dl = []
#     if _StopingDeferred:
#         dl.append(_StartingDeferred)
#     if _StartingDeferred:
#         dl.append(_StartingDeferred)
#     if wait_timeout:
#         all_states = [_svc.state for _svc in services().values()]
#         if 'INFLUENCE' in all_states or 'STARTING' in all_states or 'STOPPING' in all_states:
#             wait_timeout_defer = Deferred()
#             wait_timeout_defer.addTimeout(wait_timeout, clock=reactor)
#             dl.append(wait_timeout_defer)
#     if not dl:
#         dl.append(succeed(True))
# 
#     lg.out(4, 'driver.start_later %s' % services_list)
#     dependencies = DeferredList(dl, fireOnOneErrback=True, consumeErrors=True)
#     dependencies.addCallback(_do_start)
#     dependencies.addErrback(_on_timeout)
#     return result


# def stop_later(services_list):
#     global _StopingDeferred
#     global _StartingDeferred
#     result = Deferred()
# 
#     def _on_stopped(stop_result):
#         lg.out(4, 'driver.stop_later._on_stopped : %s with %s' % (services_list, stop_result))
#         result.callback(stop_result)
#         return stop_result
# 
#     def _on_failed(err):
#         print 'stop_later._on_failed'
#         lg.err(err)
#         result.errback(str(err))
#         return None
# 
#     def _do_stop(x=None):
#         lg.out(4, 'driver.stop_later._do_stop : %s' % services_list)
#         stop_defer = stop(services_list=services_list)
#         stop_defer.addCallback(_on_stopped)
#         stop_defer.addErrback(_on_failed)
#         return None
# 
#     lg.out(4, 'driver.stop_later %s' % services_list)
# 
#     if _StopingDeferred:
#         _StopingDeferred.addCallback(_do_stop)
#         _StopingDeferred.addErrback(_on_failed)
#         lg.warn('driver.stop already called, added pending callback')
#         return result
#     
#     if _StartingDeferred:
#         _StartingDeferred.addCallback(_do_stop)
#         _StartingDeferred.addErrback(_on_failed)
#         lg.warn('driver.start already called, added pending callback')
#         return result
# 
#     _do_stop()
#     return result

#     dl = []
#     if _StopingDeferred:
#         dl.append(_StartingDeferred)
#     if _StartingDeferred:
#         dl.append(_StartingDeferred)
#     if wait_timeout:
#         all_states = [_svc.state for _svc in services().values()]
#         if 'INFLUENCE' in all_states or 'STARTING' in all_states or 'STOPPING' in all_states:
#             wait_timeout_defer = Deferred()
#             wait_timeout_defer.addTimeout(wait_timeout, clock=reactor)
#             dl.append(wait_timeout_defer)
#     if not dl:
#         dl.append(succeed(True))
# 
#     lg.out(4, 'driver.stop_later %s' % services_list)
#     dependencies = DeferredList(dl, fireOnOneErrback=True, consumeErrors=True)
#     dependencies.addCallback(_do_stop)
#     dependencies.addErrback(_on_timeout)
#     return result
    

#------------------------------------------------------------------------------


def on_service_callback(result, service_name):
    """
    """
    if _Debug:
        lg.out(_DebugLevel +
               8, 'driver.on_service_callback %s : [%s]' %
               (service_name, result))
    svc = services().get(service_name, None)
    if not svc:
        raise ServiceNotFound(service_name)
    if result == 'started':
        if _Debug:
            lg.out(_DebugLevel, '[%s] STARTED' % service_name)
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
        if _Debug:
            lg.out(_DebugLevel, '[%s] STOPPED' % service_name)
        for depend_name in svc.dependent_on():
            depend_service = services().get(depend_name, None)
            if not depend_service:
                raise ServiceNotFound(depend_name)
            depend_service.automat('depend-service-stopped')
    return result


def on_started_all_services(results):
    if _Debug:
        lg.out(_DebugLevel, 'driver.on_started_all_services')
    global _StartingDeferred
    _StartingDeferred = None
    return results


def on_stopped_all_services(results):
    if _Debug:
        lg.out(_DebugLevel, 'driver.on_stopped_all_services')
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
    from main import settings
    lg.set_debug_level(20)
    settings.init()
    init()
    # print '\n'.join(_BootUpOrder)
    shutdown()


if __name__ == '__main__':
    main()
