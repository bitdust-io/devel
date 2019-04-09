#!/usr/bin/python
# child_process.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (child_process.py) is part of BitDust Software.
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
.. module:: child_process.

BitDust executes periodically several slaves:
    - bppipe
    - bptester
    - bpgui

They are started as a separated processes and managed from the main process: bpmain
"""

from __future__ import absolute_import
import os
import sys
import subprocess

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in child_process.py')

from twisted.internet import protocol

#------------------------------------------------------------------------------

from logs import lg

from . import bpio
from . import nonblocking

#------------------------------------------------------------------------------


class ChildProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, name):
        self.name = name

    def errReceived(self, inp):
        for line in inp.splitlines():
            lg.out(2, '[%s]: %s' % (self.name, line))

    def processEnded(self, reason):
        lg.out(2, 'child process [%s] FINISHED' % self.name)

#------------------------------------------------------------------------------


def run(child_name, params=[], base_dir='.', process_protocol=None):
    """
    This is another portable solution to execute a process.
    """
    if bpio.isFrozen() and bpio.Windows():
        progpath = os.path.abspath(os.path.join(base_dir, child_name + '.exe'))
        executable = progpath
        cmdargs = [progpath]
        cmdargs.extend(params)
    else:
        progpath = os.path.abspath(os.path.join(base_dir, child_name + '.py'))
        executable = sys.executable
        cmdargs = [executable, progpath]
        cmdargs.extend(params)
    if not os.path.isfile(executable):
        lg.out(1, 'child_process.run ERROR %s not found' % executable)
        return None
    if not os.path.isfile(progpath):
        lg.out(1, 'child_process.run ERROR %s not found' % progpath)
        return None
    lg.out(6, 'child_process.run: "%s"' % (' '.join(cmdargs)))

    if bpio.Windows():
        from twisted.internet import _dumbwin32proc
        real_CreateProcess = _dumbwin32proc.win32process.CreateProcess  # @UndefinedVariable

        def fake_createprocess(_appName, _commandLine, _processAttributes,
                               _threadAttributes, _bInheritHandles, creationFlags,
                               _newEnvironment, _currentDirectory, startupinfo):
            import win32con  # @UnresolvedImport
            flags = win32con.CREATE_NO_WINDOW
            return real_CreateProcess(_appName, _commandLine,
                                      _processAttributes, _threadAttributes,
                                      _bInheritHandles, flags, _newEnvironment,
                                      _currentDirectory, startupinfo)
        setattr(_dumbwin32proc.win32process, 'CreateProcess', fake_createprocess)

    if process_protocol is None:
        process_protocol = ChildProcessProtocol(child_name)
    try:
        Process = reactor.spawnProcess(process_protocol, executable, cmdargs, path=base_dir)  # @UndefinedVariable
    except:
        lg.out(1, 'child_process.run ERROR executing: %s' % str(cmdargs))
        lg.exc()
        return None

    if bpio.Windows():
        setattr(_dumbwin32proc.win32process, 'CreateProcess', real_CreateProcess)

    lg.out(6, 'child_process.run [%s] pid=%d' % (child_name, Process.pid))
    return Process


def kill_process(process):
    """
    Send signal "KILL" to the given ``process``.
    """
    try:
        process.signalProcess('KILL')
        lg.out(6, 'child_process.kill_process sent signal "KILL" to the process %d' % process.pid)
    except:
        return False
    return True


def kill_child(child_name):
    """
    Search (by "pid") for BitDust child process with name ``child_name`` and
    tries to kill it.
    """
    killed = False
    for pid in bpio.find_process([child_name + '.']):
        bpio.kill_process(pid)
        lg.out(6, 'child_process.kill_child pid %d' % pid)
        killed = True
    return killed

#------------------------------------------------------------------------------


def pipe(cmdargs):
    """
    Execute a process in different way, create a Pipe to do read/write
    operations with child process.

    See ``lib.nonblocking`` module.
    """
    lg.out(6, "child_process.pipe %s" % str(cmdargs))
    try:
        if bpio.Windows():
            import win32process  # @UnresolvedImport
            p = nonblocking.Popen(
                cmdargs,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,
                creationflags=win32process.CREATE_NO_WINDOW,
            )
        else:
            p = nonblocking.Popen(
                cmdargs,
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,
            )
    except:
        lg.out(1, 'child_process.pipe ERROR executing: %s' + str(cmdargs))
        lg.exc()
        return None
    return p


def detach(cmdargs):
    """
    """
    lg.out(2, "child_process.detach %s" % str(cmdargs))
    try:
        if bpio.Windows():
            import win32process  # @UnresolvedImport
            p = nonblocking.Popen(
                cmdargs,
                shell=False,
                # stdin=subprocess.PIPE,
                # stdout=subprocess.PIPE,
                # stderr=subprocess.PIPE,
                universal_newlines=False,
                creationflags=win32process.CREATE_NO_WINDOW | win32process.DETACHED_PROCESS,
                close_fds=True,
            )
        else:
            p = nonblocking.Popen(
                cmdargs,
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,
                close_fds=True,
            )
    except:
        lg.out(1, 'child_process.detach ERROR executing: %s' + str(cmdargs))
        lg.exc()
        return None
    return p
