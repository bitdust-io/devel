#!/usr/bin/env python
# nickname_observer.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (nickname_observer.py) is part of BitDust Software.
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
"""
.. module:: nickname_observer.

.. role:: red

BitDust nickname_observer() Automat

.. raw:: html

    <a href="nickname_observer.png" target="_blank">
    <img src="nickname_observer.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`find-one`
    * :red:`observe-many`
    * :red:`stop`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import sys

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.main import settings

from bitdust.userid import my_id

from bitdust.dht import dht_service
from bitdust.dht import dht_records

#------------------------------------------------------------------------------


def find_one(nickname, attempts=3, results_callback=None):
    if _Debug:
        lg.out(_DebugLevel, 'nickname_observer.find_one %s %d' % (nickname, attempts))
    observer = NicknameObserver(
        name='nickname_observer_%s' % nickname,
        state='AT_STARTUP',
        debug_level=_DebugLevel,
        log_events=_Debug,
        log_transitions=_Debug,
    )
    observer.automat('find-one', (nickname, attempts, results_callback))
    return observer


def observe_many(nickname, attempts=10, results_callback=None):
    if _Debug:
        lg.out(_DebugLevel, 'nickname_observer.observe_many %s %d' % (nickname, attempts))
    observer = NicknameObserver(
        name='nickname_observer_%s' % nickname,
        state='AT_STARTUP',
        debug_level=_DebugLevel,
        log_events=_Debug,
        log_transitions=_Debug,
    )
    observer.automat('observe-many', (nickname, attempts, results_callback))
    return observer


def stop_all():
    for a in automat.objects().values():
        if isinstance(a, NicknameObserver):
            if _Debug:
                lg.out(_DebugLevel, 'nickname_observer.stop_all sends "stop" to %r' % a)
            a.automat('stop')


#------------------------------------------------------------------------------


class NicknameObserver(automat.Automat):

    """
    This class implements all the functionality of the ``nickname_observer()``
    state machine.
    """

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.nickname = None
        self.attempts = None
        self.key = None
        self.dht_read_defer = None
        self.result_callback = None

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'observe-many':
                self.state = 'DHT_LOOP'
                self.doInit(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'find-one':
                self.state = 'DHT_FIND'
                self.doInit(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
        #---DHT_LOOP---
        elif self.state == 'DHT_LOOP':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-read-failed' and self.isMoreAttemptsNeeded(*args, **kwargs):
                self.doNextKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'dht-read-success' and not self.isMoreAttemptsNeeded(*args, **kwargs):
                self.state = 'FINISHED'
                self.doReportNicknameExist(*args, **kwargs)
                self.doReportFinished(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-read-success' and self.isMoreAttemptsNeeded(*args, **kwargs):
                self.doReportNicknameExist(*args, **kwargs)
                self.doNextKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'dht-read-failed' and not self.isMoreAttemptsNeeded(*args, **kwargs):
                self.state = 'FINISHED'
                self.doReportFinished(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---DHT_FIND---
        elif self.state == 'DHT_FIND':
            if event == 'dht-read-success':
                self.state = 'FOUND'
                self.doReportNicknameExist(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-read-failed' and self.isMoreAttemptsNeeded(*args, **kwargs):
                self.doNextKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-read-failed' and not self.isMoreAttemptsNeeded(*args, **kwargs):
                self.state = 'NOT_FOUND'
                self.doReportNicknameNotExist(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---FOUND---
        elif self.state == 'FOUND':
            pass
        #---STOPPED---
        elif self.state == 'STOPPED':
            pass
        #---NOT_FOUND---
        elif self.state == 'NOT_FOUND':
            pass
        #---FINISHED---
        elif self.state == 'FINISHED':
            pass
        return None

    def isMoreAttemptsNeeded(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.attempts > 1

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.nickname, self.attempts, self.result_callback = args[0]
        try:
            nick, index = self.nickname.rsplit(':', 1)
            index = int(index)
        except:
            nick = self.nickname.replace(':', '_')
            index = 0
        self.nickname = nick
        # self.key = nick + ':' + str(number)
        self.key = dht_service.make_key(
            key=self.nickname,
            index=index,
            prefix='nickname',
        )

    def doNextKey(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            key_info = dht_service.split_key(self.key)
            # nik, number = self.key.rsplit(':', 1)
            index = int(key_info['index'])
            # number = int(number)
        except:
            lg.exc()
            index = 0
        index += 1
        # self.key = self.nickname + ':' + str(number)
        self.key = dht_service.make_key(
            key=self.nickname,
            index=index,
            prefix='nickname',
        )
        self.attempts -= 1

    def doDHTReadKey(self, *args, **kwargs):
        """
        Action method.
        """
        if self.dht_read_defer is not None:
            self.dht_read_defer.cancel()
            self.dht_read_defer = None
        self.dht_read_defer = dht_records.get_nickname(self.key)
        self.dht_read_defer.addCallback(self._dht_read_result, self.key)
        self.dht_read_defer.addErrback(self._dht_read_failed)

    def doReportNicknameExist(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'nickname_observer.doReportNicknameExist : (%s, %s)' % (self.key, args[0]))
        if self.result_callback is not None:
            try:
                key_info = dht_service.split_key(self.key)
                nick = key_info['key']
                index = key_info['index']
            except:
                lg.exc()
                nick = self.nickname
                index = 0
            # nik, num = self.key.split(':')
            # num = int(num)
            self.result_callback('exist', nick, index, *args, **kwargs)

    def doReportNicknameNotExist(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'nickname_observer.doReportNicknameNotExist : %s' % self.nickname)
        if self.result_callback is not None:
            self.result_callback('not exist', self.nickname, -1, '')

    def doReportFinished(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'nickname_observer.doReportFinished')
        if self.result_callback is not None:
            self.result_callback('finished', '', -1, '')

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        if self.dht_read_defer is not None:
            self.dht_read_defer.pause()
            self.dht_read_defer.cancel()
            self.dht_read_defer = None
        self.result_callback = None
        self.destroy()

    def _dht_read_result(self, value, key):
        if self.dht_read_defer is None:
            return
        self.dht_read_defer = None
        if not value:
            self.automat('dht-read-failed')
            return
        try:
            v = value['idurl']
        except:
            lg.out(14, '%r' % value)
            lg.exc()
            self.automat('dht-read-failed')
            return
        self.automat('dht-read-success', v)

    def _dht_read_failed(self, x):
        if self.dht_read_defer is None:
            return
        self.automat('dht-read-failed', x)
        self.dht_read_defer = None


#------------------------------------------------------------------------------


def main():
    if len(sys.argv) < 3:
        print('usage: nickname_observer.py <"many"|"one"> <nickname> <attempts>')
        return
    from twisted.internet import reactor  # @UnresolvedImport
    lg.set_debug_level(24)
    settings.init()
    my_id.init()
    dht_service.init(settings.getDHTPort())

    def _result(result, nickname):
        print(result, nickname)
        if result == 'finished':
            reactor.stop()  # @UndefinedVariable

    if sys.argv[1] == 'many':
        observe_many(sys.argv[2], int(sys.argv[3]), results_callback=_result)
    else:
        find_one(sys.argv[2], int(sys.argv[3]), _result)
    reactor.run()  # @UndefinedVariable
    settings.shutdown()


if __name__ == '__main__':
    main()
