

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

import os
import sys
import time

from logs import lg

from automats import automat

from main import settings

from userid import my_id

from dht import dht_service

#------------------------------------------------------------------------------ 

_NicknameHolder = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _NicknameHolder
    if _NicknameHolder is None:
        # set automat name and starting state here
        _NicknameHolder = NicknameHolder('nickname_holder', 'AT_STARTUP', 6)
    if event is not None:
        _NicknameHolder.automat(event, arg)
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
    This class implements all the functionality of the ``nickname_holder()`` state machine.
    """

    timers = {
        'timer-5min': (300, ['READY']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.nickname = None
        self.key = None
        self.dht_read_defer = None
        self.result_callback = None

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'set' :
                self.state = 'DHT_READ'
                self.Attempts=0
                self.doSetNickname(arg)
                self.doMakeKey(arg)
                self.doDHTReadKey(arg)
        #---READY---
        elif self.state == 'READY':
            if event == 'timer-5min' :
                self.state = 'DHT_READ'
                self.doSetNickname(arg)
                self.doMakeKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'set' :
                self.state = 'DHT_ERASE'
                self.doDHTEraseKey(arg)
                self.doSetNickname(arg)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'dht-read-success' and self.isMyOwnKey(arg) :
                self.state = 'READY'
                self.doReportNicknameOwn(arg)
            elif event == 'dht-read-failed' :
                self.state = 'DHT_WRITE'
                self.doDHTWriteKey(arg)
            elif event == 'dht-read-success' and not self.isMyOwnKey(arg) :
                self.doReportNicknameExist(arg)
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'set' :
                self.doSetNickname(arg)
                self.doMakeKey(arg)
                self.doDHTReadKey(arg)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'dht-write-failed' and self.Attempts>5 :
                self.state = 'READY'
                self.Attempts=0
                self.doReportNicknameFailed(arg)
            elif event == 'dht-write-failed' and self.Attempts<=5 :
                self.state = 'DHT_READ'
                self.Attempts+=1
                self.doNextKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'dht-write-success' :
                self.state = 'READY'
                self.Attempts=0
                self.doReportNicknameRegistered(arg)
            elif event == 'set' :
                self.state = 'DHT_READ'
                self.doSetNickname(arg)
                self.doMakeKey(arg)
                self.doDHTReadKey(arg)
        #---DHT_ERASE---
        elif self.state == 'DHT_ERASE':
            if event == 'dht-erase-success' or event == 'dht-erase-failed' :
                self.state = 'DHT_READ'
                self.doMakeKey(arg)
                self.doDHTReadKey(arg)
            elif event == 'set' :
                self.state = 'DHT_READ'
                self.doSetNickname(arg)
                self.doMakeKey(arg)
                self.doDHTReadKey(arg)
        return None

    def isMyOwnKey(self, arg):
        """
        Condition method.
        """
        return arg == my_id.getLocalID()

    def doSetNickname(self, arg):
        """
        Action method.
        """
        if arg is None:
            a, c = None, None
        else:
            a, c = arg
        self.nickname = a or \
            settings.getNickName() or \
            my_id.getLocalIdentity().getIDName()
        self.result_callback = c

    def doMakeKey(self, arg):
        """
        Action method.
        """
        self.key = self.nickname + ':' + '0'

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
        
    def doDHTWriteKey(self, arg):
        """
        Action method.
        """
        d = dht_service.set_value(self.key, my_id.getLocalID(), age=int(time.time()))
        d.addCallback(self._dht_write_result)
        d.addErrback(lambda x: self.automat('dht-write-failed'))

    def doDHTEraseKey(self, arg):
        """
        Action method.
        """
        dht_service.delete_key(self.key)
        
    def doReportNicknameOwn(self, arg):
        """
        Action method.
        """
        lg.out(18, 'nickname_holder.doReportNicknameOwn : %s' % self.key)
        if self.result_callback:
            self.result_callback('my own', self.key)

    def doReportNicknameRegistered(self, arg):
        """
        Action method.
        """
        lg.out(18, 'nickname_holder.doReportNicknameRegistered : %s' % self.key)
        if self.result_callback:
            self.result_callback('registered', self.key)

    def doReportNicknameExist(self, arg):
        """
        Action method.
        """
        lg.out(18, 'nickname_holder.doReportNicknameExist : %s' % self.key)
        if self.result_callback:
            self.result_callback('exist', self.key)

    def doReportNicknameFailed(self, arg):
        """
        Action method.
        """
        lg.out(18, 'nickname_holder.doReportNicknameFailed : %s' % self.key)
        if self.result_callback:
            self.result_callback('failed', self.key)

    def _dht_read_result(self, value, key):
        self.dht_read_defer = None
        if type(value) != dict:
            self.automat('dht-read-failed')
            return
        try:
            v = value[dht_service.key_to_hash(key)]
        except:
            lg.out(8, '%r' % value)
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
            self.automat('dht-write-failed')        

#------------------------------------------------------------------------------ 


def main():
    from twisted.internet import reactor
    lg.set_debug_level(24)
    settings.init()
    my_id.init()
    dht_service.init(settings.getDHTPort())
    reactor.callWhenRunning(A, 'init', sys.argv[1])
    reactor.run()

if __name__ == "__main__":
    main()

