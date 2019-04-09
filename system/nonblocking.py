#!/usr/bin/python
# nonblocking.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (nonblocking.py) is part of BitDust Software.
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
.. module:: nonblocking.

This is a wrapper around built-in module ``subprocess.Popen``. Provide
some extended functionality. Can read/write from pipe without blocking
the main thread.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

import os
import sys
import errno
import time
import subprocess
import traceback
import platform

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

PIPE = subprocess.PIPE

# Pipe States:
PIPE_EMPTY = 0
PIPE_READY2READ = 1
PIPE_CLOSED = 2

#------------------------------------------------------------------------------

if getattr(subprocess, 'mswindows', None) or platform.uname()[0] == "Windows":
    from win32file import ReadFile, WriteFile  # @UnresolvedImport
    from win32pipe import PeekNamedPipe  # @UnresolvedImport
    from win32api import TerminateProcess, OpenProcess, CloseHandle  # @UnresolvedImport
    import msvcrt
else:
    import select
    import fcntl  # @UnresolvedImport
    import signal

#------------------------------------------------------------------------------

from logs import lg

#------------------------------------------------------------------------------


class Popen(subprocess.Popen):
    """
    This is inherited from ``subprocess.Popen`` class.

    Added some wrappers and platform specific code. Most important
    method added is ``make_nonblocking``.
    """
    err_report = ''

    def __init__(self, args, bufsize=0, executable=None,
                 stdin=None, stdout=None, stderr=None,
                 preexec_fn=None, close_fds=False, shell=False,
                 cwd=None, env=None, universal_newlines=False,
                 startupinfo=None, creationflags=0):

        self.args = args
        subprocess.Popen.__init__(self,
                                  args, bufsize, executable,
                                  stdin, stdout, stderr,
                                  preexec_fn, close_fds, shell,
                                  cwd, env, universal_newlines,
                                  startupinfo, creationflags)
        if _Debug:
            lg.out(_DebugLevel, 'nonblocking.Popen created')
            lg.out(_DebugLevel, '    stdin=%r' % self.stdin)
            lg.out(_DebugLevel, '    stdout=%r' % self.stdout)
            lg.out(_DebugLevel, '    stderr=%r' % self.stderr)

    def __del__(self):
        try:
            subprocess.Popen.__del__(self)
        except:
            pass
        if _Debug:
            lg.out(_DebugLevel, 'nonblocking.Popen closed')

    def returncode(self):
        return self.returncode

    def recv(self, maxsize=None):
        r = self._recv('stdout', maxsize)
        if r is None:
            return ''
        return r

    def recv_err(self, maxsize=None):
        return self._recv('stderr', maxsize)

    def send_recv(self, input='', maxsize=None):
        return self.send(input), self.recv(maxsize), self.recv_err(maxsize)

    def get_conn_maxsize(self, which, maxsize):
        if maxsize is None:
            maxsize = 1024
        elif maxsize < 1:
            maxsize = 1
        return getattr(self, which), maxsize

    def _close(self, which):
        getattr(self, which).close()
        setattr(self, which, None)

    def state(self):
        return self._state('stdout')

    def make_nonblocking(self):
        """
        Under Linux use built-in method ``fcntl.fcntl`` to make the pipe
        read/write non blocking.
        """
        if getattr(subprocess, 'mswindows', None) or platform.uname()[0] == "Windows":
            return
        conn, maxsize = self.get_conn_maxsize('stdout', None)
        if conn is None:
            return
        flags = fcntl.fcntl(conn, fcntl.F_GETFL)
        if not conn.closed:
            fcntl.fcntl(conn, fcntl.F_SETFL, flags | os.O_NONBLOCK)


    if getattr(subprocess, 'mswindows', None) or platform.uname()[0] == "Windows":

        def send(self, input):
            if not self.stdin:
                return None

            try:
                x = msvcrt.get_osfhandle(self.stdin.fileno())  # @UndefinedVariable
                (errCode, written) = WriteFile(x, input)
            except:
                return None

            return written

        def _recv(self, which, maxsize):
            conn, maxsize = self.get_conn_maxsize(which, maxsize)
            if conn is None:
                return None

            try:
                x = msvcrt.get_osfhandle(conn.fileno())  # @UndefinedVariable
                (read, nAvail, nMessage) = PeekNamedPipe(x, 0)
                if maxsize < nAvail:
                    nAvail = maxsize
                if nAvail > 0:
                    (errCode, read) = ReadFile(x, nAvail, None)
            except:
                return None

            if self.universal_newlines:
                read = self._translate_newlines(read)

            return read

        def _state(self, which):
            conn, maxsize = self.get_conn_maxsize(which, None)
            if conn is None:
                return PIPE_CLOSED
            try:
                x = msvcrt.get_osfhandle(conn.fileno())  # @UndefinedVariable
            except:
                return PIPE_CLOSED
            try:
                (read, nAvail, nMessage) = PeekNamedPipe(x, 0)
            except:
                return PIPE_CLOSED
            if nAvail > 0:
                return PIPE_READY2READ
            return PIPE_EMPTY

        def kill(self):
            try:
                PROCESS_TERMINATE = 1
                handle = OpenProcess(PROCESS_TERMINATE, False, self.pid)
                TerminateProcess(handle, -1)
                CloseHandle(handle)
            except:
                pass


    else:
        def send(self, input):
            if not self.stdin:
                return None

            if not select.select([], [self.stdin], [], 0)[1]:
                return None

            try:
                written = os.write(self.stdin.fileno(), input)
            except:
                return None

            return written

        def _recv(self, which, maxsize):
            conn, maxsize = self.get_conn_maxsize(which, maxsize)
            if conn is None:
                return None

            flags = fcntl.fcntl(conn, fcntl.F_GETFL)
            if not conn.closed:
                fcntl.fcntl(conn, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            try:
                if not select.select([conn], [], [], 0)[0]:
                    return None

                r = conn.read(maxsize)
                if not r:
                    return None

                if self.universal_newlines:
                    r = self._translate_newlines(r)
                return r
            finally:
                if not conn.closed:
                    fcntl.fcntl(conn, fcntl.F_SETFL, flags)

        def _state(self, which):
            conn, maxsize = self.get_conn_maxsize(which, None)
            if conn is None:
                return PIPE_CLOSED

            try:
                # check and see if there is any input ready
                ready = select.select([conn], [], [], 0)
                if conn in ready[0]:
                    return PIPE_READY2READ
                return PIPE_EMPTY
            except:
                return PIPE_CLOSED

        def kill(self):
            os.kill(self.pid, signal.SIGTERM)


def ExecuteString(execstr):
    """
    An old method.
    """
    try:
        import win32process  # @UnresolvedImport
        return Popen(
            execstr,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=win32process.CREATE_NO_WINDOW,)
    except:
        return None
