#!/usr/bin/python
# git_proc.py
#
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

_Debug = False
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

from bitdust.lib import strng

from bitdust.logs import lg

from bitdust.system import bpio
from bitdust.system import deploy

from bitdust.main import settings
from bitdust.main import events

#------------------------------------------------------------------------------

_CurrentProcess = None
_FirstRunDelay = 60*20
_LoopInterval = 60*60*6
_ShedulerTask = None

#------------------------------------------------------------------------------


def write2log(txt):
    try:
        out_file = open(settings.UpdateLogFilename(), 'a')
        out_file.write(strng.to_text(txt))
        out_file.close()
    except:
        pass


#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.init')
    if os.environ.get('BITDUST_GIT_SYNC_SKIP', '0') == '1':
        return
    reactor.callLater(0, loop, first_start=True)  # @UndefinedVariable


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.shutdown')
    global _ShedulerTask
    if _ShedulerTask is not None:
        if _ShedulerTask.active():
            _ShedulerTask.cancel()
            if _Debug:
                lg.out(_DebugLevel, '    loop stopped')
        _ShedulerTask = None


#------------------------------------------------------------------------------


def sync_callback(result):
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.sync_callback: %s' % result)

    if result == 'code-fetched':
        events.send('source-code-fetched', data=dict())
    elif result == 'up-to-date':
        events.send('source-code-up-to-date', data=dict())
    else:
        events.send('source-code-update-error', data=dict(result=result))

    try:
        # from bitdust.system import tray_icon
        if result == 'error':
            # tray_icon.draw_icon('error')
            # reactor.callLater(5, tray_icon.restore_icon)
            return
        elif result == 'code-fetched':
            # tray_icon.set_icon('updated')
            return
    except:
        pass


def run_sync():
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.run_sync')
    reactor.callLater(0, sync, sync_callback, update_method='reset')  # @UndefinedVariable
    reactor.callLater(0, loop)  # @UndefinedVariable


def loop(first_start=False):
    global _ShedulerTask
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.loop')
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
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.loop run_sync will start after %s minutes' % str(delay/60.0))
    _ShedulerTask = reactor.callLater(delay, run_sync)  # @UndefinedVariable


#------------------------------------------------------------------------------


def sync(callback_func=None, update_method='rebase'):
    """
    Runs commands and process stdout and stderr to recogneze the result:

        `git fetch --all -v`
        `git rebase origin/master -v`  or  `git reset --hard origin/master`

    """
    src_dir_path = os.path.abspath(os.path.join(bpio.getExecutableDir(), '..'))
    expected_src_dir = os.path.join(deploy.default_base_dir_portable(), 'src')
    if _Debug:
        lg.args(_DebugLevel, update_method=update_method, src_dir=src_dir_path, expected_src_dir=expected_src_dir)
    if bpio.portablePath(src_dir_path) != bpio.portablePath(expected_src_dir):
        if _Debug:
            lg.out(_DebugLevel, 'git_proc.sync SKIP, non standard sources location: %r' % src_dir_path)
        return

    def _reset_done(out, err, retcode, fetch_result):
        if _Debug:
            lg.args(_DebugLevel, retcode=retcode, fetch_result=fetch_result)
        if callback_func is None:
            return
        if retcode != 0:
            result = 'sync-error'
        else:
            if fetch_result == 'new-code':
                result = 'code-fetched'
            else:
                result = 'up-to-date'
        callback_func(result)

    def _rebase_done(out, err, retcode, fetch_result):
        if _Debug:
            lg.args(_DebugLevel, retcode=retcode, fetch_result=fetch_result)
        if callback_func is None:
            return
        out = strng.to_text(out)
        err = strng.to_text(err)
        if retcode != 0:
            result = 'sync-error'
        else:
            if fetch_result == 'new-code' or out.count('Changes from') or out.count('Fast-forwarded'):
                result = 'code-fetched'
            else:
                result = 'up-to-date'
        callback_func(result)

    def _fetch_done(out, err, retcode):
        if _Debug:
            lg.args(_DebugLevel, retcode=retcode)
        if retcode != 0:
            if callback_func:
                callback_func('sync-error')
            return
        out = strng.to_text(out)
        err = strng.to_text(err)
        fetch_result = 'fetch-ok'
        for ln in err.splitlines():
            if ln.count('master') and ln.count('->') and not ln.count('[up to date]'):
                fetch_result = 'new-code'
                break
        if out.count('Unpacking') or out.count('Updating') or out.count('Receiving') or out.count('Counting'):
            fetch_result = 'new-code'
        if _Debug:
            lg.args(_DebugLevel, fetch_result=fetch_result)
        if update_method == 'reset':
            run(['reset', '--hard', 'origin/master'], callback=lambda o, e, ret: _reset_done(o, e, ret, fetch_result))
        elif update_method == 'rebase':
            run(['rebase', 'origin/master', '-v'], callback=lambda o, e, ret: _rebase_done(o, e, ret, fetch_result))
        else:
            raise Exception('invalid update method: %s' % update_method)

    run(['fetch', '--all', '-v'], callback=_fetch_done)


