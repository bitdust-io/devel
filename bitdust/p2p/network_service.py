#!/usr/bin/python
# network_service.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (network_service.py) is part of BitDust Software.
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
.. module:: network_service.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.services import driver

from bitdust.interface import api

from bitdust.userid import my_id

#------------------------------------------------------------------------------


def do_service_test(service_name, result_defer, wait_timeout):
    try:
        svc_info = api.service_info(service_name)
        if not svc_info or 'result' not in svc_info:
            lg.err('failed to fetch service info: %r' % svc_info)
            result_defer.callback(dict(
                error='disconnected',
                reason='{}_info_error'.format(service_name),
            ))
            return None
        svc_state = svc_info['result']['state']
    except:
        lg.exc('service "%s" test failed' % service_name)
        result_defer.callback(dict(
            error='disconnected',
            reason='{}_info_error'.format(service_name),
        ))
        return None
    if _Debug:
        lg.args(_DebugLevel, service=service_name, state=svc_state, wait_timeout=wait_timeout)
    if svc_state == 'STARTING':
        reactor.callLater(0.1, do_service_test, service_name, result_defer, wait_timeout)  # @UndefinedVariable
        return None
    if svc_state != 'ON':
        do_service_restart(service_name, result_defer, wait_timeout)
        return None
    if service_name == 'service_network':
        reactor.callLater(0, do_service_test, 'service_gateway', result_defer, wait_timeout)  # @UndefinedVariable
    elif service_name == 'service_gateway':
        reactor.callLater(0, do_service_test, 'service_p2p_hookups', result_defer, wait_timeout)  # @UndefinedVariable
    elif service_name == 'service_p2p_hookups':
        reactor.callLater(0, do_p2p_connector_test, result_defer)  # @UndefinedVariable
    elif service_name == 'service_proxy_transport':
        reactor.callLater(0, do_service_proxy_transport_test, result_defer)  # @UndefinedVariable
    else:
        raise Exception('unknown service to test %s' % service_name)
    return None


def do_service_restart(service_name, result_defer, wait_timeout):
    if _Debug:
        lg.args(_DebugLevel, service_name=service_name)
    d = api.service_restart(service_name, wait_timeout=wait_timeout)
    d.addCallback(on_service_restarted, service_name, result_defer, wait_timeout)
    d.addErrback(lambda err: result_defer.callback(dict(
        error=err,
        reason='{}_restart_error'.format(service_name),
    ), ))
    return None


def do_service_proxy_transport_test(result_defer):
    if _Debug:
        lg.dbg(_DebugLevel, 'checking proxy_transport')
    if not driver.is_enabled('service_proxy_transport'):
        result_defer.callback({
            'service_network': 'started',
            'service_gateway': 'started',
            'service_p2p_hookups': 'started',
            'service_proxy_transport': 'disabled',
        })
        return None
    try:
        proxy_receiver_lookup = automat.find('proxy_receiver')
        if not proxy_receiver_lookup:
            lg.warn('disconnected, reason is "proxy_receiver_not_found"')
            result_defer.callback(dict(
                error='disconnected',
                reason='proxy_receiver_not_found',
            ))
            return None
        proxy_receiver_machine = automat.by_index(proxy_receiver_lookup[0])
        if not proxy_receiver_machine:
            lg.warn('disconnected, reason is "proxy_receiver_not_exist"')
            result_defer.callback(dict(
                error='disconnected',
                reason='proxy_receiver_not_exist',
            ))
            return None
        if proxy_receiver_machine.state != 'LISTEN':
            lg.warn('disconnected, reason is "proxy_receiver_disconnected", sending "start" event to proxy_receiver()')
            proxy_receiver_machine.automat('start')
            result_defer.callback(dict(
                error='disconnected',
                reason='proxy_receiver_disconnected',
            ))
            return None
        result_defer.callback({
            'service_network': 'started',
            'service_gateway': 'started',
            'service_p2p_hookups': 'started',
            'service_proxy_transport': 'started',
            'proxy_receiver_state': proxy_receiver_machine.state,
        })
    except:
        lg.exc()
        result_defer.callback(dict(
            error='disconnected',
            reason='proxy_receiver_error',
        ))
    return None


