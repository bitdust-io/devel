#!/usr/bin/python
# git_proc.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (git_proc.py) is part of BitDust Software.
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
#

"""
.. module:: git_proc.

A code for all platforms to perform source code updates from official Git repo at:

   http://dev.bitdust.io/code/public.git
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
from io import open

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import sys
import time

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in git_proc.py')

from twisted.internet import protocol

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from lib import strng

from logs import lg

from system import bpio

from main import settings
from main import events

#------------------------------------------------------------------------------

_CurrentProcess = None
_FirstRunDelay = 1200
_LoopInterval = 3600 * 6
_ShedulerTask = None

#------------------------------------------------------------------------------

def write2log(txt):
    out_file = open(settings.UpdateLogFilename(), 'a')
    out_file.write(strng.to_text(txt))
    out_file.close()

#------------------------------------------------------------------------------

def init():
    lg.out(4, 'git_proc.init')
    if os.environ.get('BITDUST_GIT_SYNC_SKIP', '0') == '1':
        return
    reactor.callLater(0, loop, first_start=True)


def shutdown():
    lg.out(4, 'git_proc.shutdown')
    global _ShedulerTask
    if _ShedulerTask is not None:
        if _ShedulerTask.active():
            _ShedulerTask.cancel()
            lg.out(4, '    loop stopped')
        _ShedulerTask = None

#------------------------------------------------------------------------------


def sync_callback(result):
    """
    """
    lg.out(6, 'git_proc.sync_callback: %s' % result)

    if result == 'code-fetched':
        events.send('source-code-fetched')
    elif result == 'up-to-date':
        events.send('source-code-up-to-date')
    else:
        events.send('source-code-update-error', dict(result=result))

    try:
        from system import tray_icon
        if result == 'error':
            # tray_icon.draw_icon('error')
            # reactor.callLater(5, tray_icon.restore_icon)
            return
        elif result == 'code-fetched':
            tray_icon.set_icon('updated')
            return
    except:
        pass


def run_sync():
    lg.out(6, 'git_proc.run_sync')
    reactor.callLater(0, sync, sync_callback)
    reactor.callLater(0, loop)


def loop(first_start=False):
    global _ShedulerTask
    lg.out(4, 'git_proc.loop')
    if first_start:
        nexttime = time.time() + _FirstRunDelay
    else:
        nexttime = time.time() + _LoopInterval
    # DEBUG
    # nexttime = time.time() + 10.0
    delay = nexttime - time.time()
    if delay < 0:
        lg.warn('delay=%s %s %s' % (str(delay), nexttime, time.time()))
        delay = 0
    lg.out(6, 'git_proc.loop run_sync will start after %s minutes' % str(delay / 60.0))
    _ShedulerTask = reactor.callLater(delay, run_sync)

#------------------------------------------------------------------------------


def sync(callback_func=None, update_method='rebase'):
    """
    Runs commands and process stdout and stderr to recogneze the result:

        git fetch --all -v
        git rebase origin/master -v

    """
    def _reset_done(response, error, retcode, result):
        if callback_func is None:
            return
        callback_func(result)

    def _rebase_done(response, error, retcode, result):
        if callback_func is None:
            return
        if retcode != 0:
            result = 'sync-error'
        else:
            if response.count(b'Changes from') or response.count(b'Fast-forwarded'):
                result = 'code-fetched'
            else:
                result = 'up-to-date'
        callback_func(result)

    def _fetch_done(response, error, retcode):
        if retcode != 0:
            if callback_func:
                callback_func('sync-error')
            return
        result = 'sync-error'
        if response.count(b'Unpacking') or \
            (response.count(b'master') and response.count(b'->')) or \
            response.count(b'Updating') or \
            response.count(b'Receiving') or \
                response.count(b'Counting'):
            result = 'new-code'
        if update_method == 'reset':
            run(['reset', '--hard', 'origin/master', ],
                callback=lambda resp, err, ret: _reset_done(resp, err, ret, result))
        elif update_method == 'rebase':
            run(['rebase', 'origin/master', '-v'],
                callback=lambda resp, err, ret: _rebase_done(resp, err, ret, result))
        else:
            raise Exception('invalid update method: %s' % update_method)

    run(['fetch', '--all', '-v'], callback=_fetch_done)

#------------------------------------------------------------------------------


def run(cmdargs, base_dir=None, git_bin=None, env=None, callback=None):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.run')
    base_dir = base_dir or bpio.getExecutableDir()
    if bpio.Windows():
        cmd = ['git', ] + cmdargs
        if git_bin:
            git_exe = git_bin
        else:
            git_exe = bpio.portablePath(os.path.join(base_dir, '..', 'git', 'bin', 'git.exe'))
        if not os.path.isfile(git_exe):
            if _Debug:
                lg.out(_DebugLevel, '    not found git.exe, try to run from shell')
            try:
                response, error, retcode = execute_in_shell(cmd, base_dir=base_dir)
            except:
                response = ''
                error = ''
                retcode = 1
            if callback:
                callback(response, error, retcode)
            return
        if _Debug:
            lg.out(_DebugLevel, '    found git in %s' % git_exe)
        cmd = [git_exe, ] + cmdargs
    else:
        cmd = [git_bin or 'git', ] + cmdargs
    execute(cmd, callback=callback, base_dir=base_dir, env=env)

#------------------------------------------------------------------------------


def execute_in_shell(cmdargs, base_dir=None):
    global _CurrentProcess
    from system import nonblocking
    import subprocess
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.execute_in_shell: "%s"' % (' '.join(cmdargs)))
    write2log('EXECUTE in shell: %s, base_dir=%s' % (cmdargs, base_dir))
    _CurrentProcess = nonblocking.Popen(
        cmdargs,
        shell=True,
        cwd=bpio.portablePath(base_dir),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,)
    result = _CurrentProcess.communicate()
    out_data = result[0]
    err_data = result[1]
    write2log('STDOUT:\n%s\nSTDERR:\n%s\n' % (out_data, err_data))
    returncode = _CurrentProcess.returncode
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.execute_in_shell returned: %s, stdout bytes: %d, stderr bytes: %d' % (
            returncode, len(out_data), len(err_data)))
    return (out_data, err_data, returncode)  # _CurrentProcess

#------------------------------------------------------------------------------


class GitProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, callbacks=[]):
        self.callbacks = callbacks
        self.out = b''
        self.err = b''

    def errReceived(self, inp):
        self.err += inp
        for line in inp.splitlines():
            if _Debug:
                lg.out(_DebugLevel, '[git:err]: %s' % strng.to_text(line))

    def outReceived(self, inp):
        self.out += inp
        for line in inp.splitlines():
            if _Debug:
                lg.out(_DebugLevel, '[git:out]: %s' % strng.to_text(line))

    def processEnded(self, reason):
        if _Debug:
            lg.out(_DebugLevel, 'git process FINISHED : %s' % reason.value.exitCode)
        for cb in self.callbacks:
            cb(self.out, self.err, reason.value.exitCode)


def execute(cmdargs, base_dir=None, process_protocol=None, env=None, callback=None):
    global _CurrentProcess
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.execute: "%s" in %s' % (' '.join(cmdargs), base_dir))
    write2log('EXECUTE: %s, base_dir=%s' % (cmdargs, base_dir))
    executable = cmdargs[0]
    if bpio.Windows():
        from twisted.internet import _dumbwin32proc
        real_CreateProcess = _dumbwin32proc.win32process.CreateProcess

        def fake_createprocess(_appName, _commandLine, _processAttributes,
                               _threadAttributes, _bInheritHandles, creationFlags,
                               _newEnvironment, _currentDirectory, startupinfo):
            import win32con
            import subprocess
            flags = win32con.CREATE_NO_WINDOW
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return real_CreateProcess(_appName, _commandLine,
                                      _processAttributes, _threadAttributes,
                                      _bInheritHandles, flags, _newEnvironment,
                                      _currentDirectory, startupinfo)
        setattr(_dumbwin32proc.win32process, 'CreateProcess', fake_createprocess)

    if process_protocol is None:
        process_protocol = GitProcessProtocol(callbacks=[
            lambda out, err, ret_code: write2log('STDOUT:\n%s\nSTDERR:\n%s\n' % (out, err)),
            callback,
        ])
    try:
        _CurrentProcess = reactor.spawnProcess(
            process_protocol, executable, cmdargs, path=base_dir, env=env)
    except:
        lg.exc()
        return None
    if bpio.Windows():
        setattr(_dumbwin32proc.win32process, 'CreateProcess', real_CreateProcess)
    return _CurrentProcess

#------------------------------------------------------------------------------


if __name__ == "__main__":
    bpio.init()
    lg.set_debug_level(18)

    def _result(res):
        print('RESULT:', res)
        reactor.stop()
    reactor.callWhenRunning(sync, _result)
    reactor.run()
