#!/usr/bin/python
# local_tester.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (local_tester.py) is part of BitDust Software.
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
.. module:: local_tester.

Checks that customer packets on the local disk still have good signatures.

These packets could be outgoing, cached, incoming, or stored for remote customers.

Idea is to detect bit-rot and then either if there is a problem we can do different
things depending on what type it is.

So far:
  1) If data we store for a remote customer:  ask for the packet again (he may call his scrubber)
  2) If just cache of our personal data stored somewhere:  just delete bad packet from cache

Also, after a system crash we need to check that things are ok and cleanup
and partial stuff, like maybe backupid/outgoing/tmp where block was being
converted to a bunch of packets but the conversion was not finished.

So has to open/parse the ``packet`` but that code is part of signed.py

The concept of "fail fast" is what we are after here.  If there is a failure we
want to know about it fast, so we can fix it fast, so the chance of multiple
failures at the same time is less.

Right now this is an interface between ``bpmain`` and ``bptester`` child process.
"""

from __future__ import absolute_import
import os
import sys
import time
import string

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in localtester.py')

from twisted.python.win32 import cmdLineQuote

import subprocess

#------------------------------------------------------------------------------

try:
    from logs import lg
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))

from logs import lg

from system import bpio
from system import nonblocking

from main import settings

#-------------------------------------------------------------------------------

TesterUpdateCustomers = 'update_customers'
TesterValidate = 'validate'
TesterSpaceTime = 'space_time'

_TesterQueue = []
_CurrentProcess = None
_Loop = None
_LoopValidate = None
_LoopUpdateCustomers = None
_LoopSpaceTime = None

#------------------------------------------------------------------------------


def init():
    global _Loop
    global _LoopValidate
    global _LoopUpdateCustomers
    lg.out(4, 'localtester.init ')
    _Loop = reactor.callLater(5, loop)
    _LoopValidate = reactor.callLater(0, loop_validate)
    _LoopUpdateCustomers = reactor.callLater(0, loop_update_customers)
    _LoopSpaceTime = reactor.callLater(0, loop_space_time)


def shutdown():
    global _Loop
    global _LoopValidate
    global _LoopUpdateCustomers
    global _LoopSpaceTime
    global _CurrentProcess
    lg.out(4, 'localtester.shutdown ')

    if _Loop:
        if _Loop.active():
            _Loop.cancel()
    if _LoopValidate:
        if _LoopValidate.active():
            _LoopValidate.cancel()
    if _LoopUpdateCustomers:
        if _LoopUpdateCustomers.active():
            _LoopUpdateCustomers.cancel()
    if _LoopSpaceTime:
        if _LoopSpaceTime.active():
            _LoopSpaceTime.cancel()

    if alive():
        lg.out(4, 'localtester.shutdown is killing bptester')

        try:
            _CurrentProcess.kill()
        except:
            lg.warn('can not kill bptester')
        del _CurrentProcess
        _CurrentProcess = None

#------------------------------------------------------------------------------


def _pushTester(Tester):
    global _TesterQueue
    if Tester in _TesterQueue:
        return
    _TesterQueue.append(Tester)


def _popTester():
    global _TesterQueue
    if len(_TesterQueue) == 0:
        return None
    Tester = _TesterQueue[0]
    del _TesterQueue[0]
    return Tester

#-------------------------------------------------------------------------------


def run(Tester):
    global _CurrentProcess
    # lg.out(8, 'localtester.run ' + str(Tester))

    if bpio.isFrozen() and bpio.Windows():
        commandpath = 'bptester.exe'
        cmdargs = [commandpath, Tester]
    else:
        commandpath = 'bptester.py'
        cmdargs = [sys.executable, commandpath, Tester]

    if not os.path.isfile(commandpath):
        lg.out(1, 'localtester.run ERROR %s not found' % commandpath)
        return None

    lg.out(14, 'localtester.run execute: %s' % cmdargs)

    try:
        if bpio.Windows():
            import win32process
            _CurrentProcess = nonblocking.Popen(
                cmdargs,
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,
                creationflags=win32process.CREATE_NO_WINDOW,)
        else:
            _CurrentProcess = nonblocking.Popen(
                cmdargs,
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,)
    except:
        lg.out(1, 'localtester.run ERROR executing: %s' % str(cmdargs))
        lg.exc()
        return None
    return _CurrentProcess


def alive():
    global _CurrentProcess
    if _CurrentProcess is None:
        return False
    try:
        p = _CurrentProcess.poll()
    except:
        return False
    return p is None


def loop():
    global _Loop
    if not alive():
        Tester = _popTester()
        if Tester:
            run(Tester)
    _Loop = reactor.callLater(settings.DefaultLocaltesterLoop(), loop)


def loop_validate():
    global _LoopValidate
    TestValid()
    _LoopValidate = reactor.callLater(settings.DefaultLocaltesterValidateTimeout(), loop_validate)


def loop_update_customers():
    global _LoopUpdateCustomers
    TestUpdateCustomers()
    _LoopUpdateCustomers = reactor.callLater(settings.DefaultLocaltesterUpdateCustomersTimeout(), loop_update_customers)


def loop_space_time():
    global _LoopSpaceTime
    TestSpaceTime()
    _LoopSpaceTime = reactor.callLater(settings.DefaultLocaltesterSpaceTimeTimeout(), loop_space_time)

#-------------------------------------------------------------------------------


def TestUpdateCustomers():
    _pushTester(TesterUpdateCustomers)


def TestValid():
    _pushTester(TesterValidate)


def TestSpaceTime():
    _pushTester(TesterSpaceTime)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
    lg.set_debug_level(18)
    bpio.init()
    settings.init()
    init()
    reactor.run()