def do_p2p_connector_test(result_defer):
    if _Debug:
        lg.dbg(_DebugLevel, 'checking p2p_connector')
    try:
        p2p_connector_lookup = automat.find('p2p_connector')
        if not p2p_connector_lookup:
            lg.warn('disconnected, reason is "p2p_connector_not_found"')
            result_defer.callback(dict(
                error='disconnected',
                reason='p2p_connector_not_found',
            ))
            return None
        p2p_connector_machine = automat.by_index(p2p_connector_lookup[0])
        if not p2p_connector_machine:
            lg.warn('disconnected, reason is "p2p_connector_not_exist"')
            result_defer.callback(dict(
                error='disconnected',
                reason='p2p_connector_not_exist',
            ))
            return None
        if p2p_connector_machine.state in [
            'DISCONNECTED',
        ]:
            lg.warn('disconnected, reason is "p2p_connector_disconnected", sending "check-synchronize" event to p2p_connector()')
            p2p_connector_machine.automat('check-synchronize')
            result_defer.callback(dict(
                error='disconnected',
                reason='p2p_connector_disconnected',
            ))
            return None
        do_service_proxy_transport_test(result_defer)
    except:
        lg.exc()
        result_defer.callback(dict(
            error='disconnected',
            reason='p2p_connector_error',
        ))
    return None


#------------------------------------------------------------------------------


def on_service_restarted(resp, service_name, result_defer, wait_timeout):
    if _Debug:
        lg.args(_DebugLevel, resp=resp, service_name=service_name)
    if service_name == 'service_network':
        do_service_test('service_gateway', result_defer, wait_timeout)
    elif service_name == 'service_gateway':
        do_service_test('service_p2p_hookups', result_defer, wait_timeout)
    else:
        do_p2p_connector_test(result_defer)
    return resp


def on_service_proxy_transport_check_healthy(healthy, wait_timeout):
    if _Debug:
        lg.args(_DebugLevel, healthy=healthy)
    if healthy is True:
        return None
    lg.err('service_proxy_transport is not healthy, going to restart it now')
    d = Deferred()
    d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='network_service.on_service_proxy_transport_check_healthy', ignore=True)
    do_service_restart('service_proxy_transport', d, wait_timeout=wait_timeout)
    return None


#------------------------------------------------------------------------------


def connected(wait_timeout=5):
    ret = Deferred()

    if driver.is_enabled('service_proxy_transport'):
        p2p_connector_lookup = automat.find('p2p_connector')
        if p2p_connector_lookup:
            p2p_connector_machine = automat.by_index(p2p_connector_lookup[0])
            if p2p_connector_machine and p2p_connector_machine.state == 'CONNECTED':
                proxy_receiver_lookup = automat.find('proxy_receiver')
                if proxy_receiver_lookup:
                    proxy_receiver_machine = automat.by_index(proxy_receiver_lookup[0])
                    if proxy_receiver_machine and proxy_receiver_machine.state == 'LISTEN':
                        # service_proxy_transport() is enabled, proxy_receiver() is listening: all good
                        wait_timeout_defer = Deferred()
                        wait_timeout_defer.addBoth(
                            lambda _: ret.
                            callback({
                                'service_network': 'started',
                                'service_gateway': 'started',
                                'service_p2p_hookups': 'started',
                                'service_proxy_transport': 'started',
                                'proxy_receiver_state': proxy_receiver_machine.state,
                            }),
                        )
                        if not wait_timeout:
                            wait_timeout = 0.01
                        wait_timeout_defer.addTimeout(wait_timeout, clock=reactor)
                        return ret
                else:
                    d = driver.is_healthy('service_proxy_transport')
                    d.addCallback(on_service_proxy_transport_check_healthy, wait_timeout=wait_timeout)
                    d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='network_service.connected', ignore=True)
                    lg.warn('disconnected, reason is proxy_receiver() not started yet')
                    ret.callback(dict(
                        error='disconnected',
                        reason='proxy_receiver_not_started',
                    ))
                    return ret

    if not my_id.isLocalIdentityReady():
        lg.warn('local identity is not valid or not exist')
        ret.callback(dict(
            error='local identity is not valid or not exist',
            reason='identity_not_exist',
        ))
        return ret
    if not driver.is_enabled('service_network'):
        lg.warn('service_network() is disabled')
        ret.callback(dict(
            error='service_network() is disabled',
            reason='service_network_disabled',
        ))
        return ret
    if not driver.is_enabled('service_gateway'):
        lg.warn('service_gateway() is disabled')
        ret.callback(dict(
            error='service_gateway() is disabled',
            reason='service_gateway_disabled',
        ))
        return ret
    if not driver.is_enabled('service_p2p_hookups'):
        lg.warn('service_p2p_hookups() is disabled')
        ret.callback(dict(
            error='service_p2p_hookups() is disabled',
            reason='service_p2p_hookups_disabled',
        ))
        return ret

    do_service_test('service_network', ret, wait_timeout)
    return ret
