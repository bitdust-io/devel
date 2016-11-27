#!/usr/bin/env python
# nickname_observer.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

import sys

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from main import settings

from userid import my_id

from dht import dht_service

#------------------------------------------------------------------------------

_NicknameObserver = None

#------------------------------------------------------------------------------


def find_one(nickname, attempts=3, results_callback=None):
    """
    
    """
    lg.out(12, 'nickname_observer.find_one %s %d' % (nickname, attempts))
    observer = NicknameObserver('%s_observer' % nickname, 'AT_STARTUP', 2)
    observer.automat('find-one', (nickname, attempts, results_callback))
    return observer


def observe_many(nickname, attempts=10, results_callback=None):
    """
    
    """
    lg.out(12, 'nickname_observer.observe_many %s %d' % (nickname, attempts))
    observer = NicknameObserver('%s_observer' % nickname, 'AT_STARTUP', 2)
    observer.automat('observe-many', (nickname, attempts, results_callback))
    return observer


def stop_all():
    """
    
    """
    for a in automat.objects().values():
        if isinstance(a, NicknameObserver):
            lg.out(12, 'nickname_observer.stop_all sends "stop" to %r' % a)
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
        self.log_events = True

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'observe-many':
                self.state = 'DHT_LOOP'
                self.doInit(arg)
                self.doDHTReadKey(arg)
            elif event == 'find-one':
                self.state = 'DHT_FIND'
                self.doInit(arg)
                self.doDHTReadKey(arg)
        #---DHT_LOOP---
        elif self.state == 'DHT_LOOP':
            if event == 'stop':
                self.state = 'STOPPED'
                self.doDestroyMe(arg)
            elif event == 'dht-read-failed' and self.isMoreAttemptsNeeded(arg):
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'dht-read-success' and not self.isMoreAttemptsNeeded(arg):
                self.state = 'FINISHED'
                self.doReportNicknameExist(arg)
                self.doReportFinished(arg)
                self.doDestroyMe(arg)
            elif event == 'dht-read-success' and self.isMoreAttemptsNeeded(arg):
                self.doReportNicknameExist(arg)
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'dht-read-failed' and not self.isMoreAttemptsNeeded(arg):
                self.state = 'FINISHED'
                self.doReportFinished(arg)
                self.doDestroyMe(arg)
        #---DHT_FIND---
        elif self.state == 'DHT_FIND':
            if event == 'dht-read-success':
                self.state = 'FOUND'
                self.doReportNicknameExist(arg)
                self.doDestroyMe(arg)
            elif event == 'dht-read-failed' and self.isMoreAttemptsNeeded(arg):
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'stop':
                self.state = 'STOPPED'
                self.doDestroyMe(arg)
            elif event == 'dht-read-failed' and not self.isMoreAttemptsNeeded(arg):
                self.state = 'NOT_FOUND'
                self.doReportNicknameNotExist(arg)
                self.doDestroyMe(arg)
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

    def isMoreAttemptsNeeded(self, arg):
        """
        Condition method.
        """
        return self.attempts > 0

    def doInit(self, arg):
        """
        Action method.
        """
        self.nickname, self.attempts, self.result_callback = arg
        try:
            nik, number = self.nickname.rsplit(':', 1)
            number = int(number)
        except:
            nik = self.nickname
            number = 0
        self.key = nik + ':' + str(number)

    def doNextKey(self, arg):
        """
        Action method.
        """
        try:
            nik, number = self.key.rsplit(':', 1)
            number = int(number)
        except:
            lg.exc()
            number = 0
        number += 1
        self.key = self.nickname + ':' + str(number)
        self.attempts -= 1

    def doDHTReadKey(self, arg):
        """
        Action method.
        """
        if self.dht_read_defer is not None:
            self.dht_read_defer.pause()
            self.dht_read_defer.cancel()
            self.dht_read_defer = None
        d = dht_service.get_value(self.key)
        d.addCallback(self._dht_read_result, self.key)
        d.addErrback(self._dht_read_failed)
        self.dht_read_defer = d

    def doReportNicknameExist(self, arg):
        """
        Action method.
        """
        lg.out(8, 'nickname_observer.doReportNicknameExist : (%s, %s)' % (self.key, arg))
        if self.result_callback is not None:
            nik, num = self.key.split(':')
            num = int(num)
            self.result_callback('exist', nik, num, arg)

    def doReportNicknameNotExist(self, arg):
        """
        Action method.
        """
        lg.out(8, 'nickname_observer.doReportNicknameNotExist : %s' % self.nickname)
        if self.result_callback is not None:
            self.result_callback('not exist', self.nickname, -1, arg)

    def doReportFinished(self, arg):
        """
        Action method.
        """
        lg.out(8, 'nickname_observer.doReportFinished')
        if self.result_callback is not None:
            self.result_callback('finished', '', -1, '')

    def doDestroyMe(self, arg):
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
        if not isinstance(value, dict):
            self.automat('dht-read-failed')
            return
        try:
            v = value[dht_service.key_to_hash(key)]
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
        print 'usage: nickname_observer.py <"many"|"one"> <nickname> <attempts>'
        return
    from twisted.internet import reactor
    lg.set_debug_level(24)
    settings.init()
    my_id.init()
    dht_service.init(settings.getDHTPort())

    def _result(result, nickname):
        print result, nickname
        if result == 'finished':
            reactor.stop()
    if sys.argv[1] == 'many':
        observe_many(sys.argv[2], int(sys.argv[3]), results_callback=_result)
    else:
        find_one(sys.argv[2], int(sys.argv[3]), _result)
    reactor.run()

if __name__ == "__main__":
    main()
