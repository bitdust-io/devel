#!/usr/bin/python
# local_service.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (local_service.py) is part of BitDust Software.
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
.. module:: local_service.

.. role:: red

BitDust local_service() Automat

.. raw:: html

    <a href="local_service.png" target="_blank">
    <img src="local_service.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`depend-service-stopped`
    * :red:`service-depend-off`
    * :red:`service-failed`
    * :red:`service-not-installed`
    * :red:`service-started`
    * :red:`service-stopped`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.services import driver

#------------------------------------------------------------------------------


class LocalService(automat.Automat):

    """
    This class implements all the functionality of the ``local_service()``
    state machine.
    """

    fast = False
    suspended = False

    service_name = ''
    config_path = ''
    data_dir_required = False
    stop_when_failed = False
    start_suspended = False

    def __init__(self):
        if not self.service_name:
            raise driver.RequireSubclass()
        if self.service_name in list(driver.services().keys()):
            raise driver.ServiceAlreadyExist(self.service_name)
        self.result_deferred = None
        if self.data_dir_required:
            my_data_dir_path = self.data_dir_path()
            if not os.path.isdir(my_data_dir_path):
                os.makedirs(my_data_dir_path)
        automat.Automat.__init__(
            self,
            name=self.service_name,
            state='OFF',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )

    def to_json(self, short=True):
        j = super().to_json(short=short)
        j.update({
            'name': self.service_name,
            'enabled': self.enabled(),
            'installed': self.installed(),
            'config_path': self.config_path,
            'depends': self.dependent_on(),
        })
        return j

    #------------------------------------------------------------------------------

    def dependent_on(self):
        return []

    def installed(self):
        return True

    def enabled(self):
        from bitdust.main import config
        return config.conf().getBool(self.config_path)

    def start(self):
        raise driver.RequireSubclass()

    def stop(self):
        raise driver.RequireSubclass()

    def suspend(self, *args, **kwargs):
        if self.suspended:
            raise driver.ServiceAlreadySuspended()
        ret = self.on_suspend(*args, **kwargs)
        if ret is not None:
            self.suspended = True
        return ret

    def resume(self, *args, **kwargs):
        if not self.suspended:
            raise driver.ServiceWasNotSuspended()
        ret = self.on_resume(*args, **kwargs)
        if ret is not None:
            self.suspended = False
        return ret

    def request(self, json_payload, newpacket, info):
        raise driver.RequireSubclass()

    def cancel(self, json_payload, newpacket, info):
        raise driver.RequireSubclass()

    def on_suspend(self, *args, **kwargs):
        return True

    def on_resume(self, *args, **kwargs):
        return True

    def health_check(self):
        return True

    def network_configuration(self):
        return None

    def attached_dht_layers(self):
        return []

    def add_callback(self, cb):
        if not self.result_deferred:
            self.result_deferred = Deferred()
        if isinstance(cb, Deferred):
            self.result_deferred.addCallback(cb.callback)
        else:
            self.result_deferred.addCallback(lambda *a, **kw: cb(*a, **kw))
        return self.result_deferred

    def data_dir_path(self):
        from bitdust.main import settings
        return settings.ServiceDir(self.service_name)

    #------------------------------------------------------------------------------

    def A(self, event, *args, **kwargs):
        #---ON---
        if self.state == 'ON':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopService(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop':
                self.state = 'INFLUENCE'
                self.doSetCallback(*args, **kwargs)
                self.doStopDependentServices(*args, **kwargs)
        #---OFF---
        elif self.state == 'OFF':
            if event == 'stop':
                self.doSetCallback(*args, **kwargs)
                self.doNotifyStopped(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'start':
                self.state = 'STARTING'
                self.NeedStart = False
                self.NeedStop = False
                self.doSetCallback(*args, **kwargs)
                self.doStartService(*args, **kwargs)
        #---NOT_INSTALLED---
        elif self.state == 'NOT_INSTALLED':
            if event == 'stop':
                self.doSetCallback(*args, **kwargs)
                self.doNotifyNotInstalled(*args, **kwargs)
            elif event == 'start':
                self.state = 'STARTING'
                self.doSetCallback(*args, **kwargs)
                self.doStartService(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---INFLUENCE---
        elif self.state == 'INFLUENCE':
            if event == 'start':
                self.doSetCallback(*args, **kwargs)
                self.NeedStart = True
            elif event == 'stop':
                self.doSetCallback(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopService(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'depend-service-stopped' and self.isAllDependsStopped(*args, **kwargs) and self.NeedStart:
                self.state = 'STARTING'
                self.NeedStart = False
                self.doStopService(*args, **kwargs)
                self.doNotifyStopped(*args, **kwargs)
                self.doStartService(*args, **kwargs)
            elif event == 'depend-service-stopped' and self.isAllDependsStopped(*args, **kwargs) and not self.NeedStart:
                self.state = 'STOPPING'
                self.doStopService(*args, **kwargs)
        #---STARTING---
        elif self.state == 'STARTING':
            if event == 'stop':
                self.doSetCallback(*args, **kwargs)
                self.NeedStop = True
            elif event == 'start':
                self.doSetCallback(*args, **kwargs)
            elif event == 'service-started' and self.NeedStop:
                self.state = 'INFLUENCE'
                self.NeedStop = False
                self.doStopDependentServices(*args, **kwargs)
            elif event == 'service-failed':
                self.state = 'OFF'
                self.doNotifyFailed(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopService(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'service-not-installed':
                self.state = 'NOT_INSTALLED'
                self.doNotifyNotInstalled(*args, **kwargs)
            elif event == 'service-depend-off':
                self.state = 'DEPENDS_OFF'
                self.doNotifyDependsOff(*args, **kwargs)
            elif event == 'service-started' and not self.NeedStop:
                self.state = 'ON'
                self.doNotifyStarted(*args, **kwargs)
        #---DEPENDS_OFF---
        elif self.state == 'DEPENDS_OFF':
            if event == 'stop':
                self.doSetCallback(*args, **kwargs)
                self.doNotifyDependsOff(*args, **kwargs)
            elif event == 'start':
                self.state = 'STARTING'
                self.doSetCallback(*args, **kwargs)
                self.doStartService(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---STOPPING---
        elif self.state == 'STOPPING':
            if event == 'start':
                self.doSetCallback(*args, **kwargs)
                self.NeedStart = True
            elif event == 'service-stopped':
                self.state = 'OFF'
                self.doNotifyStopped(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isAllDependsStopped(self, *args, **kwargs):
        """
        Condition method.
        """
        for svc in driver.services().values():
            if self.service_name in svc.dependent_on():
                if svc.state != 'OFF' and svc.state != 'DEPENDS_OFF' and svc.state != 'NOT_INSTALLED':
                    if _Debug:
                        lg.out(_DebugLevel, '    dependent %r not stopped yet, %r will have to wait' % (svc, self))
                    return False
        return True

    def doStartService(self, *args, **kwargs):
        """
        Action method.
        """
        if not self.installed():
            self.automat('service-not-installed')
            return
        depends_results = []
        for depend_name in self.dependent_on():
            depend_service = driver.services().get(depend_name, None)
            if depend_service is None:
                depends_results.append((depend_name, 'not found'))
                continue
            if depend_service.state != 'ON':
                depends_results.append((depend_name, 'not started'))
                continue
        if len(depends_results) > 0:
            self.automat('service-depend-off', depends_results)
            return
        if _Debug:
            lg.out(_DebugLevel, '[%s] STARTING' % self.service_name)
        self.suspended = bool(self.start_suspended)
        try:
            result = self._do_start()
        except Exception as exc:
            lg.exc()
            self.automat('service-failed', exc)
            return
        if isinstance(result, Deferred):
            result.addCallback(lambda x: self.automat('service-started'))
            result.addErrback(lambda err: self.automat('service-failed', err))
            return
        if result:
            self.automat('service-started')
        else:
            lg.warn('failed to start %r, result from .start() method is %r' % (self, result))
            self.automat('service-failed', Exception('service %r failed to start' % self))

    def doStopService(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, '[%s] STOPPING' % self.service_name)
        self.suspended = False
        try:
            result = self._do_stop()
        except:
            lg.exc()
            self.automat('service-stopped', 'exception during stopping [%s]' % self.service_name)
            return
        if isinstance(result, Deferred):
            result.addBoth(lambda x: self.automat('service-stopped', x))
        else:
            self.automat('service-stopped', result)

    def doSetCallback(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0]:
            self.add_callback(args[0])

    def doStopDependentServices(self, *args, **kwargs):
        """
        Action method.
        """
        count = 0
        for svc in driver.services().values():
            if self.service_name in svc.dependent_on():
                if _Debug:
                    lg.out(_DebugLevel, '%r sends "stop" to %r' % (self, svc))
                if svc.installed():
                    svc.automat('stop')
                    count += 1
        if count == 0:
            self.automat('depend-service-stopped')

    def doNotifyStarted(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, service=self, result='started')
        if self.result_deferred:
            self.result_deferred.callback('started')
            self.result_deferred = None
        driver.on_service_callback('started', self.service_name)

    def doNotifyStopped(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, service=self, result='stopped')
        if self.result_deferred:
            self.result_deferred.callback('stopped')
            self.result_deferred = None
        driver.on_service_callback('stopped', self.service_name)

    def doNotifyNotInstalled(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, service=self, result='not_installed')
        if self.result_deferred:
            self.result_deferred.callback('not_installed')
            self.result_deferred = None
        driver.on_service_callback('not_installed', self.service_name)

    def doNotifyFailed(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, service=self, result='failed')
        if self.stop_when_failed:
            try:
                self.stop()
            except:
                lg.exc()
        if self.result_deferred:
            self.result_deferred.callback('failed')
            self.result_deferred = None
        driver.on_service_callback('failed', self.service_name)

    def doNotifyDependsOff(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, service=self, result='depends_off')
        if self.result_deferred:
            self.result_deferred.callback('depends_off')
            self.result_deferred = None
        driver.on_service_callback('depends_off', self.service_name)

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.result_deferred = None
        self.destroy()

    def _do_start(self):
        return self.start()

    def _do_stop(self):
        return self.stop()


#------------------------------------------------------------------------------


class SlowStartingLocalService(LocalService):

    def _do_start(self, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, service_name=self.service_name)
        if getattr(self, 'starting_deferred', None):
            raise Exception('service already starting')
        self.starting_deferred = Deferred()
        self.starting_deferred.addErrback(lambda err: lg.warn('service %r was not started: %r' % (self.service_name, err.getErrorMessage() if err else 'unknown reason')))
        return self.start()

    def _do_stop(self):
        if _Debug:
            lg.args(_DebugLevel, service_name=self.service_name)
        if self.starting_deferred:
            if not self.starting_deferred.called:
                self.starting_deferred.errback(Exception('service was stopped before starting process finished'))
            self.starting_deferred = None
        return self.stop()

    def confirm_service_started(self, result=True):
        if _Debug:
            lg.args(_DebugLevel, service_name=self.service_name, result=result, starting_deferred=self.starting_deferred)
        ret = None
        if self.starting_deferred:
            if not self.starting_deferred.called:
                if result is True:
                    self.starting_deferred.callback(True)
                else:
                    if isinstance(result, Exception):
                        self.starting_deferred.errback(result)
                    else:
                        self.starting_deferred.callback(result)
            ret = self.starting_deferred
            self.starting_deferred = None
        return ret