#------------------------------------------------------------------------------


def run(cmdargs, base_dir=None, git_bin=None, env=None, callback=None):
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.run')
    base_dir = base_dir or os.path.abspath(os.path.join(bpio.getExecutableDir(), '..'))
    if bpio.Windows():
        cmd = [
            'git',
        ] + cmdargs
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
        cmd = [
            git_exe,
        ] + cmdargs
    else:
        cmd = [
            git_bin or 'git',
        ] + cmdargs
    execute(cmd, callback=callback, base_dir=base_dir, env=env)


#------------------------------------------------------------------------------


def execute_in_shell(cmdargs, base_dir=None):
    global _CurrentProcess
    from bitdust.system import nonblocking
    import subprocess
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.execute_in_shell: "%s"' % (' '.join(cmdargs)))
    write2log('\nEXECUTE in shell: %s, base_dir=%s\n' % (cmdargs, base_dir))
    _CurrentProcess = nonblocking.Popen(
        cmdargs,
        shell=True,
        cwd=bpio.portablePath(base_dir),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    result = _CurrentProcess.communicate()
    out_data = result[0]
    err_data = result[1]
    write2log('STDOUT:\n%s\nSTDERR:\n%s\n' % (strng.to_text(out_data), strng.to_text(err_data)))
    returncode = _CurrentProcess.returncode
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.execute_in_shell returned: %s, stdout bytes: %d, stderr bytes: %d' % (returncode, len(out_data), len(err_data)))
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
                lg.out(_DebugLevel, '    [git:err]: %s' % strng.to_text(line))

    def outReceived(self, inp):
        self.out += inp
        for line in inp.splitlines():
            if _Debug:
                lg.out(_DebugLevel, '    [git:out]: %s' % strng.to_text(line))

    def processEnded(self, reason):
        if _Debug:
            lg.out(_DebugLevel, 'git process FINISHED : %s' % reason.value.exitCode)
        for cb in self.callbacks:
            cb(self.out, self.err, reason.value.exitCode)


def execute(cmdargs, base_dir=None, process_protocol=None, env=None, callback=None):
    global _CurrentProcess
    if _Debug:
        lg.out(_DebugLevel, 'git_proc.execute: "%s" in %s' % (' '.join(cmdargs), base_dir))
    write2log('\nEXECUTE: %s, base_dir=%s\n' % (cmdargs, base_dir))
    executable = cmdargs[0]
    if bpio.Windows():
        from twisted.internet import _dumbwin32proc
        real_CreateProcess = _dumbwin32proc.win32process.CreateProcess  # @UndefinedVariable

        def fake_createprocess(_appName, _commandLine, _processAttributes, _threadAttributes, _bInheritHandles, creationFlags, _newEnvironment, _currentDirectory, startupinfo):
            import win32con  # @UnresolvedImport
            import subprocess
            flags = win32con.CREATE_NO_WINDOW
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # @UndefinedVariable
            startupinfo.wShowWindow = subprocess.SW_HIDE  # @UndefinedVariable
            return real_CreateProcess(_appName, _commandLine, _processAttributes, _threadAttributes, _bInheritHandles, flags, _newEnvironment, _currentDirectory, startupinfo)

        setattr(_dumbwin32proc.win32process, 'CreateProcess', fake_createprocess)

    if process_protocol is None:
        process_protocol = GitProcessProtocol(callbacks=[
            lambda out, err, ret_code: write2log('STDOUT:\n%s\nSTDERR:\n%s\n' % (strng.to_text(out), strng.to_text(err))),
            callback,
        ])
    try:
        _CurrentProcess = reactor.spawnProcess(  # @UndefinedVariable
            process_protocol, executable, cmdargs, path=base_dir, env=env
        )
    except:
        lg.exc()
        return None
    if bpio.Windows():
        setattr(_dumbwin32proc.win32process, 'CreateProcess', real_CreateProcess)
    return _CurrentProcess


#------------------------------------------------------------------------------

if __name__ == '__main__':
    bpio.init()
    lg.set_debug_level(18)

    def _result(res):
        print('RESULT:', res)
        reactor.stop()  # @UndefinedVariable

    reactor.callWhenRunning(sync, _result)  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable
