#!/usr/bin/python
# local_tester.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

Checks that customer packets on the local disk still have good signatures and are valid.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import sys

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in local_tester.py')

from twisted.internet import threads

#------------------------------------------------------------------------------

try:
    from bitdust.logs import lg
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))

from bitdust.system import bpio

from bitdust.main import settings

#-------------------------------------------------------------------------------

_TesterQueue = []
_CurrentProcess = None
_Loop = None
_LoopValidate = None
_LoopUpdateCustomers = None
_LoopSpaceTime = None

#------------------------------------------------------------------------------

TesterUpdateCustomers = 'update_customers'
TesterValidate = 'validate'
TesterSpaceTime = 'space_time'

#------------------------------------------------------------------------------


def init():
    global _Loop
    if _Debug:
        lg.out(_DebugLevel, 'local_tester.init')
    _Loop = reactor.callLater(5, loop)  # @UndefinedVariable


def shutdown():
    global _Loop
    global _CurrentProcess
    if _Debug:
        lg.out(_DebugLevel, 'local_tester.shutdown')

    stop()

    if _Loop:
        if _Loop.active():
            _Loop.cancel()
            _Loop = None

    if alive():
        # TODO: use some simple method to notify bptester thread to stop
        # for example write to local file some simple "marker"
        # bptester suppose to read that file every 1-2 seconds and check if "marker" is here
        if _Debug:
            lg.out(_DebugLevel, 'local_tester.shutdown is killing bptester')


#------------------------------------------------------------------------------


def start():
    global _LoopValidate
    global _LoopUpdateCustomers
    global _LoopSpaceTime
    if _Debug:
        lg.out(_DebugLevel, 'local_tester.start')
    _LoopValidate = reactor.callLater(0, loop_validate)  # @UndefinedVariable
    _LoopUpdateCustomers = reactor.callLater(0, loop_update_customers)  # @UndefinedVariable
    _LoopSpaceTime = reactor.callLater(0, loop_space_time)  # @UndefinedVariable


def stop():
    global _LoopValidate
    global _LoopUpdateCustomers
    global _LoopSpaceTime
    if _Debug:
        lg.out(_DebugLevel, 'local_tester.stop')
    if _LoopValidate:
        if _LoopValidate.active():
            _LoopValidate.cancel()
            _LoopValidate = None
    if _LoopUpdateCustomers:
        if _LoopUpdateCustomers.active():
            _LoopUpdateCustomers.cancel()
            _LoopUpdateCustomers = None
    if _LoopSpaceTime:
        if _LoopSpaceTime.active():
            _LoopSpaceTime.cancel()
            _LoopSpaceTime = None


#------------------------------------------------------------------------------


def _pushTester(cmd):
    global _TesterQueue
    if cmd in _TesterQueue:
        return
    _TesterQueue.append(cmd)


def _popTester():
    global _TesterQueue
    if len(_TesterQueue) == 0:
        return None
    cmd = _TesterQueue[0]
    del _TesterQueue[0]
    return cmd


#-------------------------------------------------------------------------------


def on_thread_finished(ret, cmd):
    global _CurrentProcess
    _CurrentProcess = None
    if _Debug:
        lg.out(_DebugLevel, 'local_tester.on_thread_finished %r with %r' % (cmd, ret))


def run_in_thread(cmd):
    global _CurrentProcess
    from bitdust.main import bptester
    if _CurrentProcess:
        raise Exception('another thread already started')
    _CurrentProcess = cmd
    command = {
        TesterUpdateCustomers: bptester.UpdateCustomers,
        TesterValidate: bptester.Validate,
        TesterSpaceTime: bptester.SpaceTime,
    }[cmd]
    d = threads.deferToThread(command)  # @UndefinedVariable
    d.addBoth(on_thread_finished, cmd)
    if _Debug:
        lg.out(_DebugLevel, 'local_tester.run_in_thread started %r' % cmd)


#------------------------------------------------------------------------------


def alive():
    global _CurrentProcess
    if _CurrentProcess is None:
        return False
    return True


def loop():
    global _Loop
    if not alive():
        cmd = _popTester()
        if cmd:
            run_in_thread(cmd)
    _Loop = reactor.callLater(settings.DefaultLocaltesterLoop(), loop)  # @UndefinedVariable


def loop_validate():
    global _LoopValidate
    TestValid()
    _LoopValidate = reactor.callLater(settings.DefaultLocaltesterValidateTimeout(), loop_validate)  # @UndefinedVariable


def loop_update_customers():
    global _LoopUpdateCustomers
    TestUpdateCustomers()
    _LoopUpdateCustomers = reactor.callLater(settings.DefaultLocaltesterUpdateCustomersTimeout(), loop_update_customers)  # @UndefinedVariable


def loop_space_time():
    global _LoopSpaceTime
    TestSpaceTime()
    _LoopSpaceTime = reactor.callLater(settings.DefaultLocaltesterSpaceTimeTimeout(), loop_space_time)  # @UndefinedVariable


#-------------------------------------------------------------------------------


def TestUpdateCustomers():
    _pushTester(TesterUpdateCustomers)


def TestValid():
    _pushTester(TesterValidate)


def TestSpaceTime():
    _pushTester(TesterSpaceTime)


#-------------------------------------------------------------------------------

if __name__ == '__main__':
    lg.set_debug_level(18)
    bpio.init()
    settings.init()
    init()
    reactor.run()  # @UndefinedVariable
    settings.shutdown()
