#!/usr/bin/env python
# nickname_holder.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (nickname_holder.py) is part of BitDust Software.
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
.. module:: nickname_holder

.. role:: red


BitDust nickname_holder() Automat

.. raw:: html

    <a href="nickname_holder.png" target="_blank">
    <img src="nickname_holder.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`dht-erase-failed`
    * :red:`dht-erase-success`
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`set`
    * :red:`timer-5min`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.main import settings

from bitdust.userid import my_id
from bitdust.userid import id_url

from bitdust.dht import dht_service
from bitdust.dht import dht_records

#------------------------------------------------------------------------------

_NicknameHolder = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _NicknameHolder
    if event is None:
        return _NicknameHolder
    if _NicknameHolder is None:
        # set automat name and starting state here
        _NicknameHolder = NicknameHolder(
            name='nickname_holder',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _NicknameHolder.automat(event, *args, **kwargs)
    return _NicknameHolder


def Destroy():
    """
    Destroy nickname_holder() automat and remove its instance from memory.
    """
    global _NicknameHolder
    if _NicknameHolder is None:
        return
    _NicknameHolder.destroy()
    del _NicknameHolder
    _NicknameHolder = None


#------------------------------------------------------------------------------


class NicknameHolder(automat.Automat):

    """
    This class implements all the functionality of the ``nickname_holder()``
    state machine.
    """

    timers = {
        'timer-5min': (300, ['READY']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.nickname = None
        self.key = None
        self.dht_read_defer = None
        self.result_callbacks = []

    def add_result_callback(self, cb):
        self.result_callbacks.append(cb)

    def remove_result_callback(self, cb):
        self.result_callbacks.remove(cb)

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'set':
                self.state = 'DHT_READ'
                self.Attempts = 0
                self.doSetNickname(*args, **kwargs)
                self.doMakeKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
        #---READY---
        elif self.state == 'READY':
            if event == 'timer-5min':
                self.state = 'DHT_READ'
                self.doSetNickname(*args, **kwargs)
                self.doMakeKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'set':
                self.state = 'DHT_ERASE'
                self.doDHTEraseKey(*args, **kwargs)
                self.doSetNickname(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'dht-read-success' and self.isMyOwnKey(*args, **kwargs):
                self.state = 'READY'
                self.doReportNicknameOwn(*args, **kwargs)
            elif event == 'dht-read-failed':
                self.state = 'DHT_WRITE'
                self.doDHTWriteKey(*args, **kwargs)
            elif event == 'dht-read-success' and not self.isMyOwnKey(*args, **kwargs):
                self.doReportNicknameExist(*args, **kwargs)
                self.doNextKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'set':
                self.doSetNickname(*args, **kwargs)
                self.doMakeKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'dht-write-failed' and self.Attempts > 5:
                self.state = 'READY'
                self.Attempts = 0
                self.doReportNicknameFailed(*args, **kwargs)
            elif event == 'dht-write-failed' and self.Attempts <= 5:
                self.state = 'DHT_READ'
                self.Attempts += 1
                self.doNextKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'dht-write-success':
                self.state = 'READY'
                self.Attempts = 0
                self.doReportNicknameRegistered(*args, **kwargs)
            elif event == 'set':
                self.state = 'DHT_READ'
                self.doSetNickname(*args, **kwargs)
                self.doMakeKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
        #---DHT_ERASE---
        elif self.state == 'DHT_ERASE':
            if event == 'dht-erase-success' or event == 'dht-erase-failed':
                self.state = 'DHT_READ'
                self.doMakeKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
            elif event == 'set':
                self.state = 'DHT_READ'
                self.doSetNickname(*args, **kwargs)
                self.doMakeKey(*args, **kwargs)
                self.doDHTReadKey(*args, **kwargs)
        return None

    def isMyOwnKey(self, *args, **kwargs):
        """
        Condition method.
        """
        return id_url.to_bin(args[0]) == my_id.getIDURL().to_bin()

    def doSetNickname(self, *args, **kwargs):
        """
        Action method.
        """
        self.nickname = my_id.getLocalIdentity().getIDName()

    def doMakeKey(self, *args, **kwargs):
        """
        Action method.
        """
        self.key = dht_service.make_key(
            key=self.nickname,
            index=0,
            prefix='nickname',
        )

    def doNextKey(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            key_info = dht_service.split_key(self.key)
            index = int(key_info['index'])
        except:
            lg.exc()
            index = 0
        index += 1
        self.key = dht_service.make_key(
            key=self.nickname,
            index=index,
            prefix='nickname',
        )

    def doDHTReadKey(self, *args, **kwargs):
        """
        Action method.
        """
        if self.dht_read_defer is not None:
            self.dht_read_defer.pause()
            self.dht_read_defer.cancel()
            self.dht_read_defer = None
        d = dht_records.get_nickname(self.key, use_cache=False)
        d.addCallback(self._dht_read_result, self.key)
        d.addErrback(self._dht_read_failed)
        self.dht_read_defer = d

    def doDHTWriteKey(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_records.set_nickname(self.key, my_id.getIDURL())
        d.addCallback(self._dht_write_result)
        d.addErrback(lambda err: self.automat('dht-write-failed', err))

    def doDHTEraseKey(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_service.delete_key(self.key)
        d.addCallback(self._dht_erase_result)
        d.addErrback(lambda x: self.automat('dht-erase-failed'))

    def doReportNicknameOwn(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'nickname_holder.doReportNicknameOwn : %s with %s' % (self.key, args[0]))
        for cb in self.result_callbacks:
            cb('my own', self.key)

    def doReportNicknameRegistered(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'nickname_holder.doReportNicknameRegistered : %s' % self.key)
        for cb in self.result_callbacks:
            cb('registered', self.key)

    def doReportNicknameExist(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'nickname_holder.doReportNicknameExist : %s' % self.key)
        for cb in self.result_callbacks:
            cb('exist', self.key)

    def doReportNicknameFailed(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'nickname_holder.doReportNicknameFailed : %s with %s' % (self.key, args[0] if args else None))
        for cb in self.result_callbacks:
            cb('failed', self.key)

    def _dht_read_result(self, value, key):
        self.dht_read_defer = None
        if not value:
            self.automat('dht-read-failed')
            return
        try:
            v = id_url.field(value['idurl'])
        except:
            if _Debug:
                lg.out(_DebugLevel, '%r' % value)
            lg.exc()
            self.automat('dht-read-failed')
            return
        self.automat('dht-read-success', v)

    def _dht_read_failed(self, x):
        self.dht_read_defer = None
        self.automat('dht-read-failed', x)

    def _dht_write_result(self, nodes):
        if len(nodes) > 0:
            self.automat('dht-write-success')
        else:
            self.automat('dht-write-failed', nodes)

    def _dht_erase_result(self, result):
        if result is None:
            self.automat('dht-erase-failed')
        else:
            self.automat('dht-erase-success')


#------------------------------------------------------------------------------


def main():
    from twisted.internet import reactor  # @UnresolvedImport
    lg.set_debug_level(24)
    settings.init()
    my_id.init()
    dht_service.init(settings.getDHTPort())
    reactor.callWhenRunning(A, 'init', sys.argv[1])  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable
    settings.shutdown()


if __name__ == '__main__':
    main()
